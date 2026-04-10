from .library import get_music_library, plexapi_client
from ..data_types import PlexTrack, PlexTracks
import json
from ...utils.logger import logger
from ...config import plex_track_lookup_override, get_folder_mappings_path
from plexapi.utils import openOrRead
from plexapi.audio import Track


def get_track(track_id: int) -> PlexTrack:
    music_library, _ = get_music_library()
    return music_library.fetchItem(track_id)


def get_all_tracks() -> PlexTracks:
    music_library, _ = get_music_library()
    title_search = plex_track_lookup_override()
    return music_library.searchTracks(title=title_search)


def update_track_poster(plex_item: Track, poster_path: str) -> bool:
    server = plexapi_client()
    try:
        key = f"/library/metadata/{plex_item.ratingKey}/posters"
        data = openOrRead(poster_path)
        server.query(key, method=server._session.post, data=data)
        return True
    except Exception as e:
        logger.error(f"Failed to update poster for track {plex_item.ratingKey}: {e}")
        return False


def get_track_thumb_file(track: Track) -> bytes:
    server = plexapi_client()
    token: str = server._token

    thumb_url: str = f"{server.url(track.thumb)}?X-Plex-Token={token}"

    response = server._session.get(thumb_url)
    response.raise_for_status()

    return response.content


def convert_path_to_plex(rekordbox_path: str) -> str:
    mappings_override = get_folder_mappings_path()
    mappings_path = mappings_override or "folderMappings.json"
    try:
        with open(mappings_path, "r") as f:
            folder_mappings = json.load(f)
    except FileNotFoundError:
        if mappings_override:
            raise FileNotFoundError(
                f"Folder mappings file not found: {mappings_override}"
            )
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
