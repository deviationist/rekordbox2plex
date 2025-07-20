from pysqlcipher3 import dbapi2 as sqlite
from ..config import get_db_pass, get_db_path
from ..utils.logger import logger
from ..utils.helpers import get_boolenv
import os
import sys
import atexit
import shutil
import tempfile


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
    _db_path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RekordboxDB, cls).__new__(cls)
        return cls._instance

    def make_temp_db_copy(self, db_path):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            temp_db_path = tmp.name
        shutil.copy2(db_path, temp_db_path)
        self._db_path = temp_db_path
        logger.debug(f"Copied Rekordbox DB to temporary location: {temp_db_path}")


    def delete_temp_db_copy(self):
        os.remove(self._db_path)
        logger.debug(f"Deleted temporary Rekordbox DB copy: {self._db_path}")


    def connect(self):
        if self._conn is None:
            DB_PATH = get_db_path()
            self._db_path = DB_PATH
            if get_boolenv("REKORDBOX_COPY_DB_BEFORE_SYNC", True):
                self.make_temp_db_copy(DB_PATH)
            DB_PASSWORD = get_db_pass()
            uri = f"file:{self._db_path}?mode=ro"
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
            if get_boolenv("REKORDBOX_COPY_DB_BEFORE_SYNC", True):
                self.delete_temp_db_copy()


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
