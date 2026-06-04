import sqlite3
from typing import Any, Dict, List, Tuple


def _connect_ro(db_path: str) -> sqlite3.Connection:
    """Open the Plex DB read-only, coping with both states it can be in.

    While Plex runs, the DB is in WAL mode with live -wal/-shm sidecars and a
    plain ``mode=ro`` open works. After a clean shutdown the sidecars are gone
    and ``mode=ro`` raises "attempt to write a readonly database" (it would need
    to recreate the -shm); ``immutable=1`` reads the consolidated main file
    directly. We try ro first (correct when a -wal exists) and fall back to
    immutable (correct when checkpointed), so reads never disturb a live Plex
    and never go stale against a stopped one."""
    last_err: Exception | None = None
    for uri in (f"file:{db_path}?mode=ro", f"file:{db_path}?immutable=1"):
        con = sqlite3.connect(uri, uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            con.execute("SELECT 1 FROM metadata_items LIMIT 1").fetchone()
            return con
        except sqlite3.OperationalError as e:
            last_err = e
            con.close()
    raise sqlite3.OperationalError(f"cannot open Plex DB read-only: {last_err}")


def read_metadata_row(db_path: str, metadata_id: int) -> Dict[str, Any] | None:
    """Read one metadata_items row (id, title, type, added_at). None if absent."""
    con = _connect_ro(db_path)
    try:
        row = con.execute(
            "SELECT id, title, metadata_type, added_at "
            "FROM metadata_items WHERE id = ?",
            (metadata_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def read_library(
    db_path: str, library_name: str
) -> Tuple[int, List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    """Enumerate a music library straight from the Plex DB.

    Returns ``(section_id, tracks, albums)`` where ``tracks`` is a list of dicts
    ``{rk, album_id, title, added_at, file}`` (rk == metadata_items.id) and
    ``albums`` maps album id -> ``{title, added_at}``. Raises ValueError if the
    named library doesn't exist."""
    con = _connect_ro(db_path)
    try:
        sec = con.execute(
            "SELECT id FROM library_sections WHERE name = ?", (library_name,)
        ).fetchone()
        if sec is None:
            raise ValueError(f"Plex library {library_name!r} not found")
        sid = int(sec["id"])

        tracks = [
            dict(r)
            for r in con.execute(
                """
                SELECT mi.id AS rk, mi.parent_id AS album_id, mi.title, mi.added_at,
                       (SELECT mp.file
                          FROM media_items med
                          JOIN media_parts mp ON mp.media_item_id = med.id
                         WHERE med.metadata_item_id = mi.id
                         ORDER BY mp.id LIMIT 1) AS file
                FROM metadata_items mi
                WHERE mi.metadata_type = 10 AND mi.library_section_id = ?
                """,
                (sid,),
            )
        ]

        albums = {
            int(r["id"]): {"title": r["title"], "added_at": r["added_at"]}
            for r in con.execute(
                "SELECT id, title, added_at FROM metadata_items "
                "WHERE metadata_type = 9 AND library_section_id = ?",
                (sid,),
            )
        }
        return sid, tracks, albums
    finally:
        con.close()
