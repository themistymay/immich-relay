import os
import re

from logger import get_logger

log = get_logger("cache_manager")


class CacheManager:
    def __init__(self, cache_dir: str):
        self._cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def asset_path(self, asset_id: str, filename: str) -> str:
        safe_filename = re.sub(r"[^\w.\-]", "_", os.path.basename(filename))
        safe_filename = safe_filename.lstrip(".")
        if not safe_filename:
            safe_filename = "asset"
        return os.path.join(self._cache_dir, f"{asset_id}_{safe_filename}")

    def purge_file(self, path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            log.warning("Cache file already missing when purging: %s", path)

    def purge_all(self) -> None:
        try:
            entries = os.listdir(self._cache_dir)
        except OSError as exc:
            log.error("Could not list cache dir for purge: %s", exc)
            return
        for name in entries:
            full = os.path.join(self._cache_dir, name)
            if os.path.isfile(full):
                try:
                    os.remove(full)
                except OSError as exc:
                    log.warning("Failed to remove cache file %s: %s", full, exc)

    def assert_empty(self) -> None:
        try:
            entries = [
                e for e in os.listdir(self._cache_dir)
                if os.path.isfile(os.path.join(self._cache_dir, e))
            ]
        except OSError:
            return
        if entries:
            log.warning(
                "Cache dir not empty after sync run — %d file(s) remain: %s",
                len(entries), entries[:5],
            )
