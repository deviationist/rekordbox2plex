"""The ONLY write path to the Rekordbox ``master.db`` — restoring ``created_at``
("Date Added") onto a re-added track for the ``rb-dates`` command.

This is the sanctioned exception to "treat the Rekordbox DB as read-only": every
other access opens a temp copy ``mode=ro`` (``RekordboxDB.py``). Here we open the
**real** file read-write, after the caller has guarded it (Rekordbox closed,
Resilio idle, backup taken — see ``utils/rb_db_safety.py``).

Each row update is USN-correct, mirroring what Rekordbox itself does for a local
edit: bump the global counter ``agentRegistry.localUpdateCount.int_1`` and stamp
the row's ``rb_local_usn`` with the new value, plus ``updated_at`` = now. After
committing we ``wal_checkpoint(TRUNCATE)`` so the change lands in ``master.db``
itself (empty ``-wal``) — essential so Resilio propagates one consistent file.
"""

from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from pysqlcipher3 import dbapi2 as sqlite

from ..config import get_db_pass, get_db_path, get_rb_added_at_field

# Only these djmdContent columns may be targeted — column names can't be bound as
# SQL parameters, so this allowlist prevents any injection via the configured field.
WRITABLE_DATE_FIELDS = ("created_at", "StockDate", "DateCreated")

# (rb_id, raw_timestamp_string)
DateRow = Tuple[int, str]


def rb_now() -> str:
    """Current UTC time in Rekordbox's stored format: ``YYYY-MM-DD HH:MM:SS.mmm
    +00:00`` (millisecond precision, space before the offset)."""
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.") + f"{dt.microsecond // 1000:03d} +00:00"


def build_date_updates(
    rows: Sequence[DateRow],
    start_usn: int,
    now_str: str,
    field: str = "created_at",
) -> Tuple[List[Tuple[str, tuple]], int]:
    """Build the (sql, params) statements for a USN-correct date restore.

    Each row consumes the next USN (``start_usn+1 … start_usn+n``) on its
    ``rb_local_usn``; a final statement sets the global counter to ``start_usn+n``.
    Returns (statements, final_usn). Pure — no DB access — so it's unit-testable."""
    if field not in WRITABLE_DATE_FIELDS:
        raise ValueError(f"Refusing to write unknown date field {field!r}")
    stmts: List[Tuple[str, tuple]] = []
    usn = start_usn
    for rb_id, value in rows:
        usn += 1
        stmts.append(
            (
                f"UPDATE djmdContent SET {field} = ?, updated_at = ?, "
                "rb_local_usn = ? WHERE ID = ?",
                (value, now_str, usn, rb_id),
            )
        )
    if rows:
        stmts.append(
            (
                "UPDATE agentRegistry SET int_1 = ?, updated_at = ? "
                "WHERE registry_id = 'localUpdateCount'",
                (usn, now_str),
            )
        )
    return stmts, usn


class RekordboxDBWriter:
    """Read-write SQLCipher connection to the real ``master.db``. Use as a context
    manager so the connection is always closed."""

    def __init__(
        self, db_path: Optional[str] = None, password: Optional[str] = None
    ) -> None:
        self._db_path = db_path or get_db_path()
        self._password = password or get_db_pass()
        self._conn: Optional[sqlite.Connection] = None

    def __enter__(self) -> "RekordboxDBWriter":
        uri = f"file:{self._db_path}?mode=rw"
        self._conn = sqlite.connect(uri, uri=True)
        cur = self._conn.cursor()
        cur.execute(f"PRAGMA key='{self._password}';")
        cur.execute("PRAGMA busy_timeout = 5000")
        return self

    def __exit__(self, *exc) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def _cursor(self):
        assert self._conn is not None, "writer used outside its context manager"
        return self._conn.cursor()

    def read_local_update_count(self) -> int:
        cur = self._cursor
        cur.execute(
            "SELECT int_1 FROM agentRegistry WHERE registry_id = 'localUpdateCount'"
        )
        row = cur.fetchone()
        if row is None or row[0] is None:
            raise RuntimeError("agentRegistry.localUpdateCount missing — aborting")
        return int(row[0])

    def read_current_value(
        self, rb_id: int, field: str = "created_at"
    ) -> Optional[str]:
        if field not in WRITABLE_DATE_FIELDS:
            raise ValueError(f"Unknown date field {field!r}")
        cur = self._cursor
        cur.execute(f"SELECT {field} FROM djmdContent WHERE ID = ?", (rb_id,))
        row = cur.fetchone()
        return None if row is None else (None if row[0] is None else str(row[0]))

    def apply_date_updates(
        self, rows: Sequence[DateRow], field: Optional[str] = None
    ) -> dict:
        """Restore the dates for ``rows`` (skipping any already equal), bumping the
        USN, committing, and truncating the WAL. Returns counts + the final USN."""
        field = field or get_rb_added_at_field()
        assert self._conn is not None
        # Idempotent skip: drop rows already at the target value.
        to_write: List[DateRow] = []
        skipped = 0
        for rb_id, value in rows:
            if self.read_current_value(rb_id, field) == value:
                skipped += 1
            else:
                to_write.append((rb_id, value))

        if not to_write:
            return {"applied": 0, "skipped": skipped, "final_usn": None}

        start_usn = self.read_local_update_count()
        stmts, final_usn = build_date_updates(to_write, start_usn, rb_now(), field)
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN")
            for sql, params in stmts:
                cur.execute(sql, params)
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise
        # Fold the WAL into master.db so Resilio carries a single consistent file.
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return {"applied": len(to_write), "skipped": skipped, "final_usn": final_usn}
