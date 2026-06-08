import sqlite3

from rekordbox2plex.plex.PlexDBReader import read_upload_posters
from rekordbox2plex.plex.PlexDBWriter import build_clear_posters_sql, count_updates


def test_build_clear_posters_sql_shape_and_int_coercion():
    sql = build_clear_posters_sql(["28859", 30911])
    assert sql.startswith("BEGIN TRANSACTION;")
    assert sql.strip().endswith("COMMIT;")
    assert "UPDATE metadata_items SET user_thumb_url = '' WHERE id = 28859;" in sql
    assert "UPDATE metadata_items SET user_thumb_url = '' WHERE id = 30911;" in sql
    assert count_updates(sql) == 2


def test_build_clear_posters_sql_empty():
    sql = build_clear_posters_sql([])
    assert count_updates(sql) == 0
    assert "BEGIN TRANSACTION;" in sql and "COMMIT;" in sql


def _seed_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE library_sections (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE metadata_items (
            id INTEGER PRIMARY KEY, title TEXT, metadata_type INTEGER,
            library_section_id INTEGER, guid TEXT, user_thumb_url TEXT
        );
        INSERT INTO library_sections (id, name) VALUES (3, 'Music2');
        -- artists (type 8)
        INSERT INTO metadata_items VALUES (10, 'Artist Upload A', 8, 3, 'g10', 'upload://posters/aaa');
        INSERT INTO metadata_items VALUES (11, 'Artist Upload B', 8, 3, 'g11', 'upload://posters/bbb');
        INSERT INTO metadata_items VALUES (12, 'Artist No Poster', 8, 3, 'g12', '');
        INSERT INTO metadata_items VALUES (13, 'Artist Agent', 8, 3, 'g13', 'metadata://thumbs/x');
        -- albums (type 9)
        INSERT INTO metadata_items VALUES (20, 'Album Upload', 9, 3, 'g20', 'upload://posters/eee');
        INSERT INTO metadata_items VALUES (21, 'Album Embedded', 9, 3, 'g21', 'media://1/file');
        -- track (type 10) with an upload thumb must NEVER be returned
        INSERT INTO metadata_items VALUES (14, 'A Track', 10, 3, 'g14', 'upload://posters/ccc');
        -- artist in a different library must NOT be returned
        INSERT INTO metadata_items VALUES (15, 'Other Lib', 8, 9, 'g15', 'upload://posters/ddd');
        """
    )
    con.commit()
    con.close()


def test_read_upload_posters_artists_only(tmp_path):
    db = tmp_path / "plex.db"
    _seed_db(str(db))
    rows = read_upload_posters(str(db), "Music2", (8,))
    assert sorted(r["id"] for r in rows) == [10, 11]
    assert all(r["user_thumb_url"].startswith("upload://") for r in rows)


def test_read_upload_posters_albums_only(tmp_path):
    db = tmp_path / "plex.db"
    _seed_db(str(db))
    rows = read_upload_posters(str(db), "Music2", (9,))
    assert [r["id"] for r in rows] == [20]  # only the uploaded album poster


def test_read_upload_posters_both(tmp_path):
    db = tmp_path / "plex.db"
    _seed_db(str(db))
    rows = read_upload_posters(str(db), "Music2", (8, 9))
    assert sorted(r["id"] for r in rows) == [10, 11, 20]


def test_read_upload_posters_no_types(tmp_path):
    db = tmp_path / "plex.db"
    _seed_db(str(db))
    assert read_upload_posters(str(db), "Music2", ()) == []
