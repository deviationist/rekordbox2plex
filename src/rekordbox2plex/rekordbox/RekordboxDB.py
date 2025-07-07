from pysqlcipher3 import dbapi2 as sqlite
from ..config import get_db_pass, get_db_path
import sys
import atexit


def close_connection():
    db = RekordboxDB()
    db.close()


def setup_db_connection():
    try:
        db = RekordboxDB()
        db.cursor
    except Exception as e:
        sys.exit(f"Cannot connect to DB. Please check DB path and password. Error: {e}")
    atexit.register(close_connection)


class RekordboxDB:
    _instance = None
    _conn = None
    _cursor = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RekordboxDB, cls).__new__(cls)
        return cls._instance

    def connect(self):
        if self._conn is None:
            DB_PATH = get_db_path()
            DB_PASSWORD = get_db_pass()
            uri = f"file:{DB_PATH}?mode=ro"
            self._conn = sqlite.connect(uri)
            self._conn.row_factory = sqlite.Row
            self._cursor = self._conn.cursor()
            self._cursor.execute(f"PRAGMA key='{DB_PASSWORD}';")
            # Optional: Set some performance pragmas
            self._cursor.execute("PRAGMA temp_store = MEMORY")
            self._cursor.execute("PRAGMA cache_size = 10000")
        return self._conn, self._cursor

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            self._cursor = None

    @property
    def cursor(self):
        if self._cursor is None:
            self.connect()
        return self._cursor

    @property
    def connection(self):
        if self._conn is None:
            self.connect()
        return self._conn
