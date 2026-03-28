from __future__ import annotations

import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agent1.config import get_settings  # noqa: E402
from agent1.tools.calendar_tool import GOOGLE_CALENDAR_SCOPES  # noqa: E402


def main() -> None:
    settings = get_settings()
    creds_path = settings.google_calendar_credentials_path
    token_path = settings.google_calendar_token_path

    if not creds_path.exists():
        raise FileNotFoundError(
            f"Missing credentials file: {creds_path}\n"
            "Download OAuth client JSON from Google Cloud Console and place it there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GOOGLE_CALENDAR_SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved Google Calendar token to: {token_path}")


if __name__ == "__main__":
    main()

