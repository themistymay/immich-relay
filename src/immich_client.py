import time

import requests

from logger import get_logger

log = get_logger("immich_client")

_RETRY_DELAYS = [1, 2, 4]


class ImmichClient:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"x-api-key": api_key})

    def _get(self, path: str, stream: bool = False, **kwargs) -> requests.Response:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt, delay in enumerate([0] + _RETRY_DELAYS):
            if delay:
                time.sleep(delay)
            try:
                resp = self._session.get(url, stream=stream, timeout=30, **kwargs)
                if resp.status_code >= 500:
                    log.warning(
                        "Immich returned %d for %s (attempt %d)",
                        resp.status_code, path, attempt + 1,
                    )
                    last_exc = RuntimeError(
                        f"Immich HTTP {resp.status_code} for {path}"
                    )
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                log.warning("Network error on %s (attempt %d): %s", path, attempt + 1, exc)
                last_exc = exc
        raise RuntimeError(
            f"Immich request failed after retries: {path}"
        ) from last_exc

    def find_album_by_name(self, name: str) -> dict | None:
        resp = self._get("/api/albums")
        albums = resp.json()
        for album in albums:
            if album.get("albumName") == name:
                return album
        return None

    def get_album(self, album_id: str) -> dict:
        resp = self._get(f"/api/albums/{album_id}")
        return resp.json()

    def download_asset(self, asset_id: str, dest_path: str) -> None:
        resp = self._get(f"/api/assets/{asset_id}/original", stream=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
