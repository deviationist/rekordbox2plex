from typing import NamedTuple, Any

class PlexTrack(NamedTuple):
    id: int
    file_path: str
    title: str
    added_at: Any
    track_artist: int
    album_id: int
    album_artist_id: int
    track_object: Any

#from collections import namedtuple

#PlexTrack = namedtuple("PlexTrack", [
#  "id", "file_path", "title", "added_at", "track_artist", "album_id", "album_artist_id", "track_object"
#])
