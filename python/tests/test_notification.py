#!/usr/bin/env python3
"""
Step 1 of the integration sequence: prove the notification path works with a
hard-coded event, independently of the classifier and the Bridge.

    python tests/test_notification.py                       # sends smoke_alarm_beeping for real
    python tests/test_notification.py glass_breaking        # any supported label / alias / display name
    python tests/test_notification.py --all --dry-run       # validates all eight labels, sends nothing
    python tests/test_notification.py --all                 # sends all eight (8 SMS - uses quota)

Exit code 0 = every message was accepted by Textbelt / SMTP.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Settings, configure_logging
from events import EVENTS
from notification_service import NotificationService


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("event", nargs="?", default="smoke_alarm_beeping")
    parser.add_argument("--all", action="store_true", help="send every supported event")
    parser.add_argument("--dry-run", action="store_true", help="log instead of sending")
    args = parser.parse_args(argv)

    configure_logging("INFO")

    settings = Settings.from_env()
    if args.dry_run:
        settings.dry_run = True
    print(f"Config: {settings.summary()}")
    if not settings.dry_run and not settings.sms_configured:
        print("Textbelt is not fully configured (TEXTBELT_API_KEY / CAREGIVER_PHONE_NUMBER). "
              "Add them to python/.env or use --dry-run.")
        return 1

    service = NotificationService(settings)

    # Invalid labels must be rejected before any network call.
    try:
        service.send_alert("definitely_not_an_event")
    except ValueError as exc:
        print(f"Invalid label rejected cleanly: {exc}")
    else:
        print("ERROR: invalid label was NOT rejected")
        return 1

    events = list(EVENTS) if args.all else [args.event]
    failures = 0
    for event in events:
        results = service.send_alert(event)
        for result in results:
            print(f"  {event:32} {result}")
            failures += 0 if result.ok else 1

    if failures:
        print(f"{failures} delivery failure(s) - check the errors above (bad number, key, or quota?)")
        return 1
    print("All notifications accepted." + (" (dry run)" if settings.dry_run else " Check the phone."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
