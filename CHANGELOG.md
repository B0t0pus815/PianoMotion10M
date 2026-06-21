# CHANGELOG

Chronological log of thesis-project milestones. Newest first.

The "Phase / Stage" labels match the architectural rollout in
[`thesis/ch3_system_architecture.md`](thesis/ch3_system_architecture.md).

---

## 2026-06-15 — Threshold calibration instrument (`calibrate.py`)

The real-time grader gated user input on absolute-pixel constants tuned for the
1920×1080 biomech renders (`MIN_PRESS_VELOCITY`, `WRIST_*`, MediaPipe
confidences); on a real webcam recording they are silently wrong and nothing
reported it. Built the measurement that unblocks "tune the thresholds".

- ✓ NEW `webui/realtime/calibrate.py` — runs the runner's tracking + history +
  A/V-sync machinery over a recording and reports, per threshold, the
  distribution it gates on (detection rate, max press velocity at onsets,
  |wrist deviation|) + data-driven recommended values + a 1080p resolution-scale
  note. `--out` writes a `CalibrationReport` JSON.
- ✓ Honest degenerate-case output: at 0 tracked onsets it says "nothing to
  measure" instead of a misleading "✓ 0% blind presses".
- ✓ `runner.py` `--detect-confidence` / `--track-confidence` flags (pass through
  to `HandTracker`, defaults unchanged) so the tracking finding is actionable.
- ✓ Verified: 22 new unit tests; real-frame negative control on the biomech
  render (0% detection → ⚠ warning fires); runner smoke with the new flags;
  full fast suite **108 passed**.
- Additive only — verified grading pipeline behavior unchanged.

### Comparator thresholds made injectable (apply path)
- ✓ NEW frozen `Thresholds` dataclass in `comparator.py` — every field defaults
  to the legacy module constant, so `Thresholds()` (and any call without `thr=`)
  reproduces today's behavior exactly. Threaded `thr=` through `compare_onset`,
  `wrist_status`, `detect_press_finger`.
- ✓ `Thresholds.from_calibration(report)` / `from_json(path)` map calibrate's
  `recommended.{min_press_velocity, wrist_threshold_px}` (None → keep default).
- ✓ `runner.py --calibration calib.json` applies them to grading — no source
  edit needed to act on a recording's recommendations.
- ✓ Verified: 5 new comparator tests (default ≡ constants; custom velocity flips
  press verdict; custom wrist threshold flips through `compare_onset`;
  from_calibration mapping + None-skip); runner `--calibration` smoke; full fast
  suite **113 passed**. The measure→recommend→apply loop is now complete on
  replay; only the threshold *values* wait on a real recording.

## 2026-05-26 — Beethoven cross-piece + Universal Winner claim revised

### Beethoven Op.2 No.1 mvt 1 audit
- ✓ Downloaded Mutopia public-domain MIDI (1675 notes, 191s)
- ✓ Generated RH n=464 / LH n=406 rule-based GT
- ✓ Four-way audit, neutral subset:
    - RH: pianoplayer Soft **0.662** vs ArLSTM 0.359 (pp wins, +0.303)
    - LH: ArLSTM 0.379 vs pianoplayer 0.335 (ArLSTM barely wins +0.044)
- ✓ Updated `eval_data/audit_results.json` with beethoven_op2no1_mvt1 block
- ✓ ch4 §4.6.4 NEW: Beethoven results + §4.6.5 修正 thesis claim + §4.6.6 methodological caveats (HAND_SPLIT, artifact rate)
- ✓ ch7 §7.1 RQ2 answer revised: "style + hand 雙重 dependent" with 4-row context table

### Key thesis revision
Previous claim (after Bach): "ArLSTM wins LH consistently across pieces"
NEW claim (after Beethoven): "ArLSTM LH dominance is texture-dependent — works on regular Alberti/contrapuntal bass, breaks down on angular Classical sonata LH"

## 2026-05-24 — Stage D OSMD sheet music + Wrist feedback v1

### Wrist height feedback v1
- ✓ `comparator.py` `HandHistory` 加 wrist_buf 雙手追蹤
- ✓ `wrist_status()` 函式：rolling-median 4 秒視窗為 baseline，arched/collapsed/good/unknown 4 個狀態
- ✓ `OnsetResult` 加 `wrist_status` + `wrist_deviation_px` 欄位
- ✓ `runner.py` broadcaster.publish 加 wrist fields 推給 WS clients
- ✓ `PracticeScreen.js` FeedbackOverlay 加 wrist warning badge（顯示「⚠ 手腕太高/太低」+ 偏離 px）
- ✓ ch7 §7.3.3 limitation 更新成 "wrist v1 done, finger curvature 未做"

### Stage D OSMD sheet music integration

- ✓ `midi_to_musicxml.py` — MIDI → MusicXML via music21
- ✓ `--annotate-fingering` flag — attach ArLSTM Fingering tags by
  position-indexed alignment (94.6% Canon RH coverage)
- ✓ `songs/{canon,canon_with_fingering,bach_invention_01}.musicxml`
- ✓ OSMD v1.8.7 via jsDelivr CDN added to `webui/index.html`
- ✓ `webui/src/OSMDScore.js` — React wrapper for OSMD
- ✓ `PracticeScreen.js` Sheet Music card swaps placeholder Staff for
  `<OSMDScore/>` when scoreUrl available; falls back to Staff otherwise
- ✓ `songs.json` canon entry adds `scoreUrl` pointing at fingering-annotated XML
- ✓ ch6 §6.2.7 rewritten to describe OSMD integration (was placeholder note)
- ✓ ch6 §6.5 + ch7 §7.3.3 limitations updated to reflect what's now done
  vs remaining (OSMD cursor sync precision)

## 2026-05-23 — Bach Invention cross-piece + 文件套件補完

### Bach Invention No.1 BWV 772 cross-piece audit
- ✓ 下載 Bach MIDI (Mutopia, Public Domain)
- ✓ 生成 RH n=181 / LH n=124 rule-based GT
- ✓ 修 `four_way_audit.py --fingertips` 為 optional
- ✓ 跑四方 audit (RH + LH × full + neutral)
- ✓ **Key finding**: pianoplayer 在 Bach RH 反超 (Soft 0.734 vs ArLSTM 0.406)，LH 維持 ArLSTM 大幅領先
- ✓ ch4 §4.6 重寫成三節（Summer / Bach / 修正後 claim）
- ✓ ch7 §7.1 RQ2 答案改成 style-dependent
- ✓ ch7 §7.4.1 加 style-aware Logic Track 自動切換
- ✓ defense_qa.md 加 Q1.5 (「Bach 反例怎麼解釋」)
- ✓ defense_slides.md 增加 Bach slide + Bach Q&A
- ✓ `eval_data/audit_results.json` 加 bach_invention_01 block

### Defense-ready package（昨日）
- ✓ `tests/` pytest suite (50/50 green; pins ch4 numbers)
- ✓ `Makefile` — `make thesis | docx | tex | slides | chapter CH=N`
- ✓ `THESIS.md` repo entry point (links to thesis/, key results, demo commands)
- ✓ `thesis/defense_slides.md` Marp slide deck (~20 slides)
- ✓ `thesis/defense_qa.md` predicted reviewer Q&A
- ✓ `thesis/references.bib` BibTeX (12 entries)
- ✓ `thesis/README.md` thesis-directory guide
- ✓ `songs/canon_henle_fingering.json` sample manual override
- ✓ `bin/regenerate_all.sh` one-shot regeneration script
- ✓ `bin/demo_defense.sh` tmux-based defense-day launcher
- ✓ `eval_data/audit_results.json` frozen snapshot
- ✓ `figures/*.mmd` + finger distribution PNGs
- ✓ `Makefile` + `THESIS.md` + `CHANGELOG.md`

## 2026-05-22 — Stage A → B → C 全部關閉 + 7 章 thesis draft

### Defense-ready package
- ✓ `tests/` pytest suite (50/50 green; pins ch4 numbers)
- ✓ `Makefile` — `make thesis | docx | tex | slides | chapter CH=N`
- ✓ `THESIS.md` repo entry point (links to thesis/, key results, demo commands)
- ✓ `thesis/defense_slides.md` Marp slide deck (~20 slides)
- ✓ `thesis/defense_qa.md` predicted reviewer Q&A
- ✓ `thesis/references.bib` BibTeX (12 entries)
- ✓ `thesis/README.md` thesis-directory guide
- ✓ `songs/canon_henle_fingering.json` sample manual override
- ✓ `bin/regenerate_all.sh` one-shot regeneration script
- ✓ `CHANGELOG.md` (this file)

### Thesis chapters (1032 lines markdown total)
- ✓ ch1 Introduction (54 lines) — motivation, RQs, contributions, structure
- ✓ ch2 Related Work (90) — fingering / motion / teaching system literature
- ✓ ch3 System Architecture (190) — Dual-Track + Stage A/B/C details
- ✓ ch4 Evaluation (225) — corpus audit, finger distribution, failure modes
- ✓ ch5 Implementation (210) — MIDI alignment, Ramoneda integration, ffmpeg fix
- ✓ ch6 User Experience (176) — PracticeScreen UI components, interaction flow
- ✓ ch7 Conclusion (87) — findings, limitations, future work

### Integration pipeline
- ✓ Stage A: ArLSTM as default Logic Track (commits f7ebf8a, 2e91953)
- ✓ Stage B: ArLSTM in render pipeline (commit 70e83c6)
- ✓ Stage C: PracticeScreen ArLSTM reference wiring (commit 4a15909)
- ✓ Summer cross-piece validation (commit 2a45a59)
- ✓ NotebookLM audit doc with all numbers (commit d1a1955)

### Headline numbers (frozen for thesis)
- Corpus RH+LH neutral subset, n=183:
  - **ArLSTM Soft 0.792** (winner)
  - ArGNN 0.654 (-17% relative)
  - pianoplayer 0.578 (-27% relative)
  - motion_v4 0.358 (-55% relative)
- LH-only (n=40 neutral): pianoplayer Soft 0.275 — systematic-failure
  evidence vs ArLSTM 0.975

---

## 2026-05-21 — Stage A corpus audit + ArLSTM judge

### Major changes
- Built `evaluate_template.py` GT-format + scoring API
- Hand-curated `eval_data/canon_rh_gt.json` first 12 onset teacher's-answer-key
- Single-track `evaluate_canon.py` runner
- Two-track `cross_audit_canon.py` (Logic vs Visual)
- Four-way `four_way_audit.py` (pianoplayer / motion / ArLSTM / ArGNN)
- `ramoneda_predict.py` wrapper for Ramoneda 2022 pretrained checkpoints
- Refactored `webui/realtime/fingering_engine.py` to dispatch by source
- Switched `--fingering-source` default from pianoplayer to arlstm
- Generated rule-based GT `eval_data/canon_rh_rulebased_gt.json` n=186
- NotebookLM-ready writeup `notes/2026-05-21_arlstm_dual_track_audit.md`

### Findings
- ArLSTM beats pianoplayer Soft +0.078 on RH neutral subset (n=143)
- pianoplayer LH ring usage: 2/107 (= 1.9%, structural cost-model bias)

---

## 2026-05-19 — Architecture pivot: Dual-Track Decoupling

- Identified Phase A problem: motion_v4 used as both judge & renderer leaks
  generative randomness into judgment scoring
- Designed Dual-Track Decoupling: separate deterministic Logic Track (judge)
  from Visual Track (renderer)
- Cross-audit found motion-based agreed with pianoplayer on only 24.4% of
  Canon notes (47 thumb-bias cases) → justifying the pivot

---

## 2026-05-17 — Phase B v0 (real-time webui)

- Built `webui/realtime/` module set: sources, hand_tracker, comparator,
  clip_recorder, broadcaster, runner
- React `PracticeScreen` with FeedbackOverlay, RecordingBanner, ClipsStrip,
  PianoRoll
- WebSocket transport from runner → browser (port 8766)
- Replay-mode CLI for testing without webcam: `--video file.mp4 --fast`

---

## 2026-05-15 — Phase A locked: biomech v4 baseline

- Biomechanical fingering Viterbi solver locked at:
  - ring_finger_stretch_multiplier=1.7
  - wide_chord_span_threshold=7
  - wide_chord_boundary_penalty=200
  - blackkey thumb=300 / pinky=80
- Canon right-hand pinky usage stabilized at 9.7%
- Pivoted to UI/UX work and Stage B/C integration

---

## Earlier (March–May 2026) — Phase A iteration

- v2: uniform black-key penalty
- v3: split black-key penalty (extremum-reward heuristic)
- v4: anatomy-based ring nerf + wide-chord rule (final)
- mir_eval benchmark suite: note F1 = 0.984 on PianoMotion10M (commit 68f558b)
- Anticipation pre-pass + 5-finger balance (commit ae5b27b)
- Keyboard overlay decay + ghost-key filter (commit 16f4340)
- Decouple MIDI extraction from gentle_fix rendering (commit 334be92)
- ByteDance MIDI extraction replaces basic_pitch (commit 424c7b5)

---

## Pre-thesis (upstream)

- Forked from PianoMotion10M (Liu et al., ICLR 2025 Spotlight)
- Upstream provides: 116 hr piano video dataset, 10M MANO hand pose annotations,
  audio-to-motion diffusion model, evaluation metrics
