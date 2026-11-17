"""What a phone number says about itself -- worked out here, never looked up.

Uses Google's libphonenumber data (the ``phonenumbers`` package), the same data
Android uses to format numbers. Everything comes from how numbering plans are
laid out, so a number never leaves this computer:

- whether it's a real, dialable number at all;
- its country, and the area its prefix was assigned to;
- the kind of line: mobile, landline, toll-free, internet (VoIP)...;
- the carrier the number range was first given to;
- its time zone.

What it can't say is who has the number now. The area is where the *prefix* was
assigned, not where anyone is; numbers move between carriers. Services that
name a number's owner are data brokers, and Footprint doesn't use them.
"""

from __future__ import annotations

import os
import re
from typing import Optional

PLAIN_TYPES = {
    "MOBILE": "Mobile", "FIXED_LINE": "Landline", "FIXED_LINE_OR_MOBILE": "Landline or mobile",
    "TOLL_FREE": "Toll-free", "PREMIUM_RATE": "Premium-rate", "SHARED_COST": "Shared-cost",
    "VOIP": "Internet phone (VoIP)", "PERSONAL_NUMBER": "Personal number (forwards elsewhere)",
    "PAGER": "Pager", "UAN": "Company number", "VOICEMAIL": "Voicemail", "UNKNOWN": "Unknown",
}


def default_region() -> str:
    """Numbers without a +country code are read as this country's."""
    return (os.environ.get("FOOTPRINT_PHONE_REGION") or "US").upper()


def facts(text: str, region: Optional[str] = None) -> dict:
    """Everything the number says about itself, in plain words."""
    text = (text or "").strip()
    region = (region or default_region()).upper()
    out: dict = {"input": text, "valid": False, "assumed_region": None}
    try:
        import phonenumbers
        from phonenumbers import carrier, geocoder, timezone
    except ImportError:
        out["summary"] = ("Phone lookups need the phonenumbers package: "
                          "pip install -r footprint/requirements.txt")
        return out
    if not text.startswith("+") and not text.startswith("00"):
        out["assumed_region"] = region
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        out["summary"] = "This doesn't look like a phone number."
        return out

    fmt = phonenumbers.PhoneNumberFormat
    out["international"] = phonenumbers.format_number(number, fmt.INTERNATIONAL)
    out["e164"] = phonenumbers.format_number(number, fmt.E164)
    if not phonenumbers.is_valid_number(number):
        out["summary"] = (f"{out['international']} isn't a valid number"
                          + (f" in {region} — if it's from another country, start it with + and "
                             f"the country code." if out["assumed_region"] else "."))
        return out

    out["valid"] = True
    out["national"] = phonenumbers.format_number(number, fmt.NATIONAL)
    kind = phonenumbers.number_type(number)
    type_name = next((k for k, v in vars(phonenumbers.PhoneNumberType).items() if v == kind), "UNKNOWN")
    out["type"] = PLAIN_TYPES.get(type_name, "Unknown")
    out["country"] = geocoder.country_name_for_number(number, "en") or None
    place = geocoder.description_for_number(number, "en") or None
    out["area"] = place if place and place != out["country"] else None
    out["carrier"] = carrier.name_for_number(number, "en") or None
    zones = [z for z in timezone.time_zones_for_number(number) if z != "Etc/Unknown"]
    # A toll-free number "is in" every zone of its country, which says nothing.
    out["time_zones"] = zones if 0 < len(zones) <= 3 else []
    out["tel"] = "tel:" + out["e164"]

    parts = [out["type"]]
    where = ", ".join(p for p in (out["area"], out["country"]) if p)
    if where:
        parts.append(where)
    if out["carrier"]:
        parts.append(f"first issued by {out['carrier']}")
    out["summary"] = " · ".join(parts)
    return out


def find_in(text: str) -> list[str]:
    """Phone-like runs in free text (a bio, a page), as written."""
    found = []
    for m in re.finditer(r"(?<![\w+])\+?\(?\d[\d\s().\-]{6,18}\d", text or ""):
        digits = re.sub(r"\D", "", m.group(0))
        if 7 <= len(digits) <= 15:
            found.append(m.group(0).strip())
    return found
