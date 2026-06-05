# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

This tool does three things, exposed as subcommands:

1. **`playlists`** — mirrors Rekordbox playlists into Plex. Audio file tags are the source of truth for track/album metadata — Plex picks them up on its own scan. Do **not** add code that pushes track/album metadata, artwork, field locks, or library-scan triggers **via the Plex API**; that path was deliberately removed.
2. **`dates`** — syncs "Date Added" (`metadata_items.added_at`) from Rekordbox `djmdContent.created_at` by a **direct write to the Plex SQLite DB** (the Plex HTTP API has no `added_at` setter). This is a *sanctioned* DB write and is distinct from the removed API metadata-push path. It **reads the Plex library straight from the DB** (`plex/PlexDBReader.py::read_library`, not the API) and computes changes **in memory — no SQL file is written** (the write streams SQL to Plex SQLite over stdin; `--plan-file` optionally dumps it). **Read-only by default** (`--dry-run`); writing requires `--write`, Plex stopped, and the `WRITE-DATES` token. Idempotent (only rows whose date differs). See `actions/DateAddedRestore.py`, `plex/PlexDBReader.py`, `plex/PlexDBWriter.py`.
3. **`parity`** — a **strictly read-only** audit comparing Title/Artist/Album/AlbumArtist 1:1 between Rekordbox and Plex, plus orphan (one-system-only) coverage gaps. Reads Plex from the DB (`plex/PlexDBReader.py::read_tracks_metadata`) and Rekordbox via `rekordbox/resolvers/metadata.py`; matches by file path with the shared `resolve_track_id_by_plex_path`. Comparison is normalized (`utils/normalize.py` — trim/collapse-whitespace/casefold) but raw values are shown. **It must never write** to either DB: no `PlexDBWriter` import, no `--write`, `SELECT`-only. See `actions/ParityCheck.py`.

## Commands

- Sync playlists: `poetry run rekordbox2plex playlists` (flags: `-v`/`-vv`, `--dry-run`, `--wipe`)
- Preview Date Added (read-only, no file): `poetry run rekordbox2plex dates --dry-run` (flags: `--only <ratingKeys>`, `--no-tracks`/`--no-albums`, `--validate-track <ratingKey>`, `--validate-album <ratingKey>`, `--plan-file <path>` to optionally dump SQL)
- Apply Date Added (destructive; Plex must be stopped): `poetry run rekordbox2plex dates --write` — see README "Syncing Date Added" for the manual backup + `docker compose down`/`up` runbook
- Metadata parity audit (read-only): `poetry run rekordbox2plex parity` (flags: `--fields title,artist,album,albumartist`, `--only <ratingKeys>`, `--no-orphans`, `--orphan-limit <N>`, `--json`; env `REKORDBOX_FOLDER_PATHS_TO_IGNORE`)
- Tests: `poetry run pytest` — single test: `poetry run pytest tests/TrackIdMapper_test.py::test_track_mapper`
- Lint: `poetry run ruff check .`
- Type-check: `poetry run mypy .` (`plexapi.*` and `pysqlcipher3` are excluded via overrides in `pyproject.toml`)
- Format: `poetry run black .`

Python 3.12+ is required. Tests live next to factories in `tests/`.

## Architecture

The flow is **Plex-driven**: walk every Plex track once to build an in-memory `Plex ratingKey ↔ Rekordbox track ID` map, then iterate Rekordbox playlists and translate each playlist's track IDs back to Plex track objects to construct/update the corresponding Plex playlist.

### Layers (under `src/rekordbox2plex/`)

- `actions/` — orchestration. `PlaylistSync` / `PlaylistWipe` (`playlists` subcommand) and `DateAddedRestore` (`dates` subcommand). All extend `_ActionBase.ActionBase`. `DateAddedRestore` reuses the Rekordbox path resolver (`resolve_track_id_by_plex_path`) but enumerates Plex from the DB (`plex/PlexDBReader.py::read_library` — tracks/albums for the configured library, scoped by `library_sections`), computes the plan in memory, and writes via `plex/PlexDBWriter.py` (`build_plan_sql` → bundled "Plex SQLite" in a `docker run` **as the DB file's owner uid** — stock `sqlite3` can't, due to Plex's FTS-trigger tokenizer). Key facts: a Plex `ratingKey` **is** its `metadata_items.id` (so the write is a keyed `UPDATE … WHERE id = ?`); album `added_at` is the **min** of its member tracks. `PlexDBReader._connect_ro` copes with both WAL-live (Plex running) and checkpointed (Plex stopped) states. `ParityCheck` (`parity` subcommand) follows the same Plex-from-DB + path-resolver pattern but compares metadata only — it enumerates Plex via `read_tracks_metadata` (self-joins track→album→artist for the four fields), reads Rekordbox via `rekordbox/resolvers/metadata.py`, and writes nothing.
- `mappers/TrackIdMapper.py` — singleton dict `rb_track_id → PlexTrackWrapper`. `ensure_mappings()` lazily walks every Plex track and resolves its Rekordbox ID via `rekordbox/resolvers/track.py::resolve_track_id` (single-column lookup by file path).
- `plex/repositories/` — cached accessors over `plexapi`. Extend `_RepositoryBase.RepositoryBase`, wrapped in the local `singleton` decorator.
- `plex/resolvers/` and `rekordbox/resolvers/` — thin functional wrappers around the SDKs / SQL queries.
- `rekordbox/RekordboxDB.py` — singleton SQLCipher connection. By default (`REKORDBOX_COPY_DB_BEFORE_SYNC=true`) it copies `master.db` to a tempfile and opens it read-only (`mode=ro`) before applying `PRAGMA key`. The temp copy is deleted via `atexit`. Always treat the Rekordbox DB as read-only.
- `config.py` — central env / CLI accessor. CLI args are stashed via `set_args(...)` in `__main__.py` and read back through `is_dry_run()`, `should_wipe()`, etc.

### Key cross-cutting flows

- **Folder path mapping** (`rekordbox/resolvers/track.py::convert_path_to_rekordbox`) translates Plex file paths into the paths Rekordbox stored, so a Plex track can be looked up in `djmdContent` by `FolderPath`. The JSON file (`folderMappings.json` or `FOLDER_MAPPINGS_PATH`) is loaded once and cached in `utils/folder_mappings.py::get_folder_mappings`. A missing file is a one-shot soft warning unless `FOLDER_MAPPINGS_PATH` was set explicitly (then it raises).
- **Playlist flattening**: Rekordbox supports nested playlists, Plex does not. Names are joined with `PLEX_PLAYLIST_FLATTENING_DELIMITER` (default `/`). Empty playlists are skipped because Plex rejects them.
- **Wipe protection**: `--wipe` is destructive (deletes every Plex playlist). `__main__.py` requires the user to type the literal token `WIPE` (case-sensitive) via `utils/confirm.py::confirm_destructive`. `--dry-run --wipe` previews without prompting.

### Configuration

Env vars are documented in `README.md` and `.env.example`. Most are required Plex/Rekordbox connection details; optional playlist knobs are `DELETE_ORPHANED_PLAYLISTS`, `REKORDBOX_PLAYLISTS_TO_IGNORE`, `PLEX_PLAYLIST_FLATTENING_DELIMITER`, and `FOLDER_MAPPINGS_PATH`. The `dates` subcommand adds `PLEX_DB_PATH` (host path to `com.plexapp.plugins.library.db`), `PLEX_CONTAINER_NAME` (default `plex`, checked stopped before a write), `PLEX_SQLITE_MECHANISM` (`docker`|`sqlite3`), `PLEX_DOCKER_IMAGE`, `PLEX_SQLITE_BIN`, `REKORDBOX_TZ` (only for naive timestamps), and `REKORDBOX_ADDED_AT_FIELD` (default `created_at`). The `parity` subcommand reuses `PLEX_DB_PATH` and adds `REKORDBOX_FOLDER_PATHS_TO_IGNORE` (comma-separated substrings; a track whose Rekordbox `FolderPath` contains any is excluded from the check on both sides — same substring convention as `REKORDBOX_PLAYLISTS_TO_IGNORE`).
