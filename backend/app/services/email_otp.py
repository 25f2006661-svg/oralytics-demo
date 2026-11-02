from email.message import EmailMessage
import smtplib
import ssl

from ..config import settings


class EmailDeliveryError(Exception):
    pass


def deliver_email_otp(address: str, code: str) -> None:
    """Send an OTP using the SMTP settings configured for this deployment."""
    if not settings.smtp_host or not settings.smtp_from_email:
        raise EmailDeliveryError("Email delivery is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL.")
    if settings.smtp_username and not settings.smtp_password:
        raise EmailDeliveryError("SMTP_PASSWORD is required when SMTP_USERNAME is set.")

    message = EmailMessage()
    message["Subject"] = "Your Oralytics email verification code"
    message["From"] = settings.smtp_from_email
    message["To"] = address
    message.set_content(
        "Use this 6-digit code to verify your email for Oralytics:\n\n"
        f"{code}\n\n"
        "The code expires in 10 minutes and can be used once. "
        "If you did not request it, you can ignore this message."
    )

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=15,
                context=ssl.create_default_context(),
            ) as server:
                _authenticate(server)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.ehlo()
                if settings.smtp_starttls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                _authenticate(server)
                server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("Email delivery failed. Check the SMTP settings.") from error


def _authenticate(server: smtplib.SMTP | smtplib.SMTP_SSL) -> None:
    if settings.smtp_username:
        server.login(settings.smtp_username, settings.smtp_password)
