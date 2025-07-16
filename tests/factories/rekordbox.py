from rekordbox2plex.rekordbox.data_types import ResolvedTrack, Track, Artist, Album

def generate_rb_item(id: int, track_title: str) -> ResolvedTrack:
    return ResolvedTrack(
        track=Track(
            id=id,
            title=track_title,
            release_year=1969
        ),
        artist=Artist(
            id=111,
            name="Plex-o-rama"
        ),
        album=Album(
            id=222,
            name="Plex-o-rama-lama"
        ),
        album_artist=Artist(
            id=333,
            name="Plex-o-rama-lama-rama"
        )
    )
