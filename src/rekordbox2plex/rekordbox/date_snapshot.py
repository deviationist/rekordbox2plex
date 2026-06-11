"""Capture each lossy file's Rekordbox "Date Added" before a lossy→lossless swap.

Shared by the ``rb-dates snapshot`` command and the ``lossless-tags
--snapshot-dates`` hook. For each (lossy, lossless) pair we resolve the **lossy**
file to its Rekordbox row (read-only) and read the raw added-at string, keyed by
the **lossless** path so ``rb-dates apply`` can restore it onto the re-added row.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from ..config import get_rb_added_at_field
from ..utils.media_paths import PathMap
from ..utils.snapshot_store import SnapshotEntry
from .resolvers.added_at import read_rb_added_at_raw
from .resolvers.track import resolve_rb_id_by_host_path

# (lossy_path, lossless_path)
Pair = Tuple[str, str]


def capture_dates(
    pairs: Sequence[Pair],
    media_map: PathMap,
    field: Optional[str] = None,
) -> Tuple[Dict[str, SnapshotEntry], List[Tuple[str, str]]]:
    """Return ({lossless_path: entry}, skipped). ``skipped`` is (lossy_path, reason)
    for pairs whose lossy file isn't in Rekordbox or has no added-at value."""
    field = field or get_rb_added_at_field()
    captured_at = datetime.now(timezone.utc).isoformat()
    entries: Dict[str, SnapshotEntry] = {}
    skipped: List[Tuple[str, str]] = []
    for lossy, lossless in pairs:
        rb_id = resolve_rb_id_by_host_path(lossy, media_map)
        if rb_id is None:
            skipped.append((lossy, "lossy file not found in Rekordbox"))
            continue
        raw = read_rb_added_at_raw(rb_id, field)
        if raw is None:
            skipped.append((lossy, f"no {field} on Rekordbox row {rb_id}"))
            continue
        entries[lossless] = SnapshotEntry(
            lossy_path=lossy,
            rb_field=field,
            value=raw,
            source_rb_id=rb_id,
            captured_at=captured_at,
        )
    return entries, skipped
