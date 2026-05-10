from ..RekordboxDB import RekordboxDB
from ...utils.progress_bar import Progress, TaskID, NullProgress
from ...utils.logger import logger
from ...utils.folder_mappings import get_folder_mappings
from ...plex.data_types import PlexTrackWrapper
from ..data_types import TrackWithArtwork, Track, Artist, Album, ResolvedTrack
from typing import Literal, List, Tuple


def convert_path_to_rekordbox(plex_path: str) -> str:
    folder_mappings = get_folder_mappings()
    if not folder_mappings:
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
) -> Tuple[str, List[str]]:
    if len(paths_to_ignore) == 0:
        return "", []
    clauses = " ".join(f"AND {column_name} NOT LIKE ?" for _ in paths_to_ignore)
    params = [f"%{p}%" for p in paths_to_ignore]
    return clauses, params


def get_all_tracks(
    paths_to_ignore: List[str] = [],
) -> List[Track] | Literal[False]:
    """Get all tracks from Rekordbox database."""
    db = RekordboxDB()
    cursor = db.cursor

    paths_to_ignore_str, paths_to_ignore_params = paths_to_ignore_query_part(
        paths_to_ignore
    )
    try:
        query = f"""
        SELECT
            ID, Title, Label, ReleaseYear, ReleaseDate, StockDate, FolderPath
        FROM
            djmdContent
        WHERE
            rb_local_deleted = 0
            AND rb_data_status = 0
            AND FolderPath LIKE '/%'
            AND rb_file_id != 0
            {paths_to_ignore_str}
"""
        cursor.execute(query, paths_to_ignore_params)
        rows = cursor.fetchall()

        if rows:
            tracks = []
            for row in rows:
                row_dict = dict(row)
                release_year = row_dict.get("ReleaseYear")
                tracks.append(
                    Track(
                        id=int(row_dict["ID"]),
                        title=row_dict["Title"],
                        label=row_dict.get("Label"),
                        release_year=int(release_year) if release_year else None,
                        release_date=row_dict["ReleaseDate"],
                        added_at=row_dict["StockDate"],
                        folder_path=row_dict["FolderPath"],
                    )
                )
            logger.debug(f"[green]Found {len(tracks)} tracks in Rekordbox database.")
            return tracks
        else:
            logger.debug("[yellow]Warning: No tracks found in Rekordbox database.")
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info(f"[red]Database error: {e}")
        return False


def handle_track_row(row: dict) -> ResolvedTrack:

    # Convert row to dict for easier handling
    row_dict = dict(row)

    # Extract track data (all columns that don't have prefixes)
    artist = None
    album = None
    album_artist = None

    # Build track data
    release_year = row_dict.get("track_ReleaseYear")
    track = TrackWithArtwork(
        id=int(row_dict["track_ID"]),
        title=row_dict["track_Title"],
        label=row_dict.get("track_Label"),
        release_year=int(release_year) if release_year else None,
        release_date=row_dict["track_ReleaseDate"],
        added_at=row_dict.get("track_AddedAt"),
        folder_path=row_dict.get("track_FolderPath"),
        artwork_id=row_dict.get("artwork_ID"),
        artwork_path=row_dict.get("artwork_Path"),
        artwork_local_path=row_dict.get("artwork_rb_local_path"),
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
            description=f'[yellow]Resolving track "{plex_track.track_title}" in Rekordbox database...',
        )

    try:
        # Single query with JOINs to get all related data at once
        query = """
        SELECT
            c.ID AS track_ID, c.Title AS track_Title, c.ReleaseYear AS track_ReleaseYear, c.ReleaseDate AS track_ReleaseDate, c.FolderPath AS track_FolderPath, c.StockDate AS track_AddedAt,
            a.ID AS artist_ID, a.Name AS artist_Name,
            al.ID AS album_ID, al.Name AS album_Name,
            aa.ID AS albumArtist_ID, aa.Name AS albumArtist_Name,
            cf.ID AS artwork_ID, cf.Path AS artwork_Path, cf.rb_local_path AS artwork_rb_local_path,
            l.Name AS track_Label
        FROM
            djmdContent AS c
        LEFT JOIN
            djmdArtist AS a
            ON c.ArtistID = a.ID
        LEFT JOIN
            djmdAlbum AS al
            ON c.AlbumID = al.ID
        LEFT JOIN
            djmdArtist AS aa
            ON al.albumArtistID = aa.ID
        LEFT JOIN
            contentFile AS cf
            ON c.ImagePath = cf.Path
        LEFT JOIN
            djmdLabel AS l
            ON c.LabelID = l.ID
        WHERE
            c.rb_local_deleted = 0
            AND c.rb_data_status = 0
            AND c.folderPath = ?
            AND c.rb_file_id != 0
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
            logger.debug(f'[yellow]Warning: No file found for "{rekordboxPath}"')
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info(f"[red]Database error: {e}")
        return False
