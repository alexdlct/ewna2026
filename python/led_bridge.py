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
"""

from __future__ import annotations

import logging

from events import EVENTS

log = logging.getLogger(__name__)

try:  # only available inside the Arduino App Lab Python runtime
    from arduino.app_utils import Bridge  # type: ignore
except ImportError:  # pragma: no cover
    Bridge = None


class LedMatrixClient:
    RPC_SHOW = "show_emergency"
    RPC_CLEAR = "clear_emergency"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.available = Bridge is not None
        if not self.available:
            log.info("Router Bridge not available - LED alerts will be logged only")

    def show_emergency(self, event_id: str) -> bool:
        spec = EVENTS[event_id]
        log.info("LED matrix: %s (icon=%s rgb=%s)", event_id, spec.led_icon, spec.rgb_hint)
        return self._call(self.RPC_SHOW, event_id)

    def clear(self) -> bool:
        log.info("LED matrix: clear")
        return self._call(self.RPC_CLEAR)

    def _call(self, method: str, *args) -> bool:
        if not self.enabled or not self.available:
            return False
        try:
            Bridge.call(method, *args)
            return True
        except Exception as exc:  # Bridge raises ValueError when the MCU has no such method / times out
            log.warning("Bridge.call(%r) failed: %s", method, exc)
            return False
