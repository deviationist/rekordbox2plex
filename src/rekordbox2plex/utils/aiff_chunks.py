"""Read/write the native AIFF/AIFF-C text chunks that shadow ID3 in Plex.

AIFF (and its compressed superset AIFF-C) carry two parallel metadata systems:
native chunks (``NAME`` = title, etc.) AND an embedded ``ID3 `` chunk. Plex reads
the native ``NAME`` chunk for the title in preference to ID3 ``TIT2`` — so a stale
``NAME`` (frozen at file-conversion time, never updated by OneTagger which only
writes ID3) makes Plex display the wrong title. This module reads the ``NAME``
chunk + ID3 ``TIT2`` and surgically rewrites/removes the ``NAME`` chunk while
leaving the audio (``SSND``) and the ``ID3 `` chunk untouched.

Layout: ``FORM`` + 4-byte big-endian size + a form type + a sequence of chunks,
each ``<4-byte id><4-byte BE size><size bytes data><1 pad byte if size is odd>``
(word-aligned). The form type is ``AIFF`` for plain AIFF or ``AIFC`` for AIFF-C;
everything after the 12-byte header is identical, so both are handled here. (Many
``.aiff`` files are actually AIFF-C with no compression, distinguished only by the
form type, hence we accept both.)
"""

import hashlib
import os
import shutil
import struct
from typing import Iterator, Optional, Tuple

# FORM type tag (bytes 8:12). AIFF = uncompressed; AIFC = AIFF-C (may be
# compressed, but often just little-endian/uncompressed PCM). We only touch the
# NAME chunk, never COMM/SSND, so the compression type is irrelevant here.
_FORM_TYPES = (b"AIFF", b"AIFC")


def _iter_chunks(data: bytes) -> Iterator[Tuple[bytes, int, int, int]]:
    """Yield (chunk_id, header_offset, data_size, total_size) for each top-level
    chunk in an in-memory AIFF, where total_size includes the 8-byte header and
    any pad byte."""
    pos = 12  # skip FORM(4) + size(4) + form-type(4)
    n = len(data)
    while pos + 8 <= n:
        cid = data[pos : pos + 4]
        size = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        total = 8 + size + (size & 1)
        yield cid, pos, size, total
        pos += total


def read_name(path: str) -> Optional[str]:
    """Return the native AIFF ``NAME`` chunk text, or None if there is none.

    Streams chunk headers and seeks over chunk bodies, so the multi-MB ``SSND``
    payload is never read into memory."""
    with open(path, "rb") as f:
        if f.read(4) != b"FORM":
            return None
        f.seek(4, os.SEEK_CUR)  # skip FORM size
        if f.read(4) not in _FORM_TYPES:  # form type: AIFF or AIFC
            return None
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            cid = header[:4]
            size = struct.unpack(">I", header[4:8])[0]
            if cid == b"NAME":
                raw = f.read(size)
                return raw.rstrip(b"\x00").decode("utf-8", "replace")
            f.seek(size + (size & 1), os.SEEK_CUR)  # skip data + pad
    return None


def read_id3_title(path: str) -> Optional[str]:
    """Return the embedded ID3 ``TIT2`` (title) text, or None if absent."""
    from mutagen.aiff import AIFF

    try:
        audio = AIFF(path)
    except Exception:
        return None
    tags = audio.tags
    if not tags or "TIT2" not in tags:
        return None
    frame = tags["TIT2"]
    try:
        return str(frame.text[0])
    except (AttributeError, IndexError):
        return str(frame)


def _validate(
    new_data: bytes,
    ssnd_md5_before: Optional[str],
    had_id3: bool,
    expected_name: Optional[str],
) -> None:
    if new_data[:4] != b"FORM" or new_data[8:12] not in _FORM_TYPES:
        raise ValueError("rewrite produced non-AIFF data")
    if struct.unpack(">I", new_data[4:8])[0] != len(new_data) - 8:
        raise ValueError("FORM size mismatch after rewrite")
    ssnd_after: Optional[str] = None
    id3_after = False
    name_after: Optional[str] = None
    for cid, off, size, total in _iter_chunks(new_data):
        if cid == b"SSND":
            ssnd_after = hashlib.md5(new_data[off : off + total]).hexdigest()
        elif cid == b"ID3 ":
            id3_after = True
        elif cid == b"NAME":
            name_after = (
                new_data[off + 8 : off + 8 + size]
                .rstrip(b"\x00")
                .decode("utf-8", "replace")
            )
    if ssnd_md5_before is not None and ssnd_after != ssnd_md5_before:
        raise ValueError("audio (SSND) changed during rewrite — aborting")
    if had_id3 and not id3_after:
        raise ValueError("ID3 chunk lost during rewrite — aborting")
    if expected_name is None:
        if name_after is not None:
            raise ValueError("NAME chunk still present after removal")
    elif name_after != expected_name:
        raise ValueError("NAME chunk not set to the expected value")


def rewrite_name(
    path: str, new_value: Optional[str], backup_dir: Optional[str]
) -> Optional[str]:
    """Set the AIFF ``NAME`` chunk to ``new_value`` (or remove it when
    ``new_value`` is None), preserving audio + ID3, file owner and mode.

    Backs the original up under ``backup_dir`` (mirroring its absolute path)
    before writing. Validates that ``SSND`` bytes are byte-identical and the
    ``ID3 `` chunk survives. Returns the previous NAME value (for logging).
    Raises ValueError on any integrity failure (the original is left intact)."""
    st = os.stat(path)
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"FORM" or data[8:12] not in _FORM_TYPES:
        raise ValueError(f"not an AIFF/AIFF-C file: {path}")

    name_span: Optional[Tuple[int, int]] = None
    old_name: Optional[str] = None
    ssnd_md5_before: Optional[str] = None
    had_id3 = False
    for cid, off, size, total in _iter_chunks(data):
        if cid == b"NAME" and name_span is None:
            name_span = (off, total)
            old_name = (
                data[off + 8 : off + 8 + size]
                .rstrip(b"\x00")
                .decode("utf-8", "replace")
            )
        elif cid == b"SSND":
            ssnd_md5_before = hashlib.md5(data[off : off + total]).hexdigest()
        elif cid == b"ID3 ":
            had_id3 = True

    if new_value is None:
        if name_span is None:
            return old_name  # nothing to remove
        start, total = name_span
        new_data = data[:start] + data[start + total :]
    else:
        encoded = new_value.encode("utf-8")
        chunk = (
            b"NAME"
            + struct.pack(">I", len(encoded))
            + encoded
            + (b"\x00" if len(encoded) & 1 else b"")
        )
        if name_span is None:
            # Insert after a leading FVER chunk if present (AIFF-C requires FVER
            # first), otherwise right after the 12-byte FORM header.
            first = next(_iter_chunks(data), None)
            insert_at = (
                first[1] + first[3] if first is not None and first[0] == b"FVER" else 12
            )
            new_data = data[:insert_at] + chunk + data[insert_at:]
        else:
            start, total = name_span
            new_data = data[:start] + chunk + data[start + total :]

    # Recompute the FORM size (file length minus the 8-byte FORM header).
    new_data = new_data[:4] + struct.pack(">I", len(new_data) - 8) + new_data[8:]

    _validate(new_data, ssnd_md5_before, had_id3, new_value)

    if backup_dir:
        dest = os.path.join(backup_dir, path.lstrip("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)

    tmp = path + ".r2p.tmp"
    with open(tmp, "wb") as f:
        f.write(new_data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        os.chown(path, st.st_uid, st.st_gid)
    except (PermissionError, OSError):
        pass
    os.chmod(path, st.st_mode & 0o7777)
    return old_name
