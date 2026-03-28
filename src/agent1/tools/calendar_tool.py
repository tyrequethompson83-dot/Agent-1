from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from agent1.config import Settings
from agent1.tools.approval import ApprovalManager

logger = logging.getLogger("agent1.tools")

GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarTool:
    def __init__(self, settings: Settings, approvals: ApprovalManager):
        self.settings = settings
        self.approvals = approvals

    def _is_enabled(self) -> tuple[bool, str]:
        if not self.settings.calendar_enabled:
            return False, "Calendar is disabled. Set CALENDAR_ENABLED=true."
        return True, ""

    def _service(self):
        token_path = self.settings.google_calendar_token_path
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), GOOGLE_CALENDAR_SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")

        if not creds or not creds.valid:
            return None, (
                "Google Calendar is not authenticated yet. "
                "Run `python scripts/setup_google_calendar.py` first."
            )

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return service, ""

    def list_upcoming(self, user_id: str, max_results: int = 10) -> str:
        logger.info("tool=list_upcoming_events user=%s limit=%s", user_id, max_results)
        enabled, message = self._is_enabled()
        if not enabled:
            return message

        service, error = self._service()
        if not service:
            return error

        max_results = max(1, min(max_results, 20))
        now = datetime.now(timezone.utc).isoformat()
        try:
            event_result = (
                service.events()
                .list(
                    calendarId=self.settings.google_calendar_id,
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except Exception as exc:
            return f"Calendar read failed: {exc}"

        events = event_result.get("items", [])
        if not events:
            return "No upcoming events."

        lines = []
        for item in events:
            start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date", ""))
            summary = item.get("summary", "(no title)")
            lines.append(f"- {start} | {summary}")
        return "\n".join(lines)

    def create_event(
        self,
        user_id: str,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
        timezone_name: str = "UTC",
    ) -> str:
        logger.info("tool=create_calendar_event user=%s summary=%s", user_id, summary)
        enabled, message = self._is_enabled()
        if not enabled:
            return message

        payload = {
            "summary": summary.strip(),
            "start_iso": start_iso.strip(),
            "end_iso": end_iso.strip(),
            "description_sha256": hashlib.sha256(description.encode("utf-8")).hexdigest(),
            "timezone_name": timezone_name.strip(),
        }
        if not self.settings.auto_approve_risky_actions:
            if not self.approvals.consume_if_approved("calendar_create", payload):
                approval = self.approvals.request_approval(
                    action_type="calendar_create",
                    payload=payload,
                    requested_by=user_id,
                    reason="Calendar event creation",
                )
                if approval.status == "denied":
                    return (
                        "DENIED: Calendar event creation rejected by approval policy.\n"
                        f"Request id: `{approval.id}`. Use `/approve {approval.id}` to override."
                    )
                if approval.status != "approved":
                    return (
                        "APPROVAL_REQUIRED: Calendar event creation blocked pending approval.\n"
                        f"Use `/approve {approval.id}` in Telegram, then re-send the request."
                    )

        service, error = self._service()
        if not service:
            return error

        event_body = {
            "summary": summary.strip(),
            "description": description.strip(),
            "start": {"dateTime": start_iso.strip(), "timeZone": timezone_name.strip()},
            "end": {"dateTime": end_iso.strip(), "timeZone": timezone_name.strip()},
        }
        try:
            event = service.events().insert(calendarId=self.settings.google_calendar_id, body=event_body).execute()
        except Exception as exc:
            return f"Calendar create failed: {exc}"
        return f"Event created: {event.get('htmlLink', 'no link returned')}"
