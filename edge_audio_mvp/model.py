"""
TinyAudioNet: a small depthwise-separable CNN for log-Mel inputs.

    Input [64 mel, 198 frames, 1]
    Conv2D 16 3x3 s2 -> BN -> ReLU
    DW 3x3        -> PW 32  -> BN -> ReLU
    DW 3x3 s2     -> PW 64  -> BN -> ReLU
    DW 3x3 s2     -> PW 96  -> BN -> ReLU
    DW 3x3 s2     -> PW 128 -> BN -> ReLU
    GlobalAveragePooling -> Dropout 0.2 -> Dense(n_classes) softmax
"""

import keras
from keras import layers

import config as C
from features import feature_shape


def build_tiny_audio_net(n_classes, stem=C.STEM_CHANNELS, blocks=C.BLOCK_CHANNELS,
                         dropout=C.DROPOUT):
    inp = keras.Input(shape=feature_shape(), name="log_mel")
    x = layers.Conv2D(stem, 3, strides=2, padding="same", use_bias=False, name="stem_conv")(inp)
    x = layers.BatchNormalization(name="stem_bn")(x)
    x = layers.ReLU(name="stem_relu")(x)

    for i, (ch, stride) in enumerate(blocks, start=1):
        x = layers.DepthwiseConv2D(3, strides=stride, padding="same", use_bias=False,
                                   name=f"block{i}_dw")(x)
        x = layers.Conv2D(ch, 1, use_bias=False, name=f"block{i}_pw")(x)
        x = layers.BatchNormalization(name=f"block{i}_bn")(x)
        x = layers.ReLU(name=f"block{i}_relu")(x)

    x = layers.GlobalAveragePooling2D(name="gap")(x)
    x = layers.Dropout(dropout, name="dropout")(x)
    out = layers.Dense(n_classes, activation="softmax", name="probs")(x)

    model = keras.Model(inp, out, name="TinyAudioNet")
    n_params = model.count_params()
    if n_params > C.MAX_PARAMS:
        raise ValueError(f"TinyAudioNet has {n_params:,} params, over the {C.MAX_PARAMS:,} hard limit")
    return model


if __name__ == "__main__":
    m = build_tiny_audio_net(len(C.CLASSES))
    m.summary()
