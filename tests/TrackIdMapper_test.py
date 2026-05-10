import dotenv
from rekordbox2plex.mappers.TrackIdMapper import TrackIdMapper
from rekordbox2plex.plex.data_types import PlexTrackWrapper
from faker import Faker
from factories.plex import generate_plex_track

dotenv.load_dotenv()


def test_track_mapper(faker: Faker):
    mapper = TrackIdMapper()
    # Bypass the lazy Plex-walk inside resolve_plex_track_by_rb; we're testing
    # the in-memory lookup, not the singleton's bootstrap behaviour.
    mapper._all_mapped = True

    track_title = faker.words(5)
    plex_track_id = 123
    rb_track_id = 321
    plex_track = generate_plex_track(plex_track_id, track_title)

    mapper.map(plex_track, rb_track_id)

    resolved = mapper.resolve_plex_track_by_rb(rb_track_id)
    assert isinstance(resolved, PlexTrackWrapper)
    assert resolved.id == plex_track_id
    assert resolved.track_title == track_title

    # Unknown rb ID returns False rather than raising
    assert mapper.resolve_plex_track_by_rb(999_999) is False
