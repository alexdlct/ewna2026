"""
All tunables for the audio MVP live here so they can be changed quickly
during the demo. Threshold values are STARTING GUESSES — calibrate them
with `python main.py --debug --no-serial` (see README.md / handoff §15).
"""

# ---------------------------------------------------------------------------
# Audio capture / FFT
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000       # Hz
CHANNELS = 1
FFT_SIZE = 1024           # samples  (~64 ms frame, ~15.6 Hz/bin)
HOP_SIZE = 256            # samples  (~16 ms between results)
HISTORY_SECONDS = 2.0     # rolling history kept for transient / cadence logic
INPUT_DEVICE = None       # sounddevice index or name substring; None = default mic

# ---------------------------------------------------------------------------
# Frequency bands (Hz). Exactly five, in this order.
# ---------------------------------------------------------------------------
BANDS = [
    (60, 250),      # B1: footsteps, thuds, voice fundamental
    (250, 1000),    # B2: low speech, impacts, doors
    (1000, 3000),   # B3: strong speech content, many alarms
    (3000, 5000),   # B4: alarm harmonics, glass
    (5000, 8000),   # B5: glass / sharp broadband events
]
ANALYSIS_MIN_HZ = 60      # ignore bins below this for flatness / dominant freq
FLATNESS_FLOOR_RATIO = 0.01   # bins below this fraction of mean power are clamped for flatness
                              # (pure tone ~0.01, band-limited noise ~0.1-0.2, white noise ~0.5+)

# ---------------------------------------------------------------------------
# Activity gate + transient detection
# ---------------------------------------------------------------------------
SOUND_ACTIVE_RMS = 0.01        # frames below this RMS are "silence"
TRANSIENT_RMS_RATIO = 4.0      # frame RMS must exceed baseline * this to be a transient
TRANSIENT_MIN_RMS = 0.03       # ...and exceed this absolute floor
TRANSIENT_ONSET_RATIO = 1.5    # ...and be a sudden rise vs. ~50 ms earlier (not a sustained tone)
TRANSIENT_MIN_GAP_S = 0.12     # min spacing between two counted transients
BASELINE_SECONDS = 1.0         # window for the rolling RMS baseline (median)

# ---------------------------------------------------------------------------
# ALARM: tonal, strong dominant peak, stable frequency, sustained
# ---------------------------------------------------------------------------
ALARM_MIN_RMS = 0.03            # alarms are loud; ignore quiet hums/fans
ALARM_MIN_DOMINANT_HZ = 800.0   # alarms are high-pitched (smoke alarms ~3 kHz); rejects mains/fan hum
ALARM_MAX_FLATNESS = 0.05       # flatness below this -> fully tonal
ALARM_MIN_PEAK_RATIO = 40.0     # peak-bin power / mean power; above this -> strong peak
ALARM_FREQ_STABILITY_HZ = 60.0  # std-dev of dominant freq over tonal frames must be below this
ALARM_WINDOW_S = 1.0            # look-back window (alarms beep with gaps, so this spans a few beeps)
ALARM_MIN_DURATION_S = 0.4      # total tonal time inside the window for full score

# ---------------------------------------------------------------------------
# GLASS_BREAK: one large broadband impulse with lots of high-frequency energy
# ---------------------------------------------------------------------------
GLASS_MIN_HIGH_RATIO = 0.35     # (B4 + B5) / total at the transient
GLASS_MIN_FLATNESS = 0.10       # broadband-ish (a tone is ~0.01)
GLASS_MIN_RMS_SPIKE = 0.08      # absolute RMS at the transient
GLASS_RECENT_S = 0.15           # transient must be at most this old

# ---------------------------------------------------------------------------
# FALL_THUD: one large low-frequency impulse, isolated
# ---------------------------------------------------------------------------
FALL_MIN_LOW_RATIO = 0.60       # (B1 + B2) / total at the transient
FALL_MIN_RMS_SPIKE = 0.12       # absolute RMS at the transient
FALL_ISOLATION_S = 0.5          # no other transient within this window before it
FALL_RECENT_S = 0.15

# ---------------------------------------------------------------------------
# FOOTSTEPS: repeated small low-frequency transients with consistent spacing
# ---------------------------------------------------------------------------
STEP_MIN_COUNT = 2
STEP_INTERVAL_RANGE = (0.25, 1.0)   # seconds between steps
STEP_INTERVAL_CONSISTENCY = 0.5     # std(intervals)/mean(intervals) must be below this
STEP_MIN_LOW_RATIO = 0.45           # each step should be low-frequency heavy
STEP_MAX_RMS_SPIKE = FALL_MIN_RMS_SPIKE   # steps are quieter than a fall

# ---------------------------------------------------------------------------
# VOICE: sustained speech-band energy that changes over time and is not a tone
# ---------------------------------------------------------------------------
VOICE_MIN_SPEECH_RATIO = 0.75   # (B1 + B2 + B3) / total
VOICE_MIN_DURATION_S = 0.3      # active this long before full score
VOICE_MIN_SPECTRAL_CHANGE = 0.05  # mean |delta band ratios| across ~100 ms strides
VOICE_CHANGE_STRIDE_HOPS = 6      # ~100 ms stride for the change measure
VOICE_CHANGE_WINDOW_S = 0.3
VOICE_MAX_PEAK_RATIO = 120.0    # above this it looks like a pure tone, not harmonic speech

# ---------------------------------------------------------------------------
# Event selection / temporal confirmation
# ---------------------------------------------------------------------------
MIN_CONFIDENCE = 0.5            # best score below this -> UNKNOWN (if sound active)
UNKNOWN_MIN_RMS = 0.03          # sound must be at least this loud to emit UNKNOWN
UNKNOWN_CONFIRM_FRAMES = 36     # ~0.6 s of unmatched loud sound (gives ALARM/VOICE time to build)
CONFIRM_FRAMES = {              # consecutive hops required before emitting
    "ALARM": 6,                 # ~100 ms (the score already requires ALARM_MIN_DURATION_S of tone)
    "VOICE": 3,
    "FOOTSTEPS": 2,
    "FALL_THUD": 1,
    "GLASS_BREAK": 1,
}
EVENT_COOLDOWN_S = 1.5          # don't re-emit the same event within this window
IMPACT_SUPPRESS_S = 1.0         # after FALL/GLASS, ignore ALARM/VOICE/FOOTSTEPS for this long
IDLE_AFTER_S = 2.0              # send IDLE after this much silence following an event

# ---------------------------------------------------------------------------
# Serial (PC -> Arduino)
# ---------------------------------------------------------------------------
SERIAL_PORT = None              # e.g. "COM5"; None = auto-detect first Arduino port
SERIAL_BAUD = 115200
EVENT_TO_SERIAL = {
    "ALARM": "ALARM",
    "VOICE": "VOICE",
    "FALL_THUD": "FALL",
    "FOOTSTEPS": "STEPS",
    "GLASS_BREAK": "GLASS",
    "UNKNOWN": "UNKNOWN",
    "IDLE": "IDLE",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = "logs"
CSV_COLUMNS = ["timestamp", "event", "score", "rms", "dominant_hz",
               "b1", "b2", "b3", "b4", "b5"]
DEBUG_PRINT_EVERY = 6           # in --debug mode, print features every N hops (~100 ms)
