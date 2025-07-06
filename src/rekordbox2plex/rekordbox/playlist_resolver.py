from .RekordboxDB import RekordboxDB
from typing import Any

def get_playlist_tracks(playlist_ID) -> Any:
    db = RekordboxDB()
    cursor = db.cursor

    query = """
    SELECT
        c.ID,
        c.Title
    FROM djmdSongPlaylist AS pl
    INNER JOIN
        djmdContent AS c
  		ON c.ID = pl.ContentID
    WHERE
        pl.PlaylistID = ?
        AND pl.rb_data_status = 0
        AND c.rb_data_status = 0
"""
    cursor.execute(query, (playlist_ID,))
    return cursor.fetchall()

def get_all_playlists() -> Any:
    db = RekordboxDB()
    cursor = db.cursor

    query = """
    SELECT
        child.ID AS PlaylistID,
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
    return cursor.fetchall()

