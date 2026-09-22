"""
Runtime configuration for the Sound Guardian service.

Everything is read from environment variables (optionally via a `.env` file
next to this package or at the repo root). Nothing here is required for the
offline tests; only the notification service needs credentials.

See `.env.example` for the full list.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from events import EVENTS

log = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "on", "y"}

# Third-party HTTP loggers are too chatty at INFO for an always-on service.
_NOISY_LOGGERS = ("urllib3", "requests")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def _load_dotenv() -> None:
    """Load python/.env or ../.env if python-dotenv is installed. Never overrides real env vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # dotenv is optional; App Lab / systemd can inject env directly
        return
    here = Path(__file__).resolve().parent
    for candidate in (here / ".env", here.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            log.debug("Loaded environment from %s", candidate)
            return
    load_dotenv(override=False)  # last resort: search from the CWD upwards


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in _TRUE


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        log.warning("Ignoring invalid float for %s=%r (using %s)", name, value, default)
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        log.warning("Ignoring invalid int for %s=%r (using %s)", name, value, default)
        return default


def _env_list(*names: str) -> list[str]:
    """First non-empty of the given vars, split on commas / semicolons / whitespace."""
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return [item for item in re.split(r"[,\s;]+", value.strip()) if item]
    return []


@dataclass
class Settings:
    # --- general -----------------------------------------------------------
    dry_run: bool = False            # log alerts instead of calling Textbelt / SMTP
    log_level: str = "INFO"
    classifier: str = "bridge"       # bridge | model | scripted   (see classifier.py)

    # --- alert policy ------------------------------------------------------
    event_cooldown_s: float = 60.0   # min seconds between two SMS for the SAME event
    global_cooldown_s: float = 0.0   # min seconds between ANY two SMS (0 = disabled)
    hits_required: int = 1           # consecutive detections needed before alerting
    hits_window_s: float = 3.0       # ...within this many seconds
    led_enabled: bool = True
    led_repeat_s: float = 2.0        # throttle for re-sending the same icon to the MCU
    global_threshold: Optional[float] = None       # overrides every per-event default
    thresholds: dict = field(default_factory=dict)  # per-event overrides
    include_confidence: bool = False # append "confidence 87%" to the SMS body

    # --- Textbelt SMS ------------------------------------------------------
    textbelt_api_key: str = ""
    caregiver_numbers: list = field(default_factory=list)

    # --- optional e-mail (SMTP) -------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: list = field(default_factory=list)

    # ----------------------------------------------------------------------
    @property
    def sms_configured(self) -> bool:
        return bool(self.textbelt_api_key and self.caregiver_numbers)

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.email_from and self.email_to)

    def threshold_for(self, event_id: str) -> float:
        if event_id in self.thresholds:
            return self.thresholds[event_id]
        if self.global_threshold is not None:
            return self.global_threshold
        return EVENTS[event_id].default_threshold

    def summary(self) -> str:
        """One-line, secret-free description for the startup log."""
        return (
            f"classifier={self.classifier} dry_run={self.dry_run} "
            f"sms={'on' if self.sms_configured else 'off'}({len(self.caregiver_numbers)} recipients) "
            f"email={'on' if self.email_configured else 'off'} led={'on' if self.led_enabled else 'off'} "
            f"cooldown={self.event_cooldown_s:g}s/event"
            f"{f' {self.global_cooldown_s:g}s/global' if self.global_cooldown_s else ''} "
            f"hits={self.hits_required}/{self.hits_window_s:g}s"
        )

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()

        thresholds = {}
        for event_id in EVENTS:
            raw = os.getenv(f"THRESHOLD_{event_id.upper()}")
            if raw:
                try:
                    thresholds[event_id] = float(raw)
                except ValueError:
                    log.warning("Ignoring invalid THRESHOLD_%s=%r", event_id.upper(), raw)

        global_threshold_raw = os.getenv("ALERT_THRESHOLD")
        global_threshold = float(global_threshold_raw) if global_threshold_raw else None

        return cls(
            dry_run=_env_bool("ALERT_DRY_RUN", False),
            log_level=_env_str("LOG_LEVEL", "INFO").upper(),
            classifier=_env_str("CLASSIFIER", "bridge").lower(),
            event_cooldown_s=_env_float("EVENT_COOLDOWN_SECONDS", 60.0),
            global_cooldown_s=_env_float("GLOBAL_COOLDOWN_SECONDS", 0.0),
            hits_required=max(1, _env_int("HITS_REQUIRED", 1)),
            hits_window_s=_env_float("HITS_WINDOW_SECONDS", 3.0),
            led_enabled=_env_bool("LED_ENABLED", True),
            led_repeat_s=_env_float("LED_REPEAT_SECONDS", 2.0),
            global_threshold=global_threshold,
            thresholds=thresholds,
            include_confidence=_env_bool("SMS_INCLUDE_CONFIDENCE", False),
            textbelt_api_key=_env_str("TEXTBELT_API_KEY"),
            caregiver_numbers=_env_list("CAREGIVER_PHONE_NUMBERS", "CAREGIVER_PHONE_NUMBER"),
            smtp_host=_env_str("SMTP_HOST"),
            smtp_port=_env_int("SMTP_PORT", 587),
            smtp_user=_env_str("SMTP_USER"),
            smtp_password=_env_str("SMTP_PASSWORD"),
            email_from=_env_str("EMAIL_FROM"),
            email_to=_env_list("EMAIL_TO"),
        )
