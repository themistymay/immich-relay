import os
import sys
from datetime import datetime, timedelta

import requests

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from logger import get_logger
from config import SCOPES

log = get_logger("token_manager")


class TokenManager:
    def __init__(self, token_path: str):
        self._token_path = token_path
        self._credentials: Credentials | None = None

    def load(self) -> Credentials:
        if not os.path.exists(self._token_path):
            log.critical(
                "Token file not found at %s — run oauth_setup.py to generate it.",
                self._token_path,
            )
            sys.exit(1)

        try:
            self._credentials = Credentials.from_authorized_user_file(
                self._token_path, SCOPES
            )
        except Exception as exc:
            log.critical("Failed to load token file: %s", exc)
            sys.exit(1)

        self._refresh_if_needed()
        return self._credentials

    def get_credentials(self) -> Credentials:
        if self._credentials is None:
            return self.load()
        self._refresh_if_needed()
        return self._credentials

    def handle_403(self, context: str, resp: requests.Response) -> None:
        log.critical(f"{context}: {resp.json()}")
        sys.exit(1)

    def _refresh_if_needed(self) -> None:
        creds = self._credentials
        if creds is None:
            return

        needs_refresh = (
            not creds.valid
            or (
                creds.expiry is not None
                and creds.expiry - datetime.utcnow() < timedelta(minutes=5)
            )
        )

        if needs_refresh:
            if not creds.refresh_token:
                log.critical(
                    "Credentials have no refresh token — re-run oauth_setup.py."
                )
                sys.exit(1)
            log.debug("Refreshing Google OAuth token.")
            try:
                creds.refresh(Request())
            except Exception as exc:
                log.critical("Failed to refresh Google OAuth token: %s", exc)
                sys.exit(1)
            self._persist()

    def _persist(self) -> None:
        tmp_path = self._token_path + ".tmp"
        try:
            with open(tmp_path, "w") as f:
                f.write(self._credentials.to_json())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._token_path)
        except Exception as exc:
            log.error("Failed to persist refreshed token: %s", exc)
