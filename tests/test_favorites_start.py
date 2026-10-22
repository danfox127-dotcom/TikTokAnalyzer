"""start.command and always-on.command, run against stand-in commands."""

import hashlib
import os
import plistlib
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

FAV = Path(__file__).resolve().parent.parent / "favorites"


def executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_both_scripts_parse():
    for name in ("start.command", "always-on.command"):
        subprocess.run(["bash", "-n", str(FAV / name)], check=True)


def test_the_launch_agent_opens_start_command_in_terminal_at_login(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    out = subprocess.run([str(FAV / "always-on.command"), "--print-plist"],
                         capture_output=True, check=True, env=env).stdout
    agent = plistlib.loads(out)
    assert agent["Label"] == "app.faves" and agent["RunAtLoad"] is True
    assert agent["ProgramArguments"][:3] == ["/usr/bin/open", "-a", "Terminal"]
    assert agent["ProgramArguments"][3].endswith("Library/Application Support/Faves/open-at-login.command")
    opener = subprocess.run([str(FAV / "always-on.command"), "--print-opener"],
                            capture_output=True, text=True, check=True, env=env).stdout
    assert "FAVES_AT_LOGIN=1 exec" in opener and str(FAV / "start.command") in opener


@pytest.fixture
def checkout(tmp_path):
    """A copy of start.command with a stand-in Python, browser and caffeinate."""
    root = tmp_path / "repo"
    (root / "favorites").mkdir(parents=True)
    shutil.copy(FAV / "start.command", root / "favorites" / "start.command")
    reqs = root / "favorites" / "requirements.txt"
    reqs.write_text("fastapi\n")
    venv = root / "favorites" / ".venv"
    log = tmp_path / "log"
    # uvicorn: fails the first time, stops cleanly the second.
    executable(venv / "bin" / "python",
               f'echo "python $*" >> "{log}"\n'
               f'n=$(cat "{tmp_path}/runs" 2>/dev/null || echo 0); echo $((n+1)) > "{tmp_path}/runs"\n'
               '[ "$n" -eq 0 ] && exit 1\nexit 0\n')
    (venv / ".requirements.sha").write_text(hashlib.sha256(reqs.read_bytes()).hexdigest())
    home = tmp_path / "home"
    home.mkdir()
    (home / ".favorites.env").write_text("# nothing switched on\n")
    bin_ = tmp_path / "bin"
    executable(bin_ / "open", f'echo "open $*" >> "{log}"\n')
    executable(bin_ / "caffeinate", f'echo "caffeinate $*" >> "{log}"\n')
    executable(bin_ / "sleep", "exit 0\n")
    # Not running at first; then up, so the browser step can run.
    executable(bin_ / "curl", f'n=$(cat "{tmp_path}/curls" 2>/dev/null || echo 0); echo $((n+1)) > "{tmp_path}/curls"\n'
                              '[ "$n" -eq 0 ] && exit 7\nexit 0\n')
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_}:{os.environ['PATH']}"}
    env.pop("FAVORITES_PORT", None)
    return root, env, log


def run(root, env):
    return subprocess.run(["bash", str(root / "favorites" / "start.command")], env=env,
                          capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)


def test_faves_starts_again_after_an_error_and_keeps_the_mac_awake(checkout):
    root, env, log = checkout
    result = run(root, env)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = log.read_text().splitlines()
    assert sum(l.startswith("python -m uvicorn favorites.app:app") for l in lines) == 2
    assert "Starting it again" in result.stdout
    assert any(l.startswith("caffeinate -s -w ") for l in lines)
    assert "open http://localhost:8000" in lines


def test_at_login_it_opens_no_browser_tab(checkout):
    root, env, log = checkout
    result = run(root, {**env, "FAVES_AT_LOGIN": "1"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(l.startswith("open ") for l in log.read_text().splitlines())
