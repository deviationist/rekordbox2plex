from .RekordboxDB import RekordboxDB
from ..utils.logger import logger
from .types import TrackWithArtwork, Artist, Album, ResolvedAlbumWithTracks

def get_album_with_tracks(album_name, artist_name) -> ResolvedAlbumWithTracks | bool:
    db = RekordboxDB()
    cursor = db.cursor

    try:
        query = """
        SELECT
            a.ID AS album_ID, a.Name AS album_Name,
            c.ID AS track_ID, c.Title AS track_Title, c.ReleaseYear AS track_ReleaseYear,
            aa.ID AS albumAritst_ID, aa.Name AS albumAritst_Name,
            cf.ID AS artwork_ID, cf.Path AS artwork_Path, cf.rb_local_path AS artwork_rb_local_path
        FROM djmdContent AS c
        INNER JOIN
            djmdArtist AS aa
            ON c.ArtistID = aa.ID
        INNER JOIN
            djmdAlbum AS a
            ON a.AlbumArtistID = aa.ID
        LEFT JOIN
            contentFile AS cf
            ON c.ImagePath = cf.Path
        WHERE
            a.Name = ?
            AND aa.Name = ?
            AND c.rb_local_deleted = 0
    """
        cursor.execute(query, (album_name, artist_name))

        rows = cursor.fetchall()
        if rows:
            tracks = []
            artist = None
            album = None
            artwork = None

            for row in rows:
                # Convert row to dict for easier handling
                row_dict = dict(row)

                # Provide None for artwork fields if they don't exist
                tracks.append(TrackWithArtwork(
                    id=int(row_dict["track_ID"]),
                    title=row_dict["track_Title"],
                    release_year=int(row_dict["track_ReleaseYear"]),
                    artwork_id=row_dict.get("artwork_ID"),
                    artwork_path=row_dict.get("artwork_Path"),
                    artwork_local_path=row_dict.get("artwork_rb_local_path")
                ))

                if artist == None:
                    artist = Artist(
                        id=int(row_dict["albumAritst_ID"]),
                        name=row_dict["albumAritst_Name"]
                    )
                if album == None:
                    album = Album(
                        id=int(row_dict["album_ID"]),
                        name=row_dict["album_Name"]
                    )

            return ResolvedAlbumWithTracks(tracks, artist, album, artwork)
        else:
            return False

    except Exception as e:  # Changed from sqlite.Error to catch any issues
        logger.info("[red]Database error:", e)
        return False





