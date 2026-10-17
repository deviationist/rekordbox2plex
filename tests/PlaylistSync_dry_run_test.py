"""--dry-run is a promise that Plex is not changed.

`playlists` is the one command that writes unless told not to, so every write
in PlaylistSync has to check `dry_run` itself. Two did not -- creating a
playlist missing from Plex, and deleting one empty on both sides -- and a dry
run went ahead and did both. These tests drive each write path with fakes that
record any call, in both modes.
"""

import pytest

from rekordbox2plex.actions import PlaylistSync as playlist_sync_module
from rekordbox2plex.actions.PlaylistSync import PlaylistSync


class FakeTrack:
    def __init__(self, rating_key):
        self.ratingKey = rating_key


class FakePlexPlaylist:
    def __init__(self, title, items):
        self.title = title
        self._items = items
        self.calls = []

    def items(self):
        return list(self._items)

    def addItems(self, items):
        self.calls.append(("addItems", [t.ratingKey for t in items]))

    def removeItems(self, items):
        self.calls.append(("removeItems", [t.ratingKey for t in items]))

    def delete(self):
        self.calls.append(("delete",))


class FakeRbPlaylist:
    def __init__(self, name, id=1):
        self.name = name
        self.id = id


class FakeRepository:
    created = []

    def create_playlist(self, name, items):
        FakeRepository.created.append((name, [t.ratingKey for t in items]))


def make_sync(monkeypatch, dry_run, rb_tracks):
    """A PlaylistSync with no Plex and no Rekordbox behind it: the mapper is
    skipped, and the Rekordbox side of every playlist is `rb_tracks`."""
    monkeypatch.setattr(PlaylistSync, "__init__", lambda self: None)
    monkeypatch.setattr(playlist_sync_module, "PlexPlaylistRepository", FakeRepository)
    FakeRepository.created = []
    sync = PlaylistSync()
    sync.dry_run = dry_run
    sync.deleted = sync.created = sync.updated = 0
    monkeypatch.setattr(
        sync, "resolve_plex_tracks_from_rb_playlist", lambda rb: list(rb_tracks)
    )
    return sync


@pytest.mark.parametrize("dry_run, writes", [(True, False), (False, True)])
def test_a_playlist_empty_on_both_sides_is_deleted_only_for_real(
    monkeypatch, dry_run, writes
):
    sync = make_sync(monkeypatch, dry_run, rb_tracks=[])
    plex = FakePlexPlaylist("Empty", items=[])
    sync.sync_playlist_tracks(FakeRbPlaylist("Empty"), plex)
    assert plex.calls == ([("delete",)] if writes else [])
    assert sync.deleted == 1  # the summary says what a real run would do


@pytest.mark.parametrize("dry_run, writes", [(True, False), (False, True)])
def test_a_playlist_missing_from_plex_is_created_only_for_real(
    monkeypatch, dry_run, writes
):
    sync = make_sync(monkeypatch, dry_run, rb_tracks=[FakeTrack(1), FakeTrack(2)])
    assert sync.create_playlist(FakeRbPlaylist("New")) == 2
    assert FakeRepository.created == ([("New", [1, 2])] if writes else [])
    assert sync.created == 1


@pytest.mark.parametrize("dry_run, writes", [(True, False), (False, True)])
def test_tracks_are_added_and_removed_only_for_real(monkeypatch, dry_run, writes):
    sync = make_sync(monkeypatch, dry_run, rb_tracks=[FakeTrack(1), FakeTrack(3)])
    plex = FakePlexPlaylist("Jungle", items=[FakeTrack(1), FakeTrack(2)])
    assert sync.sync_playlist_tracks(FakeRbPlaylist("Jungle"), plex) is True
    expected = [("addItems", [3]), ("removeItems", [2])] if writes else []
    assert plex.calls == expected
    assert sync.updated == 1


@pytest.mark.parametrize("dry_run, writes", [(True, False), (False, True)])
def test_an_orphaned_playlist_is_deleted_only_for_real(monkeypatch, dry_run, writes):
    sync = make_sync(monkeypatch, dry_run, rb_tracks=[])
    orphan = FakePlexPlaylist("Gone from Rekordbox", items=[FakeTrack(1)])
    sync.delete_orphaned_playlists([FakeRbPlaylist("Kept")], [orphan])
    assert orphan.calls == ([("delete",)] if writes else [])
    assert sync.deleted == 1
