"""
Offline tests - no Textbelt, no board, no network.

    python tests/test_offline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alert_manager import AlertManager
from config import Settings
from events import CLASS_ORDER, EVENTS, normalize_label
from notification_service import NotificationService
from providers.textbelt import TEXTBELT_ENDPOINT, TextbeltProvider


# --------------------------------------------------------------------- fakes
class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, float]] = []

    def send_alert(self, event_type, confidence=None):
        self.sent.append((event_type, confidence))
        return []


class FakeLed:
    def __init__(self) -> None:
        self.shown: list[str] = []
        self.cleared = 0

    def show_emergency(self, event_id):
        self.shown.append(event_id)
        return True

    def clear(self):
        self.cleared += 1
        return True


def make_manager(**overrides):
    settings = Settings(dry_run=True, event_cooldown_s=60, led_repeat_s=0, **overrides)
    clock = FakeClock()
    notifier, led = FakeNotifier(), FakeLed()
    manager = AlertManager(settings, notifier, led, clock=clock)
    return manager, notifier, led, clock


# -------------------------------------------------------------------- events
def test_all_eight_events_are_supported():
    assert len(EVENTS) == 8
    assert set(EVENTS) == set(CLASS_ORDER)
    for event_id, spec in EVENTS.items():
        assert normalize_label(event_id) == event_id
        assert normalize_label(spec.display_name) == event_id, spec.display_name
        assert 0 < spec.default_threshold <= 1
        assert spec.sms_text and spec.led_icon


def test_classifier_output_labels_normalise():
    cases = {
        "Smoke alarm beeping": "smoke_alarm_beeping",
        "Carbon monoxide alarm": "carbon_monoxide_alarm",
        "Glass breaking (Dropped item)": "glass_breaking",
        "Someone screaming or yelling for help": "screaming_or_yelling_for_help",
        "Water rushing or spraying": "water_rushing_or_spraying",
        "thud": "thud",
        "Security alarm/siren": "security_alarm_or_siren",
        "Electrical buzzing or sparking": "electrical_buzzing_or_sparking",
        "SMOKE_ALARM": "smoke_alarm_beeping",
        "fire alarm": "smoke_alarm_beeping",
        "CO alarm": "carbon_monoxide_alarm",
        "fall_detected": "thud",
        0: "smoke_alarm_beeping",
        7: "electrical_buzzing_or_sparking",
    }
    for raw, expected in cases.items():
        assert normalize_label(raw) == expected, raw


def test_unknown_labels_are_rejected():
    for raw in ("background", "silence", "dog_bark", "", None, 8, -1, True):
        assert normalize_label(raw) is None, raw


# ---------------------------------------------------------- notification svc
def test_notification_service_dry_run_supports_all_events():
    service = NotificationService(Settings(dry_run=True, caregiver_numbers=["+15550000000"]))
    for event_id in EVENTS:
        results = service.send_alert(event_id)
        assert results and all(r.ok for r in results)


def test_notification_service_rejects_invalid_label():
    service = NotificationService(Settings(dry_run=True))
    try:
        service.send_alert("not_a_real_event")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid label was accepted")


def test_notification_service_requires_a_channel_when_live():
    try:
        NotificationService(Settings(dry_run=False))
    except RuntimeError:
        pass
    else:
        raise AssertionError("should refuse to start without any channel configured")


def test_textbelt_provider_posts_expected_payload():
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True, "textId": 12345, "quotaRemaining": 9}

    def fake_post(url, *, data, timeout):
        captured.update(url=url, data=data, timeout=timeout)
        return Response()

    provider = TextbeltProvider("test-key", request_post=fake_post)
    text_id = provider.send_message("+15550000000", "Sound Guardian test")

    assert text_id == "12345"
    assert captured == {
        "url": TEXTBELT_ENDPOINT,
        "data": {
            "phone": "+15550000000",
            "message": "Sound Guardian test",
            "key": "test-key",
        },
        "timeout": 15,
    }


def test_textbelt_provider_reports_api_rejection():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": False, "error": "Out of quota", "quotaRemaining": 0}

    provider = TextbeltProvider("test-key", request_post=lambda *args, **kwargs: Response())
    try:
        provider.send_message("+15550000000", "Sound Guardian test")
    except RuntimeError as exc:
        assert str(exc) == "Out of quota"
    else:
        raise AssertionError("Textbelt API rejection was accepted")


def test_notification_service_returns_provider_failure():
    class FailingProvider:
        def send_message(self, phone, message):
            raise RuntimeError("Textbelt unavailable")

    settings = Settings(dry_run=False, caregiver_numbers=["+15550000000"])
    service = NotificationService(settings, provider=FailingProvider())
    results = service.send_alert("glass_breaking")

    assert len(results) == 1
    assert not results[0].ok
    assert results[0].recipient == "+15550000000"
    assert results[0].error == "RuntimeError: Textbelt unavailable"


def test_notification_service_preserves_event_specific_messages():
    class RecordingProvider:
        def __init__(self):
            self.messages = []

        def send_message(self, phone, message):
            self.messages.append((phone, message))
            return str(len(self.messages))

    provider = RecordingProvider()
    settings = Settings(dry_run=False, caregiver_numbers=["+15550000000"])
    service = NotificationService(settings, provider=provider)

    assert service.send_alert("glass_breaking")[0].ok
    assert service.send_alert("smoke_alarm_beeping")[0].ok
    messages = [message for _, message in provider.messages]
    assert messages[0].startswith("Sound Guardian: 💥 Glass breaking detected.")
    assert messages[1].startswith("Sound Guardian: 🚨 Smoke alarm detected.")
    assert messages[0] != messages[1]


# ------------------------------------------------------------ alert manager
def test_threshold_rejects_low_confidence():
    manager, notifier, led, _ = make_manager()
    decision = manager.handle_detection("thud", 0.5)   # default threshold 0.80
    assert not decision.accepted and decision.event_id == "thud"
    assert not led.shown and not notifier.sent
    manager.stop()


def test_accepted_detection_hits_led_and_queues_sms():
    manager, notifier, led, _ = make_manager()
    decision = manager.handle_detection("Smoke alarm beeping", 0.95)
    assert decision.accepted and decision.led_shown and decision.notified
    assert manager.flush(2)
    assert notifier.sent == [("smoke_alarm_beeping", 0.95)]
    assert led.shown == ["smoke_alarm_beeping"]
    manager.stop()


def test_per_event_cooldown_allows_one_sms_per_window():
    manager, notifier, led, clock = make_manager()
    for _ in range(5):                      # alarm keeps ringing for a few seconds
        manager.handle_detection("smoke_alarm_beeping", 0.9)
        clock.advance(1)
    assert manager.flush(2)
    assert len(notifier.sent) == 1          # one SMS...
    assert len(led.shown) == 5              # ...but the LED is refreshed every time

    clock.advance(61)                       # still ringing after the cooldown -> remind again
    manager.handle_detection("smoke_alarm_beeping", 0.9)
    assert manager.flush(2)
    assert len(notifier.sent) == 2
    manager.stop()


def test_cooldown_is_tracked_per_event_by_default():
    manager, notifier, _, _ = make_manager()
    manager.handle_detection("glass_breaking", 0.9)
    manager.handle_detection("thud", 0.9)
    assert manager.flush(2)
    assert [e for e, _ in notifier.sent] == ["glass_breaking", "thud"]
    manager.stop()


def test_global_cooldown_suppresses_second_event():
    manager, notifier, _, _ = make_manager(global_cooldown_s=10)
    manager.handle_detection("glass_breaking", 0.9)
    manager.handle_detection("thud", 0.9)
    assert manager.flush(2)
    assert [e for e, _ in notifier.sent] == ["glass_breaking"]
    manager.stop()


def test_hits_required_debounces_single_blips():
    manager, notifier, _, clock = make_manager(hits_required=2, hits_window_s=3)
    assert not manager.handle_detection("thud", 0.9).accepted      # 1/2
    clock.advance(5)                                               # window expired
    assert not manager.handle_detection("thud", 0.9).accepted      # 1/2 again
    clock.advance(1)
    assert manager.handle_detection("thud", 0.9).accepted          # 2/2 within 3 s
    assert manager.flush(2)
    assert len(notifier.sent) == 1
    manager.stop()


def test_manual_trigger_bypasses_threshold_but_respects_cooldown():
    manager, notifier, _, _ = make_manager()
    assert manager.trigger("water_rushing_or_spraying").notified
    assert not manager.trigger("water_rushing_or_spraying").notified       # cooldown
    assert manager.trigger("water_rushing_or_spraying", force=True).notified
    assert not manager.trigger("nope").accepted
    assert manager.flush(2)
    assert len(notifier.sent) == 2
    manager.stop()


def test_notifier_exception_does_not_kill_worker():
    class ExplodingNotifier(FakeNotifier):
        def send_alert(self, event_type, confidence=None):
            raise RuntimeError("textbelt down")

    settings = Settings(dry_run=True, led_repeat_s=0)
    manager = AlertManager(settings, ExplodingNotifier(), FakeLed(), clock=FakeClock())
    manager.handle_detection("thud", 0.9)
    assert manager.flush(2)
    assert manager._worker.is_alive()
    manager.stop()


if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} tests passed")
