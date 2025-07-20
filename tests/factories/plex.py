from rekordbox2plex.plex.data_types import PlexTrackWrapper


def generate_plex_track(id: int, track_title: str) -> PlexTrackWrapper:
    return PlexTrackWrapper(
        id=id,
        track_title=track_title,
        track_artist_name="Test Artist",
        album_id=420,
        album_name="Test Album",
        album_artist_id=69,
        album_artist_name="Test Album Artist",
        track_object={},
        file_path="/bogus/path",
        added_at="",
        has_artwork=False,
    )
