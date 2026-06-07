"""Translate Plex *container* file paths into HOST filesystem paths.

Plex stores each media part's path as the container sees it (e.g.
``/data/music/main/x.aiff``). To open that file from the host where this tool
runs (e.g. xavi, where the bind mounts it at ``/tank/music/main/x.aiff``) we
need a prefix map. The existing ``folderMappings.json`` is Plex→Rekordbox only;
this is the separate Plex→host mapping the ``aiff-titles`` command needs.

Config: ``PLEX_MEDIA_PATH_MAP`` = comma-separated ``container=host`` pairs,
e.g. ``/data/music=/tank/music``. Longest container prefix wins.
"""

from typing import List, Optional, Tuple

# (container_prefix, host_prefix) pairs, no trailing slash, longest-first.
PathMap = List[Tuple[str, str]]


def parse_media_path_map(raw: Optional[str]) -> PathMap:
    """Parse the PLEX_MEDIA_PATH_MAP env value into longest-prefix-first pairs.

    Raises ValueError on a malformed entry (missing ``=``)."""
    if not raw:
        return []
    pairs: PathMap = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(
                f"Invalid PLEX_MEDIA_PATH_MAP entry {item!r} "
                f"(expected 'container=host', e.g. '/data/music=/tank/music')"
            )
        container, host = item.split("=", 1)
        pairs.append((container.strip().rstrip("/"), host.strip().rstrip("/")))
    # Longest container prefix first so the most specific mapping wins.
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def resolve_host_path(plex_path: str, mapping: PathMap) -> Optional[str]:
    """Return the host filesystem path for a Plex container path, or None if no
    mapping prefix matches."""
    for container, host in mapping:
        if plex_path == container or plex_path.startswith(container + "/"):
            return host + plex_path[len(container) :]
    return None
