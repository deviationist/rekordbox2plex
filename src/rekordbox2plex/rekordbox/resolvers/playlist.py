from ..RekordboxDB import RekordboxDB
from typing import List, Literal
from ..data_types import Playlist, PlaylistTrack
from ...plex.resolvers.library import plex_playlist_flattening_delimiter


def get_playlist_tracks(playlist_id: int) -> List[PlaylistTrack] | Literal[False]:
    db = RekordboxDB()
    cursor = db.cursor

    query = """
    SELECT
        c.ID AS track_ID,
        c.Title AS track_Title
    FROM djmdSongPlaylist AS pl
    INNER JOIN
        djmdContent AS c
  		ON c.ID = pl.ContentID
    WHERE
        pl.PlaylistID = ?
        AND pl.rb_data_status = 0
        AND c.rb_data_status = 0
"""
    cursor.execute(query, (playlist_id,))
    rows = cursor.fetchall()
    if rows:
        tracks = []

        for row in rows:
            # Convert row to dict for easier handling
            row_dict = dict(row)
            tracks.append(
                PlaylistTrack(id=row_dict["track_ID"], title=row_dict["track_Title"])
            )
        return tracks
    return False


def resolve_playlist_name(playlist: dict, playlist_lookup: dict) -> str:
    """Resolve the full name of a playlist by traversing its parent hierarchy."""
    name_parts = [playlist["Name"]]
    parent_id = playlist.get("ParentID")
    while parent_id and parent_id != "root":
        parent_item = playlist_lookup.get(int(parent_id))
        if parent_item:
            parent_name = parent_item.get("Name")
            if parent_name:
                name_parts.append(parent_name)
                parent_id = playlist_lookup.get(int(parent_id), {}).get("ParentID")
            else:
                break
        else:
            break
    return plex_playlist_flattening_delimiter().join(reversed(name_parts))


def get_all_playlists() -> List[Playlist] | Literal[False]:
    db = RekordboxDB()
    cursor = db.cursor

    query = """
    SELECT
        p.ID AS PlaylistID,
        p.Name AS Name,
        ParentID,
        COUNT(sp.ID) AS TrackCount
    FROM
        djmdPlaylist AS p
    LEFT JOIN
        djmdSongPlaylist AS sp
        ON sp.PlaylistID = p.ID
        AND sp.rb_data_status = 0
        AND sp.rb_local_deleted = 0
    WHERE
        p.rb_data_status = 0
        AND p.rb_local_deleted = 0
    GROUP BY
        p.ID
    ORDER BY
        Name
"""
    cursor.execute(query)
    rows = cursor.fetchall()
    if rows:
        playlists = []
        playlist_lookup = {}

        for row in rows:
            # Convert row to dict for easier handling
            row_dict = dict(row)
            playlist_lookup[int(row_dict["PlaylistID"])] = row_dict

        for row in rows:
            # Convert row to dict for easier handling
            row_dict = dict(row)

            flattened_name = resolve_playlist_name(row_dict, playlist_lookup)

            if row_dict["TrackCount"] > 0:
                playlists.append(
                    Playlist(id=row_dict["PlaylistID"], name=flattened_name)
                )

        return playlists
    return False
