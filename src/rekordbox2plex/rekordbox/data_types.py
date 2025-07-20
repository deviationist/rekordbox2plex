from typing import NamedTuple, List


class Track(NamedTuple):
    id: int
    title: str
    label: str | None
    release_year: int | None
    folder_path: str | None


class Artwork(NamedTuple):
    id: int | None
    path: str | None
    local_path: str | None


class TrackWithArtwork(NamedTuple):
    id: int
    title: str
    label: str | None
    release_year: int
    folder_path: str | None
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
    track: TrackWithArtwork
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
    album_artist: Artist | None
