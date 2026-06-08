# AGENTS.md

Canonical agent guidance for this repo lives in **[`CLAUDE.md`](./CLAUDE.md)** — read it
first. This file is a thin pointer so tools that look for `AGENTS.md` find the same rules.
Keep the two in sync (or keep detail in `CLAUDE.md` and only a summary here).

## Scope guardrails

This tool has six subcommands:

- **`playlists`** — mirrors Rekordbox playlists into Plex over the HTTP API. **Do not** add
  code that pushes track/album metadata, artwork, field locks, or scan triggers via the Plex
  API; that path was deliberately removed (audio file tags are the source of truth). The
  **only sanctioned artwork exceptions** are the artist-poster *upload* in `artist-images` and
  the poster *clearing* in `clear-art` (both below) — they do **not** loosen the rule for
  track/album metadata or art from tags.
- **`dates`** — syncs "Date Added" (`metadata_items.added_at`) from Rekordbox
  `djmdContent.created_at` via a **direct, guarded write to the Plex SQLite DB** (the HTTP API
  has no `added_at` setter). Read-only by default; `--write` requires Plex stopped + the
  `WRITE-DATES` token. This DB write is sanctioned and distinct from the removed API path.
- **`parity`** — **strictly read-only** audit comparing Title/Artist/Album/AlbumArtist 1:1
  between Rekordbox and Plex, plus one-system-only orphans. Reads Plex from the DB and
  Rekordbox read-only; **never writes** to either (no `PlexDBWriter`, no `--write`,
  `SELECT`-only). Comparison is normalized; raw values are shown.
- **`aiff-titles`** — repairs AIFF/AIFF-C files whose legacy native `NAME` chunk (which Plex
  reads for the title) shadows the correct ID3 `TIT2` (which Rekordbox/OneTagger use). A
  **direct edit of the audio file on disk** (not via the Plex API) — it fixes the source tag
  so Plex picks it up. Read-only by default; `--write` requires the `WRITE-TITLES` token,
  backs up every original, and leaves the audio (`SSND`) + ID3 chunk byte-identical. Needs
  `PLEX_MEDIA_PATH_MAP` to map Plex container paths → host paths.
- **`artist-images`** — sets Plex **artist posters** for a local-metadata library that has no
  artist art (the one **sanctioned artwork-via-API exception** — artist posters only, never
  track/album art). Identity (MBID + canonical name) comes from Plex's own agent match
  (read-only, no rebind) with a MusicBrainz fallback; the portrait is fetched from providers
  in order — **fanart.tv → TheAudioDB → Deezer → Spotify → Discogs** — with name-verification
  (no wrong-artist matches) and content-based placeholder rejection. `--collab-mode` handles
  multi-artist "A, B" strings (`primary` or `collage`). Read-only by default; `--write`
  prompts `WRITE-IMAGES`.
- **`clear-art`** — removes uploaded **artist/album posters**: clears
  `metadata_items.user_thumb_url` via a **direct, guarded Plex DB write** (the only way to
  delete an uploaded poster — the HTTP API can't) **and** deletes the on-disk image file from
  the bundle (`--keep-files` to skip). `--kind artist|album|both`, `--only <ratingKeys>`.
  Read-only by default; `--write` requires Plex stopped + the `CLEAR-IMAGES` token (same
  bundled "Plex SQLite" mechanism as `dates`).

Always treat the Rekordbox DB as read-only.

## Commands

```bash
poetry run rekordbox2plex playlists [--dry-run] [--wipe]
poetry run rekordbox2plex dates [--dry-run] [--only <ratingKeys>] [--no-tracks|--no-albums]
poetry run rekordbox2plex dates --write            # Plex must be stopped; prompts WRITE-DATES
poetry run rekordbox2plex parity [--fields title,artist,album,albumartist] [--only <ratingKeys>] [--no-orphans] [--orphan-limit N] [--json]
#   read-only audit; env REKORDBOX_FOLDER_PATHS_TO_IGNORE excludes folder-path prefixes
poetry run rekordbox2plex aiff-titles [--dry-run] [--only <ratingKeys>]
poetry run rekordbox2plex aiff-titles --write [--remove-name] [--refresh-plex] [--backup-dir <dir>]
#   fixes AIFF/AIFF-C NAME-chunk titles shadowing ID3; prompts WRITE-TITLES; env PLEX_MEDIA_PATH_MAP required
poetry run rekordbox2plex artist-images [--dry-run] [--overwrite] [--collab-mode skip|primary|collage] [--providers ...] [--only <ratingKeys>] [--limit N] [--threads N]
poetry run rekordbox2plex artist-images --write    # uploads posters; prompts WRITE-IMAGES
#   sets ARTIST posters: MBID from Plex match → fanart.tv,TheAudioDB,Deezer,Spotify,Discogs;
#   name-verified; rejects placeholder/blank(single-color) images; collage mode composites collabs.
#   env: PLEX_ARTIST_IMAGE_PROVIDERS, DISCOGS_TOKEN|KEY/SECRET, FANARTTV_API_KEY, SPOTIFY_CLIENT_ID/SECRET, THEAUDIODB_API_KEY
poetry run rekordbox2plex clear-art [--kind artist|album|both] [--only <ratingKeys>] [--keep-files]
poetry run rekordbox2plex clear-art --write        # Plex stopped; prompts CLEAR-IMAGES
#   removes uploaded posters: clears DB user_thumb_url + deletes the on-disk bundle file (unless --keep-files)

poetry run pytest          # tests
poetry run ruff check .    # lint
poetry run mypy .          # types
poetry run black .         # format
```

Python 3.12+. See `CLAUDE.md` for architecture, the `dates` write mechanism (bundled "Plex
SQLite" via `docker run` as the DB-file owner), and configuration/env vars.
