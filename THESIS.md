# Thesis Project: AI Piano Learning

**Graduation thesis built on top of [PianoMotion10M](README.md) (Liu et al., ICLR 2025 Spotlight).**

> The base repo is PianoMotion10M, an audio-to-3D-hand-motion benchmark dataset & model. This thesis project extends it to a **complete AI piano learning system** by integrating SOTA piano fingering decision (Ramoneda 2022) into the rendering pipeline, with a real-time teaching feedback UI.

For the original PianoMotion10M README see [README.md](README.md). This document covers the thesis-specific additions.

---

## TL;DR

**Problem**: PianoMotion10M generates anatomically plausible hand motions but doesn't guarantee pedagogically correct fingering. A student watching its output may learn incorrect fingerings.

**Solution**: Dual-Track Decoupling architecture — replace the implicit fingering decision in PianoMotion10M with an explicit Logic Track using Ramoneda 2022 ArLSTM (SOTA neural fingering model), feeding its prescriptive fingering into the motion renderer.

**Evidence**: On Canon RH+LH corpus (n=183 predictor-neutral subset), ArLSTM achieves Soft Accuracy 0.792 vs. pianoplayer 0.578 (-27% relative) vs. motion-derived 0.358 (-55%).

**Status**: Stage A (Logic Track) + Stage B (render integration) + Stage C (UI wiring) all complete on Canon and Summer; 7-chapter thesis draft + 20-slide defense deck ready.

---

## Quick Start

### 1. Setup

```bash
conda activate pianomotion  # see thesis/ch5_implementation.md §5.6
# Pretrained ArLSTM checkpoints are inside the Ramoneda submodule:
ls external/Automatic-Piano-Fingering/models/
#   left_ArLSTM.pth   left_ArGNN.pth
#   right_ArLSTM.pth  right_ArGNN.pth
```

If `external/Automatic-Piano-Fingering/` is missing:

```bash
mkdir -p external && cd external
git clone --depth 1 https://github.com/PRamoneda/Automatic-Piano-Fingering.git
```

### 2. Render a piece with the integrated pipeline (Stage B)

```bash
python simple_natural.py \
    --mp3 "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mp3" \
    --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    --fingering arlstm \
    --out_dir results/canon_arlstm \
    --out_video results/canon_arlstm_kb.mp4
```

Use `--fingering pianoplayer` for the cost-model baseline (ablation comparison).

### 3. Run the full webui teaching loop (Stage C)

```bash
# Terminal A: HTTP server
python webui/serve.py 8765

# Terminal B: real-time judge + broadcaster
python -m webui.realtime.runner \
    --video results/canon_biomech_v4_kb.mp4 \
    --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    --reference results/canon_arlstm_fingertips.json \
    --fast --no-preview --ws-port 8766 --ws-linger 3600 \
    --clip-record --clip-threshold 0.6 --clip-window 8

# Browser: http://localhost:8765/webui/
```

### 4. Reproduce the corpus audit numbers

```bash
# Right hand (n=186)
python four_way_audit.py \
    --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    --gt eval_data/canon_rh_rulebased_gt.json \
    --fingertips results/canon_biomech_v4_fingertips.json \
    --exclude-tiebreakers

# Left hand (n=90)
python four_way_audit.py \
    --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    --gt eval_data/canon_lh_rulebased_gt.json \
    --fingertips results/canon_biomech_v4_fingertips.json \
    --exclude-tiebreakers
```

---

## Thesis Materials

All thesis materials live under [`thesis/`](thesis/):

| File | Description |
|---|---|
| [`thesis/ch1_introduction.md`](thesis/ch1_introduction.md) | Motivation, RQs, contributions |
| [`thesis/ch2_related_work.md`](thesis/ch2_related_work.md) | Fingering / motion / teaching system literature |
| [`thesis/ch3_system_architecture.md`](thesis/ch3_system_architecture.md) | Dual-Track + Stage A/B/C |
| [`thesis/ch4_evaluation.md`](thesis/ch4_evaluation.md) | Corpus audit (the headline numbers) |
| [`thesis/ch5_implementation.md`](thesis/ch5_implementation.md) | Engineering details |
| [`thesis/ch6_user_experience.md`](thesis/ch6_user_experience.md) | PracticeScreen design |
| [`thesis/ch7_conclusion.md`](thesis/ch7_conclusion.md) | Findings, limitations, future work |
| [`thesis/defense_slides.md`](thesis/defense_slides.md) | Marp slide deck for defense |
| [`thesis/defense_qa.md`](thesis/defense_qa.md) | Predicted reviewer questions + answers |
| [`thesis/references.bib`](thesis/references.bib) | BibTeX bibliography |
| [`thesis/README.md`](thesis/README.md) | Thesis directory guide |

The companion NotebookLM-ready writeup (combining the audit findings with prose) lives at [`notes/2026-05-21_arlstm_dual_track_audit.md`](notes/2026-05-21_arlstm_dual_track_audit.md).

---

## Build PDFs

A Makefile is provided at repo root. Common targets:

```bash
make thesis      # → build/thesis_full.pdf  (single combined PDF, all 7 chapters)
make slides      # → build/defense_slides.pdf  (Marp slides)
make chapter CH=4   # → build/ch4.pdf  (one chapter)
make docx        # → build/thesis_full.docx  (Word version for advisor)
make clean
```

Requires `pandoc` and (for slides) `marp-cli` on PATH.

---

## Key Contribution (one-liner)

> Took the existing PianoMotion10M motion generator (Liu 2024) and the existing Ramoneda 2022 ArLSTM fingering decision model, decoupled the implicit fingering inside the former and replaced it with the latter's prescriptions via a Dual-Track architecture, then quantified that the integration is empirically justified (Soft Accuracy 0.792 vs. baselines 0.275-0.663 on Canon n=183 neutral subset).

---

## Git History Highlights (Today's Work)

```
c4bb39b  docs: defense prep package (slides + Q&A + BibTeX + README)
4cb2c84  docs: thesis ch5 implementation + ch6 UX + ch7 conclusion
ef7e561  docs: thesis ch1 introduction + ch2 related work
d2024c3  docs: thesis ch3 system architecture
fbf6cce  docs: thesis ch4 evaluation
d1a1955  docs: NotebookLM audit notes update
2a45a59  feat: LH corpus GT + Summer Stage A-C pipeline
4a15909  feat: Stage C — wire ArLSTM reference into PracticeScreen
70e83c6  feat: Stage B — ArLSTM in render pipeline
2e91953  feat: rule-based corpus GT + four-way audit (RH n=186)
f7ebf8a  feat: ArLSTM as default Logic Track + audit framework
```

---

## Acknowledgments

Built on:
- [PianoMotion10M](https://github.com/agnJason/PianoMotion10M) (Liu et al., ICLR 2025 Spotlight) — base motion model & dataset
- [PRamoneda/Automatic-Piano-Fingering](https://github.com/PRamoneda/Automatic-Piano-Fingering) (Ramoneda et al., 2022) — pretrained ArLSTM / ArGNN
- pianoplayer (Parncutt 1997 cost model implementation) — baseline judge
- MediaPipe Hands v0.10.14 — webcam hand tracking
