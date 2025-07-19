from ..RekordboxDB import RekordboxDB
from ...utils.progress_bar import Progress, TaskID, NullProgress
from ...utils.logger import logger
from ...plex.data_types import PlexTrackWrapper
import json
from ..data_types import Track, Artist, Album, ResolvedTrack
from typing import Literal, List


def convert_path_to_rekordbox(plex_path: str) -> str:
    try:
        with open("folderMappings.json", "r") as f:
            folder_mappings = json.load(f)
    except FileNotFoundError:
        logger.info("[red]Warning: folderMappings.json not found, using original path")
        return plex_path

    for plex_folder, rekordbox_folder in folder_mappings.items():
        if plex_path.startswith(plex_folder):
            return rekordbox_folder + plex_path[len(plex_folder) :]

    # No mapping found, just return the original path
    logger.info(
        f'[yellow]Warning: No mapping found for "{plex_path}", using original path'
    )
    return plex_path


def paths_to_ignore_query_part(
    paths_to_ignore: List[str], column_name: str = "FolderPath"
) -> str:
    if len(paths_to_ignore) == 0:
        return ""
    query = ""
    for path_to_ignore in paths_to_ignore:
        query += f"AND {column_name} NOT LIKE '%{path_to_ignore}%'"
    return query


def get_all_tracks(
    paths_to_ignore: List[str] = [],
) -> List[Track] | Literal[False]:
    """Get all tracks from Rekordbox database."""
    db = RekordboxDB()
    cursor = db.cursor

    paths_to_ignore_str = paths_to_ignore_query_part(paths_to_ignore)
    try:
        query = f"""
        SELECT
            *
        FROM
            djmdContent
        WHERE
            rb_local_deleted = 0
            AND rb_data_status = 0
            AND FolderPath LIKE '/%'
            {paths_to_ignore_str}
"""
        cursor.execute(query)
        rows = cursor.fetchall()

        if rows:
            tracks = []
            for row in rows:
                row_dict = dict(row)
                tracks.append(
                    Track(
                        id=int(row_dict["ID"]),
                        title=row_dict["Title"],
                        release_year=int(row_dict["ReleaseYear"]),
                        folder_path=row_dict["FolderPath"],
                    )
                )
            logger.debug(f"[green]Found {len(tracks)} tracks in Rekordbox database.")
            return tracks
        else:
            logger.debug("[yellow]Warning: No tracks found in Rekordbox database.")
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info("[red]Database error:", e)
        return False


def handle_track_row(row: dict) -> ResolvedTrack:

    # Convert row to dict for easier handling
    row_dict = dict(row)

    # Extract track data (all columns that don't have prefixes)
    artist = None
    album = None
    album_artist = None

    # Build track data
    track = Track(
        id=int(row_dict["track_ID"]),
        title=row_dict["track_Title"],
        release_year=int(row_dict["track_ReleaseYear"]),
    )

    # Build artist dictionary if artist exists
    if row_dict.get("artist_ID"):
        artist = Artist(id=int(row_dict["artist_ID"]), name=row_dict["artist_Name"])

    # Build album dictionary if album exists
    if row_dict.get("album_ID"):
        album = Album(id=int(row_dict["album_ID"]), name=row_dict["album_Name"])

    # Build album artist dictionary if album artist exists
    if row_dict.get("albumArtist_ID"):
        album_artist = Artist(
            id=int(row_dict["albumArtist_ID"]),
            name=row_dict["albumArtist_Name"],
        )

    return ResolvedTrack(track, artist, album, album_artist)


def resolve_track(
    plex_track: PlexTrackWrapper,
    progress: Progress | NullProgress | None = None,
    task: TaskID | None = None,
) -> ResolvedTrack | Literal[False]:
    db = RekordboxDB()
    cursor = db.cursor

    rekordboxPath = convert_path_to_rekordbox(plex_track.file_path)
    logger.debug(f'Attempting to resolve file in Rekordbox using path "{rekordboxPath}')

    if progress and task:
        progress.update(
            task,
            description=f'[yellow]Resolving track "{plex_track.title}" in Rekordbox database...',
        )

    try:
        # Single query with JOINs to get all related data at once
        query = """
        SELECT
            c.ID AS track_ID, c.Title AS track_Title, c.ReleaseYear AS track_ReleaseYear,
            a.ID AS artist_ID, a.Name AS artist_Name,
            al.ID AS album_ID, al.Name AS album_Name,
            aa.ID AS albumArtist_ID, aa.Name AS albumArtist_Name
        FROM djmdContent c
        LEFT JOIN djmdArtist a ON c.ArtistID = a.ID
        LEFT JOIN djmdAlbum al ON c.AlbumID = al.ID
        LEFT JOIN djmdArtist aa ON al.albumArtistID = aa.ID
        WHERE c.rb_local_deleted = 0 AND c.folderPath = ?
        """

        cursor.execute(query, (rekordboxPath,))
        row = cursor.fetchone()

        if row:
            resolved_track = handle_track_row(row)
            logger.debug(
                f"[green]Resolved track {rekordboxPath} in Rekordbox database."
            )
            return resolved_track

        else:
            logger.debug(f"[yellow]Warning: No file found for {rekordboxPath}")
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info("[red]Database error:", e)
        return False
