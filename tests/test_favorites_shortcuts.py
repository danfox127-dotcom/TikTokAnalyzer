"""The ready-made iPhone shortcuts, and the page that offers them."""

import os
import plistlib
import stat

import pytest
from fastapi.testclient import TestClient

from favorites import app as app_module
from favorites import shortcuts
from favorites.app import app


def actions(workflow):
    return [(a["WFWorkflowActionIdentifier"].rsplit(".", 1)[-1] if "file." not in a["WFWorkflowActionIdentifier"]
             else "file.append", a["WFWorkflowActionParameters"]) for a in workflow["WFWorkflowActions"]]


class TestBuild:
    def test_save_to_faves_writes_the_inbox_first_then_sends_to_faves(self):
        workflow = plistlib.loads(plistlib.dumps(
            shortcuts.build("Save to Faves", "http://100.1.2.3:8000", "sesame"), fmt=plistlib.FMT_BINARY))
        steps = actions(workflow)
        assert [name for name, _ in steps] == ["gettext", "file.append", "downloadurl", "notification"]
        assert workflow["WFWorkflowTypes"] == ["ActionExtension"]
        line = steps[0][1]["WFTextActionText"]["Value"]
        assert line["string"] == "￼\t￼"
        assert line["attachmentsByRange"]["{0, 1}"]["Type"] == "CurrentDate"
        assert line["attachmentsByRange"]["{2, 1}"] == {"Type": "ExtensionInput"}
        assert steps[1][1]["WFFilePath"] == "Faves inbox.txt"
        assert steps[1][1]["WFInput"]["Value"]["OutputUUID"] == steps[0][1]["UUID"]
        send = steps[2][1]
        assert (send["WFURL"], send["WFHTTPMethod"], send["WFHTTPBodyType"]) == (
            "http://100.1.2.3:8000/save", "POST", "JSON")
        [header] = send["WFHTTPHeaders"]["Value"]["WFDictionaryFieldValueItems"]
        assert header["WFKey"]["Value"]["string"] == "Authorization"
        assert header["WFValue"]["Value"]["string"] == "Bearer sesame"
        [field] = send["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]
        assert field["WFKey"]["Value"]["string"] == "url"
        assert field["WFValue"]["Value"]["attachmentsByRange"]["{0, 1}"] == {"Type": "ExtensionInput"}

    def test_save_copied_link_starts_from_the_clipboard(self):
        workflow = shortcuts.build("Save copied link", "http://100.1.2.3:8000", None)
        steps = actions(workflow)
        assert steps[0][0] == "getclipboard" and workflow["WFWorkflowTypes"] == []
        clip = {"Type": "ActionOutput", "OutputName": "Clipboard", "OutputUUID": steps[0][1]["UUID"]}
        assert steps[1][1]["WFTextActionText"]["Value"]["attachmentsByRange"]["{2, 1}"] == clip
        assert steps[3][1]["WFHTTPHeaders"]["Value"]["WFDictionaryFieldValueItems"] == []  # no password


@pytest.fixture
def fake_shortcuts_command(tmp_path, monkeypatch):
    """A stand-in for macOS's `shortcuts sign`: copies the input to the output."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    cmd = bin_ / "shortcuts"
    cmd.write_text('#!/bin/bash\nwhile [ $# -gt 0 ]; do case "$1" in --input) i="$2"; shift;; '
                   '--output) o="$2"; shift;; esac; shift; done\ncp "$i" "$o"\n')
    cmd.chmod(cmd.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    shortcuts._signed.clear()
    return cmd


@pytest.fixture
def phone(tmp_path, monkeypatch):
    monkeypatch.setenv("FAVORITES_DB", str(tmp_path / "lib.db"))
    monkeypatch.setenv("FAVORITES_TOKEN", "sesame")
    monkeypatch.setattr(app_module, "_tailscale_address", lambda: "100.101.150.74")
    # The library on the Mac, reached over Tailscale (see TestOnceInTheCloud).
    monkeypatch.setattr(app_module, "_cloud_address", lambda request: None)
    with TestClient(app, client=("100.88.36.117", 50000)) as c:
        yield c


class TestInstalling:
    def test_a_locked_phone_is_sent_to_unlock_first(self, phone, fake_shortcuts_command):
        assert phone.get("/shortcuts/save-to-faves.shortcut").status_code == 401
        page = phone.get("/sync").text
        assert "unlock it on the Keep page" in page and 'href="/shortcuts/' not in page

    def test_an_unlocked_phone_gets_the_shortcut_with_the_address_that_works_anywhere(
            self, phone, fake_shortcuts_command):
        phone.cookies.set(app_module.KEY_COOKIE, "sesame")
        page = phone.get("/sync").text
        assert 'href="/shortcuts/save-to-faves.shortcut"' in page
        assert 'href="/shortcuts/save-copied-link.shortcut"' in page
        resp = phone.get("/shortcuts/save-to-faves.shortcut")
        assert resp.status_code == 200
        assert resp.headers["content-disposition"] == 'attachment; filename="Save to Faves.shortcut"'
        workflow = plistlib.loads(resp.content)
        send = [a for a in workflow["WFWorkflowActions"] if a["WFWorkflowActionIdentifier"].endswith("downloadurl")][0]
        assert send["WFWorkflowActionParameters"]["WFURL"] == "http://100.101.150.74:8000/save"

    def test_without_the_shortcuts_command_it_says_so_and_offers_the_steps(self, phone, monkeypatch):
        monkeypatch.setattr(shortcuts.shutil, "which", lambda name: None)
        shortcuts._signed.clear()
        phone.cookies.set(app_module.KEY_COOKIE, "sesame")
        resp = phone.get("/shortcuts/save-copied-link.shortcut")
        assert resp.status_code == 503 and "macOS 12" in resp.text
        page = phone.get("/sync").text
        assert "can't prepare ready-made shortcuts" in page and "Build it yourself" in page

    def test_unknown_shortcut(self, phone):
        assert phone.get("/shortcuts/nope.shortcut").status_code == 404


class TestOnceInTheCloud:
    """With the library in the cloud, the ready-made shortcuts save to the cloud
    copy: from anywhere, whether or not the Mac is awake."""

    @pytest.fixture
    def on_the_cloud_library(self, phone, monkeypatch):
        from favorites import cloud
        monkeypatch.setattr(app_module, "_cloud_address", lambda request: cloud.address())
        phone.cookies.set(app_module.KEY_COOKIE, "sesame")
        return phone

    def sends_to(self, data: bytes) -> str:
        workflow = plistlib.loads(data)
        send = [a for a in workflow["WFWorkflowActions"] if a["WFWorkflowActionIdentifier"].endswith("downloadurl")][0]
        return send["WFWorkflowActionParameters"]["WFURL"]

    def test_the_shortcuts_save_to_the_cloud(self, on_the_cloud_library, fake_shortcuts_command):
        for slug in ("save-to-faves", "save-copied-link"):
            resp = on_the_cloud_library.get(f"/shortcuts/{slug}.shortcut")
            assert resp.status_code == 200
            assert self.sends_to(resp.content) == "https://tik-tok-analyzer.vercel.app/save"
            # Still with the password, and still writing the inbox first.
            assert b"Bearer sesame" in resp.content and b"Faves inbox.txt" in resp.content

    def test_the_page_offers_them_with_the_cloud_address(self, on_the_cloud_library, fake_shortcuts_command):
        page = on_the_cloud_library.get("/sync").text
        assert 'href="/shortcuts/save-to-faves.shortcut"' in page
        assert "<code>https://tik-tok-analyzer.vercel.app/save</code>" in page
        assert "Your Faves address in the cloud" in page and "The shortcuts below save straight to it." in page
        assert "Tailscale address" not in page and "White screen" not in page
        assert "home-wi-fi-only" not in page and "only reach Faves while the Mac is awake" not in page

    def test_another_cloud_address_can_be_set(self, on_the_cloud_library, fake_shortcuts_command, monkeypatch):
        monkeypatch.setenv("FAVES_CLOUD_URL", "https://faves.example.com/")
        resp = on_the_cloud_library.get("/shortcuts/save-to-faves.shortcut")
        assert self.sends_to(resp.content) == "https://faves.example.com/save"


def test_the_cloud_address_is_used_once_the_library_is_there(monkeypatch):
    from starlette.requests import Request
    from favorites import cloud
    request = Request({"type": "http", "headers": [], "server": ("127.0.0.1", 8000), "path": "/"})
    for name in ("VERCEL", "FAVES_CLOUD", "FAVES_CLOUD_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert app_module._cloud_address(request) is None  # the library on the Mac
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@db.example/postgres")
    assert app_module._cloud_address(request) == cloud.ADDRESS
    monkeypatch.setenv("FAVES_CLOUD_URL", "https://faves.example.com/")
    assert app_module._cloud_address(request) == "https://faves.example.com"


def test_the_cloud_copy_names_its_own_address(monkeypatch):
    from starlette.requests import Request
    monkeypatch.setenv("FAVES_CLOUD", "1")
    request = Request({"type": "http", "headers": [(b"host", b"faves.example.vercel.app")],
                       "server": ("faves.example.vercel.app", 443), "scheme": "https", "path": "/"})
    assert app_module._cloud_address(request) == "https://faves.example.vercel.app"

