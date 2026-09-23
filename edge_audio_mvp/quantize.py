"""
Export the trained Keras model to TensorFlow Lite: float32 and full-integer INT8.

    python quantize.py

INT8 uses post-training quantization with a representative dataset of real
training windows. Both models are then scored on the validation split and the
accuracy drop is checked against config.INT8_MAX_ACCURACY_DROP.
"""

import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import numpy as np
import tensorflow as tf
import keras

import config as C
from features import crop, log_mel
from train import read_manifest, load_split, train_windows
from evaluate import collect, metrics, predict_tflite


def representative_windows(n=C.REPRESENTATIVE_SAMPLES, seed=0):
    rows, labels = read_manifest()
    label_to_idx = {l: i for i, l in enumerate(labels)}
    sources = load_split(rows, "train")
    rng = np.random.default_rng(seed)
    items = train_windows(sources, label_to_idx, rng)[:n]
    return [log_mel(crop(sources[i]["wave"], st)) for i, st, _ in items]


def convert(model, int8_samples=None):
    conv = tf.lite.TFLiteConverter.from_keras_model(model)
    if int8_samples is not None:
        def rep():
            for m in int8_samples:
                yield [m[None].astype(np.float32)]
        conv.optimizations = [tf.lite.Optimize.DEFAULT]
        conv.representative_dataset = rep
        conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        conv.inference_input_type = tf.int8
        conv.inference_output_type = tf.int8
    return conv.convert()


def main():
    model = keras.models.load_model(C.MODEL_KERAS)
    print(f"loaded {C.MODEL_KERAS} ({model.count_params():,} params)")

    C.MODEL_FLOAT_TFLITE.write_bytes(convert(model))
    print(f"wrote {C.MODEL_FLOAT_TFLITE} ({C.MODEL_FLOAT_TFLITE.stat().st_size/1024:.0f} KB)")

    reps = representative_windows()
    C.MODEL_INT8_TFLITE.write_bytes(convert(model, reps))
    print(f"wrote {C.MODEL_INT8_TFLITE} ({C.MODEL_INT8_TFLITE.stat().st_size/1024:.0f} KB) "
          f"using {len(reps)} representative windows")

    # accuracy check on validation
    X, y, labels, _ = collect("val")
    keras_acc = float((model.predict(X, batch_size=64, verbose=0).argmax(1) == y).mean())
    out = {}
    for name, path in (("float", C.MODEL_FLOAT_TFLITE), ("int8", C.MODEL_INT8_TFLITE)):
        probs, ms = predict_tflite(X, path)
        m = metrics(probs, y, labels, C.CONFIDENCE_THRESHOLD)
        out[name] = (m["accuracy"], ms)
    print(f"\nval accuracy: keras {keras_acc:.3f}  float {out['float'][0]:.3f} ({out['float'][1]:.1f} ms)  "
          f"int8 {out['int8'][0]:.3f} ({out['int8'][1]:.1f} ms)")
    drop = keras_acc - out["int8"][0]
    if drop > C.INT8_MAX_ACCURACY_DROP:
        print(f"WARNING: INT8 drops {drop*100:.1f} points (> {C.INT8_MAX_ACCURACY_DROP*100:.0f}). "
              f"Consider quantization-aware training (tensorflow_model_optimization) before deploying.")
    else:
        print(f"INT8 accuracy drop {drop*100:.1f} points: within acceptance")


if __name__ == "__main__":
    main()
