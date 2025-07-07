from ..RekordboxDB import RekordboxDB
from typing import List, Literal
import pprint
from ..data_types import Playlist, PlaylistTrack

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
            pprint.pprint(row_dict)
            tracks.append(PlaylistTrack(
                id=row_dict["track_ID"],
                title=row_dict["track_Title"]
            ))
        return tracks
    return False

def get_all_playlists() -> List[Playlist] | Literal[False]:
    db = RekordboxDB()
    cursor = db.cursor

    query = """
    SELECT
        child.ID AS playlist_ID,
        CASE
            WHEN parent.Name IS NOT NULL THEN parent.Name || '/' || child.Name
            ELSE child.Name
        END AS FlattenedName,
        COUNT(sp.ID) AS TrackCount
    FROM
        djmdPlaylist AS child
    LEFT JOIN
        djmdPlaylist AS parent
        ON child.ParentID = parent.ID
    JOIN
        djmdSongPlaylist AS sp
        ON sp.PlaylistID = child.ID
    WHERE
        child.rb_data_status = 0
        AND sp.rb_data_status = 0
    GROUP BY
        child.ID, FlattenedName
    HAVING
        COUNT(sp.ID) > 0
    ORDER BY
        FlattenedName;
"""
    cursor.execute(query)
    rows = cursor.fetchall()
    if rows:
        tracks = []

        for row in rows:
            # Convert row to dict for easier handling
            row_dict = dict(row)
            pprint.pprint(row_dict)
            tracks.append(Playlist(
                id=row_dict["playlist_ID"],
                name=row_dict["FlattenedName"]
            ))
        return tracks
    return False

