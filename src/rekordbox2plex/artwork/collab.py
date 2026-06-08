"""Split a multi-artist "collab" string into its component artists.

Plex's local agent makes one artist entity per album-artist string, so a track
tagged ``A, B, C`` becomes a single artist ``A, B, C`` that no image source has.

Two tiers, both **fully configurable** (the lists come from config):
- ``split_collab`` — the primary, always-on separators (default comma + ``feat./
  ft./featuring``). Applied first; each component is then resolved.
- ``split_ambiguous`` — the opt-in, *last-resort* separators (``&`` / ``+`` /
  ``x`` / ``vs`` …) that CAN join two artists but also appear inside real names.
  Only ever applied by the matcher to a component that already missed every source
  as a whole, so genuine ``&``-artists (which resolve whole) never reach it.

Separator regex is shared: a **word** separator (``feat``, ``x``, ``vs``) requires
surrounding whitespace (and tolerates a trailing dot, e.g. ``feat.``) so it never
matches inside a token (``Aphex Twin``, ``Max``); a **symbol** separator (``,``,
``&``, ``+``) allows optional whitespace, so both ``A + B`` and ``A+B`` split."""

import re
from typing import Iterable, List, Optional

#: default primary (always-on) separators — override via ARTIST_COLLAB_PRIMARY_SEPARATORS
DEFAULT_PRIMARY_SEPARATORS = [",", "feat", "ft", "featuring"]


def _sep_pattern(sep: str) -> str:
    """Regex fragment for one separator (word vs symbol — see module docstring)."""
    if sep.isalnum():  # word separator: needs spaces, tolerate a trailing dot
        return r"\s+" + re.escape(sep) + r"\.?\s+"
    return r"\s*" + re.escape(sep) + r"\s*"  # symbol separator: optional spaces


def _split_on(name: str, separators: Iterable[str]) -> List[str]:
    seps = [s.strip() for s in separators if s and s.strip()]
    if not seps:
        return []
    pattern = "|".join(_sep_pattern(s) for s in seps)
    parts = [
        p.strip()
        for p in re.split(pattern, name or "", flags=re.IGNORECASE)
        if p.strip()
    ]
    return parts if len(parts) > 1 else []


def split_collab(name: str, separators: Optional[Iterable[str]] = None):
    """Return the component artist names if ``name`` splits on the (configurable)
    primary separators into 2+ parts, else ``[]`` (not a collab — handle normally)."""
    return _split_on(
        name, DEFAULT_PRIMARY_SEPARATORS if separators is None else separators
    )


def split_ambiguous(name: str, separators: Iterable[str]) -> List[str]:
    """Split ``name`` on the given opt-in ambiguous separators (e.g.
    ``["&", "+", "x"]``). Returns the parts if it splits into 2+, else ``[]``.

    Safety does NOT come from the split being conservative — it comes from the
    *caller*: this is only applied to a component that already missed every source
    as a whole, and each piece must then name-verify against a real source artist.
    So an over-eager split (e.g. ``AT&T`` → ``AT``/``T``) just yields pieces that
    don't resolve → no image, not a wrong one. Empty pieces are dropped and 2+ real
    parts are required, so ``D+`` / ``C++`` don't split; word separators (``x``/
    ``vs``) need spaces on both sides, so ``Aphex Twin`` is safe but ``A x B`` is not.
    """
    return _split_on(name, separators)
