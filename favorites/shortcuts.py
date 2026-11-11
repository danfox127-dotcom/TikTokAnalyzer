"""Ready-made iPhone shortcuts, with this Mac's address and password inside.

Building a shortcut by hand is ten fiddly steps; installing one is a tap.
Faves builds three, signs them with the Mac's own ``shortcuts sign`` (iOS only
imports signed shortcuts) and offers them on the Set up this phone page:

- **Save to Faves** -- in the share sheet of any app.
- **Save copied link** -- the same, for the link you just copied; give it to
  Back Tap, the Action Button or Control Center.
- **Auto-save copied link** -- silent, for an iPhone Automation that runs it
  when you leave TikTok, Instagram or YouTube: whatever link you copied there
  is kept, and one already kept is skipped.

The first two add the link to ``Faves inbox.txt`` in iCloud Drive (see
favorites/inbox.py) and only then send it to Faves. Writing the file needs no
connection, so a link shared while the Mac is asleep is not lost: Faves reads
the inbox when it can and saves whatever never arrived. The automatic one
skips the inbox: it runs every time you leave the app, mostly with nothing
new, and the inbox would fill with repeats.

Only a Mac can sign, so once the library is in the cloud the Mac also signs
them for the cloud copy and leaves them in the library (``store``), and a
phone set up away from the Mac downloads them from there.

The file format is Apple's, unpublished; these are the actions and keys the
Shortcuts app itself writes.
"""

from __future__ import annotations

import hashlib
import plistlib
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

INBOX_FILE = "Faves inbox.txt"
OBJ = "￼"  # where a variable sits in a Shortcuts text field

#: name -> (where the link comes from, shown in the share sheet?)
SHORTCUTS = {
    "Save to Faves": ("share", True),
    "Save copied link": ("clipboard", False),
    "Auto-save copied link": ("auto", False),
}

#: Changes whenever the actions do, so the Mac re-signs what it stored.
VERSION = "3"


def _text(string: str, attachments: Optional[dict] = None) -> dict:
    value: dict = {"string": string}
    if attachments:
        value["attachmentsByRange"] = attachments
    return {"Value": value, "WFSerializationType": "WFTextTokenString"}


def _field(key: str, value: dict) -> dict:
    return {"WFItemType": 0, "WFKey": _text(key), "WFValue": value}


def _dictionary(*fields: dict) -> dict:
    return {"Value": {"WFDictionaryFieldValueItems": list(fields)},
            "WFSerializationType": "WFDictionaryFieldValue"}


def _action(identifier: str, **params) -> dict:
    return {"WFWorkflowActionIdentifier": f"is.workflow.actions.{identifier}",
            "WFWorkflowActionParameters": params}


def _ref(output: str, uuid_: str) -> dict:
    """A previous action's result, as an action's input."""
    return {"Value": {"Type": "ActionOutput", "OutputName": output, "OutputUUID": uuid_},
            "WFSerializationType": "WFTextTokenAttachment"}


def _post(address: str, password: Optional[str], link: dict, query: str = "") -> dict:
    """Send one link to Faves: POST /save with the password."""
    headers = [_field("Authorization", _text(f"Bearer {password}"))] if password else []
    return _action(
        "downloadurl", WFURL=f"{address.rstrip('/')}/save{query}", WFHTTPMethod="POST",
        ShowHeaders=bool(headers), WFHTTPHeaders=_dictionary(*headers),
        WFHTTPBodyType="JSON", WFJSONValues=_dictionary(_field("url", _text(OBJ, {"{0, 1}": link}))))


def _auto(address: str, password: Optional[str]) -> list[dict]:
    """Every link on the clipboard, sent quietly; Faves keeps only video links
    it doesn't already have (``/save?auto=1``), so a repeat costs nothing."""
    clip, links, loop = (str(uuid.uuid4()).upper() for _ in range(3))
    return [
        _action("getclipboard", UUID=clip),
        _action("detect.link", UUID=links, WFInput=_ref("Clipboard", clip)),
        _action("repeat.each", GroupingIdentifier=loop, WFControlFlowMode=0, WFInput=_ref("URLs", links)),
        _post(address, password, {"Type": "Variable", "VariableName": "Repeat Item"}, "?auto=1"),
        _action("repeat.each", GroupingIdentifier=loop, WFControlFlowMode=2, UUID=str(uuid.uuid4()).upper()),
    ]


def build(name: str, address: str, password: Optional[str]) -> dict:
    """The shortcut as a plist dictionary (unsigned)."""
    source, in_share_sheet = SHORTCUTS[name]
    actions = []
    if source == "auto":
        return _workflow(_auto(address, password), in_share_sheet)
    if source == "share":
        link = {"Type": "ExtensionInput"}
    else:
        clip = str(uuid.uuid4()).upper()
        actions.append(_action("getclipboard", UUID=clip))
        link = {"Type": "ActionOutput", "OutputName": "Clipboard", "OutputUUID": clip}

    # 1. One line for the inbox: when, a tab, the link.
    line = str(uuid.uuid4()).upper()
    when = {"Type": "CurrentDate", "Aggrandizements": [{
        "Type": "WFDateFormatVariableAggrandizement",
        "WFDateFormatStyle": "ISO 8601", "WFISO8601IncludeTime": True}]}
    actions.append(_action("gettext", UUID=line, WFTextActionText=_text(
        f"{OBJ}\t{OBJ}", {"{0, 1}": when, "{2, 1}": link})))
    # 2. Into the inbox in iCloud Drive -- works with no connection at all.
    actions.append(_action(
        "file.append", WFFilePath=INBOX_FILE, WFAppendOnNewLine=True,
        WFInput={"Value": {"Type": "ActionOutput", "OutputName": "Text", "OutputUUID": line},
                 "WFSerializationType": "WFTextTokenAttachment"}))
    # 3. Then straight to Faves.
    actions.append(_post(address, password, link))
    # 4. A word to say it worked.
    actions.append(_action("notification", WFNotificationActionTitle="Faves",
                           WFNotificationActionBody="Saved to Faves ✓"))
    return _workflow(actions, in_share_sheet)


def _workflow(actions: list[dict], in_share_sheet: bool) -> dict:
    return {
        "WFWorkflowClientVersion": "2302.0.4",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": ["ActionExtension"] if in_share_sheet else [],
        "WFWorkflowInputContentItemClasses": ["WFURLContentItem", "WFStringContentItem"],
        "WFWorkflowHasShortcutInputVariables": in_share_sheet,
        "WFWorkflowOutputContentItemClasses": [],
        "WFQuickActionSurfaces": [],
        "WFWorkflowActions": actions,
    }


def can_sign() -> bool:
    """Is this a Mac with the Shortcuts command (macOS 12 or later)?"""
    return shutil.which("shortcuts") is not None


class CannotSign(RuntimeError):
    """Signing failed; the message says why, in plain words."""


_signed: dict[tuple, bytes] = {}


def signed(name: str, address: str, password: Optional[str]) -> bytes:
    """The shortcut, signed so an iPhone will import it. Cached per settings."""
    key = (name, address, password)
    if key in _signed:
        return _signed[key]
    if not can_sign():
        raise CannotSign("This Mac can't prepare shortcuts: it needs macOS 12 or later.")
    with tempfile.TemporaryDirectory() as tmp:
        unsigned, out = Path(tmp) / "in.shortcut", Path(tmp) / "out.shortcut"
        unsigned.write_bytes(plistlib.dumps(build(name, address, password), fmt=plistlib.FMT_BINARY))
        try:
            done = subprocess.run(["shortcuts", "sign", "--mode", "anyone",
                                   "--input", str(unsigned), "--output", str(out)],
                                  capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            raise CannotSign(f"Signing the shortcut failed ({exc}).") from exc
        if done.returncode != 0 or not out.exists():
            why = (done.stderr or done.stdout or "").strip().splitlines()[-1:] or ["no reason given"]
            raise CannotSign("macOS wouldn't sign the shortcut (" + why[0] + "). "
                             "Signing needs this Mac to be signed in to iCloud.")
        _signed[key] = out.read_bytes()
    return _signed[key]


def fingerprint(name: str, address: str, password: Optional[str]) -> str:
    """What a signed copy was made for: the actions, the address, the password."""
    return hashlib.sha256(f"{VERSION}\n{name}\n{address}\n{password or ''}".encode()).hexdigest()


def store(conn, slug: str, data: bytes, fingerprint_: str, made_at: str) -> None:
    """Keep a signed shortcut in the library, for the cloud copy to offer."""
    conn.execute(
        "INSERT INTO shortcut_files (slug, data, fingerprint, made_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (slug) DO UPDATE SET data = excluded.data,"
        " fingerprint = excluded.fingerprint, made_at = excluded.made_at",
        (slug, data, fingerprint_, made_at))
    conn.commit()


def stored(conn, slug: str) -> Optional[tuple[bytes, str]]:
    """The signed shortcut the Mac left in the library, and its fingerprint."""
    row = conn.execute("SELECT data, fingerprint FROM shortcut_files WHERE slug = ?", (slug,)).fetchone()
    return (bytes(row["data"]), row["fingerprint"]) if row else None
