"""CSV event logger. One row per confirmed event."""

import csv
import os
import time
from datetime import datetime

import config


class EventLogger:
    def __init__(self, log_dir=config.LOG_DIR):
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(log_dir, f"events_{stamp}.csv")
        self._file = open(self.path, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(config.CSV_COLUMNS)
        self._file.flush()
        self._t0 = time.monotonic()

    def log(self, event, score, features):
        """features: dict with rms, dominant_hz and ratios (list of 5)."""
        ratios = features.get("ratios", [0.0] * 5)
        row = [
            f"{time.monotonic() - self._t0:.3f}",
            event,
            f"{score:.2f}",
            f"{features.get('rms', 0.0):.4f}",
            f"{features.get('dominant_hz', 0.0):.0f}",
        ] + [f"{r:.3f}" for r in ratios]
        self._writer.writerow(row)
        self._file.flush()

    def close(self):
        if not self._file.closed:
            self._file.close()
