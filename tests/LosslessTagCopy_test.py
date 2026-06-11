import argparse
import hashlib
import struct

import pytest
from mutagen.aiff import AIFF
from mutagen.id3 import ID3, TIT2, TPE1

from rekordbox2plex import config
from rekordbox2plex.actions.LosslessTagCopy import LosslessTagCopy
from rekordbox2plex.utils.aiff_chunks import read_name


def _chunk(cid: bytes, data: bytes) -> bytes:
    out = cid + struct.pack(">I", len(data)) + data
    if len(data) & 1:
        out += b"\x00"
    return out


def _aiff_bytes(samples=b"\x01\x02\x03\x04" * 4, name_text=None) -> bytes:
    sample_rate_80bit = bytes([0x40, 0x0E, 0xAC, 0x44, 0, 0, 0, 0, 0, 0])
    n_frames = len(samples) // 4
    comm = (
        struct.pack(">h", 2)
        + struct.pack(">I", n_frames)
        + struct.pack(">h", 16)
        + sample_rate_80bit
    )
    body = _chunk(b"COMM", comm)
    if name_text is not None:
        body += _chunk(b"NAME", name_text.encode("utf-8"))
    body += _chunk(b"SSND", struct.pack(">I", 0) + struct.pack(">I", 0) + samples)
    form = b"AIFF" + body
    return b"FORM" + struct.pack(">I", len(form)) + form


def _write_aiff(path, name_text=None):
    path.write_bytes(_aiff_bytes(name_text=name_text))
    return path


def _ssnd_md5(path):
    data = path.read_bytes()
    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        total = 8 + size + (size & 1)
        if cid == b"SSND":
            return hashlib.md5(data[pos : pos + total]).hexdigest()
        pos += total
    return None


def _write_mp3(path, title="Title", artist="Artist"):
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=[artist]))
    tags.save(str(path))
    return path


def _set_args(root, **overrides):
    defaults = dict(
        command="lossless-tags",
        root=str(root),
        dry_run=True,
        write=False,
        show="matched",
        lossy_exts=None,
        lossless_exts=None,
        remove_name=False,
        refresh_plex=False,
        delete_lossy=False,
        mirror_version=False,
        ignore_case=False,
        limit=None,
        backup_dir=None,
        verbose=0,
    )
    defaults.update(overrides)
    config.set_args(argparse.Namespace(**defaults))


def test_matched_pair_recurses_and_reads_incoming_tags(tmp_path):
    sub = tmp_path / "Artist - Album"
    sub.mkdir()
    _write_mp3(sub / "song.mp3", title="Real Title", artist="Fred V")
    _write_aiff(sub / "song.aiff")
    _set_args(tmp_path)

    pairs, unmatched, skipped = LosslessTagCopy().compute()

    assert len(pairs) == 1
    assert not unmatched and not skipped
    p = pairs[0]
    assert p["lossy_fields"]["title"] == "Real Title"
    assert p["overwrite"] is False  # the AIFF had no tags


def test_lossy_without_sibling_is_unmatched(tmp_path):
    _write_mp3(tmp_path / "orphan.mp3")
    _set_args(tmp_path)

    pairs, unmatched, skipped = LosslessTagCopy().compute()

    assert not pairs and not skipped
    assert unmatched == [str(tmp_path / "orphan.mp3")]


def test_more_than_one_lossless_sibling_is_skipped(tmp_path):
    _write_mp3(tmp_path / "dup.mp3")
    _write_aiff(tmp_path / "dup.aiff")
    _write_aiff(tmp_path / "dup.aif")
    _set_args(tmp_path)

    pairs, unmatched, skipped = LosslessTagCopy().compute()

    assert not pairs and not unmatched
    assert len(skipped) == 1
    assert ">1 lossless sibling" in skipped[0][1]


def test_lossy_without_id3_is_skipped(tmp_path):
    (tmp_path / "bare.mp3").write_bytes(b"no id3 here" * 8)
    _write_aiff(tmp_path / "bare.aiff")
    _set_args(tmp_path)

    pairs, unmatched, skipped = LosslessTagCopy().compute()

    assert not pairs
    assert skipped and "no ID3 tag" in skipped[0][1]


def test_zero_byte_lossless_is_skipped(tmp_path):
    _write_mp3(tmp_path / "z.mp3")
    (tmp_path / "z.aiff").write_bytes(b"")
    _set_args(tmp_path)

    pairs, unmatched, skipped = LosslessTagCopy().compute()

    assert not pairs
    assert skipped and "zero-byte" in skipped[0][1]


def test_unsupported_lossless_target_is_skipped(tmp_path):
    _write_mp3(tmp_path / "t.mp3")
    (tmp_path / "t.flac").write_bytes(b"fLaC fake")
    _set_args(tmp_path, lossless_exts=".aiff,.flac")

    pairs, unmatched, skipped = LosslessTagCopy().compute()

    assert not pairs
    assert skipped and "unsupported lossless target" in skipped[0][1]


@pytest.mark.parametrize(
    "ignore_case,expect_pairs", [(False, 0), (True, 1)], ids=["exact", "ignore-case"]
)
def test_basename_case_sensitivity(tmp_path, ignore_case, expect_pairs):
    _write_mp3(tmp_path / "Song.mp3")
    _write_aiff(tmp_path / "song.aiff")
    _set_args(tmp_path, ignore_case=ignore_case)

    pairs, unmatched, _skipped = LosslessTagCopy().compute()

    assert len(pairs) == expect_pairs
    # The lossy file is unmatched in the exact-match case.
    assert len(unmatched) == (1 - expect_pairs)


def test_copy_pair_write_path_backs_up_aligns_name_and_deletes_lossy(tmp_path):
    """End-to-end of the actual mutation: backup → wholesale ID3 copy → NAME-chunk
    alignment → lossy delete (bypassing the interactive confirmation)."""
    mp3 = _write_mp3(tmp_path / "song.mp3", title="Real Title", artist="Fred V")
    aiff = _write_aiff(tmp_path / "song.aiff", name_text="Stale NAME")
    ssnd_before = _ssnd_md5(aiff)
    _set_args(tmp_path, write=True, dry_run=False, delete_lossy=True)

    action = LosslessTagCopy()
    pairs, _unmatched, _skipped = action.compute()
    assert len(pairs) == 1
    backup_dir = str(tmp_path / "backups")
    action._copy_pair(pairs[0], backup_dir)

    tags = AIFF(str(aiff)).tags
    assert str(tags["TIT2"].text[0]) == "Real Title"  # tags copied from the MP3
    assert str(tags["TPE1"].text[0]) == "Fred V"
    assert read_name(str(aiff)) == "Real Title"  # NAME chunk aligned to new title
    assert _ssnd_md5(aiff) == ssnd_before  # audio byte-identical
    assert not mp3.exists()  # lossy source deleted after success
    assert (tmp_path / "backups" / str(aiff).lstrip("/")).exists()  # pristine backup


def test_copy_pair_remove_name_strips_chunk_and_keeps_lossy(tmp_path):
    mp3 = _write_mp3(tmp_path / "t.mp3", title="New")
    aiff = _write_aiff(tmp_path / "t.aiff", name_text="Stale NAME")
    _set_args(tmp_path, write=True, dry_run=False, remove_name=True)

    action = LosslessTagCopy()
    pairs, _u, _s = action.compute()
    action._copy_pair(pairs[0], str(tmp_path / "backups"))

    assert read_name(str(aiff)) is None  # NAME chunk stripped → Plex falls back to ID3
    assert str(AIFF(str(aiff)).tags["TIT2"].text[0]) == "New"
    assert mp3.exists()  # lossy kept when --delete-lossy not given


def test_limit_caps_matched_pairs(tmp_path):
    for i in range(3):
        _write_mp3(tmp_path / f"s{i}.mp3")
        _write_aiff(tmp_path / f"s{i}.aiff")
    _set_args(tmp_path, limit=2)

    pairs, _unmatched, _skipped = LosslessTagCopy().compute()

    assert len(pairs) == 2
