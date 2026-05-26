# Project Status Summary — 2026-05-26

**One-page status card for advisor handoff & next-session pickup.**

---

## 完成度盤點

| 領域 | 狀態 | 量化證據 |
|---|---|---|
| **Phase A** biomech v4 baseline | ✅ Locked 2026-05-15 | RH pinky 9.7%, 4 hyperparams 鎖定 |
| **Phase B Stage A** Logic Track | ✅ Shipped | ArLSTM as default, 71 tests passing |
| **Phase B Stage B** Render pipeline | ✅ Shipped | Canon + Summer mp4 rendered |
| **Phase B Stage C** PracticeScreen UI | ✅ Shipped | songs.json wired, end-to-end smoke test passed |
| **Stage D** OSMD sheet music | ✅ Shipped 2026-05-24 | 296/313 fingering tags on Canon |
| **Stage D** Wrist height feedback v1 | ✅ Shipped 2026-05-24 | 13 unit tests, rolling-median calibration |
| **Stage D** Hardware live mode | ⏸ User-action required | Needs webcam + MIDI keyboard plugged in |
| **Stage D** Finger curvature feedback | ☐ Future work | Needs 3D MediaPipe landmarks |
| **Stage D** Local DTW chord matching | ☐ Future work | Substantial refactor |
| **Stage E** Demo recording | ⏸ User-action | Open webui + screen capture |
| **Stage E** Thesis defense | ⏸ User-action | Advisor review + slides rehearsal |

---

## Thesis Headline Numbers (Frozen)

**Canon corpus n=183 predictor-neutral subset:**
- ArLSTM Soft **0.792** (winner)
- ArGNN 0.654 (-17% relative)
- pianoplayer 0.578 (-27% relative)
- motion_v4 0.358 (-55% relative)

**Bach Invention cross-piece reveal (nuance):**
- Bach RH n=122: pianoplayer 0.734 ← reverses on scalar passages
- Bach LH n=78: ArLSTM 0.878 ← LH dominance persists

**Distribution evidence (Canon, n=344 notes):**
- LH ring: pianoplayer 2 → ArLSTM 14 (+600%)
- RH pinky: pianoplayer 66 → ArLSTM 26 (-60%)

---

## File Inventory

| Category | Count | Location |
|---|---|---|
| Thesis chapters + front-matter | 14 .md | `thesis/` |
| Defense materials | 3 (slides, Q&A, BibTeX) | `thesis/defense_*` + `thesis/references.bib` |
| Python source | 9 new + edits | repo root + `webui/realtime/` |
| Tests | 71 tests in 4 files | `tests/` |
| Figures (PNG + SVG + Mermaid) | 9 files | `figures/` |
| Eval ground-truth files | 7 JSON | `eval_data/` |
| MusicXML scores | 3 files | `songs/` |
| Build infrastructure | Makefile + 3 scripts | repo root + `bin/` |

---

## Reproducibility — Single Commands

```bash
# First-time setup (interactive)
bin/setup.sh

# Reproduce all audit numbers (~15 min)
bin/regenerate_all.sh

# Unit tests only (1.4s)
python -m pytest tests/ -q --ignore=tests/test_audit_pipeline_integration.py

# Full tests including integration (12 min, loads Ramoneda ckpts)
python -m pytest tests/ -q

# Build full thesis PDF (needs pandoc + xelatex)
make thesis

# Build defense slides PDF (needs marp-cli)
make slides

# Open defense demo in tmux
bin/demo_defense.sh canon
```

---

## What User Needs to Do Next

1. **Push** the 27 commits to your fork
   - Auth blocker — see earlier session notes for fork instructions
2. **Show advisor** the 4 core chapters (ch1, ch2, ch3, ch4)
   - 中文 + English abstracts ready in `thesis/abstract_*.md`
   - Format conversion: `make docx` or `make thesis`
3. **Defense preparation**
   - Slide deck: `thesis/defense_slides.md` (Marp format)
   - Q&A cheat sheet: `thesis/defense_qa.md`
   - Demo launch: `bin/demo_defense.sh`
4. **Optional Stage D follow-ups** (if time permits)
   - Hardware live mode setup (webcam + MIDI keyboard)
   - Tempo-precise OSMD cursor (small polish)
   - Mozart / Chopin cross-piece (extra evidence)

---

## Commit Log (this session: 27 commits)

```
9f4a223  test    wrist_status unit tests (13/13 ✓)
3adc8b7  feat    Stage D wrist height feedback v1
8f126a6  docs    ch6/ch7/CHANGELOG OSMD updates
37a0838  feat    Stage D OSMD sheet music + fingering annotations
748b355  test    audit integration tests + setup.sh
fddb3dd  docs    thesis front-matter (abstracts, ack, lists)
f667054  docs    Bach finger distribution figures
0ed37f5  docs    Bach finding integration into ch7/slides/Q&A
0c42ed4  feat    Bach Invention cross-piece audit
d944e41  docs    frozen audit results + demo_defense.sh
579408f  docs    Mermaid architecture diagrams
95b50f7  docs    finger distribution viz + ch4 embed
c154ae3  test    pytest suite (50/50 ✓)
9deded8  docs    manual override + regenerate script + CHANGELOG
0b495e9  docs    THESIS.md entry + pandoc Makefile
c4bb39b  docs    defense package (slides + Q&A + BibTeX)
4cb2c84  docs    ch5/6/7 thesis drafts
ef7e561  docs    ch1/ch2 thesis drafts
d2024c3  docs    ch3 architecture chapter
fbf6cce  docs    ch4 evaluation chapter
d1a1955  docs    NotebookLM audit notes update
2a45a59  feat    LH corpus GT + Summer pipeline
4a15909  feat    Stage C PracticeScreen ArLSTM wire
70e83c6  feat    Stage B ArLSTM render integration
2e91953  feat    rule-based corpus GT + four-way audit (RH n=186)
f7ebf8a  feat    ArLSTM as default Logic Track
```

---

## Bottom Line

The thesis is **ready to send to your advisor**. Code is comprehensively
tested, documented, and reproducible. The remaining work is user-only
(push to fork, advisor feedback loop, demo recording, defense day).
