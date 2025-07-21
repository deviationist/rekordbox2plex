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

Note that Plex does not allow empty playlists, so empty playlists in Rekordbox will be ignored.

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
Parent Playlist
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

#### Available `.env` variables

| Variable | Type | Default | Description |
|---------|------|---------|-------------|
| `REKORDBOX_FOLDER_PATH` | string | – | Full path to your Rekordbox files (needed for artwork sync) |
| `REKORDBOX_MASTERDB_PATH` | string | – | Full path to your Rekordbox SQLite DB (not required if `REKORDBOX_FOLDER_PATH` is set) |
| `REKORDBOX_MASTERDB_PASSWORD` | string | `402fd...` | Password for decrypting the SQLite DB |
| `REKORDBOX_COPY_DB_BEFORE_SYNC` | bool | `true` | Whether to make a copy the DB file before starting sync |
| `REKORDBOX_FOLDER_PATHS_TO_IGNORE` | string | – | Comma-separated list of folder paths to ignore (only used if `ADD_NEW_TRACKS=true`) |
| `REKORDBOX_PLAYLISTS_TO_IGNORE` | string | – | Comma-separated list of playlist names to ignore |
| `PLEX_URL` | string | – | Your Plex server URL (e.g., `http://localhost:32400`) |
| `PLEX_TOKEN` | string | – | Your Plex API token |
| `PLEX_LIBRARY_NAME` | string | – | Your Plex library name that contains your music |
| `PLEX_PLAYLIST_FLATTENING_DELIMITER` | string | `/` | Delimiter for flattening nested Rekordbox playlists |
| `MAP_TRACK_TITLE` | bool | `true` | Sync track title to Plex |
| `MAP_TRACK_ARTIST` | bool | `true` | Sync track artist to Plex |
| `MAP_TRACK_ALBUM` | bool | `true` | Sync album to Plex |
| `MAP_TRACK_ARTWORK` | bool | `true` | Sync track artwork to Plex |
| `OVERWRITE_EXISTING_TRACK_ARTWORK` | bool | `true` | Overwrite existing Plex track artwork |
| `ADD_NEW_TRACKS` | bool | `true` | Add tracks from Rekordbox missing in Plex and reindex |
| `MAP_ALBUM_RELEASE_YEAR` | bool | `true` | Sync album release year |
| `MAP_ALBUM_RELEASE_DATE` | bool | `true` | Sync album release date |
| `MAP_ALBUM_LABEL` | bool | `true` | Sync album label |
| `MAP_ALBUM_ARTWORKS` | bool | `true` | Sync album artwork/thumb/poster |
| `OVERWRITE_EXISTING_ALBUM_ARTWORK` | bool | `true` | Overwrite existing Plex album artwork |
| `DELETE_ORPHANED_TRACKS` | bool | `true` | Delete orphaned tracks in Plex |
| `DELETE_ORPHANED_PLAYLISTS` | bool | `true` | Delete orphaned playlists in Plex |
| `DELETE_ORPHANED_ALBUMS` | bool | `false` | Delete orphaned albums in Plex |



> 🔐 **How to find your Plex Token?**
> See [this guide](#how-to-find-your-plex-api-token).

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

## How to Find Your Plex API Token

The **Plex API token** (also called `X-Plex-Token`) is needed to authenticate with the Plex server API.

### 🔍 Option 1: Get Token via Web Browser

1. **Sign in to Plex** in your browser:
   Go to [https://app.plex.tv/](https://app.plex.tv/) and log in.

2. **Open Dev Tools**:
   - Right-click anywhere on the page → **Inspect**
   - Go to the **Network** tab
   - Reload the page (F5)

3. **Find a request** to `plex.tv` or your Plex server.
   - Click on a request (e.g., `home`, `resources`, etc.)
   - Look under **Headers**

4. **Search for `X-Plex-Token`**:
   - You’ll see something like:
     ```
     X-Plex-Token: YOUR_TOKEN_HERE
     ```

### 💡 Option 2: Look in a URL

Sometimes the token is included in the URL of a request. Example:

`https://plex.tv/api/resources?includeHttps=1&X-Plex-Token=YOUR_TOKEN_HERE`

### ⚠️ Important Notes

- Treat the token like a **password** – don't share it.
- If your token is ever compromised, you can revoke access by signing out of devices in your Plex settings.

## How to Find Your Rekordbox SQLite DB
1. Open Rekordbox
2. Click **Preferences > Advanced > Database** to see your library location
3. Under "Imported Library" you will see the path to the file `rekordbox.xml`. For Mac-users it will look something like `/Users/yourusername/Library/Pioneer/rekordbox/rekordbox.xml`. Copy the path, replace `rekordbox.xml` with `master.db`. This is the path to your Rekordbox SQLite DB file.

If you don't know your username then:
- For Windows: Press Win + R, type cmd, and hit Enter. Then type `echo %username%` and hit enter.
- For Mac: Open Terminal (press Cmd + Space, type "Terminal", hit Enter). Then type `whoami` and hit enter.

## Rekordbox SQLite DB Password
The password for the Rekordbox SQLite DB is `402fd482c38817c35ffa8ffb8c7d93143b749e7d315df7a81732a1ff43608497` and is already specified in the `.env.example`-file. This password is used to decrypt the database file which is encrypted using [`sqlcipher`](https://www.zetetic.net/sqlcipher/). Thanks to [liamcottle](https://github.com/liamcottle) for his great research into how Rekordbox works. See [this repo](https://github.com/liamcottle/pioneer-rekordbox-database-encryption) for more information.

---

## Development

This project is using:

* [`python-plexapi`](https://github.com/pkkid/python-plexapi)
* [`pysqlcipher3`](https://pypi.org/project/pysqlcipher3/)
* [`rich`](https://github.com/Textualize/rich)
* [`poetry`](https://python-poetry.org/)
* [`poetry`](https://python-poetry.org/)
* [`pytest`](https://docs.pytest.org/)

### Running tests
To run tests: `poetry run pytest`

### Goals for future versions

* Add concurrency for faster syncing

---

## Contributing

Pull requests, issues and feedback are welcome! Feel free to fork the repo and experiment.

---

## License

MIT License
