"""
AlertManager: turns raw classifier detections into LED alerts and caregiver
notifications, applying the alert policy:

    detection (label, confidence)
        -> normalise label            (unknown / background classes are ignored)
        -> confidence >= threshold    (per-event, overridable via env)
        -> N hits within a window     (optional debounce; default 1 = off)
        -> LED matrix                 (every accepted detection, throttled)
        -> notification               (per-event cooldown + optional global cooldown)

Notifications are sent from a background worker thread so a slow Textbelt call
never stalls the audio/classifier loop. handle_detection() is thread-safe and
may be called from the classifier thread, a Bridge callback, or the CLI.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Union

from config import Settings
from events import EVENTS, normalize_label

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def send_alert(self, event_type: str, confidence: Optional[float] = None): ...


class LedClient(Protocol):
    def show_emergency(self, event_id: str) -> bool: ...
    def clear(self) -> bool: ...


@dataclass
class Decision:
    event_id: Optional[str]
    accepted: bool          # passed label / threshold / debounce checks
    reason: str
    led_shown: bool = False
    notified: bool = False  # a notification was queued (not necessarily delivered yet)

    def __str__(self) -> str:
        flags = []
        if self.led_shown:
            flags.append("led")
        if self.notified:
            flags.append("notify")
        return f"{self.event_id or '?'}: {'ACCEPT' if self.accepted else 'skip'} ({self.reason})" + (
            f" -> {'+'.join(flags)}" if flags else ""
        )


@dataclass
class _Job:
    event_id: str
    confidence: Optional[float]


class AlertManager:
    def __init__(
        self,
        settings: Settings,
        notifier: Optional[Notifier],
        led: Optional[LedClient],
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self.notifier = notifier
        self.led = led
        self._clock = clock

        self._lock = threading.Lock()
        self._hits: dict[str, deque] = defaultdict(deque)
        self._last_led: dict[str, float] = {}
        self._last_notified: dict[str, float] = {}
        self._last_notified_any: Optional[float] = None

        self._queue: "queue.Queue[Optional[_Job]]" = queue.Queue()
        self._worker = threading.Thread(target=self._drain, name="alert-notifier", daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------ public
    def handle_detection(self, label: Union[str, int], confidence: float = 1.0) -> Decision:
        """Entry point for the classifier. Cheap, non-blocking (except a throttled LED RPC)."""
        event_id = normalize_label(label)
        if event_id is None:
            log.debug("Ignoring unsupported label %r", label)
            return Decision(None, False, f"unsupported label {label!r}")

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return Decision(event_id, False, f"bad confidence {confidence!r}")

        threshold = self.settings.threshold_for(event_id)
        if confidence < threshold:
            log.debug("%s below threshold (%.2f < %.2f)", event_id, confidence, threshold)
            return Decision(event_id, False, f"confidence {confidence:.2f} < {threshold:.2f}")

        now = self._clock()
        with self._lock:
            hits = self._hits[event_id]
            hits.append(now)
            while hits and now - hits[0] > self.settings.hits_window_s:
                hits.popleft()
            if len(hits) < self.settings.hits_required:
                return Decision(event_id, False, f"{len(hits)}/{self.settings.hits_required} hits")
            hits.clear()  # burst consumed; next alert needs a fresh burst

            show_led = self._led_due_locked(event_id, now)
            notify = self._notification_due_locked(event_id, now)

        return self._act(event_id, confidence, show_led, notify, reason="accepted")

    def trigger(self, event_id: Union[str, int], confidence: float = 1.0, *, force: bool = False) -> Decision:
        """
        Manual / test trigger: skips threshold and debounce, keeps cooldowns
        unless force=True. Used by `main.py --trigger` and the Bridge `test_alert` endpoint.
        """
        canonical = normalize_label(event_id)
        if canonical is None:
            return Decision(None, False, f"unsupported label {event_id!r}")
        now = self._clock()
        with self._lock:
            show_led = True if force else self._led_due_locked(canonical, now)
            notify = True if force else self._notification_due_locked(canonical, now)
            if force:
                self._mark_notified_locked(canonical, now)
                self._last_led[canonical] = now
        return self._act(canonical, confidence, show_led, notify, reason="manual trigger")

    def flush(self, timeout: float = 30.0) -> bool:
        """Block until queued notifications have been sent (True) or `timeout` elapses (False)."""
        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.05)
        return self._queue.unfinished_tasks == 0

    def stop(self, timeout: float = 5.0) -> None:
        self._queue.put(None)
        self._worker.join(timeout)

    # ---------------------------------------------------------------- policy
    def _led_due_locked(self, event_id: str, now: float) -> bool:
        if self.led is None or not self.settings.led_enabled:
            return False
        last = self._last_led.get(event_id)
        if last is not None and now - last < self.settings.led_repeat_s:
            return False
        self._last_led[event_id] = now
        return True

    def _notification_due_locked(self, event_id: str, now: float) -> bool:
        if self.notifier is None:
            return False
        last = self._last_notified.get(event_id)
        if last is not None and now - last < self.settings.event_cooldown_s:
            return False
        if (
            self.settings.global_cooldown_s > 0
            and self._last_notified_any is not None
            and now - self._last_notified_any < self.settings.global_cooldown_s
        ):
            return False
        self._mark_notified_locked(event_id, now)
        return True

    def _mark_notified_locked(self, event_id: str, now: float) -> None:
        self._last_notified[event_id] = now
        self._last_notified_any = now

    # ---------------------------------------------------------------- actions
    def _act(self, event_id: str, confidence: float, show_led: bool, notify: bool, *, reason: str) -> Decision:
        decision = Decision(event_id, True, reason)

        led_status = "no"
        if show_led:
            # Local, fast RPC to the MCU; the client swallows Bridge errors and returns False.
            delivered = self.led.show_emergency(event_id)
            decision.led_shown = True
            led_status = "sent" if delivered else "logged only"

        if notify:
            self._queue.put(_Job(event_id, confidence))
            decision.notified = True
        elif self.notifier is not None:
            decision.reason = f"{reason}; notification suppressed by cooldown"

        spec = EVENTS[event_id]
        log.info("%s (%s, %.2f) -> LED %s, notify %s",
                 spec.display_name, spec.severity.value, confidence,
                 led_status, "queued" if decision.notified else "no (cooldown)" if self.notifier else "no")
        return decision

    def _drain(self) -> None:
        while True:
            job = self._queue.get()
            try:
                if job is None:
                    return
                self.notifier.send_alert(job.event_id, job.confidence)
            except Exception:  # never let the worker die
                log.exception("Notification failed for %s", job.event_id if job else None)
            finally:
                self._queue.task_done()
