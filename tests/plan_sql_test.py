from rekordbox2plex.plex.PlexDBWriter import build_plan_sql, count_updates


def test_build_plan_sql_structure():
    tracks = [{"id": 17779, "proposed": 1602344757, "title": "Fly Away (Instrumental)"}]
    albums = [{"id": 17776, "proposed": 1602344757, "title": "Fly Away"}]
    sql = build_plan_sql(tracks, albums)
    assert sql.startswith("BEGIN TRANSACTION;")
    assert sql.strip().endswith("COMMIT;")
    assert "UPDATE metadata_items SET added_at = 1602344757 WHERE id = 17779;" in sql
    assert "UPDATE metadata_items SET added_at = 1602344757 WHERE id = 17776;" in sql
    assert count_updates(sql) == 2


def test_titles_only_appear_in_sanitized_comments():
    # A title with a newline and an SQL-comment marker must not break a line or
    # leak past its comment — values/ids are pure ints.
    rows = [{"id": 5, "proposed": 100, "title": "evil\n-- DROP TABLE"}]
    sql = build_plan_sql(rows, [])
    update_lines = [ln for ln in sql.splitlines() if ln.startswith("UPDATE")]
    assert len(update_lines) == 1
    assert update_lines[0] == "UPDATE metadata_items SET added_at = 100 WHERE id = 5;  -- evil — DROP TABLE"


def test_empty_plan_is_just_a_transaction():
    sql = build_plan_sql([], [])
    assert count_updates(sql) == 0
    assert "BEGIN TRANSACTION;" in sql and "COMMIT;" in sql
