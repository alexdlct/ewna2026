#!/usr/bin/env python3
"""
Sound Guardian - Linux-side service for the Arduino UNO Q.

    classifier  ->  AlertManager  ->  LED matrix (Router Bridge)  +  Textbelt SMS / e-mail

Inside Arduino App Lab this file is the app's `python/main.py`; App.run()
keeps it alive and serves the Bridge endpoints below. It also runs on a
laptop for development (Bridge calls are logged instead).

Usage:
    python main.py                        normal run (see CLASSIFIER in .env)
    python main.py --demo                 replay scripted detections through the pipeline
    python main.py --trigger thud         fire one event (LED + SMS) and exit
    python main.py --trigger thud --force ...ignoring cooldowns
    python main.py --list-events          print the supported event table
    ALERT_DRY_RUN=1 python main.py --demo log instead of sending real SMS

Bridge endpoints provided to the MCU / other processes:
    report_detection(label: str, confidence: float) -> bool   # feed the classifier output
    test_alert(event_id: str) -> bool                          # manual trigger (e.g. from a button)
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from typing import Optional

from alert_manager import AlertManager
from classifier import BaseClassifier, ModelClassifier, ScriptedClassifier
from config import Settings, configure_logging
from events import describe_events
from led_bridge import LedMatrixClient
from notification_service import NotificationService

try:  # Arduino App Lab runtime
    from arduino.app_utils import App, Bridge  # type: ignore
except ImportError:  # laptop / CI
    App = None
    Bridge = None

log = logging.getLogger("sound_guardian")


# --------------------------------------------------------------------------- wiring
def build(settings: Settings) -> tuple[AlertManager, LedMatrixClient, NotificationService]:
    notifier = NotificationService(settings)
    led = LedMatrixClient(enabled=settings.led_enabled)
    manager = AlertManager(settings, notifier, led)
    return manager, led, notifier


def register_bridge_endpoints(manager: AlertManager) -> None:
    """Expose the alert pipeline to the MCU sketch (and anything else on the Bridge)."""
    if Bridge is None:
        log.info("Router Bridge not available - report_detection/test_alert endpoints not registered")
        return

    def report_detection(label, confidence=1.0):
        try:
            return manager.handle_detection(label, float(confidence)).accepted
        except Exception:
            log.exception("report_detection failed for %r", label)
            return False

    def test_alert(event_id):
        return manager.trigger(str(event_id)).accepted

    Bridge.provide("report_detection", report_detection)
    Bridge.provide("test_alert", test_alert)
    log.info("Bridge endpoints registered: report_detection(label, confidence), test_alert(event_id)")


def make_classifier(settings: Settings, stop: threading.Event) -> Optional[BaseClassifier]:
    mode = settings.classifier
    if mode == "scripted":
        # After the script finishes, stop the service when we are not under App Lab.
        return ScriptedClassifier(on_finished=None if App else stop.set)
    if mode == "model":
        return ModelClassifier()
    if mode == "bridge":
        log.info("CLASSIFIER=bridge: waiting for detections via Bridge report_detection()")
        return None
    raise SystemExit(f"Unknown CLASSIFIER={mode!r} (expected bridge | model | scripted)")


def run_forever(stop: threading.Event) -> None:
    if App is not None:
        App.run()  # blocks until App Lab stops the app
    else:
        while not stop.is_set():
            time.sleep(0.25)


# ------------------------------------------------------------------------------ cli
def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sound Guardian alert service")
    parser.add_argument("--demo", action="store_true", help="replay the scripted demo detections")
    parser.add_argument("--trigger", metavar="EVENT", help="fire a single event and exit")
    parser.add_argument("--force", action="store_true", help="with --trigger: ignore cooldowns")
    parser.add_argument("--dry-run", action="store_true", help="log notifications instead of sending")
    parser.add_argument("--list-events", action="store_true", help="print supported events and exit")
    parser.add_argument("--log-level", help="DEBUG / INFO / WARNING (default from LOG_LEVEL)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.list_events:
        print(describe_events())
        return 0

    settings = Settings.from_env()
    if args.dry_run:
        settings.dry_run = True
    if args.demo:
        settings.classifier = "scripted"
    if args.log_level:
        settings.log_level = args.log_level.upper()

    configure_logging(settings.log_level)
    log.info("Sound Guardian starting: %s", settings.summary())
    if settings.classifier == "scripted" and not settings.dry_run:
        log.warning("Demo will send REAL notifications - use --dry-run / ALERT_DRY_RUN=1 to avoid that")

    manager, led, _ = build(settings)

    # One-shot mode: useful for the integration checklist and for burning exactly one SMS.
    if args.trigger:
        event = int(args.trigger) if args.trigger.isdigit() else args.trigger   # allow class index
        decision = manager.trigger(event, force=args.force)
        print(decision)
        if decision.notified:
            manager.flush(timeout=30)
        manager.stop()
        return 0 if decision.accepted else 2

    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: stop.set())
        except ValueError:  # not on the main thread
            pass

    register_bridge_endpoints(manager)
    classifier = make_classifier(settings, stop)
    if classifier is not None:
        classifier.start(manager.handle_detection)

    log.info("Running. Press Ctrl+C to stop.")
    try:
        run_forever(stop)
    finally:
        log.info("Shutting down...")
        if classifier is not None:
            classifier.stop()
        manager.flush(timeout=15)
        manager.stop()
        led.clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
