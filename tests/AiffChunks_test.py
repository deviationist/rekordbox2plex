import hashlib
import struct

import pytest
from mutagen.aiff import AIFF
from mutagen.id3 import TIT2

from rekordbox2plex.utils.aiff_chunks import read_id3_title, read_name, rewrite_name


def _chunk(cid: bytes, data: bytes) -> bytes:
    out = cid + struct.pack(">I", len(data)) + data
    if len(data) & 1:  # AIFF chunks are word-aligned
        out += b"\x00"
    return out


def _build_aiff(name_text=None, samples=b"\x01\x02\x03\x04" * 4, aifc=False) -> bytes:
    """A minimal but valid AIFF or AIFF-C (mutagen-parseable).

    AIFF: COMM + optional NAME + SSND, form type ``AIFF``.
    AIFF-C: leading FVER + extended COMM (compressionType + name) + optional NAME
    + SSND, form type ``AIFC`` (uncompressed, compressionType ``NONE``).
    """
    sample_rate_80bit = bytes([0x40, 0x0E, 0xAC, 0x44, 0, 0, 0, 0, 0, 0])  # 44100 Hz
    n_frames = len(samples) // (2 * 2)  # 2 channels, 16-bit
    comm = (
        struct.pack(">h", 2)
        + struct.pack(">I", n_frames)
        + struct.pack(">h", 16)
        + sample_rate_80bit
    )
    body = b""
    if aifc:
        body += _chunk(b"FVER", struct.pack(">I", 0xA2805140))  # AIFC version stamp
        comp_name = b"not compressed"
        comm += b"NONE" + bytes([len(comp_name)]) + comp_name  # compressionType + pstr
    body += _chunk(b"COMM", comm)
    if name_text is not None:
        body += _chunk(b"NAME", name_text.encode("utf-8"))
    body += _chunk(b"SSND", struct.pack(">I", 0) + struct.pack(">I", 0) + samples)
    form = (b"AIFC" if aifc else b"AIFF") + body
    return b"FORM" + struct.pack(">I", len(form)) + form


def _ssnd_md5(path: str):
    with open(path, "rb") as f:
        data = f.read()
    pos = 12
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        total = 8 + size + (size & 1)
        if cid == b"SSND":
            return hashlib.md5(data[pos : pos + total]).hexdigest()
        pos += total
    return None


def _make_track(tmp_path, name_text, id3_title, aifc=False):
    p = tmp_path / "track.aiff"
    p.write_bytes(_build_aiff(name_text=name_text, aifc=aifc))
    audio = AIFF(str(p))
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=[id3_title]))
    audio.save()
    return p


# Run every case against both plain AIFF and AIFF-C, since Plex reads the NAME
# chunk for both and the only structural difference is the form type / FVER.
@pytest.mark.parametrize("aifc", [False, True], ids=["aiff", "aifc"])
def test_read_name_and_id3(tmp_path, aifc):
    p = _make_track(tmp_path, "Old Title", "Correct Title", aifc=aifc)
    assert read_name(str(p)) == "Old Title"
    assert read_id3_title(str(p)) == "Correct Title"


@pytest.mark.parametrize("aifc", [False, True], ids=["aiff", "aifc"])
def test_set_name_to_id3_preserves_audio_and_id3(tmp_path, aifc):
    p = _make_track(tmp_path, "Old Title", "Correct Title", aifc=aifc)
    ssnd_before = _ssnd_md5(str(p))
    backup = tmp_path / "backups"

    old = rewrite_name(str(p), "Correct Title", str(backup))

    assert old == "Old Title"
    assert read_name(str(p)) == "Correct Title"  # NAME now matches ID3
    assert read_id3_title(str(p)) == "Correct Title"  # ID3 untouched
    assert _ssnd_md5(str(p)) == ssnd_before  # audio byte-identical
    assert (backup / str(p).lstrip("/")).exists()  # backup mirrors absolute path
    data = p.read_bytes()
    assert struct.unpack(">I", data[4:8])[0] == len(data) - 8  # FORM size consistent


@pytest.mark.parametrize("aifc", [False, True], ids=["aiff", "aifc"])
def test_remove_name_falls_back_to_id3(tmp_path, aifc):
    p = _make_track(tmp_path, "Old Title", "Keep ID3", aifc=aifc)
    ssnd_before = _ssnd_md5(str(p))

    rewrite_name(str(p), None, None)

    assert read_name(str(p)) is None  # NAME chunk gone
    assert read_id3_title(str(p)) == "Keep ID3"  # ID3 preserved
    assert _ssnd_md5(str(p)) == ssnd_before


@pytest.mark.parametrize("aifc", [False, True], ids=["aiff", "aifc"])
def test_remove_when_no_name_is_noop(tmp_path, aifc):
    p = _make_track(tmp_path, None, "Only ID3", aifc=aifc)
    ssnd_before = _ssnd_md5(str(p))
    assert read_name(str(p)) is None
    rewrite_name(str(p), None, None)  # nothing to remove
    assert read_name(str(p)) is None
    assert _ssnd_md5(str(p)) == ssnd_before


def test_insert_name_keeps_fver_first_in_aifc(tmp_path):
    """Setting NAME on an AIFC file that has none must keep FVER as the first
    chunk (AIFF-C requires it)."""
    p = _make_track(tmp_path, None, "Title", aifc=True)
    rewrite_name(str(p), "New Name", None)
    data = p.read_bytes()
    first_chunk_id = data[12:16]
    assert first_chunk_id == b"FVER"
    assert read_name(str(p)) == "New Name"
    assert read_id3_title(str(p)) == "Title"
