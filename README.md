# rekordbox2plex

**rekordbox2plex** is a Python script that syncs your **track metadata**, **album metadata** and **playlists** from Rekordbox to Plex using [`python-plexapi`](https://github.com/pkkid/python-plexapi). This is especially useful for DJs who manage their music library in Rekordbox and want to reflect the same structure in Plex or Plexamp.

![rekordbox2plex screenshot](https://raw.githubusercontent.com/deviationist/rekordbox2plex/main/screenshot.png)

## Features

* ✅ Sync Rekordbox track metadata, album metadata and playlists to Plex
* ✅ Supports file path remapping (e.g. when Plex is running in Docker and the media is mounted on a different path than Rekordbox)
* ✅ Reads Rekordbox’s encrypted SQLite database using `pysqlcipher3` (read-only mode for safety)
* ✅ Colorful console output and progress bars using `rich`
* ❌ No concurrency yet – planned for future versions
* 🛠️ Can be run manually or scheduled via `cron`

### The problem
Using Plex and Plexamp for listening to music is great, but the indexing and organizing is pretty shit tbh. I attempted to add my whole collection of tracks from my DJ collection (WAV, AIFF, MP3s) to Plex and it ended up being extremely messy. I wanted a Spotify-like experience with my own music collection, but ended up with an unorganized mess. If I could only get the neat and organized structure from Rekordbox in Plex then it would be much better!

### The solution
I created this script to get the best of two worlds - the availability of Plex/Plexamp for listening, and the structure (metadata, playlists) from Rekordbox. This script bridges this gap, by taking control over the metadata in Plex by "mapping"/mirroring the structure from Rekordbox. Because of this I finally reached my goal of getting a Spotify-like experience in Plexamp, with my own curated music. This allows me to listen on the go, to have an active listening-relationship with my collection, re-discover old tracks, or delete tracks I no longer want in my collection. I hope this tool can do the same for you!

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

### Album Metadata Resolving
So Rekordbox bases everything of tracks, and each track have a title, artist, album, album artist etc. Under the hood Rekordbox will create these artists, albums and album artists in separate tables (`djmdArtists` and `djdmAlbums`), but this is not visible in the Rekordbox GUI. But Plex works a bit different – it builds an artist index based on the artist on the album (not the artist specified on the track) which can lead to some confusion. The best way to solve this is not make sure that each track in Rekordbox has values for the title, artist, album artist and album fields.

But even if all the metadata in Rekordbox is correct there are still some challenges - let's say you have an album with 4 tracks, and not all tracks have the same artwork. In Rekordbox the artwork is stored on the track, but in Plex it is stored on the album. This script will compare all the artworks of the tracks, evaluate whether they are similar, and if so then the artwork will be selected and sync'ed to album in Plex. If the artworks are not the same then no artwork will be sync'ed to Plex. The same logic works for `release year`, `release date` and `label` which are all stored on the tracks in Rekordbox, but on the album in Plex. To sum it up - when working with album metadata we try to resolve the "unison" metadata from the Rekordbox tracks and apply it to the Plex album.

### Field Locking
Plex supports field locking, meaning that Plex will not touch then when reindexing etc. This is useful since we want the data to come from Rekordbox, and leave all the other metadata out. This behaviour can be granularly controlled using the environment variables.

### Plex Configuration
These are the recommended settings for your music library:

#### Prefer local metadata
Find your music library, click "Manage Library" -> "Edit..." -> "Advanced" -> check "Prefer local metadata"

### Other comments
This solution is made for a library that only contains music from Rekordbox. I have not yet tested combining multiple "sources" of music files. It might work, but the safest solution is to have a dedicated library for your Rekordbox music.

I have not yet tested Rekordbox Intelligent Playlists, but from what I can see so far it should work as any other playlists.


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
| `PLEX_LOCK_FIELDS` | bool | `true` | Whether to lock the fields in Plex |
| `MAP_TRACK_TITLE` | bool | `true` | Sync track title to Plex |
| `MAP_TRACK_ARTIST` | bool | `true` | Sync track artist to Plex |
| `MAP_TRACK_ALBUM` | bool | `true` | Sync album to Plex |
| `MAP_TRACK_ARTWORK` | bool | `true` | Sync track artwork to Plex |
| `LOCK_TRACK_TITLE` | bool | `true` | Lock track title |
| `LOCK_TRACK_ARTIST` | bool | `true` | Lock track artist |
| `LOCK_TRACK_ARTWORK` | bool | `true` | Lock track artwork |
| `OVERWRITE_EXISTING_TRACK_ARTWORK` | bool | `true` | Overwrite existing Plex track artwork with Rekordbox artwork |
| `ADD_NEW_TRACKS` | bool | `true` | Re-index folders with new tracks to add them to Plex |
| `MAP_ALBUM_RELEASE_YEAR` | bool | `true` | Sync album release year |
| `MAP_ALBUM_RELEASE_DATE` | bool | `true` | Sync album release date |
| `MAP_ALBUM_LABEL` | bool | `true` | Sync album label |
| `MAP_ALBUM_ARTWORKS` | bool | `true` | Sync album artwork/thumb/poster |
| `LOCK_ALBUM_TITLE` | bool | `true` | Lock album title |
| `LOCK_ALBUM_SORT_TITLE` | bool | `true` | Lock album sort title |
| `LOCK_ALBUM_YEAR` | bool | `true` | Lock album year |
| `LOCK_ALBUM_DATE` | bool | `true` | Lock album field "Originally available" |
| `LOCK_ALBUM_LABEL` | bool | `true` | Lock album record label |
| `LOCK_ALBUM_ARTWORK` | bool | `true` | Lock album artwork |
| `OVERWRITE_EXISTING_ALBUM_ARTWORK` | bool | `true` | Overwrite existing Plex album artwork with Rekordbox artwork |
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
