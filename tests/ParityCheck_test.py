import argparse
import contextlib
import sqlite3

import pytest

from rekordbox2plex import config
from rekordbox2plex.actions.ParityCheck import ParityCheck
from rekordbox2plex.rekordbox.resolvers.track import is_ignored_rb_path
from rekordbox2plex.utils.normalize import normalize

# --- fake Plex DB ---------------------------------------------------------
#
# Minimal subset of the schema read_tracks_metadata touches: tracks (type 10)
# whose parent_id is an album (type 9) whose parent_id is an artist (type 8).
#
# Track 11: fully matches Rekordbox.
# Track 12: album differs (real mismatch).
# Track 13: differs only by case/whitespace -> normalized equal, NOT a mismatch.
# Track 14: file has no Rekordbox match -> Plex orphan.
# Track 15: under /ignore/ -> excluded when REKORDBOX_FOLDER_PATHS_TO_IGNORE is set.
#
# With no folder mappings, convert_path_to_rekordbox is a no-op, so the resolver
# is keyed by the same paths the Plex DB stores.
FILE_TO_RB = {
    "/m/t11.mp3": 11,
    "/m/t12.mp3": 12,
    "/m/t13.mp3": 13,
    # t14 deliberately absent
    "/ignore/t15.mp3": 15,
}
RB_META = {
    11: {
        "title": "Song One",
        "artist": "Artist A",
        "album": "Album A",
        "album_artist": "Artist A",
    },
    12: {
        "title": "Song Two",
        "artist": "Artist A",
        "album": "Different Album",
        "album_artist": "Artist A",
    },
    13: {
        "title": "Song Three",
        "artist": "Artist B",
        "album": "Album B",
        "album_artist": "Artist B",
    },
    15: {
        "title": "Ignored Song",
        "artist": "Artist A",
        "album": "Album A",
        "album_artist": "Artist A",
    },
}
# Whole Rekordbox collection -> FolderPath. id 99 exists in RB but not Plex
# (RB orphan); id 15 lives under the ignorable /ignore/ prefix.
RB_ID_TO_PATH = {
    11: "/m/t11.mp3",
    12: "/m/t12.mp3",
    13: "/m/t13.mp3",
    15: "/ignore/t15.mp3",
    99: "/m/t99.mp3",
}


def _build_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE library_sections (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE metadata_items (
            id INTEGER PRIMARY KEY, library_section_id INTEGER,
            metadata_type INTEGER, parent_id INTEGER,
            title TEXT, original_title TEXT, added_at INTEGER);
        CREATE TABLE media_items (id INTEGER PRIMARY KEY, metadata_item_id INTEGER);
        CREATE TABLE media_parts (id INTEGER PRIMARY KEY, media_item_id INTEGER, file TEXT);
        """
    )
    con.execute("INSERT INTO library_sections VALUES (1, 'TestMusic')")
    con.executemany(
        "INSERT INTO metadata_items VALUES (?,?,?,?,?,?,?)",
        [
            # artists (type 8)
            (800, 1, 8, None, "Artist A", None, 0),
            (801, 1, 8, None, "Artist B", None, 0),
            # albums (type 9), parent = artist
            (900, 1, 9, 800, "Album A", None, 0),
            (901, 1, 9, 800, "Different Plex Album", None, 0),
            (902, 1, 9, 801, "  album   b  ", None, 0),  # case/whitespace variant
            # tracks (type 10), parent = album; original_title = per-track artist
            (11, 1, 10, 900, "Song One", None, 0),
            (12, 1, 10, 901, "Song Two", None, 0),
            (13, 1, 10, 902, "Song Three", None, 0),
            (14, 1, 10, 900, "Orphan Song", None, 0),
            (15, 1, 10, 900, "Ignored Song", None, 0),
        ],
    )
    con.executemany(
        "INSERT INTO media_items VALUES (?,?)",
        [(111, 11), (112, 12), (113, 13), (114, 14), (115, 15)],
    )
    con.executemany(
        "INSERT INTO media_parts VALUES (?,?,?)",
        [
            (1, 111, "/m/t11.mp3"),
            (2, 112, "/m/t12.mp3"),
            (3, 113, "/m/t13.mp3"),
            (4, 114, "/m/t14.mp3"),
            (5, 115, "/ignore/t15.mp3"),
        ],
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
            command="parity",
            fields=None,
            only=None,
            orphans=True,
            orphan_limit=50,
            verbose=0,
        )
    )
    mod = "rekordbox2plex.actions.ParityCheck"
    # convert_path_to_rekordbox is identity here (no folder mappings), so the
    # rb_path passed downstream equals the Plex file path.
    monkeypatch.setattr(f"{mod}.convert_path_to_rekordbox", lambda p: p)
    monkeypatch.setattr(
        f"{mod}.resolve_track_id_by_rb_path", lambda p: FILE_TO_RB.get(p)
    )
    monkeypatch.setattr(f"{mod}.get_rb_metadata", lambda rb_id: RB_META.get(rb_id))
    # Mirror the real get_all_rb_track_ids: drop ids whose FolderPath is ignored.
    monkeypatch.setattr(
        f"{mod}.get_all_rb_track_ids",
        lambda ignore_fragments=None: {
            rb_id
            for rb_id, path in RB_ID_TO_PATH.items()
            if not is_ignored_rb_path(path, ignore_fragments or [])
        },
    )
    monkeypatch.setattr(f"{mod}.progress_instance", _no_progress)
    return ParityCheck()


def _fields(report):
    return {(m["rk"], m["field"]) for m in report.mismatches}


def test_normalize_folds_case_and_whitespace():
    assert normalize("  Album   B ") == normalize("album b")
    assert normalize(None) == ""
    assert normalize("A") != normalize("B")


def test_matched_track_with_identical_metadata_is_not_a_mismatch(action):
    report = action.compute_report(None)
    assert (11, "album") not in _fields(report)
    assert all(m["rk"] != 11 for m in report.mismatches)


def test_real_album_difference_is_reported(action):
    report = action.compute_report(None)
    assert (12, "album") in _fields(report)


def test_case_whitespace_only_difference_is_not_a_mismatch(action):
    report = action.compute_report(None)
    # Track 13's album differs only by case/whitespace -> normalized equal.
    assert all(m["rk"] != 13 for m in report.mismatches)


def test_plex_track_without_rekordbox_match_is_a_plex_orphan(action):
    report = action.compute_report(None)
    assert [o["rk"] for o in report.plex_orphans] == [14]
    assert report.compared == 4  # 11, 12, 13, 15 matched; 14 is an orphan
    # scanned counts every walked track; the three buckets sum back to it.
    assert report.scanned == 5
    assert report.scanned == (
        report.compared + len(report.plex_orphans) + report.ignored
    )


def test_rekordbox_track_without_plex_match_is_an_rb_orphan(action):
    report = action.compute_report(None)
    assert report.rb_orphan_ids == [99]


def test_is_ignored_rb_path_substring_match():
    assert is_ignored_rb_path("/ignore/x.mp3", ["/ignore/"]) is True
    # Substring (not prefix): a bare folder name matches anywhere in the path.
    assert (
        is_ignored_rb_path("/Volumes/REKORDBOX/on-hold/Memes/x.mp3", ["Memes"]) is True
    )
    assert is_ignored_rb_path("/m/x.mp3", ["/ignore/"]) is False
    assert is_ignored_rb_path("/m/x.mp3", []) is False
    assert is_ignored_rb_path(None, ["/ignore/"]) is False


def test_ignored_folder_excludes_track_from_both_sides(action, monkeypatch):
    monkeypatch.setenv("REKORDBOX_FOLDER_PATHS_TO_IGNORE", "/ignore/")
    ignoring = ParityCheck()  # re-read env at construction
    report = ignoring.compute_report(None)
    # Track 15 is neither compared nor reported as an orphan, and is counted.
    assert report.ignored == 1
    assert report.compared == 3  # 11, 12, 13 (15 skipped)
    assert report.scanned == 5  # 15 is still scanned, then ignored
    assert 15 not in report.matched_rb_ids
    assert all(o["rk"] != 15 for o in report.plex_orphans)
    # ...and it must not surface as an RB-side orphan either.
    assert 15 not in report.rb_orphan_ids


def test_default_fields_exclude_albumartist(action):
    # albumartist is opt-in: Rekordbox dedups djmdAlbum by name, so its album-artist
    # is per-album (unreliable for same-named releases). Default = the other three.
    assert action.fields == {"title", "artist", "album"}


def test_albumartist_is_opt_in_via_fields(tmp_path, monkeypatch):
    db = tmp_path / "p.db"
    _build_db(str(db))
    monkeypatch.setenv("PLEX_DB_PATH", str(db))
    monkeypatch.setenv("PLEX_LIBRARY_NAME", "TestMusic")
    config.set_args(
        argparse.Namespace(
            command="parity",
            fields="title,artist,album,albumartist",
            only=None,
            orphans=True,
            orphan_limit=50,
            verbose=0,
        )
    )
    assert "albumartist" in ParityCheck().fields


def test_field_filter_limits_compared_fields(action):
    action.fields = {"title"}
    report = action.compute_report(None)
    # Only title is compared, so the album-12 mismatch must not surface.
    assert all(m["field"] == "title" for m in report.mismatches)


def test_only_filter_scopes_to_named_track_and_skips_rb_orphans(action):
    report = action.compute_report({12})
    assert report.compared == 1
    assert (12, "album") in _fields(report)
    # RB-orphan detection is skipped on a filtered (partial) scan.
    assert report.rb_orphan_ids == []


# --- --split-artists set comparison ------------------------------------------
#
# A single Plex track (id 11) whose only divergence from Rekordbox is the
# per-track Artist string. title/album are kept identical so artist is the
# sole field that can mismatch.


def _build_single_db(path: str, plex_artist: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE library_sections (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE metadata_items (
            id INTEGER PRIMARY KEY, library_section_id INTEGER,
            metadata_type INTEGER, parent_id INTEGER,
            title TEXT, original_title TEXT, added_at INTEGER);
        CREATE TABLE media_items (id INTEGER PRIMARY KEY, metadata_item_id INTEGER);
        CREATE TABLE media_parts (id INTEGER PRIMARY KEY, media_item_id INTEGER, file TEXT);
        """
    )
    con.execute("INSERT INTO library_sections VALUES (1, 'TestMusic')")
    con.executemany(
        "INSERT INTO metadata_items VALUES (?,?,?,?,?,?,?)",
        [
            (800, 1, 8, None, plex_artist, None, 0),  # artist (type 8)
            (900, 1, 9, 800, "Album X", None, 0),  # album (type 9)
            (11, 1, 10, 900, "Song", None, 0),  # track (type 10)
        ],
    )
    con.execute("INSERT INTO media_items VALUES (111, 11)")
    con.execute("INSERT INTO media_parts VALUES (1, 111, '/m/t11.mp3')")
    con.commit()
    con.close()


def _collab_action(
    tmp_path,
    monkeypatch,
    *,
    plex_artist: str,
    rb_artist: str,
    split: bool,
    ordered: bool = False,
    extra_seps=None,
):
    db = tmp_path / "collab.db"
    _build_single_db(str(db), plex_artist)
    monkeypatch.setenv("PLEX_DB_PATH", str(db))
    monkeypatch.setenv("PLEX_LIBRARY_NAME", "TestMusic")
    # Isolate the separator config from any repo .env that a sibling test module
    # may have loaded via dotenv — the extra-seps tier here comes only from the
    # explicit `extra_seps` arg (Namespace.collab_extra_seps below).
    monkeypatch.delenv("ARTIST_COLLAB_PRIMARY_SEPARATORS", raising=False)
    monkeypatch.delenv("ARTIST_COLLAB_EXTRA_SEPARATORS", raising=False)
    config.set_args(
        argparse.Namespace(
            command="parity",
            fields=None,
            only=None,
            orphans=False,  # no RB-orphan walk → get_all_rb_track_ids unused
            orphan_limit=50,
            verbose=0,
            split_artists=split,
            split_artists_ordered=ordered,
            collab_extra_seps=extra_seps,
        )
    )
    mod = "rekordbox2plex.actions.ParityCheck"
    monkeypatch.setattr(f"{mod}.convert_path_to_rekordbox", lambda p: p)
    monkeypatch.setattr(
        f"{mod}.resolve_track_id_by_rb_path",
        lambda p: 11 if p == "/m/t11.mp3" else None,
    )
    monkeypatch.setattr(
        f"{mod}.get_rb_metadata",
        lambda rb_id: (
            {
                "title": "Song",
                "artist": rb_artist,
                "album": "Album X",
                "album_artist": rb_artist,
            }
            if rb_id == 11
            else None
        ),
    )
    monkeypatch.setattr(f"{mod}.progress_instance", _no_progress)
    return ParityCheck()


def test_split_artists_treats_ampersand_and_comma_as_equal(tmp_path, monkeypatch):
    # The motivating case: Plex "Fred V & Grafix" vs Rekordbox "Fred V, Grafix".
    action = _collab_action(
        tmp_path,
        monkeypatch,
        plex_artist="Fred V & Grafix",
        rb_artist="Fred V, Grafix",
        split=True,
        extra_seps="& +",  # opt in the ambiguous tier so '&' splits
    )
    report = action.compute_report(None)
    assert all(m["field"] != "artist" for m in report.mismatches)


def test_split_artists_off_still_reports_the_artist_mismatch(tmp_path, monkeypatch):
    action = _collab_action(
        tmp_path,
        monkeypatch,
        plex_artist="Fred V & Grafix",
        rb_artist="Fred V, Grafix",
        split=False,
    )
    report = action.compute_report(None)
    assert (11, "artist") in _fields(report)


def test_split_artists_without_extra_seps_does_not_split_ampersand(
    tmp_path, monkeypatch
):
    # '&' is opt-in: with only the primary separators (comma + feat) the two
    # strings don't decompose the same way, so the mismatch still stands.
    action = _collab_action(
        tmp_path,
        monkeypatch,
        plex_artist="Fred V & Grafix",
        rb_artist="Fred V, Grafix",
        split=True,
        extra_seps=None,
    )
    report = action.compute_report(None)
    assert (11, "artist") in _fields(report)


def test_split_artists_is_order_independent_by_default(tmp_path, monkeypatch):
    # comma is a primary separator, so no extra seps needed here.
    action = _collab_action(
        tmp_path,
        monkeypatch,
        plex_artist="Grafix, Fred V",
        rb_artist="Fred V, Grafix",
        split=True,
    )
    report = action.compute_report(None)
    assert all(m["field"] != "artist" for m in report.mismatches)


def test_split_artists_ordered_requires_same_order(tmp_path, monkeypatch):
    action = _collab_action(
        tmp_path,
        monkeypatch,
        plex_artist="Grafix, Fred V",
        rb_artist="Fred V, Grafix",
        split=True,
        ordered=True,
    )
    report = action.compute_report(None)
    assert (11, "artist") in _fields(report)


def test_split_artists_does_not_mask_a_genuinely_different_artist(
    tmp_path, monkeypatch
):
    # Different real artists must still surface even with the fallback on.
    action = _collab_action(
        tmp_path,
        monkeypatch,
        plex_artist="Fred V & Grafix",
        rb_artist="Some Other Artist",
        split=True,
        extra_seps="& +",
    )
    report = action.compute_report(None)
    assert (11, "artist") in _fields(report)
