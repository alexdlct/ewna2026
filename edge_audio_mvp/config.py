"""
All settings for the edge audio classifier. Everything else imports from here.

Paths default to this repo's layout (ESC-50 lives in ../dataset/ESC-50-master),
but prepare_data.py accepts --esc50-root / --custom-root overrides.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DEFAULT_ESC50_ROOT = ROOT.parent / "dataset" / "ESC-50-master"
DEFAULT_CUSTOM_ROOT = ROOT / "custom_data"

# EDGE_AUDIO_ARTIFACTS lets you keep several experiments side by side; the
# standardized-audio cache is data-derived, not experiment-derived, so it is
# shared unless EDGE_AUDIO_CACHE is set.
ARTIFACTS = Path(os.environ.get("EDGE_AUDIO_ARTIFACTS", ROOT / "artifacts"))
CACHE_DIR = Path(os.environ.get("EDGE_AUDIO_CACHE", ROOT / "artifacts" / "cache"))
MANIFEST_CSV = ARTIFACTS / "manifest.csv"
LABELS_TXT = ARTIFACTS / "labels.txt"
MODEL_KERAS = ARTIFACTS / "model.keras"
MODEL_FLOAT_TFLITE = ARTIFACTS / "model_float.tflite"
MODEL_INT8_TFLITE = ARTIFACTS / "model_int8.tflite"
METRICS_JSON = ARTIFACTS / "metrics.json"
CONFUSION_PNG = ARTIFACTS / "confusion_matrix.png"

LOGS = ROOT / "logs"
EXPERIMENTS_CSV = LOGS / "experiments.csv"      # one row per training run
RUNTIME_LOG_DIR = LOGS                          # unoq_stream.py detections_*.csv

# ---------------------------------------------------------------------------
# Classes (order is the model output order; saved to labels.txt)
# ---------------------------------------------------------------------------
CLASSES = [
    "BACKGROUND",
    "GLASS_BREAK",
    "ALARM",
    "LOUD_THUD",
    "KNOWN_VOICE",
    "UNFAMILIAR_VOICE",
]
BASELINE_CLASSES = ["BACKGROUND", "GLASS_BREAK", "ALARM"]   # first experiment, ESC-50 only

# ESC-50 category -> class
ESC50_POSITIVE = {
    "glass_breaking": "GLASS_BREAK",
    "clock_alarm": "ALARM",
    "siren": "ALARM",
}
ESC50_BACKGROUND = [
    "door_wood_knock", "door_wood_creaks", "footsteps", "fireworks",
    "thunderstorm", "clock_tick", "vacuum_cleaner", "washing_machine",
    "keyboard_typing", "clapping", "coughing", "laughing",
    "pouring_water", "water_drops",
]
ESC_TEST_FOLD = 5        # official fold held out for test
ESC_VAL_FOLD = 4         # of the remaining folds, this one is validation

# custom_data/<dir> -> class. Voice classes may have one sub-folder per speaker.
CUSTOM_DIRS = {
    "loud_thud": "LOUD_THUD",
    "known_voice": "KNOWN_VOICE",
    "unfamiliar_voice": "UNFAMILIAR_VOICE",
    "alarm": "ALARM",
    "glass_break": "GLASS_BREAK",
    "background": "BACKGROUND",
}
CUSTOM_SPLIT = (0.70, 0.15, 0.15)   # train / val / test, by SOURCE RECORDING
SPLIT_SEED = 42
UNFAMILIAR_TEST_SPEAKER = None      # sub-folder name to hold out entirely; None = last one alphabetically
MIN_SPEAKERS_FOR_HOLDOUT = 3

# ---------------------------------------------------------------------------
# Audio / features
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16000
WINDOW_S = 2.0
WINDOW_SAMPLES = int(WINDOW_S * SAMPLE_RATE)       # 32000
STRIDE_S = 0.5                                     # streaming stride on the UNO Q

N_FFT = 512
WIN_LENGTH = 400        # 25 ms
HOP_LENGTH = 160        # 10 ms
N_MELS = 64
FMIN = 50.0
FMAX = 8000.0
N_FRAMES = 1 + (WINDOW_SAMPLES - WIN_LENGTH) // HOP_LENGTH   # 198
LOG_EPS = 1e-6

# ---------------------------------------------------------------------------
# Windowing
# ---------------------------------------------------------------------------
ESC_TRAIN_CROPS = {"positive": 8, "background": 2}   # random 2 s crops per 5 s clip per epoch
ENERGY_BIAS_PROB = 0.5                               # fraction of crops centred on the loudest moment
ENERGY_JITTER_S = 0.5
CUSTOM_TRAIN_STRIDE_S = 0.5                          # overlapping windows from custom recordings
EVAL_STRIDE_S = 1.0                                  # deterministic windows for val / test
EVAL_POSITIVE_ENERGY_RATIO = 0.5                     # ESC positives: keep windows with >= this x the loudest window's RMS

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
STEM_CHANNELS = 16
BLOCK_CHANNELS = [(32, 1), (64, 2), (96, 2), (128, 2)]   # (pointwise channels, depthwise stride)
DROPOUT = 0.2
MAX_PARAMS = 3_000_000

# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
BATCH_SIZE = 32
EPOCHS = 50
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
EARLY_STOP_PATIENCE = 8
REDUCE_LR_PATIENCE = 3
REDUCE_LR_FACTOR = 0.5

# augmentation (train only)
AUG_GAIN_DB = 6.0
AUG_SHIFT_S = 0.2
AUG_NOISE_PROB = 0.5
AUG_NOISE_SNR_DB = (5.0, 20.0)
AUG_TIME_STRETCH = (0.95, 1.05)     # None to disable
AUG_TIME_STRETCH_PROB = 0.3
SPEC_TIME_MASKS = 2                 # 0..N masks
SPEC_TIME_MASK_MAX = 20             # frames
SPEC_FREQ_MASKS = 2
SPEC_FREQ_MASK_MAX = 8              # mel bins
MIXUP_ALPHA = 0.3
MIXUP_PROB = 0.3                    # fraction of batches mixed; higher values flatten confidences

# ---------------------------------------------------------------------------
# Quantization
# ---------------------------------------------------------------------------
REPRESENTATIVE_SAMPLES = 200
INT8_MAX_ACCURACY_DROP = 0.01       # acceptance: <= 1 percentage point

# ---------------------------------------------------------------------------
# Inference / temporal confirmation
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.60         # below this -> UNKNOWN (tune from validation)
HISTORY = 3                         # keep last N window predictions
CONFIRM_AGREE = 2                   # sustained classes: N of HISTORY must agree
TRANSIENT_IMMEDIATE_CONFIDENCE = 0.90
SUSTAINED_CLASSES = {"ALARM", "KNOWN_VOICE", "UNFAMILIAR_VOICE"}
TRANSIENT_CLASSES = {"GLASS_BREAK", "LOUD_THUD"}
EVENT_COOLDOWN_S = 2.0              # don't re-announce the same event within this window

# class -> Sound Guardian event id (python/events.py). None = not an alert.
# UNFAMILIAR_VOICE has no event id in events.py yet; "unfamiliar_voice" is
# ignored by the service until the notification team adds it.
SOUND_GUARDIAN_EVENT = {
    "GLASS_BREAK": "glass_breaking",
    "ALARM": "smoke_alarm_beeping",
    "LOUD_THUD": "thud",
    "KNOWN_VOICE": None,
    "UNFAMILIAR_VOICE": "unfamiliar_voice",
    "BACKGROUND": None,
    "UNKNOWN": None,
}

# class -> one-word serial message for the UNO R4 LED sketch
# (lightning/sound_events/sound_events.ino), used only with --port.
SERIAL_EVENT = {
    "GLASS_BREAK": "GLASS",
    "ALARM": "ALARM",
    "LOUD_THUD": "FALL",
    "KNOWN_VOICE": None,
    "UNFAMILIAR_VOICE": "VOICE",
    "UNKNOWN": "UNKNOWN",
}
SERIAL_BAUD = 115200
