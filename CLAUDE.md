# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Run sync: `poetry run rekordbox2plex` (flags: `-v`/`-vv`, `--dry-run`, `--wipe`, `--targets=tracks,playlists,albums`)
- Tests: `poetry run pytest` — single test: `poetry run pytest tests/TrackIdMapper_test.py::test_track_mapper`
- Lint: `poetry run ruff check .`
- Type-check: `poetry run mypy .` (`plexapi.*` and `pysqlcipher3` are excluded via overrides in `pyproject.toml`)
- Format: `poetry run black .`

Python 3.12+ is required. Tests live next to factories in `tests/` and use `faker` plus the helpers under `tests/factories/`.

## Architecture

The pipeline is **Plex-driven, not Rekordbox-driven**: each sync iterates Plex items and looks them up in Rekordbox, not the other way around. The exception is `add_new_tracks` in `TrackSync`, which finds Rekordbox tracks missing from Plex and triggers a folder re-index via `update_library`.

### Layers (under `src/rekordbox2plex/`)

- `actions/` — top-level orchestration, one class per sync target (`TrackSync`, `AlbumSync`, `PlaylistSync`, plus `*Wipe` variants). All extend `_ActionBase.ActionBase`, which captures `is_dry_run()` once at construction.
- `mappers/` — translate a resolved Rekordbox record into Plex `edit()` payloads. `TrackMetadataMapper` and `AlbumMetadataMapper` extend `_MapperBase.MapperBase`, accumulating changes in `self.edits` and flipping `did_change`. The mapper's `transfer()` builds the diff; `save()` applies it (skipped under `--dry-run` by the calling action).
- `plex/repositories/` — cached accessors over `plexapi`. All extend `_RepositoryBase.RepositoryBase` and are wrapped in the local `singleton` decorator. Repositories own a `_cache` dict keyed by `ratingKey` (or a custom resolver) and an optional `SearchCache` for search-by-name lookups.
- `plex/resolvers/` and `rekordbox/resolvers/` — thin functional wrappers around the SDKs / SQL queries. Resolvers contain the actual SQL strings and `plexapi` calls; repositories cache their output.
- `rekordbox/RekordboxDB.py` — singleton SQLCipher connection. By default (`REKORDBOX_COPY_DB_BEFORE_SYNC=true`) it copies `master.db` to a tempfile and opens it read-only (`mode=ro`) before applying `PRAGMA key`. The temp copy is deleted via `atexit`. Always treat the Rekordbox DB as read-only.
- `config.py` — central env / CLI accessor. CLI args are stashed via `set_args(...)` in `__main__.py` and read back through `is_dry_run()`, `should_wipe()`, etc. Modules should import these helpers rather than calling `os.getenv` directly (a few places still use `os.getenv` for Plex creds and `MAP_*`/`LOCK_*` flags via `get_boolenv`).

### Key cross-cutting flows

- **`TrackIdMapper` (singleton in `mappers/`)** is the bridge between sync stages. `TrackSync` populates it as it resolves each Plex track in Rekordbox, then `PlaylistSync` calls `ensure_mappings()` to translate Rekordbox playlist members back into Plex `Track` objects. If playlists are synced without tracks first, `ensure_mappings()` lazily rebuilds the index by walking the full Plex library.
- **Folder path mapping** (`rekordbox/resolvers/track.py::convert_path_to_rekordbox` and `plex/resolvers/track.py::convert_path_to_plex`) translates between Plex and Rekordbox paths in both directions — Plex→Rekordbox for DB lookups, Rekordbox→Plex when telling Plex to re-index a folder. The JSON file (`folderMappings.json` or `FOLDER_MAPPINGS_PATH`) is loaded once and cached in `utils/folder_mappings.py::get_folder_mappings`; both resolvers consume it. A missing file is a one-shot soft warning unless `FOLDER_MAPPINGS_PATH` was set explicitly (then it raises).
- **Album "unison" metadata resolution**: Rekordbox stores release year / release date / label / artwork on tracks, but Plex stores them on the album. `AlbumMetadataMapper` (and `utils/AlbumArtworkResolver.py` + `utils/ImageHashComparer.py`) compare across all tracks of an album and only apply a value to Plex when the tracks agree. Image similarity uses perceptual hashing.
- **Field locking**: when `PLEX_LOCK_FIELDS=true` and a per-field `LOCK_*` is true, the mapper adds `<field>.locked=1` to the edit payload so Plex won't overwrite the value during reindex. `helpers.field_is_locked` checks the live state to avoid redundant writes.
- **Reparenting in `TrackMetadataMapper.save()`** is split into two `edit()` calls: artist/album reparenting first, then remaining metadata. This is intentional — combining them in one call has been observed to drop edits in plexapi.
- **Playlist flattening**: Rekordbox supports nested playlists, Plex does not. Names are joined with `PLEX_PLAYLIST_FLATTENING_DELIMITER` (default `/`). Empty playlists are skipped because Plex rejects them.
- **Lookup overrides** (`PLEX_TRACK_LOOKUP_OVERRIDE`, `PLEX_ALBUM_LOOKUP_OVERRIDE`, `PLEX_PLAYLIST_LOOKUP_OVERRIDE`) restrict the Plex search to a single item — useful for debugging one record. `helpers.check_for_dangerous_config` blocks combining an override with the matching `DELETE_ORPHANED_*` flag (it would delete most of the library).

### Configuration

Env vars are documented exhaustively in `README.md`. The defaults in `helpers.get_boolenv` calls within the codebase are the source of truth and may differ from `.env.example` — when adding a new flag, default it in both places.
