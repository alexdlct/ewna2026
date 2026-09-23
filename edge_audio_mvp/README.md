# edge_audio_mvp — TinyAudioNet sound classifier

Implements `CLAUDE_MVP_AUDIO_CLASSIFIER.md`: a small depthwise-separable CNN on
log-Mel spectrograms, trained on the PC from local ESC-50 plus our own
recordings, exported to INT8 TensorFlow Lite and run on the Arduino UNO Q.

```
ESC-50 + custom_data ─► prepare_data ─► train ─► evaluate ─► quantize ─► model_int8.tflite
                                                                             │
             mic on UNO Q ─► unoq_stream (2 s window / 0.5 s stride) ◄───────┘
                                  └─► rejection + confirmation ─► CSV log ─► Sound Guardian event id
```

Classes (model output order, saved to `artifacts/labels.txt`):
`BACKGROUND GLASS_BREAK ALARM LOUD_THUD KNOWN_VOICE UNFAMILIAR_VOICE`.
`UNKNOWN` is an application state (confidence below threshold), not a class.

## Files

| file | job |
|---|---|
| `config.py` | every setting: paths, classes, ESC-50 mapping, features, model, training, inference |
| `prepare_data.py` | ESC-50 folds + custom recordings → `artifacts/manifest.csv`, `labels.txt`, 16 kHz cache |
| `features.py` | audio loading, resampling, windowing, log-Mel (numpy; shared by training and the board) |
| `model.py` | TinyAudioNet |
| `train.py` | on-the-fly windows + augmentation, AdamW, early stopping → `artifacts/model.keras` |
| `evaluate.py` | accuracy, macro F1, per-class P/R, confusion matrix, background FPR → `metrics.json`, `confusion_matrix.png` |
| `quantize.py` | `model_float.tflite`, `model_int8.tflite` (+ INT8 accuracy check) |
| `infer_wav.py` | classify a file; also holds `TFLiteClassifier` and `EventDecider` for the board |
| `unoq_stream.py` | streaming inference on the UNO Q, CSV detection log, optional serial to a UNO R4 |
| `logs/experiments.csv` | one row per training run |

## Run (development PC)

```
pip install -r requirements.txt

# 1. baseline: GLASS_BREAK / ALARM / BACKGROUND from ESC-50 only
python prepare_data.py --experiment baseline      # ESC-50 root defaults to ../dataset/ESC-50-master
python train.py --name baseline
python evaluate.py                                # test = ESC-50 fold 5
python quantize.py
python infer_wav.py ../dataset/ESC-50-master/audio/1-100038-A-14.wav --verbose

# 2. full: add our recordings (see "Recording" below), then
python prepare_data.py --experiment full
python train.py --name full
python evaluate.py && python quantize.py
```

`prepare_data.py` never downloads ESC-50; pass `--esc50-root` if it lives
elsewhere. It only reads the audio and writes 16 kHz copies to
`artifacts/cache/` (gitignored). Set `EDGE_AUDIO_ARTIFACTS=some/dir` to keep
several experiments side by side.

## Current results (six classes, INT8, 53k params, shipped 2026-09-23)

Training data: ESC-50 (glass, clock alarm, siren, 32 background categories),
43 phone-recorded thuds, one 4.5-min known-voice take (split by time), two
teammates + 40 LibriSpeech speakers as unfamiliar voices.

Test = ESC-50 fold 5 + held-out custom recordings: 6 thuds, the last 15 % of
the known-voice take, and five speakers the model never heard (four
LibriSpeech, one phone-recorded teammate).

Per-window, with the KNOWN_VOICE prior applied, before the threshold:

| class | precision | recall | windows |
|---|---|---|---|
| BACKGROUND | 0.98 | 0.89 | 1024 |
| GLASS_BREAK | 0.21 | 1.00 | 10 |
| ALARM | 0.68 | 0.72 | 72 |
| LOUD_THUD | 0.29 | 0.95 | 19 |
| KNOWN_VOICE | 0.76 | 0.78 | 40 |
| UNFAMILIAR_VOICE | 0.98 | 0.99 | 567 |

What the demo actually sees, through the streaming decider
(`evaluate.py --simulate`, clip-level, background = 21 min of ESC-50 noise,
which is far busier than a quiet room):

| threshold | false announcements / min | glass | alarm | thud | known | unfamiliar |
|---|---|---|---|---|---|---|
| 0.60 | 1.4 | 8/8 | 12/16 | 5/6 | 1/1 | 5/5 |
| **0.70** | **0.9** | **8/8** | **12/16** | **5/6** | **1/1** | **5/5** |
| 0.80 | 0.7 | 8/8 | 12/16 | 5/6 | 1/1 | 5/5 |

Notes:
- Unfamiliar voice generalizes: 559 of 567 windows from five never-heard
  speakers, and the phone-recorded teammate held out for test was called
  UNFAMILIAR in 88 of 91 windows and KNOWN in none. That last number is the
  one to watch after every retrain (see the channel trap above).
- Known voice is the weakest voice number (31 of 40 windows on the tail of
  the take, 8 called unfamiliar) because there is exactly one take of one
  person. A second recording session of the enrolled person is the fix.
  `CLASS_PRIOR` (x3 on KNOWN_VOICE) is what lifts it from 0.50 to 0.78; it
  flips 0 windows of the held-out phone stranger and 4 of 567 overall.
- The alarm misses are ESC-50 *sirens* (5/8); clock alarms, the closest
  thing to a smoke alarm, are 7/8. Recording the real demo alarm into
  `custom_data/alarm/` is the fix.
- Glass / thud precision looks terrible per-window only because 10-19 event
  windows sit against 1024 background windows; the false-announcement rate is
  the honest number. Remaining false thuds are footsteps, engines and car
  horns; false glass is dripping water and rain; false alarms are vacuum
  cleaner, wind and bells. `custom_data/background/` recorded in the demo
  room is what brings that rate down.
- Calibration (validation): windows at confidence >= 0.80 are right 97-100 %
  of the time; 0.70-0.80 about two thirds; below 0.70 a coin flip.
- INT8 matches float within 0.2 points; 0.7 ms per window on the PC.
- `artifacts/model.keras` is not shipped for this model: it was overwritten
  by an aborted follow-up run. Retraining from scratch with this config
  takes ~12 min and reproduces the same setup.

`train.py` records every run in `logs/experiments.csv`.

## Recording custom data

```
custom_data/
├── loud_thud/          40–80 clips: dropped backpack / book / shoe, chair bump …   (nobody falls)
├── known_voice/        ONE enrolled person, 5–10 min natural speech, varied distance / volume
├── unfamiliar_voice/   one SUB-FOLDER PER SPEAKER, ≥3 speakers, 1–3 min each
├── alarm/              20–40 clips of the demo alarm played back through the real mic
├── glass_break/        optional 10–30 playback clips (no real glass)
└── background/         3–5 min of the actual room: talk, chairs, typing, HVAC, silence
```

Any format / sample rate works, including `.m4a` phone voice memos (decoded
with PyAV). Splits are by *recording*, never by window,
so overlapping windows from one file never land on both sides. A single
recording longer than 45 s (a long voice take) is cut by time into contiguous
first-70 % / next-15 % / last-15 % segments instead. With three or
more unfamiliar speakers, one whole speaker (last alphabetically, or
`UNFAMILIAR_TEST_SPEAKER` in config) is held out for test. That is the only
honest measure of unfamiliar-speaker detection. With fewer speakers the
script says so, and you should not claim it.

Voice recordings of teammates are personal data: `custom_data/**` audio is
gitignored on purpose.

### Extra unfamiliar speakers from LibriSpeech

Three teammates are not enough for the model to learn "any voice that is not
the enrolled person"; it memorizes those three. `prepare_data.py` therefore
also pulls in LibriSpeech read speech (CC BY 4.0) as `UNFAMILIAR_VOICE` when
it finds it, 2 minutes per speaker, with whole speakers held out for val and
test. Your own held-out custom speaker stays the real-world check.

```
mkdir -p ../dataset/LibriSpeech && cd ../dataset/LibriSpeech
curl -L -O https://www.openslr.org/resources/12/dev-clean.tar.gz   # 337 MB, 40 speakers
tar -xzf dev-clean.tar.gz && rm dev-clean.tar.gz                     # -> LibriSpeech/dev-clean/<speaker>/...
```

`--librispeech-root` points elsewhere, `--no-librispeech` disables it. Adding
`test-clean.tar.gz` the same way gives 40 more speakers.

Watch the channel trap: the known voice is a phone recording, LibriSpeech is
clean studio audio, so a model could learn "phone = known person". Training
therefore draws windows from our own long takes at 4x the LibriSpeech rate
(`CUSTOM_LONG_WINDOWS_PER_S` vs `LONG_SOURCE_WINDOWS_PER_S`), and the real
check is the held-out *phone-recorded* stranger in `evaluate.py`: if that
speaker is called KNOWN_VOICE, the trap has sprung and you need more
phone-recorded strangers and room background.

## Deploy to the UNO Q

```
sudo apt install libportaudio2
pip install numpy soundfile sounddevice tflite-runtime     # or ai-edge-litert
scp config.py features.py infer_wav.py unoq_stream.py artifacts/model_int8.tflite artifacts/labels.txt  unoq:~/edge/
python unoq_stream.py --list-devices
python unoq_stream.py --device 1
```

Each confirmed prediction is appended to `logs/detections_*.csv`:
`timestamp,event,confidence,top2_class,top2_confidence,rms,inference_ms`.

Decision rules (`config.py`): confidence < `CONFIDENCE_THRESHOLD` (0.70,
picked from the sweep + runtime simulation) → `UNKNOWN`; sustained classes need 2 of
the last 3 windows to agree; glass / thud fire immediately at ≥ 0.90,
otherwise they also need agreement; the same event is not re-announced
within 2 s. Every decision also carries a confidence tier from
`CONFIDENCE_LEVELS`: `HIGH` ≥ 0.95, `MEDIUM` ≥ 0.85, else `LOW`. It is shown
in the printed output (`conf=0.93 (MEDIUM)`) and available as
`Decision.level`; the CSV keeps the raw probability.

Use `python evaluate.py --split val --sweep` to re-pick the threshold after a
retrain, and `python evaluate.py --simulate` to see false announcements per
minute of background through the real streaming decider.

### Sound Guardian service

`python/` (the notification + LED service) expects `(label, confidence)` per
window. `unoq_stream.StreamClassifier.predict()` returns the service's own
event ids (`glass_breaking`, `smoke_alarm_beeping`, `thud`, …) for confirmed
events and the raw class name otherwise, which the service ignores. To wire it
into `python/classifier.py`:

```python
ModelClassifier.WINDOW_S = 2.0
def load_model(self): self._model = StreamClassifier()
def predict(self, window): return self._model.predict(window)
```

`UNFAMILIAR_VOICE` maps to `unfamiliar_voice`, which `python/events.py` does
not define yet; add it there when the alert policy for it is decided.

## Bench demo with the UNO R4 LED sketch

`python unoq_stream.py --port COM5` sends `GLASS / ALARM / FALL / VOICE /
UNKNOWN / IDLE` lines to `lightning/sound_events/sound_events.ino`, the same
protocol the earlier rule-based pipeline used.
