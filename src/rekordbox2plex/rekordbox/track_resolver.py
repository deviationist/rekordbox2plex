from .RekordboxDB import RekordboxDB
from ..utils.logger import logger
import json

def convert_path_to_rekordbox(plex_path: str) -> str:
    try:
        with open("folderMappings.json", "r") as f:
            folder_mappings = json.load(f)
    except FileNotFoundError:
        logger.info('[red]Warning: folderMappings.json not found, using original path')
        return plex_path

    for plex_folder, rekordbox_folder in folder_mappings.items():
        if plex_path.startswith(plex_folder):
            return rekordbox_folder + plex_path[len(plex_folder):]

    # No mapping found, just return the original path
    logger.info(f'[yellow]Warning: No mapping found for "{plex_path}", using original path')
    return plex_path

def resolve_track(plex_track: str, progress = None, task = None) -> tuple[dict, dict | None, dict | None, dict | None, dict | None] | bool:
    db = RekordboxDB()
    cursor = db.cursor

    rekordboxPath = convert_path_to_rekordbox(plex_track["file_path"])
    if not rekordboxPath:
        return False

    if progress and task: progress.update(task, description=f'[yellow]Resolving track "{plex_track["title"]}" in Rekordbox database...')

    try:
        # Single query with JOINs to get all related data at once
        query = """
        SELECT
            c.ID, c.ArtistID, c.AlbumID, c.Title, c.DateCreated,
            a.ID as artist_ID, a.Name as artist_Name,
            al.ID as album_ID, al.Name as album_Name,
            aa.ID as albumArtist_ID, aa.Name as albumArtist_Name,
            cf.Path as artwork_Path, cf.rb_local_path as artwork_rb_local_path
        FROM djmdContent c
        LEFT JOIN djmdArtist a ON c.ArtistID = a.ID
        LEFT JOIN djmdAlbum al ON c.AlbumID = al.ID
        LEFT JOIN djmdArtist aa ON al.albumArtistID = aa.ID
        LEFT JOIN contentFile cf ON c.ImagePath = cf.Path
        WHERE c.rb_local_deleted = 0 AND c.folderPath = ?
        """

        cursor.execute(query, (rekordboxPath,))
        row = cursor.fetchone()

        if row:
            # Convert row to dict for easier handling
            row_dict = dict(row)

            # Extract track data (all columns that don't have prefixes)
            track = {}
            artist = None
            album = None
            albumArtist = None

            # Extract track data
            track = {
                'ID': row_dict['ID'],
                'Title': row_dict['Title'],
                'DateCreated': row_dict['DateCreated'],
            }

            # Build artist dictionary if artist exists
            if row_dict.get('artist_ID'):
                artist = {
                    #'ID': row_dict['artist_ID'],
                    'Name': row_dict['artist_Name']
                }

            # Build album dictionary if album exists
            if row_dict.get('album_ID'):
                album = {
                    #'ID': row_dict['album_ID'],
                    'Name': row_dict['album_Name']
                }

            # Build album artist dictionary if album artist exists
            if row_dict.get('albumArtist_ID'):
                albumArtist = {
                    #'ID': row_dict['albumArtist_ID'],
                    'Name': row_dict['albumArtist_Name']
                }

            # Build artwork dictionary if artwork path exists
            artwork = None
            #if row_dict.get('artwork_path'):
            #    artwork = {
            #        'rb_local_path': row_dict['artwork_path']
            #    }

            if progress and task: progress.update(task, description=f'[yellow]Resolved track "{plex_track["title"]}" in Rekordbox database...')

            return track, artist, artwork, album, albumArtist
        else:
            logger.info(f"[red]Warning: No file found for {rekordboxPath}")
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info("[red]Database error:", e)
        return False
