from rekordbox2plex.mappers.TrackIdMapper import TrackIdMapper
from rekordbox2plex.plex.data_types import PlexTrackWrapper
from rekordbox2plex.rekordbox.data_types import ResolvedTrack
from faker import Faker
from .factories.plex import generate_plex_track
from .factories.rekordbox import generate_rb_item


def test_track_mapper(faker: Faker):
    mapper = TrackIdMapper()

    track_title = faker.words(5)
    plex_track_id = 123
    plex_track = generate_plex_track(plex_track_id, track_title)
    rb_track_id = 321
    rb_item = generate_rb_item(rb_track_id, track_title)

    mapper.map(plex_track, rb_item)

    assert plex_track.id == plex_track_id
    assert rb_item.track.id == rb_track_id

    resolved_plex_track = mapper.resolve_plex_track_by_rb(rb_track_id)
    resolved_rb_track = mapper.resolve_rb_track_by_plex(plex_track_id)

    assert isinstance(resolved_plex_track, PlexTrackWrapper)
    assert isinstance(resolved_rb_track, ResolvedTrack)

    assert resolved_plex_track.id == plex_track_id
    assert resolved_rb_track.track.id == rb_track_id

    assert resolved_plex_track.title == track_title
    assert resolved_rb_track.track.title == track_title
