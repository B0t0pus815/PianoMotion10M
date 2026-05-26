# Session Complete — AI 鋼琴學習 thesis 全套工作整理
**Date range**: 2026-05-22 ~ 2026-05-26
**Repo**: PianoMotion10M (forked, thesis 整合層 + 量化評估)
**Status**: thesis 整套 advisor-ready，等 push 跟教授 review

---

## 摘要 (TL;DR)

從「biomech v4 是不是合格糾正模板」這一個質疑開始，做完整個 Stage A → B → C → D 的整合工作 + 量化評估 + 7 章 thesis draft + defense 材料。共 **31 個 commits、~6000 行 net change** 跨 5 天。

**核心 finding**：在 Canon corpus n=183 predictor-neutral subset 上，Ramoneda 2022 ArLSTM Soft Accuracy **0.792** 顯著優於 pianoplayer (0.578, -27%) 與 motion-derived baseline (0.358, -55%)。Cross-piece 在 Bach Invention No.1 揭示 ArLSTM **不是 universal winner**——RH scalar 段落 pianoplayer 反超，但 LH 跨曲一致 ArLSTM 大幅領先。

**架構決策**：Dual-Track Decoupling——把 fingering judgment (Logic Track, ArLSTM) 跟 hand rendering (Visual Track, biomech v4) 解耦。Stage A→B→C 三階段把同一個指法決策貫穿到評分、視覺示範、UI。

---

## 1. 工作時序 (Chronological)

### Day 1 — 2026-05-22

**Stage A 基礎建設**：

- 寫 `evaluate_template.py`：GT JSON schema + Hard/Soft Accuracy 評分 API
- 手工寫 `eval_data/canon_rh_gt.json` (n=12) 當初步 GT
- 寫 `evaluate_canon.py`、`cross_audit_canon.py`、`four_way_audit.py` 評估 runners
- 寫 `ramoneda_predict.py` 包 Ramoneda 2022 ArLSTM/ArGNN 預訓練 checkpoint
- Refactor `webui/realtime/fingering_engine.py` 加 `generate_fingering(source='arlstm')` dispatch
- 把 `--fingering-source` default 從 pianoplayer 改成 arlstm
- 寫 `build_gt_rulebased.py` 自動產生 GT (interval rules + stepwise continuity + consensus + tiebreaker)
- 把 RH GT 擴展到 n=186 (rule-based)
- 四方 audit：ArLSTM 在 RH neutral subset Soft 0.741 vs pianoplayer 0.663

**Stage B 整合**：

- `simple_natural.py` 加 `apply_arlstm_fingering()` drop-in replacement
- CLI 加 `--fingering arlstm` choice
- 修 `add_keyboard_overlay.py` ffmpeg encoder `libopenh264 → libx264` bug
- 跑出 `results/canon_arlstm_kb.mp4` (8.3 MB, 3:11)
- 產 `results/canon_arlstm_vs_biomech.mp4` 並排對比

**Stage C UI 接軌**：

- `webui/songs.json` videoUrl 換成 ArLSTM render
- `PracticeScreen.js` fallback path + brand label `AI · ArLSTM × biomech v4`
- End-to-end smoke test：runner log 確認 `[ref] 344 expected onsets — Logic Track (Ramoneda ArLSTM)`

**LH 擴展 + cross-piece**：

- LH rule-based GT n=90，audit 顯示 pianoplayer LH 是 systematic failure (Soft 0.275 vs ArLSTM 0.975)
- Summer (J-pop) cross-piece pipeline 通過性測試
- NotebookLM doc 更新

### Day 2 — 2026-05-23

**Bach Invention cross-piece**：

- 從 Mutopia 下載 Bach Invention No.1 BWV 772 MIDI
- 修 `four_way_audit.py` 讓 `--fingertips` 變 optional（Bach 沒 biomech 渲染）
- Bach RH 結果**反轉**：pianoplayer 0.734 vs ArLSTM 0.406
- Bach LH 結果一致：ArLSTM 0.878 vs pianoplayer 0.391
- 把 finding 滲透到 ch7 (RQ2 答案改成 "style-dependent")、defense_qa.md 加 Q1.5、defense_slides.md 加 Bach 對比 slide

**Thesis 7 章寫作**：

- ch1 Introduction (motivation, RQ, contributions, structure)
- ch2 Related Work (指法決策 / 動作生成 / 教學系統三領域)
- ch3 System Architecture (Dual-Track + Stage A/B/C)
- ch4 Evaluation (corpus audit + finger distribution + Bach + 失敗模式)
- ch5 Implementation (MIDI 對齊 / Ramoneda integration / ffmpeg fix / WS broadcaster)
- ch6 User Experience (PracticeScreen UI 元件 + 互動流程)
- ch7 Conclusion (findings + limitations + future work)
- 合計 1032 行 markdown

**Defense package**：

- `thesis/defense_slides.md` Marp 格式 20 張 slides
- `thesis/defense_qa.md` 預期 reviewer Q&A
- `thesis/references.bib` 12 條 BibTeX
- `thesis/README.md` 目錄 guide
- `bin/regenerate_all.sh` 一鍵重做所有 audit
- `bin/demo_defense.sh` tmux 啟動 defense demo
- `THESIS.md` repo entry
- `Makefile` (make thesis | slides | docx | tex)
- `CHANGELOG.md`
- `eval_data/audit_results.json` 凍結快照
- `songs/canon_henle_fingering.json` manual override sample

**Tests**：

- `tests/test_evaluate_template.py` 17 unit tests
- `tests/test_build_gt_rulebased.py` 33 unit tests
- `tests/test_audit_pipeline_integration.py` 8 integration tests (12 min)

**Visualization**：

- `visualize_finger_distribution.py` matplotlib script
- `figures/finger_dist_*.png` Canon RH/LH/combined (PNG 300 dpi)
- `figures/bach/finger_dist_*.png` Bach RH/LH/combined
- `figures/*.mmd` 3 個 Mermaid 架構圖 source
- ch4 §4.5 + 4.6.2 embed 圖片

### Day 3 — 2026-05-24

**Stage D OSMD 整合**：

- `pip install music21`
- `midi_to_musicxml.py` MIDI → MusicXML converter
- `--annotate-fingering` flag：用 position-indexed alignment 把 ArLSTM 指法 attach 到 MusicXML Fingering tags（Canon RH 296/313 = 94.6% 覆蓋）
- `songs/canon.musicxml`、`canon_with_fingering.musicxml`、`bach_invention_01.musicxml`
- `webui/index.html` 加 OSMD 1.8.7 via jsDelivr CDN
- `webui/src/OSMDScore.js` React wrapper for OSMD
- `PracticeScreen.js` Sheet music card 換成 `<OSMDScore/>`，舊 Staff 當 fallback
- `songs.json` canon 加 `scoreUrl`
- ch6 §6.2.7 重寫成 "OSMD shipped"

**Stage D Wrist height feedback v1**：

- `comparator.py` `HandHistory` 加 `wrist_buf` 雙手追蹤
- `wrist_status()` 函式：rolling-median 4 秒視窗作 baseline (per-student calibration)，arched/collapsed/good/unknown 4 個狀態
- `OnsetResult` 加 `wrist_status` + `wrist_deviation_px` 欄位
- `runner.py` broadcaster 加 wrist fields
- `PracticeScreen.js` FeedbackOverlay 加 wrist warning chip

### Day 4 — 2026-05-25/26

**測試補完 + audit 清理**：

- `tests/test_comparator.py` 13 unit tests for wrist v1 + HandHistory
- 總 test count 71 (50 unit + 13 wrist + 8 integration)
- `STATUS_SUMMARY.md` 一頁總覽 for advisor handoff
- Audit 找到 3 個 SVG 引用沒對應檔（mermaid mmd 沒 render 過）→ 用 mermaid.ink 公開 service 渲染補上
- `tests/conftest.py` 註冊 pytest `slow` marker（壓掉 warning）

---

## 2. 完成項目按類別

### 2.1 Pipeline 整合 (Stages A/B/C/D)

| Stage | 內容 | 主要 commit |
|---|---|---|
| **A** | Logic Track = Ramoneda 2022 ArLSTM (default) + rule-based corpus GT (RH n=186 + LH n=90 + Bach RH n=181 + Bach LH n=124) | f7ebf8a, 2e91953, 2a45a59, 0c42ed4 |
| **B** | `simple_natural --fingering arlstm` 渲染 mp4 (Canon + Summer); libx264 fix | 70e83c6 |
| **C** | PracticeScreen videoUrl + label 接 Stage B 輸出 | 4a15909 |
| **D-1** | OSMD 樂譜 + ArLSTM 指法 annotation (94.6% coverage on Canon) | 37a0838 |
| **D-2** | Wrist height feedback v1 (rolling-median per-student calibration) | 3adc8b7 |
| **D-3** | (Pending) Hardware live mode, finger curvature, DTW chord matching | — |

### 2.2 評估框架

| 元件 | 檔案 |
|---|---|
| GT JSON schema + Hard/Soft API | `evaluate_template.py` |
| Rule-based GT 自動生成器 | `build_gt_rulebased.py` |
| 單一 track 評估 | `evaluate_canon.py` |
| 雙方 Logic vs Visual audit | `cross_audit_canon.py` |
| 四方 audit + predictor-neutral subset flag | `four_way_audit.py` |
| Ramoneda 模型 inference wrapper | `ramoneda_predict.py` |
| Interactive GT 標註 helper | `build_gt_interactive.py` |
| Finger distribution matplotlib | `visualize_finger_distribution.py` |
| MIDI → MusicXML (含 fingering annotation) | `midi_to_musicxml.py` |

### 2.3 Test suite

| 檔案 | tests | 覆蓋 |
|---|---|---|
| `test_evaluate_template.py` | 17 | Hard/Soft API + corpus eval + GT loader |
| `test_build_gt_rulebased.py` | 33 | Chord rules table + artifact + stepwise + decide |
| `test_comparator.py` | 13 | wrist_status + HandHistory + compare_onset wrist propagation |
| `test_audit_pipeline_integration.py` | 8 | end-to-end audit pipeline frozen-result reproducibility (slow, ~12 min) |
| `conftest.py` | — | 註冊 'slow' marker |
| **Total** | **71** | (63 fast in 1.4s + 8 slow in 12 min) |

### 2.4 Thesis 寫作 (~1700 行 markdown)

| 檔案 | 內容 | 行數 |
|---|---|---|
| `thesis/ch1_introduction.md` | 緒論 (motivation, RQ, contributions) | 54 |
| `thesis/ch2_related_work.md` | 文獻回顧 (指法 / 動作 / 教學系統) | 90 |
| `thesis/ch3_system_architecture.md` | Dual-Track + Stage A/B/C 設計 | 190 |
| `thesis/ch4_evaluation.md` | corpus audit + Bach + finger distribution | 250+ |
| `thesis/ch5_implementation.md` | 工程細節 + reproducibility | 210 |
| `thesis/ch6_user_experience.md` | UI 元件 + 互動 + OSMD 整合 | 200 |
| `thesis/ch7_conclusion.md` | findings + limitations + future work | 110 |
| `thesis/abstract_zh.md` | 中文摘要 (約 600 字) | 30 |
| `thesis/abstract_en.md` | English abstract (約 450 words) | 30 |
| `thesis/acknowledgments.md` | 致謝（含 AI assistance scope disclosure）| 30 |
| `thesis/figures_tables_list.md` | 圖目錄 / 表目錄 | 50 |
| `thesis/defense_slides.md` | Marp slides 20 張 | 290 |
| `thesis/defense_qa.md` | 預期 Q&A 6 大類 | 340 |
| `thesis/references.bib` | BibTeX 12 條 | 113 |
| `thesis/README.md` | thesis directory guide | 130 |

### 2.5 Figures (300 dpi PNG + SVG + Mermaid source)

| 檔案 | 章節引用 |
|---|---|
| `figures/finger_dist_combined.png` | ch4 §4.5 |
| `figures/bach/finger_dist_combined.png` | ch4 §4.6.2 |
| `figures/dual_track_architecture.svg` | ch3 §3.2 圖 3.1 |
| `figures/stage_pipeline.svg` | ch3 §3.6 圖 3.2 |
| `figures/eval_methodology.svg` | ch4 §4.1 圖 4.0 |
| `figures/*.mmd` (3 個) | Mermaid source 供 regenerate |

### 2.6 Build infrastructure

- `Makefile` — `make thesis | docx | tex | slides | chapter CH=N`
- `bin/setup.sh` — 第一次安裝 5 步流程
- `bin/regenerate_all.sh` — 重做所有 audit + render
- `bin/demo_defense.sh` — tmux 啟動 defense demo
- `STATUS_SUMMARY.md` — 一頁狀態卡
- `THESIS.md` — repo entry point
- `CHANGELOG.md` — 跨日紀錄

---

## 3. 關鍵數字 (Frozen for thesis)

### 3.1 Headline — Canon RH+LH 合併 n=183 neutral subset

| Track | Soft Accuracy | vs ArLSTM 相對差距 |
|---|---|---|
| **ArLSTM** (winner) | **0.792** | — |
| ArGNN | 0.654 | -17% |
| pianoplayer | 0.578 | -27% |
| motion_v4 | 0.358 | -55% |

### 3.2 Per-hand breakdown

**Canon RH (n=143 neutral)**：ArLSTM 0.741 vs pianoplayer 0.663（差 +0.078）

**Canon LH (n=40 neutral)**：ArLSTM 0.975 vs pianoplayer 0.275（差 +0.700，pp ≈ systematic failure）

**Bach RH (n=122 neutral)**：pianoplayer 0.734 vs ArLSTM 0.406（反向，pp 在 scalar 段落贏）

**Bach LH (n=78 neutral)**：ArLSTM 0.878 vs pianoplayer 0.391（差 +0.487，跟 Canon LH 一致）

### 3.3 Finger distribution (Canon 全曲 344 notes)

- LH ring：pianoplayer 用 **2** 次 vs ArLSTM **14** 次（**+600%**）— Parncutt cost model atrophy 的直接證據
- RH pinky：pianoplayer 用 **66** 次 vs ArLSTM **26** 次（**-60%**）— pp pinky over-use
- RH ring：pianoplayer 用 19 次 vs ArLSTM 39 次（+105%）

### 3.4 Stage B render artifacts

- `results/canon_arlstm_kb.mp4` — 8.3 MB, 3:11, 1920×1080 H.264
- `results/canon_arlstm_fingertips.json` — 2.2 MB（給 webui comparator 用）
- `results/summer_arlstm_kb.mp4` — 13.9 MB, 2:32
- `results/canon_arlstm_vs_biomech.mp4` — 並排對比影片 (用於 defense demo)

---

## 4. 架構決策 (Key Architectural Decisions)

### 4.1 Dual-Track Decoupling（核心 contribution）

**Why**: Phase A 用 biomech v4 同時當示範器 + 判官，暴露兩個問題：
- generative 模型的 stochastic sampling 洩漏到判分（同一首歌每次跑「標準答案」不一樣）
- motion-derived 指法產生物理不可能解（觀察到 [1,1]、[2,2] 兩音同指）

**Solution**: 把 fingering decision (Logic Track) 與 hand rendering (Visual Track) 拆給兩個獨立 deterministic 來源。

### 4.2 ArLSTM 為 Logic Track default

**Why**: Corpus n=183 neutral subset 顯示 ArLSTM Soft 0.792 vs pianoplayer 0.578；ArLSTM 在 LH 接近完美 (0.975)，修正了 pianoplayer cost-model 的 LH ring atrophy。

**Caveat**: Bach RH scalar 段落 pianoplayer 反超——預示需要 style-aware 自動切換（future work）。

### 4.3 Rule-based GT + predictor-neutral subset

**Why**: 避免「單一 annotator 主觀偏差」與「LLM-GT self-favoring」。Rule 採用 piano-pedagogy 文獻可引用慣例 (interval rules + stepwise continuity)。23% rule-ambiguous 條目用 ArLSTM tiebreaker，但 `--exclude-tiebreakers` flag 產生 predictor-neutral subset 排除這部分，提供 self-favoring 防守證據。

### 4.4 Per-student rolling-median wrist baseline

**Why**: 不同 webcam 角度 / 學生手大小不同，絕對 pixel threshold 不能 transfer。改用學生自己最近 4 秒視窗的 wrist y 中位數當 baseline，arched/collapsed 偏差 ±25 px 觸發 warning。

### 4.5 OSMD position-indexed alignment

**Why**: music21 重 quantize MIDI 時時間戳跟 ArLSTM 的 seconds 對不上。用「第 N 個 score note of pitch P ↔ ArLSTM 第 N 個 (time, pitch=P) prediction」對齊，達 94.6% 覆蓋。

---

## 5. Known Limitations（誠實列）

### 5.1 評估面

- **GT 規模**：Canon 兩手 n=290 onset + Bach 兩手 n=200。共 2 首曲子。Reviewer 可挑「樣本太少」
- **單一 annotator**：rule-based GT 反映西方古典慣例，未做 multi-annotator agreement（PIG corpus 用 5-8 位 annotator）
- **rule timeline**：rule 是在實驗中迭代收斂的，不是事先 pre-registered。完全獨立的 GT 需要第三方 annotator

### 5.2 模型面

- **ArLSTM 視野有限**：±20 lookahead notes，無法考慮長 phrase
- **生成式 Visual Track 仍有隨機性**：biomech v4 生成的非按鍵 transitional motion 仍 stochastic
- **PIG-trained inductive bias**：學到的是西方古典指法，對 jazz/pop 可能不適用

### 5.3 系統面

- **Hardware live mode 未驗證**：所有 demo 採 replay 模式（用 biomech v4 影片當 fake student）
- **無正式 user study**：第六章設計基於 informal 內部測試
- **OSMD cursor sync 是 beat 估算**：精確 sync 需要 explicit tempo map
- **Finger curvature feedback 未做**：需要 3D landmarks (現在用 2D)

---

## 6. Reviewer Q&A 演練摘要

跟 Claude 練了兩題 defense simulation，整理出幾個防守原則：

### 6.1 通用模板（三段式）

對任何 critical 攻擊，按這順序答：
1. **承認 limitation 給對方台階**：「同意這是 limitation」
2. **拿具體數字防守**：引用 corpus number、commit hash、檔案位置
3. **反擊或 motivate future work**：把 limitation 轉成下一個 paper 的 motivation

### 6.2 已演練過的兩個攻擊角度

**Q1：GT 是否 self-favor ArLSTM？**
最佳答覆三層：
- 第一層：承認 rule 是迭代收斂，不是 pre-registered（limitation）
- 第二層：`--exclude-tiebreakers` 排除 23% arlstm-tiebreaker 條目後 ArLSTM 仍 Soft 0.741 vs pp 0.663 (+0.078)
- 第三層：Bach RH 上 pp 反超 (0.734 vs 0.406)——如果 rule 系統性偏 ArLSTM，Bach 也該 ArLSTM 贏

**Q2：cross-piece n=2 太少**
最佳答覆三層：
- 同意 n=2 是 limitation
- LH 跨曲一致：Canon 0.975 vs 0.275，Bach 0.878 vs 0.391（兩首都差 0.5+）
- 解釋機制：LH bass texture 一致，RH texture 多樣化所以 style-dependent；future 加 Mozart + Chopin 做完整 4 首矩陣

### 6.3 還沒練但 reviewer 必問的攻擊

- **「你只是 wget + import，沒做 ML」**：要列具體工程（架構決策 / MIDI 對齊 bug / 統一 ExpectedOnset shape / cross-piece evaluation methodology）
- **「沒有 real student data，RQ3 沒被回答」**：要 acknowledge gap + 提出 hardware mode 為下一步
- **「你的 Henle 引用為什麼沒對比 published Henle edition？」**：methodological hole，可以承認後 motivate 補做

---

## 7. Git Commit History (31 commits)

```
7e0e5e4  test     register pytest 'slow' marker (kill warning)
bd970a5  fix      render Mermaid sources to SVG (chapter refs)
1262ffe  docs     STATUS_SUMMARY for advisor handoff
9f4a223  test     13 wrist_status unit tests
3adc8b7  feat     Stage D wrist height feedback v1
8f126a6  docs     ch6/ch7 reflect OSMD shipped
37a0838  feat     Stage D OSMD sheet music + ArLSTM annotations
748b355  test     audit integration tests + setup.sh
fddb3dd  docs     thesis front-matter (abstract zh/en, ack, lists)
f667054  docs     Bach finger distribution figures
0ed37f5  docs     Bach finding integration into thesis
0c42ed4  feat     Bach Invention cross-piece audit + pp wins Bach RH
d944e41  docs     frozen audit_results.json + demo_defense.sh
579408f  docs     Mermaid architecture diagrams
95b50f7  docs     finger distribution matplotlib + ch4 embed
c154ae3  test     pytest suite 50/50 green
9deded8  docs     manual override sample + regenerate script
0b495e9  docs     THESIS.md + Makefile
c4bb39b  docs     defense slides + Q&A + BibTeX
4cb2c84  docs     ch5/6/7 thesis drafts
ef7e561  docs     ch1/ch2 thesis drafts
d2024c3  docs     ch3 architecture chapter
fbf6cce  docs     ch4 evaluation chapter
d1a1955  docs     NotebookLM audit notes update
2a45a59  feat     LH corpus GT + Summer pipeline
4a15909  feat     Stage C PracticeScreen ArLSTM wire
70e83c6  feat     Stage B ArLSTM render integration
2e91953  feat     rule-based corpus GT + four-way audit
f7ebf8a  feat     ArLSTM as default Logic Track
```

---

## 8. Next Steps (User-only action)

1. **Push 到 fork**（auth blocker；需在普通 terminal 跑或裝 gh CLI）
2. **跟教授 review** ch1-4 核心 4 章
3. **錄 demo 影片**：開 webui + screen capture
4. **練 defense**：用 `defense_slides.md` + `defense_qa.md`
5. **Stage D 補完項**（可選）：Hardware live mode、tempo-precise OSMD cursor、Mozart/Chopin 第 4-5 首 cross-piece
6. **學校 thesis 格式調整**：套校方 LaTeX template / Word template

---

## 9. References

- **Nakamura, E. et al. (2014)**. Statistical Learning and Estimation of Piano Fingering. ISMIR.
- **Parncutt, R. et al. (1997)**. An Ergonomic Model of Keyboard Fingering for Melodic Fragments. Music Perception.
- **Ramoneda, P. et al. (2022)**. Automatic Piano Fingering from Partially Annotated Scores using Autoregressive Neural Networks. ACM MM.
- **Liu et al. (2024)**. PianoMotion10M. ICLR 2025 Spotlight.
- **Romero et al. (2017)**. MANO hand model. SIGGRAPH Asia.
- **ThumbSet dataset** (Ramoneda et al. 2022). Zenodo DOI 10.5281/zenodo.6433702.
- **MediaPipe Hands** v0.10.14 (pin for EGL compat on Ubuntu 22.04).
- **OpenSheetMusicDisplay** v1.8.7 (jsDelivr CDN).

---

**完。** 把這份檔上傳到 NotebookLM 就有整個 session 的 context。
