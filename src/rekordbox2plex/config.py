import os
import re
import argparse
from typing import Optional, List, Set
from .utils.helpers import get_boolenv
from .utils.paths import PROJECT_ROOT

_args: argparse.Namespace | None = None


def set_args(args: argparse.Namespace) -> None:
    global _args
    _args = args


def get_args() -> argparse.Namespace:
    if _args is None:
        raise RuntimeError("Arguments have not been initialized")
    return _args


def get_command() -> str:
    return get_args().command


def should_wipe() -> bool:
    return getattr(get_args(), "wipe", False)


def is_dry_run() -> bool:
    return getattr(get_args(), "dry_run", False)


def should_restore_dates() -> bool:
    return get_command() == "dates"


def get_validate_track() -> Optional[str]:
    return getattr(get_args(), "validate_track", None)


def get_validate_album() -> Optional[str]:
    return getattr(get_args(), "validate_album", None)


def should_write() -> bool:
    # --dry-run always wins: it forces a read-only run even if --write is given.
    return getattr(get_args(), "write", False) and not getattr(
        get_args(), "dry_run", False
    )


def get_plan_file() -> Optional[str]:
    """Optional path to dump the SQL plan for inspection. None = don't write a
    file (the default; the write itself streams SQL to Plex SQLite via stdin)."""
    return getattr(get_args(), "plan_file", None)


def get_only_rating_keys() -> Optional[Set[int]]:
    """Parse --only into a set of Plex ratingKeys, or None for the whole library.
    Accepts track and/or album ids (e.g. "17779,17776")."""
    raw = getattr(get_args(), "only", None)
    if not raw:
        return None
    ids = {int(p.strip()) for p in raw.split(",") if p.strip()}
    return ids or None


def should_include_tracks() -> bool:
    return getattr(get_args(), "tracks", True)


def should_include_albums() -> bool:
    return getattr(get_args(), "albums", True)


PARITY_FIELDS = ("title", "artist", "album", "albumartist")  # selectable via --fields
# `albumartist` is OFF by default: Rekordbox deduplicates djmdAlbum by NAME (even on
# edit), so one album row backs unrelated same-named releases and its AlbumArtistID is
# per-album, not per-track — structurally unreliable and unfixable in Rekordbox. The
# album row is trustworthy only for the album *name*. Opt in with --fields …,albumartist.
PARITY_DEFAULT_FIELDS = ("title", "artist", "album")


def get_parity_fields() -> Set[str]:
    """Which metadata fields the `parity` check compares. Default: title, artist,
    album. `albumartist` is **opt-in** — Rekordbox shares one album row across
    same-named releases, so its album-artist is unreliable (see
    PARITY_DEFAULT_FIELDS). --fields takes a comma-separated subset of
    title,artist,album,albumartist."""
    raw = getattr(get_args(), "fields", None)
    if not raw:
        return set(PARITY_DEFAULT_FIELDS)
    chosen = {p.strip().lower() for p in raw.split(",") if p.strip()}
    unknown = chosen - set(PARITY_FIELDS)
    if unknown:
        raise ValueError(
            f"Unknown parity field(s): {', '.join(sorted(unknown))}. "
            f"Valid: {', '.join(PARITY_FIELDS)}"
        )
    return chosen or set(PARITY_DEFAULT_FIELDS)


def should_split_artists() -> bool:
    """`parity`: when an ``artist``/``albumartist`` field misses a direct
    (normalized) comparison, retry by splitting **both** sides into component
    artists with the shared collab separators and comparing the components. Lets
    'Fred V & Grafix' (Plex) equal 'Fred V, Grafix' (Rekordbox). Off by default.
    Separators come from the artist-images collab config (primary +
    ARTIST_COLLAB_EXTRA_SEPARATORS / --collab-extra-seps), so the ambiguous
    ``&``/``+`` tier stays opt-in."""
    return getattr(get_args(), "split_artists", False)


def should_match_artist_order() -> bool:
    """`parity --split-artists`: require the split artist components to match in
    the same **order**. Default off → order-independent comparison, so
    'A, B' equals 'B, A'."""
    return getattr(get_args(), "split_artists_ordered", False)


def should_include_orphans() -> bool:
    """Whether `parity` reports tracks present in one system but not the other."""
    return getattr(get_args(), "orphans", True)


def get_orphan_limit() -> int:
    """Cap on the per-side orphan *sample* printed (counts are always full)."""
    return int(getattr(get_args(), "orphan_limit", 50))


def should_output_json() -> bool:
    """Whether `parity` emits a JSON document on stdout instead of tables."""
    return getattr(get_args(), "json", False)


def should_remove_name() -> bool:
    """`aiff-titles`: delete the AIFF NAME chunk instead of setting it to the
    ID3 title."""
    return getattr(get_args(), "remove_name", False)


def should_refresh_plex() -> bool:
    """`aiff-titles`: after writing, trigger album-level Refresh Metadata via
    the Plex API so Plex re-reads the corrected tags."""
    return getattr(get_args(), "refresh_plex", False)


def get_aiff_backup_dir() -> Optional[str]:
    """`aiff-titles`: where originals are backed up before editing. CLI
    --backup-dir wins, then AIFF_BACKUP_DIR; None lets the action pick a default."""
    return getattr(get_args(), "backup_dir", None) or os.getenv("AIFF_BACKUP_DIR")


# --- lossless-tags subcommand -------------------------------------------------


def get_music_root() -> Optional[str]:
    """`lossless-tags`: filesystem root to walk for lossy/lossless pairs. CLI
    --root wins, then MUSIC_ROOT. None means unset (the action errors)."""
    return getattr(get_args(), "root", None) or os.getenv("MUSIC_ROOT")


def _split_exts(raw: Optional[str], default: tuple[str, ...]) -> tuple[str, ...]:
    """Normalise a comma-separated extension list into a lowercased, dot-prefixed
    tuple (e.g. 'mp3, .M4A' → ('.mp3', '.m4a')). Empty/unset → default."""
    if not raw:
        return default
    out = []
    for part in raw.split(","):
        e = part.strip().lower()
        if not e:
            continue
        out.append(e if e.startswith(".") else "." + e)
    return tuple(out) or default


def get_lossy_exts() -> tuple[str, ...]:
    """`lossless-tags`: extensions treated as lossy sources (default '.mp3')."""
    return _split_exts(getattr(get_args(), "lossy_exts", None), (".mp3",))


def get_lossless_exts() -> tuple[str, ...]:
    """`lossless-tags`: extensions treated as lossless targets (default AIFF).
    Only AIFF/AIFF-C are supported for the wholesale ID3 copy; FLAC (Vorbis
    comments) and WAV are intentionally excluded."""
    return _split_exts(getattr(get_args(), "lossless_exts", None), (".aiff", ".aif"))


def should_delete_lossy() -> bool:
    """`lossless-tags`: delete the lossy source after a fully successful copy."""
    return getattr(get_args(), "delete_lossy", False)


def should_mirror_id3_version() -> bool:
    """`lossless-tags`: save ID3 as the source's major version instead of forcing
    v2.3 (the Plex/Rekordbox-friendly default)."""
    return getattr(get_args(), "mirror_version", False)


def should_ignore_case() -> bool:
    """`lossless-tags`: match basenames case-insensitively (default: exact, to
    mirror the case-sensitive host filesystem)."""
    return getattr(get_args(), "ignore_case", False)


def get_show_mode() -> str:
    """`lossless-tags`: which lossy files the dry-run lists — 'matched' (default,
    those with a lossless sibling), 'unmatched' (not yet upgraded), or 'both'."""
    return getattr(get_args(), "show", "matched")


def get_tag_backup_dir() -> Optional[str]:
    """`lossless-tags`: where lossless originals are backed up before the ID3
    overwrite. CLI --backup-dir wins, then TAG_BACKUP_DIR; None → action default."""
    return getattr(get_args(), "backup_dir", None) or os.getenv("TAG_BACKUP_DIR")


def get_tag_copy_limit() -> Optional[int]:
    """`lossless-tags`: process at most N pairs this run (None = no cap)."""
    return getattr(get_args(), "limit", None)


def should_snapshot_dates() -> bool:
    """`lossless-tags --snapshot-dates`: while copying, capture each lossy file's
    Rekordbox Date Added into the rb-dates sidecar (read-only RB access), so it can
    be restored onto the re-added lossless file later. See [[rb-dates]]."""
    return getattr(get_args(), "snapshot_dates", False)


# --- rb-dates subcommand ------------------------------------------------------


def get_rb_dates_mode() -> str:
    """`rb-dates`: 'snapshot' (capture, read-only) or 'apply' (restore)."""
    return getattr(get_args(), "rb_dates_mode", "snapshot")


def get_rb_date_snapshot_path() -> str:
    """Sidecar JSON holding captured dates. CLI --snapshot-file wins, then
    RB_DATE_SNAPSHOT_PATH, else ./rb-date-snapshots.json."""
    return (
        getattr(get_args(), "snapshot_file", None)
        or os.getenv("RB_DATE_SNAPSHOT_PATH")
        or str(PROJECT_ROOT / "rb-date-snapshots.json")
    )


def get_rb_date_backup_dir() -> Optional[str]:
    """Where master.db is backed up before an `rb-dates apply --write`. CLI
    --backup-dir wins, then RB_DATE_BACKUP_DIR; None → action default."""
    return getattr(get_args(), "backup_dir", None) or os.getenv("RB_DATE_BACKUP_DIR")


def get_stability_wait() -> float:
    """`rb-dates apply`: seconds the quiescence probe waits between stat samples
    (the master.db must be unchanged across the window)."""
    return float(getattr(get_args(), "stability_wait", 5.0) or 5.0)


def should_ignore_wal() -> bool:
    """`rb-dates apply`: proceed even if a non-empty master.db-wal exists
    (advanced — normally a sign Rekordbox is still open)."""
    return getattr(get_args(), "ignore_wal", False)


def should_keep_applied() -> bool:
    """`rb-dates apply`: keep successfully-restored entries in the sidecar instead
    of pruning them (default prunes so the backlog shrinks)."""
    return getattr(get_args(), "keep_applied", False)


# --- artist-images subcommand -------------------------------------------------


def get_artist_image_providers() -> List[str]:
    """Ordered list of artist-image provider names (driver priority). CLI
    --providers wins, then PLEX_ARTIST_IMAGE_PROVIDERS, default
    'fanarttv,theaudiodb,discogs' — curated MBID-keyed portraits first (closest
    to what Plex's agent prefers), with Discogs last as the broad coverage
    fallback (its community images are often release covers, not portraits).
    fanarttv needs FANARTTV_API_KEY and discogs a token/key+secret — each is
    skipped, with a warning, if unconfigured."""
    raw = getattr(get_args(), "providers", None)
    if not raw:
        raw = (
            os.getenv("PLEX_ARTIST_IMAGE_PROVIDERS")
            or "fanarttv,theaudiodb,deezer,spotify,bandcamp,discogs"
        )
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def get_theaudiodb_api_key() -> str:
    """TheAudioDB API key. Defaults to the public test key '2'."""
    return os.getenv("THEAUDIODB_API_KEY", "2")


def get_fanarttv_api_key() -> Optional[str]:
    """fanart.tv personal API key. None disables the fanarttv provider."""
    return os.getenv("FANARTTV_API_KEY")


def get_spotify_client_id() -> Optional[str]:
    """Spotify app client id (client-credentials flow). None disables spotify."""
    return os.getenv("SPOTIFY_CLIENT_ID")


def get_spotify_client_secret() -> Optional[str]:
    """Spotify app client secret (paired with SPOTIFY_CLIENT_ID)."""
    return os.getenv("SPOTIFY_CLIENT_SECRET")


def get_discogs_token() -> Optional[str]:
    """Discogs personal access token (simplest auth). Alternative to key+secret."""
    return os.getenv("DISCOGS_TOKEN")


def get_discogs_key() -> Optional[str]:
    """Discogs consumer key (used with DISCOGS_SECRET if no DISCOGS_TOKEN)."""
    return os.getenv("DISCOGS_KEY")


def get_discogs_secret() -> Optional[str]:
    """Discogs consumer secret (paired with DISCOGS_KEY)."""
    return os.getenv("DISCOGS_SECRET")


def get_musicbrainz_user_agent() -> str:
    """User-Agent for MusicBrainz lookups (their rules require a descriptive one)."""
    return os.getenv(
        "MUSICBRAINZ_USER_AGENT",
        "rekordbox2plex/0.1 ( https://github.com/deviationist/rekordbox2plex )",
    )


def should_overwrite_posters() -> bool:
    """`artist-images`: replace existing artist posters too (default: only fill
    artists that have none)."""
    return getattr(get_args(), "overwrite", False)


def get_clear_kinds() -> tuple:
    """`clear-art`: which metadata types to clear uploaded posters for, from
    --kind (artist=8, album=9, both). Defaults to artist only."""
    kind = getattr(get_args(), "kind", None) or "artist"
    return {"artist": (8,), "album": (9,), "both": (8, 9)}.get(kind, (8,))


def should_keep_files() -> bool:
    """`clear-art --keep-files`: only clear the DB selection, leaving the uploaded
    image file on disk (default: also delete the file)."""
    return getattr(get_args(), "keep_files", False)


def get_plex_metadata_path() -> Optional[str]:
    """Override for the Plex ``Metadata`` dir (where poster files live). Defaults
    to None — derived from PLEX_DB_PATH (…/Plex Media Server/Metadata)."""
    return os.getenv("PLEX_METADATA_PATH")


def get_artist_image_limit() -> Optional[int]:
    """`artist-images`: cap how many artists to process this run (None = all)."""
    v = getattr(get_args(), "limit", None)
    return int(v) if v else None


def get_collab_primary_separators() -> List[str]:
    """`artist-images`: the always-on primary collab separators. Default comma +
    feat/ft/featuring. Env ARTIST_COLLAB_PRIMARY_SEPARATORS, **whitespace-separated**
    so ',' can be a token (e.g. ", feat ft featuring & +")."""
    from .artwork.collab import DEFAULT_PRIMARY_SEPARATORS

    raw = os.getenv("ARTIST_COLLAB_PRIMARY_SEPARATORS")
    if not raw:
        return list(DEFAULT_PRIMARY_SEPARATORS)
    return [tok for tok in re.split(r"\s+", raw.strip()) if tok]


def get_collab_ambiguous_separators() -> List[str]:
    """`artist-images`: extra *ambiguous* separators (e.g. ``&``, ``+``) the matcher
    may split a collab name on **as a last resort** — only after the full string and
    each component miss every source. CLI --collab-extra-seps wins, then env
    ARTIST_COLLAB_EXTRA_SEPARATORS. **Empty/unset = off** (opt-in). Accepts a space-
    or comma-separated list, e.g. "& +" or "&,+"."""
    raw = getattr(get_args(), "collab_extra_seps", None)
    if raw is None:
        raw = os.getenv("ARTIST_COLLAB_EXTRA_SEPARATORS")
    if not raw:
        return []
    return [tok for tok in re.split(r"[,\s]+", str(raw)) if tok]


def get_collab_min_segment_len() -> int:
    """`artist-images`: minimum character length for a split-collab segment to be
    worth resolving (a too-short fragment like 'Bz' or 'A' from a bad split is
    skipped). Env ARTIST_COLLAB_MIN_SEGMENT_LEN; default 2 (drops 1-char only —
    raise to 3+ to also drop 2-char fragments)."""
    raw = os.getenv("ARTIST_COLLAB_MIN_SEGMENT_LEN")
    try:
        return int(raw) if raw else 2
    except ValueError:
        return 2


def get_collab_min_score() -> int:
    """`artist-images`: MusicBrainz confidence threshold for **split-collab pieces**
    (stricter than the default 90 used for whole names, since splitting is riskier).
    Env ARTIST_COLLAB_MIN_SCORE; default 95."""
    raw = os.getenv("ARTIST_COLLAB_MIN_SCORE")
    try:
        return int(raw) if raw else 95
    except ValueError:
        return 95


def get_collab_mode() -> str:
    """`artist-images`: how to handle multi-artist "collab" strings (e.g.
    'A, B, C') that match no single artist — 'skip' (default, leave blank),
    'primary' (use the first member's portrait), or 'collage' (composite each
    member's portrait into one poster)."""
    v = getattr(get_args(), "collab_mode", None)
    return v if v in ("skip", "primary", "collage") else "skip"


def get_artist_image_threads() -> int:
    """`artist-images`: concurrent workers for the (network-bound) match + upload
    phases. Default 8; 1 = serial."""
    v = getattr(get_args(), "threads", None)
    return max(1, int(v)) if v else 8


def get_verbosity() -> int:
    """Shared -v/-vv count (0/1/2)."""
    return int(getattr(get_args(), "verbose", 0) or 0)


def get_plex_db_path() -> Optional[str]:
    """Host path to com.plexapp.plugins.library.db. Optional: when unset the
    read-only DB cross-check is skipped and the write phase will error."""
    return os.getenv("PLEX_DB_PATH")


def get_plex_container_name() -> str:
    return os.getenv("PLEX_CONTAINER_NAME", "plex")


def get_plex_media_path_map() -> Optional[str]:
    """Comma-separated ``container=host`` path-prefix pairs that map Plex's
    stored file paths (e.g. ``/data/music``) to host filesystem paths (e.g.
    ``/tank/music``), so `aiff-titles` can open the audio files on disk. Longest
    matching prefix wins. Example: ``/data/music=/tank/music``."""
    return os.getenv("PLEX_MEDIA_PATH_MAP")


def get_rekordbox_tz() -> Optional[str]:
    """IANA tz name used to interpret *naive* Rekordbox timestamps. None = host
    local zone. Ignored for offset-aware timestamps (e.g. created_at)."""
    return os.getenv("REKORDBOX_TZ")


def get_rb_added_at_field() -> str:
    """Which djmdContent column feeds Plex added_at. Default created_at."""
    return os.getenv("REKORDBOX_ADDED_AT_FIELD", "created_at")


def get_plex_sqlite_mechanism() -> str:
    """How the write executes: 'docker' (bundled Plex SQLite in the stopped
    container's image — recommended) or 'sqlite3' (stock sqlite3, for writing
    to a scratch copy during verification)."""
    return os.getenv("PLEX_SQLITE_MECHANISM", "docker").lower()


def get_plex_docker_image() -> str:
    return os.getenv("PLEX_DOCKER_IMAGE", "linuxserver/plex")


def get_plex_sqlite_bin() -> str:
    return os.getenv("PLEX_SQLITE_BIN", "/usr/lib/plexmediaserver/Plex SQLite")


def should_allow_running() -> bool:
    """Bypass the container-stopped guard (only for scratch-copy testing)."""
    return getattr(get_args(), "allow_running", False)


def get_logger_name() -> str:
    LOGGER_NAME = os.getenv("LOGGER_NAME")
    if LOGGER_NAME:
        return LOGGER_NAME
    return "rekordbox2plex"


def should_delete_orphaned_playlists() -> bool:
    return get_boolenv("DELETE_ORPHANED_PLAYLISTS", False)


def get_playlists_to_ignore() -> List[str]:
    REKORDBOX_PLAYLISTS_TO_IGNORE = os.getenv("REKORDBOX_PLAYLISTS_TO_IGNORE")
    if not REKORDBOX_PLAYLISTS_TO_IGNORE:
        return []
    return [item.strip() for item in REKORDBOX_PLAYLISTS_TO_IGNORE.split(",")]


def get_rb_folder_paths_to_ignore() -> List[str]:
    """Rekordbox FolderPath prefixes to exclude from the `parity` check. A track
    whose Rekordbox FolderPath starts with any of these is skipped entirely (not
    compared, not reported as an orphan on either side). Comma-separated."""
    raw = os.getenv("REKORDBOX_FOLDER_PATHS_TO_IGNORE")
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_folder_mappings_path() -> Optional[str]:
    return os.getenv("FOLDER_MAPPINGS_PATH")


def get_db_path() -> str:
    DB_PATH = os.getenv("REKORDBOX_MASTERDB_PATH")
    if DB_PATH:
        return DB_PATH
    RB_FOLDER_PATH = os.getenv("REKORDBOX_FOLDER_PATH")
    if RB_FOLDER_PATH:
        return f"{RB_FOLDER_PATH.rstrip('/')}/master.db"
    raise Exception("Env REKORDBOX_MASTERDB_PATH missing")


def get_db_pass() -> str:
    DB_PASSWORD = os.getenv("REKORDBOX_MASTERDB_PASSWORD")
    if not DB_PASSWORD:
        raise Exception("Env REKORDBOX_MASTERDB_PASSWORD missing")
    return DB_PASSWORD
