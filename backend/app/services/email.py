"""Send email via Resend (production) or plain SMTP to Mailpit (local dev)."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


async def send_email(to: str, subject: str, text: str, html: str) -> bool:
    s = get_settings()
    if s.resend_api_key:
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {s.resend_api_key}"},
                json={"from": s.email_from, "to": [to], "subject": subject, "text": text, "html": html},
            )
        if resp.is_error:
            log.error("Resend failed (%s): %s", resp.status_code, resp.text[:300])
        return not resp.is_error

    if s.smtp_host:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.email_from, to, subject
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        def _send() -> None:
            with smtplib.SMTP(s.smtp_host, s.smtp_port) as smtp:
                smtp.send_message(msg)

        # smtplib is blocking; run it in a thread so we don't stall the event loop.
        await asyncio.to_thread(_send)
        return True

    log.warning("No email transport configured; skipping email to %s", to)
    return False
