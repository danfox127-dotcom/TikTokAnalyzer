"""Transcripts, where they are legitimately available.

In practice that means YouTube, which publishes caption tracks through an API
intended for exactly this. TikTok and Instagram have no equivalent: getting
their spoken text would mean downloading the media and running speech
recognition over it, which their terms do not allow. This module therefore
returns ``None`` for those platforms rather than pretending otherwise.

``youtube-transcript-api`` is an optional dependency. Without it installed the
library works exactly as before, minus transcripts.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED = {"youtube"}
MAX_CHARS = 20_000


def available() -> bool:
    """True when the optional transcript dependency is importable."""
    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        return False
    return True


def fetch(platform: str, external_id: Optional[str], languages=("en",)) -> Optional[str]:
    """Best-effort transcript text. Returns ``None`` for anything unsupported."""
    if platform not in SUPPORTED or not external_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.debug("youtube-transcript-api not installed; skipping transcript")
        return None

    try:
        # The library's entry point was reshaped in v1.0 from a classmethod to
        # an instance method. Supporting both keeps this working across the
        # version someone happens to have installed.
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            parts = YouTubeTranscriptApi.get_transcript(external_id, languages=list(languages))
            chunks = [p.get("text", "") for p in parts]
        else:
            fetched = YouTubeTranscriptApi().fetch(external_id, languages=list(languages))
            chunks = [getattr(s, "text", "") for s in fetched]
    except Exception as exc:
        # No captions, age restriction, region block, rate limit -- all of these
        # are ordinary and none of them should fail a save.
        logger.debug("no transcript for %s: %s", external_id, exc)
        return None

    text = " ".join(c.strip() for c in chunks if c and c.strip())
    return text[:MAX_CHARS] or None
