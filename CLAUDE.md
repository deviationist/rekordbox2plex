# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

This tool **only mirrors Rekordbox playlists into Plex**. Audio file tags are the source of truth for track and album metadata — Plex picks them up on its own scan. Do not add code that pushes track/album metadata, artwork, field locks, or library-scan triggers via the Plex API; that path was deliberately removed.

## Commands

- Run sync: `poetry run rekordbox2plex` (flags: `-v`/`-vv`, `--dry-run`, `--wipe`)
- Tests: `poetry run pytest` — single test: `poetry run pytest tests/TrackIdMapper_test.py::test_track_mapper`
- Lint: `poetry run ruff check .`
- Type-check: `poetry run mypy .` (`plexapi.*` and `pysqlcipher3` are excluded via overrides in `pyproject.toml`)
- Format: `poetry run black .`

Python 3.12+ is required. Tests live next to factories in `tests/`.

## Architecture

The flow is **Plex-driven**: walk every Plex track once to build an in-memory `Plex ratingKey ↔ Rekordbox track ID` map, then iterate Rekordbox playlists and translate each playlist's track IDs back to Plex track objects to construct/update the corresponding Plex playlist.

### Layers (under `src/rekordbox2plex/`)

- `actions/` — orchestration. `PlaylistSync` (default) and `PlaylistWipe` (`--wipe`). Both extend `_ActionBase.ActionBase`, which captures `is_dry_run()` once at construction.
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

Env vars are documented in `README.md` and `.env.example`. Most are required Plex/Rekordbox connection details; the only optional sync knobs are `DELETE_ORPHANED_PLAYLISTS`, `REKORDBOX_PLAYLISTS_TO_IGNORE`, `PLEX_PLAYLIST_FLATTENING_DELIMITER`, and `FOLDER_MAPPINGS_PATH`.
