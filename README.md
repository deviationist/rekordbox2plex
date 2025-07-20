# rekordbox2plex

**rekordbox2plex** is a Python script that syncs your **track metadata**, **album metadata** and **playlists** from Rekordbox to Plex using [`python-plexapi`](https://github.com/pkkid/python-plexapi). This is especially useful for DJs who manage their music library in Rekordbox and want to reflect the same structure in Plex or Plexamp.

## Features

* ✅ Sync Rekordbox track metadata, album metadata and playlists to Plex
* ✅ Supports file path remapping (e.g. when Plex is running in Docker and the media is mounted on a different path than Rekordbox)
* ✅ Reads Rekordbox’s encrypted SQLite database using `pysqlcipher3` (read-only mode for safety)
* ✅ Colorful console output and progress bars using `rich`
* ❌ No concurrency yet – planned for future versions
* 🛠️ Can be run manually or scheduled via `cron`

## Hierarchical Playlist Flattening

Plex does not support nested or hierarchical playlists, so we flatten the Rekordbox playlist structure during the sync process. This is done by prepending the parent playlist name to each child playlist name.

By default, playlists are joined using the `/` delimiter. You can change this by setting the `PLEX_PLAYLIST_FLATTENING_DELIMITER` environment variable.

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
Parent Playlist/Child Playlist 1
Parent Playlist/Child Playlist 2
Parent Playlist/Child Playlist 3
Parent Playlist/Child Playlist 3/Grand-Child Playlist 1
```

---

## Requirements

* Python 3.8+
* [`Poetry`](https://python-poetry.org/)
* Rekordbox (with access to its encrypted SQLite DB)
* A running Plex server + Plex access token
* Rekordbox and Plex must be on the same file system

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/rekordbox2plex.git
cd rekordbox2plex
```

### 2. Install dependencies

```bash
poetry install
```

### 3. Configure environment variables

Copy the example file and fill in the values:

```bash
cp .env.example .env
```

#### `.env` variables include:

* `REKORDBOX_FOLDER_PATH` – full path to your Rekordbox files (needed when synchronizing album artwork)
* `REKORDBOX_MASTERDB_PATH` – full path to your Rekordbox SQLite DB (not required `REKORDBOX_FOLDER_PATH` if set)
* `REKORDBOX_MASTERDB_PASSWORD` – the password for decrypting the SQLite DB
* `REKORDBOX_COPY_DB_BEFORE_SYNC=true|false` - whether to make a copy of the SQLite DB before starting sync.
* `REKORDBOX_FOLDER_PATHS_TO_IGNORE` - (optional) whether to ignore certain folder paths from the Rekordbox query when looking for new tracks, comma separated paths. Only used when `ADD_NEW_TRACKS` is set to true.
* `REKORDBOX_PLAYLISTS_TO_IGNORE` - (optional) whether to ignore certain playlists from being synced to Plex, comma separated playlist names.
* `PLEX_URL` – your Plex server URL (e.g. [http://localhost:32400](http://localhost:32400))
* `PLEX_TOKEN` – your Plex API token
* `PLEX_LIBRARY_NAME` - your Plex library name that contains your music
* `PLEX_PLAYLIST_FLATTENING_DELIMITER`- (defaults to "/") the delimiter used to flatten hierarchical playlists from Rekordbox (since Plex does not support nested playlists)
* `MAP_TRACK_TITLE=true|false` – (default true) whether to sync the track title to Plex
* `MAP_TRACK_ARTIST=true|false` - (default true) whether to sync the track artist to Plex
* `MAP_TRACK_ALBUM_ARTIST=true|false` - (default true) whether to sync the album artist to Plex
* `MAP_TRACK_ALBUM=true|false` - (default true) whether to sync the album to Plex
* `MAP_TRACK_ARTWORK=true|false` - (default true) whether to sync the track artwork to Plex
* `OVERWRITE_EXISTING_TRACK_ARTWORK=true|false` - (default true) whether to overwrite existing Plex track art with artwork from Rekordbox.
* `ADD_NEW_TRACKS=true|false` - (default true) whether to look for tracks present in Rekordbox but not in Plex, then re-index the folder which contains the new tracks.
* `MAP_ALBUM_YEAR=true|false` - (default true) whether to sync album release year
* `MAP_ALBUM_ARTWORKS=true|false` - (default true) whether to sync album artwork/thumb/poster
* `OVERWRITE_EXISTING_ALBUM_ARTWORK=true|false` - (default true) whether to overwrite existing Plex album art with artwork from Rekordbox.
* `DELETE_ORPHANED_TRACKS=true|false` - (default true) whether to delete orphaned tracks after synchronization
* `DELETE_ORPHANED_PLAYLISTS=true|false` - (default true) whether to delete orphaned playlists after synchronization
* `DELETE_ORPHANED_ALBUMS=false|false` - (default false) whether to delete orphaned albums after synchronization


> 🔐 **How to find your Plex Token?**
> See [this guide](#how-to-find-your-plex-token).

> 🔐 **How to find your Rekordbox database and password?**
> See [this guide](#how-to-find-your-rekordbox-sqlite-db).

### 4. (Optional) Configure folder mappings
If your Plex and Rekordbox libraries are on different paths (e.g., Plex is in Docker and has a different folder mount path), you can create a file to remap file paths:

```bash
cp folderMappings.json.example folderMappings.json
```

Edit `folderMappings.json` to map local Rekordbox paths to Plex-accessible paths:

```json
{
  "/path/to/your/plex/music": "/path/to/your/rekordbox/music"
}
```

### Linting with ruff and mypy
Run `poetry run ruff check .` and `poetry run mypy .`.

### Code formatting with black
Run `poetry run black .`.

---

## Usage

Run the script via Poetry:

```bash
poetry run rekordbox2plex
```

### Arguments
* `-v` and `-vv` - verbosity control (`-v` for info and `-vv`for debug)
* `--dry-run` - no changes will be made
* `--sync=` - what to sync, comma separated list, values: all, tracks, albums, playlists

Example:

This will attempt to synchronize tracks and playlists, but in dry mode so no real changes will be made. The log level is set to debug, meaning that log output will describe each step of the process.
```bash
poetry run rekordbox2plex -vv --dry-run --sync=tracks,playlists
```

### Running via UNIX Cron
To run the sync regularly (e.g. nightly), set up a cron job:

```cron
0 2 * * * cd /path/to/rekordbox2plex && poetry run rekordbox2plex >> sync.log 2>&1
```

---

## How to Find Your Plex Token

TODO: Finish this

## How to Find Your Rekordbox SQLite DB

TODO: Correct this

1. Open Rekordbox.
2. Click **Preferences > Advanced > Database** to see your library location.
3. The SQLite database is typically named something like `master.db`.
4. You’ll also need the encryption password. This varies between Rekordbox versions but tools like [`rekordcloud`](https://rekord.cloud/) or online forums may help identify your password.
5. Ensure `pysqlcipher3` is able to open the DB using the provided password.

---

## Development

This project is using:

* [`python-plexapi`](https://github.com/pkkid/python-plexapi)
* [`pysqlcipher3`](https://pypi.org/project/pysqlcipher3/)
* [`rich`](https://github.com/Textualize/rich)
* [`poetry`](https://python-poetry.org/)

### Goals for future versions

* Add concurrency for faster syncing
* More configurability
* Improved error handling and logging
* Better playlist syncing (e.g., smart playlists)

---

## Contributing

Pull requests, issues and feedback are welcome! Feel free to fork the repo and experiment.

---

## License

MIT License
