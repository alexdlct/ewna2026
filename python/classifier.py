"""
Sound classifier interface.

The rest of the service only needs one thing from a classifier: a callback
`on_detection(label, confidence)` fired whenever a window of audio is
classified. Where the model actually runs is up to the classifier team:

  * CLASSIFIER=bridge   (default) - the model runs elsewhere (MCU sketch or another
                        process) and reports through Bridge `report_detection`.
                        No Python classifier is started; see main.py.
  * CLASSIFIER=model    - ModelClassifier below runs the model in this process.
  * CLASSIFIER=scripted - ScriptedClassifier replays DEMO_SCRIPT (also `main.py --demo`).

Privacy: everything in this file stays on the UNO Q. Audio buffers must never
be passed to the notifier or written anywhere off-device.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Iterable, Optional, Tuple, Union

DetectionCallback = Callable[[Union[str, int], float], None]

log = logging.getLogger(__name__)


class BaseClassifier:
    """Threaded runner; subclasses implement `_run()` and call `self.emit()`."""

    def __init__(self) -> None:
        self._on_detection: Optional[DetectionCallback] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self, on_detection: DetectionCallback) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._on_detection = on_detection
        self._stop.clear()
        self._thread = threading.Thread(target=self._guarded_run, name=type(self).__name__, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def emit(self, label: Union[str, int], confidence: float) -> None:
        if self._on_detection is not None:
            self._on_detection(label, confidence)

    def _guarded_run(self) -> None:
        try:
            self._run()
        except Exception:
            log.exception("%s crashed", type(self).__name__)

    def _run(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


# --------------------------------------------------------------------------- demo
# (label, confidence, delay-before-emitting in seconds). Labels are deliberately the
# human-readable names to prove normalisation end-to-end.
DEMO_SCRIPT: list[Tuple[str, float, float]] = [
    ("Smoke alarm beeping", 0.93, 0.5),
    ("Smoke alarm beeping", 0.96, 1.0),                # inside cooldown -> LED only, no 2nd SMS
    ("Water rushing or spraying", 0.55, 2.0),          # below threshold -> ignored
    ("thud", 0.88, 2.0),
    ("Glass breaking (Dropped item)", 0.91, 3.0),
    ("Someone screaming or yelling for help", 0.97, 3.0),
]


class ScriptedClassifier(BaseClassifier):
    """Replays a fixed sequence of detections. For demos and end-to-end integration checks."""

    def __init__(self, script: Iterable[Tuple[str, float, float]] = DEMO_SCRIPT,
                 on_finished: Optional[Callable[[], None]] = None, loop: bool = False):
        super().__init__()
        self.script = list(script)
        self.on_finished = on_finished
        self.loop = loop

    def _run(self) -> None:
        while not self.stopping:
            for label, confidence, delay in self.script:
                if self._stop.wait(delay):
                    return
                log.info("Scripted detection: %r (%.2f)", label, confidence)
                self.emit(label, confidence)
            if not self.loop:
                break
        if self.on_finished:
            self.on_finished()


# -------------------------------------------------------------------------- model
class ModelClassifier(BaseClassifier):
    """
    Skeleton for the real on-device model. Two things to fill in:

        open_audio()  -> yields fixed-size float32 windows from the microphone
        predict()     -> (label_or_index, confidence) for one window

    The base loop is already threaded and stop-aware; it just streams windows
    into predict() and emits whatever comes back. Emit the *top class every
    window* (including background/silence) - AlertManager ignores unknown
    labels and applies thresholds/debounce, so the classifier can stay dumb.

    Audio deps are imported lazily so the rest of the service runs without them:
        pip install sounddevice numpy      # + `sudo apt install libportaudio2` on the board
    """

    SAMPLE_RATE = 16_000
    WINDOW_S = 1.0     # model input length
    HOP_S = 0.5        # 50 % overlap so short impulsive sounds (thud, glass) are not missed

    def __init__(self, model_path: Optional[str] = None, device: Optional[Union[int, str]] = None):
        super().__init__()
        self.model_path = model_path
        self.device = device
        self._model = None

    # ---- to implement ---------------------------------------------------
    def load_model(self) -> None:
        """Load TFLite / ONNX / Edge Impulse model from self.model_path into self._model."""
        raise NotImplementedError("Load the sound model here (models/ directory).")

    def predict(self, window) -> Tuple[Union[str, int], float]:
        """
        Classify one window (np.ndarray, shape (WINDOW_S*SAMPLE_RATE,), float32 in [-1, 1]).
        Return (label, confidence). label may be a class index into events.CLASS_ORDER.
        """
        raise NotImplementedError("Run the model on `window` here.")

    # ---- provided ------------------------------------------------------
    def open_audio(self):
        """Generator of overlapping windows from the default (or chosen) input device."""
        import numpy as np
        import sounddevice as sd

        window_n = int(self.WINDOW_S * self.SAMPLE_RATE)
        hop_n = int(self.HOP_S * self.SAMPLE_RATE)
        blocks: "queue.Queue" = queue.Queue(maxsize=64)

        def _callback(indata, frames, time_info, status):
            if status:
                log.debug("audio status: %s", status)
            try:
                blocks.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass  # drop rather than block the audio thread

        buffer = np.zeros(0, dtype=np.float32)
        with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1, dtype="float32",
                            blocksize=hop_n, device=self.device, callback=_callback):
            while not self.stopping:
                try:
                    block = blocks.get(timeout=0.5)
                except queue.Empty:
                    continue
                buffer = np.concatenate([buffer, block])
                while len(buffer) >= window_n:
                    yield buffer[:window_n]
                    buffer = buffer[hop_n:]

    def _run(self) -> None:
        self.load_model()
        log.info("ModelClassifier listening (%d Hz, %.1fs window, %.1fs hop)",
                 self.SAMPLE_RATE, self.WINDOW_S, self.HOP_S)
        for window in self.open_audio():
            started = time.monotonic()
            label, confidence = self.predict(window)
            self.emit(label, float(confidence))
            log.debug("predict %r %.2f in %.0f ms", label, confidence, (time.monotonic() - started) * 1e3)
