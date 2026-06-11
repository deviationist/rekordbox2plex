"""Pair lossy files with their lossless replacements by basename within a folder.

Shared by ``lossless-tags`` (copy the tags across) and ``rb-dates`` (carry the
Rekordbox "Date Added" across). A pair is a lossy file and a lossless file in the
**same directory** whose names match once the extension is stripped.
"""

import os
from typing import Dict, List, Optional, Tuple

# (lossy_path, lossless_path)
Pair = Tuple[str, str]


def classify_ext(
    ext: str, lossy_exts: Tuple[str, ...], lossless_exts: Tuple[str, ...]
) -> Optional[str]:
    ext = ext.lower()
    if ext in lossy_exts:
        return "lossy"
    if ext in lossless_exts:
        return "lossless"
    return None


def walk_pairs(
    root: str,
    lossy_exts: Tuple[str, ...],
    lossless_exts: Tuple[str, ...],
    ignore_case: bool = False,
) -> Tuple[List[Pair], List[str], List[Tuple[str, str]]]:
    """Walk ``root`` and return (pairs, unmatched, ambiguous).

    pairs: (lossy, lossless) where exactly one lossless sibling matched.
    unmatched: lossy files with no lossless sibling (the upgrade backlog).
    ambiguous: (lossy, reason) where more than one lossless sibling matched —
    skipped rather than guessed."""
    pairs: List[Pair] = []
    unmatched: List[str] = []
    ambiguous: List[Tuple[str, str]] = []

    for dirpath, _dirnames, filenames in os.walk(root):
        groups: Dict[str, Dict[str, List[str]]] = {}
        for fn in filenames:
            stem, ext = os.path.splitext(fn)
            kind = classify_ext(ext, lossy_exts, lossless_exts)
            if kind is None:
                continue
            key = stem.lower() if ignore_case else stem
            groups.setdefault(key, {"lossy": [], "lossless": []})[kind].append(
                os.path.join(dirpath, fn)
            )
        for grp in groups.values():
            for lossy in grp["lossy"]:
                losslesses = grp["lossless"]
                if not losslesses:
                    unmatched.append(lossy)
                elif len(losslesses) > 1:
                    names = ", ".join(os.path.basename(p) for p in losslesses)
                    ambiguous.append((lossy, f">1 lossless sibling ({names})"))
                else:
                    pairs.append((lossy, losslesses[0]))

    pairs.sort(key=lambda t: t[1].lower())
    unmatched.sort(key=str.lower)
    ambiguous.sort(key=lambda t: t[0].lower())
    return pairs, unmatched, ambiguous
