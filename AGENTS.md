# AGENTS.md

Canonical agent guidance for this repo lives in **[`CLAUDE.md`](./CLAUDE.md)** — read it
first. This file is a thin pointer so tools that look for `AGENTS.md` find the same rules.
Keep the two in sync (or keep detail in `CLAUDE.md` and only a summary here).

## Scope guardrails

This tool has three subcommands:

- **`playlists`** — mirrors Rekordbox playlists into Plex over the HTTP API. **Do not** add
  code that pushes track/album metadata, artwork, field locks, or scan triggers via the Plex
  API; that path was deliberately removed (audio file tags are the source of truth).
- **`dates`** — syncs "Date Added" (`metadata_items.added_at`) from Rekordbox
  `djmdContent.created_at` via a **direct, guarded write to the Plex SQLite DB** (the HTTP API
  has no `added_at` setter). Read-only by default; `--write` requires Plex stopped + the
  `WRITE-DATES` token. This DB write is sanctioned and distinct from the removed API path.
- **`parity`** — **strictly read-only** audit comparing Title/Artist/Album/AlbumArtist 1:1
  between Rekordbox and Plex, plus one-system-only orphans. Reads Plex from the DB and
  Rekordbox read-only; **never writes** to either (no `PlexDBWriter`, no `--write`,
  `SELECT`-only). Comparison is normalized; raw values are shown.

Always treat the Rekordbox DB as read-only.

## Commands

```bash
poetry run rekordbox2plex playlists [--dry-run] [--wipe]
poetry run rekordbox2plex dates [--dry-run] [--only <ratingKeys>] [--no-tracks|--no-albums]
poetry run rekordbox2plex dates --write            # Plex must be stopped; prompts WRITE-DATES
poetry run rekordbox2plex parity [--fields title,artist,album,albumartist] [--only <ratingKeys>] [--no-orphans] [--orphan-limit N] [--json]
#   read-only audit; env REKORDBOX_FOLDER_PATHS_TO_IGNORE excludes folder-path prefixes

poetry run pytest          # tests
poetry run ruff check .    # lint
poetry run mypy .          # types
poetry run black .         # format
```

Python 3.12+. See `CLAUDE.md` for architecture, the `dates` write mechanism (bundled "Plex
SQLite" via `docker run` as the DB-file owner), and configuration/env vars.
