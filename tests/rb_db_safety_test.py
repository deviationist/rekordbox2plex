import os

import pytest

from rekordbox2plex.utils.rb_db_safety import (
    DBNotQuiescent,
    assert_db_quiescent,
    backup_rekordbox_db,
    probe_stable,
    wal_state,
)


def _make_db(tmp_path, wal=b"", shm=False):
    db = tmp_path / "master.db"
    db.write_bytes(b"SQLite format 3\x00")
    if wal:
        (tmp_path / "master.db-wal").write_bytes(wal)
    if shm:
        (tmp_path / "master.db-shm").write_bytes(b"\x00")
    return str(db)


def test_wal_state_detects_dirty(tmp_path):
    clean = _make_db(tmp_path)
    assert wal_state(clean) == (False, 0)

    sub = tmp_path / "d2"
    sub.mkdir()
    dirty = _make_db(sub, wal=b"\x01\x02\x03")
    is_dirty, size = wal_state(dirty)
    assert is_dirty and size == 3


def test_probe_stable_true_when_untouched(tmp_path):
    db = _make_db(tmp_path)
    assert probe_stable(db, 0.0, samples=2, sleep_func=lambda _s: None) is True


def test_probe_stable_false_when_file_moves(tmp_path):
    db = _make_db(tmp_path)

    def mutate(_seconds):
        with open(db, "ab") as f:
            f.write(b"more")  # size change between samples

    assert probe_stable(db, 0.0, samples=2, sleep_func=mutate) is False


def test_assert_quiescent_refuses_nonempty_wal(tmp_path):
    db = _make_db(tmp_path, wal=b"\x01\x02")
    with pytest.raises(DBNotQuiescent):
        assert_db_quiescent(db, wait_seconds=0.0)
    # --ignore-wal bypasses just the WAL check
    assert_db_quiescent(db, wait_seconds=0.0, ignore_wal=True)


def test_assert_quiescent_allow_running_bypasses_everything(tmp_path):
    db = _make_db(tmp_path, wal=b"\x01\x02", shm=True)
    # would otherwise raise; allow_running short-circuits
    assert_db_quiescent(db, wait_seconds=0.0, allow_running=True)


def test_backup_copies_db_and_sidecars(tmp_path):
    db = _make_db(tmp_path, wal=b"\x09", shm=True)
    dest = backup_rekordbox_db(db, str(tmp_path / "backups"))
    assert os.path.isfile(os.path.join(dest, "master.db"))
    assert os.path.isfile(os.path.join(dest, "master.db-wal"))
    assert os.path.isfile(os.path.join(dest, "master.db-shm"))
