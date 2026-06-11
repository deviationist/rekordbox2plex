import re

import pytest

from rekordbox2plex.rekordbox.RekordboxDBWriter import build_date_updates, rb_now


def test_usn_sequence_and_global_counter():
    rows = [(10, "D1"), (20, "D2"), (30, "D3")]
    stmts, final_usn = build_date_updates(rows, start_usn=100, now_str="NOW")

    # One UPDATE per row (rb_local_usn = 101, 102, 103) + the global counter row.
    assert len(stmts) == 4
    assert final_usn == 103
    for i, (rb_id, _val) in enumerate(rows):
        sql, params = stmts[i]
        assert "UPDATE djmdContent SET created_at = ?" in sql
        assert "rb_local_usn = ?" in sql
        # params: (value, now, usn, rb_id)
        assert params == (rows[i][1], "NOW", 101 + i, rb_id)
    # Final statement bumps agentRegistry.localUpdateCount to the last USN.
    last_sql, last_params = stmts[-1]
    assert "UPDATE agentRegistry SET int_1 = ?" in last_sql
    assert "localUpdateCount" in last_sql
    assert last_params == (103, "NOW")


def test_empty_rows_produce_no_statements():
    stmts, final_usn = build_date_updates([], start_usn=500, now_str="NOW")
    assert stmts == []
    assert final_usn == 500


def test_field_is_allowlisted():
    with pytest.raises(ValueError):
        build_date_updates([(1, "x")], 0, "NOW", field="created_at; DROP TABLE x")


def test_alternate_field_targets_that_column():
    stmts, _ = build_date_updates([(1, "x")], 0, "NOW", field="StockDate")
    assert "UPDATE djmdContent SET StockDate = ?" in stmts[0][0]


def test_rb_now_matches_rekordbox_format():
    # e.g. "2026-06-11 10:37:39.680 +00:00"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \+00:00", rb_now())
