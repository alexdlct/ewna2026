"""
Evaluate the trained models on the held-out split.

    python evaluate.py                 # test split, every model present in artifacts/
    python evaluate.py --split val --models keras,int8

Reports accuracy, macro F1, per-class precision / recall, confusion matrix,
BACKGROUND false-positive rate (with and without the confidence rejection),
the key confusion pairs, and INT8 inference time. Writes artifacts/metrics.json
and artifacts/confusion_matrix.png.
"""

import argparse
import json
import os
import time

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np

import config as C
from features import crop, log_mel
from train import read_manifest, load_split, eval_windows

KEY_PAIRS = [("GLASS_BREAK", "LOUD_THUD"), ("ALARM", "BACKGROUND"),
             ("KNOWN_VOICE", "UNFAMILIAR_VOICE"), ("LOUD_THUD", "BACKGROUND")]


# ---------------------------------------------------------------------------
def collect(split):
    rows, labels = read_manifest()
    sources = load_split(rows, split)
    if not sources:
        raise SystemExit(f"no sources with split={split!r} in the manifest")
    label_to_idx = {l: i for i, l in enumerate(labels)}
    items = eval_windows(sources, label_to_idx)
    X = np.stack([log_mel(crop(sources[i]["wave"], st)) for i, st, _ in items])
    y = np.array([lab for _, _, lab in items])
    speakers = sorted({s["speaker"] for s in sources if s["label"] == "UNFAMILIAR_VOICE" and s["speaker"]})
    return X, y, labels, speakers


def predict_keras(X):
    import keras
    model = keras.models.load_model(C.MODEL_KERAS)
    return model.predict(X, batch_size=64, verbose=0), None


def predict_tflite(X, path):
    from infer_wav import TFLiteClassifier
    clf = TFLiteClassifier(path, labels=[""] * 0 or None)
    probs, ms = [], []
    for m in X:
        t0 = time.perf_counter()
        probs.append(clf.predict_features(m))
        ms.append((time.perf_counter() - t0) * 1e3)
    return np.stack(probs), float(np.mean(ms))


# ---------------------------------------------------------------------------
def metrics(probs, y, labels, threshold):
    from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
    n = len(labels)
    pred = probs.argmax(1)
    conf = probs.max(1)
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=range(n), zero_division=0)
    cm = confusion_matrix(y, pred, labels=range(n))

    out = {
        "n_windows": int(len(y)),
        "accuracy": float((pred == y).mean()),
        "macro_f1": float(f1_score(y, pred, labels=range(n), average="macro", zero_division=0)),
        "per_class": {labels[i]: {"precision": float(p[i]), "recall": float(r[i]),
                                  "f1": float(f[i]), "support": int(s[i])} for i in range(n)},
        "confusion_matrix": cm.tolist(),
        "confusion_labels": labels,
        "rejection_threshold": threshold,
        "unknown_rate": float((conf < threshold).mean()),
    }
    if "BACKGROUND" in labels:
        b = labels.index("BACKGROUND")
        bg = y == b
        if bg.any():
            fp = pred[bg] != b
            out["background_fpr"] = float(fp.mean())
            out["background_fpr_with_rejection"] = float((fp & (conf[bg] >= threshold)).mean())
    pairs = {}
    for a, c in KEY_PAIRS:
        if a in labels and c in labels:
            ia, ic = labels.index(a), labels.index(c)
            pairs[f"{a}->{c}"] = int(cm[ia, ic])
            pairs[f"{c}->{a}"] = int(cm[ic, ia])
    out["key_confusions"] = pairs
    return out


def print_report(name, m, labels):
    print(f"\n=== {name}: {m['n_windows']} windows ===")
    print(f"accuracy {m['accuracy']:.3f}   macro F1 {m['macro_f1']:.3f}   "
          f"unknown rate @{m['rejection_threshold']:.2f}: {m['unknown_rate']:.3f}")
    if "background_fpr" in m:
        print(f"BACKGROUND false-positive rate: {m['background_fpr']:.3f} raw, "
              f"{m['background_fpr_with_rejection']:.3f} after rejection")
    if m.get("inference_ms") is not None:
        print(f"inference: {m['inference_ms']:.1f} ms/window")
    print(f"{'class':18s} {'prec':>6s} {'rec':>6s} {'f1':>6s} {'n':>5s}")
    for l in labels:
        c = m["per_class"][l]
        print(f"{l:18s} {c['precision']:6.2f} {c['recall']:6.2f} {c['f1']:6.2f} {c['support']:5d}")
    if m["key_confusions"]:
        print("key confusions (true->pred): " +
              ", ".join(f"{k}={v}" for k, v in m["key_confusions"].items()))
    cm = np.array(m["confusion_matrix"])
    w = max(len(l) for l in labels)
    print("confusion (rows = true):")
    print(" " * (w + 1) + " ".join(f"{l[:6]:>6s}" for l in labels))
    for i, l in enumerate(labels):
        print(f"{l:>{w}s} " + " ".join(f"{v:6d}" for v in cm[i]))


def sweep_thresholds(probs, y, labels, thresholds=(0.5, 0.6, 0.7, 0.8, 0.9)):
    """How the rejection threshold trades BACKGROUND false positives against
    recall of each event class. Pick CONFIDENCE_THRESHOLD from this on the
    validation split, never on test."""
    pred, conf = probs.argmax(1), probs.max(1)
    b = labels.index("BACKGROUND") if "BACKGROUND" in labels else None
    events = [l for l in labels if l != "BACKGROUND"]
    print(f"\n--- threshold sweep ---\n{'thr':>4s} {'bg FPR':>7s} " +
          " ".join(f"{l[:9]:>9s}" for l in events) + "   (recall after rejection)")
    for t in thresholds:
        keep = conf >= t
        row = f"{t:4.2f} "
        if b is not None:
            bg = y == b
            row += f"{float(((pred != b) & keep)[bg].mean()):7.3f} " if bg.any() else f"{'-':>7s} "
        for l in events:
            i = labels.index(l)
            m = y == i
            row += f"{float(((pred == i) & keep)[m].mean()):9.3f} " if m.any() else f"{'-':>9s} "
        print(row)


def simulate_runtime(split, model_path):
    """Run the real streaming decision logic (infer_wav.EventDecider) over every
    clip of a split and count ANNOUNCED events. For BACKGROUND clips that is the
    false-alarm rate per minute, the number a demo actually lives or dies by."""
    from collections import Counter
    from features import crop, strided_starts
    from infer_wav import EventDecider, TFLiteClassifier

    rows, labels = read_manifest()
    sources = load_split(rows, split)
    clf = TFLiteClassifier(model_path)
    settings = [(t, imm) for t in (0.6, 0.7, 0.8) for imm in (0.9, 1.01)]
    print(f"\n--- runtime simulation on {split} ({model_path.name}) ---")
    print("thr / transient-immediate   bg false announcements per min   detected clips per class")
    for thr, imm in settings:
        C.TRANSIENT_IMMEDIATE_CONFIDENCE = imm
        false_n, bg_secs, hits = 0, 0.0, Counter()
        totals = Counter(s["label"] for s in sources)
        for s in sources:
            decider = EventDecider(labels, thr)
            got = set()
            for st in strided_starts(len(s["wave"]), C.STRIDE_S):
                probs, _ = clf.predict_window(crop(s["wave"], st))
                d = decider.update(probs, st / C.SAMPLE_RATE)
                if d.announce:
                    got.add(d.event)
            if s["label"] == "BACKGROUND":
                false_n += len(got)
                bg_secs += len(s["wave"]) / C.SAMPLE_RATE
            elif s["label"] in got:
                hits[s["label"]] += 1
        per_min = false_n / (bg_secs / 60) if bg_secs else float("nan")
        imm_txt = "off" if imm > 1 else f"{imm:.2f}"
        det = "  ".join(f"{l[:5]} {hits[l]}/{totals[l]}" for l in labels if l != "BACKGROUND" and totals[l])
        print(f"{thr:.2f} / {imm_txt:4s}   {per_min:8.1f}                         {det}")
    C.TRANSIENT_IMMEDIATE_CONFIDENCE = 0.90


def plot_confusions(results, labels, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(4.5 * n, 4.2), squeeze=False)
    for ax, (name, m) in zip(axes[0], results.items()):
        cm = np.array(m["confusion_matrix"])
        ax.imshow(cm, cmap="Blues")
        ax.set_title(f"{name}  acc={m['accuracy']:.2f}")
        ax.set_xticks(range(len(labels)), [l[:8] for l in labels], rotation=45, ha="right")
        ax.set_yticks(range(len(labels)), [l[:8] for l in labels])
        ax.set_xlabel("predicted")
        ax.set_ylabel("true")
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Evaluate models on a held-out split")
    ap.add_argument("--split", choices=["test", "val"], default="test")
    ap.add_argument("--models", default="keras,float,int8", help="comma list of keras,float,int8")
    ap.add_argument("--threshold", type=float, default=C.CONFIDENCE_THRESHOLD)
    ap.add_argument("--sweep", action="store_true", help="print FPR / recall for several thresholds")
    ap.add_argument("--simulate", action="store_true",
                    help="run the streaming decider over every clip: false announcements per minute")
    args = ap.parse_args()

    X, y, labels, speakers = collect(args.split)
    print(f"{args.split}: {len(y)} windows, classes {labels}")
    if speakers:
        print(f"UNFAMILIAR_VOICE speakers in this split: {speakers}")

    available = {"keras": C.MODEL_KERAS, "float": C.MODEL_FLOAT_TFLITE, "int8": C.MODEL_INT8_TFLITE}
    results = {}
    for name in [m.strip() for m in args.models.split(",")]:
        path = available.get(name)
        if path is None or not path.exists():
            print(f"skipping {name}: {path} not found")
            continue
        probs, ms = predict_keras(X) if name == "keras" else predict_tflite(X, path)
        from infer_wav import apply_prior
        probs = apply_prior(probs, labels)          # same deployment prior the decider uses
        m = metrics(probs, y, labels, args.threshold)
        m["inference_ms"] = ms
        results[name] = m
        print_report(name, m, labels)
        if args.sweep:
            sweep_thresholds(probs, y, labels)
    if not results:
        raise SystemExit("no models evaluated")

    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    plot_confusions(results, labels, C.CONFUSION_PNG)
    payload = {"split": args.split, "classes": labels, "n_windows": int(len(y)),
               "unfamiliar_voice_speakers": speakers, "models": results}
    C.METRICS_JSON.write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {C.METRICS_JSON}\nwrote {C.CONFUSION_PNG}")
    if args.simulate and "int8" in results:
        simulate_runtime(args.split, C.MODEL_INT8_TFLITE)


if __name__ == "__main__":
    main()
