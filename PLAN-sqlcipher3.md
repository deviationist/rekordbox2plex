# Plan: `pysqlcipher3` → `sqlcipher3-wheels`

Status: **planned, not started** (written 2026-10-17). Everything below marked
*verified* was measured on xavi that day, against copies of the live
`master.db`, in a throwaway environment under `/tmp/sqlc-eval` — the repo and
the live database were not changed.

## Why

On 2026-10-08 xavi moved to Ubuntu 26.04, which ships **Python 3.14 only**.
rekordbox2plex stopped working without anyone noticing — the file-watcher that
triggers it had separately gone deaf to `master.db`, so nothing ran to fail.
Found 2026-10-17:

- The project venv (and poetry's own pipx venv) pointed at `/usr/bin/python3.12`,
  which the upgrade removed.
- **`pysqlcipher3` 1.2.0 does not compile on Python 3.13+.** It calls
  `PyObject_AsCharBuffer` and `_PyLong_AsInt`, both removed from the C API. Its
  last release was January 2023; it publishes no wheels at all.
- pip's cached wheel was linked against `libsqlcipher.so.1`; 26.04 ships
  `libsqlcipher.so.2`. Even on a working Python, a binding that links the
  system library breaks on the next soname bump.

**The stopgap in place now:** the venv runs on **uv's Python 3.12**
(`~/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu`), with `pysqlcipher3`
built from source against `.so.2`:

```sh
uv python install 3.12
poetry env remove --all
poetry env use "$(uv python find 3.12)"
poetry install
poetry run pip install --no-cache-dir --force-reinstall --no-deps \
    --no-binary pysqlcipher3 "pysqlcipher3==1.2.0"
```

That is a pinned interpreter kept alive for one unmaintained C extension. This
plan removes the reason for it.

## Decision: `sqlcipher3-wheels`, pinned `>=0.5.7,<0.6.0`

| candidate | latest | cp314 wheel | SQLCipher inside | verdict |
|---|---|---|---|---|
| `pysqlcipher3` | 1.2.0 (2023-01) | none, sdist only, fails to build on 3.13+ | links system lib | **remove** |
| **`sqlcipher3-wheels`** | 0.5.7 (2026-01-07) | yes | 4.12.0, **static** | **use** |
| `sqlcipher3` | 0.6.4 (2026-10-13) | yes | 4.19.0, static | works too; four days old when measured — revisit later |
| `sqlcipher3-binary` | 0.6.0 (2025-12) | yes | static | superseded; same module name |

- **It is what media-bridge already uses** against this same `master.db`, for
  both reads and live writes (`quim:~/code/media-bridge/pyproject.toml`, with the
  reasoning in a comment). One binding across the two projects that touch the
  file.
- **Statically linked** (*verified*: no `libsqlcipher` in `ldd` of the
  extension, no bundled `.libs`): immune to the soname bump that broke this.
  `libsqlcipher-dev` stops being a build requirement.
- **Ships type stubs** (`py.typed`, `dbapi2.pyi`), so the mypy override for the
  binding can go.
- Upstream: `laggykiller/sqlcipher3`, a wheel-building fork of
  `coleifer/sqlcipher3`; zlib licence.
- **Never install two of these together.** `sqlcipher3`, `sqlcipher3-wheels`
  and `sqlcipher3-binary` all install the module `sqlcipher3`; a second one
  silently overwrites the first. (pyrekordbox depends on `sqlcipher3` — if this
  project ever takes pyrekordbox on, do what media-bridge did.)

## Evidence (verified 2026-10-17)

1. **Identical reads.** pysqlcipher3 (py3.12), sqlcipher3-wheels 0.5.7 and
   sqlcipher3 0.6.4 (both py3.14), each on a fresh copy of `master.db`: same
   `djmdContent` counts (3908 live / 4891 all), same 145 playlists and 11304
   playlist rows, same `localUpdateCount` (345156), same Heat path, and the
   **same SHA-256 over every playlist's membership in order**.
2. **Writes are interchangeable.** Each binding did the `RekordboxDBWriter`
   shape on its own copy (`mode=rw`, key, `busy_timeout`, `BEGIN` → `UPDATE` →
   `COMMIT`, `wal_checkpoint(TRUNCATE)`), and each write was verified by all
   three bindings: 9/9 `integrity_check = ok` and the write seen.
3. **The test suite passes** on Python 3.14 + sqlcipher3-wheels, via a shim
   package mapping `pysqlcipher3.dbapi2` onto `sqlcipher3.dbapi2`: 149 passed.
4. **A real `playlists --dry-run`** on Python 3.14 + sqlcipher3-wheels (Plex
   writes additionally refused at the HTTP layer): mapped 3853/3957 tracks, 132
   playlists, `0 deleted, 0 updated, 0 created` — identical to the production
   run on the 3.12 stopgap minutes earlier.
5. **Every locked dependency** (32 packages) has a wheel that installs on
   CPython 3.14 / linux x86_64. No other upgrade is forced.
6. **mypy.** Baseline with the locked deps is clean. With the import swapped
   and the binding *type-checked* through its stubs, the binding adds no errors.
   (A scratch env that resolved **PlexAPI 4.18.3** instead of the locked
   **4.17.0** showed 6 unrelated errors in `TrackIdMapper.py` / `resolvers/playlist.py`
   — so do not let the lock move PlexAPI as a side effect; see step 3.)

## Steps

Each step says how to know it worked. Do them on a branch; the watcher runs
whatever is checked out in `~/code/rekordbox2plex`, so **pause it first**.

### 0. Pause the trigger

```sh
sudo systemctl stop file-watcher-rekordbox     # a master.db change would run the half-switched tree
```

Restart it in step 8. Pending changes are not lost: the next master.db change,
or a publisher restart within 10 min of one, re-announces it.

### 1. Branch

```sh
git switch -c chore/sqlcipher3
```

### 2. Code: two imports, one explicit flag

- `src/rekordbox2plex/rekordbox/RekordboxDB.py:1` and
  `src/rekordbox2plex/rekordbox/RekordboxDBWriter.py:19`:
  `from pysqlcipher3 import dbapi2 as sqlite` → `from sqlcipher3 import dbapi2 as sqlite`.
  `connect`, `Row`, `Connection`, `PRAGMA key=…`, `busy_timeout`,
  `wal_checkpoint(TRUNCATE)` are all the same API (*verified*).
- **`RekordboxDB.connect` passes the `file:…?mode=ro` URI without `uri=True`.**
  It works only because every build measured has URI filenames on by default
  (*verified* for all three). A build without that default would open — or
  create — a file literally named `file:/tmp/….db?mode=ro`. Add `uri=True`, as
  the writer already does.

### 3. Dependencies — without moving anything else

```sh
poetry add "sqlcipher3-wheels>=0.5.7,<0.6.0"
poetry remove pysqlcipher3
git diff poetry.lock | grep -E '^[-+](name|version) = ' # expect only the two packages
grep -A1 'name = "plexapi"' poetry.lock                 # must still be 4.17.0
```

### 4. mypy

In `pyproject.toml`, delete the `[[tool.mypy.overrides]]` block for
`module = "pysqlcipher3"` — the new binding ships stubs.

```sh
poetry run mypy .        # expect: Success, as today
```

Update `CLAUDE.md:31`, which lists `pysqlcipher3` among the excluded modules.

### 5. Back onto the system Python

```sh
poetry env use python3.14
poetry install
poetry run python -c "from sqlcipher3 import dbapi2 as s; c = s.connect(':memory:'); print(c.execute('PRAGMA cipher_version').fetchone()[0])"
#   → 4.12.0 community
```

Keep the old 3.12 env until step 7 passes (`poetry env list`); then
`poetry env remove <name>`. `uv python uninstall 3.12` only if nothing else on
xavi uses it (see *Out of scope*).

### 6. Tests that exercise the binding

Today **no test opens an encrypted database** — the suite only *imports* the
binding (`rb_date_updates_test.py` imports `RekordboxDBWriter`), so it would
pass on a binding that cannot open master.db. Add, in a new
`tests/rekordbox_db_test.py`, with a fixture that creates a small
SQLCipher-encrypted DB **in WAL mode** under `tmp_path` with a known key and a
minimal `djmdContent` / `djmdPlaylist` / `djmdSongPlaylist` / `agentRegistry`:

- `RekordboxDB` reads it through the temp-copy path, with `row_factory = Row`.
- A wrong key fails with a clear error at the first read (SQLCipher does not
  fail on `PRAGMA key` itself — media-bridge's `rekordbox.py` has the pattern).
- `RekordboxDBWriter` round trip: write a date, checkpoint, reopen read-only,
  see the value; `-wal` empty or absent after `TRUNCATE`.
- **No `-wal`/`-shm` left behind** by the read path (the related fix below).

```sh
poetry run pytest -q     # 149 today, plus the new ones
```

### 7. Against the real database

```sh
COLUMNS=300 poetry run rekordbox2plex playlists --dry-run -vv 2>&1 | grep -E "Mapped|synchronized|Result"
```

Compare with the stopgap's numbers (on 2026-10-17: `Mapped 3853/3957`,
`132 Rekordbox playlists`, `0 deleted, 0 updated, 0 created` once in sync).
They drift as the library changes — run the same command on the old env
(`poetry env use "$(uv python find 3.12)"`) first, if it is still there, and
diff the two. `--dry-run` has been truly read-only since `01af162`; for an
extra belt, the probe in the appendix refuses every non-GET request to Plex.

### 8. Release

```sh
sudo systemctl start file-watcher-rekordbox
```

Then nudge master.db (`rbnudge` on the Mac) and watch
`/var/log/file-watcher/rekordbox.log`: the change, `Debounce expired` 30 s
later, `PLAYLIST SYNC`, `Command completed successfully`. Merge, push.

Update the docs that describe the stopgap:
`~/.claude/shared/topics/music-sync-pipeline.md` (*Rekordbox subscriber* →
"Its Python broke with the 26.04 upgrade"), `README.md:19` and `:505`.

### Rollback

```sh
git switch main                                  # or revert the merge
poetry env use "$(uv python find 3.12)"          # uv install 3.12 again if removed
poetry install
poetry run pip install --no-cache-dir --force-reinstall --no-deps \
    --no-binary pysqlcipher3 "pysqlcipher3==1.2.0"
```

## Related fixes found while measuring (do alongside, separate commits)

### Every run leaks a `-wal` and `-shm` into `/tmp`

*Verified:* opening a WAL-mode database with `mode=ro` **creates** `-wal`
(empty) and `-shm` (32 KB) beside it and leaves them after close — with every
binding. `make_temp_db_copy` copies to `/tmp/tmpXXXX.db`;
`delete_temp_db_copy` removes only the `.db`. On 2026-10-17 xavi's `/tmp` held
9 orphaned pairs from that day's runs. Harmless in size, but wrong.

Fix: open the temp copy with `?mode=ro&immutable=1` (*verified*: no sidecar
files created — and true, since nothing changes a private copy while it is
open), **and** have `delete_temp_db_copy` remove `-wal`/`-shm` siblings too.

### `REKORDBOX_COPY_DB_BEFORE_SYNC=false` would put files into the Resilio folder

It is `true` on xavi, so this is latent. With `false`, the reader opens the
**live** `/mnt/resilio/data/rekordbox/master.db` with `mode=ro`, which (above)
creates an empty `master.db-wal` and a `-shm` beside it. Resilio would sync
them to every Mac running Rekordbox; the file-watcher now watches
`master.db-wal` and would announce it; and media-bridge's Rekordbox writer
refuses to write while a `-wal` exists. Either remove the option (a copy of a
~40 MB file costs nothing), or make the live path use `immutable=1` — which is
only honest if nothing writes the file meanwhile, and Resilio can. Removing it
is the safer choice.

## Out of scope, noticed on the way

Four other poetry envs on xavi are dead the same way (python → the removed
`/usr/bin/python3.12`): `civit-dl`, `kombo`, `kombo-api` (×2). Each needs
`poetry env use python3.14 && poetry install`, and its own check for C
extensions that no longer build. pipx tools (`poetry`, `uv`, `mitmproxy`,
`cocoindex-code`) are fine — `pipx reinstall poetry` was run on 2026-10-17.

## Appendix: the probe

What produced the evidence, condensed. It reads the key from `.env` and never
prints it, and only ever touches copies.

```python
import os, shutil, hashlib, dotenv
from sqlcipher3 import dbapi2 as sqlite          # or: from pysqlcipher3 import dbapi2 as sqlite
dotenv.load_dotenv("/home/xavi/code/rekordbox2plex/.env")
key = os.environ["REKORDBOX_MASTERDB_PASSWORD"]
live = os.environ.get("REKORDBOX_MASTERDB_PATH") or \
    os.environ["REKORDBOX_FOLDER_PATH"].rstrip("/") + "/master.db"
copy = "/tmp/probe-master.db"
shutil.copy2(live, copy)
c = sqlite.connect(f"file:{copy}?mode=ro&immutable=1", uri=True)
c.execute(f"PRAGMA key='{key}'")
q = lambda sql: c.execute(sql).fetchone()[0]
print(q("PRAGMA cipher_version"),
      q("SELECT count(*) FROM djmdContent WHERE rb_local_deleted = 0"),
      q("SELECT count(*) FROM djmdPlaylist WHERE rb_local_deleted = 0"))
h = hashlib.sha256()
for row in c.execute("SELECT p.Name, sp.ContentID, sp.TrackNo FROM djmdSongPlaylist sp "
                     "JOIN djmdPlaylist p ON p.ID = sp.PlaylistID WHERE sp.rb_local_deleted = 0 "
                     "ORDER BY p.Name, sp.TrackNo, sp.ContentID"):
    h.update(repr(tuple(row)).encode())
print("membership", h.hexdigest()[:16])         # equal across bindings = same rows
c.close(); os.remove(copy)
```

To refuse Plex writes during a dry run, regardless of the code under test:

```python
import requests
_orig = requests.Session.request
def guarded(self, method, url, *a, **k):
    if method.upper() != "GET":
        raise RuntimeError(f"refused {method} {url}")
    return _orig(self, method, url, *a, **k)
requests.Session.request = guarded
import sys; sys.argv = ["rekordbox2plex", "playlists", "--dry-run", "-v"]
from rekordbox2plex.__main__ import main; main()
```
