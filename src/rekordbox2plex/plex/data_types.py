from typing import NamedTuple, Any, Dict, TypeAlias, ValuesView
from plexapi.audio import Track
from plexapi.playlist import Playlist
from plexapi.base import MediaContainer


class PlexTrackWrapper(NamedTuple):
    id: int
    track_title: str
    track_artist_name: str
    album_id: int
    album_name: str
    album_artist_id: int
    album_artist_name: str
    track_object: Track
    file_path: str
    added_at: Any
    has_artwork: bool


PlexItem: TypeAlias = Track | Playlist

CacheItem: TypeAlias = PlexItem
CacheItems: TypeAlias = ValuesView[CacheItem]
Cache: TypeAlias = Dict[str, CacheItem]

PlexTrack = Track
PlexTracks = MediaContainer[PlexTrack]

PlexPlaylist = Playlist
PlexPlaylists = MediaContainer[PlexPlaylist]

__all__ = [
    "Track",
    "Cache",
    "CacheItem",
    "CacheItems",
    "Playlist",
    "MediaContainer",
    "PlexTrackWrapper",
    "PlexItem",
    "PlexTrack",
    "PlexTracks",
    "PlexPlaylist",
    "PlexPlaylists",
]
