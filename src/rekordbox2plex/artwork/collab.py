"""Split a multi-artist "collab" string into its component artists.

Plex's local agent makes one artist entity per album-artist string, so a track
tagged ``A, B, C`` becomes a single artist ``A, B, C`` that no image source has.
We split **conservatively** — only on commas and ``feat./ft./featuring`` — so
genuine single names that merely contain ``&`` / ``/`` / ``x`` (e.g. ``Above &
Beyond``, ``A/B Sides``, ``AC/DC``) are left intact."""

import re

_SPLIT = re.compile(
    r"\s*,\s*|\s+feat\.?\s+|\s+ft\.?\s+|\s+featuring\s+",
    re.IGNORECASE,
)


def split_collab(name: str):
    """Return the component artist names if ``name`` is a multi-artist collab
    string (2+ parts), else ``[]`` (not a collab — handle normally)."""
    parts = [p.strip() for p in _SPLIT.split(name or "") if p.strip()]
    return parts if len(parts) > 1 else []
