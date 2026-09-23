"""
Build the dataset manifest from local ESC-50 + our custom recordings.

    python prepare_data.py --experiment baseline               # ESC-50 only: GLASS_BREAK / ALARM / BACKGROUND
    python prepare_data.py --experiment full                   # + custom_data classes that have recordings
    python prepare_data.py --esc50-root "D:/ESC-50" --custom-root ./custom_data

What it does
  * validates the ESC-50 root (audio/ + meta/esc50.csv). Never downloads anything.
  * keeps only the ESC-50 categories we use, mapped to our classes
  * splits ESC-50 by official fold (test = fold 5, val = fold 4, train = 1-3)
  * splits custom recordings by SOURCE RECORDING (never by window), 70/15/15,
    holding out one unfamiliar-voice speaker entirely for test when possible
  * standardizes every source to 16 kHz mono float32 into artifacts/cache/*.npy
    (originals are never modified)
  * writes artifacts/manifest.csv and artifacts/labels.txt
"""

import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import config as C
from features import load_audio

AUDIO_EXT = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aiff", ".aif"}


# ---------------------------------------------------------------------------
# ESC-50
# ---------------------------------------------------------------------------
def esc50_sources(root):
    root = Path(root)
    audio_dir, meta = root / "audio", root / "meta" / "esc50.csv"
    if not audio_dir.is_dir() or not meta.is_file():
        sys.exit(f"ESC-50 not found at {root} (need audio/ and meta/esc50.csv). "
                 f"Pass the correct path with --esc50-root. Not downloading.")

    wanted = dict(C.ESC50_POSITIVE)
    wanted.update({cat: "BACKGROUND" for cat in C.ESC50_BACKGROUND})

    sources = []
    with open(meta, newline="") as f:
        for row in csv.DictReader(f):
            label = wanted.get(row["category"])
            if label is None:
                continue
            fold = int(row["fold"])
            split = ("test" if fold == C.ESC_TEST_FOLD
                     else "val" if fold == C.ESC_VAL_FOLD else "train")
            sources.append({
                "source_id": Path(row["filename"]).stem,
                "origin": "esc50",
                "category": row["category"],
                "label": label,
                "split": split,
                "speaker": "",
                "fold": fold,
                "path": audio_dir / row["filename"],
            })
    if not sources:
        sys.exit("ESC-50 metadata has none of the expected categories; is this the official esc50.csv?")
    return sources


# ---------------------------------------------------------------------------
# Custom recordings
# ---------------------------------------------------------------------------
def custom_sources(root):
    root = Path(root)
    sources = []
    for dirname, label in C.CUSTOM_DIRS.items():
        d = root / dirname
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.suffix.lower() not in AUDIO_EXT:
                continue
            rel = p.relative_to(d)
            speaker = rel.parts[0] if len(rel.parts) > 1 else ""
            sources.append({
                "source_id": f"custom/{dirname}/{rel.as_posix()}",
                "origin": "custom",
                "category": dirname,
                "label": label,
                "split": None,
                "speaker": speaker,
                "fold": "",
                "path": p,
            })
    return sources


def _three_way(items, rng):
    """Split a list of sources 70/15/15 (by source), guaranteeing val/test when possible."""
    items = list(items)
    rng.shuffle(items)
    n = len(items)
    if n == 1:
        return items, [], []
    if n == 2:
        return items[:1], items[1:], []
    n_test = max(1, round(n * C.CUSTOM_SPLIT[2]))
    n_val = max(1, round(n * C.CUSTOM_SPLIT[1]))
    return items[n_val + n_test:], items[:n_val], items[n_val:n_val + n_test]


def assign_custom_splits(sources):
    rng = random.Random(C.SPLIT_SEED)
    by_label = defaultdict(list)
    for s in sources:
        by_label[s["label"]].append(s)

    notes = []
    for label, items in by_label.items():
        speakers = sorted({s["speaker"] for s in items if s["speaker"]})
        if label == "UNFAMILIAR_VOICE" and len(speakers) >= C.MIN_SPEAKERS_FOR_HOLDOUT:
            held = C.UNFAMILIAR_TEST_SPEAKER or speakers[-1]
            if held not in speakers:
                sys.exit(f"UNFAMILIAR_TEST_SPEAKER={held!r} not found; speakers: {speakers}")
            rest = [s for s in items if s["speaker"] != held]
            for s in items:
                if s["speaker"] == held:
                    s["split"] = "test"
            rng.shuffle(rest)
            n_val = max(1, round(len(rest) * C.CUSTOM_SPLIT[1]))
            for i, s in enumerate(rest):
                s["split"] = "val" if i < n_val else "train"
            notes.append(f"UNFAMILIAR_VOICE: speaker {held!r} held out entirely for test "
                         f"({len(speakers) - 1} speakers in train/val)")
        else:
            if label == "UNFAMILIAR_VOICE":
                notes.append(f"UNFAMILIAR_VOICE: only {len(speakers)} speaker folder(s); "
                             f"need >= {C.MIN_SPEAKERS_FOR_HOLDOUT} to hold one out. "
                             f"Do NOT claim unfamiliar-speaker generalization from this split.")
            tr, va, te = _three_way(items, rng)
            for s in tr:
                s["split"] = "train"
            for s in va:
                s["split"] = "val"
            for s in te:
                s["split"] = "test"
    return notes


# ---------------------------------------------------------------------------
# Standardize + cache
# ---------------------------------------------------------------------------
def cache_source(src):
    C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = src["source_id"].replace("/", "__").replace("\\", "__")
    out = C.CACHE_DIR / f"{safe}.npy"
    if not out.exists() or out.stat().st_mtime < Path(src["path"]).stat().st_mtime:
        x = load_audio(src["path"])
        np.save(out, x)
        n = len(x)
    else:
        n = np.load(out, mmap_mode="r").shape[0]
    src["cache"] = out
    src["seconds"] = n / C.SAMPLE_RATE
    return src


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build manifest from ESC-50 + custom recordings")
    ap.add_argument("--esc50-root", default=str(C.DEFAULT_ESC50_ROOT))
    ap.add_argument("--custom-root", default=str(C.DEFAULT_CUSTOM_ROOT))
    ap.add_argument("--experiment", choices=["baseline", "full"], default="baseline",
                    help="baseline = ESC-50 only (GLASS_BREAK/ALARM/BACKGROUND); full = + custom_data")
    args = ap.parse_args()

    sources = esc50_sources(args.esc50_root)
    notes = []
    if args.experiment == "full":
        custom = custom_sources(args.custom_root)
        if custom:
            notes += assign_custom_splits(custom)
            sources += custom
        else:
            notes.append(f"no custom recordings found under {args.custom_root}; using ESC-50 only")

    # active classes = CLASSES order, restricted to what has data
    present = {s["label"] for s in sources}
    if args.experiment == "baseline":
        present &= set(C.BASELINE_CLASSES)
        sources = [s for s in sources if s["label"] in present]
    labels = [c for c in C.CLASSES if c in present]
    missing = [c for c in C.CLASSES if c not in present]
    if "KNOWN_VOICE" in labels and "UNFAMILIAR_VOICE" not in labels:
        notes.append("KNOWN_VOICE present but no UNFAMILIAR_VOICE recordings: the model can only "
                     "recognize the enrolled speaker. Other voices will fall to UNKNOWN via "
                     "low-confidence rejection, which is NOT real unfamiliar-speaker detection.")

    print(f"standardizing {len(sources)} sources to {C.SAMPLE_RATE} Hz mono -> {C.CACHE_DIR}")
    for i, s in enumerate(sources, 1):
        cache_source(s)
        if i % 100 == 0 or i == len(sources):
            print(f"  {i}/{len(sources)}")

    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with open(C.MANIFEST_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "origin", "category", "label", "split", "speaker", "fold",
                    "cache", "seconds"])
        for s in sources:
            w.writerow([s["source_id"], s["origin"], s["category"], s["label"], s["split"],
                        s["speaker"], s["fold"], s["cache"], f"{s['seconds']:.3f}"])
    C.LABELS_TXT.write_text("\n".join(labels) + "\n")

    # summary
    counts = Counter((s["label"], s["split"]) for s in sources)
    secs = defaultdict(float)
    for s in sources:
        secs[(s["label"], s["split"])] += s["seconds"]
    print(f"\nexperiment: {args.experiment}   classes: {labels}")
    if missing:
        print(f"no data for: {missing}")
    print(f"{'class':18s} {'train':>12s} {'val':>12s} {'test':>12s}")
    for label in labels:
        cells = [f"{counts[(label, sp)]:4d} ({secs[(label, sp)]/60:5.1f}m)" for sp in ("train", "val", "test")]
        print(f"{label:18s} {cells[0]:>12s} {cells[1]:>12s} {cells[2]:>12s}")
    for n in notes:
        print(f"NOTE: {n}")
    print(f"\nwrote {C.MANIFEST_CSV}\nwrote {C.LABELS_TXT}")


if __name__ == "__main__":
    main()
