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
    """A copy of start.command with stand-ins for Python, the browser, curl,
    lsof and caffeinate. ``codes`` lists the exit code of each uvicorn run; a
    run that ends with 0 first makes Faves "answer" (the ``up`` file)."""
    root = tmp_path / "repo"
    (root / "favorites").mkdir(parents=True)
    shutil.copy(FAV / "start.command", root / "favorites" / "start.command")
    reqs = root / "favorites" / "requirements.txt"
    reqs.write_text("fastapi\n")
    venv = root / "favorites" / ".venv"
    log, up = tmp_path / "log", tmp_path / "up"
    executable(venv / "bin" / "python",
               f'echo "python $*" >> "{log}"\n'
               f'n=$(cat "{tmp_path}/runs" 2>/dev/null || echo 0); echo $((n+1)) > "{tmp_path}/runs"\n'
               f'code=$(cut -d, -f$((n+1)) "{tmp_path}/codes")\n'
               f'[ "$code" = 0 ] && {{ touch "{up}"; /bin/sleep 1.5; }}\n'
               'exit "$code"\n')
    (venv / ".requirements.sha").write_text(hashlib.sha256(reqs.read_bytes()).hexdigest())
    home = tmp_path / "home"
    home.mkdir()
    (home / ".favorites.env").write_text("# nothing switched on\n")
    bin_ = tmp_path / "bin"
    executable(bin_ / "open", f'echo "open $*" >> "{log}"\n')
    executable(bin_ / "caffeinate", f'echo "caffeinate $*" >> "{log}"\n')
    # Skip the 10-second restart wait; shorten the browser-tab poll.
    executable(bin_ / "sleep", '[ "$1" = 10 ] && exit 0\n[ "$1" = 0.5 ] && exec /bin/sleep 0.1\nexec /bin/sleep "$@"\n')
    executable(bin_ / "curl", f'[ -f "{up}" ]\n')
    # What holds the port: the PID in holder_pid, while that process lives.
    executable(bin_ / "lsof", f'[ -f "{tmp_path}/also_up" ] && touch "{up}"\n'
                              f'pid=$(cat "{tmp_path}/holder_pid" 2>/dev/null) && kill -0 "$pid" 2>/dev/null && echo "$pid"\n'
                              'exit 0\n')
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_}:{os.environ['PATH']}"}
    env.pop("FAVORITES_PORT", None)

    def run(codes, **extra):
        (tmp_path / "codes").write_text(codes)
        return subprocess.run(["bash", str(root / "favorites" / "start.command")], env={**env, **extra},
                              capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)

    def lines():
        return log.read_text().splitlines() if log.exists() else []

    holders = []

    def hold_port(command_line):
        proc = subprocess.Popen(["bash", "-c", f'exec -a "{command_line}" /bin/sleep 300'])
        holders.append(proc)
        (tmp_path / "holder_pid").write_text(str(proc.pid))
        return proc

    yield run, lines, hold_port, tmp_path
    for proc in holders:
        proc.kill()
        proc.wait()


def uvicorn_runs(lines):
    return sum(l.startswith("python -m uvicorn favorites.app:app") for l in lines())


def test_faves_starts_again_after_an_error_and_keeps_the_mac_awake(checkout):
    run, lines, _, _ = checkout
    result = run("1,0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert uvicorn_runs(lines) == 2 and "Starting it again" in result.stdout
    assert any(l.startswith("caffeinate -s -w ") for l in lines())
    assert "open http://localhost:8000" in lines()


def test_at_login_it_opens_no_browser_tab(checkout):
    run, lines, _, _ = checkout
    result = run("0", FAVES_AT_LOGIN="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(l.startswith("open ") for l in lines())


def test_it_gives_up_after_three_failed_starts_instead_of_looping(checkout):
    run, lines, _, _ = checkout
    result = run("3,3,3,3,3")
    assert result.returncode == 1
    assert uvicorn_runs(lines) == 3 and "three times in a row" in result.stdout


def test_a_stuck_older_faves_is_stopped_and_replaced(checkout):
    run, lines, hold_port, _ = checkout
    stuck = hold_port("python -m uvicorn favorites.app:app --port 8000")
    result = run("0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"older copy of Faves (process {stuck.pid}) is stuck" in result.stdout
    assert stuck.wait(timeout=10) is not None and uvicorn_runs(lines) == 1


def test_another_program_on_the_port_is_named_not_stopped(checkout):
    run, lines, hold_port, _ = checkout
    other = hold_port("nginx")
    result = run("0")
    assert result.returncode == 1
    assert "already in use by another program" in result.stdout and "nginx" in result.stdout
    assert "FAVORITES_PORT=8001" in result.stdout
    assert other.poll() is None and uvicorn_runs(lines) == 0


def test_a_faves_already_answering_in_another_window_is_left_alone(checkout):
    run, lines, hold_port, tmp_path = checkout
    other = hold_port("python -m uvicorn favorites.app:app --port 8000")
    (tmp_path / "also_up").touch()  # it finishes starting while this window gets ready
    result = run("0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already running in another window" in result.stdout
    assert other.poll() is None and uvicorn_runs(lines) == 0
