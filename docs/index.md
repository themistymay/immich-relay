---
layout: default
title: immich-relay
---

# immich-relay

Syncs curated Immich albums to Google Photos albums for family displays (Google Home, Chromecast, etc.). Immich is the system of record — deletions flow one way, from Immich to Google Photos.

---

## How It Works

1. On each sync cycle, the service checks every configured album pair for changes (using Immich's `updatedAt` timestamp).
2. New assets are downloaded from Immich and uploaded to Google Photos.
3. Assets removed from Immich are removed from the Google Photos album.
4. Multiple Immich albums can be merged into a single Google Photos album.
5. State is persisted to `data/sync_state.json` so restarts pick up where they left off.

---

## Source

[github.com/themistymay/immich-relay](https://github.com/themistymay/immich-relay)

---

## Legal

- [Privacy Policy](privacy)
- [Terms of Service](terms)
