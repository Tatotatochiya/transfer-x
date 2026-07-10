"""TRA-44 — email delivery for high-value notification types.

Uses stdlib smtplib (blocking) run in a worker thread so it never blocks the
event loop; callers fire this as `asyncio.create_task(...)` and don't await
the result. If SMTP isn't configured (no SMTP_HOST), sends are skipped —
this is the expected state for local/dev environments.
"""

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.notifications.models import NotificationType

logger = logging.getLogger(__name__)

# Curated per TRA-44/76 — not every notification type warrants an email.
EMAIL_ENABLED_TYPES = {
    NotificationType.OFFER_RECEIVED,
    NotificationType.OFFER_ACCEPTED,
    NotificationType.OFFER_REJECTED,
    NotificationType.DEAL_COMPLETED,
    NotificationType.OFFER_EXPIRING,
    NotificationType.AUCTION_ENDING,
    NotificationType.REPRESENTATION_STARTED,
    NotificationType.INSTALMENT_DUE,
    NotificationType.DEAL_CLAUSE_TRIGGERED,
}


def _render_html(message: str, link: str | None) -> str:
    button = (
        f'<a href="{link}" style="display:inline-block;margin-top:20px;padding:10px 20px;'
        f'background:#10b981;color:#ffffff;text-decoration:none;border-radius:8px;'
        f'font-weight:600;">View in TransferX</a>'
        if link else ""
    )
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f4f5;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;">
            <tr>
              <td style="background:#0f172a;padding:20px 28px;">
                <span style="color:#10b981;font-size:18px;font-weight:700;">TransferX</span>
              </td>
            </tr>
            <tr>
              <td style="padding:28px;">
                <p style="margin:0;color:#0f172a;font-size:15px;line-height:1.6;">{message}</p>
                {button}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;border-top:1px solid #e5e7eb;">
                <p style="margin:0;color:#9ca3af;font-size:12px;">
                  You're receiving this because of your TransferX notification preferences.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _send_sync(to_email: str, subject: str, html_body: str) -> None:
    if not settings.smtp_host:
        logger.info("SMTP not configured — skipping email to %s (%s)", to_email, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password or "")
        server.send_message(msg)


async def send_staff_invitation_email(
    to_email: str, club_name: str, role: str, accept_url: str
) -> None:
    """TRA-86: fire-and-forget invitation email. No-ops without SMTP_HOST —
    the create response returns the accept URL once so the owner can share it
    manually in dev (D6). Never logs the URL (it embeds the raw token)."""
    try:
        message = (
            f"{club_name} has invited you to join their TransferX team as "
            f"{role.replace('_', ' ').title()}. The link expires in 7 days."
        )
        html = _render_html(message, accept_url)
        await asyncio.to_thread(
            _send_sync, to_email, f"TransferX — {club_name} team invitation", html
        )
    except Exception:
        logger.exception("Failed to send staff invitation email")


async def maybe_send_notification_email(
    recipient_user_id: uuid.UUID,
    type_: NotificationType,
    message: str,
    link: str | None,
) -> None:
    """Fire-and-forget email send. Opens its own DB session — must not share
    a session with the caller's request-scoped transaction."""
    if type_ not in EMAIL_ENABLED_TYPES:
        return

    try:
        from sqlalchemy import select

        from app.auth.models import User
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User.email).where(User.id == recipient_user_id))
            to_email = result.scalar_one_or_none()

        if not to_email:
            return

        full_link = f"{settings.frontend_base_url}{link}" if link else None
        html = _render_html(message, full_link)
        await asyncio.to_thread(_send_sync, to_email, f"TransferX — {message}", html)
    except Exception:
        logger.exception("Failed to send notification email to user %s", recipient_user_id)
