# rekordbox2plex

**rekordbox2plex** is a Python script that syncs your **track metadata** and **playlists** from Rekordbox to Plex using [`python-plexapi`](https://github.com/pkkid/python-plexapi). This is especially useful for DJs who manage their music library in Rekordbox and want to reflect the same structure in Plex or Plexamp.

> ⚠️ This is a **work in progress** and currently an MVP.

## Todo
- "Cosmic Cubes - A Cosmic Trance Compilation Vol. I" <- An example on what needs to be merged to one
- When album artist is empty, default to "VA"? Use track artist?
- Attempt to assign album / album artist via ID if it already exists? Now there seems to be a lot of duplicates...
- Create script to check if there's any orphaned files in my folder structure? Or any tracks that misses it's file?
- Check if there's some artwork that does not get transfered to Plex?
- Write about how playlists are flattened
- Make stuff optional and configurable

## Features

* ✅ Sync Rekordbox track metadata and playlists to Plex
* ✅ Supports file path remapping (e.g. when Plex is running in Docker)
* ✅ Reads Rekordbox’s encrypted SQLite database using `pysqlcipher3` (read-only mode for safety)
* ✅ Colorful console output and progress bars using `rich`
* ❌ No concurrency yet – planned for future versions
* 🛠️ Can be run manually or scheduled via `cron`

---

## Requirements

* Python 3.8+
* [`Poetry`](https://python-poetry.org/)
* Rekordbox (with access to its encrypted SQLite DB)
* A running Plex server
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

* `REKORDBOX_DB_PATH` – full path to your Rekordbox SQLite DB
* `REKORDBOX_DB_PASSWORD` – the password for decrypting the DB
* `PLEX_TOKEN` – your Plex API token
* `PLEX_BASEURL` – your Plex server URL (e.g. [http://localhost:32400](http://localhost:32400))
* `PLEX_LIBRARY_NAME`- your Plex library name that contains your music

> 🔐 **How to find your Plex Token?**
> See [this guide](#how-to-find-your-plex-token).

> 🔐 **How to find your Rekordbox database and password?**
> See [this guide](#how-to-find-your-rekordbox-sqlite-db).

### 4. (Optional) Configure folder mappings

If your Plex and Rekordbox libraries are on different paths (e.g., Plex is in Docker), you can create a file to remap file paths:

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

---

## Usage

Run the script via Poetry:

```bash
poetry run rekordbox2plex
```

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
