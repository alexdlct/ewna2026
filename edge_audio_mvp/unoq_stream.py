"""
Streaming inference on the Arduino UNO Q (Linux side): microphone -> 2 s window
every 0.5 s -> INT8 TFLite -> rejection + confirmation -> CSV log (+ optional
serial line to the UNO R4 LED sketch for bench demos).

    python unoq_stream.py                       # default mic, int8 model
    python unoq_stream.py --device 1            # pick the USB mic (see --list-devices)
    python unoq_stream.py --wav clip.wav        # same loop fed from a file, no mic
    python unoq_stream.py --port /dev/ttyACM0   # also send GLASS/ALARM/FALL/... over serial

Board setup:   sudo apt install libportaudio2 && pip install numpy sounddevice soundfile tflite-runtime
               (or `pip install ai-edge-litert` if tflite-runtime has no wheel for the board's Python)
Copy over:     features.py config.py infer_wav.py unoq_stream.py artifacts/model_int8.tflite artifacts/labels.txt

Plugging into the Sound Guardian service (python/classifier.py ModelClassifier):
    ModelClassifier.WINDOW_S = 2.0
    load_model():  self._model = StreamClassifier()
    predict(w):    return self._model.predict(w)     # -> (event_id_or_label, confidence)
"""

import argparse
import csv
import os
import queue
import sys
import time
from datetime import datetime

import numpy as np

import config as C
from features import crop, load_audio, rms, strided_starts
from infer_wav import EventDecider, TFLiteClassifier


class StreamClassifier:
    """Model + decision state in one object. predict() returns Sound Guardian event ids."""

    def __init__(self, model_path=C.MODEL_INT8_TFLITE, threshold=C.CONFIDENCE_THRESHOLD):
        self.clf = TFLiteClassifier(model_path)
        self.decider = EventDecider(self.clf.labels, threshold)
        self.t0 = time.monotonic()

    def step(self, window, t=None):
        """Full decision for one window: (Decision, rms, inference_ms)."""
        t = time.monotonic() - self.t0 if t is None else t
        probs, ms = self.clf.predict_window(window)
        return self.decider.update(probs, t), rms(window), ms

    def predict(self, window):
        """ModelClassifier.predict() contract: (label, confidence). Unmapped classes
        return their own name, which the AlertManager ignores."""
        d, _, _ = self.step(window)
        if d.event and d.announce:
            return C.SOUND_GUARDIAN_EVENT.get(d.event) or d.event, d.confidence
        return d.label, d.confidence


# ---------------------------------------------------------------------------
class DetectionLog:
    COLUMNS = ["timestamp", "event", "confidence", "top2_class", "top2_confidence", "rms", "inference_ms"]

    def __init__(self, log_dir=C.RUNTIME_LOG_DIR):
        os.makedirs(log_dir, exist_ok=True)
        self.path = os.path.join(log_dir, f"detections_{datetime.now():%Y%m%d_%H%M%S_%f}.csv")
        self._f = open(self.path, "w", newline="")
        self._w = csv.writer(self._f)
        self._w.writerow(self.COLUMNS)
        self._f.flush()

    def write(self, d, level, ms):
        self._w.writerow([f"{time.time():.2f}", d.event, f"{d.confidence:.2f}", d.top2_label,
                          f"{d.top2_confidence:.2f}", f"{level:.3f}", f"{ms:.1f}"])
        self._f.flush()

    def close(self):
        self._f.close()


def open_serial(port):
    try:
        import serial
        ser = serial.Serial(port, C.SERIAL_BAUD, timeout=0.1)
        time.sleep(1.5)
        print(f"[serial] {port} @ {C.SERIAL_BAUD}")
        return ser
    except Exception as e:  # noqa: BLE001
        print(f"[serial] could not open {port}: {e}; continuing without it")
        return None


def handle(d, level, ms, log, ser):
    """Log every confirmed prediction; announce (print / serial) once per cooldown."""
    if d.event is None:
        return
    log.write(d, level, ms)
    if not d.announce:
        return
    guardian = C.SOUND_GUARDIAN_EVENT.get(d.event)
    print(f"[event] {d.event:16s} conf={d.confidence:.2f} ({d.level}) 2nd={d.top2_label}:{d.top2_confidence:.2f} "
          f"rms={level:.3f} {ms:.0f}ms" + (f"  -> {guardian}" if guardian else ""))
    msg = C.SERIAL_EVENT.get(d.event)
    if ser is not None and msg:
        try:
            ser.write((msg + "\n").encode("ascii"))
        except Exception as e:  # noqa: BLE001
            print(f"[serial] write failed: {e}")


# ---------------------------------------------------------------------------
def run_mic(sc, log, ser, device, verbose):
    import sounddevice as sd

    hop = int(C.STRIDE_S * C.SAMPLE_RATE)
    blocks = queue.Queue(maxsize=64)

    def cb(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        try:
            blocks.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    ring = np.zeros(C.WINDOW_SAMPLES, dtype=np.float32)
    filled = 0
    print(f"[audio] listening: {C.WINDOW_S:.1f} s window every {C.STRIDE_S:.1f} s (Ctrl-C to stop)")
    with sd.InputStream(samplerate=C.SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=hop, device=device, callback=cb):
        while True:
            block = blocks.get()
            ring = np.roll(ring, -len(block))
            ring[-len(block):] = block
            filled = min(filled + len(block), C.WINDOW_SAMPLES)
            if filled < C.WINDOW_SAMPLES:
                continue
            d, level, ms = sc.step(ring)
            if verbose:
                print(d)
            handle(d, level, ms, log, ser)


def run_wav(sc, log, ser, path, verbose):
    x = load_audio(path)
    print(f"[wav] {path}: {len(x)/C.SAMPLE_RATE:.1f} s")
    for st in strided_starts(len(x), C.STRIDE_S):
        w = crop(x, st)
        d, level, ms = sc.step(w, t=st / C.SAMPLE_RATE)
        if verbose:
            print(d)
        handle(d, level, ms, log, ser)


def main():
    ap = argparse.ArgumentParser(description="UNO Q streaming classifier")
    ap.add_argument("--model", choices=["int8", "float"], default="int8")
    ap.add_argument("--device", default=os.environ.get("MIC_DEVICE"), help="input device index or name")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--wav", help="run the same loop over a file instead of the mic")
    ap.add_argument("--port", help="serial port of a UNO R4 running sound_events.ino")
    ap.add_argument("--threshold", type=float, default=C.CONFIDENCE_THRESHOLD)
    ap.add_argument("--verbose", action="store_true", help="print every window")
    args = ap.parse_args()

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return

    device = args.device
    if device is not None:
        try:
            device = int(device)
        except ValueError:
            pass

    path = C.MODEL_INT8_TFLITE if args.model == "int8" else C.MODEL_FLOAT_TFLITE
    if not path.exists():
        sys.exit(f"{path} not found; run train.py and quantize.py, then copy artifacts/ to the board")
    sc = StreamClassifier(path, args.threshold)
    print(f"[model] {path.name}  labels {sc.clf.labels}")
    log = DetectionLog()
    print(f"[log] {log.path}")
    ser = open_serial(args.port) if args.port else None

    try:
        if args.wav:
            run_wav(sc, log, ser, args.wav, args.verbose)
        else:
            run_mic(sc, log, ser, device, args.verbose)
    except KeyboardInterrupt:
        print("\n[main] stopping")
    finally:
        log.close()
        if ser is not None:
            try:
                ser.write(b"IDLE\n")
                ser.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    main()
