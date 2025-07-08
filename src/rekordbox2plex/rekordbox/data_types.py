from typing import NamedTuple, List


class Track(NamedTuple):
    id: int
    title: str
    release_year: int


class Artwork(NamedTuple):
    id: int | None
    path: str | None
    local_path: str | None


class TrackWithArtwork(NamedTuple):
    id: int
    title: str
    release_year: int
    artwork_id: int | None
    artwork_path: str | None
    artwork_local_path: str | None


class Artist(NamedTuple):
    id: int
    name: str


class Album(NamedTuple):
    id: int
    name: str


class ResolvedTrack(NamedTuple):
    track: Track
    artist: Artist | None
    album: Album | None
    album_artist: Artist | None


class PlaylistTrack(NamedTuple):
    id: int
    title: str


class Playlist(NamedTuple):
    id: int
    name: str


class ResolvedAlbumWithTracks(NamedTuple):
    tracks: List[TrackWithArtwork]
    artist: Artist | None
    album: Album | None
