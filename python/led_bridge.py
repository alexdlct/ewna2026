"""
LED matrix client: forwards accepted events to the MCU sketch over the
Arduino Router Bridge (Linux MPU -> STM32 MCU RPC).

Sketch-side contract (sketch/sketch.ino):

    #include <Arduino_RouterBridge.h>

    void showEmergency(String eventId);   // draw icon for eventId, light RGB LEDs
    void clearEmergency();                // back to idle animation

    void setup() {
        Bridge.begin();
        Bridge.provide("show_emergency", showEmergency);
        Bridge.provide("clear_emergency", clearEmergency);
    }

The event id (e.g. "smoke_alarm_beeping") is what crosses the Bridge; the
sketch owns the mapping from id -> icons.h frame. Off-board (laptop dev,
unit tests) the Bridge import fails and calls are just logged.

The sketch actually deployed (Lighting/88_lighting_animated_rgb) does NOT
provide show_emergency; it provides `sound_event` via provide_safe and expects
Bridge.notify("sound_event", "<COMMAND>") with commands such as GLASS, ALARM,
THUD, VOICE, CLEAR. That is the default protocol here (LED_PROTOCOL=sound_event);
LED_PROTOCOL=rpc restores the show_emergency contract above.
"""

from __future__ import annotations

import logging
import os

from events import EVENTS

log = logging.getLogger(__name__)

try:  # only available inside the Arduino App Lab Python runtime
    from arduino.app_utils import Bridge  # type: ignore
except ImportError:  # pragma: no cover
    Bridge = None


class LedMatrixClient:
    RPC_SHOW = "show_emergency"
    RPC_CLEAR = "clear_emergency"
    NOTIFY_TOPIC = "sound_event"
    CLEAR_COMMAND = "CLEAR"

    # event id -> command understood by handleEvent() in the deployed sketch
    SKETCH_COMMANDS = {
        "smoke_alarm_beeping": "ALARM",
        "carbon_monoxide_alarm": "CO",
        "glass_breaking": "GLASS",
        "screaming_or_yelling_for_help": "SCREAM",
        "water_rushing_or_spraying": "WATER",
        "thud": "THUD",
        "security_alarm_or_siren": "ALARM",
        "electrical_buzzing_or_sparking": "ELECTRICAL",
        "loud_sound": "LOUD",
        "unfamiliar_voice": "VOICE",
    }

    def __init__(self, enabled: bool = True, protocol: str | None = None):
        self.enabled = enabled
        self.available = Bridge is not None
        self.protocol = (protocol or os.getenv("LED_PROTOCOL", "sound_event")).strip().lower()
        if self.protocol not in ("sound_event", "rpc"):
            log.warning("Unknown LED_PROTOCOL=%r, using sound_event", self.protocol)
            self.protocol = "sound_event"
        if not self.available:
            log.info("Router Bridge not available - LED alerts will be logged only")

    def show_emergency(self, event_id: str) -> bool:
        spec = EVENTS[event_id]
        command = self.SKETCH_COMMANDS.get(event_id, "DANGER")
        log.info("LED matrix: %s (icon=%s rgb=%s) -> %s", event_id, spec.led_icon, spec.rgb_hint,
                 event_id if self.protocol == "rpc" else command)
        if self.protocol == "rpc":
            return self._call(self.RPC_SHOW, event_id)
        return self._notify(command)

    def clear(self) -> bool:
        log.info("LED matrix: clear")
        if self.protocol == "rpc":
            return self._call(self.RPC_CLEAR)
        return self._notify(self.CLEAR_COMMAND)

    def _notify(self, command: str) -> bool:
        if not self.enabled or not self.available:
            return False
        try:
            Bridge.notify(self.NOTIFY_TOPIC, command)
            return True
        except Exception as exc:
            log.warning("Bridge.notify(%r, %r) failed: %s", self.NOTIFY_TOPIC, command, exc)
            return False

    def _call(self, method: str, *args) -> bool:
        if not self.enabled or not self.available:
            return False
        try:
            Bridge.call(method, *args)
            return True
        except Exception as exc:  # Bridge raises ValueError when the MCU has no such method / times out
            log.warning("Bridge.call(%r) failed: %s", method, exc)
            return False
