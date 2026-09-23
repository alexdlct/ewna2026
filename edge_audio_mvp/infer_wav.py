"""
Runtime inference: TFLite model + confidence rejection + temporal confirmation.

    python infer_wav.py path/to/test.wav
    python infer_wav.py path/to/test.wav --model float --verbose

Only numpy + a TFLite interpreter are needed here (no TensorFlow on the UNO Q):
tflite_runtime -> ai_edge_litert -> tensorflow.lite, whichever is installed.
unoq_stream.py reuses TFLiteClassifier and EventDecider from this file.
"""

import argparse
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

import config as C
from features import load_audio, log_mel, rms, strided_starts, crop


# ---------------------------------------------------------------------------
def _interpreter_class():
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter
    except ImportError:
        pass
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter
    except ImportError:
        pass
    import os
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf
    return tf.lite.Interpreter


def read_labels(path=C.LABELS_TXT):
    return [l for l in open(path).read().split("\n") if l.strip()]


class TFLiteClassifier:
    """Wraps a float or full-INT8 .tflite model. predict_* return float32 probabilities."""

    def __init__(self, model_path=C.MODEL_INT8_TFLITE, labels=None, num_threads=2):
        Interpreter = _interpreter_class()
        try:
            self.interp = Interpreter(model_path=str(model_path), num_threads=num_threads)
        except TypeError:                       # older interpreters lack num_threads
            self.interp = Interpreter(model_path=str(model_path))
        self.interp.allocate_tensors()
        self.inp = self.interp.get_input_details()[0]
        self.out = self.interp.get_output_details()[0]
        self.labels = labels or read_labels()
        self.model_path = str(model_path)
        n_out = int(self.out["shape"][-1])
        if n_out != len(self.labels):
            raise ValueError(f"model has {n_out} outputs but labels.txt has {len(self.labels)}")

    def predict_features(self, m):
        x = np.asarray(m, dtype=np.float32)[None]
        if self.inp["dtype"] == np.int8:
            scale, zp = self.inp["quantization"]
            x = np.clip(np.round(x / scale + zp), -128, 127).astype(np.int8)
        self.interp.set_tensor(self.inp["index"], x)
        self.interp.invoke()
        y = self.interp.get_tensor(self.out["index"])[0]
        if self.out["dtype"] == np.int8:
            scale, zp = self.out["quantization"]
            y = (y.astype(np.float32) - zp) * scale
        return y.astype(np.float32)

    def predict_window(self, wave):
        """2 s waveform -> (probs, inference_ms). Timing covers features + model."""
        t0 = time.perf_counter()
        probs = self.predict_features(log_mel(wave))
        return probs, (time.perf_counter() - t0) * 1e3


# ---------------------------------------------------------------------------
def apply_prior(probs, labels):
    """Multiply config.CLASS_PRIOR into the probabilities and renormalize.
    Works on one vector or a [n, classes] array. Identity when no prior is set."""
    q = np.asarray(probs, dtype=np.float32).copy()
    changed = False
    for name, factor in C.CLASS_PRIOR.items():
        if name in labels and factor != 1.0:
            q[..., labels.index(name)] *= factor
            changed = True
    if changed:
        q /= np.maximum(q.sum(axis=-1, keepdims=True), 1e-9)
    return q


def confidence_level(confidence):
    """Map a probability to the tier names in config.CONFIDENCE_LEVELS (HIGH / MEDIUM / LOW)."""
    for floor, name in C.CONFIDENCE_LEVELS:
        if confidence >= floor:
            return name
    return C.CONFIDENCE_LEVELS[-1][1]


@dataclass
class Decision:
    t: float
    label: str               # top class of this window
    confidence: float
    top2_label: str
    top2_confidence: float
    event: Optional[str]     # confirmed class for this window, or None
    announce: bool           # event confirmed and not inside its cooldown

    @property
    def level(self):
        """HIGH / MEDIUM / LOW tier of this window's confidence."""
        return confidence_level(self.confidence)

    def __str__(self):
        s = f"{self.t:7.2f}s  {self.label:16s} {self.confidence:.2f} {self.level:6s} (2nd {self.top2_label} {self.top2_confidence:.2f})"
        if self.event:
            s += f"  -> {self.event}" + ("  ANNOUNCE" if self.announce else "")
        return s


class EventDecider:
    """
    Confidence rejection (< threshold -> UNKNOWN) and temporal confirmation:
      sustained classes  : CONFIRM_AGREE of the last HISTORY windows agree
      transient classes  : immediate if confidence >= TRANSIENT_IMMEDIATE_CONFIDENCE,
                           otherwise the same agreement rule
    """

    def __init__(self, labels, threshold=C.CONFIDENCE_THRESHOLD):
        self.labels = labels
        self.threshold = threshold
        self.history = deque(maxlen=C.HISTORY)
        self.last_announced = {}

    def update(self, probs, t):
        probs = apply_prior(probs, self.labels)
        order = np.argsort(probs)[::-1]
        label, conf = self.labels[order[0]], float(probs[order[0]])
        top2 = (self.labels[order[1]], float(probs[order[1]])) if len(order) > 1 else ("", 0.0)
        accepted = label if conf >= self.threshold else "UNKNOWN"
        self.history.append(accepted)

        event = None
        if label in C.TRANSIENT_CLASSES and conf >= C.TRANSIENT_IMMEDIATE_CONFIDENCE:
            event = label
        elif accepted not in ("UNKNOWN", "BACKGROUND") and self.history.count(accepted) >= C.CONFIRM_AGREE:
            event = accepted

        announce = False
        if event is not None:
            last = self.last_announced.get(event, -1e9)
            if t - last >= C.EVENT_COOLDOWN_S:
                self.last_announced[event] = t
                announce = True
        return Decision(t, label, conf, top2[0], top2[1], event, announce)


# ---------------------------------------------------------------------------
def run_file(path, clf, stride_s=C.STRIDE_S, verbose=False, threshold=C.CONFIDENCE_THRESHOLD):
    x = load_audio(path)
    decider = EventDecider(clf.labels, threshold)
    decisions, ms_all = [], []
    for st in strided_starts(len(x), stride_s):
        w = crop(x, st)
        probs, ms = clf.predict_window(w)
        d = decider.update(probs, st / C.SAMPLE_RATE)
        decisions.append((d, rms(w), ms))
        ms_all.append(ms)
        if verbose or d.announce:
            print(d)
    return decisions, x


def main():
    ap = argparse.ArgumentParser(description="Classify a WAV file window by window")
    ap.add_argument("wav")
    ap.add_argument("--model", choices=["int8", "float"], default="int8")
    ap.add_argument("--stride", type=float, default=C.STRIDE_S)
    ap.add_argument("--threshold", type=float, default=C.CONFIDENCE_THRESHOLD)
    ap.add_argument("--verbose", action="store_true", help="print every window, not just events")
    args = ap.parse_args()

    path = C.MODEL_INT8_TFLITE if args.model == "int8" else C.MODEL_FLOAT_TFLITE
    if not path.exists():
        sys.exit(f"{path} not found; run train.py and quantize.py first")
    clf = TFLiteClassifier(path)
    print(f"model {path.name}  labels {clf.labels}")
    decisions, x = run_file(args.wav, clf, args.stride, args.verbose, args.threshold)

    events = [d for d, _, _ in decisions if d.announce]
    ms = [m for _, _, m in decisions]
    print(f"\n{len(x)/C.SAMPLE_RATE:.1f} s, {len(decisions)} windows, "
          f"inference {np.mean(ms):.1f} ms/window (max {np.max(ms):.1f})")
    if events:
        print("events: " + ", ".join(f"{d.event}@{d.t:.1f}s({d.confidence:.2f} {d.level})" for d in events))
    else:
        top = max(decisions, key=lambda z: z[0].confidence)[0]
        print(f"no confirmed event; most confident window was {top.label} {top.confidence:.2f} at {top.t:.1f}s")


if __name__ == "__main__":
    main()
