"""Ready-made iPhone shortcuts, with this Mac's address and password inside.

Building a shortcut by hand is ten fiddly steps; installing one is a tap.
Faves builds two, signs them with the Mac's own ``shortcuts sign`` (iOS only
imports signed shortcuts) and offers them on the Keep it in sync page:

- **Save to Faves** -- in the share sheet of any app.
- **Save copied link** -- the same, for the link you just copied; give it to
  Back Tap (double-tap the back of the phone).

Both first add the link to ``Faves inbox.txt`` in iCloud Drive (see
favorites/inbox.py) and only then send it to Faves. Writing the file needs no
connection, so a link shared while the Mac is asleep is not lost: Faves reads
the inbox when it can and saves whatever never arrived.

The file format is Apple's, unpublished; these are the actions and keys the
Shortcuts app itself writes.
"""

from __future__ import annotations

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
}


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


def build(name: str, address: str, password: Optional[str]) -> dict:
    """The shortcut as a plist dictionary (unsigned)."""
    source, in_share_sheet = SHORTCUTS[name]
    actions = []
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
    headers = [_field("Authorization", _text(f"Bearer {password}"))] if password else []
    actions.append(_action(
        "downloadurl", WFURL=f"{address.rstrip('/')}/save", WFHTTPMethod="POST",
        ShowHeaders=bool(headers), WFHTTPHeaders=_dictionary(*headers),
        WFHTTPBodyType="JSON", WFJSONValues=_dictionary(_field("url", _text(OBJ, {"{0, 1}": link})))))
    # 4. A word to say it worked.
    actions.append(_action("notification", WFNotificationActionTitle="Faves",
                           WFNotificationActionBody="Saved to Faves ✓"))

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
