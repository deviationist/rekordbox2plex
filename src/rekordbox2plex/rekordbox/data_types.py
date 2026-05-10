from typing import NamedTuple


class PlaylistTrack(NamedTuple):
    id: int
    title: str


class Playlist(NamedTuple):
    id: int
    name: str
