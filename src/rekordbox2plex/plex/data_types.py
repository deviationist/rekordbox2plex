from typing import NamedTuple, Any, Dict, TypeAlias, ValuesView
from plexapi.audio import Track, Album, Artist
from plexapi.playlist import Playlist
from plexapi.base import MediaContainer


class PlexTrackWrapper(NamedTuple):
    id: int
    file_path: str
    title: str
    added_at: Any
    track_artist: int
    album_id: int
    album_artist_id: int
    track_object: Track


PlexItem: TypeAlias = Track | Album | Artist | Playlist

CacheItem: TypeAlias = PlexItem
CacheItems: TypeAlias = ValuesView[CacheItem]
Cache: TypeAlias = Dict[str, CacheItem]

PlexArtist = Artist | None
PlexArtists = MediaContainer[PlexArtist]

PlexAlbum = Album | None
PlexAlbums = MediaContainer[PlexAlbum]

PlexTrack = Track | None
PlexTracks = MediaContainer[PlexTrack]

PlexPlaylist = Playlist | None
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
