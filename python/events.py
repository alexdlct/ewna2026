"""
Shared event vocabulary for Sound Guardian (Arduino UNO Q).

Single source of truth for the contract between:
  * the sound classifier      -> produces (label, confidence)
  * the alert manager         -> thresholds + cooldowns
  * the LED-matrix sketch     -> receives the event id over the Router Bridge
  * the notification service  -> SMS / e-mail text

This module has no hardware or network dependencies, so it can be imported
anywhere (tests, tooling, the sketch team's icon generator, ...).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class Severity(str, Enum):
    CRITICAL = "critical"  # life-threatening; notify immediately
    HIGH = "high"          # likely injury or property damage
    MEDIUM = "medium"      # worth a look; higher false-positive risk


@dataclass(frozen=True)
class EventSpec:
    id: str                    # snake_case id used across the whole system
    display_name: str          # human-readable name (matches the classifier spec)
    meaning: str               # what the sound implies
    acoustic_class: str        # signal character, as described by the classifier team
    led_icon: str              # icon name the sketch maps to a frame in icons.h
    rgb_hint: tuple            # (r, g, b) hint for the UNO Q's on-board RGB LEDs
    severity: Severity
    sms_text: str              # alert body; event metadata only, never audio
    default_threshold: float   # minimum confidence to accept a detection


# Order matches the classifier team's class list. If the model emits a class
# index instead of a label, index i maps to CLASS_ORDER[i].
CLASS_ORDER = [
    "smoke_alarm_beeping",
    "carbon_monoxide_alarm",
    "glass_breaking",
    "screaming_or_yelling_for_help",
    "water_rushing_or_spraying",
    "thud",
    "security_alarm_or_siren",
    "electrical_buzzing_or_sparking",
]

_SPECS = [
    EventSpec(
        id="smoke_alarm_beeping",
        display_name="Smoke alarm beeping",
        meaning="Fire or smoke detected",
        acoustic_class="Harmonic / Tonal",
        led_icon="fire",
        rgb_hint=(255, 0, 0),
        severity=Severity.CRITICAL,
        sms_text="Sound Guardian: 🚨 Smoke alarm detected.",
        default_threshold=0.70,
    ),
    EventSpec(
        id="carbon_monoxide_alarm",
        display_name="Carbon monoxide alarm",
        meaning="Dangerous CO levels detected",
        acoustic_class="Harmonic / Tonal",
        led_icon="skull",
        rgb_hint=(160, 0, 255),
        severity=Severity.CRITICAL,
        sms_text="Sound Guardian: ☠️ Carbon monoxide alarm detected.",
        default_threshold=0.70,
    ),
    EventSpec(
        id="glass_breaking",
        display_name="Glass breaking",
        meaning="Broken window, dropped item, or possible intrusion",
        acoustic_class="Percussive + Broadband",
        led_icon="shatter",
        rgb_hint=(255, 255, 255),
        severity=Severity.HIGH,
        sms_text="Sound Guardian: 💥 Glass breaking detected.",
        default_threshold=0.75,
    ),
    EventSpec(
        id="screaming_or_yelling_for_help",
        display_name="Someone screaming or yelling for help",
        meaning="Injury or immediate danger",
        acoustic_class="Vocal / Harmonic (human voice band, male or female)",
        led_icon="sos",
        rgb_hint=(255, 0, 0),
        severity=Severity.CRITICAL,
        sms_text="Sound Guardian: 🆘 Yelling for help detected.",
        default_threshold=0.75,
    ),
    EventSpec(
        id="water_rushing_or_spraying",
        display_name="Water rushing or spraying",
        meaning="Burst pipe, flooding, or overflowing fixture",
        acoustic_class="Broadband / Noise-like",
        led_icon="droplet",
        rgb_hint=(0, 90, 255),
        severity=Severity.MEDIUM,
        sms_text="Sound Guardian: 💧 Possible water leak detected.",
        default_threshold=0.80,  # noise-like; easy to confuse with a shower or fan
    ),
    EventSpec(
        id="thud",
        display_name="Thud",
        meaning="Someone falling or an object collapsing",
        acoustic_class="Percussive / Impulsive",
        led_icon="exclamation",
        rgb_hint=(255, 170, 0),
        severity=Severity.HIGH,
        sms_text="Sound Guardian: ⚠️ Possible fall or heavy impact detected.",
        default_threshold=0.80,  # impulsive; doors and dropped items look similar
    ),
    EventSpec(
        id="security_alarm_or_siren",
        display_name="Security alarm / siren",
        meaning="Break-in or security system activation",
        acoustic_class="Harmonic / Tonal",
        led_icon="danger",
        rgb_hint=(255, 0, 40),
        severity=Severity.HIGH,
        sms_text="Sound Guardian: 🚨 Security alarm detected.",
        default_threshold=0.70,
    ),
    EventSpec(
        id="electrical_buzzing_or_sparking",
        display_name="Electrical buzzing or sparking",
        meaning="Possible electrical malfunction or short circuit",
        acoustic_class="Harmonic + Percussive",
        led_icon="lightning",
        rgb_hint=(255, 220, 0),
        severity=Severity.HIGH,
        sms_text="Sound Guardian: ⚡ Possible electrical hazard detected.",
        default_threshold=0.75,
    ),
    EventSpec(
    id="loud_sound",
    display_name="Loud sound",
    meaning="Sound exceeded the configured volume threshold",
    acoustic_class="Volume threshold",
    led_icon="danger",
    rgb_hint=(255, 170, 0),
    severity=Severity.MEDIUM,
    sms_text="Sound Guardian: A loud sound was detected.",
    default_threshold=0.5,),
]

EVENTS: dict[str, EventSpec] = {spec.id: spec for spec in _SPECS}
SUPPORTED_EVENTS = frozenset(EVENTS)

assert list(EVENTS) == CLASS_ORDER, "CLASS_ORDER must match the spec list"


# ---------------------------------------------------------------------------
# Label normalisation
#
# The classifier may emit the human-readable names ("Smoke alarm beeping",
# "Glass breaking (Dropped item)", "thud", ...), the snake_case ids, or a
# class index. normalize_label() maps any of those onto a canonical event id
# and returns None for anything it does not recognise.
# ---------------------------------------------------------------------------

_ALIASES = {
    # smoke
    "smoke_alarm": "smoke_alarm_beeping",
    "fire_alarm": "smoke_alarm_beeping",
    "smoke_detector": "smoke_alarm_beeping",
    # carbon monoxide
    "carbon_monoxide": "carbon_monoxide_alarm",
    "co_alarm": "carbon_monoxide_alarm",
    "co_detector": "carbon_monoxide_alarm",
    # glass
    "glass_breaking_dropped_item": "glass_breaking",
    "glass_break": "glass_breaking",
    "glass_shatter": "glass_breaking",
    "glass_shattering": "glass_breaking",
    # voice
    "someone_screaming_or_yelling_for_help": "screaming_or_yelling_for_help",
    "screaming": "screaming_or_yelling_for_help",
    "scream": "screaming_or_yelling_for_help",
    "yelling": "screaming_or_yelling_for_help",
    "yell_for_help": "screaming_or_yelling_for_help",
    "cry_for_help": "screaming_or_yelling_for_help",
    "help": "screaming_or_yelling_for_help",
    # water
    "water_rushing": "water_rushing_or_spraying",
    "water_spraying": "water_rushing_or_spraying",
    "running_water": "water_rushing_or_spraying",
    "water_leak": "water_rushing_or_spraying",
    # thud
    "fall": "thud",
    "fall_detected": "thud",
    "thump": "thud",
    "bang": "thud",
    "impact": "thud",
    # security
    "security_alarm": "security_alarm_or_siren",
    "security_alarm_siren": "security_alarm_or_siren",
    "siren": "security_alarm_or_siren",
    "burglar_alarm": "security_alarm_or_siren",
    "alarm_siren": "security_alarm_or_siren",
    # electrical
    "electrical_buzzing": "electrical_buzzing_or_sparking",
    "electrical_sparking": "electrical_buzzing_or_sparking",
    "sparking": "electrical_buzzing_or_sparking",
    "buzzing": "electrical_buzzing_or_sparking",
    "electric_arc": "electrical_buzzing_or_sparking",
    "loud": "loud_sound",
}

# Last-resort keyword rules, checked in order. Specific words first so that
# "fire alarm" lands on smoke rather than on the generic "alarm" of security.
_KEYWORD_RULES = [
    (("smoke", "fire"), "smoke_alarm_beeping"),
    (("monoxide", "carbon"), "carbon_monoxide_alarm"),
    (("glass", "shatter"), "glass_breaking"),
    (("scream", "yell", "help", "shout"), "screaming_or_yelling_for_help"),
    (("water", "spray", "flood", "leak"), "water_rushing_or_spraying"),
    (("thud", "thump", "fall", "collapse", "impact"), "thud"),
    (("siren", "security", "intrusion", "burglar"), "security_alarm_or_siren"),
    (("electric", "buzz", "spark", "arcing"), "electrical_buzzing_or_sparking"),
]


def slugify(raw: str) -> str:
    """'Glass breaking (Dropped item)' -> 'glass_breaking_dropped_item'."""
    slug = re.sub(r"[^a-z0-9]+", "_", raw.strip().lower())
    return slug.strip("_")


def event_from_index(index: int) -> Optional[str]:
    """Map a model output index to an event id (None if out of range)."""
    if 0 <= index < len(CLASS_ORDER):
        return CLASS_ORDER[index]
    return None


def normalize_label(raw: Union[str, int, None]) -> Optional[str]:
    """
    Map whatever the classifier emitted onto a canonical event id.

    Accepts snake_case ids, the display names, common aliases, or an int
    class index. Returns None when the label is not a supported event so the
    caller can log and ignore it (e.g. a "background"/"silence" class).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):  # bool is an int subclass; never a class index
        return None
    if isinstance(raw, int):
        return event_from_index(raw)

    slug = slugify(str(raw))
    if not slug:
        return None
    if slug in EVENTS:
        return slug
    if slug in _ALIASES:
        return _ALIASES[slug]
    for keywords, event_id in _KEYWORD_RULES:
        if any(word in slug for word in keywords):
            return event_id
    return None


def describe_events() -> str:
    """Plain-text table of the supported events (used by `main.py --list-events`)."""
    rows = [f"{'event id':32} {'threshold':>9}  {'icon':11} severity   display name"]
    for spec in EVENTS.values():
        rows.append(
            f"{spec.id:32} {spec.default_threshold:>9.2f}  {spec.led_icon:11} "
            f"{spec.severity.value:9}  {spec.display_name}"
        )
    return "\n".join(rows)
