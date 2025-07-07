from typing import NamedTuple, Any
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

PlexItem = Track | Album | Artist | Playlist

PlexArtist = Artist | None
PlexArtists = MediaContainer[PlexArtist]

PlexAlbum = Album | None
PlexAlbums = MediaContainer[PlexAlbum]

PlexTrack = Track | None
PlexTracks = MediaContainer[PlexTrack]

PlexPlaylist = Playlist | None
PlexPlaylists = MediaContainer[PlexPlaylist]
