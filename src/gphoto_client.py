import sys

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logger import get_logger

log = get_logger("gphoto_client")

_GPHOTOS_BASE = "https://photoslibrary.googleapis.com/v1"
_BATCH_LIMIT = 50


class GPhotoClient:
    def __init__(self, credentials: Credentials, token_manager=None):
        self._creds = credentials
        self._token_manager = token_manager
        self._session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist={429, 500, 502, 503, 504},
            respect_retry_after_header=True,
            allowed_methods=False,  # retry all HTTP methods, including POST
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    def _refresh_auth(self) -> None:
        if self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(GoogleRequest())

    def _headers(self) -> dict:
        self._refresh_auth()
        return {"Authorization": f"Bearer {self._creds.token}"}

    def _get(self, path: str, **kwargs) -> requests.Response:
        resp = self._session.get(
            f"{_GPHOTOS_BASE}{path}", headers=self._headers(), timeout=30, **kwargs
        )
        self._check_response(resp, path)
        return resp

    def _post(self, path: str, **kwargs) -> requests.Response:
        resp = self._session.post(
            f"{_GPHOTOS_BASE}{path}", headers=self._headers(), timeout=60, **kwargs
        )
        self._check_response(resp, path)
        return resp

    def _check_response(self, resp: requests.Response, context: str) -> None:
        if resp.status_code == 403:
            if self._token_manager:
                self._token_manager.handle_403(context, resp)
            else:
                log.critical(
                    "403 from Google Photos (%s). Possible causes: "
                    "(1) token was generated with wrong or missing scopes — re-run oauth_setup.py; "
                    "(2) Photos Library API is not enabled in Google Cloud Console; "
                    "(3) your Google account is not added as a test user on the OAuth consent screen.",
                    context
                )
                sys.exit(1)
        resp.raise_for_status()

    # ── Album operations ──────────────────────────────────────────────────────

    def find_album_by_name(self, name: str) -> dict | None:
        page_token = None
        while True:
            params = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token
            resp = self._get("/albums", params=params)
            data = resp.json()
            for album in data.get("albums", []):
                if album.get("title") == name:
                    return album
            page_token = data.get("nextPageToken")
            if not page_token:
                return None

    def create_album(self, title: str) -> dict:
        resp = self._post("/albums", json={"album": {"title": title}})
        album = resp.json()
        self.enforce_album_not_shared(album["id"])
        return album

    def get_or_create_album(self, title: str) -> dict:
        album = self.find_album_by_name(title)
        if album is None:
            log.info("Creating Google Photos album: %s", title)
            album = self.create_album(title)
        else:
            self.enforce_album_not_shared(album["id"])
        return album

    def enforce_album_not_shared(self, album_id: str) -> None:
        resp = self._get(f"/albums/{album_id}")
        album = resp.json()
        share_info = album.get("shareInfo", {})
        if share_info.get("isShared", False) or share_info.get("shareableUrl"):
            log.critical(
                "Album %s has sharing enabled — sync aborted. "
                "Evaluate and unshare manually before restarting.", album_id
            )
            raise RuntimeError(f"Album {album_id} is shared — sync aborted.")

    def get_album_media_item_ids(self, album_id: str) -> set[str]:
        item_ids: set[str] = set()
        page_token = None
        while True:
            body: dict = {"albumId": album_id, "pageSize": 100}
            if page_token:
                body["pageToken"] = page_token
            resp = self._post("/mediaItems:search", json=body)
            data = resp.json()
            for item in data.get("mediaItems", []):
                item_ids.add(item["id"])
            page_token = data.get("nextPageToken")
            if not page_token:
                return item_ids

    # ── Media item operations ─────────────────────────────────────────────────

    def upload_media_item(self, file_path: str, filename: str) -> str:
        upload_url = f"{_GPHOTOS_BASE.replace('/v1', '')}/v1/uploads"

        self._refresh_auth()
        headers = {
            "Authorization": f"Bearer {self._creds.token}",
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": "image/jpeg",
            "X-Goog-Upload-Protocol": "raw",
        }

        with open(file_path, "rb") as f:
            resp = self._session.post(upload_url, data=f, headers=headers, timeout=120)
        if resp.status_code == 403:
            if self._token_manager:
                self._token_manager.handle_403(f"/v1/uploads: {resp.text}")
        resp.raise_for_status()
        upload_token = resp.text.strip()

        create_resp = self._post(
            "/mediaItems:batchCreate",
            json={
                "newMediaItems": [
                    {
                        "description": "",
                        "simpleMediaItem": {
                            "fileName": filename,
                            "uploadToken": upload_token,
                        },
                    }
                ]
            },
        )
        result = create_resp.json()
        item_result = result["newMediaItemResults"][0]
        status = item_result.get("status", {})
        if status.get("code", 0) != 0:
            raise RuntimeError(
                f"batchCreate failed for {filename}: {status.get('message')}"
            )
        return item_result["mediaItem"]["id"]

    def add_to_album(self, album_id: str, media_item_ids: list[str]) -> None:
        if not media_item_ids:
            return
        for chunk in _chunks(media_item_ids, _BATCH_LIMIT):
            self._post(
                f"/albums/{album_id}:batchAddMediaItems",
                json={"mediaItemIds": chunk},
            )

    def remove_from_album(self, album_id: str, media_item_ids: list[str]) -> None:
        if not media_item_ids:
            return
        for chunk in _chunks(media_item_ids, _BATCH_LIMIT):
            self._post(
                f"/albums/{album_id}:batchRemoveMediaItems",
                json={"mediaItemIds": chunk},
            )



def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
