# signal_processing — audio MVP

PC-side DSP pipeline from `AUDIO_PROCESSING_HANDOFF.md`:
mic @ 16 kHz → 1024-pt Hann FFT (256 hop) → 5 band energies + RMS / peak /
dominant frequency / spectral flatness → rule-based detectors → CSV log →
serial event name → Arduino LED matrix.

Events: `ALARM`, `VOICE`, `FALL_THUD`, `FOOTSTEPS`, `GLASS_BREAK`, `UNKNOWN`
(serial names: `ALARM VOICE FALL STEPS GLASS UNKNOWN IDLE`).

## Files

| file | role |
|---|---|
| `main.py` | mic stream, main loop, serial output, CLI flags |
| `audio_processor.py` | ring buffer, FFT, bands, features, detectors, temporal confirmation |
| `config.py` | every tunable (sample rate, bands, thresholds, serial port) |
| `logger.py` | CSV event log → `logs/events_<timestamp>.csv` |
| `test_detectors.py` | offline regression test on synthetic sounds |

Arduino side: `../lightning/sound_events/sound_events.ino` (UNO R4 WiFi LED matrix).

## Run

```
pip install -r requirements.txt
python main.py --list-devices          # find the mic index
python main.py --debug --no-serial     # calibration: live features + scores
python main.py                         # demo: auto-detects the Arduino port
python main.py --port COM5 --device 1  # force port / mic
```

## Testing without the Arduino

Nothing here needs the board. With no board attached, `main.py` says so and
runs anyway; the event names it prints are exactly what it would have sent.

**Replay a recording** instead of using the mic. Any sample rate and channel
count works (it mixes to mono and resamples). This is the repeatable way to
tune thresholds against real glass-break or smoke-alarm clips:

```
python main.py --wav clips/glass.wav --no-serial --debug
python main.py --wav clips/glass.wav --realtime      # pace at real speed, e.g. with a board attached
```

**Regression test** on synthetic sounds, no mic and no board:

```
python test_detectors.py                    # pass/fail per class
python test_detectors.py --write-wavs clips # dump the clips as WAVs
```

Run it after any threshold edit. It catches a change that silences a whole
class. It does not prove the detector works in the demo room, because the
clips are crude stand-ins rather than recordings. Only calibration with the
real microphone proves that.

Debug line format (every ~100 ms):

```
rms=0.042 pk=0.31 dom= 1015Hz flat=0.08 pr= 61.2 | B1=0.05 B2=0.10 B3=0.70 B4=0.10 B5=0.05 | ALARM=0.83 VOICE=0.00 FALL_=0.00 FOOTS=0.00 GLASS=0.00 | tr=0
```

`pr` = peak-bin power / mean power (tonality), `tr` = transients in the last 2 s.

## Calibration (handoff §15)

For each class, perform the sound 5×, watch the debug printout, note typical
values, then move the thresholds in `config.py` between the classes:

- **ALARM**: `ALARM_MIN_PEAK_RATIO` (pr), `ALARM_MAX_FLATNESS` (flat), `ALARM_MIN_RMS`, `ALARM_MIN_DOMINANT_HZ` (raise if a fan/hum triggers it).
- **Speech triggering FOOTSTEPS**: raise `STEP_MIN_LOW_RATIO` or `TRANSIENT_RMS_RATIO`.
- **GLASS_BREAK**: `GLASS_MIN_HIGH_RATIO` (B4+B5), `GLASS_MIN_FLATNESS`, `GLASS_MIN_RMS_SPIKE`.
- **FALL_THUD**: `FALL_MIN_LOW_RATIO` (B1+B2), `FALL_MIN_RMS_SPIKE`.
- **FOOTSTEPS**: `STEP_MAX_RMS_SPIKE`, `STEP_INTERVAL_RANGE`, `STEP_MIN_LOW_RATIO`.
- **VOICE**: `VOICE_MIN_SPEECH_RATIO` (B1+B2+B3), `VOICE_MIN_SPECTRAL_CHANGE`.
- If nothing ever fires: lower `MIN_CONFIDENCE`. If transients are missed:
  lower `TRANSIENT_MIN_RMS` / `TRANSIENT_RMS_RATIO`.

Tune with the microphone and room used in the actual demo.
