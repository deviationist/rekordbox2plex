"""Locate (and delete) the on-disk image file behind an uploaded Plex poster.

Clearing ``user_thumb_url`` in the DB only *deselects* a poster — the uploaded
image file lingers in the item's metadata bundle, and Plex's Clean Bundles /
Optimize do NOT remove it (verified). Plex stores each item's metadata under
``<PMS>/Metadata/<Type>/<h[0]>/<h[1:]>.bundle`` where ``h = sha1(guid)``; uploaded
posters live in that bundle's ``Uploads/posters/<upload-hash>``. The files are
owned by the Plex container's uid, so deletion goes through the same
docker-run-as-owner mechanism the DB write uses (no sudo)."""

import hashlib
import os
import subprocess
from typing import List, Optional

_TYPE_DIR = {8: "Artists", 9: "Albums"}


def metadata_dir_from_db_path(db_path: str) -> str:
    """Derive ``…/Plex Media Server/Metadata`` from the library DB path
    (``…/Plex Media Server/Plug-in Support/Databases/com.plexapp….db``)."""
    pms = os.path.dirname(os.path.dirname(os.path.dirname(db_path)))
    return os.path.join(pms, "Metadata")


def bundle_posters_dir(
    metadata_dir: str, metadata_type: int, guid: str
) -> Optional[str]:
    """The ``Uploads/posters`` dir for an item's bundle, or None for an
    unsupported type / empty guid."""
    sub = _TYPE_DIR.get(metadata_type)
    if not sub or not guid:
        return None
    h = hashlib.sha1(guid.encode("utf-8")).hexdigest()
    return os.path.join(
        metadata_dir, sub, h[0], h[1:] + ".bundle", "Uploads", "posters"
    )


def poster_file_path(
    metadata_dir: str, metadata_type: int, guid: str, user_thumb_url: str
) -> Optional[str]:
    """Absolute path of the uploaded image file behind ``user_thumb_url``
    (``upload://posters/<hash>``), or None if it isn't an upload/unsupported."""
    if not user_thumb_url or not user_thumb_url.startswith("upload://"):
        return None
    posters = bundle_posters_dir(metadata_dir, metadata_type, guid)
    if posters is None:
        return None
    return os.path.join(posters, user_thumb_url.rsplit("/", 1)[-1])


def delete_poster_files_docker(
    metadata_dir: str, abs_paths: List[str], image: str
) -> Optional[subprocess.CompletedProcess]:
    """Delete the given files (under metadata_dir) by running ``rm`` inside the
    Plex image as the bundle owner's uid:gid — mirrors PlexDBWriter's docker
    write. Paths are passed NUL-separated on stdin to ``xargs -0`` (handles the
    spaces in Plex's paths and any count). Returns None if there's nothing to do."""
    if not abs_paths:
        return None
    st = os.stat(metadata_dir)
    payload = "\0".join("/meta/" + os.path.relpath(p, metadata_dir) for p in abs_paths)
    cmd = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--user",
        f"{st.st_uid}:{st.st_gid}",
        "-v",
        f"{metadata_dir}:/meta",
        "--entrypoint",
        "/bin/sh",
        image,
        "-c",
        "xargs -0 rm -f",
    ]
    return subprocess.run(cmd, input=payload, capture_output=True, text=True)
