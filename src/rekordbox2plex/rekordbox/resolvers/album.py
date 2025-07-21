from ..RekordboxDB import RekordboxDB
from ...utils.logger import logger
from ..data_types import TrackWithArtwork, Artist, Album, ResolvedAlbumWithTracks
from typing import Literal


def get_album_with_tracks(
    album_name: str, artist_name: str
) -> ResolvedAlbumWithTracks | Literal[False]:
    db = RekordboxDB()
    cursor = db.cursor

    try:
        query = """
        SELECT
            al.ID AS album_ID, al.Name AS album_Name,
            c.ID AS track_ID, c.Title AS track_Title, c.ReleaseYear AS track_ReleaseYear, c.ReleaseDate AS track_ReleaseDate, c.FolderPath AS track_FolderPath, c.StockDate AS track_AddedAt,
            a.ID AS artist_ID, a.Name AS artist_Name,
            aa.ID AS albumArtist_ID, aa.Name AS albumArtist_Name,
            cf.ID AS artwork_ID, cf.Path AS artwork_Path, cf.rb_local_path AS artwork_rb_local_path,
            l.Name AS track_Label
        FROM djmdContent AS c
        LEFT JOIN
            djmdArtist AS a
            ON c.ArtistID = a.ID
        LEFT JOIN
            djmdAlbum AS al
            ON al.ID = c.AlbumID
        LEFT JOIN
            djmdArtist AS aa
            ON aa.ID = al.AlbumArtistID
        LEFT JOIN
            djmdLabel as l
            ON l.ID = c.LabelID
        LEFT JOIN
            contentFile AS cf
            ON c.ImagePath = cf.Path
        WHERE
            al.Name = ?
            AND aa.Name = ?
            AND a.rb_local_deleted = 0
            AND al.rb_local_deleted = 0
            AND c.rb_local_deleted = 0
    """
        cursor.execute(query, (album_name, artist_name))

        rows = cursor.fetchall()
        if rows:
            tracks = []
            artist = None
            album = None
            album_artist = None

            for row in rows:
                # Convert row to dict for easier handling
                row_dict = dict(row)

                # Provide None for artwork fields if they don't exist
                tracks.append(
                    TrackWithArtwork(
                        id=int(row_dict["track_ID"]),
                        title=row_dict["track_Title"],
                        label=row_dict["track_Label"],
                        release_year=int(row_dict["track_ReleaseYear"]),
                        release_date=row_dict["track_ReleaseDate"],
                        added_at=row_dict.get("track_AddedAt"),
                        folder_path=row_dict.get("track_FolderPath"),
                        artwork_id=row_dict.get("artwork_ID"),
                        artwork_path=row_dict.get("artwork_Path"),
                        artwork_local_path=row_dict.get("artwork_rb_local_path"),
                    )
                )

                if artist is None:
                    artist = Artist(
                        id=int(row_dict["artist_ID"]),
                        name=row_dict["artist_Name"],
                    )
                if album is None:
                    album = Album(
                        id=int(row_dict["album_ID"]), name=row_dict["album_Name"]
                    )

                if album_artist is None:
                    album_artist = Artist(
                        id=int(row_dict["albumArtist_ID"]),
                        name=row_dict["albumArtist_Name"],
                    )

            return ResolvedAlbumWithTracks(tracks, artist, album, album_artist)
        else:
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info("[red]Database error:", e)
        return False
