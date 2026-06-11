from ..RekordboxDB import RekordboxDB
from ...utils.progress_bar import Progress, TaskID, NullProgress
from ...utils.logger import logger
from ...utils.folder_mappings import get_folder_mappings
from ...utils.media_paths import PathMap, resolve_container_path
from ...plex.data_types import PlexTrackWrapper


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


def _query_rb_id(rekordbox_path: str) -> int | None:
    """Look up a single Rekordbox track ID by its stored FolderPath."""
    cursor = RekordboxDB().cursor
    cursor.execute(
        """
        SELECT ID FROM djmdContent
        WHERE FolderPath = ?
          AND rb_local_deleted = 0
          AND rb_data_status = 0
          AND rb_file_id != 0
        """,
        (rekordbox_path,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return int(dict(row)["ID"])


def is_ignored_rb_path(rb_path: str | None, ignore_fragments: list[str]) -> bool:
    """True if a Rekordbox FolderPath contains one of the ignored fragments.

    Used by the `parity` check to honour ``REKORDBOX_FOLDER_PATHS_TO_IGNORE``.
    Substring match against the Rekordbox FolderPath (same convention as
    ``REKORDBOX_PLAYLISTS_TO_IGNORE``), so a value like ``Memes`` matches
    ``/Volumes/REKORDBOX/on-hold/Memes/x.mp3``. Empty inputs never match.
    """
    if not rb_path or not ignore_fragments:
        return False
    return any(fragment in rb_path for fragment in ignore_fragments)


def resolve_track_id_by_rb_path(rekordbox_path: str) -> int | None:
    """Resolve a Rekordbox track ID from an already-mapped Rekordbox FolderPath."""
    logger.debug(
        f'Attempting to resolve file in Rekordbox using path "{rekordbox_path}"'
    )
    try:
        return _query_rb_id(rekordbox_path)
    except Exception as e:
        logger.info(f"[red]Database error: {e}")
        return None


def resolve_track_id_by_plex_path(plex_file_path: str) -> int | None:
    """Resolve a Rekordbox track ID from a Plex file path (path-mapped).

    Returns None if the file isn't present in the Rekordbox database. Used by
    the `dates` command, which enumerates Plex from its DB rather than the API.
    """
    return resolve_track_id_by_rb_path(convert_path_to_rekordbox(plex_file_path))


def resolve_rb_id_by_host_path(
    host_path: str, media_map: PathMap | None = None
) -> int | None:
    """Resolve a Rekordbox track ID from a HOST filesystem path (as walked by the
    ``lossless-tags``/``rb-dates`` filesystem pass).

    Bridges the path representations: host path → Plex *container* path (reverse
    ``PLEX_MEDIA_PATH_MAP``) → Rekordbox ``FolderPath`` (folderMappings.json) →
    ``djmdContent.ID``. If no media map applies (e.g. run on the Mac where the host
    path already matches what Rekordbox stored), the path passes straight through
    ``convert_path_to_rekordbox``."""
    plex_path = host_path
    if media_map:
        container = resolve_container_path(host_path, media_map)
        if container is not None:
            plex_path = container
    return resolve_track_id_by_plex_path(plex_path)


def resolve_track_id(
    plex_track: PlexTrackWrapper,
    progress: Progress | NullProgress | None = None,
    task: TaskID | None = None,
) -> int | None:
    """Resolve the Rekordbox track ID for a Plex track by file path.

    Returns None if the file isn't present in the Rekordbox database.
    """
    rekordbox_path = convert_path_to_rekordbox(plex_track.file_path)
    logger.debug(
        f'Attempting to resolve file in Rekordbox using path "{rekordbox_path}"'
    )

    if progress and task:
        progress.update(
            task,
            description=f'[yellow]Resolving track "{plex_track.track_title}" in Rekordbox database...',
        )

    try:
        rb_id = _query_rb_id(rekordbox_path)
        if rb_id is None:
            logger.debug(f'[yellow]Warning: No file found for "{rekordbox_path}"')
        return rb_id
    except Exception as e:
        logger.info(f"[red]Database error: {e}")
        return None
