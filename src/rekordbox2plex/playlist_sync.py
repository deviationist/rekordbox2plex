from .rekordbox.playlist_resolver import get_all_playlists as get_all_playlists_from_rekordbox, get_playlist_tracks
from .plex.playlist_resolver import create_playlist as create_playlist_in_plex, get_all_playlists as get_all_playlists_from_plex
from .TrackMapper import TrackMapper
import pprint

trackMapper = TrackMapper()

def playlist_sync():
    trackMapper.ensure_mappings() # Ensure we have all tracks
    rb_playlists = get_all_playlists_from_rekordbox()
    plex_playlists = get_all_playlists_from_plex()
    for rb_playlist in rb_playlists:
        plex_playlist = next((pl for pl in plex_playlists if pl.title == rb_playlist["FlattenedName"]), None)

        if plex_playlist:
            print(f"Update playlist: {rb_playlist["FlattenedName"]}")
            sync_playlist_tracks(rb_playlist, plex_playlist) # Make sure tracks are up to date
        else:
            # TODO: Resolve all the track in the playlist, match them with the tracks in Plex, resolve the corresponding Plex tracks and add them to playlist
            # TODO: Handle removal of tracks from playlists
            # TODO: Handle deletion of playlists
            #create_playlist(playlist["FlattenedName"])
            print(f"Create playlist: {rb_playlist["FlattenedName"]}")
            create_playlist(rb_playlist)
        break

            #print(dict(playlist_items[0]))
    #delete_orphaned_playlists(rekordbox_playlists, plex_playlists)


def resolve_plex_track_from_rb_playlist(rb_playlist):
    plex_items = []
    rb_playlist_items = get_playlist_tracks(rb_playlist["PlaylistID"])
    print(f"RB item count: {len(rb_playlist_items)}")
    for rb_playlist_item in rb_playlist_items:
        pprint.pprint(dict(rb_playlist_item))
        plex_item = trackMapper.resolve_plex_track_by_rb(rb_playlist_item["ID"])
        if plex_item:
            plex_items.append(plex_item["track_object"])
        else:
            print(f"No track hit: {rb_playlist_item["Title"]}")
    return plex_items

def create_playlist(rb_playlist):
    plex_items = resolve_plex_track_from_rb_playlist(rb_playlist)
    create_playlist_in_plex(rb_playlist["FlattenedName"], plex_items)

def sync_playlist_tracks(rb_playlist, plex_playlist):
    pprint.pprint(rb_playlist);
    plex_playlist_items_from_rb = resolve_plex_track_from_rb_playlist(rb_playlist)
    plex_playlist_existing_items = plex_playlist.items()

    # Add items
    items_to_add = []
    for plex_item in plex_playlist_items_from_rb:
        print(f"Check to add: {plex_item.title}")
        in_playlist = next((pl for pl in plex_playlist_existing_items if pl.ratingKey == plex_item.ratingKey), None)
        if not in_playlist:
            items_to_add.append(plex_item)
    if len(items_to_add) > 0:
        print(f"Items to add: {len(items_to_add)}")
        plex_playlist.addItems(items_to_add)

    # Remove items
    items_to_remove = []
    for plex_item in plex_playlist_existing_items:
        print(f"Check to remove: {plex_item.title}")
        in_playlist = next((pl for pl in plex_playlist_items_from_rb if pl.ratingKey == plex_item.ratingKey), None)
        if not in_playlist:
            items_to_remove.append(plex_item)
    if len(items_to_remove) > 0:
        print(f"Items to remove: {len(items_to_remove)}")
        plex_playlist.removeItems(items_to_remove)

def delete_orphaned_playlists(rb_playlists, plex_playlists):
    for playlist in plex_playlists:
        playlist_exists_in_rb = next((pl for pl in rb_playlists if pl["FlattenedName"] == playlist.title), None)
        if not playlist_exists_in_rb:
            #playlist.delete()
            print(f"Delete playlist: {playlist.title}")

