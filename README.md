# rekordbox2plex

**rekordbox2plex** keeps Plex in sync with Rekordbox. It does two things, each its own subcommand:

- **`playlists`** — mirror your Rekordbox playlist tree into Plex (with nested-playlist flattening), using [`python-plexapi`](https://github.com/pkkid/python-plexapi).
- **`dates`** — restore Plex **"Date Added"** from when each track actually entered your Rekordbox collection (Plex has no API for this, so it's a guarded direct write to the Plex DB).

It's designed for DJs who curate in Rekordbox and want the same playlists — and the real collection-entry dates — available for listening in Plex / Plexamp.

![rekordbox2plex screenshot](https://raw.githubusercontent.com/deviationist/rekordbox2plex/main/screenshot.png)

## What this does (and doesn't) do

* ✅ Read your Rekordbox playlist tree, flatten nested playlists, and create/update the equivalent playlists in Plex.
* ✅ Optionally delete Plex playlists that no longer exist in Rekordbox.
* ✅ **Sync "Date Added"** from Rekordbox into Plex (`rekordbox2plex dates`). Like playlists, Date Added is Plex-internal state that doesn't live in audio file tags — Rekordbox knows when each track entered your collection, Plex doesn't (especially after re-importing a library). This is **read-only by default** and writes directly to the Plex DB only with explicit opt-in. See [Syncing "Date Added"](#syncing-date-added).
* ✅ Reads Rekordbox's encrypted SQLite database with `pysqlcipher3` in read-only mode.
* ✅ Supports file path remapping (e.g. when Plex is running in Docker on a different mount than Rekordbox).
* ❌ **Does not sync track or album metadata, artwork, release year, label, etc.** — this is on purpose. The right place to fix that data is in the audio file tags themselves; once the file is correct, Plex will pick it up on its next library scan. Pushing metadata via the Plex API is fragile and fights the platform.
* ❌ Does not trigger Plex library scans for new files. Plex auto-scan or a cron job is the right tool for that.

### Why playlists only?

Playlists are the one piece of state that doesn't live in audio files — Plex stores them in its own database, and so does Rekordbox. Everything else (titles, artists, album, artwork, year, label) is best maintained inside the file tags. If your Plex library is messy, fix the tags in your DJ tool of choice; don't paper over it with API writes.

## Why this project was scaled down

Earlier versions of `rekordbox2plex` synced track titles, artists, albums, artwork, release year, label, and triggered Plex library re-indexing for new files. It worked, but it was a constant fight with Plex.

Plex's music agent re-reads file tags on every library scan. The initial plan here was to push the Rekordbox metadata via the Plex API and then lock each field so the next reindex couldn't overwrite our values. That partly worked — but Plex doesn't just re-read titles. It actively orchestrates the artist and album-artist hierarchy on every scan: merging duplicate artists, splitting tracks by `originalTitle`, deciding which artist node a track belongs to. Once we started locking fields, every scan became a battle. Plex would try to restructure the tree, our locks would block half the changes, and the result was a library that was neither the file's truth nor Plex's truth — just a frozen-in-time snapshot of our last sync, drifting further from disk every day.

The realization: **the audio file is the source of truth.** If a track's metadata is wrong in Plex, the tag in the file is wrong. Fix it there and Plex will align on the next scan. No locks, no API writes, no drift, no battling Plex.

Once that became clear, almost everything in this tool was redundant. Playlists are the one exception — they're stored in each platform's own database, not in audio files, so the only way to get Rekordbox's playlist tree into Plex is via the API.

So the metadata sync, artwork sync, field locks, orphan track/album deletion, and library-scan trigger were all removed. What's left is a single, well-defined job: **mirror the Rekordbox playlist tree into Plex**. Smaller surface, fewer dependencies, no fights with the platform.

If you need the old metadata-syncing version, the git history still has it.

## Recommended workflow for fixing metadata

If a track shows up wrong in Plex (wrong title, missing album, no artwork, wrong year, etc.), the fix lives in the audio file's tags — not in Plex.

**The recommended path is to edit the metadata in Rekordbox itself and then re-index Plex.** Rekordbox writes its track metadata (title, artist, album, album artist, year, label, comments, artwork) back to the file's tags, so once you've polished a track in Rekordbox the audio file is correct, and the next Plex scan picks it up. No external tools needed for the common case — perfecting the metadata in Rekordbox and triggering a Plex re-index is the way to go.

Then trigger a Plex library scan from the UI ("Scan Library Files") or wait for the auto-scan, and run `rekordbox2plex` to mirror your playlists across.

If you do need a dedicated tag editor — Rekordbox can't write a particular field, or you're cleaning up a fresh batch of imports outside of Rekordbox — these are the usual suspects:

- **Meta** — macOS, paid. Very popular among DJs.
- [**Mp3tag**](https://www.mp3tag.de/) — Windows / macOS, free.
- [**Kid3**](https://kid3.kde.org/) — cross-platform (Linux / Windows / macOS), open source.
- [**MusicBrainz Picard**](https://picard.musicbrainz.org/) — auto-tags by matching against the MusicBrainz database. Useful when importing unfamiliar music in bulk.

> **Format gotcha**: WAV and AIFF have historically had patchy tag-writing support across tools. If a tag editor can't write to a particular format, converting to FLAC (lossless, well-supported tags) is usually the cleanest fix. MP3, FLAC, and M4A all handle tags reliably.

## Hierarchical Playlist Flattening

Plex does not support nested playlists, so we flatten the Rekordbox playlist structure during the sync. Each child playlist's name is prepended with its parents' names, joined by `PLEX_PLAYLIST_FLATTENING_DELIMITER` (default `/`). Empty playlists in Rekordbox are skipped because Plex rejects them.

**Rekordbox structure:**

```
Parent Playlist
├─ Child Playlist 1
├─ Child Playlist 2
└─ Child Playlist 3
   └─ Grand-Child Playlist 1
```

**Flattened Plex structure:**

```
Parent Playlist
Parent Playlist/Child Playlist 1
Parent Playlist/Child Playlist 2
Parent Playlist/Child Playlist 3
Parent Playlist/Child Playlist 3/Grand-Child Playlist 1
```

## Requirements

* Python 3.12+
* [`Poetry`](https://python-poetry.org/)
* Rekordbox (with access to its encrypted SQLite DB)
* A running Plex server + Plex access token
* Plex must be able to see the same files as Rekordbox (same paths, or remapped via `folderMappings.json`)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/deviationist/rekordbox2plex.git
cd rekordbox2plex
```

### 2. Install dependencies

```bash
poetry install
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

#### Available `.env` variables

| Variable | Type | Default | Description |
|---------|------|---------|-------------|
| `REKORDBOX_FOLDER_PATH` | string | – | Folder containing your Rekordbox files. Used as a fallback to locate `master.db` if `REKORDBOX_MASTERDB_PATH` is unset. |
| `REKORDBOX_MASTERDB_PATH` | string | – | Full path to your Rekordbox SQLite DB. |
| `REKORDBOX_MASTERDB_PASSWORD` | string | `402fd...` | Password for decrypting the SQLite DB. |
| `REKORDBOX_COPY_DB_BEFORE_SYNC` | bool | `true` | Copy `master.db` to a tempfile before syncing (recommended). |
| `REKORDBOX_PLAYLISTS_TO_IGNORE` | string | – | Comma-separated list of playlist names to skip. |
| `PLEX_URL` | string | – | Your Plex server URL (e.g., `http://localhost:32400`). |
| `PLEX_TOKEN` | string | – | Your Plex API token. |
| `PLEX_LIBRARY_NAME` | string | – | The Plex library that contains your music. |
| `PLEX_PLAYLIST_FLATTENING_DELIMITER` | string | `/` | Delimiter for flattening nested Rekordbox playlists. |
| `DELETE_ORPHANED_PLAYLISTS` | bool | `false` | Delete Plex playlists that don't exist in Rekordbox. |
| `FOLDER_MAPPINGS_PATH` | string | – | Override the path to the folder-mapping JSON (default: `./folderMappings.json`). |
| `PLEX_DB_PATH` | string | – | (`dates` only) Host path to `com.plexapp.plugins.library.db`. Needed for the write and the read-only cross-check. |
| `PLEX_CONTAINER_NAME` | string | `plex` | (`dates` only) Docker container checked to be **stopped** before any write. |
| `PLEX_SQLITE_MECHANISM` | string | `docker` | (`dates` only) `docker` = bundled "Plex SQLite" in the container image (**required for Plex** — runs as the DB file's owner). `sqlite3` = stock sqlite3; does **not** work on a real Plex schema (FTS-trigger tokenizer), kept only for non-Plex/advanced use. |
| `PLEX_DOCKER_IMAGE` | string | `linuxserver/plex` | (`dates` only) Image providing the bundled Plex SQLite binary. |
| `PLEX_SQLITE_BIN` | string | `/usr/lib/plexmediaserver/Plex SQLite` | (`dates` only) Path to that binary inside the image. |
| `REKORDBOX_ADDED_AT_FIELD` | string | `created_at` | (`dates` only) `djmdContent` column used as the source date. |
| `REKORDBOX_TZ` | string | host local | (`dates` only) Timezone for interpreting *naive* Rekordbox timestamps. Ignored for offset-aware ones like `created_at`. |

> 🔐 **How to find your Plex Token?** See [this guide](#how-to-find-your-plex-api-token).
>
> 🔐 **How to find your Rekordbox database and password?** See [this guide](#how-to-find-your-rekordbox-sqlite-db).

### 4. (Optional) Configure folder mappings

If your Plex and Rekordbox libraries have different paths (e.g., Plex in Docker), create `folderMappings.json` to remap them:

```bash
cp folderMappings.json.example folderMappings.json
```

Map each Plex path to the corresponding Rekordbox path:

```json
{
  "/path/to/your/plex/music": "/path/to/your/rekordbox/music"
}
```

---

## Usage

The tool has two subcommands — **`playlists`** and **`dates`** — which you can run independently:

```bash
poetry run rekordbox2plex playlists          # mirror Rekordbox playlists into Plex
poetry run rekordbox2plex dates --dry-run     # preview the "Date Added" sync (read-only)
poetry run rekordbox2plex dates --write       # apply it (Plex must be stopped; see below)
```

- **`playlists`** — arguments below.
- **`dates`** — full read-only-preview → write workflow in [Syncing "Date Added"](#syncing-date-added).

### `playlists` arguments

* `-v` / `-vv` — verbosity (`-v` = info, `-vv` = debug)
* `--dry-run` — preview changes without applying them
* `--wipe` — delete **all** playlists in your Plex library. Requires typing the literal word `WIPE` to confirm.

### Running via cron

```cron
0 2 * * * cd /path/to/rekordbox2plex && poetry run rekordbox2plex playlists >> sync.log 2>&1
```

## Syncing "Date Added"

Plex stores a track's/album's "Date Added" as `metadata_items.added_at`. There's **no Plex HTTP API to set it**, so this is the one place the tool writes directly to Plex's SQLite database. The `dates` subcommand reads the Plex library **straight from that DB** (reusing the same Rekordbox path→date resolver as playlist sync), computes the changes **in memory**, and is built to be cautious:

* **Read-only by default.** `rekordbox2plex dates` (or `--dry-run`) resolves every Plex track to Rekordbox, computes the proposed `added_at` from `djmdContent.created_at`, and prints a summary + sample of the changes. It never touches the DB. **No SQL file is written** — the plan lives in memory. (Pass `--plan-file <path>` if you *want* a SQL dump to inspect.)
* **Idempotent.** It only changes rows whose date actually differs, so re-running after adding new tracks in Rekordbox just tops up what changed.
* **Writing is opt-in and guarded.** `--write` proceeds only when (1) you pass it explicitly, (2) the Plex container is stopped (verified via `docker inspect`), and (3) you type the confirmation token `WRITE-DATES`. The SQL is streamed to the bundled Plex SQLite over stdin — still no file on disk.
* **The DB backup is your job, not the tool's.** The script *checks* that Plex is stopped, but never stops Plex and never backs up the database for you.

### Workflow

```bash
# 1. Preview (Plex can stay running). Prints what would change — no file, no writes.
poetry run rekordbox2plex dates --dry-run
#    Scope flags: --no-albums (tracks only), --no-tracks (albums only).
#    Inspect a single item in detail: --validate-track <ratingKey> --validate-album <ratingKey>
#    Want the full SQL to eyeball? add: --plan-file /tmp/plan.sql

# 2. Stop Plex and BACK UP THE DATABASE (manual, required).
cd /home/xavi/docker-root/plex && docker compose down
#    Back up the DB plus its -wal and -shm siblings (a clean shutdown usually
#    checkpoints the -wal/-shm away, leaving just the .db):
DB="database/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"
cp "$DB"      "$DB.bak"
cp "$DB-wal"  "$DB-wal.bak"   # if present
cp "$DB-shm"  "$DB-shm.bak"   # if present

# 3. Write (Plex stopped). Recomputes and applies; prompts for WRITE-DATES.
cd /path/to/rekordbox2plex && poetry run rekordbox2plex dates --write

# 4. Start Plex again.
cd /home/xavi/docker-root/plex && docker compose up -d
```

> **Tip — verify on a copy first.** Copy the DB to a scratch path, point `PLEX_DB_PATH` at it, and run `dates --write --allow-running` (keep the default `docker` mechanism). Re-query a few `added_at` values to confirm before touching the real DB. Note: the `sqlite3` mechanism **cannot** be used against a real Plex schema — Plex's full-text-search triggers reference a custom tokenizer only the bundled "Plex SQLite" build provides (and that build must run as the DB file's owner), so writes must go through the `docker` mechanism.

### `dates` arguments

* `--dry-run` — preview changes without writing (also the default; overrides `--write` if both are given).
* `--validate-track <ratingKey>` / `--validate-album <ratingKey>` — read-only single-item view; prints the Rekordbox-vs-Plex timestamps and the exact UPDATE that *would* run.
* `--only <ratingKeys>` — comma-separated Plex ratingKeys to sync only those items, e.g. `--only 17779,17776`. A **track** id updates that track; an **album** id updates that album (its date is still the earliest across *all* its tracks). Works with `--dry-run` and `--write`.
* `--no-tracks` / `--no-albums` — restrict scope (both included by default). Album `added_at` is the **earliest** of its tracks.
* `--plan-file <path>` — optional: also dump the SQL plan to a file for inspection (off by default).
* `--write` — apply the changes to the Plex DB (Plex must be stopped; prompts for `WRITE-DATES`).
* `--allow-running` — bypass the stopped-check (**only** for scratch-copy testing).

---

## How to Find Your Plex API Token

1. Sign in to Plex at [https://app.plex.tv/](https://app.plex.tv/).
2. Open Dev Tools → Network tab → reload.
3. Click any request and look for an `X-Plex-Token` header. (It also appears in many request URLs.)

Treat the token like a password.

## How to Find Your Rekordbox SQLite DB

1. Open Rekordbox.
2. Preferences → Advanced → Database. Note the "Imported Library" path; it points at `rekordbox.xml`. Replace `rekordbox.xml` with `master.db` for the SQLite DB path.

The DB password is `402fd482c38817c35ffa8ffb8c7d93143b749e7d315df7a81732a1ff43608497` (already in `.env.example`). Thanks to [liamcottle](https://github.com/liamcottle) for [the encryption research](https://github.com/liamcottle/pioneer-rekordbox-database-encryption).

---

## Development

* [`python-plexapi`](https://github.com/pkkid/python-plexapi)
* [`pysqlcipher3`](https://pypi.org/project/pysqlcipher3/)
* [`rich`](https://github.com/Textualize/rich)
* [`poetry`](https://python-poetry.org/)
* [`pytest`](https://docs.pytest.org/)

```bash
poetry run pytest               # tests
poetry run ruff check .         # lint
poetry run mypy .               # types
poetry run black .              # format
```

---

## Contributing

Pull requests, issues and feedback welcome.

## License

MIT
