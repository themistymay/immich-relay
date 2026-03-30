import json
import os

from logger import get_logger

log = get_logger("state_manager")

SCHEMA_VERSION = 1


class StateManager:
    def __init__(self, state_path: str):
        self._state_path = state_path
        self._state: dict = {}

    def load(self) -> None:
        if not os.path.exists(self._state_path):
            log.info("No state file found at %s — starting fresh.", self._state_path)
            self._state = {"schema_version": SCHEMA_VERSION, "albums": [], "assets": {}}
            return

        with open(self._state_path) as f:
            self._state = json.load(f)

        if "schema_version" not in self._state:
            self._state["schema_version"] = SCHEMA_VERSION
        if "albums" not in self._state:
            self._state["albums"] = []
        if "assets" not in self._state:
            self._state["assets"] = {}

        log.info("State loaded: %d albums, %d assets tracked.",
                 len(self._state["albums"]), len(self._state["assets"]))

    def save(self) -> None:
        tmp_path = self._state_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(self._state, f, indent=2)
        os.replace(tmp_path, self._state_path)

    # ── Ensure albums list is long enough ────────────────────────────────────

    def _ensure_pair(self, index: int) -> None:
        while len(self._state["albums"]) <= index:
            self._state["albums"].append({
                "immich_album_id": None,
                "gphoto_album_id": None,
                "last_album_updated_at": None,
            })

    # ── Per-pair album ID tracking ────────────────────────────────────────────

    def get_immich_album_id(self, index: int) -> str | None:
        if index >= len(self._state["albums"]):
            return None
        return self._state["albums"][index].get("immich_album_id")

    def set_immich_album_id(self, index: int, album_id: str) -> None:
        self._ensure_pair(index)
        self._state["albums"][index]["immich_album_id"] = album_id

    def get_gphoto_album_id(self, index: int) -> str | None:
        if index >= len(self._state["albums"]):
            return None
        return self._state["albums"][index].get("gphoto_album_id")

    def set_gphoto_album_id(self, index: int, album_id: str) -> None:
        self._ensure_pair(index)
        self._state["albums"][index]["gphoto_album_id"] = album_id

    # ── Asset state ───────────────────────────────────────────────────────────

    def get_synced_asset_ids_for_pair(self, pair_index: int) -> set[str]:
        return {
            asset_id
            for asset_id, entry in self._state["assets"].items()
            if pair_index in entry.get("albums", [])
        }

    def get_gphoto_media_item_id(self, immich_asset_id: str) -> str | None:
        entry = self._state["assets"].get(immich_asset_id)
        if entry is None:
            return None
        return entry.get("gphoto_media_item_id")

    def is_uploaded(self, immich_asset_id: str) -> bool:
        return self.get_gphoto_media_item_id(immich_asset_id) is not None

    def record_synced(self, immich_asset_id: str, gphoto_media_item_id: str,
                      filename: str, pair_index: int) -> None:
        assets = self._state["assets"]
        if immich_asset_id in assets:
            entry = assets[immich_asset_id]
            if pair_index not in entry["albums"]:
                entry["albums"].append(pair_index)
        else:
            from datetime import datetime, timezone
            assets[immich_asset_id] = {
                "gphoto_media_item_id": gphoto_media_item_id,
                "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "filename": filename,
                "albums": [pair_index],
                "keep_hint": False,
                "favorited_at": None,
            }

    def record_removed_from_pair(self, immich_asset_id: str, pair_index: int) -> None:
        entry = self._state["assets"].get(immich_asset_id)
        if entry is None:
            return
        entry["albums"] = [i for i in entry["albums"] if i != pair_index]
        if not entry["albums"]:
            del self._state["assets"][immich_asset_id]

    def is_in_any_pair(self, immich_asset_id: str) -> bool:
        entry = self._state["assets"].get(immich_asset_id)
        if entry is None:
            return False
        return bool(entry.get("albums"))

    def set_keep_hint(self, immich_asset_id: str, favorited_at: str) -> None:
        entry = self._state["assets"].get(immich_asset_id)
        if entry is None:
            return
        entry["keep_hint"] = True
        if entry.get("favorited_at") is None:
            entry["favorited_at"] = favorited_at

    # ── Change detection ──────────────────────────────────────────────────────

    def get_last_album_updated_at(self, pair_index: int) -> str | None:
        if pair_index >= len(self._state["albums"]):
            return None
        return self._state["albums"][pair_index].get("last_album_updated_at")

    def set_last_album_updated_at(self, pair_index: int, updated_at: str) -> None:
        self._ensure_pair(pair_index)
        self._state["albums"][pair_index]["last_album_updated_at"] = updated_at
