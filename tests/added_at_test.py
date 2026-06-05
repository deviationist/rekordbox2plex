from datetime import timezone

from rekordbox2plex.rekordbox.resolvers.added_at import (
    parse_rb_timestamp,
    rollup_added_at,
    to_epoch,
)

# Anchor from the real library (Fly Away (Instrumental), rb_id 147954772):
# created_at "2020-10-10 15:45:57.775 +00:00" -> 1602344757
ANCHOR_RAW = "2020-10-10 15:45:57.775 +00:00"
ANCHOR_EPOCH = 1602344757
# StockDate/DateCreated are date-only -> midnight UTC
DATE_ONLY_EPOCH = 1602288000  # 2020-10-10 00:00:00 UTC


def test_offset_aware_created_at():
    dt = parse_rb_timestamp(ANCHOR_RAW)
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert to_epoch(dt) == ANCHOR_EPOCH


def test_offset_aware_ignores_tz_arg():
    # An explicit offset must win over any tz_name fallback.
    assert to_epoch(parse_rb_timestamp(ANCHOR_RAW, "America/New_York")) == ANCHOR_EPOCH


def test_date_only_naive_utc():
    assert to_epoch(parse_rb_timestamp("2020-10-10", "UTC")) == DATE_ONLY_EPOCH


def test_naive_tz_shifts_by_offset():
    # Same wall-clock interpreted at UTC+2 is 2h earlier in UTC than the same
    # interpreted as UTC. Etc/GMT-2 is a fixed UTC+2 zone (no city, no DST).
    naive = "2020-07-01 12:00:00"
    utc = to_epoch(parse_rb_timestamp(naive, "UTC"))
    plus2 = to_epoch(parse_rb_timestamp(naive, "Etc/GMT-2"))
    assert utc is not None and plus2 is not None
    assert utc - plus2 == 2 * 3600


def test_space_before_offset_is_handled():
    # The space before "+00:00" (Rekordbox's format) must not break parsing.
    spaced = "2021-01-02 03:04:05 +00:00"
    tight = "2021-01-02T03:04:05+00:00"
    assert to_epoch(parse_rb_timestamp(spaced)) == to_epoch(parse_rb_timestamp(tight))


def test_empty_and_garbage_return_none():
    assert parse_rb_timestamp(None) is None
    assert parse_rb_timestamp("") is None
    assert parse_rb_timestamp("   ") is None
    assert parse_rb_timestamp("not a date") is None
    assert to_epoch(None) is None


def test_rollup_min_ignores_none():
    assert rollup_added_at([1647023618, ANCHOR_EPOCH]) == ANCHOR_EPOCH
    assert rollup_added_at([None, ANCHOR_EPOCH, None]) == ANCHOR_EPOCH
    assert rollup_added_at([]) is None
    assert rollup_added_at([None, None]) is None
