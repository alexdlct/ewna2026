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

## Baseline results (ESC-50 only, test = fold 5, INT8 model)

| class | precision | recall | windows |
|---|---|---|---|
| BACKGROUND | 0.99 | 0.83 | 448 |
| GLASS_BREAK | 0.17 | 1.00 | 10 |
| ALARM | 0.71 | 0.93 | 72 |

Macro F1 0.67, INT8 identical to float, 0.4 ms per window on the PC. Every
held-out glass and alarm clip triggers; a vacuum cleaner does not. The weak
spot is the spec's first priority: 12.9 % of background windows still pass
the 0.60 threshold as glass or alarm, mostly `water_drops`,
`door_wood_creaks`, `coughing` and `vacuum_cleaner`. That is what the
`custom_data/background/` recordings of the real room and the full class set
are for; re-tune `CONFIDENCE_THRESHOLD` from `evaluate.py --split val` after
each retrain. `train.py` records every run in `logs/experiments.csv`.

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

Any format / sample rate works. Splits are by *recording*, never by window,
so overlapping windows from one file never land on both sides. With three or
more unfamiliar speakers, one whole speaker (last alphabetically, or
`UNFAMILIAR_TEST_SPEAKER` in config) is held out for test. That is the only
honest measure of unfamiliar-speaker detection. With fewer speakers the
script says so, and you should not claim it.

Voice recordings of teammates are personal data: `custom_data/**` audio is
gitignored on purpose.

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

Decision rules (`config.py`): confidence < 0.60 → `UNKNOWN`; sustained
classes need 2 of the last 3 windows to agree; glass / thud fire immediately
at ≥ 0.90, otherwise they also need agreement; the same event is not
re-announced within 2 s.

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
