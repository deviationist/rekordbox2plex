"""Resolve an artist's identity from Plex's own agent match, most-aligned-with-Plex.

Plex's agent match (`Artist.matches`) returns ranked candidates — each a canonical
**name** + an ``mbid://`` GUID + a confidence score — but **no artwork** (you'd only
get art via ``fixMatch``, which rebinds metadata). So we use that match to obtain the
identity Plex itself would pick: the MBID (for MBID-keyed art providers) and the
canonical name (to verify name-based provider hits, killing fuzzy mismatches). A raw
MusicBrainz text search is the fallback when Plex has no confident match.
"""

from dataclasses import dataclass
from typing import Any, Optional

from ..utils.logger import logger

_MUSIC_AGENT = "tv.plex.agents.music"


@dataclass
class PlexMatch:
    """Plex's confident identification of an artist."""

    name: Optional[str]  # canonical artist name as Plex resolved it
    mbid: Optional[str]  # MusicBrainz ID (None if the top match had no mbid:// guid)


class PlexMbidResolver:
    """Top confident match (name + MBID) from Plex's agent for a live plexapi Artist."""

    def __init__(self, min_score: int = 90) -> None:
        self.min_score = min_score

    def match(self, plex_artist: Any) -> Optional[PlexMatch]:
        """Return Plex's top confident (score ≥ min_score) match, or None."""
        if plex_artist is None:
            return None
        try:
            matches = plex_artist.matches(agent=_MUSIC_AGENT)
        except Exception as e:  # noqa: BLE001 - any plexapi/agent failure → no match
            logger.debug(
                f"[dim]plex match failed for {getattr(plex_artist, 'title', '?')!r}: {e}"
            )
            return None
        for m in matches or []:
            if int(getattr(m, "score", 0) or 0) < self.min_score:
                continue
            guid = str(getattr(m, "guid", "") or "")
            mbid = guid[len("mbid://") :] if guid.startswith("mbid://") else None
            name = getattr(m, "name", None) or None
            if mbid or name:
                return PlexMatch(name=name, mbid=mbid)
        return None

    def mbid_for(self, plex_artist: Any) -> Optional[str]:
        m = self.match(plex_artist)
        return m.mbid if m else None
