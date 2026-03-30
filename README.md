# immich-relay

Syncs curated Immich albums to Google Photos albums for family display (Google Home, etc.). Immich is the system of record — deletions flow one way, from Immich to Google Photos.

---

## How It Works

1. On each sync cycle, the service checks every configured album pair for changes (using Immich's `updatedAt` timestamp).
2. New assets are downloaded from Immich and uploaded to Google Photos.
3. Assets removed from Immich are removed from the Google Photos album.
4. Multiple Immich albums can be merged into a single Google Photos album.
5. State is persisted to `data/sync_state.json` so restarts pick up where they left off.

---

## Prerequisites

- Docker and Docker Compose
- An Immich instance with an API key
- A Google account and a Google Cloud project

---

## Setup

### 1. Clone and create the data directory

```sh
git clone <repo-url> immich-relay
cd immich-relay
mkdir -p ./data && chmod 700 ./data
```

### 2. Configure environment variables

```sh
cp .env.example .env
```

Edit `.env`:

| Variable | Required | Description |
|---|---|---|
| `IMMICH_BASE_URL` | yes | Base URL of your Immich instance (e.g. `https://immich.example.com`) |
| `IMMICH_API_KEY` | yes | Immich API key (see [Immich API Key](#immich-api-key) below) |
| `GPHOTO_TOKEN_PATH` | no | Path inside the container where `token.json` is stored (default: `/data/token.json`) |
| `OAUTH_REDIRECT_PORT` | no | Port used during the one-time OAuth setup (default: `8080`) |
| `CACHE_DIR` | no | Ephemeral download cache directory (default: `/tmp/sync_cache`) |
| `LOG_LEVEL` | no | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |

> `SYNC_INTERVAL_SECONDS`, `SYNC_FULL_INTERVAL_SECONDS`, and `SYNC_DOWNLOAD_WORKERS` can also be set via env var but are preferably configured in `config.json` (see below).

### 3. Configure album mappings

```sh
cp config.json.example config.json
```

Edit `config.json`:

| Key | Required | Default | Description |
|---|---|---|---|
| `mappings` | yes | — | List of album mapping objects |
| `mappings[].immich` | yes | — | One or more Immich album names to merge into the Google Photos album |
| `mappings[].gphoto` | yes | — | Google Photos album name to sync into |
| `sync_interval_seconds` | no | `300` | How often to poll for changes (seconds) |
| `sync_full_interval_seconds` | no | `3600` | How often to force a full re-sync regardless of `updatedAt` (seconds) |
| `download_workers` | no | `4` | Number of parallel download threads per sync cycle |

Example:

```json
{
  "sync_interval_seconds": 300,
  "sync_full_interval_seconds": 3600,
  "download_workers": 4,
  "mappings": [
    {
      "immich": ["Share - Both Families", "Share - May Family"],
      "gphoto": "Share - May Family"
    }
  ]
}
```

### 4. Set up Google Cloud Console

You need a Google Cloud project with the Photos Library API enabled and an OAuth 2.0 client to authorize the service.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create or select a project.
2. Navigate to **APIs & Services → Library**, search for **Photos Library API**, and enable it.
3. Navigate to **APIs & Services → OAuth consent screen**:
   - Choose **External** user type.
   - Fill in the app name and your email.
   - Under **Scopes**, add the following three scopes:
     - `/auth/photoslibrary.appendonly`
     - `/auth/photoslibrary.edit.appcreateddata`
     - `/auth/photoslibrary.readonly.appcreateddata`
   - Under **Test users**, add the Google account that owns the target Google Photos library.
4. Navigate to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**:
   - Application type: **Desktop app**
   - Under **Authorized redirect URIs**, add: `http://localhost:8080/`
5. Click **Download JSON** and save the file as `client_secrets.json` in the project root.

> `client_secrets.json` is only needed during the one-time OAuth setup step. Do not commit it.

### 5. Build the image

```sh
docker compose build
```

### 6. OAuth setup (generates token.json)

This step authorizes the service to access your Google Photos account. The token is persisted to `data/token.json` and refreshed automatically at runtime. If you are in 
testing mode in the Google Cloud project, the refresh token is only valid for 7 days.

```sh
docker compose run --rm -it \
  -p 8080:8080 \
  -v ${PWD}/client_secrets.json:/app/client_secrets.json:ro \
  --entrypoint python \
  immich-relay /app/src/oauth_setup.py
```

Click or copy the URL printed to the terminal and open it in your browser. After authorizing, the token is written to `data/token.json`. You should see:

```
[oauth_setup] Token written to /data/token.json
[oauth_setup] Done. You can now start the sync service.
```

> `client_secrets.json` is not needed after this step and does not need to be present when the service runs normally.

### 7. Start the service

```sh
docker compose up -d
docker compose logs -f
```

---

## Immich API Key

When creating the API key in Immich (**Account Settings → API Keys**), grant only these two permissions:

| Permission | Why |
|---|---|
| `album.read` | List albums, fetch membership and `updatedAt` for change detection |
| `asset.download` | Download original files for upload to Google Photos |

All other permissions should be left unchecked. The service is structurally read-only and never modifies Immich.

---

## Resetting State

Deleting `data/sync_state.json` causes the next sync cycle to treat all album pairs as new and perform a full re-sync. This is safe — no data is lost; the service will re-upload any assets not already in Google Photos.
