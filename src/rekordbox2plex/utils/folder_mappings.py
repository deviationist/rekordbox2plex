import json
from typing import Dict, Optional
from ..config import get_folder_mappings_path
from .logger import logger

_cache: Optional[Dict[str, str]] = None
_warned_missing = False


def get_folder_mappings() -> Dict[str, str]:
    global _cache, _warned_missing
    if _cache is not None:
        return _cache

    mappings_override = get_folder_mappings_path()
    mappings_path = mappings_override or "folderMappings.json"
    try:
        with open(mappings_path, "r") as f:
            _cache = json.load(f)
    except FileNotFoundError:
        if mappings_override:
            raise FileNotFoundError(
                f"Folder mappings file not found: {mappings_override}"
            )
        if not _warned_missing:
            logger.info(
                "[red]Warning: folderMappings.json not found, using original path"
            )
            _warned_missing = True
        _cache = {}
    return _cache
