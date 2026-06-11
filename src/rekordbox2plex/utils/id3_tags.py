"""Wholesale ID3 copy from a lossy source onto a lossless ID3-carrying target.

The ``lossless-tags`` command replaces a leftover lossy file (MP3) with a
lossless version (AIFF) of the same basename, but the freshly downloaded
lossless file usually has poor/no tags. Both MP3 and AIFF carry ID3v2, so we
copy the **entire** ID3 tag — every frame, including APIC artwork — from the
lossy file onto the lossless one, so the curated metadata survives the swap.
Tags remain the source of truth (see CLAUDE.md); this edits the file on disk,
never the Plex API.

mutagen's ``AIFF.save()`` is surgical: it rewrites only the ``ID3 `` chunk and
leaves the native ``NAME`` chunk and the audio (``SSND``) bytes intact. The
caller is responsible for backing the target up first (mutagen saves in place)
and for the subsequent ``NAME``-chunk fix via ``utils.aiff_chunks.rewrite_name``.
"""

from typing import Dict, Optional

import mutagen
from mutagen.aiff import AIFF
from mutagen.id3 import ID3

# Human-readable ID3 text frames surfaced in the dry-run diff table.
_DIFF_FRAMES = {
    "TIT2": "title",
    "TPE1": "artist",
    "TALB": "album",
    "TPE2": "albumartist",
    "TCON": "genre",
    "TRCK": "track",
}


def read_id3_fields(path: str) -> Dict[str, object]:
    """Read a small, human-readable subset of ID3 text frames for diff display.

    Works for both MP3 (ID3 at the file head) and AIFF (ID3 inside the ``ID3 ``
    chunk) via ``mutagen.File``. Returns ``{}`` if the file has no ID3 tag (or
    can't be parsed). Never raises. Includes a boolean ``has_artwork`` flag (any
    APIC frame present)."""
    tags = None
    try:
        audio = mutagen.File(path)
        tags = getattr(audio, "tags", None)
    except Exception:  # noqa: BLE001 - unparseable; diff is best-effort
        tags = None
    if not tags:
        # Fallback for files mutagen.File can't type (e.g. a tag-only MP3 with no
        # decodable audio frames): read the bare ID3 tag from the file head.
        try:
            tags = ID3(path)
        except Exception:  # noqa: BLE001 - no ID3 tag at all
            return {}
    out: Dict[str, object] = {}
    for fid, label in _DIFF_FRAMES.items():
        frame = tags.get(fid)
        text = getattr(frame, "text", None)
        out[label] = str(text[0]) if text else None
    out["has_artwork"] = bool(tags.getall("APIC"))
    return out


def copy_id3_wholesale(src_path: str, dst_path: str, v2_version: int = 3) -> str:
    """Replace ``dst``'s entire ID3 tag with ``src``'s (all frames incl. APIC).

    ``src`` is a lossy ID3-bearing file (MP3); ``dst`` an AIFF/AIFF-C. Any
    pre-existing ID3 on ``dst`` is cleared first (wholesale replace). Saves in
    place — the caller MUST snapshot ``dst`` beforehand. Returns the new ``TIT2``
    text ("" if none) so the caller can align the AIFF ``NAME`` chunk.

    ``v2_version`` is the ID3v2 minor version to write (3 = v2.3, the
    Plex/Rekordbox-friendly default; 4 = v2.4). Raises ``ID3NoHeaderError`` when
    ``src`` has no ID3 tag (the caller skips + warns). Leaves the AIFF's
    ``SSND``/``COMM``/``NAME`` chunks untouched."""
    if v2_version not in (3, 4):
        raise ValueError("v2_version must be 3 or 4")
    src = ID3(src_path)  # raises ID3NoHeaderError if the lossy file is untagged

    dst = AIFF(dst_path)
    if dst.tags is None:
        dst.add_tags()  # initialise an empty ID3; only legal when none exists
    tags = dst.tags
    assert tags is not None  # add_tags() guarantees this; narrows for the type checker
    tags.clear()  # wholesale: drop any stale ID3 already on the lossless file
    for frame in src.values():
        tags.add(frame)  # text frames + APIC artwork, keyed by HashKey
    dst.save(v2_version=v2_version)  # surgical ID3-chunk write; mutagen downgrades

    tit2 = tags.get("TIT2")
    text: Optional[list] = getattr(tit2, "text", None)
    return str(text[0]) if text else ""
