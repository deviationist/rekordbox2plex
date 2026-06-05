import os
import sqlite3
import subprocess
from typing import Optional


def container_state(container_name: str) -> Optional[str]:
    """Return the container's docker state ('running', 'exited', ...) or None
    if docker is unavailable or the container does not exist."""
    try:
        proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def apply_plan_docker(
    db_path: str, plan_sql: str, image: str, sqlite_bin: str
) -> subprocess.CompletedProcess:
    """Apply the plan via the bundled 'Plex SQLite' binary inside `image`.

    Mounts the database directory to /db and runs the binary (overriding the
    image entrypoint so it bypasses the s6 init). The container is run as the
    DB file's own uid:gid (`--user`) so it can write — some Docker setups don't
    give container-root a DAC bypass over host files, and the live Plex DB is
    typically owned by the Plex container's (non-root) UID. Plex must be stopped:
    this opens the DB for writing."""
    db_dir = os.path.dirname(db_path)
    db_name = os.path.basename(db_path)
    st = os.stat(db_path)
    cmd = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--user",
        f"{st.st_uid}:{st.st_gid}",
        "-v",
        f"{db_dir}:/db",
        "--entrypoint",
        sqlite_bin,
        image,
        f"/db/{db_name}",
    ]
    return subprocess.run(cmd, input=plan_sql, capture_output=True, text=True)


def apply_plan_sqlite3(db_path: str, plan_sql: str) -> None:
    """Apply the plan with stock sqlite3 (for writing to a scratch copy).

    A bare integer UPDATE by integer primary key touches no Plex custom
    collation, so this is safe for verification on a copy. Not recommended
    against the live DB — prefer the docker mechanism."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(plan_sql)
        conn.commit()
    finally:
        conn.close()


def count_updates(plan_sql: str) -> int:
    return sum(
        1 for line in plan_sql.splitlines() if line.startswith("UPDATE metadata_items")
    )


def _safe_comment(text: str) -> str:
    return str(text).replace("\n", " ").replace("--", "—")


def build_plan_sql(track_updates, album_updates) -> str:
    """Build the UPDATE script from in-memory plan rows.

    Each row is a dict with ``id``, ``proposed`` (epoch int) and ``title``. The
    title only appears in a sanitized trailing comment — values and ids are pure
    integers, so titles can't affect or inject SQL. Returned as a string and fed
    to Plex SQLite via stdin; no file is written."""
    lines = ["BEGIN TRANSACTION;"]
    if track_updates:
        lines.append("-- TRACKS (metadata_type 10)")
        for u in track_updates:
            lines.append(
                f"UPDATE metadata_items SET added_at = {int(u['proposed'])} "
                f"WHERE id = {int(u['id'])};  -- {_safe_comment(u['title'])}"
            )
    if album_updates:
        lines.append("-- ALBUMS (metadata_type 9, min of member tracks)")
        for u in album_updates:
            lines.append(
                f"UPDATE metadata_items SET added_at = {int(u['proposed'])} "
                f"WHERE id = {int(u['id'])};  -- {_safe_comment(u['title'])}"
            )
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"
