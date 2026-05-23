# CHANGELOG

Chronological log of thesis-project milestones. Newest first.

The "Phase / Stage" labels match the architectural rollout in
[`thesis/ch3_system_architecture.md`](thesis/ch3_system_architecture.md).

---

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
