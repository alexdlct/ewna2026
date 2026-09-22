"""
Offline regression test: synthetic sounds -> detectors. No mic, no Arduino.

    python test_detectors.py                 # pass/fail per class
    python test_detectors.py --verbose       # also show every event emitted
    python test_detectors.py --write-wavs clips   # dump the clips as WAV files

The clips are crude stand-ins for the real sounds, not recordings. They are
here to catch regressions when thresholds in config.py change: if a threshold
edit silences a whole class, this fails immediately. Passing here does NOT
mean the detector works in the demo room -- only calibration with the real
microphone proves that.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C                      # noqa: E402
from audio_processor import AudioProcessor   # noqa: E402

SR = C.SAMPLE_RATE
rng = np.random.default_rng(0)


# ---------------------------------------------------------------------------
# Synthetic signals
# ---------------------------------------------------------------------------
def silence(sec):
    return rng.normal(0, 0.001, int(sec * SR)).astype(np.float32)


def tone(sec, hz, amp=0.2):
    t = np.arange(int(sec * SR)) / SR
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def burst(sec, amp, lo, hi, decay=0.08):
    """Decaying noise burst band-limited to [lo, hi] Hz."""
    n = int(sec * SR)
    spec = np.fft.rfft(rng.normal(0, 1, n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    x /= np.max(np.abs(x)) + 1e-9
    return (amp * x * np.exp(-np.arange(n) / (decay * SR))).astype(np.float32)


def alarm(sec=1.5):
    """Repeating 3.1 kHz beep, like a smoke alarm."""
    out, total = [], 0
    while total < sec * SR:
        out += [tone(0.25, 3100), silence(0.1)]
        total = sum(len(x) for x in out)
    return np.concatenate(out)


def thud():
    return burst(0.3, 0.6, 40, 400)


def footsteps(n=5, gap=0.45):
    return np.concatenate([np.concatenate([burst(0.15, 0.15, 40, 400), silence(gap)])
                           for _ in range(n)])


def glass():
    return burst(0.4, 0.7, 2500, 8000)


def voice(sec=1.2):
    """Pulse train through wandering formants. Crude, but it moves the band
    ratios around the way speech does, which is what the detector keys on."""
    n = int(sec * SR)
    t = np.arange(n) / SR
    f0 = 120 + 30 * np.sin(2 * np.pi * 3 * t)
    phase = np.cumsum(f0) / SR
    src = np.zeros(n)
    src[np.where(np.diff(np.floor(phase)) > 0)[0]] = 1.0

    out = np.zeros(n)
    chunk = int(0.04 * SR)
    for i in range(0, n - chunk, chunk // 2):
        spec = np.fft.rfft(src[i:i + chunk] * np.hanning(chunk))
        f = np.fft.rfftfreq(chunk, 1 / SR)
        f1, f2 = 400 + 400 * rng.random(), 1200 + 1200 * rng.random()
        shape = np.exp(-((f - f1) / 150) ** 2) + 0.6 * np.exp(-((f - f2) / 250) ** 2)
        out[i:i + chunk] += np.fft.irfft(spec * shape, chunk)
    out /= np.max(np.abs(out)) + 1e-9
    return (0.25 * out).astype(np.float32)


def hiss(sec=1.0):
    """Steady broadband noise, like a fan. Should be UNKNOWN, not a class."""
    return rng.normal(0, 0.05, int(sec * SR)).astype(np.float32)


CASES = [
    ("alarm", "ALARM", alarm),
    ("glass", "GLASS_BREAK", glass),
    ("thud", "FALL_THUD", thud),
    ("footsteps", "FOOTSTEPS", footsteps),
    ("voice", "VOICE", voice),
    ("hiss", "UNKNOWN", hiss),
    ("silence", None, lambda: silence(1.0)),
]


# ---------------------------------------------------------------------------
def build(signal_fn):
    """Signal padded with lead-in and trailing silence."""
    return np.concatenate([silence(1.0), signal_fn(), silence(2.5)])


def run_case(audio):
    processor = AudioProcessor()
    events = []
    for i in range(0, len(audio), C.HOP_SIZE):
        events += [(e, round(s, 2)) for e, s, _ in processor.push(audio[i:i + C.HOP_SIZE])]
    return events


def main():
    ap = argparse.ArgumentParser(description="Offline detector regression test")
    ap.add_argument("--verbose", action="store_true", help="show every event emitted")
    ap.add_argument("--write-wavs", metavar="DIR", default=None,
                    help="also write each clip as a WAV for --wav / speaker testing")
    args = ap.parse_args()

    if args.write_wavs:
        try:
            import soundfile as sf
        except ImportError:
            print("soundfile is required for --write-wavs: pip install soundfile")
            raise SystemExit(1)
        os.makedirs(args.write_wavs, exist_ok=True)

    failures = 0
    for name, expected, fn in CASES:
        audio = build(fn)
        events = run_case(audio)
        detected = [e for e, _ in events if e != "IDLE"]
        first = detected[0] if detected else None

        if expected is None:
            ok = not detected
            want = "no events"
        else:
            ok = first == expected
            want = expected

        failures += not ok
        print(f"{name:10s} expect {want:12s} got {str(first):12s} {'OK' if ok else 'FAIL'}")
        if args.verbose:
            print(f"           events: {events}")

        if args.write_wavs:
            path = os.path.join(args.write_wavs, f"{name}.wav")
            sf.write(path, audio, SR)
            print(f"           wrote {path}")

    print("ALL OK" if not failures else f"{failures} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
