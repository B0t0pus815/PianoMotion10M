# Dual-Track Fingering Audit & ArLSTM Integration
**Date:** 2026-05-21
**Project:** AI 鋼琴學習 (AI Piano Learning) — graduation thesis built on PianoMotion10M
**Phase:** B (real-time 教學閉環) → Logic Track 升級

---

## 摘要 (Executive Summary)

今天為 thesis 的 Logic Track（指法判官）做了一次正式的四方 cross-audit，並把 **Ramoneda 2022 ArLSTM** 升格為 default 指法來源，取代原本的 pianoplayer DP。

**核心發現**：在 Canon RH 的 Teacher's Answer-Key benchmark 上，ArLSTM 取得 **Soft Accuracy 0.792**，比 pianoplayer 的 0.625 高出 27%、比 motion-based 的 0.375 高出 111%。ArLSTM 同時修正了 pianoplayer 的 ring-finger atrophy（LH ring 用量 2 → 14，RH ring 19 → 39）。

**結論**：Logic Track 的 default judge 改為 ArLSTM，pianoplayer 降為 baseline alternative。架構不變（Dual-Track Decoupling 維持），但 judgment quality 從「cost model 的局部最優」升級到「神經模型學到的人類偏好」。

---

## 背景：Dual-Track Decoupling 架構

在 2026-05-19 的架構 pivot 之前，系統用 biomech v4 的動作軌跡同時作為「視覺示範」和「指法判官」。但 motion-derived 指法跟 deterministic baseline（pianoplayer）在整首 Canon 上只有 24.4% agreement，且 motion-based 有 47 個 pinky→thumb confusion 案例，根本不能當 judge。

於是 architecture 拆成兩條獨立 track：

- **Logic Track (judge)**：deterministic fingering，負責判斷學生彈得對不對。原本是 pianoplayer DP。
- **Visual Track (renderer)**：biomech v4 影片，純粹當示範。被剝奪 judgment 權限。

今天的工作是進一步驗證 Logic Track 本身是否夠好——也就是 pianoplayer 是不是真的能 represent「老師的標準答案」。

---

## 評估框架設計

### Ground-Truth JSON Schema

為了能量化「fingering 對不對」，我設計了一份 GT JSON 格式（`eval_data/canon_rh_gt.json`）：

```json
{
  "song": "Canon in D (Pachelbel, EASY tutorial) — RH first 12 onsets",
  "hand": "right",
  "fingering_convention": "1=thumb, 2=index, 3=middle, 4=ring, 5=pinky",
  "ground_truth": [
    {"onset_index": 0, "onset_time": 27.865, "midi_notes": [78], "fingering": [5]},
    {"onset_index": 1, "onset_time": 29.633, "midi_notes": [76], "fingering": [4]},
    ...
    {"onset_index": 8, "onset_time": 41.985, "midi_notes": [74, 78], "fingering": [1, 5]}
  ]
}
```

**規則**：
- 一個 onset 一個 entry，`midi_notes` 升冪排序，`fingering[i]` 對應 `midi_notes[i]`
- 一隻手一個檔案（左右手獨立評估，避免歧義）
- `onset_time` 為對齊用 metadata，不影響評分

### 評分函式

`evaluate_template.py` 提供兩個 metric：

- **Hard Accuracy**: list 完全一致才 1.0，否則 0.0。對單音 onset 等價於「finger 完全對」。
- **Soft Accuracy**: 逐 finger 評分後取平均
  - 差 0 → 1.0（完全對）
  - 差 1 → 0.5（valid alternative，例如 GT 是 3 但預測 2 或 4）
  - 其他 → 0.0
  - 長度不一致：缺位算 0、多按算進分母

Soft 設計的依據：鋼琴指法本來就有 inherent flexibility，差一隻指頭通常不算「錯」，只是次優。Hard 抓「絕對對」，Soft 抓「方向感對」，兩者一起看才有意義。

---

## 實驗：Cross-Audit 設計

### 資料

- **MIDI**: `input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid`
- **GT**: 手寫 12 個 onset 的右手 teacher's answer-key
  - 開頭 8 個單音下行：F#5→E5→D5→C#5→B4→A4→B4→C#5 → 指法 5,4,3,2,1,3,2,3
  - 後 4 個雙音和弦：[D5,F#5], [C#5,E5], [B4,D5], [A4,C#5] → 指法 [1,5], [1,4], [1,3], [1,4]
- **指法選擇依據**：descending 5-4-3-2-1 thumb anchor 是 Henle / Schirmer 標準；雙音用 1+5 / 1+4 / 1+3 是 octave / sixth / fifth 對應的教科書配指

### 四個被評估的 track

1. **pianoplayer (Logic baseline)**：Parncutt 1997 cost model + DP 最優解
2. **motion_v4 (Visual fallback)**：biomech v4 影片的 fingertip 軌跡 + downward-velocity 啟發式判斷
3. **ArLSTM** (Ramoneda 2022)：3-layer BiLSTM + AR LSTM decoder，PIG-finetuned
4. **ArGNN** (Ramoneda 2022)：3-layer Gated GNN + AR LSTM decoder，PIG-finetuned

ArLSTM / ArGNN 的 checkpoint 來自 `external/Automatic-Piano-Fingering/models/` (MIT)。完全沒有重新訓練，純 inference。

### 評估腳本

`four_way_audit.py` 把四個 track 的輸出 bucket 到相同 onset_index，餵進 `evaluate_template.evaluate()`，產生統一報表。

---

## 結果

### 四方 Accuracy 表

| Track | Hard | Soft | 角色判定 |
|---|---|---|---|
| pianoplayer | 0.500 | 0.625 | 原 default，被超越 |
| motion_v4 | 0.083 | 0.375 | 不適任 judge，已剝奪 |
| **ArLSTM** | **0.500** | **0.792** | **新 default** |
| ArGNN | 0.333 | 0.500 | monophonic 場景不利 |

### 逐 onset 對比（重點）

| idx | pitches | GT | pianoplayer | motion_v4 | ArLSTM | ArGNN |
|---|---|---|---|---|---|---|
| 0 | [78] | [5] | [5] ✓ | [1] ✗ | [5] ✓ | [3] |
| 4 | [71] B4 (thumb anchor) | **[1]** | [5] ✗ | [2] | **[1] ✓** | [2] |
| 6 | [71] | [2] | [5] ✗ | [1] | [1] | [2] ✓ |
| 8 | [74,78] | [1,5] | [1,5] ✓ | [1,1] ✗ | [3,5] | [1,5] ✓ |
| 11 | [69,73] | [1,4] | [3,2] | [2,2] ✗ | [2,4] | [1,4] ✓ |

**關鍵觀察**：
- pianoplayer 在第 4 個 onset 重複用 pinky (5) 跳到較低音 B4——這是 Parncutt cost model 的 thumb-conservative bias，物理上動作不流暢
- ArLSTM 在第 4 個 onset 正確選 thumb (1)——它**從 PIG 真實 pianist annotation 學到**這個 thumb anchor 模式
- motion_v4 整列幾乎全錯，並出現 [1,1]、[2,2] 兩音同指的物理錯誤——再次驗證它不能當 judge
- ArGNN 在 polyphonic onset (8, 11) 表現好，但 monophonic 下行被自身結構干擾

### Finger Distribution 全曲分析

整首 Canon (344 notes) 的指法分布：

**左手 (107 notes)**：
| Finger | pianoplayer | ArLSTM | 變化 |
|---|---|---|---|
| thumb | 43 | 20 | -53% |
| index | 23 | 28 | +22% |
| middle | 22 | 29 | +32% |
| ring | **2** | **14** | **+600%** |
| pinky | 17 | 16 | -6% |

**右手 (237 notes)**：
| Finger | pianoplayer | ArLSTM |
|---|---|---|
| thumb | 46 | 61 |
| index | 57 | 57 |
| middle | 49 | 54 |
| ring | **19** | **39** (2×) |
| pinky | **66** | **26** (-60%) |

pianoplayer 左手只用 ring 2 次——這就是 Parncutt cost model 把 ring 設定為 "expensive finger" 的副作用。ArLSTM 把 ring 用回應有的次數（左手 14、右手 39），pinky 從濫用 (66) 降到合理 (26)。

**為什麼這個分布更 pedagogically 對**：

人類鋼琴老師教學的時候，會儘量讓 5 根手指均勻負擔。pianoplayer 因為 cost model 設定，會把困難的位置塞給 pinky（因為它本來就被定義為 "weak"，被使用的"懲罰"已經很高，cost model 反正都會懲罰它），導致 pinky 過度使用、ring 棄用。ArLSTM 從 PIG 學到「人類偏好把 ring 當主力 weak finger，pinky 只在真的需要的時候用」，更接近老師會教的方式。

---

## 架構決策：ArLSTM 升為 Default

### 改動

- **`webui/realtime/fingering_engine.py`**：
  - `generate_fingering(midi_path, source='arlstm', ...)` — default 從 `pianoplayer` 改成 `arlstm`
  - Dispatch 函式 `_generate_pianoplayer()` / `_generate_arlstm()`
  - 共用 `_pack_with_override()` 套用人工 fingering JSON override

- **`webui/realtime/runner.py`**：
  - `--fingering-source` choices 加入 `arlstm`
  - Default 從 `pianoplayer` 改成 `arlstm`
  - help text 更新

- **`ramoneda_predict.py`** (new)：
  - `predict(midi_path, hand, kind='ArLSTM'|'ArGNN')` 包 Ramoneda 模型
  - Lazy-import 從 `external/Automatic-Piano-Fingering/`
  - 處理 ArLSTM (only_pitch + LSTM) 與 ArGNN (emb_pitch + GNN) 的不同架構

### Demo command 對使用者透明

```bash
python -m webui.realtime.runner \
    --video results/canon_biomech_v4_kb.mp4 \
    --midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    --reference results/canon_biomech_v4_fingertips.json \
    --fast --no-preview --ws-port 8766 --ws-linger 3600 \
    --clip-record
```

不寫 `--fingering-source` 就走 ArLSTM。要回退到 pianoplayer 加 `--fingering-source pianoplayer`，要做對比實驗很方便。

下游的 comparator / clip_recorder / broadcaster / React PracticeScreen **一行 code 都不用改**，因為 ExpectedOnset shape 統一。

---

## 對 Thesis Defense 的意義

### Story Arc

完整的 thesis Logic Track 章節敘事：

1. **問題定義**：motion-derived fingering 從 PianoMotion10M v4 萃取出來判分，但跟 deterministic baseline 在 Canon 上只 24.4% agreement，且 47 case thumb-bias。
2. **架構 pivot (2026-05-19)**：Dual-Track Decoupling，把 judgment 跟 rendering 拆開。判分用 deterministic 來源，避免 generative 模型的隨機性洩漏到判分。
3. **Cost Model baseline (pianoplayer)**：Parncutt 1997 + DP 是合理 starting point，但 thumb-conservative + ring-atrophy bias 明顯。
4. **SOTA upgrade (ArLSTM)**：Ramoneda 2022 神經模型 outperform cost model，且 finger distribution 更 pedagogically aligned。
5. **驗證 (today's audit)**：在 teacher's answer-key benchmark 上 ArLSTM Soft 0.792 > pianoplayer 0.625 > motion 0.375。

### 防守 (Reviewer 質疑預期)

**Q: 你用的 fingering model 是 SOTA 嗎？**
A: ArLSTM 是 Ramoneda et al. 2022 paper 的方法，在 PIG corpus 上 beat 之前的 HMM/RNN baseline。我直接用他們的 pretrained checkpoint，方法級別跟 SOTA 同步。

**Q: 你的 evaluation 怎麼防守？**
A: 三層 metric：
- pianoplayer derivative metric（automatic, large-scale）
- teacher's-answer-key Hard/Soft accuracy（manual, small-scale, 客觀）
- finger distribution analysis（quantitative, 全曲）

**Q: 為什麼不從零訓練？**
A: PIG corpus 的 official access 是 upon-request，且 thesis 的核心 contribution 不是改進 fingering model 本身（那是 Ramoneda 2022 的事），而是把 SOTA fingering 跟 PianoMotion10M motion generation 整合成教學系統。inference-only 路線 maximize the contribution-to-effort ratio。

**Q: 12 個 onset 太少了吧？**
A: 同意這是 limitation。但 finger distribution 是全曲 344 notes 的 evidence，足以說明 distribution-level claim。下一步是擴 GT 到全曲，做 corpus-level Hard/Soft。

---

## Code Artifacts

| File | Role |
|---|---|
| `evaluate_template.py` | GT 格式 + Hard/Soft 評分 API |
| `eval_data/canon_rh_gt.json` | Canon RH 前 12 onset teacher's answer-key |
| `evaluate_canon.py` | 單一 track 評估 runner |
| `cross_audit_canon.py` | Logic vs Visual 兩方 audit (前一版) |
| `four_way_audit.py` | pianoplayer / motion / ArLSTM / ArGNN 四方比較 |
| `ramoneda_predict.py` | Ramoneda 模型 inference wrapper |
| `webui/realtime/fingering_engine.py` | Logic Track 統一入口 (refactored) |
| `webui/realtime/runner.py` | Phase B CLI (default 切到 arlstm) |
| `external/Automatic-Piano-Fingering/` | 第三方 repo (MIT)，提供 .pth checkpoints |

Git commit: `f7ebf8a` (feat: ArLSTM as default Logic Track + fingering audit framework)

---

## Limitations & Next Steps

**Limitations**:
1. GT 只有 12 個 onset，corpus-level conclusion 還不夠強
2. 只測 RH，LH 沒做（雖然 finger distribution 證據暗示 LH 改善更明顯）
3. ArLSTM 沒考慮樂句、踏板、後續樂段——它只看 ±20 lookahead notes
4. PIG corpus 的 official 版本沒拿到（用 lumikey 預處理版本驗證；正式 thesis 不依賴它）

**Next Steps (按優先序)**:
1. 擴 GT 到 Canon RH 全 237 onset（人工約 30 分鐘）跑 corpus-level 數字
2. 加 LH GT，驗證 finger distribution 觀察
3. 把 Stage B 接起來：用 ArLSTM 的 fingering 當 conditioning 餵進 PianoMotion10M motion generator，讓 v4 的視覺軌跡跟 prescribed fingering 對齊
4. （若時間允許）試 ArGNN 在 Bach Invention 這類 polyphonic 曲目，看是否反超 ArLSTM

---

## References

- **Nakamura, E., et al. (2014)**. *Merged-Output HMM for Piano Fingering of Both Hands.* ISMIR.
- **Parncutt, R., et al. (1997)**. *An Ergonomic Model of Keyboard Fingering for Melodic Fragments.* Music Perception.
- **Ramoneda, P., Jeong, D., Nakamura, E., Serra, X., Miron, M. (2022)**. *Automatic Piano Fingering from Partially Annotated Scores using Autoregressive Neural Networks.* ACM Multimedia. ([repo](https://github.com/PRamoneda/Automatic-Piano-Fingering))
- **Liu, et al. (2024)**. *PianoMotion10M.* [project page](https://agnjason.github.io/PianoMotion-page)
- **ThumbSet dataset** (Ramoneda et al. 2022). Zenodo DOI 10.5281/zenodo.6433702.
