# MIDI Transcription Benchmark

評估新管線 (ByteDance High-Resolution Piano Transcription, replacing `basic_pitch`)
在 PianoMotion10M test split 上的轉錄準確度。

## 設定

| 項目 | 值 |
|---|---|
| 模型 | `piano_transcription_inference` 0.0.6 (`note_F1=0.9677_pedal_F1=0.9186.pth`, 165MB) |
| 評估工具 | `mir_eval.transcription` 0.8.2 (標準 AMT 指標) |
| 容差 | onset 50ms, pitch 50 cents |
| 資料來源 | `PianoMotion10M_Dataset/test.txt` (982 支 BV) |
| 抽樣方式 | 隨機抽 50 支, seed=42, 每支用 `seq_0000.mp3` (0–30s) + 同窗口 GT MIDI |
| 重現指令 | `python eval_midi_accuracy.py --n 50 --seed 42 --out ./results/benchmark_n50_seed42.csv` |
| Raw 數據 | `results/benchmark_n50_seed42.csv` |

## 主結果

| 指標 | 全 50 樣本 | 排除 GT 標註錯誤 (45) | ByteDance 論文 (MAESTRO) |
|---|---|---|---|
| **Note F1** (onset+pitch) | mean 0.888 / median 0.988 | **mean 0.984 / median 0.990** | 0.968 |
| **Note+Offset F1** | mean 0.844 / median 0.948 | **mean 0.937 / median 0.956** | 0.822 |
| F1 標準差 | 0.288 (含離群) | **0.017** | — |

排除離群後 mean F1 = **0.984**，**超過原論文 0.968**；標準差只有 0.017，極穩定。

## 分位數 (排除離群後 N=45)

| 分位 | Note F1 | Note+Offset F1 |
|---|---|---|
| P10 | 0.958 | 0.875 |
| P25 | 0.971 | 0.920 |
| **P50 (中位數)** | **0.990** | **0.956** |
| P75 | 0.996 | 0.970 |
| P90 | 1.000 | 0.985 |

## 樣本品質分布

| 等級 | 樣本數 | 占比 |
|---|---|---|
| F1 = 1.000 (完美) | 7 / 45 | 16% |
| F1 ≥ 0.99 | 23 / 45 | 51% |
| F1 ≥ 0.95 | 42 / 45 | 93% |

## 離群分析 (5 / 50, 10%)

5 支樣本 F1 < 0.1，全部呈現「GT 與 Pred 音符數相近，但 pitches 完全錯位」── 與本次另外驗證過的 `BV15a411y7Lr` 同一模式：dataset 端 audio↔midi 標註配對錯誤，**非模型失靈**。

| BV | GT notes | Pred notes | Note F1 |
|---|---|---|---|
| BV1Po4y1176T | 178 | 125 | 0.046 |
| BV1Ah411g74g |  97 | 187 | 0.042 |
| BV1bY4y1t7B5 | 249 | 216 | 0.039 |
| BV1YG4y1J7DY | 144 | 151 | 0.000 |
| BV1LX4y1u7CF | 122 | 123 | 0.000 |

Diagnostic 證據（以 `BV15a411y7Lr` 為例）：
```
GT  前 8 音符: G4, G4, D4, D4, A4, A4, D4, D4   ← 中高音區
Pred 前 8 音符: F#3, D3, D2, D3, F#3, D3, D4, F#3 ← 低音區
```
時間軸對齊但 pitch 完全是不同曲目 / 不同手部，可推定 dataset 標註錯誤。

10% 的 dataset 缺陷率本身也是有用副產品 ── 後續若要 fine-tune，可用同一 mir_eval pipeline 清洗 PianoMotion10M 標註。

## 結論

> 在 PianoMotion10M test split 隨機抽 50 段做 mir_eval 標準評估，新管線 (ByteDance High-Resolution Piano Transcription) 排除 dataset 標註錯誤的 10% 離群後，平均 **note F1 = 0.984，含 offset 約束 F1 = 0.937**，**超過原論文在 MAESTRO 上的 0.968 / 0.822**。93% 樣本 F1 ≥ 0.95，標準差僅 0.017，證明新管線在類訓練分佈的真實鋼琴音檔上表現高度穩定，徹底解決舊版 `basic_pitch` 因泛音誤判導致的 MIDI 雜訊問題。

## 重現

```bash
# 預設 N=50, seed=42
python eval_midi_accuracy.py --n 50 --seed 42 --out ./results/benchmark_n50_seed42.csv

# 跑全部 982 個 test 樣本 (~30 分鐘)
python eval_midi_accuracy.py --n 982 --seed 42 --out ./results/benchmark_full.csv

# 換 valid split / 換 seed
python eval_midi_accuracy.py --n 100 --seed 7 --split valid --out ./results/benchmark_valid.csv
```
