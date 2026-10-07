"""A rough time-zone guess from when an account's public posts go out.

People sleep, and the hours they don't post give their time zone away. Count
an account's public posts by hour of the day (in UTC), find the quietest five
hours in a row, and assume the middle of that stretch is about 4 am local
time. The difference is the UTC offset.

It is a guess, and it is presented as one:

- It needs at least 30 posts; fewer, and it says so instead of guessing.
- It is given as a band of plus or minus two hours, never narrower, and never
  as a place -- only examples of regions in that band.
- An account that posts around the clock (a scheduler, a team, a bot) has no
  quiet stretch, and the hint says the rhythm is unclear.

Only post times the platforms publish to anyone are used (GitHub, Bluesky,
Mastodon, Reddit -- see :mod:`footprint.profile`). For a brand, the same chart
answers a more useful question: when do our accounts actually post?
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

MIN_POSTS = 30
WINDOW = 5
ASSUMED_QUIET_CENTRE = 4.0  # local time, middle of the night

EXAMPLES = {
    -10: "Hawaii", -9: "Alaska", -8: "US Pacific", -7: "US Mountain",
    -6: "US Central, Mexico City", -5: "US Eastern, Bogotá, Lima", -4: "Atlantic Canada, Santiago",
    -3: "Brazil, Buenos Aires", -2: "mid-Atlantic", -1: "Azores, Cape Verde",
    0: "UK, Ireland, Portugal, West Africa", 1: "Central Europe, Nigeria",
    2: "Eastern Europe, South Africa, Egypt", 3: "Moscow, Istanbul, East Africa, Saudi Arabia",
    4: "Gulf states", 5: "Pakistan, India (UTC+5:30)", 6: "Bangladesh, India (UTC+5:30)",
    7: "Thailand, Vietnam, Jakarta", 8: "China, Singapore, Philippines, Perth", 9: "Japan, Korea",
    10: "Eastern Australia", 11: "Solomon Islands", 12: "New Zealand",
}


@dataclass
class Hint:
    posts: int
    platforms: list[str]
    histogram: list[int] = field(default_factory=lambda: [0] * 24)  # posts per UTC hour
    offset: Optional[int] = None
    low: Optional[int] = None
    high: Optional[int] = None
    strength: str = "none"            # clear | some | unclear | none
    summary: str = ""
    examples: str = ""
    quiet_utc: Optional[tuple[int, int]] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _offset_label(offset: int) -> str:
    return "UTC" if offset == 0 else f"UTC{'+' if offset > 0 else '−'}{abs(offset)}"


def _wrap(offset: float) -> int:
    o = round(offset)
    while o < -11:
        o += 24
    while o > 12:
        o -= 24
    return o


def hint(times: Iterable[str | datetime], platforms: Iterable[str] = ()) -> Hint:
    """The time-zone guess for a set of post times (ISO 8601 or datetimes, any zone)."""
    hours = []
    for t in times:
        try:
            dt = t if isinstance(t, datetime) else datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            continue
        hours.append(dt.astimezone(timezone.utc).hour)
    h = Hint(posts=len(hours), platforms=sorted(set(platforms)))
    for hour in hours:
        h.histogram[hour] += 1
    if len(hours) < MIN_POSTS:
        h.summary = (f"Not enough public posts to guess a time zone ({len(hours)} found; "
                     f"needs {MIN_POSTS}).")
        return h

    sums = [sum(h.histogram[(start + i) % 24] for i in range(WINDOW)) for start in range(24)]
    start = min(range(24), key=lambda s: (sums[s], s))
    quiet_share = sums[start] / len(hours)
    h.quiet_utc = (start, (start + WINDOW) % 24)
    centre = start + WINDOW / 2
    h.offset = _wrap(ASSUMED_QUIET_CENTRE - centre)
    h.low, h.high = h.offset - 2, h.offset + 2
    h.examples = EXAMPLES.get(h.offset, "")
    if quiet_share <= 0.04:
        h.strength = "clear"
    elif quiet_share <= 0.10:
        h.strength = "some"
    else:
        h.strength = "unclear"
    where = f" — for example {h.examples}" if h.examples else ""
    if h.strength == "unclear":
        h.summary = (f"Posts go out at all hours, so there's no clear daily rhythm to read "
                     f"(the quietest hours would suggest around {_offset_label(h.offset)}).")
    else:
        h.summary = (f"Around {_offset_label(h.offset)} (±2 hours){where}. A guess from "
                     f"{len(hours)} public posts: the account is quietest between "
                     f"{start:02d}:00 and {(start + WINDOW) % 24:02d}:00 UTC.")
    return h
