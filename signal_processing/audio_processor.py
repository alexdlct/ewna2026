"""
Rolling buffer -> FFT -> 5 band energies + 4 features -> rule-based detectors
-> temporal confirmation -> confirmed events.

Everything is classical DSP with numpy. No ML.
"""

from collections import deque

import numpy as np

import config as C

EVENTS = ["ALARM", "VOICE", "FALL_THUD", "FOOTSTEPS", "GLASS_BREAK"]
IMPACT_EVENTS = {"FALL_THUD", "GLASS_BREAK"}        # one strong frame is enough
SUSTAINED_EVENTS = {"ALARM", "VOICE", "FOOTSTEPS"}  # need confirmation over time
_EPS = 1e-12


def ramp(x, lo, hi):
    """0 at x<=lo, 1 at x>=hi, linear between. Explainable, tunable."""
    if hi == lo:
        return 1.0 if x >= hi else 0.0
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))


class AudioProcessor:
    def __init__(self):
        sr, n = C.SAMPLE_RATE, C.FFT_SIZE
        self.hop_s = C.HOP_SIZE / sr

        # FFT helpers
        self._window = np.hanning(n).astype(np.float32)
        freqs = np.fft.rfftfreq(n, d=1.0 / sr)
        self._band_masks = [(freqs >= lo) & (freqs < hi) for lo, hi in C.BANDS]
        self._analysis_mask = (freqs >= C.ANALYSIS_MIN_HZ) & (freqs <= C.BANDS[-1][1])
        self._freqs = freqs

        # Rolling sample buffer (long enough for history + one FFT frame)
        self._buffer = np.zeros(int(C.HISTORY_SECONDS * sr) + n, dtype=np.float32)
        self._unprocessed = 0
        self._samples_seen = 0

        # Short histories (in hops)
        hops = lambda seconds: max(1, int(round(seconds / self.hop_s)))
        self._rms_hist = deque(maxlen=hops(C.BASELINE_SECONDS))
        self._alarm_hist = deque(maxlen=hops(C.ALARM_WINDOW_S))   # (tonal quality, dominant hz)
        self._ratio_hist = deque(maxlen=hops(C.VOICE_CHANGE_WINDOW_S) + C.VOICE_CHANGE_STRIDE_HOPS)
        self._transients = deque()          # dicts: t, rms, low_ratio, high_ratio, flatness
        self._voice_run = 0                 # consecutive speech-band frames

        # Event confirmation state
        self._candidate = None
        self._candidate_run = 0
        self._last_emit = {}                # event -> t
        self._last_any_event_t = -1e9
        self._last_impact_t = -1e9          # last FALL_THUD / GLASS_BREAK emission
        self._last_active_t = 0.0
        self._idle_sent = True

        self._now = 0.0

        # Exposed for debug printing
        self.frames_processed = 0
        self.last_features = None
        self.last_scores = {e: 0.0 for e in EVENTS}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def push(self, samples):
        """Append mono float samples. Returns list of (event, score, features)."""
        samples = np.asarray(samples, dtype=np.float32).ravel()
        k = len(samples)
        if k == 0:
            return []
        if k >= len(self._buffer):
            samples = samples[-len(self._buffer):]
            k = len(samples)
        self._buffer = np.roll(self._buffer, -k)
        self._buffer[-k:] = samples
        self._samples_seen += k
        self._unprocessed = min(self._unprocessed + k, len(self._buffer) - C.FFT_SIZE)

        events = []
        n = C.FFT_SIZE
        while self._unprocessed >= C.HOP_SIZE:
            end = len(self._buffer) - self._unprocessed + C.HOP_SIZE
            frame = self._buffer[end - n:end]
            t = (self._samples_seen - self._unprocessed + C.HOP_SIZE) / C.SAMPLE_RATE
            events.extend(self._process_frame(frame, t))
            self._unprocessed -= C.HOP_SIZE
        return events

    def debug_line(self):
        f, s = self.last_features, self.last_scores
        if f is None:
            return ""
        bands = " ".join(f"B{i+1}={r:.2f}" for i, r in enumerate(f["ratios"]))
        scores = " ".join(f"{e[:5]}={s[e]:.2f}" for e in EVENTS)
        return (f"rms={f['rms']:.3f} pk={f['peak']:.2f} dom={f['dominant_hz']:5.0f}Hz "
                f"flat={f['flatness']:.3f} pr={f['peak_ratio']:5.1f} "
                f"ch={f.get('spectral_change', 0.0):.3f} | {bands} | "
                f"{scores} | tr={len(self._transients)}")

    # ------------------------------------------------------------------
    # Per-frame pipeline
    # ------------------------------------------------------------------
    def _process_frame(self, frame, t):
        f = self._features(frame)
        self._now = t
        self.frames_processed += 1
        self.last_features = f

        sound_active = f["rms"] > C.SOUND_ACTIVE_RMS
        if sound_active:
            self._last_active_t = t

        self._update_transients(t, f)
        self._ratio_hist.append(f["ratios"])

        scores = {
            "ALARM": self._score_alarm(f, sound_active),
            "GLASS_BREAK": self._score_glass(t),
            "FALL_THUD": self._score_fall(t),
            "FOOTSTEPS": self._score_footsteps(t),
            "VOICE": self._score_voice(f, sound_active),
        }
        self.last_scores = scores
        return self._choose_event(t, f, scores, sound_active)

    def _features(self, frame):
        rms = float(np.sqrt(np.mean(frame * frame)))
        peak = float(np.max(np.abs(frame)))

        spec = np.fft.rfft(frame * self._window)
        power = (spec.real ** 2 + spec.imag ** 2)

        band_power = [float(power[m].sum()) for m in self._band_masks]
        total = sum(band_power) + _EPS
        ratios = [b / total for b in band_power]

        p = power[self._analysis_mask]
        fa = self._freqs[self._analysis_mask]
        dominant_hz = float(fa[int(np.argmax(p))])
        mean_p = float(np.mean(p)) + _EPS
        # Spectral flatness = geometric mean / arithmetic mean. Bins quieter than
        # a small fraction of the mean are clamped so empty regions of the
        # spectrum don't drive the geometric mean to zero.
        p_floor = np.maximum(p, mean_p * C.FLATNESS_FLOOR_RATIO)
        flatness = float(np.exp(np.mean(np.log(p_floor))) / mean_p)
        peak_ratio = float(np.max(p)) / mean_p

        return {
            "rms": rms,
            "peak": peak,
            "dominant_hz": dominant_hz,
            "flatness": flatness,
            "peak_ratio": peak_ratio,
            "ratios": ratios,
            "low_ratio": ratios[0] + ratios[1],
            "high_ratio": ratios[3] + ratios[4],
            "speech_ratio": ratios[0] + ratios[1] + ratios[2],
        }

    # ------------------------------------------------------------------
    # Transient tracking (for FALL / GLASS / FOOTSTEPS)
    # ------------------------------------------------------------------
    def _update_transients(self, t, f):
        rms = f["rms"]
        baseline = float(np.median(self._rms_hist)) if len(self._rms_hist) >= 4 else 0.0
        onset_ref = self._rms_hist[-3] if len(self._rms_hist) >= 3 else 0.0
        self._rms_hist.append(rms)

        # prune old
        while self._transients and t - self._transients[0]["t"] > C.HISTORY_SECONDS:
            self._transients.popleft()

        last = self._transients[-1] if self._transients else None

        # A transient that is still "fresh" tracks its own peak so we record the
        # loudest frame of the impulse, not just its onset.
        if last is not None and t - last["t"] <= C.TRANSIENT_MIN_GAP_S:
            if rms > last["rms"]:
                last.update(rms=rms, low_ratio=f["low_ratio"],
                            high_ratio=f["high_ratio"], flatness=f["flatness"])
            return

        is_spike = (rms > max(baseline * C.TRANSIENT_RMS_RATIO, C.TRANSIENT_MIN_RMS)
                    and rms > onset_ref * C.TRANSIENT_ONSET_RATIO)
        if is_spike:
            self._transients.append({
                "t": t, "rms": rms,
                "low_ratio": f["low_ratio"], "high_ratio": f["high_ratio"],
                "flatness": f["flatness"],
            })

    def _latest_transient(self, max_age):
        if not self._transients:
            return None
        tr = self._transients[-1]
        return tr if (self._now - tr["t"]) <= max_age else None

    # ------------------------------------------------------------------
    # Detectors (each returns 0..1)
    # ------------------------------------------------------------------
    def _score_alarm(self, f, sound_active):
        """Tonal + strong stable peak + persists/repeats within the last window.

        Alarms beep with gaps, so we look at how much *tonal time* occurred in
        the last ALARM_WINDOW_S rather than requiring an unbroken run.
        """
        tonal = ramp(f["peak_ratio"], C.ALARM_MIN_PEAK_RATIO * 0.5, C.ALARM_MIN_PEAK_RATIO)
        not_flat = 1.0 - ramp(f["flatness"], C.ALARM_MAX_FLATNESS, C.ALARM_MAX_FLATNESS * 2)
        loud = ramp(f["rms"], C.ALARM_MIN_RMS * 0.5, C.ALARM_MIN_RMS)
        pitched = 1.0 if f["dominant_hz"] >= C.ALARM_MIN_DOMINANT_HZ else 0.0
        q = tonal * not_flat * loud * pitched if sound_active else np.nan
        self._alarm_hist.append((q, f["dominant_hz"]))

        if sound_active and q <= 0.5:      # currently loud but not a tone
            return 0.0
        active = [(qq, d) for qq, d in self._alarm_hist if not np.isnan(qq)]
        tonal_frames = [(qq, d) for qq, d in active if qq > 0.5]
        if len(tonal_frames) < 2:
            return 0.0

        tonal_time = len(tonal_frames) * self.hop_s
        sustained = ramp(tonal_time, C.ALARM_MIN_DURATION_S * 0.5, C.ALARM_MIN_DURATION_S)
        purity = ramp(len(tonal_frames) / len(active), 0.3, 0.7)   # mostly tone, not speech
        quality = float(np.mean([qq for qq, _ in tonal_frames]))
        dom_std = float(np.std([d for _, d in tonal_frames]))
        stable = 1.0 - ramp(dom_std, C.ALARM_FREQ_STABILITY_HZ, C.ALARM_FREQ_STABILITY_HZ * 2)
        return quality * stable * sustained * purity

    def _score_glass(self, t):
        tr = self._latest_transient(C.GLASS_RECENT_S)
        if tr is None:
            return 0.0
        high = ramp(tr["high_ratio"], C.GLASS_MIN_HIGH_RATIO * 0.6, C.GLASS_MIN_HIGH_RATIO)
        flat = ramp(tr["flatness"], C.GLASS_MIN_FLATNESS * 0.6, C.GLASS_MIN_FLATNESS)
        spike = ramp(tr["rms"], C.GLASS_MIN_RMS_SPIKE * 0.6, C.GLASS_MIN_RMS_SPIKE)
        return high * flat * spike

    def _score_fall(self, t):
        tr = self._latest_transient(C.FALL_RECENT_S)
        if tr is None:
            return 0.0
        low = ramp(tr["low_ratio"], C.FALL_MIN_LOW_RATIO * 0.6, C.FALL_MIN_LOW_RATIO)
        spike = ramp(tr["rms"], C.FALL_MIN_RMS_SPIKE * 0.6, C.FALL_MIN_RMS_SPIKE)
        others = [x for x in self._transients
                  if x is not tr and 0 < tr["t"] - x["t"] <= C.FALL_ISOLATION_S]
        isolated = 1.0 if not others else 0.3
        return low * spike * isolated

    def _score_footsteps(self, t):
        if not self._transients or t - self._transients[-1]["t"] > 1.2:
            return 0.0
        steps = []
        for tr in self._transients:
            lowish = ramp(tr["low_ratio"], C.STEP_MIN_LOW_RATIO * 0.6, C.STEP_MIN_LOW_RATIO)
            quiet = 1.0 - ramp(tr["rms"], C.STEP_MAX_RMS_SPIKE, C.STEP_MAX_RMS_SPIKE * 1.5)
            like = lowish * quiet
            if like > 0.3:
                steps.append((tr["t"], like))
        if len(steps) < C.STEP_MIN_COUNT:
            return 0.0
        steps = steps[-6:]  # only the most recent few
        times = np.array([s[0] for s in steps])
        intervals = np.diff(times)
        lo, hi = C.STEP_INTERVAL_RANGE
        in_range = float(np.mean((intervals >= lo) & (intervals <= hi)))
        if in_range == 0.0:
            return 0.0
        cv = float(np.std(intervals) / (np.mean(intervals) + _EPS)) if len(intervals) > 1 else 0.0
        consistent = 1.0 - ramp(cv, C.STEP_INTERVAL_CONSISTENCY, C.STEP_INTERVAL_CONSISTENCY * 2)
        count_score = ramp(len(steps), C.STEP_MIN_COUNT - 1, C.STEP_MIN_COUNT)
        likeness = float(np.mean([s[1] for s in steps]))
        return in_range * consistent * count_score * likeness

    def _score_voice(self, f, sound_active):
        sp = ramp(f["speech_ratio"], C.VOICE_MIN_SPEECH_RATIO * 0.8, C.VOICE_MIN_SPEECH_RATIO)
        active = sound_active and sp > 0.0
        self._voice_run = self._voice_run + 1 if active else 0
        if not active:
            return 0.0

        # How much the band ratios move over ~100 ms strides (speech wanders,
        # a steady tone or hum does not).
        k = C.VOICE_CHANGE_STRIDE_HOPS
        if len(self._ratio_hist) > k:
            r = np.array(self._ratio_hist)
            change = float(np.mean(np.abs(r[k:] - r[:-k])))
        else:
            change = 0.0
        f["spectral_change"] = change
        ch = ramp(change, C.VOICE_MIN_SPECTRAL_CHANGE * 0.5, C.VOICE_MIN_SPECTRAL_CHANGE)
        not_tone = 1.0 - ramp(f["peak_ratio"], C.VOICE_MAX_PEAK_RATIO, C.VOICE_MAX_PEAK_RATIO * 2)
        dur = ramp(self._voice_run * self.hop_s, 0.0, C.VOICE_MIN_DURATION_S)
        return sp * ch * not_tone * dur

    # ------------------------------------------------------------------
    # Event selection + temporal confirmation
    # ------------------------------------------------------------------
    def _choose_event(self, t, f, scores, sound_active):
        out = []
        best = max(scores, key=scores.get)
        best_score = scores[best]

        if best_score >= C.MIN_CONFIDENCE:
            candidate, cand_score = best, best_score
            # The ringing tail of an impact should not be re-read as a
            # sustained event (e.g. thud tail -> VOICE / FOOTSTEPS).
            if (candidate in SUSTAINED_EVENTS
                    and t - self._last_impact_t < C.IMPACT_SUPPRESS_S):
                candidate, cand_score = None, 0.0
        elif (sound_active and f["rms"] > C.UNKNOWN_MIN_RMS
              and t - self._last_any_event_t > C.EVENT_COOLDOWN_S):
            candidate, cand_score = "UNKNOWN", best_score
        else:
            candidate, cand_score = None, 0.0

        if candidate == self._candidate:
            self._candidate_run += 1
        else:
            self._candidate = candidate
            self._candidate_run = 1

        if candidate is not None:
            needed = C.CONFIRM_FRAMES.get(candidate, C.UNKNOWN_CONFIRM_FRAMES)
            last = self._last_emit.get(candidate, -1e9)
            if self._candidate_run >= needed and t - last > C.EVENT_COOLDOWN_S:
                self._last_emit[candidate] = t
                self._last_any_event_t = t
                if candidate in IMPACT_EVENTS:
                    self._last_impact_t = t
                self._idle_sent = False
                self._candidate_run = 0
                out.append((candidate, cand_score, f))

        if (not self._idle_sent and not sound_active
                and t - self._last_active_t > C.IDLE_AFTER_S):
            self._idle_sent = True
            out.append(("IDLE", 0.0, f))
        return out
