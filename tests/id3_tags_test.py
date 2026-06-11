import hashlib
import struct

from mutagen.aiff import AIFF
from mutagen.id3 import APIC, ID3, TALB, TCON, TIT2, TPE1

from rekordbox2plex.utils.aiff_chunks import read_name
from rekordbox2plex.utils.id3_tags import copy_id3_wholesale, read_id3_fields

# 1x1 transparent PNG — stand-in for embedded artwork (APIC).
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _chunk(cid: bytes, data: bytes) -> bytes:
    out = cid + struct.pack(">I", len(data)) + data
    if len(data) & 1:  # AIFF chunks are word-aligned
        out += b"\x00"
    return out


def _build_aiff(name_text=None, samples=b"\x01\x02\x03\x04" * 4) -> bytes:
    """A minimal, mutagen-parseable AIFF: COMM + optional NAME + SSND."""
    sample_rate_80bit = bytes([0x40, 0x0E, 0xAC, 0x44, 0, 0, 0, 0, 0, 0])  # 44100 Hz
    n_frames = len(samples) // (2 * 2)  # 2 channels, 16-bit
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


def _make_mp3(path, title="Title", artist="Artist", album="Album", art=True):
    """A tag-only 'MP3' (ID3 head, no audio frames) — enough for the copy."""
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=[artist]))
    tags.add(TALB(encoding=3, text=[album]))
    tags.add(TCON(encoding=3, text=["Drum & Bass"]))
    if art:
        tags.add(APIC(encoding=3, mime="image/png", type=3, desc="", data=_PNG))
    tags.save(str(path))
    return path


def test_copy_id3_wholesale_transfers_all_frames_and_preserves_audio(tmp_path):
    mp3 = _make_mp3(tmp_path / "track.mp3", title="Real Title", artist="Fred V")
    aiff = tmp_path / "track.aiff"
    aiff.write_bytes(_build_aiff(name_text="Stale NAME"))
    # Give the AIFF some pre-existing (wrong) ID3 to prove a wholesale replace.
    pre = AIFF(str(aiff))
    pre.add_tags()
    pre.tags.add(TIT2(encoding=3, text=["WRONG"]))
    pre.save()
    ssnd_before = _ssnd_md5(str(aiff))

    new_title = copy_id3_wholesale(str(mp3), str(aiff), v2_version=3)

    assert new_title == "Real Title"
    tags = AIFF(str(aiff)).tags
    assert str(tags["TIT2"].text[0]) == "Real Title"
    assert str(tags["TPE1"].text[0]) == "Fred V"
    assert str(tags["TALB"].text[0]) == "Album"
    assert tags.getall("APIC")  # artwork carried over
    assert tags.version[1] == 3  # saved as ID3 v2.3
    assert _ssnd_md5(str(aiff)) == ssnd_before  # audio byte-identical
    assert read_name(str(aiff)) == "Stale NAME"  # NAME chunk untouched by the copy


def test_read_id3_fields_reads_mp3_and_aiff(tmp_path):
    mp3 = _make_mp3(tmp_path / "x.mp3", title="T", artist="A", album="B")
    fields = read_id3_fields(str(mp3))
    assert fields["title"] == "T"
    assert fields["artist"] == "A"
    assert fields["album"] == "B"
    assert fields["has_artwork"] is True

    aiff = tmp_path / "x.aiff"
    aiff.write_bytes(_build_aiff())
    copy_id3_wholesale(str(mp3), str(aiff))
    aiff_fields = read_id3_fields(str(aiff))
    assert aiff_fields["title"] == "T"
    assert aiff_fields["has_artwork"] is True


def test_read_id3_fields_empty_when_untagged(tmp_path):
    bare = tmp_path / "untagged.mp3"
    bare.write_bytes(b"not an id3 tag at all" * 8)
    assert read_id3_fields(str(bare)) == {}
