import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(to_email: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())


def send_email(to_email: str, subject: str, html_body: str) -> None:
    if settings.SMTP_ENABLED:
        try:
            _send_smtp(to_email, subject, html_body)
        except Exception:
            logger.exception("Failed to send email to %s", to_email)
    else:
        logger.info(
            "[EMAIL MOCK] To: %s | Subject: %s\n%s",
            to_email,
            subject,
            html_body,
        )


def send_welcome_email(to_email: str, display_name: str) -> None:
    subject = f"Welcome to Tick 8, {display_name}!"
    body = f"""
    <h2>Welcome to Tick 8, {display_name}!</h2>
    <p>Your account has been created. Start building your flashcard decks and mastering knowledge with the Tick 8 spaced-repetition method.</p>
    <p>The Tick 8 Team</p>
    """
    send_email(to_email, subject, body)


def send_verification_email(to_email: str, display_name: str, token: str) -> None:
    from app.core.config import settings as cfg

    link = f"{cfg.FRONTEND_ORIGIN}/verify-email?token={token}"
    subject = "Verify your Tick 8 email address"
    body = f"""
    <h2>Hi {display_name},</h2>
    <p>Please verify your email address by clicking the link below. This link expires in 24 hours.</p>
    <p><a href="{link}">Verify Email Address</a></p>
    <p>If you did not create an account, you can ignore this email.</p>
    """
    send_email(to_email, subject, body)


def send_password_reset_email(to_email: str, display_name: str, token: str) -> None:
    from app.core.config import settings as cfg

    link = f"{cfg.FRONTEND_ORIGIN}/reset-password?token={token}"
    subject = "Reset your Tick 8 password"
    body = f"""
    <h2>Hi {display_name},</h2>
    <p>Click the link below to reset your password. This link expires in 1 hour and can only be used once.</p>
    <p><a href="{link}">Reset Password</a></p>
    <p>If you did not request a password reset, you can safely ignore this email.</p>
    """
    send_email(to_email, subject, body)


def send_email_change_verification(to_email: str, display_name: str, token: str) -> None:
    from app.core.config import settings as cfg

    link = f"{cfg.FRONTEND_ORIGIN}/confirm-email-change?token={token}"
    subject = "Confirm your new Tick 8 email address"
    body = f"""
    <h2>Hi {display_name},</h2>
    <p>Click the link below to confirm your new email address. This link expires in 24 hours.</p>
    <p><a href="{link}">Confirm New Email</a></p>
    <p>Your old email remains active until you confirm the new one.</p>
    """
    send_email(to_email, subject, body)
