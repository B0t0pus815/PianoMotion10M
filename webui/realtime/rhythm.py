"""rhythm.py — per-onset timing (rush/drag) tracker for the Phase B runner.

At every matched onset the runner knows both the PLAYED time and the faithful
REFERENCE onset time, so the raw timing signal is `played - reference`:

  - offset > 0  → played later than the reference  → DRAG  (拖拍)
  - offset < 0  → played earlier                   → RUSH  (搶拍)

Two readings of that signal are emitted (see RhythmResult):

  - `offset_s`    — the raw lag/lead vs the reference clock. Use this for
    "are you behind the song overall" (the report card's tendency).
  - `detrended_s` — the raw offset minus the student's OWN running tempo
    baseline (an EMA of recent offsets). A constant lag or a slow tempo drift
    is absorbed into the baseline, so a steady-but-faster performance reads as
    EVEN (detrended ≈ 0) while a local hesitation spikes. The live rush/drag
    badge classifies on this — it measures steadiness, not absolute speed.

Stateful and order-dependent: feed onsets in time order (the runner does, in
both replay and live modes). One global tracker for v1; per-hand / chord-aware
tracking is left as future work.
"""
from __future__ import annotations

from dataclasses import dataclass


DEFAULT_TOLERANCE_S = 0.06   # |detrended| within this → 'on_time'
DEFAULT_EMA_ALPHA = 0.2      # baseline = alpha*raw + (1-alpha)*baseline


@dataclass
class RhythmResult:
    offset_s: float          # raw: played - reference (+ve = drag/late)
    detrended_s: float       # raw - running tempo baseline
    status: str              # 'rush' | 'drag' | 'on_time' | 'unknown'


class RhythmTracker:
    """Running rush/drag classifier with an EMA tempo baseline.

    `tolerance_s` is the on-time half-window applied to the DETRENDED offset.
    `ema_alpha` weights the most recent onset when updating the baseline.
    """

    def __init__(self, tolerance_s: float = DEFAULT_TOLERANCE_S,
                 ema_alpha: float = DEFAULT_EMA_ALPHA):
        self.tolerance_s = tolerance_s
        self.ema_alpha = ema_alpha
        self._baseline: float | None = None

    def update(self, played_t: float, reference_t: float) -> RhythmResult:
        raw = played_t - reference_t
        if self._baseline is None:
            # First onset — no baseline yet, so we can't judge steadiness.
            self._baseline = raw
            return RhythmResult(offset_s=raw, detrended_s=0.0, status='unknown')

        detrended = raw - self._baseline
        if detrended < -self.tolerance_s:
            status = 'rush'
        elif detrended > self.tolerance_s:
            status = 'drag'
        else:
            status = 'on_time'

        # Update the running baseline AFTER classifying against the prior one.
        self._baseline = self.ema_alpha * raw + (1.0 - self.ema_alpha) * self._baseline
        return RhythmResult(offset_s=raw, detrended_s=detrended, status=status)
