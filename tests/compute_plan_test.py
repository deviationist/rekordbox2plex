import argparse
import contextlib
import sqlite3

import pytest

from rekordbox2plex import config
from rekordbox2plex.actions.DateAddedRestore import DateAddedRestore

# --- fake Plex DB ---------------------------------------------------------
#
# Minimal subset of the Plex schema that PlexDBReader.read_library touches.
# Three albums; album C and its track are *already correct* (to exercise
# idempotency). All "current" added_at values are 9999 except the C pair.
#
# file -> rb_id, then rb_id -> proposed epoch (the two Rekordbox lookups are
# monkeypatched, so no Rekordbox DB is needed):
FILE_TO_RB = {"/m/a1.mp3": 1, "/m/a2.mp3": 2, "/m/b1.mp3": 3, "/m/c1.mp3": 4}
RB_TO_EPOCH = {1: 1000, 2: 2000, 3: 3000, 4: 5000}


def _build_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE library_sections (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE metadata_items (
            id INTEGER PRIMARY KEY, library_section_id INTEGER,
            metadata_type INTEGER, parent_id INTEGER, title TEXT, added_at INTEGER);
        CREATE TABLE media_items (id INTEGER PRIMARY KEY, metadata_item_id INTEGER);
        CREATE TABLE media_parts (id INTEGER PRIMARY KEY, media_item_id INTEGER, file TEXT);
        """
    )
    con.execute("INSERT INTO library_sections VALUES (1, 'TestMusic')")
    con.executemany(
        "INSERT INTO metadata_items VALUES (?,?,?,?,?,?)",
        [
            # albums (type 9)
            (100, 1, 9, None, "Album A", 9999),
            (200, 1, 9, None, "Album B", 9999),
            (300, 1, 9, None, "Album C", 5000),  # already correct
            # tracks (type 10)
            (11, 1, 10, 100, "A1", 9999),
            (12, 1, 10, 100, "A2", 9999),
            (21, 1, 10, 200, "B1", 9999),
            (31, 1, 10, 300, "C1", 5000),  # already correct
        ],
    )
    con.executemany(
        "INSERT INTO media_items VALUES (?,?)",
        [(1011, 11), (1012, 12), (1021, 21), (1031, 31)],
    )
    con.executemany(
        "INSERT INTO media_parts VALUES (?,?,?)",
        [(1, 1011, "/m/a1.mp3"), (2, 1012, "/m/a2.mp3"),
         (3, 1021, "/m/b1.mp3"), (4, 1031, "/m/c1.mp3")],
    )
    con.commit()
    con.close()


@contextlib.contextmanager
def _no_progress(*_a, **_k):
    class _P:
        def add_task(self, *_a, **_k):
            return 0

        def update(self, *_a, **_k):
            pass

    yield _P()


@pytest.fixture
def action(tmp_path, monkeypatch):
    db = tmp_path / "plex.db"
    _build_db(str(db))
    monkeypatch.setenv("PLEX_DB_PATH", str(db))
    monkeypatch.setenv("PLEX_LIBRARY_NAME", "TestMusic")
    config.set_args(
        argparse.Namespace(
            command="dates", dry_run=False, write=False, tracks=True, albums=True,
            only=None, validate_track=None, validate_album=None, plan_file=None,
            allow_running=False, verbose=0, wipe=False,
        )
    )
    mod = "rekordbox2plex.actions.DateAddedRestore"
    monkeypatch.setattr(f"{mod}.resolve_track_id_by_plex_path", lambda p: FILE_TO_RB.get(p))
    monkeypatch.setattr(f"{mod}.resolve_rb_added_at", lambda rb, *a, **k: RB_TO_EPOCH.get(rb))
    monkeypatch.setattr(f"{mod}.progress_instance", _no_progress)
    return DateAddedRestore()


def _by_id(updates):
    return {u["id"]: u["proposed"] for u in updates}


def test_no_filter_plans_all_changed_rows(action):
    plan = action.compute_plan(None)
    assert plan.matched == 4
    assert _by_id(plan.track_updates) == {11: 1000, 12: 2000, 21: 3000}
    # album A = min(1000, 2000); album B = min(3000)
    assert _by_id(plan.album_updates) == {100: 1000, 200: 3000}


def test_idempotent_rows_are_skipped(action):
    plan = action.compute_plan(None)
    # C1 (track 31) and Album C (300) already match -> not in the plan.
    assert 31 not in _by_id(plan.track_updates)
    assert 300 not in _by_id(plan.album_updates)


def test_only_track_id_updates_just_that_track(action):
    plan = action.compute_plan({11})
    assert _by_id(plan.track_updates) == {11: 1000}
    # naming a track must NOT update its album
    assert plan.album_updates == []


def test_only_album_id_updates_album_with_full_track_rollup(action):
    plan = action.compute_plan({100})
    # naming an album must NOT update its tracks...
    assert plan.track_updates == []
    # ...and the album date is the min across ALL its tracks (1000, not 2000),
    # proving both A1 and A2 fed the rollup even though only the album was named.
    assert _by_id(plan.album_updates) == {100: 1000}


def test_scope_flags_filter_output(action):
    plan = action.compute_plan(None)
    action.include_albums = False
    tracks, albums = action._scoped(plan)
    assert albums == [] and len(tracks) == 3
    action.include_tracks, action.include_albums = False, True
    tracks, albums = action._scoped(plan)
    assert tracks == [] and len(albums) == 2
