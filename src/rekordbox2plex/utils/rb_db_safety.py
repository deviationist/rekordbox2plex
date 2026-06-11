"""Preconditions that make a write to the Resilio-synced Rekordbox ``master.db``
safe — the "free up the DB before we touch it" guard.

The DB is a single file synced across workstations by Resilio, and Rekordbox may
be open on any of them. We can't see a remote Rekordbox from here, so the real
protection is: refuse to write unless the file looks quiescent (no open handle, no
in-flight WAL, not being modified), and always back it up first. These checks are
heuristics layered behind an explicit human checklist — defence in depth, not a
substitute for closing Rekordbox everywhere.
"""

import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import Callable, List, Optional, Tuple


class DBNotQuiescent(Exception):
    """Raised when ``master.db`` looks in-use/in-flight and a write must abort."""


def sidecar_paths(db_path: str) -> List[str]:
    """The SQLite sidecars Resilio must carry alongside the main DB."""
    return [db_path + suffix for suffix in ("-wal", "-shm")]


def wal_state(db_path: str) -> Tuple[bool, int]:
    """Return (dirty, wal_size_bytes). ``dirty`` is True if a non-empty ``-wal``
    or any ``-shm`` exists — a sign of an open or uncleanly-closed connection."""
    wal = db_path + "-wal"
    shm = db_path + "-shm"
    wal_size = os.path.getsize(wal) if os.path.isfile(wal) else 0
    shm_present = os.path.isfile(shm)
    return (wal_size > 0 or shm_present, wal_size)


def _stat_signature(db_path: str) -> tuple:
    """A (path, size, mtime_ns) tuple for the DB and its ``-wal`` — changes if
    anything writes to either between samples."""
    sig: List[tuple] = []
    for p in (db_path, db_path + "-wal"):
        try:
            st = os.stat(p)
            sig.append((p, st.st_size, st.st_mtime_ns))
        except FileNotFoundError:
            sig.append((p, None, None))
    return tuple(sig)


def probe_stable(
    db_path: str,
    wait_seconds: float,
    samples: int = 2,
    sleep_func: Callable[[float], None] = time.sleep,
) -> bool:
    """Require ``samples`` consecutive identical stat signatures, each separated by
    ``wait_seconds``. Any change ⇒ something (Resilio mid-sync, Rekordbox) is
    writing ⇒ not stable. ``sleep_func`` is injectable for tests."""
    prev = _stat_signature(db_path)
    for _ in range(max(1, samples)):
        sleep_func(wait_seconds)
        cur = _stat_signature(db_path)
        if cur != prev:
            return False
        prev = cur
    return True


def local_open_handle(db_path: str) -> Optional[str]:
    """Best-effort: if a process *on this host* holds ``master.db`` open, return a
    one-line description, else None. Can't see a remote Rekordbox — that's what the
    human checklist is for. Silently returns None if ``lsof`` is unavailable."""
    try:
        out = subprocess.run(
            ["lsof", "--", db_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    lines = [ln for ln in out.stdout.splitlines()[1:] if ln.strip()]
    return lines[0] if lines else None


def backup_rekordbox_db(db_path: str, backup_dir: str) -> str:
    """Copy ``master.db`` (+ any ``-wal``/``-shm``) into a timestamped subdir of
    ``backup_dir``. Returns the backup directory path (the recovery point)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backup_dir, f"master.db-{stamp}")
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(db_path, os.path.join(dest, os.path.basename(db_path)))
    for side in sidecar_paths(db_path):
        if os.path.isfile(side):
            shutil.copy2(side, os.path.join(dest, os.path.basename(side)))
    return dest


def assert_db_quiescent(
    db_path: str,
    *,
    wait_seconds: float,
    samples: int = 2,
    ignore_wal: bool = False,
    allow_running: bool = False,
) -> None:
    """Raise ``DBNotQuiescent`` (with an actionable message) unless the DB looks
    free to write. ``allow_running`` bypasses every check (scratch-copy testing)."""
    if allow_running:
        return
    if not os.path.isfile(db_path):
        raise DBNotQuiescent(f"Rekordbox DB not found at {db_path}")

    dirty, wal_size = wal_state(db_path)
    if dirty and not ignore_wal:
        raise DBNotQuiescent(
            f"{db_path}-wal is non-empty ({wal_size} bytes) or a -shm exists — "
            "Rekordbox is likely open or was not closed cleanly. Close it on every "
            "workstation (a clean close checkpoints the WAL), then retry "
            "(or pass --ignore-wal if you are certain)."
        )

    handle = local_open_handle(db_path)
    if handle is not None:
        raise DBNotQuiescent(
            f"A process on this host has {db_path} open:\n  {handle}\n"
            "Close it before writing."
        )

    if not probe_stable(db_path, wait_seconds, samples):
        raise DBNotQuiescent(
            f"{db_path} changed during the {wait_seconds:g}s stability window — "
            "something is still writing it (Resilio mid-sync, or Rekordbox open). "
            "Pause Resilio and close Rekordbox everywhere, then retry."
        )
