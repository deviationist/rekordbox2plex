import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Optional

from ..RekordboxDB import RekordboxDB
from ...config import get_rb_added_at_field, get_rekordbox_tz

# Candidate djmdContent columns that can express "entered the collection".
# created_at is canonical (full UTC-offset timestamp); StockDate/DateCreated
# are date-only fallbacks shown for verification.
RB_TIMESTAMP_FIELDS = ("created_at", "StockDate", "DateCreated")


def _normalize(raw: str) -> str:
    """Make a Rekordbox timestamp parseable by datetime.fromisoformat.

    Rekordbox stores created_at like ``2020-10-10 15:45:57.775 +00:00`` — note
    the space before the offset, which fromisoformat rejects. Collapse it.
    """
    s = str(raw).strip()
    return re.sub(r"\s+([+-]\d{2}:?\d{2})$", r"\1", s)


def parse_rb_timestamp(
    raw: Optional[str], tz_name: Optional[str] = None
) -> Optional[datetime]:
    """Parse a Rekordbox timestamp string into a UTC-aware datetime.

    Offset-aware inputs are converted straight to UTC. Naive inputs (e.g. the
    date-only StockDate) are interpreted in ``tz_name`` (or the host local zone
    when None) before conversion. Returns None for empty/unparseable values.
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        dt = datetime.fromisoformat(_normalize(raw))
    except ValueError:
        return None
    if dt.tzinfo is None:
        tz = ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def to_epoch(dt: Optional[datetime]) -> Optional[int]:
    return int(dt.timestamp()) if dt is not None else None


def rollup_added_at(epochs) -> Optional[int]:
    """Album-level added_at = the earliest (min) of its member tracks' epochs.
    Ignores None entries; returns None when nothing usable is present."""
    values = [e for e in epochs if e is not None]
    return min(values) if values else None


def get_rb_timestamps(rb_id: int) -> Dict[str, Optional[str]]:
    """Return the raw candidate timestamp strings for a Rekordbox track ID."""
    cursor = RekordboxDB().cursor
    cursor.execute(
        "SELECT created_at, StockDate, DateCreated FROM djmdContent WHERE ID = ?",
        (rb_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return {field: None for field in RB_TIMESTAMP_FIELDS}
    data = dict(row)
    return {field: data.get(field) for field in RB_TIMESTAMP_FIELDS}


def resolve_rb_added_at(
    rb_id: int,
    field: Optional[str] = None,
    tz_name: Optional[str] = None,
) -> Optional[int]:
    """Resolve a Rekordbox track ID to a UTC epoch (seconds) for Plex added_at."""
    field = field or get_rb_added_at_field()
    tz_name = tz_name if tz_name is not None else get_rekordbox_tz()
    raw = get_rb_timestamps(rb_id).get(field)
    return to_epoch(parse_rb_timestamp(raw, tz_name))


def read_rb_added_at_raw(rb_id: int, field: Optional[str] = None) -> Optional[str]:
    """Return the **raw, unparsed** added-at string (the configured field, default
    ``created_at``) for a Rekordbox track ID, e.g. ``2020-09-17 22:16:29.060
    +00:00`` — or None if absent. Used by the ``rb-dates`` snapshot so the value
    can be restored byte-for-byte later."""
    field = field or get_rb_added_at_field()
    raw = get_rb_timestamps(rb_id).get(field)
    if raw is None or not str(raw).strip():
        return None
    return str(raw)
