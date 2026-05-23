# 圖目錄 / 表目錄 (Lists of Figures and Tables)

## 圖目錄 (List of Figures)

| 編號 | 標題 | 章節 | 來源檔 |
|---|---|---|---|
| 圖 3.1 | Dual-Track Decoupling 架構 | 3.2 | `figures/dual_track_architecture.svg` |
| 圖 3.2 | Stage A → B → C 整體 pipeline 資料流 | 3.6 | `figures/stage_pipeline.svg` |
| 圖 4.0 | 評估方法 overview | 4.1 | `figures/eval_methodology.svg` |
| 圖 4.1 | Canon in D 全曲指法分布對比 (pianoplayer vs ArLSTM) | 4.5 | `figures/finger_dist_combined.png` |
| 圖 4.2 | Bach Invention No.1 全曲指法分布對比 | 4.6.2 | `figures/bach/finger_dist_combined.png` |

## 表目錄 (List of Tables)

| 編號 | 標題 | 章節 |
|---|---|---|
| 表 4.1 | Right Hand 評估結果 — Canon RH (n=186/143) | 4.4.1 |
| 表 4.2 | Left Hand 評估結果 — Canon LH (n=90/40) | 4.4.2 |
| 表 4.3 | RH + LH 合併 neutral subset 結果 (n=183) | 4.4.3 |
| 表 4.4 | 左手 finger distribution 對比 (107 notes) | 4.5 |
| 表 4.5 | 右手 finger distribution 對比 (237 notes) | 4.5 |
| 表 4.6 | 失敗模式案例 — 前 12 onset 對比 | 4.7 |
| 表 4.7 | Bach RH 評估結果 (n=181/122) | 4.6.2 |
| 表 4.8 | Bach LH 評估結果 (n=124/78) | 4.6.2 |
| 表 5.1 | (Stage 各檔案責任 — text-only) | 5 |
| 表 7.1 | 三個 RQ 的 corpus-level 證據摘要 | 7.1 |
| 表 7.2 | Contributions × 章節 × 量化證據對照 | 7.2 |

## 參考文獻數量

12 BibTeX entries (見 `thesis/references.bib`)：

- Parncutt et al. 1997 — cost model baseline
- Nakamura et al. 2014 — PIG corpus
- Ramoneda et al. 2022 — ArLSTM/ArGNN SOTA
- Liu et al. 2024 — PianoMotion10M base
- Romero et al. 2017 — MANO hand model
- Zakka et al. 2023 — RoboPianist
- Ramoneda et al. 2022 — ThumbSet (Zenodo DOI)
- Mauch & Dixon 2014 — pYIN pitch tracker
- Kim et al. 2018 — CREPE pitch tracker
- Google — MediaPipe Hands
- Hart et al. 2000 — early HMM fingering
- At Your Fingertips — ICLR 2024 视覺指法擷取
- pianoplayer — Parncutt cost model 開源實作

## 程式碼工件 (Reproducibility Index)

詳細工件對照表見 `thesis/ch5_implementation.md` §5.6 及 `THESIS.md` 主目錄。一行重現本論文 corpus 數字：

```bash
bin/regenerate_all.sh
```
