from rekordbox2plex.plex.data_types import PlexTrackWrapper

def generate_plex_track(id: int, track_title: str) -> PlexTrackWrapper:
    return PlexTrackWrapper(
        id=id,
        file_path="/bogus/path",
        title=track_title,
        added_at="",
        track_artist="Plex-o-rama",
        album_id=420,
        album_artist_id=69,
        track_object={}
    )
