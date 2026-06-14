# Session summary — Threshold calibration instrument (2026-06-15)

> Self-contained narrative of one short work session on the PianoMotion10M
> AI-piano-learning project. The deliverable is a *working software (+ hardware)
> system*, not a thesis. This session built the instrument that unblocks the next
> frontier ("tune the currently-blind thresholds against a real recording").

---

## 0. TL;DR

The real-time grader gates user input on **absolute-pixel constants tuned for the
1920×1080 biomech-v4 renders**. On a real webcam recording (different resolution,
framing, real-photo hands) they are *silently* wrong, and nothing in the pipeline
reports whether a press cleared the velocity bar or whether a hand was even
tracked. "Tune them" was therefore blocked on a measurement we didn't have — and
on Desmond physically providing a recording.

Built **`webui/realtime/calibrate.py`**: runs the *same* tracking + history +
A/V-sync machinery as `runner.py` over a recording, but instead of grading it
reports the **distributions each threshold gates on**, plus data-driven
recommended values. So when a real recording lands, "tune the thresholds" is one
command and a read-off, not a guess.

Also exposed MediaPipe's confidence knobs on the runner (`--detect-confidence` /
`--track-confidence`) so calibrate's tracking-quality finding is *actionable*
without editing source.

108 fast tests pass (86 baseline + 22 new). Additive only — the verified grading
pipeline (comparator/note_align/runner core) was not changed in behavior.

---

## 1. The blind thresholds (what was un-measured)

| Threshold | File | Default | Why blind on a real recording |
|---|---|---|---|
| `MIN_PRESS_VELOCITY` | comparator.py | 80 px/s | px/s scales with resolution **and** how much of the frame the hands fill |
| `WRIST_ARCHED/COLLAPSED_THRESHOLD` | comparator.py | ±25 px | comment *claimed* "scales OK to 720p" — it does not (absolute px) |
| `PRESS_WINDOW` | comparator.py | 0.12 s | time-based (fine) but never measured |
| `min_detection/tracking_confidence` | hand_tracker.py | 0.3 | tracking quality — no visibility into the actual per-hand detection rate |
| `MATCH_WINDOW` / `CHORD_CLUSTER_WINDOW` | runner.py | 0.5 / 0.05 s | time-based, untuned (left as-is) |

A low-velocity legato press and a tracking dropout both collapse to
"no clear motion → lowest finger", indistinguishable in the output — so a bad
recording could score plausibly and silently.

## 2. What calibrate.py reports

For a recording + its played MIDI it prints three sections, each naming the gate:

- **Tracking quality** — per-hand detection rate (% of frames), detection-score
  percentiles, hand span (wrist→middle-tip px) as an absolute and a fraction of
  frame height. Fires **⚠ LOW detection** below 50%.
- **Press detection** — distribution of the max-finger downward velocity *at
  onsets* (the exact number `MIN_PRESS_VELOCITY` is compared against — mirrors
  `comparator.detect_press_finger`), the **fraction of onsets that fall below the
  bar** (= silently hit the lowest-finger fallback = blind presses), and a
  recommended bar for ≤10% fallback.
- **Wrist posture** — distribution of |deviation from the rolling median| at
  onsets, the fraction that would trip a flag at ±25px, and a recommended
  threshold that flags only the worst ~5%.
- **Resolution note** — calls out the 1080p-baseline mismatch and gives both a
  resolution-scaled default and the (preferred) measured recommendation.

Onset times are put on the **video clock** via the same A/V-sync convention as
the runner (`eff_t = frame_ts − δ`, `estimate_offset_xcorr`); `--no-sync` skips it
for already-aligned renders.

`--out calib.json` writes the full `CalibrationReport` (JSON) for the record.

## 3. Verification

- **22 unit tests** (`tests/test_calibrate.py`) cover the pure stats/recommendation
  helpers, `_onset_max_velocity` (the one video-path math the control run can't
  reach), and `format_report` on both the data-present path (recommendations
  render, fallback>25% warns) and the **n=0 degenerate path** (no false "✓" — it
  says "nothing to measure"). Run without MediaPipe.
- **Real-frame negative control**: ran calibrate on `results/canon_biomech_v4_kb.mp4`
  (MANO render). Decoded 181–241 frames, MediaPipe ran, detection = **0%**
  (exactly as the hand_tracker docstring predicts for non-photoreal hands), and
  the ⚠ LOW-detection warning fired. Proves the whole video→MediaPipe→history→
  onset-sampling→report path works and that the instrument *catches* unusable
  input rather than emitting a confident wrong grade.
- **Runner smoke** with `--detect-confidence 0.2 --track-confidence 0.2` on the
  same render ran clean end-to-end (flags flow into `HandTracker`, which already
  accepted them; behavior-preserving at the 0.3 defaults).
- Full fast suite: **108 passed** (`pytest tests/ -q --ignore=tests/test_audit_pipeline_integration.py`).

## 4. Commands

```bash
# When a real recording lands (video + keyboard-exported MIDI):
python -m webui.realtime.calibrate user_recordings/take1.mp4 user_recordings/take1.mid \
    --out user_recordings/take1.calib.json
#   → quick first look:  add --max-seconds 8
#   → user-facing webcam: add --mirror
#   → already-aligned render: add --no-sync

# Apply the tracking-quality finding (no source edit):
python -m webui.realtime.runner --video … --midi … --reference … \
    --detect-confidence 0.25 --track-confidence 0.25
```

## 5. State + next

- New: `webui/realtime/calibrate.py`, `tests/test_calibrate.py`.
  Modified: `webui/realtime/runner.py` (two optional confidence flags).
- **Still genuinely blocked on Desmond's data**: producing real numbers and
  picking final threshold values needs an actual camera+MIDI capture in
  `user_recordings/`. The instrument is staged and verified for that moment.
- **Natural follow-up (do it WITH the first real recording, so it's tuned and
  verified in one loop)**: thread the comparator pixel thresholds
  (`MIN_PRESS_VELOCITY`, `WRIST_*`) as injectable params + a `--calibration
  calib.json` loader on the runner, so calibrate's recommendations apply without
  editing source. Deliberately *not* done this session — it modifies the verified
  comparator and the override path can't be validated without real data.
