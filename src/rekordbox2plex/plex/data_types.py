from typing import NamedTuple, Any, Dict, TypeAlias, ValuesView
from plexapi.audio import Track, Album, Artist
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


PlexItem: TypeAlias = Track | Album | Artist | Playlist

CacheItem: TypeAlias = PlexItem
CacheItems: TypeAlias = ValuesView[CacheItem]
Cache: TypeAlias = Dict[str, CacheItem]

PlexArtist = Artist
PlexArtists = MediaContainer[PlexArtist]

PlexAlbum = Album
PlexAlbums = MediaContainer[PlexAlbum]

PlexTrack = Track
PlexTracks = MediaContainer[PlexTrack]

PlexPlaylist = Playlist
PlexPlaylists = MediaContainer[PlexPlaylist]

__all__ = [
    "Track",
    "Album",
    "Artist",
    "Cache",
    "CacheItem",
    "CacheItems",
    "Playlist",
    "MediaContainer",
    "PlexTrackWrapper",
    "PlexItem",
    "PlexArtist",
    "PlexArtists",
    "PlexAlbum",
    "PlexAlbums",
    "PlexTrack",
    "PlexTracks",
    "PlexPlaylist",
    "PlexPlaylists",
]
