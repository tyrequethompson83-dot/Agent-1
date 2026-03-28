from __future__ import annotations

import email
import hashlib
import imaplib
import logging
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from email.policy import default as default_policy

from agent1.config import Settings
from agent1.tools.approval import ApprovalManager

logger = logging.getLogger("agent1.tools")


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    chunks = decode_header(raw)
    parts: list[str] = []
    for value, charset in chunks:
        if isinstance(value, bytes):
            parts.append(value.decode(charset or "utf-8", errors="ignore"))
        else:
            parts.append(value)
    return "".join(parts)


def _extract_text_body(message: email.message.EmailMessage) -> str:
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition.lower():
                try:
                    return part.get_content().strip()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(part.get_content_charset() or "utf-8", errors="ignore").strip()
        return ""
    try:
        return message.get_content().strip()
    except Exception:
        payload = message.get_payload(decode=True) or b""
        return payload.decode(message.get_content_charset() or "utf-8", errors="ignore").strip()


class EmailTool:
    def __init__(self, settings: Settings, approvals: ApprovalManager):
        self.settings = settings
        self.approvals = approvals

    def _is_ready(self) -> tuple[bool, str]:
        if not self.settings.email_enabled:
            return False, "Email is disabled. Set EMAIL_ENABLED=true."
        required = [
            self.settings.email_address,
            self.settings.email_password,
            self.settings.email_imap_host,
            self.settings.email_smtp_host,
        ]
        if not all(required):
            return False, "Email is not configured. Check EMAIL_* values in .env."
        return True, ""

    def read_recent(self, user_id: str, limit: int = 5) -> str:
        logger.info("tool=read_recent_emails user=%s limit=%s", user_id, limit)
        ready, message = self._is_ready()
        if not ready:
            return message

        limit = max(1, min(limit, 20))
        try:
            client = imaplib.IMAP4_SSL(self.settings.email_imap_host, self.settings.email_imap_port)
            client.login(self.settings.email_address, self.settings.email_password)
            client.select(self.settings.email_mailbox)
            status, data = client.search(None, "ALL")
            if status != "OK":
                client.logout()
                return "Failed to read mailbox."

            ids = data[0].split()[-limit:]
            rows: list[str] = []
            for msg_id in reversed(ids):
                status, packet = client.fetch(msg_id, "(RFC822)")
                if status != "OK" or not packet or not packet[0]:
                    continue
                raw_bytes = packet[0][1]
                msg = email.message_from_bytes(raw_bytes, policy=default_policy)
                sender = _decode_header_value(msg.get("From"))
                subject = _decode_header_value(msg.get("Subject"))
                body = _extract_text_body(msg)
                rows.append(
                    f"From: {sender}\nSubject: {subject}\nBody: {body[:600] or '[empty]'}"
                )
            client.logout()
            return "\n\n---\n\n".join(rows) if rows else "No recent emails found."
        except Exception as exc:
            return f"Email read failed: {exc}"

    def send_email(self, user_id: str, to: str, subject: str, body: str) -> str:
        logger.info("tool=send_email user=%s to=%s subject=%s", user_id, to, subject)
        ready, message = self._is_ready()
        if not ready:
            return message

        payload = {
            "to": to.strip(),
            "subject": subject.strip(),
            "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        }
        if not self.settings.auto_approve_risky_actions:
            if not self.approvals.consume_if_approved("send_email", payload):
                approval = self.approvals.request_approval(
                    action_type="send_email",
                    payload=payload,
                    requested_by=user_id,
                    reason="Outbound email send",
                )
                if approval.status == "denied":
                    return (
                        "DENIED: Email send rejected by approval policy.\n"
                        f"Request id: `{approval.id}`. Use `/approve {approval.id}` to override."
                    )
                if approval.status != "approved":
                    return (
                        "APPROVAL_REQUIRED: Email send blocked pending approval.\n"
                        f"Use `/approve {approval.id}` in Telegram, then re-send the request."
                    )

        msg = EmailMessage()
        msg["From"] = self.settings.email_address
        msg["To"] = to.strip()
        msg["Subject"] = subject.strip()
        msg.set_content(body)

        try:
            if self.settings.email_smtp_use_starttls:
                smtp = smtplib.SMTP(self.settings.email_smtp_host, self.settings.email_smtp_port, timeout=20)
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            else:
                smtp = smtplib.SMTP_SSL(self.settings.email_smtp_host, self.settings.email_smtp_port, timeout=20)
            smtp.login(self.settings.email_address, self.settings.email_password)
            smtp.send_message(msg)
            smtp.quit()
            return "Email sent."
        except Exception as exc:
            return f"Email send failed: {exc}"
