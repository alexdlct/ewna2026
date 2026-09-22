"""
Microphone (or WAV file) -> AudioProcessor -> CSV log + serial event to Arduino.

    python main.py --list-devices
    python main.py --debug --no-serial        # calibration mode, live mic
    python main.py --wav clips/glass.wav      # replay a recording, no mic needed
    python main.py --port COM5                # full demo
"""

import argparse
import queue
import sys
import time

import numpy as np

import config as C
from audio_processor import AudioProcessor
from logger import EventLogger


# ---------------------------------------------------------------------------
# Serial
# ---------------------------------------------------------------------------
def open_serial(port):
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        print("[serial] pyserial not installed; running without Arduino output")
        return None

    if port is None:
        ports = list(list_ports.comports())
        for p in ports:
            text = f"{p.description} {p.manufacturer or ''}".lower()
            if "arduino" in text or p.vid in (0x2341, 0x2A03):
                port = p.device
                break
        if port is None and len(ports) == 1:
            port = ports[0].device
            print(f"[serial] no Arduino-branded port found; using the only port {port}")
    if port is None:
        print("[serial] no serial port found; running without Arduino output "
              "(use --port COMx to force one)")
        return None
    try:
        ser = serial.Serial(port, C.SERIAL_BAUD, timeout=0.1)
        time.sleep(1.5)  # let the board settle after the port opens
        print(f"[serial] connected to {port} @ {C.SERIAL_BAUD}")
        return ser
    except Exception as e:  # noqa: BLE001
        print(f"[serial] could not open {port}: {e}; running without Arduino output")
        return None


# ---------------------------------------------------------------------------
# Audio file input
# ---------------------------------------------------------------------------
def resample(x, sr_in, sr_out):
    """Band-limited resample via the FFT.

    Truncating the spectrum is an ideal low-pass, so downsampling (e.g.
    44.1 kHz -> 16 kHz) does not fold high-frequency content down into the
    glass / alarm bands the way naive decimation would.
    """
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
    """Return mono float32 samples at C.SAMPLE_RATE."""
    try:
        import soundfile as sf
    except ImportError:
        print("[wav] soundfile is required for --wav: pip install soundfile", file=sys.stderr)
        raise SystemExit(1)

    try:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception as e:  # noqa: BLE001
        print(f"[wav] could not read {path}: {e}", file=sys.stderr)
        raise SystemExit(1)

    x = data.mean(axis=1)                       # mix down to mono
    if sr != C.SAMPLE_RATE:
        print(f"[wav] resampling {sr} Hz -> {C.SAMPLE_RATE} Hz")
        x = resample(x, sr, C.SAMPLE_RATE)
    print(f"[wav] {path}: {len(x) / C.SAMPLE_RATE:.2f} s, peak {np.max(np.abs(x)):.3f}")
    return x


# ---------------------------------------------------------------------------
# Event output
# ---------------------------------------------------------------------------
def emit(events, logger, ser):
    for event, score, features in events:
        ratios = " ".join(f"{r:.2f}" for r in features["ratios"])
        print(f"[event] {event:11s} score={score:.2f} rms={features['rms']:.3f} "
              f"dom={features['dominant_hz']:.0f}Hz bands=[{ratios}]")
        logger.log(event, score, features)
        if ser is not None:
            msg = C.EVENT_TO_SERIAL.get(event, "UNKNOWN")
            try:
                ser.write((msg + "\n").encode("ascii"))
            except Exception as e:  # noqa: BLE001
                print(f"[serial] write failed: {e}")


def maybe_debug(args, processor, state):
    if args.debug and processor.frames_processed >= state["next"]:
        state["next"] = processor.frames_processed + C.DEBUG_PRINT_EVERY
        print(processor.debug_line())


# ---------------------------------------------------------------------------
# Run modes
# ---------------------------------------------------------------------------
def run_wav(path, processor, logger, ser, args):
    x = load_audio(path)
    state = {"next": C.DEBUG_PRINT_EVERY}
    t0 = time.monotonic()

    for i in range(0, len(x), C.HOP_SIZE):
        chunk = x[i:i + C.HOP_SIZE]
        emit(processor.push(chunk), logger, ser)
        maybe_debug(args, processor, state)
        if args.realtime:
            lag = (i + len(chunk)) / C.SAMPLE_RATE - (time.monotonic() - t0)
            if lag > 0:
                time.sleep(lag)

    # trailing silence so a pending IDLE gets flushed
    tail = np.zeros(int(C.IDLE_AFTER_S * C.SAMPLE_RATE) + C.FFT_SIZE, dtype=np.float32)
    emit(processor.push(tail), logger, ser)
    print("[wav] done")


def run_mic(processor, logger, ser, args):
    import sounddevice as sd

    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[audio] {status}", file=sys.stderr)
        q.put(indata[:, 0].copy())

    device = C.INPUT_DEVICE
    if args.device is not None:
        try:
            device = int(args.device)
        except ValueError:
            device = args.device

    stream = sd.InputStream(
        samplerate=C.SAMPLE_RATE,
        channels=C.CHANNELS,
        dtype="float32",
        blocksize=C.HOP_SIZE,
        device=device,
        callback=callback,
    )

    print("[audio] listening (Ctrl-C to stop)")
    state = {"next": C.DEBUG_PRINT_EVERY}
    with stream:
        while True:
            emit(processor.push(q.get()), logger, ser)
            maybe_debug(args, processor, state)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Audio MVP: PC DSP -> Arduino LED events")
    ap.add_argument("--debug", action="store_true", help="print features + scores continuously")
    ap.add_argument("--no-serial", action="store_true", help="don't talk to the Arduino")
    ap.add_argument("--port", default=C.SERIAL_PORT, help="serial port, e.g. COM5")
    ap.add_argument("--device", default=None, help="input device index or name substring")
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--wav", default=None, help="process a WAV file instead of the microphone")
    ap.add_argument("--realtime", action="store_true",
                    help="with --wav, play at real speed instead of as fast as possible")
    args = ap.parse_args()

    if args.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return

    ser = None if args.no_serial else open_serial(args.port)
    processor = AudioProcessor()
    logger = EventLogger()
    print(f"[log] writing events to {logger.path}")

    try:
        if args.wav:
            run_wav(args.wav, processor, logger, ser, args)
        else:
            run_mic(processor, logger, ser, args)
    except KeyboardInterrupt:
        print("\n[main] stopping")
    finally:
        logger.close()
        if ser is not None:
            try:
                ser.write(b"IDLE\n")
                ser.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    main()
