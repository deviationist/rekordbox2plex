"""Split a multi-artist "collab" string into its component artists.

Plex's local agent makes one artist entity per album-artist string, so a track
tagged ``A, B, C`` becomes a single artist ``A, B, C`` that no image source has.
``split_collab`` splits **conservatively** — only on commas and ``feat./ft./
featuring`` — so genuine single names that merely contain ``&`` / ``/`` / ``x``
(e.g. ``Above & Beyond``, ``A/B Sides``, ``AC/DC``) are left intact.

``split_ambiguous`` is the opt-in, *last-resort* tier: it splits on ambiguous
separators like ``&`` / ``+`` that CAN join two artists but also appear inside
real names. It's only ever applied by the matcher to a component that already
missed every source as a whole, so genuine ``&``-artists (which resolve whole)
never reach it."""

import re
from typing import Iterable, List

_SPLIT = re.compile(
    r"\s*,\s*|\s+feat\.?\s+|\s+ft\.?\s+|\s+featuring\s+",
    re.IGNORECASE,
)


def split_collab(name: str):
    """Return the component artist names if ``name`` is a multi-artist collab
    string (2+ parts), else ``[]`` (not a collab — handle normally)."""
    parts = [p.strip() for p in _SPLIT.split(name or "") if p.strip()]
    return parts if len(parts) > 1 else []


def split_ambiguous(name: str, separators: Iterable[str]) -> List[str]:
    """Split ``name`` on the given ambiguous separators (e.g. ``["&", "+"]``),
    with **optional surrounding whitespace**, so both ``A + B`` and ``A+B`` break.

    Safety does NOT come from the split being conservative (it isn't) — it comes
    from the *caller*: this is only ever applied to a component that already missed
    every source as a whole, and each returned piece must then name-verify against
    a real source artist. So an over-eager split (e.g. ``AT&T`` → ``AT``/``T``)
    just yields pieces that don't resolve → no image, not a wrong one. Empty pieces
    are dropped and we require 2+ real parts, so ``D+`` / ``C++`` don't split.
    Returns the parts if it splits into 2+, else ``[]``."""
    seps = [s.strip() for s in separators if s and s.strip()]
    if not seps:
        return []
    pattern = "|".join(r"\s*" + re.escape(s) + r"\s*" for s in seps)
    parts = [p.strip() for p in re.split(pattern, name or "") if p.strip()]
    return parts if len(parts) > 1 else []
