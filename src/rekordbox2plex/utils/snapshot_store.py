"""The sidecar store for the ``rb-dates`` snapshot→apply flow.

When a lossy file is about to be swapped for a lossless one, we capture the
lossy file's Rekordbox "Date Added" (raw ``created_at`` string) *before* the
swap and stash it here, keyed by the **lossless** file's path. After the user
re-adds the lossless file in Rekordbox (which resets its date to "now"), the
``apply`` phase reads this back and restores the original date onto the new row.

The store is a plain JSON object: ``{ lossless_path: entry }``. Snapshots merge
into it across runs; ``apply`` prunes entries it has successfully restored so the
backlog shrinks and re-runs stay idempotent. Storing the *raw* timestamp string
means we restore it byte-for-byte — no timezone reconstruction.
"""

import json
import os
import tempfile
from typing import Dict, Iterable, Optional, TypedDict


class SnapshotEntry(TypedDict):
    lossy_path: str
    rb_field: str
    value: str  # the raw Rekordbox timestamp, e.g. "2020-09-17 22:16:29.060 +00:00"
    source_rb_id: int
    captured_at: str  # ISO-8601 of when we captured it (provenance only)


SnapshotStore = Dict[str, SnapshotEntry]


def load(path: str) -> SnapshotStore:
    """Load the sidecar, or return an empty store if it's missing/unreadable."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save(path: str, store: SnapshotStore) -> None:
    """Atomically write the sidecar (temp file + os.replace) as pretty JSON."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def merge_entry(store: SnapshotStore, lossless_path: str, entry: SnapshotEntry) -> bool:
    """Insert/replace one entry keyed by the lossless path. Returns True when the
    stored content changed (new key, or a different captured value)."""
    prev: Optional[SnapshotEntry] = store.get(lossless_path)
    store[lossless_path] = entry
    return prev is None or prev.get("value") != entry.get("value")


def prune(store: SnapshotStore, keys: Iterable[str]) -> int:
    """Remove the given lossless-path keys (e.g. successfully-applied ones).
    Returns how many were removed."""
    removed = 0
    for k in keys:
        if store.pop(k, None) is not None:
            removed += 1
    return removed
