"""
Audio loading, standardization and log-Mel features. numpy only, so the exact
same code runs in training (PC) and inference (UNO Q). Never use a different
mel implementation on one side; a mismatch silently wrecks accuracy.
"""

import numpy as np

import config as C


# ---------------------------------------------------------------------------
# Loading / standardization
# ---------------------------------------------------------------------------
def resample(x, sr_in, sr_out=C.SAMPLE_RATE):
    """Band-limited resample via the FFT (ideal low-pass, so no aliasing)."""
    if sr_in == sr_out:
        return x.astype(np.float32)
    n_in = len(x)
    n_out = int(round(n_in * sr_out / sr_in))
    spec = np.fft.rfft(x)
    out = np.zeros(n_out // 2 + 1, dtype=complex)
    keep = min(len(spec), len(out))
    out[:keep] = spec[:keep]
    return (np.fft.irfft(out, n_out) * (n_out / n_in)).astype(np.float32)


def load_audio(path):
    """Read any audio file -> mono float32 at SAMPLE_RATE. Originals are never modified."""
    import soundfile as sf
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = data.mean(axis=1)
    return resample(x, sr)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


# ---------------------------------------------------------------------------
# Windowing helpers
# ---------------------------------------------------------------------------
def pad_to_window(x, n=C.WINDOW_SAMPLES):
    if len(x) >= n:
        return x
    out = np.zeros(n, dtype=np.float32)
    out[:len(x)] = x
    return out


def strided_starts(n_samples, stride_s, window=C.WINDOW_SAMPLES):
    """Start indices of windows covering the signal at the given stride."""
    if n_samples <= window:
        return [0]
    stride = int(stride_s * C.SAMPLE_RATE)
    starts = list(range(0, n_samples - window + 1, stride))
    if starts[-1] + window < n_samples:          # make sure the tail is covered
        starts.append(n_samples - window)
    return starts


def energy_envelope(x, block=C.HOP_LENGTH):
    n = len(x) // block
    return np.sqrt(np.mean(np.square(x[:n * block]).reshape(n, block), axis=1) + 1e-12)


def loudest_start(x, window=C.WINDOW_SAMPLES):
    """Start of the 2 s window containing the most energy (for short events in long clips)."""
    if len(x) <= window:
        return 0
    env = energy_envelope(x)
    w = window // C.HOP_LENGTH
    cum = np.concatenate([[0.0], np.cumsum(env ** 2)])
    sums = cum[w:] - cum[:-w]
    return int(np.argmax(sums)) * C.HOP_LENGTH


def crop(x, start, window=C.WINDOW_SAMPLES):
    start = int(max(0, min(start, len(x) - window)))
    return pad_to_window(x[start:start + window])


# ---------------------------------------------------------------------------
# Log-Mel spectrogram
# ---------------------------------------------------------------------------
def _hz_to_mel(f):
    return 2595.0 * np.log10(1.0 + np.asarray(f, dtype=np.float64) / 700.0)


def _mel_to_hz(m):
    return 700.0 * (10.0 ** (np.asarray(m, dtype=np.float64) / 2595.0) - 1.0)


def mel_filterbank(sr=C.SAMPLE_RATE, n_fft=C.N_FFT, n_mels=C.N_MELS, fmin=C.FMIN, fmax=C.FMAX):
    """Triangular HTK-mel filters, shape [n_mels, n_fft//2 + 1]."""
    fft_freqs = np.linspace(0.0, sr / 2.0, n_fft // 2 + 1)
    mel_pts = np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    hz_pts = _mel_to_hz(mel_pts)
    fb = np.zeros((n_mels, len(fft_freqs)), dtype=np.float32)
    for m in range(n_mels):
        lo, ctr, hi = hz_pts[m], hz_pts[m + 1], hz_pts[m + 2]
        up = (fft_freqs - lo) / max(ctr - lo, 1e-9)
        down = (hi - fft_freqs) / max(hi - ctr, 1e-9)
        fb[m] = np.maximum(0.0, np.minimum(up, down))
    return fb


_MEL_FB = mel_filterbank()
_WINDOW = np.hanning(C.WIN_LENGTH + 1)[:-1].astype(np.float32)   # periodic Hann


def log_mel(window):
    """
    2 s float32 waveform -> normalized log-Mel spectrogram [N_MELS, N_FRAMES, 1].
    Windows shorter than 2 s are zero-padded; longer ones are truncated.
    """
    x = pad_to_window(np.asarray(window, dtype=np.float32))[:C.WINDOW_SAMPLES]
    n_frames = 1 + (len(x) - C.WIN_LENGTH) // C.HOP_LENGTH
    idx = np.arange(C.WIN_LENGTH)[None, :] + C.HOP_LENGTH * np.arange(n_frames)[:, None]
    frames = x[idx] * _WINDOW                                   # [T, 400]
    spec = np.fft.rfft(frames, n=C.N_FFT, axis=1)               # [T, 257]
    power = (spec.real ** 2 + spec.imag ** 2).astype(np.float32)
    mel = power @ _MEL_FB.T                                     # [T, 64]
    logmel = np.log(mel + C.LOG_EPS).T                          # [64, T]
    logmel = (logmel - logmel.mean()) / (logmel.std() + 1e-6)
    return logmel[:, :, None].astype(np.float32)


def feature_shape():
    return (C.N_MELS, C.N_FRAMES, 1)
