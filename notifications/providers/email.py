"""SMTP email notification provider."""

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Sequence

from notifications.models import FailureNotification, NotificationResult


class EmailProvider:
    """Send confirmed-failure alerts through SMTP email."""

    provider_name = "email"

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_security: str,
        username: str,
        password: str,
        sender: str,
        recipients: str | Sequence[str],
        send_screenshot: bool = True,
        timeout_seconds: float = 5.0,
    ) -> None:
        """Create an SMTP email notification provider."""

        self._smtp_host = smtp_host.strip()
        self._smtp_port = smtp_port
        self._smtp_security = smtp_security.lower().strip()
        self._username = username.strip()
        self._password = password
        self._sender = sender.strip()
        self._recipients = parse_email_recipients(recipients)
        self._send_screenshot = send_screenshot
        self._timeout_seconds = timeout_seconds
        self.destination_id = ",".join(self._recipients) or "email"

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> NotificationResult:
        """Send an SMTP email alert."""

        config_error = self._validate_config()
        if config_error is not None:
            return config_error

        try:
            message = self._build_message(notification)
            self._send_message(message)
        except smtplib.SMTPAuthenticationError:
            return self._failure_result("SMTP authentication failed.")
        except smtplib.SMTPException as exc:
            return self._failure_result(f"SMTP email failed: {exc.__class__.__name__}")
        except OSError as exc:
            return self._failure_result(f"SMTP network or file error: {exc}")
        except Exception as exc:  # noqa: BLE001 - providers must isolate failures.
            return self._failure_result(
                f"SMTP notification failed: {exc.__class__.__name__}"
            )

        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=True,
            message="Email notification sent.",
        )

    def _validate_config(self) -> NotificationResult | None:
        """Return a failed result when required SMTP config is missing."""

        missing_fields = []
        if not self._smtp_host:
            missing_fields.append("SMTP host")
        if self._smtp_port <= 0:
            missing_fields.append("SMTP port")
        if self._smtp_security not in {"ssl", "starttls", "none"}:
            missing_fields.append("SMTP security")
        if not self._username:
            missing_fields.append("SMTP username")
        if not self._password:
            missing_fields.append("SMTP password")
        if not self._sender:
            missing_fields.append("email sender")
        if not self._recipients:
            missing_fields.append("email recipients")
        if self._timeout_seconds <= 0:
            missing_fields.append("notification timeout")

        if missing_fields:
            return self._failure_result(
                "Missing or invalid SMTP config: " + ", ".join(missing_fields) + "."
            )

        return None

    def _build_message(self, notification: FailureNotification) -> EmailMessage:
        """Build an email alert message."""

        message = EmailMessage()
        message["Subject"] = (
            f"PrintSentinel failure: {notification.label} "
            f"({notification.confidence:.2f})"
        )
        message["From"] = self._sender
        message["To"] = ", ".join(self._recipients)
        message.set_content(_format_message(notification))

        if self._should_attach_screenshot(notification.screenshot_path):
            self._attach_screenshot(message, notification.screenshot_path)

        return message

    def _send_message(self, message: EmailMessage) -> None:
        """Send an email message using the configured SMTP security mode."""

        context = ssl.create_default_context()
        if self._smtp_security == "ssl":
            with smtplib.SMTP_SSL(
                self._smtp_host,
                self._smtp_port,
                timeout=self._timeout_seconds,
                context=context,
            ) as smtp:
                smtp.login(self._username, self._password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(
            self._smtp_host,
            self._smtp_port,
            timeout=self._timeout_seconds,
        ) as smtp:
            if self._smtp_security == "starttls":
                smtp.starttls(context=context)
            smtp.login(self._username, self._password)
            smtp.send_message(message)

    def _should_attach_screenshot(self, screenshot_path: Path | None) -> bool:
        """Return whether a screenshot should be attached to the email."""

        return (
            self._send_screenshot
            and screenshot_path is not None
            and screenshot_path.exists()
        )

    def _attach_screenshot(
        self,
        message: EmailMessage,
        screenshot_path: Path | None,
    ) -> None:
        """Attach a screenshot to an email message."""

        if screenshot_path is None:
            return

        content_type, _ = mimetypes.guess_type(screenshot_path)
        if content_type is None:
            maintype, subtype = "application", "octet-stream"
        else:
            maintype, subtype = content_type.split("/", 1)

        message.add_attachment(
            screenshot_path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=screenshot_path.name,
        )

    def _failure_result(self, message: str) -> NotificationResult:
        """Build a failed email notification result."""

        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=False,
            message=message,
        )


def parse_email_recipients(recipients: str | Sequence[str]) -> list[str]:
    """Parse configured email recipients into a clean list."""

    if isinstance(recipients, str):
        raw_values = recipients.split(",")
    else:
        raw_values = recipients

    return [recipient.strip() for recipient in raw_values if recipient.strip()]


def _format_message(notification: FailureNotification) -> str:
    """Build plain-text email alert body."""

    screenshot = (
        str(notification.screenshot_path)
        if notification.screenshot_path is not None
        else "not saved"
    )
    return (
        "PrintSentinel confirmed a 3D printer failure.\n\n"
        f"Time: {notification.timestamp}\n"
        f"Source: {notification.source}\n"
        f"Label: {notification.label}\n"
        f"Confidence: {notification.confidence:.2f}\n"
        f"Printer action: {notification.action}\n"
        f"Screenshot: {screenshot}\n"
    )
