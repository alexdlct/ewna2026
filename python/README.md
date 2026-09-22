# Notification System — Linux-side service (Arduino UNO Q)

Privacy-preserving emergency-sound alerts. Everything in this folder runs on the
UNO Q's Qualcomm/Debian side inside **Arduino App Lab**. Raw audio never leaves
the board; only the event id (e.g. `smoke_alarm_beeping`) crosses the Bridge to
the MCU and only a fixed alert sentence goes out over SMS.

```
microphone ─► classifier ─► AlertManager ─┬─► LED matrix   (Bridge.call "show_emergency")
                          threshold        └─► Notification (Textbelt SMS / optional e-mail)
                          debounce
                          cooldown
```

## Files

| file | job |
|---|---|
| `main.py` | entrypoint (App Lab `python/main.py`); CLI for demo / one-shot triggers; Bridge endpoints |
| `events.py` | the eight event ids, thresholds, LED icon names, SMS text, label normalisation |
| `alert_manager.py` | confidence threshold → optional N-hit debounce → LED (throttled) → SMS (cooldown); background sender |
| `notification_service.py` | `NotificationService().send_alert(event)` — Textbelt SMS + optional SMTP e-mail |
| `providers/textbelt.py` | Textbelt HTTP API transport |
| `led_bridge.py` | Router Bridge wrapper; logs instead of failing when off-board |
| `classifier.py` | classifier interface, scripted demo classifier, skeleton for the real model |
| `config.py` | all settings from env / `.env` |
| `test_notification.py` | Step 1: real Textbelt smoke test with a hard-coded event |
| `test_offline.py` | unit tests, no network / board needed |

## Quick start

```bash
cd python
cp .env.example .env            # fill in Textbelt key + caregiver number
pip install -r requirements.txt

python tests/test_offline.py                          # logic only, no network
python tests/test_notification.py --all --dry-run     # all eight labels validated, nothing sent
ALERT_DRY_RUN=0 python tests/test_notification.py     # ONE real SMS: smoke_alarm_beeping
python main.py --demo --dry-run                 # full pipeline with scripted detections
ALERT_DRY_RUN=0 python main.py --trigger thud   # one real end-to-end alert (LED + SMS)
python main.py                                  # service mode
```

In App Lab: create the app, drop these files into its `python/` folder (App Lab
installs `requirements.txt`), put the secrets in `python/.env`, run. Because
`.env` is git-ignored, only `.env.example` is committed.

### Definition-of-done mapping

| checklist item | how it's covered |
|---|---|
| Textbelt credentials loaded securely | env vars / git-ignored `.env`; service refuses to start live with none configured |
| Recipient configured | `CAREGIVER_PHONE_NUMBER` uses E.164 format (for example, `+15555555555`) |
| SMS reaches test phone | `python test_notification.py` prints the Textbelt message id |
| All eight labels supported | `test_notification.py --all`, `test_offline.py` |
| Invalid labels rejected cleanly | `ValueError` before any network I/O (tested) |
| Secrets excluded from git | `.gitignore` |

## How detections get in

`AlertManager.handle_detection(label, confidence)` is the single entry point. The
label can be the snake_case id, the human name from the classifier spec
("Glass breaking (Dropped item)", "Security alarm/siren"…), or the class index
(order = `events.CLASS_ORDER`, same order as the spec). Anything else
(background, silence, dog bark) is ignored — so emit the top class for every
window and let the manager filter.

Pick where the classifier lives with `CLASSIFIER=`:

* `bridge` (default) — model runs on the MCU (or any other process) and calls
  `Bridge.call("report_detection", label, confidence)`. No Python classifier starts.
* `model` — fill in `ModelClassifier.load_model()` / `predict()` in `classifier.py`; the
  mic loop (16 kHz, 1 s windows, 0.5 s hop) is already written.
* `scripted` — replays `DEMO_SCRIPT` (also `main.py --demo`).

## Bridge contract with the sketch

Python provides: `report_detection(label, confidence) -> bool`, `test_alert(event_id) -> bool`.
Python calls: `show_emergency(event_id)`, `clear_emergency()`.

```cpp
#include <Arduino_RouterBridge.h>
#include "icons.h"          // one frame per event id

void showEmergency(String eventId) {
  // map eventId -> icon frame + RGB colour, start blinking
}
void clearEmergency() { /* back to idle */ }

void setup() {
  Bridge.begin();
  Bridge.provide("show_emergency", showEmergency);
  Bridge.provide("clear_emergency", clearEmergency);
}

void loop() {
  // if the classifier runs here:
  // Bridge.call("report_detection", "smoke_alarm_beeping", 0.93f);
}
```

Icon names / colour hints per event (`main.py --list-events`):

| event id | icon | RGB hint |
|---|---|---|
| `smoke_alarm_beeping` | fire | red |
| `carbon_monoxide_alarm` | skull | purple |
| `glass_breaking` | shatter | white |
| `screaming_or_yelling_for_help` | sos | red |
| `water_rushing_or_spraying` | droplet | blue |
| `thud` | exclamation | amber |
| `security_alarm_or_siren` | danger | red |
| `electrical_buzzing_or_sparking` | lightning | yellow |

The 8×13 matrix is single-colour; the colour hints are for the four on-board RGB LEDs.

## Alert policy (answers to the open questions)

* **Threshold** — per-event defaults in `events.py` (0.70 tonal alarms, 0.75 glass/voice/electrical,
  0.80 thud/water since those are the false-positive magnets). Override with
  `ALERT_THRESHOLD` or `THRESHOLD_<EVENT_ID>`.
* **Debounce** — `HITS_REQUIRED=2` + `HITS_WINDOW_SECONDS=3` requires two positive windows
  before alerting. Off by default (`1`). Worth turning on for `thud` once you see real data.
* **Cooldown** — tracked **per event type** (`EVENT_COOLDOWN_SECONDS=60`): a smoke alarm
  ringing for 20 s sends one SMS; the LED keeps refreshing. A different event (glass then thud)
  still alerts. Add `GLOBAL_COOLDOWN_SECONDS` if you also want a floor between *any* two SMS.
  After the cooldown a still-ringing alarm sends a reminder.
* **E-mail** — implemented, off until `SMTP_HOST`, `EMAIL_FROM`, `EMAIL_TO` are set.
* **Textbelt** — set `TEXTBELT_API_KEY` and one or more caregiver numbers. For a
  quota-free API check, Textbelt supports appending `_test` to the key.
  Bodies with emoji may use more SMS segments; `SMS_PLAIN_TEXT=1` strips the emoji.

## Runtime notes

* Textbelt/SMTP calls run on a worker thread; a slow or failing network never blocks the audio loop.
* Network errors are logged and returned as `NotificationResult(ok=False, error=...)`, never raised.
* `Bridge.call` failures (MCU not flashed yet, method missing) are logged and ignored.
* `ALERT_DRY_RUN=1` logs the exact message that would go out — use it for every demo rehearsal.
