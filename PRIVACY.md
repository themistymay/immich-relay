# Privacy Policy

**Project:** immich-relay
**Repository:** https://github.com/themistymay/immich-relay
**Last updated:** 2026-03-30

---

## Overview

immich-relay is a self-hosted, open-source tool that synchronizes albums from an Immich instance to Google Photos. It runs entirely on infrastructure you own and control. The project maintainer does not operate any servers, does not collect any data, and has no visibility into how you use this software.

---

## Data the Developer Does NOT Collect

The maintainer of this project does not collect, receive, store, or process any of the following:

- Your photos, videos, or any media files
- Your Immich API key or server URL
- Your Google account credentials or OAuth tokens
- Metadata about your albums, assets, or sync activity
- Usage telemetry, crash reports, or analytics of any kind

There are no tracking pixels, remote logging endpoints, analytics SDKs, or any mechanism by which data leaves your environment and reaches the project maintainer.

---

## Data Processed Locally on Your Infrastructure

When you run immich-relay, it processes the following data entirely within your own environment:

| Data | Where it stays |
|---|---|
| Photos and videos downloaded from Immich | Temporary local cache (`/tmp/sync_cache` by default), deleted after upload |
| Immich API key | Your `.env` file and running container |
| Google OAuth token (`token.json`) | Your `data/` directory |
| Sync state (`sync_state.json`) | Your `data/` directory |

All of this data is under your sole control. You are responsible for securing it appropriately.

---

## Third-Party Services

immich-relay communicates with two external services **that you configure and authorize**:

- **Your Immich instance** — to read album and asset data. You control this server.
- **Google Photos API** — to upload media and manage albums in your Google account. This is governed by [Google's Privacy Policy](https://policies.google.com/privacy).

The tool requests only the minimum Google Photos OAuth scopes required to function:
- `photoslibrary.appendonly` — upload new media
- `photoslibrary.edit.appcreateddata` — remove media the app uploaded
- `photoslibrary.readonly.appcreateddata` — read media the app uploaded

No other Google account data is accessed.

---

## Children's Privacy

This software is a developer tool intended for personal self-hosted use. It does not target children and has no mechanism to collect data from any user, regardless of age.

---

## Changes to This Policy

If this policy is updated, the "Last updated" date at the top of this file will change. You can review the full history of changes in the [repository's commit log](https://github.com/themistymay/immich-relay/commits/main/PRIVACY.md).

---

## Contact

For questions or concerns, open an issue at https://github.com/themistymay/immich-relay/issues.
