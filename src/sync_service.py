import json
import os
import sys
import signal
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from dotenv import load_dotenv

from logger import get_logger
from token_manager import TokenManager
from immich_client import ImmichClient
from gphoto_client import GPhotoClient
from cache_manager import CacheManager
from state_manager import StateManager

load_dotenv()
log = get_logger("sync")


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        log.warning("Invalid value for %s: %r — using default %d", name, val, default)
        return default


def _load_config(config_path: str) -> tuple[list[dict], dict]:
    with open(config_path) as f:
        config = json.load(f)
    mappings = config.get("mappings", [])
    if not mappings:
        log.error("config.json has no mappings — nothing to sync.")
        sys.exit(1)
    settings = {
        "sync_interval_seconds": config.get("sync_interval_seconds"),
        "sync_full_interval_seconds": config.get("sync_full_interval_seconds"),
        "download_workers": config.get("download_workers"),
    }
    return mappings, settings


def _flatten_pairs(mappings: list[dict]) -> list[tuple[str, str]]:
    """Expand each mapping's immich list into individual (immich_name, gphoto_name) pairs."""
    pairs = []
    for mapping in mappings:
        gphoto_name = mapping["gphoto"]
        for immich_name in mapping["immich"]:
            pairs.append((immich_name, gphoto_name))
    return pairs


def run_sync_cycle(
    pairs: list[tuple[str, str]],
    immich: ImmichClient,
    gphoto: GPhotoClient,
    cache: CacheManager,
    state: StateManager,
    force_full: bool,
    download_workers: int,
) -> dict:
    t_start = time.monotonic()
    counters = {
        "pairs": len(pairs),
        "pairs_skipped": 0,
        "uploaded": 0,
        "reused": 0,
        "removed": 0,
        "readded": 0,
        "errors": 0,
    }

    try:
        for i, (immich_name, gphoto_name) in enumerate(pairs):
            try:
                _sync_pair(
                    pair_index=i,
                    immich_name=immich_name,
                    gphoto_name=gphoto_name,
                    immich=immich,
                    gphoto=gphoto,
                    cache=cache,
                    state=state,
                    force_full=force_full,
                    download_workers=download_workers,
                    counters=counters,
                )
            except Exception:
                log.error(
                    "Error syncing pair %d (%s → %s):\n%s",
                    i, immich_name, gphoto_name, traceback.format_exc(),
                )
                counters["errors"] += 1

        state.save()
        cache.assert_empty()

    except Exception:
        cache.purge_all()
        log.critical("Unhandled exception in sync cycle:\n%s", traceback.format_exc())
        try:
            state.save()
        except Exception:
            pass
        raise

    counters["duration_s"] = round(time.monotonic() - t_start, 2)
    counters["forced_full"] = force_full
    log.info(
        "Sync cycle complete: pairs=%(pairs)d skipped=%(pairs_skipped)d "
        "uploaded=%(uploaded)d reused=%(reused)d removed=%(removed)d "
        "readded=%(readded)d errors=%(errors)d duration_s=%(duration_s).2f",
        counters,
    )
    return counters


def _sync_pair(
    pair_index: int,
    immich_name: str,
    gphoto_name: str,
    immich: ImmichClient,
    gphoto: GPhotoClient,
    cache: CacheManager,
    state: StateManager,
    force_full: bool,
    download_workers: int,
    counters: dict,
) -> None:
    # RESOLVE ALBUMS
    immich_album = immich.find_album_by_name(immich_name)
    if immich_album is None:
        log.error("Pair %d: Immich album not found: %r — skipping.", pair_index, immich_name)
        counters["errors"] += 1
        return

    resolved_id = immich_album["id"]
    stored_id = state.get_immich_album_id(pair_index)
    if stored_id and stored_id != resolved_id:
        log.warning(
            "Pair %d: Immich album ID changed from %s to %s",
            pair_index, stored_id, resolved_id,
        )
    state.set_immich_album_id(pair_index, resolved_id)

    album_resource = immich.get_album(resolved_id)
    album_updated_at = album_resource.get("updatedAt", "")

    # CHANGE DETECTION
    if (
        not force_full
        and state.get_last_album_updated_at(pair_index) == album_updated_at
    ):
        log.debug("Pair %d: no Immich changes (updatedAt unchanged), skipping.", pair_index)
        counters["pairs_skipped"] += 1
        return

    # RESOLVE GOOGLE ALBUM
    gphoto_album = gphoto.get_or_create_album(gphoto_name)
    gphoto_album_id = gphoto_album["id"]
    state.set_gphoto_album_id(pair_index, gphoto_album_id)

    # COMPUTE TRUTH SETS
    immich_assets = album_resource.get("assets", [])
    immich_current_ids: set[str] = {a["id"] for a in immich_assets}
    immich_asset_map: dict[str, dict] = {a["id"]: a for a in immich_assets}

    synced_ids = state.get_synced_asset_ids_for_pair(pair_index)
    gphoto_current_ids = gphoto.get_album_media_item_ids(gphoto_album_id)

    # COMPUTE DELTAS
    to_add = immich_current_ids - synced_ids
    to_remove = synced_ids - immich_current_ids
    to_readd = {
        asset_id for asset_id in synced_ids
        if state.get_gphoto_media_item_id(asset_id) not in gphoto_current_ids
    }

    # PROCESS REMOVALS
    collect_album_remove: list[str] = []

    for asset_id in to_remove:
        gphoto_id = state.get_gphoto_media_item_id(asset_id)
        if not gphoto_id:
            state.record_removed_from_pair(asset_id, pair_index)
            continue
        if gphoto_id in gphoto_current_ids:
            collect_album_remove.append(gphoto_id)
        state.record_removed_from_pair(asset_id, pair_index)

    gphoto.remove_from_album(gphoto_album_id, collect_album_remove)

    if collect_album_remove:
        log.info("Pair %d: removed %d from album.", pair_index, len(collect_album_remove))
    counters["removed"] += len(collect_album_remove)

    # PROCESS ADDITIONS
    need_upload = [aid for aid in to_add if not state.is_uploaded(aid)]
    already_have = [aid for aid in to_add if state.is_uploaded(aid)]

    pending_upload: dict[str, str] = {}

    def _upload_one(asset_id: str) -> tuple[str, str]:
        asset = immich_asset_map[asset_id]
        filename = asset.get("originalFileName", asset_id)
        dest_path = cache.asset_path(asset_id, filename)
        immich.download_asset(asset_id, dest_path)
        gphoto_id = gphoto.upload_media_item(dest_path, filename)
        cache.purge_file(dest_path)
        return asset_id, gphoto_id

    if need_upload:
        with ThreadPoolExecutor(max_workers=download_workers) as executor:
            futures = {executor.submit(_upload_one, aid): aid for aid in need_upload}
            for future in as_completed(futures):
                asset_id = futures[future]
                try:
                    aid, gid = future.result()
                    pending_upload[aid] = gid
                except Exception:
                    log.error(
                        "Pair %d: upload failed for asset %s:\n%s",
                        pair_index, asset_id, traceback.format_exc(),
                    )
                    counters["errors"] += 1

    all_new_gphoto_ids = list(pending_upload.values()) + [
        state.get_gphoto_media_item_id(aid) for aid in already_have
        if state.get_gphoto_media_item_id(aid)
    ]

    if all_new_gphoto_ids:
        gphoto.add_to_album(gphoto_album_id, all_new_gphoto_ids)

    for asset_id, gphoto_id in pending_upload.items():
        filename = immich_asset_map[asset_id].get("originalFileName", asset_id)
        state.record_synced(asset_id, gphoto_id, filename, pair_index)

    for asset_id in already_have:
        existing_gid = state.get_gphoto_media_item_id(asset_id)
        if existing_gid:
            filename = immich_asset_map[asset_id].get("originalFileName", asset_id)
            state.record_synced(asset_id, existing_gid, filename, pair_index)

    if to_add:
        log.info(
            "Pair %d: uploaded %d, reused %d from other pairs, added %d to album.",
            pair_index, len(pending_upload), len(already_have), len(all_new_gphoto_ids),
        )
    counters["uploaded"] += len(pending_upload)
    counters["reused"] += len(already_have)

    # PROCESS RE-ADDITIONS
    if to_readd:
        readd_gphoto_ids = [
            state.get_gphoto_media_item_id(aid)
            for aid in to_readd
            if state.get_gphoto_media_item_id(aid)
        ]
        if readd_gphoto_ids:
            gphoto.add_to_album(gphoto_album_id, readd_gphoto_ids)
            log.info("Pair %d: re-added %d assets removed from Google album.", pair_index, len(readd_gphoto_ids))
            counters["readded"] += len(readd_gphoto_ids)

    # RECORD CHANGE DETECTION CURSOR
    state.set_last_album_updated_at(pair_index, album_updated_at)


def main() -> None:
    log.info("immich-relay starting up.")

    config_path = os.environ.get("CONFIG_PATH", "/app/config.json")
    mappings, settings = _load_config(config_path)
    pairs = _flatten_pairs(mappings)

    sync_interval = settings["sync_interval_seconds"] or _env_int("SYNC_INTERVAL_SECONDS", 300)
    full_interval = settings["sync_full_interval_seconds"] or _env_int("SYNC_FULL_INTERVAL_SECONDS", 3600)
    download_workers = settings["download_workers"] or _env_int("SYNC_DOWNLOAD_WORKERS", 4)

    immich_base_url = os.environ["IMMICH_BASE_URL"]
    immich_api_key = os.environ["IMMICH_API_KEY"]
    token_path = os.environ.get("GPHOTO_TOKEN_PATH", "/data/token.json")
    cache_dir = os.environ.get("CACHE_DIR", "/tmp/sync_cache")
    state_path = os.environ.get("STATE_PATH", "/data/sync_state.json")

    token_mgr = TokenManager(token_path)
    creds = token_mgr.load()

    immich = ImmichClient(immich_base_url, immich_api_key)
    gphoto = GPhotoClient(creds, token_manager=token_mgr)
    cache = CacheManager(cache_dir)
    state = StateManager(state_path)
    state.load()

    _shutdown = threading.Event()

    def _handle_signal(signum, frame):
        log.info("Signal %d received — shutting down after current cycle.", signum)
        _shutdown.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info(
        "Service started.",
        extra={
            "interval_s": sync_interval,
            "full_interval_s": full_interval,
            "pairs": len(pairs),
        },
    )

    force_full = True
    last_full_sync_time = time.monotonic()

    while True:
        run_sync_cycle(
            pairs=pairs,
            immich=immich,
            gphoto=gphoto,
            cache=cache,
            state=state,
            force_full=force_full,
            download_workers=download_workers,
        )
        force_full = False

        if _shutdown.is_set():
            break

        _shutdown.wait(timeout=sync_interval)

        if _shutdown.is_set():
            break

        if time.monotonic() - last_full_sync_time >= full_interval:
            force_full = True
            last_full_sync_time = time.monotonic()

    log.info("Shutdown complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
