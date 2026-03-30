import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from config import SCOPES

secrets_file = os.environ.get("CLIENT_SECRETS_PATH", "client_secrets.json")
if not os.path.exists(secrets_file):
    print(f"[oauth_setup] ERROR: client_secrets.json not found at {secrets_file}")
    print("[oauth_setup] Mount it into the container with -v ./client_secrets.json:/app/client_secrets.json:ro")
    sys.exit(1)

port = int(os.environ.get("OAUTH_REDIRECT_PORT", 8080))

flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)

print("[oauth_setup] Open this URL in your browser:")
print("[oauth_setup] (URL will appear below after the flow starts)")
print()

creds = flow.run_local_server(
    host="localhost",
    bind_addr="0.0.0.0",
    port=port,
    open_browser=False,
    prompt="consent",
)

token_path = os.environ.get("GPHOTO_TOKEN_PATH", "/data/token.json")
with open(token_path, "w") as f:
    f.write(creds.to_json())
os.chmod(token_path, 0o600)

print(f"[oauth_setup] Token written to {token_path}")
print("[oauth_setup] Done. You can now start the sync service.")
