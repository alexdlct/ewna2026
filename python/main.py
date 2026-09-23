#!/usr/bin/env python3
"""
Sound Guardian - Arduino UNO Q

Mac microphone:
    Mac -> USB relay -> TCP :8765 -> main.py

When volume exceeds LOUD_THRESHOLD:
    1. Bridge.notify("sound_event", "LOUD") -> MCU -> animateVoice()
    2. AlertManager.handle_detection("loud", 1.0) -> notification
"""

from __future__ import annotations

import argparse
import logging
import queue
import signal
import socket
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

try:
    # Arduino App Lab runtime
    from arduino.app_utils import App, Bridge  # type: ignore
except ImportError:
    # Laptop / CI
    App = None
    Bridge = None


log = logging.getLogger("sound_guardian")


# =============================================================================
# MAC MICROPHONE CONFIGURATION
# =============================================================================

HOST = "0.0.0.0"
PORT = 8765

LOUD_THRESHOLD = 0.05

commands = queue.Queue()

was_loud = False


# =============================================================================
# SOUND GUARDIAN
# =============================================================================

def build(
    settings: Settings
) -> tuple[AlertManager, LedMatrixClient, NotificationService]:

    notifier = NotificationService(settings)
    led = LedMatrixClient(enabled=settings.led_enabled)
    manager = AlertManager(settings, notifier, led)

    return manager, led, notifier


# =============================================================================
# ROUTER BRIDGE ENDPOINTS
# =============================================================================

def register_bridge_endpoints(manager: AlertManager) -> None:

    if Bridge is None:
        log.info(
            "Router Bridge not available - "
            "report_detection/test_alert endpoints not registered"
        )
        return

    def report_detection(label, confidence=1.0):
        try:
            return manager.handle_detection(
                label,
                float(confidence)
            ).accepted

        except Exception:
            log.exception(
                "report_detection failed for %r",
                label
            )
            return False

    def test_alert(event_id):
        return manager.trigger(
            str(event_id)
        ).accepted

    Bridge.provide(
        "report_detection",
        report_detection
    )

    Bridge.provide(
        "test_alert",
        test_alert
    )

    log.info(
        "Bridge endpoints registered: "
        "report_detection(label, confidence), "
        "test_alert(event_id)"
    )


# =============================================================================
# MAC -> UNO Q TCP SERVER
# =============================================================================

def command_server(stop: threading.Event):

    server = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    server.bind((HOST, PORT))
    server.listen(5)

    # Prevent accept() from blocking forever during shutdown.
    server.settimeout(1.0)

    log.info(
        "Mac microphone receiver listening on port %d",
        PORT
    )

    while not stop.is_set():

        try:
            conn, addr = server.accept()

        except socket.timeout:
            continue

        except Exception:
            if not stop.is_set():
                log.exception("TCP accept failed")
            continue

        log.info(
            "USB relay connected: %s",
            addr
        )

        buffer = b""

        try:

            while not stop.is_set():

                data = conn.recv(1024)

                if not data:
                    break

                buffer += data

                # Messages from Mac end in \n
                while b"\n" in buffer:

                    line, buffer = buffer.split(
                        b"\n",
                        1
                    )

                    command = line.decode(
                        "utf-8",
                        errors="ignore"
                    ).strip()

                    if command:
                        commands.put(command)

        except Exception:
            if not stop.is_set():
                log.exception(
                    "Microphone connection error"
                )

        finally:
            conn.close()

    server.close()


# =============================================================================
# HANDLE MAC COMMANDS
# =============================================================================

def handle_command(
    command: str,
    manager: AlertManager
):

    global was_loud

    # -------------------------------------------------------------------------
    # MICROPHONE VOLUME
    # -------------------------------------------------------------------------

    if command.startswith("VOL:"):

        try:

            volume = float(
                command.split(":", 1)[1]
            )

            print(
                f"MIC VOLUME: {volume:.4f}"
            )

            # ================================================================
            # LOUD SOUND DETECTED
            # ================================================================

            if volume > LOUD_THRESHOLD:

                # Trigger only when we CROSS the threshold.
                #
                # Without this, a loud sound lasting one second could
                # trigger several animations / notifications.

                if not was_loud:

                    print(
                        ">>> LOUD DETECTED"
                    )

                    # ---------------------------------------------------------
                    # 1. MCU LED animation
                    # ---------------------------------------------------------

                    if Bridge is not None:

                        try:

                            print(
                                ">>> LOUD -> MCU"
                            )

                            Bridge.notify(
                                "sound_event",
                                "LOUD"
                            )

                        except Exception:
                            log.exception(
                                "Failed to send LOUD to MCU"
                            )

                    else:

                        log.info(
                            "Bridge unavailable - "
                            "would send LOUD to MCU"
                        )

                    # ---------------------------------------------------------
                    # 2. SOUND GUARDIAN NOTIFICATION
                    # ---------------------------------------------------------

                    try:

                        print(
                            ">>> LOUD -> ALERT MANAGER"
                        )

                        decision = manager.handle_detection(
                            "loud",
                            1.0
                        )

                        log.info(
                            "Loud detection decision: %s",
                            decision
                        )

                    except Exception:

                        log.exception(
                            "Failed to process loud notification"
                        )

                    was_loud = True

            else:

                # Reset after volume falls below threshold.
                # The next loud sound can trigger again.

                was_loud = False

        except ValueError:

            log.warning(
                "Invalid volume command: %s",
                command
            )

        return

    # -------------------------------------------------------------------------
    # OTHER COMMANDS
    # -------------------------------------------------------------------------

    if command == "VOICE":

        print(">>> HUMAN VOICE")

        manager.handle_detection(
            "screaming_or_yelling_for_help",
            1.0
        )

    elif command == "GLASS":

        print(">>> GLASS BREAK")

        manager.handle_detection(
            "glass_breaking",
            1.0
        )

    elif command == "WATER":

        print(">>> WATER")

        manager.handle_detection(
            "water_rushing_or_spraying",
            1.0
        )

    elif command == "ALARM":

        print(">>> ALARM")

        manager.handle_detection(
            "security_alarm_or_siren",
            1.0
        )

    elif command == "SOS":

        print(">>> SOS")

        manager.handle_detection(
            "screaming_or_yelling_for_help",
            1.0
        )

    elif command == "CLEAR":

        print(">>> CLEAR")

    else:

        print(
            ">>> UNKNOWN:",
            command
        )


# =============================================================================
# PROCESS TCP COMMAND QUEUE
# =============================================================================

def command_processor(
    manager: AlertManager,
    stop: threading.Event
):

    while not stop.is_set():

        try:

            command = commands.get(
                timeout=0.1
            )

            handle_command(
                command,
                manager
            )

        except queue.Empty:
            pass

        except Exception:
            log.exception(
                "Command processing error"
            )


# =============================================================================
# CLASSIFIER
# =============================================================================

def make_classifier(
    settings: Settings,
    stop: threading.Event
) -> Optional[BaseClassifier]:

    mode = settings.classifier

    if mode == "scripted":

        return ScriptedClassifier(
            on_finished=None if App else stop.set
        )

    if mode == "model":

        return ModelClassifier()

    if mode == "bridge":

        log.info(
            "CLASSIFIER=bridge: "
            "waiting for detections via Bridge "
            "report_detection()"
        )

        return None

    raise SystemExit(
        f"Unknown CLASSIFIER={mode!r} "
        "(expected bridge | model | scripted)"
    )


# =============================================================================
# RUN
# =============================================================================

def run_forever(
    stop: threading.Event
) -> None:

    if App is not None:

        App.run()

    else:

        while not stop.is_set():
            time.sleep(0.25)


# =============================================================================
# COMMAND LINE
# =============================================================================

def parse_args(argv=None) -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description="Sound Guardian alert service"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="replay the scripted demo detections"
    )

    parser.add_argument(
        "--trigger",
        metavar="EVENT",
        help="fire a single event and exit"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="with --trigger: ignore cooldowns"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="log notifications instead of sending"
    )

    parser.add_argument(
        "--list-events",
        action="store_true",
        help="print supported events and exit"
    )

    parser.add_argument(
        "--log-level",
        help="DEBUG / INFO / WARNING"
    )

    return parser.parse_args(argv)


# =============================================================================
# MAIN
# =============================================================================

def main(argv=None) -> int:

    args = parse_args(argv)

    if args.list_events:

        print(
            describe_events()
        )

        return 0

    # -------------------------------------------------------------------------
    # SETTINGS
    # -------------------------------------------------------------------------

    settings = Settings.from_env()

    if args.dry_run:
        settings.dry_run = True

    if args.demo:
        settings.classifier = "scripted"

    if args.log_level:
        settings.log_level = args.log_level.upper()

    configure_logging(
        settings.log_level
    )

    log.info(
        "Sound Guardian starting: %s",
        settings.summary()
    )

    if (
        settings.classifier == "scripted"
        and not settings.dry_run
    ):

        log.warning(
            "Demo will send REAL notifications - "
            "use --dry-run to avoid that"
        )

    # -------------------------------------------------------------------------
    # BUILD SOUND GUARDIAN
    # -------------------------------------------------------------------------

    manager, led, _ = build(
        settings
    )

    # -------------------------------------------------------------------------
    # ONE-SHOT CLI MODE
    # -------------------------------------------------------------------------

    if args.trigger:

        event = (
            int(args.trigger)
            if args.trigger.isdigit()
            else args.trigger
        )

        decision = manager.trigger(
            event,
            force=args.force
        )

        print(decision)

        if decision.notified:
            manager.flush(timeout=30)

        manager.stop()

        return (
            0 if decision.accepted else 2
        )

    # -------------------------------------------------------------------------
    # START SERVICE
    # -------------------------------------------------------------------------

    stop = threading.Event()

    for sig in (
        signal.SIGINT,
        signal.SIGTERM
    ):

        try:

            signal.signal(
                sig,
                lambda *_: stop.set()
            )

        except ValueError:
            pass

    # -------------------------------------------------------------------------
    # REGISTER ROUTER BRIDGE
    # -------------------------------------------------------------------------

    register_bridge_endpoints(
        manager
    )

    # -------------------------------------------------------------------------
    # START MAC MICROPHONE TCP RECEIVER
    # -------------------------------------------------------------------------

    threading.Thread(
        target=command_server,
        args=(stop,),
        daemon=True
    ).start()

    # -------------------------------------------------------------------------
    # START COMMAND PROCESSOR
    # -------------------------------------------------------------------------

    threading.Thread(
        target=command_processor,
        args=(manager, stop),
        daemon=True
    ).start()

    # -------------------------------------------------------------------------
    # OPTIONAL CLASSIFIER
    # -------------------------------------------------------------------------

    classifier = make_classifier(
        settings,
        stop
    )

    if classifier is not None:

        classifier.start(
            manager.handle_detection
        )

    log.info(
        "Running. Press Ctrl+C to stop."
    )

    # -------------------------------------------------------------------------
    # RUN APP LAB
    # -------------------------------------------------------------------------

    try:

        run_forever(
            stop
        )

    finally:

        log.info(
            "Shutting down..."
        )

        stop.set()

        if classifier is not None:
            classifier.stop()

        manager.flush(
            timeout=15
        )

        manager.stop()

        led.clear()

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )