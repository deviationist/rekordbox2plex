from pysqlcipher3 import dbapi2 as sqlite
import os

DB_PATH = os.getenv("REKORDBOX_MASTERDB_PATH")
DB_PASSWORD = os.getenv("REKORDBOX_MASTERDB_PASSWORD")

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
