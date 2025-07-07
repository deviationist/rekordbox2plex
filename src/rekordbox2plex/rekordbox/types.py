#from collections import namedtuple
from typing import NamedTuple, List

class Track(NamedTuple):
    id: int
    title: str
    release_year: int

class Artist(NamedTuple):
    id: int
    name: str

class Album(NamedTuple):
    id: int
    name: str

class ResolvedTrack(NamedTuple):
  track: Track
  artist: Artist
  album: Album
  album_artist: Artist

class PlaylistTrack(NamedTuple):
    id: int
    title: str

class Playlist(NamedTuple):
    id: int
    name: str

class TrackWithArtwork(Track):
      artwork_id: int
      artwork_path: str
      artwork_local_path: str

class ResolvedAlbumWithTracks(NamedTuple):
    tracks: List[TrackWithArtwork]
    artist: Artist
    album: Album
