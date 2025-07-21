from ..data_types import CacheItem
from typing import Dict, Literal, List


def singleton(cls):
    """Decorator to make a class a singleton"""
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


class SearchCache:
    """Base repository class with caching functionality for search"""

    def __init__(self) -> None:
        self._cache: Dict[str, List[CacheItem]] = {}

    def _get_cache_key(self, search_string: str) -> str:
        return search_string.strip()

    def get_from_cache(self, search_string: str) -> List[CacheItem] | Literal[False]:
        key = self._get_cache_key(search_string)
        return self._cache.get(key, False)

    def store_in_cache(self, search_string: str, items: List[CacheItem]):
        key = self._get_cache_key(search_string)
        self._cache[key] = items

    def clear_cache(self):
        self._cache.clear()
