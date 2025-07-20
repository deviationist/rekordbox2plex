from .library import get_music_library, plexapi_client
from ..data_types import PlexTrack, PlexTracks
import json
from ...utils.logger import logger
from plexapi.utils import openOrRead


def get_track(track_id: int) -> PlexTrack:
    music_library, _ = get_music_library()
    return music_library.fetchItem(track_id)


def get_all_tracks() -> PlexTracks:
    music_library, _ = get_music_library()
    return music_library.searchTracks()


def update_track_poster(track_id: int, poster_path: str) -> bool:
    server = plexapi_client()
    library, _ = get_music_library()
    plex_item = library.fetchItem(track_id)
    try:
        key = f"/library/metadata/{plex_item.ratingKey}/posters"
        data = openOrRead(poster_path)
        server.query(key, method=server._session.post, data=data)
        return True
    except Exception as e:
        logger.error(f"Failed to update poster for track {track_id}: {e}")
        return False


def convert_path_to_plex(rekordbox_path: str) -> str:
    try:
        with open("folderMappings.json", "r") as f:
            folder_mappings = json.load(f)
    except FileNotFoundError:
        logger.info("[red]Warning: folderMappings.json not found, using original path")
        return rekordbox_path

    for plex_folder, rekordbox_folder in folder_mappings.items():
        if rekordbox_path.startswith(rekordbox_folder):
            return plex_folder + rekordbox_path[len(rekordbox_folder) :]

    # No mapping found, just return the original path
    logger.info(
        f'[yellow]Warning: No mapping found for "{rekordbox_path}", using original path'
    )
    return rekordbox_path
