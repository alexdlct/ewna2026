"""
Train TinyAudioNet on the manifest written by prepare_data.py.

    python train.py                      # uses artifacts/manifest.csv + labels.txt
    python train.py --epochs 10 --name quick

Windows are cut from the cached 16 kHz waveforms on the fly, so each epoch
sees fresh random crops of the ESC-50 clips. Augmentation is waveform-level
(gain / shift / noise mix / optional stretch) + SpecAugment masks + light mixup.
Sample weights balance the classes.
"""

import argparse
import csv
import os
import time
from datetime import datetime

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf
import keras

import config as C
from features import (crop, log_mel, loudest_start, resample, rms, strided_starts, feature_shape)
from model import build_tiny_audio_net


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------
def read_manifest():
    with open(C.MANIFEST_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    labels = [l for l in C.LABELS_TXT.read_text().split("\n") if l.strip()]
    return rows, labels


def load_split(rows, split):
    out = []
    for r in rows:
        if r["split"] != split:
            continue
        r = dict(r)
        wave = np.load(r["cache"]).astype(np.float32)
        if r.get("start_s"):        # a time segment of a long recording
            a = int(float(r["start_s"]) * C.SAMPLE_RATE)
            b = int(float(r["end_s"]) * C.SAMPLE_RATE)
            wave = wave[a:b]
        r["wave"] = wave
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Window enumeration
# ---------------------------------------------------------------------------
def eval_windows(sources, label_to_idx):
    """Deterministic (source_idx, start, label_idx) for val / test."""
    items = []
    for i, s in enumerate(sources):
        x = s["wave"]
        n = len(x)
        starts = strided_starts(n, C.EVAL_STRIDE_S)
        if s["origin"] == "esc50" and s["label"] != "BACKGROUND":
            # ESC-50 positives are 5 s clips where the event may be short: keep the
            # loudest window plus any other window with comparable energy, and
            # drop the near-silent ones so they are not labelled as the event.
            peak = loudest_start(x)
            ref = rms(crop(x, peak))
            starts = [st for st in starts if rms(crop(x, st)) >= C.EVAL_POSITIVE_ENERGY_RATIO * ref]
            if peak not in starts:
                starts.append(peak)
        items += [(i, st, label_to_idx[s["label"]]) for st in starts]
    return items


def balanced_weights(label_idx_list, n_classes, power=1.0):
    """Per-class weight (N / (K * n_c)) ** power. power=1 makes a weighted
    accuracy equal balanced accuracy; power<1 tempers the boost given to rare classes."""
    counts = np.bincount(label_idx_list, minlength=n_classes).astype(np.float64)
    return counts, (counts.sum() / (n_classes * np.maximum(counts, 1.0))) ** power


def train_windows(sources, label_to_idx, rng):
    """Fresh (source_idx, start, label_idx) list for one epoch."""
    items = []
    for i, s in enumerate(sources):
        n = len(s["wave"])
        if s["origin"] == "esc50":
            k = C.ESC_TRAIN_CROPS["background" if s["label"] == "BACKGROUND" else "positive"]
            peak = loudest_start(s["wave"])
            for _ in range(k):
                if rng.random() < C.ENERGY_BIAS_PROB:
                    st = peak + rng.integers(-int(C.ENERGY_JITTER_S * C.SAMPLE_RATE),
                                             int(C.ENERGY_JITTER_S * C.SAMPLE_RATE) + 1)
                else:
                    st = rng.integers(0, max(1, n - C.WINDOW_SAMPLES + 1))
                items.append((i, int(st), label_to_idx[s["label"]]))
        elif n > C.LONG_SOURCE_S * C.SAMPLE_RATE:
            # long recording (voice take, LibriSpeech speaker): random windows,
            # a fresh draw every epoch, instead of thousands of strided ones
            rate = C.LONG_SOURCE_WINDOWS_PER_S if s["origin"] == "librispeech" else C.CUSTOM_LONG_WINDOWS_PER_S
            k = max(1, int(n / C.SAMPLE_RATE * rate))
            for st in rng.integers(0, n - C.WINDOW_SAMPLES + 1, size=k):
                items.append((i, int(st), label_to_idx[s["label"]]))
        else:
            for st in strided_starts(n, C.CUSTOM_TRAIN_STRIDE_S):
                items.append((i, st, label_to_idx[s["label"]]))
    rng.shuffle(items)
    return items


# ---------------------------------------------------------------------------
# Augmentation (numpy, train only)
# ---------------------------------------------------------------------------
def augment_wave(x, rng, noise_pool):
    # gain
    x = x * (10.0 ** (rng.uniform(-C.AUG_GAIN_DB, C.AUG_GAIN_DB) / 20.0))
    # time shift (zero fill)
    shift = int(rng.uniform(-C.AUG_SHIFT_S, C.AUG_SHIFT_S) * C.SAMPLE_RATE)
    if shift:
        y = np.zeros_like(x)
        if shift > 0:
            y[shift:] = x[:-shift]
        else:
            y[:shift] = x[-shift:]
        x = y
    # optional time stretch (resample then crop / pad)
    if C.AUG_TIME_STRETCH and rng.random() < C.AUG_TIME_STRETCH_PROB:
        rate = rng.uniform(*C.AUG_TIME_STRETCH)
        x = crop(resample(x, C.SAMPLE_RATE, int(C.SAMPLE_RATE * rate)), 0)
    # background noise mix at random SNR
    if noise_pool and rng.random() < C.AUG_NOISE_PROB:
        noise = noise_pool[rng.integers(len(noise_pool))]
        snr = rng.uniform(*C.AUG_NOISE_SNR_DB)
        px, pn = np.mean(x ** 2) + 1e-9, np.mean(noise ** 2) + 1e-9
        x = x + noise * np.sqrt(px / (pn * 10.0 ** (snr / 10.0)))
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def spec_augment(m, rng):
    m = m.copy()
    for _ in range(rng.integers(0, C.SPEC_TIME_MASKS + 1)):
        w = rng.integers(1, C.SPEC_TIME_MASK_MAX + 1)
        t0 = rng.integers(0, max(1, C.N_FRAMES - w))
        m[:, t0:t0 + w, :] = 0.0
    for _ in range(rng.integers(0, C.SPEC_FREQ_MASKS + 1)):
        w = rng.integers(1, C.SPEC_FREQ_MASK_MAX + 1)
        f0 = rng.integers(0, max(1, C.N_MELS - w))
        m[f0:f0 + w, :, :] = 0.0
    return m


# ---------------------------------------------------------------------------
# tf.data pipelines
# ---------------------------------------------------------------------------
def make_dataset(sources, items_fn, n_classes, class_weight, augment, seed):
    """items_fn() -> list of (source_idx, start, label_idx); called once per epoch."""
    rng = np.random.default_rng(seed)
    noise_pool = []
    if augment:
        for s in sources:
            if s["label"] == "BACKGROUND":
                for st in strided_starts(len(s["wave"]), 1.0)[:4]:
                    noise_pool.append(crop(s["wave"], st))

    def gen():
        for src_i, start, lab in items_fn():
            yield np.int64(src_i), np.int64(start), np.int64(lab)

    def load(src_i, start, lab):
        x = crop(sources[int(src_i)]["wave"], int(start))
        if augment:
            x = augment_wave(x, rng, noise_pool)
        m = log_mel(x)
        if augment:
            m = spec_augment(m, rng)
        y = np.zeros(n_classes, np.float32)
        y[int(lab)] = 1.0
        return m, y, np.float32(class_weight[int(lab)])

    def tf_load(src_i, start, lab):
        m, y, w = tf.numpy_function(load, [src_i, start, lab], [tf.float32, tf.float32, tf.float32])
        m.set_shape(feature_shape())
        y.set_shape([n_classes])
        w.set_shape([])
        return m, y, w

    ds = tf.data.Dataset.from_generator(
        gen, output_signature=(tf.TensorSpec([], tf.int64),) * 3)
    ds = ds.map(tf_load, num_parallel_calls=tf.data.AUTOTUNE, deterministic=not augment)
    ds = ds.batch(C.BATCH_SIZE, drop_remainder=augment)
    if augment and C.MIXUP_ALPHA:
        ds = ds.map(mixup, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.prefetch(tf.data.AUTOTUNE)


def mixup(x, y, w):
    def do_mix():
        g1 = tf.random.gamma([], C.MIXUP_ALPHA)
        g2 = tf.random.gamma([], C.MIXUP_ALPHA)
        lam = g1 / (g1 + g2 + 1e-9)
        idx = tf.random.shuffle(tf.range(tf.shape(x)[0]))
        return lam * x + (1.0 - lam) * tf.gather(x, idx), lam * y + (1.0 - lam) * tf.gather(y, idx), w
    return tf.cond(tf.random.uniform([]) < C.MIXUP_PROB, do_mix, lambda: (x, y, w))


# ---------------------------------------------------------------------------
def log_experiment(row):
    C.LOGS.mkdir(parents=True, exist_ok=True)
    new = not C.EXPERIMENTS_CSV.exists()
    with open(C.EXPERIMENTS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="Train TinyAudioNet")
    ap.add_argument("--epochs", type=int, default=C.EPOCHS)
    ap.add_argument("--name", default="run", help="label for logs/experiments.csv")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    keras.utils.set_random_seed(args.seed)
    rows, labels = read_manifest()
    n_classes = len(labels)
    label_to_idx = {l: i for i, l in enumerate(labels)}
    train_src = load_split(rows, "train")
    val_src = load_split(rows, "val")
    if not train_src or not val_src:
        raise SystemExit("manifest has no train or no val sources; run prepare_data.py first")

    # class weights from one epoch's worth of training windows; validation gets
    # its own weights from ITS class counts, so the weighted accuracy ("bal_acc")
    # is true balanced accuracy on validation and not dominated by BACKGROUND.
    rng = np.random.default_rng(args.seed)
    first_epoch = train_windows(train_src, label_to_idx, rng)
    counts, class_weight = balanced_weights([lab for _, _, lab in first_epoch], n_classes,
                                            power=C.CLASS_WEIGHT_POWER)
    for name, boost in C.CLASS_WEIGHT_BOOST.items():
        if name in label_to_idx:
            class_weight[label_to_idx[name]] *= boost
    steps = len(first_epoch) // C.BATCH_SIZE
    val_items = eval_windows(val_src, label_to_idx)
    val_counts, val_weight = balanced_weights([lab for _, _, lab in val_items], n_classes)

    print(f"classes: {labels}")
    print(f"train sources: {len(train_src)}  windows/epoch: {len(first_epoch)}  "
          f"val sources: {len(val_src)}  val windows: {len(val_items)}")
    print("train windows per class:", {l: int(counts[i]) for l, i in label_to_idx.items()})
    print("val windows per class:  ", {l: int(val_counts[i]) for l, i in label_to_idx.items()})
    print("train class weights:", {l: round(float(class_weight[i]), 2) for l, i in label_to_idx.items()})

    train_ds = make_dataset(train_src, lambda: train_windows(train_src, label_to_idx, rng),
                            n_classes, class_weight, augment=True, seed=args.seed).repeat()
    val_ds = make_dataset(val_src, lambda: val_items, n_classes, val_weight,
                          augment=False, seed=args.seed)

    model = build_tiny_audio_net(n_classes)
    model.summary()
    model.compile(
        optimizer=keras.optimizers.AdamW(learning_rate=C.LEARNING_RATE, weight_decay=C.WEIGHT_DECAY),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
        weighted_metrics=[keras.metrics.CategoricalAccuracy(name="bal_acc")],
    )
    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    callbacks = [
        keras.callbacks.EarlyStopping(monitor="val_bal_acc", mode="max", patience=C.EARLY_STOP_PATIENCE,
                                      restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=C.REDUCE_LR_FACTOR,
                                          patience=C.REDUCE_LR_PATIENCE, verbose=1),
        keras.callbacks.ModelCheckpoint(str(C.MODEL_KERAS), monitor="val_bal_acc", mode="max",
                                        save_best_only=True, verbose=0),
    ]

    t0 = time.time()
    hist = model.fit(train_ds, validation_data=val_ds, epochs=args.epochs,
                     steps_per_epoch=steps, callbacks=callbacks, verbose=2)
    seconds = time.time() - t0

    best_i = int(np.argmax(hist.history["val_bal_acc"]))
    C.LABELS_TXT.write_text("\n".join(labels) + "\n")
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "name": args.name,
        "classes": "|".join(labels),
        "train_windows": len(first_epoch),
        "val_windows": len(val_items),
        "epochs_run": len(hist.history["loss"]),
        "best_epoch": best_i + 1,
        "best_val_balanced_accuracy": round(float(hist.history["val_bal_acc"][best_i]), 4),
        "val_accuracy_at_best": round(float(hist.history["val_accuracy"][best_i]), 4),
        "val_loss_at_best": round(float(hist.history["val_loss"][best_i]), 4),
        "params": model.count_params(),
        "train_seconds": round(seconds),
    }
    log_experiment(row)
    print(f"\nbest val balanced accuracy {row['best_val_balanced_accuracy']} "
          f"(plain {row['val_accuracy_at_best']}) at epoch {row['best_epoch']} "
          f"({row['epochs_run']} epochs, {seconds/60:.1f} min)")
    print(f"saved {C.MODEL_KERAS}\nlogged {C.EXPERIMENTS_CSV}")


if __name__ == "__main__":
    main()
    # The repeated tf.data generator leaves a prefetch thread that can keep the
    # interpreter from exiting on Windows after everything is saved. Exit hard.
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
