from typing import Dict, List, Optional, Set

from ..RekordboxDB import RekordboxDB
from .track import is_ignored_rb_path

# Same collection filter used by track.py::_query_rb_id: a live, non-deleted
# entry that actually points at a file.
_COLLECTION_WHERE = (
    "c.rb_local_deleted = 0 AND c.rb_data_status = 0 AND c.rb_file_id != 0"
)


def get_rb_metadata(rb_id: int) -> Optional[Dict[str, Optional[str]]]:
    """Read a Rekordbox track's display metadata by ``djmdContent.ID``.

    Returns ``{title, artist, album, album_artist, folder_path}`` (values may be
    ``None`` when Rekordbox has no artist/album set), or ``None`` if the id isn't
    present.

    ``Title`` and ``FolderPath`` are denormalized on ``djmdContent``; artist/album
    are id references resolved via ``djmdArtist``/``djmdAlbum``, and the album
    artist hangs off the album (``djmdAlbum.AlbumArtistID`` -> ``djmdArtist.Name``).
    """
    cursor = RekordboxDB().cursor
    cursor.execute(
        """
        SELECT c.Title      AS title,
               a.Name        AS artist,
               al.Name       AS album,
               aa.Name       AS album_artist,
               c.FolderPath  AS folder_path
        FROM djmdContent c
        LEFT JOIN djmdArtist a  ON a.ID  = c.ArtistID
        LEFT JOIN djmdAlbum  al ON al.ID = c.AlbumID
        LEFT JOIN djmdArtist aa ON aa.ID = al.AlbumArtistID
        WHERE c.ID = ?
        """,
        (rb_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def get_all_rb_track_ids(ignore_fragments: Optional[List[str]] = None) -> Set[int]:
    """All live Rekordbox collection track ids (for orphan detection).

    Mirrors the collection filter in ``track.py``: deleted/stale entries and
    rows with no backing file are excluded. Tracks whose ``FolderPath`` contains
    one of ``ignore_fragments`` (REKORDBOX_FOLDER_PATHS_TO_IGNORE) are dropped so
    they don't surface as Rekordbox-side orphans.
    """
    cursor = RekordboxDB().cursor
    cursor.execute(
        f"SELECT c.ID AS id, c.FolderPath AS folder_path "
        f"FROM djmdContent c WHERE {_COLLECTION_WHERE}"
    )
    rows = [dict(r) for r in cursor.fetchall()]
    return {
        int(r["id"])
        for r in rows
        if not is_ignored_rb_path(r["folder_path"], ignore_fragments or [])
    }
