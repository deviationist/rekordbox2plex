from abc import ABC
from typing import Dict, Any, Optional, Callable
from ..data_types import PlexItem


def singleton(cls):
    """Decorator to make a class a singleton"""
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


class RepositoryBase(ABC):
    """Base repository class with caching functionality"""

    def __init__(self) -> None:
        self._cache: Dict[str, PlexItem] = {}
        self._all_fetched = False
        self._display_progress = False

    def progress(self, display_progress=True):
        self._display_progress = display_progress
        return self

    def _get_cache_key(
        self, params: PlexItem, cache_key_resolver: Callable | None = None
    ):
        """Generate cache key from endpoint and parameters"""
        if callable(cache_key_resolver):
            return cache_key_resolver(params)
        return params.ratingKey

    def _get_all_cache(self):
        if len(self._cache) > 0:
            return self._cache
        return False

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Retrieve data from cache"""
        if cache_key in self._cache:
            return self._cache[cache_key]
        return False

    def _append_to_cache(self, items: Any):
        """Append data in cache"""
        for item in items:
            self._store_single_in_cache(item)

    def _store_in_cache(self, items: Any, cache_key_resolver: Callable | None = None):
        """Store data in cache"""
        self._clear_cache()
        for item in items:
            self._store_single_in_cache(item, cache_key_resolver)
        self._display_progress = False
        self._all_fetched = True

    def _store_single_in_cache(
        self, item: Any, cache_key_resolver: Callable | None = None
    ):
        """Store item in cache"""
        cache_key = self._get_cache_key(item, cache_key_resolver)
        self._cache[cache_key] = item

    def _clear_cache(self):
        """Clear cache"""
        self._cache.clear()
