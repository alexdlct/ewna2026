"""
Remote notification service: Textbelt SMS, plus optional SMTP e-mail.

Contract (unchanged from the hand-off):

    NotificationService().send_alert("smoke_alarm_beeping")

* Only event metadata leaves the device. The message body is built from the
  static text in events.py plus a timestamp (and optionally the confidence).
  Raw audio never reaches this module.
* Unsupported labels raise ValueError *before* any network I/O.
* Network failures never raise; they are logged and reported in the returned
  NotificationResult list so the caller (AlertManager's worker thread) keeps running.

Textbelt sends the event-specific message body with no provider SDK. Set
SMS_PLAIN_TEXT=1 to strip the leading emoji if message segmentation matters.
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Optional, Protocol

from config import Settings
from events import EVENTS, EventSpec, normalize_label
from providers.textbelt import TextbeltProvider

log = logging.getLogger(__name__)

# Kept for anyone importing the old name from the hand-off draft.
EVENT_MESSAGES = {event_id: spec.sms_text for event_id, spec in EVENTS.items()}


@dataclass
class NotificationResult:
    channel: str            # "sms" | "email" | "dry-run"
    ok: bool
    recipient: str
    message_id: Optional[str] = None
    error: Optional[str] = None

    def __str__(self) -> str:
        status = "OK" if self.ok else "FAILED"
        extra = f" id={self.message_id}" if self.message_id else (f" error={self.error}" if self.error else "")
        return f"[{self.channel}] {status} -> {self.recipient}{extra}"


class SmsProvider(Protocol):
    def send_message(self, phone: str, message: str) -> str: ...


class NotificationService:
    """Sends the alert for a classified event to the caregiver(s)."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        dry_run: Optional[bool] = None,
        provider: Optional[SmsProvider] = None,
    ):
        self.settings = settings or Settings.from_env()
        self.dry_run = self.settings.dry_run if dry_run is None else dry_run
        self.plain_text = os.getenv("SMS_PLAIN_TEXT", "").strip().lower() in {"1", "true", "yes", "on"}
        self._sms_provider = provider
        self._sms_enabled = bool(
            self.settings.caregiver_numbers
            and (self.settings.textbelt_api_key or provider is not None)
        )

        if not self.dry_run and not (self._sms_enabled or self.settings.email_configured):
            raise RuntimeError(
                "No notification channel configured. Set TEXTBELT_API_KEY and "
                "CAREGIVER_PHONE_NUMBER (or the SMTP_* / EMAIL_* variables), "
                "or run with ALERT_DRY_RUN=1."
            )

    # ------------------------------------------------------------------ public
    def send_alert(self, event_type: str, confidence: Optional[float] = None) -> list[NotificationResult]:
        """
        Send the alert for `event_type` through every configured channel.

        Returns one NotificationResult per recipient/channel. Raises ValueError
        for labels that are not a supported event.
        """
        event_id = normalize_label(event_type)
        if event_id is None:
            raise ValueError(f"Unsupported event type: {event_type!r}")
        spec = EVENTS[event_id]

        body = self.build_message(spec, confidence)
        subject = f"Sound Guardian: {spec.display_name}"

        if self.dry_run:
            recipients = list(self.settings.caregiver_numbers) + list(self.settings.email_to) or ["<nobody configured>"]
            log.info("DRY RUN - would send %r to %s", body, recipients)
            return [NotificationResult("dry-run", True, r) for r in recipients]

        results: list[NotificationResult] = []
        if self._sms_enabled:
            results.extend(self._send_sms(body))
        if self.settings.email_configured:
            results.extend(self._send_email(subject, body))

        for result in results:
            (log.info if result.ok else log.error)("%s", result)
        return results

    def build_message(self, spec: EventSpec, confidence: Optional[float] = None) -> str:
        text = spec.sms_text
        if self.plain_text:
            # drop everything up to the first ASCII letter (i.e. the leading emoji)
            text = text[next((i for i, ch in enumerate(text) if ch.isascii() and ch.isalpha()), 0):]
        parts = [text, f"[{time.strftime('%H:%M')}]"]
        if confidence is not None and self.settings.include_confidence:
            parts.append(f"(confidence {confidence:.0%})")
        return " ".join(parts)

    def _provider(self) -> SmsProvider:
        if self._sms_provider is None:
            self._sms_provider = TextbeltProvider(self.settings.textbelt_api_key)
        return self._sms_provider

    def _send_sms(self, body: str) -> list[NotificationResult]:
        results = []
        for number in self.settings.caregiver_numbers:
            try:
                text_id = self._provider().send_message(number, body)
                results.append(NotificationResult("sms", True, number, message_id=text_id))
            except Exception as exc:  # API rejection, network error, invalid response, ...
                results.append(NotificationResult("sms", False, number, error=f"{type(exc).__name__}: {exc}"))
        return results

    def _send_email(self, subject: str, body: str) -> list[NotificationResult]:
        s = self.settings
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = s.email_from
        msg["To"] = ", ".join(s.email_to)
        msg.set_content(body)

        try:
            if s.smtp_port == 465:
                server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
                server.starttls()
            with server:
                if s.smtp_user:
                    server.login(s.smtp_user, s.smtp_password)
                server.send_message(msg)
            return [NotificationResult("email", True, to) for to in s.email_to]
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            return [NotificationResult("email", False, to, error=error) for to in s.email_to]
