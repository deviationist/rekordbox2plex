from rekordbox2plex.utils import snapshot_store
from rekordbox2plex.utils.snapshot_store import SnapshotEntry


def _entry(value="2020-01-01 00:00:00.000 +00:00", lossy="/m/a.mp3", rb_id=1):
    return SnapshotEntry(
        lossy_path=lossy,
        rb_field="created_at",
        value=value,
        source_rb_id=rb_id,
        captured_at="2026-06-11T00:00:00+00:00",
    )


def test_save_load_roundtrip(tmp_path):
    path = str(tmp_path / "snap.json")
    store = {"/m/a.aiff": _entry()}
    snapshot_store.save(path, store)
    assert snapshot_store.load(path) == store


def test_load_missing_or_garbage_returns_empty(tmp_path):
    assert snapshot_store.load(str(tmp_path / "nope.json")) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert snapshot_store.load(str(bad)) == {}


def test_merge_entry_reports_changes():
    store: dict = {}
    assert snapshot_store.merge_entry(store, "/m/a.aiff", _entry(value="V1")) is True
    # same value → no change
    assert snapshot_store.merge_entry(store, "/m/a.aiff", _entry(value="V1")) is False
    # different value → change
    assert snapshot_store.merge_entry(store, "/m/a.aiff", _entry(value="V2")) is True
    assert store["/m/a.aiff"]["value"] == "V2"


def test_prune_removes_only_given_keys():
    store = {"/a.aiff": _entry(), "/b.aiff": _entry(), "/c.aiff": _entry()}
    removed = snapshot_store.prune(store, ["/a.aiff", "/c.aiff", "/missing.aiff"])
    assert removed == 2
    assert set(store) == {"/b.aiff"}


def test_merge_then_save_is_idempotent(tmp_path):
    path = str(tmp_path / "snap.json")
    store = snapshot_store.load(path)
    snapshot_store.merge_entry(store, "/m/a.aiff", _entry())
    snapshot_store.save(path, store)
    reloaded = snapshot_store.load(path)
    assert reloaded == store
