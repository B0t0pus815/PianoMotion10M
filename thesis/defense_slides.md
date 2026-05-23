---
marp: true
theme: default
size: 16:9
paginate: true
header: 'AI 鋼琴學習 — Dual-Track Decoupling 與 ArLSTM 整合'
footer: 'Desmond Tee · 畢業專題 defense · 2026'
style: |
  section { font-family: 'Helvetica Neue', sans-serif; }
  h1 { font-size: 1.6em; color: #1a4d8f; }
  h2 { color: #1a4d8f; border-bottom: 2px solid #1a4d8f; padding-bottom: 0.2em; }
  .lead h1 { font-size: 2.4em; }
  .lead { padding-top: 12%; }
  table { font-size: 0.85em; margin: 0 auto; }
  .small { font-size: 0.75em; }
  .winner { color: #1a8f4d; font-weight: bold; }
  .loser { color: #9f1f1f; }
---

<!-- _class: lead -->

# AI 鋼琴學習：Dual-Track 架構與 SOTA 指法整合

**Desmond Tee** · 畢業專題
基於 PianoMotion10M (Liu 2024) 與 Ramoneda 2022 ArLSTM

---

## 一頁總結

**問題**：能否用 AI 教學生彈鋼琴的**正確指法**？

**現狀**：手勢生成 SOTA (PianoMotion10M) 與指法決策 SOTA (Ramoneda 2022) **各自存在但沒整合**——學生看到的影片不保證指法正確、知道正確指法的模型沒有視覺示範。

**本論文**：把兩者透過 **Dual-Track Decoupling** 架構整合成可教學閉環，並用 corpus-level (n=183) 量化驗證整合決策合理。

**Headline 數字**：ArLSTM Soft Accuracy **0.792** vs pianoplayer 0.578 (-27%) vs motion-derived 0.358 (-55%)，n=183 predictor-neutral subset。

---

## 三個研究問題

**RQ1（架構）**：能否讓「正確示範」與「判分」基於同一個指法決策來源？

**RQ2（選擇）**：哪個指法決策模型適合擔任判官？

**RQ3（教學閉環）**：能否做成學生實際可用的工具？

---

## Phase A 暴露的問題

Phase A 用 biomech v4 同時做示範器 + 判官。實作後發現：

**問題一**：generative 模型 stochastic sampling 洩漏到判分
→ 同一首歌在不同 inference 跑出來的 "標準答案" 不一樣

**問題二**：motion-derived 指法包含 anatomical 不可能解
→ 觀察到 [1,1] (兩音同指) 等物理錯誤

**結論**：generative 模型**不適合**當判官。

---

## 解法：Dual-Track Decoupling

![bg right:40% 80%](https://via.placeholder.com/600x450?text=Dual-Track+Diagram)

把兩個職責拆給兩個 deterministic 來源：

- **Logic Track (judge)**：指法決策器
  - 採用 Ramoneda 2022 ArLSTM
- **Visual Track (renderer)**：手部姿態生成
  - 保留 biomech v4，剝奪判官權

兩個 track 各自輸出 deterministic 結果，整合後變成「指法正確的視覺示範」。

---

## Stage A：Logic Track 整合

**選擇問題**：四個候選——pianoplayer / motion / ArLSTM / ArGNN，哪個適合？

**整合方式**：
1. Vendoring Ramoneda 2022 開源 repo (`external/Automatic-Piano-Fingering/`)
2. 包裝 thin wrapper `ramoneda_predict.py`
3. 在 `fingering_engine.py` 統一介面 `generate_fingering(source='arlstm')`

下游 comparator / clip_recorder / broadcaster **一行 code 不用改**（ExpectedOnset shape 一致）。

---

## Stage B：渲染 Pipeline 整合

**問題**：Stage A 升級判官，但學生看到的影片仍由 biomech v4 自己選指法——**判官跟示範不一致**。

**解法**：把 ArLSTM 指法注入到 biomech v4 渲染流程。

```bash
python simple_natural.py --fingering arlstm \
    --midi Canon.mid --mp3 Canon.mp3 \
    --out_video results/canon_arlstm_kb.mp4
```

`apply_arlstm_fingering()` 是 `apply_biomech_fingering()` 的 drop-in replacement，shape 完全一致，6+ note chord fallback 到 biomech。

---

## Stage C：UI 接軌

把 Stage B 輸出 (`canon_arlstm_kb.mp4`) 接到 React PracticeScreen 學生實際看到的影片：

- `webui/songs.json`：videoUrl 指向 ArLSTM render
- `PracticeScreen.js`：fallback path、brand label `AI · ArLSTM × biomech v4`

端到端 smoke test：

```
[ref] 344 expected onsets — Logic Track (Ramoneda ArLSTM)
```

---

## 評估方法：Rule-based Corpus GT

**GT 自動生成**（避免 LLM-GT 自我循環）：

| 規則 | 觸發 | 輸出 |
|---|---|---|
| Interval rules | m3/M3/P4/P5+ chord | [1,3] / [1,4] / [1,5] |
| Stepwise | ±1/2 半音單音 | 前一指 ± 1 |
| Predictor consensus | pp == arlstm | 共識值 |
| Rule-ambiguous | else | ArLSTM tiebreaker |

每條 GT 附 `decision` 欄位記錄來源，`--exclude-tiebreakers` flag 產生 **predictor-neutral subset** 防止 self-favoring。

---

## 評估指標

**Hard Accuracy**：list 完全一致才 1.0

$$\text{Hard}(g, p) = \mathbb{1}[g = p]$$

**Soft Accuracy**：±1 finger 算 0.5，更貼近鋼琴指法的 inherent flexibility

$$s(g_i, p_i) = \begin{cases} 1.0 & |g_i - p_i| = 0 \\ 0.5 & |g_i - p_i| = 1 \\ 0.0 & \text{else} \end{cases}$$

兩者並列才完整刻畫 candidate 表現。

---

## 結果：RH (n=143 neutral subset)

| Track | Hard | Soft |
|---|---|---|
| **ArLSTM** | **0.587** | **0.741** |
| ArGNN | 0.336 | 0.572 |
| pianoplayer | 0.510 | 0.663 |
| motion_v4 | 0.252 | 0.411 |

ArLSTM 在 Soft 領先 pianoplayer 約 8 pp，領先 motion 約 33 pp。

---

## 結果：LH (n=40 neutral subset)

| Track | Hard | Soft |
|---|---|---|
| **ArLSTM** | **0.975** | **0.975** |
| ArGNN | 0.850 | 0.919 |
| pianoplayer | 0.225 | <span class="loser">0.275</span> |
| motion_v4 | 0.000 | 0.175 |

**LH 上 pianoplayer 0.275 ≈ systematic failure**——不是「弱於 ArLSTM」是「near-random」。

原因：Parncutt cost model 把 LH ring 設定為 expensive，造成「ring 棄用、pinky 濫用」結構性 bias。

---

## 結果：RH + LH 合併 (n=183)

| Track | Soft | 相對 ArLSTM |
|---|---|---|
| **ArLSTM** | **0.792** | — |
| ArGNN | 0.654 | -17% |
| pianoplayer | 0.578 | <span class="loser">-27%</span> |
| motion_v4 | 0.358 | <span class="loser">-55%</span> |

**對 thesis defense 主要的數字**——ArLSTM corpus-level Soft 0.792 顯著優於所有 baseline。

---

## Finger Distribution 分布證據

整曲 Canon **左手 (107 notes)** 指法分布：

| Finger | pianoplayer | ArLSTM | Δ |
|---|---|---|---|
| ring (4) | <span class="loser">2</span> | <span class="winner">14</span> | **+600%** |
| pinky (5) | 17 | 16 | -6% |

pianoplayer 在 LH 只用 ring 2 次——這是 cost model 的 **直接 visible failure mode**。ArLSTM 從 PIG 真實鋼琴家標註學到平衡分布。

---

## Cross-piece Validation：Summer + Bach

**Summer** (Joe Hisaishi, J-pop)：pipeline 端到端通過，無 GT 數字（pipeline test only）

**Bach Invention No.1 BWV 772** (Public Domain Mutopia)，n=200 neutral subset：

| Track | Bach RH | Bach LH |
|---|---|---|
| **pianoplayer** | **Soft 0.734** | Soft 0.391 |
| **ArLSTM** | Soft 0.406 | **Soft 0.878** |
| ArGNN | Soft 0.402 | Soft 0.859 |

**ArLSTM 不是 universal winner** — Bach RH 連續 16 分音符 scalar 段落 pianoplayer 反超。LH 維持 ArLSTM 大幅領先。

→ **Logic Track 的 `--fingering-source` runtime switch 設計剛好涵蓋這個 cross-style 需求。**

---

## Live Demo

**(切到 webui 實際操作)**

`python webui/serve.py 8765` → 瀏覽器開 PracticeScreen

可展示：
- ArLSTM 渲染影片在 hero video
- PianoRoll 同步落鍵
- ScoreRing 即時準確率
- 故意彈錯指法 → FeedbackOverlay 即時 flash
- 累積錯誤 → ClipsStrip 自動生成並排對比影片

---

## 主要貢獻

1. **Dual-Track Decoupling 架構**——拆 fingering decision 與 hand rendering，避免 generative 模型隨機性洩漏判分
2. **整合 Ramoneda 2022 SOTA 為 default Logic Track**——把 paper-stage model 變成 production-usable judge
3. **Rule-based corpus GT framework**——77% 條目可文獻引用，predictor-neutral subset 防止自我循環
4. **Stage A→B→C 完整 pipeline**——兩首風格不同的曲子端到端驗證
5. **量化 cost-model failure modes**——pianoplayer LH ring atrophy 直接可視化

---

## 限制 (Limitations)

- **GT 規模**：只在 Canon (n=290 onset) 做完整 GT
- **單一 annotator**：rule-based GT 反映西方古典慣例，不是 multi-annotator consensus
- **ArLSTM 視野**：±20 lookahead notes，無法考慮長 phrase
- **Hardware live mode 未驗證**：所有 demo 採 replay 模式
- **UI 未經正式 user study**

---

## 未來工作

**短期 (1-3 個月)**：
- OSMD 即時樂譜 + 指法標註
- Bach Invention polyphonic cross-piece (ArGNN 有機會反超 ArLSTM)
- Hardware live mode 部署

**中期 (3-6 個月)**：
- PIG 官方 test split 申請 + benchmark
- Multi-annotator GT (3-5 位 ABRSM 8 級鋼琴老師)
- Long-horizon Transformer encoder 取代 LSTM

**長期 (6+ 個月)**：
- PianoMotion10M conditioned retrain (fingering token as input)
- 個人化適配 (手大小、學生 history)
- 多樂器拓展 (吉他、小提琴)

---

## 預期 Q&A

**Q**：你的 GT 由 LLM 規則生成不會自我循環嗎？
**A**：predictor-neutral subset 已排除所有 arlstm-tiebreaker 條目；剩下 77% 是文獻可引用的 piano-pedagogy rules + predictor consensus。

**Q**：只測 Canon 一首太少？
**A**：實測三首 (Canon, Summer, Bach Invention)。Bach 揭示 ArLSTM 不是 universal winner，這恰好驗證 audit framework 對 cross-style 差異敏感。

**Q**：Bach 上 pianoplayer 贏了，這不打臉嗎？
**A**：相反——增強了 Logic Track 該保留 `--fingering-source` runtime switch 的設計決策，並 motivate 後續 style-aware 自動切換 (ch7 7.4.1)。

**Q**：跟單純跑 Ramoneda 2022 有什麼差別？
**A**：本論文證明 Ramoneda 的指法決策**值得**接進視覺示範系統（Stage A 量化驗證），且**有辦法**接（Stage B/C 工程整合）。把 benchmark model 變 teaching tool。

---

<!-- _class: lead -->

# 謝謝指導

Q&A 時間

**Resources**:
- Code: github.com/Desmond/PianoMotion10M
- Thesis chapters: `thesis/ch{1..7}.md`
- Demo videos: `results/canon_arlstm_kb.mp4`, `results/summer_arlstm_kb.mp4`
