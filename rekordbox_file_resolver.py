from pysqlcipher3 import dbapi2 as sqlite
import os, json

DB_PATH = os.getenv("REKORDBOX_MASTERDB_PATH")
DB_PASSWORD = os.getenv("REKORDBOX_MASTERDB_PASSWORD")

def convert_path_to_rekordbox(plexPath: str) -> str:
    with open("folderMappings.json", "r") as f:
        folder_mappings = json.load(f)
    for plex_folder, rekordbox_folder in folder_mappings.items():
        if plexPath.startswith(plex_folder):
            return rekordbox_folder + plexPath[len(plex_folder):]
    print(f"Warning: No mapping found for {plexPath}") 

def connect_to_db():
    conn = sqlite.connect(DB_PATH)
    conn.row_factory = sqlite.Row
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA key='{DB_PASSWORD}';")
    return conn, cursor

def resolve_track(plexPath: str) -> tuple | bool:
    conn, cursor = connect_to_db()
    track = None
    artist = None
    album = None
    albumArtist = None

    rekordboxPath = convert_path_to_rekordbox(plexPath)
    if not rekordboxPath:
        return False

    try:
        cursor.execute("SELECT * FROM djmdContent WHERE rb_local_deleted = 0 AND folderPath =?", (rekordboxPath,))
        row = cursor.fetchone()
        if row:
            track = row
            cursor.execute("SELECT * FROM djmdArtist WHERE ID = ?", (track['artistID'],))
            artist_row = cursor.fetchone()
            if artist_row:
                artist = artist_row
            cursor.execute("SELECT * FROM djmdAlbum WHERE ID = ?", (track['albumID'],))
            album_row = cursor.fetchone()
            if album_row:
                album = album_row
                cursor.execute("SELECT * FROM djmdArtist WHERE ID = ?", (album['albumArtistID'],))
                albumArtist_row = cursor.fetchone()
                if albumArtist_row:
                    albumArtist = albumArtist_row

            

    except sqlite.Error as e:
        print("SQLite error:", e)

    finally:
        conn.close()

    if track:
        return dict(row), dict(artist) if artist else None, dict(album) if album else None, dict(albumArtist) if albumArtist else None
    else:
        print(f"Warning: No file found for {rekordboxPath}")
        return False