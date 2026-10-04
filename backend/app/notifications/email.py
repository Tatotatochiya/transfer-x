"""TRA-44 — email delivery for high-value notification types.

Uses stdlib smtplib (blocking) run in a worker thread so it never blocks the
event loop; callers fire this as `asyncio.create_task(...)` and don't await
the result. If SMTP isn't configured (no SMTP_HOST), sends are skipped —
this is the expected state for local/dev environments.
"""

import asyncio
import html
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
    # Each of these puts the next move with the recipient, and a club that
    # visits a few times a week would otherwise not know until it looked.
    NotificationType.OFFER_COUNTERED,
    NotificationType.APPROVAL_REQUESTED,
    NotificationType.DEAL_PERSONAL_TERMS_SENT,
}


def _action_buttons(actions: list[tuple[str, str]] | None) -> str:
    """One-tap decisions (Lite L8): the first is the suggested one. Each
    opens a confirm page; nothing happens until the recipient confirms."""
    if not actions:
        return ""
    out = []
    for i, (label, url) in enumerate(actions):
        style = ("background:#2563eb;color:#ffffff;" if i == 0 else "background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;")
        out.append(
            f'<a href="{html.escape(url)}" style="display:inline-block;margin:12px 8px 0 0;padding:9px 16px;'
            f'{style}text-decoration:none;border-radius:8px;font-weight:600;font-size:14px;">{html.escape(label)}</a>'
        )
    return "<div>" + "".join(out) + "</div>"


def _render_html(message: str, link: str | None, actions: list[tuple[str, str]] | None = None) -> str:
    button = (
        f'<a href="{link}" style="display:inline-block;margin-top:20px;padding:10px 20px;'
        f'background:#10b981;color:#ffffff;text-decoration:none;border-radius:8px;'
        f'font-weight:600;">View in TransferX</a>'
        if link else ""
    )
    return _wrap(
        f'<p style="margin:0;color:#0f172a;font-size:15px;line-height:1.6;">{message}</p>'
        f"{_action_buttons(actions)}{button}"
    )


def render_digest_html(lines: list[tuple], dashboard_url: str, briefing: dict | None = None) -> str:
    """The daily digest: one row per thing waiting on the recipient, each
    linking straight to it. `lines` are (text, url). `briefing`, when the AI
    assistant is available, opens the email with the day's headline and the
    one thing to focus on."""
    # A line is (text, url) or (text, url, one-tap decision buttons).
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #eef0f3;">'
        f'<a href="{html.escape(line[1])}" style="color:#0f172a;text-decoration:none;font-size:14px;'
        f'line-height:1.5;">{html.escape(line[0])} &rarr;</a>'
        f"{_action_buttons(line[2] if len(line) > 2 else None)}</td></tr>"
        for line in lines
    )
    button = (
        f'<a href="{html.escape(dashboard_url)}" style="display:inline-block;margin-top:20px;'
        f'padding:10px 20px;background:#10b981;color:#ffffff;text-decoration:none;'
        f'border-radius:8px;font-weight:600;">Open your dashboard</a>'
    )
    intro = ""
    if briefing and briefing.get("headline"):
        intro = (
            f'<p style="margin:0 0 6px;color:#0f172a;font-size:15px;line-height:1.5;">{html.escape(briefing["headline"])}</p>'
            + (
                f'<p style="margin:0 0 20px;color:#334155;font-size:14px;line-height:1.5;">'
                f'<strong>Today&rsquo;s focus:</strong> {html.escape(briefing["focus"])}</p>'
                if briefing.get("focus") else ""
            )
        )
    return _wrap(
        intro
        + '<p style="margin:0 0 8px;color:#0f172a;font-size:15px;font-weight:600;">'
        "Waiting on you</p>"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
        f"{button}"
    )


def _wrap(inner_html: str) -> str:
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
                {inner_html}
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


async def send_player_invitation_email(to_email: str, player_name: str, inviter: str, accept_url: str) -> None:
    """Fire-and-forget player invitation. `inviter` is his club's name, "your
    agent …" or "TransferX". Never logs the URL (it embeds the raw token)."""
    try:
        message = (
            f"{inviter[:1].upper()}{inviter[1:]} has invited you, {player_name}, to TransferX. With your own "
            "account you review and accept the personal terms offered to you. The link expires in 7 days."
        )
        await asyncio.to_thread(
            _send_sync, to_email, f"TransferX — {inviter[:1].upper()}{inviter[1:]} invites you", _render_html(message, accept_url)
        )
    except Exception:
        logger.exception("Failed to send player invitation email")


async def send_club_invitation_email(to_email: str, club_name: str, accept_url: str) -> None:
    """Fire-and-forget club invitation. Never logs the URL (it embeds the raw
    token)."""
    try:
        message = (
            f"You're invited to bring {club_name} onto TransferX. Set a password to "
            "create your club's account. The link expires in 7 days."
        )
        await asyncio.to_thread(
            _send_sync, to_email, f"TransferX — {club_name} is invited", _render_html(message, accept_url)
        )
    except Exception:
        logger.exception("Failed to send club invitation email")


async def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """Fire-and-forget password reset link (admin panel). Never logs the URL
    (it embeds the raw token)."""
    try:
        message = (
            "TransferX staff have sent you a link to choose a new password. "
            "It works once and expires in 24 hours. If you didn't ask for this, "
            "you can ignore this email; your password stays as it is."
        )
        await asyncio.to_thread(
            _send_sync, to_email, "TransferX — choose a new password", _render_html(message, reset_url)
        )
    except Exception:
        logger.exception("Failed to send password reset email")


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

        actions = None
        async with AsyncSessionLocal() as db:
            user = await db.get(User, recipient_user_id)
            to_email = user.email if user else None
            # An offer waiting on them: one-tap decisions (Lite L8). Only when
            # the email really goes out, so no token is issued for nothing.
            if (to_email and settings.smtp_host and link and link.startswith("/offers/")
                    and type_ in (NotificationType.OFFER_RECEIVED, NotificationType.OFFER_COUNTERED)):
                try:
                    from app.lite.email_actions import offer_buttons

                    actions = await offer_buttons(db, user, uuid.UUID(link.split("/")[2].split("?")[0]))
                    await db.commit()
                except Exception:
                    logger.exception("No one-tap buttons for user %s's email", recipient_user_id)
                    actions = None

        if not to_email:
            return

        full_link = f"{settings.frontend_base_url}{link}" if link else None
        html = _render_html(message, full_link, actions)
        await asyncio.to_thread(_send_sync, to_email, f"TransferX — {message}", html)
    except Exception:
        logger.exception("Failed to send notification email to user %s", recipient_user_id)
