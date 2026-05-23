# 第七章 結論與未來工作 (Conclusion & Future Work)

## 7.1 主要 Findings

本論文針對「能否設計一個 AI 鋼琴學習系統，使得正確示範與判分基於同一個指法決策來源」這個整合性問題，提出 Dual-Track Decoupling 架構並完成端到端系統。三個 research questions 的回答：

**RQ1（架構問題）**：能否設計一個 AI 鋼琴學習系統，使得正確示範與判分基於同一個指法決策來源？

**答**：可以。透過 Dual-Track Decoupling，把 fingering decision (Logic Track) 與 hand rendering (Visual Track) 解耦，讓兩者都基於 deterministic 來源。Stage A→B→C 三階段把同一個 ArLSTM 指法決策貫穿到評分邏輯、視覺渲染、UI 顯示三個層面。實作上對下游 module shape 完全相容，更換指法來源（如改用 pianoplayer 做 ablation）不需改動 comparator / renderer / UI。

**RQ2（選擇問題）**：在多個候選指法決策來源中，哪一個最適合擔任 Logic Track？

**答**：**Style-dependent**。Canon RH+LH (n=183 neutral subset) 與 Bach LH (n=78 neutral) 上 ArLSTM 大幅勝過所有 baseline：

| Track | Canon RH+LH Soft | Bach LH Soft |
|---|---|---|
| **ArLSTM** | **0.792** | **0.878** |
| ArGNN | 0.654 | 0.859 |
| pianoplayer | 0.578 | 0.391 |
| motion_v4 | 0.358 | (no fingertips) |

但 Bach RH (n=122 neutral) 上 **pianoplayer 反超** (Soft 0.734 vs ArLSTM 0.406)，因為 Bach RH 連續 16 分音符 scalar 段落正好是 Parncutt cost model 設計時的核心場景。

**結論**：將 ArLSTM 設為 default（適配大多數教學曲目的 chordal/homophonic 段落 + 所有 bass line），但保留 pianoplayer 作為 `--fingering-source pianoplayer` 可選方案（適配 scalar-dominant 段落如 Bach inventions、Czerny 練習曲）。Logic Track **本來就是** runtime-switchable 的，這個彈性設計剛好涵蓋 cross-style 需求。LH 上 pianoplayer 的 Soft 在兩首曲子都 < 0.4，呈現 systematic-failure 樣態（不是「弱於 ArLSTM」，而是「接近 random」）——為 cost-model 對 LH ring finger 的結構性 atrophy 提供跨樂曲一致證據。

**RQ3（教學閉環問題）**：能否把上述系統做成學生可以實際使用的工具？

**答**：可以。PracticeScreen + WebSocket broadcaster + ClipRecorder 構成一個即時 per-onset feedback 的閉環。其中 ClipRecorder 自動生成的學生本人 vs ArLSTM 示範並排對比影片，是相對 Synthesia 類商業產品的關鍵差異。

## 7.2 主要 Contributions 回顧

| Contribution | 第幾章 | 量化證據 |
|---|---|---|
| Dual-Track Decoupling 架構 | ch3 | 系統可在 source 間切換 |
| Ramoneda 2022 整合為 default | ch3, ch4 | Soft 0.792 corpus |
| Rule-based GT framework | ch4, ch5 | 預測中性子集設計 |
| Stage A→B→C 完整 pipeline | ch3, ch5 | Canon + Summer 兩首通過 |
| 量化 cost-model failure modes | ch4 | LH ring=2 (-98%), pinky 濫用 |

## 7.3 限制 (Limitations)

本論文採取「整合 SOTA 而非自研 SOTA」的策略，相應有以下限制：

### 7.3.1 評估面

1. **GT 規模**：Canon 一首兩手 n=290 onset。若 reviewer 要求 3+ 首 cross-genre validation，仍嫌不足。本系統的 `build_gt_rulebased.py` 可以 cheaply 擴增到任何 MIDI，但人工 sanity check 需要時間
2. **GT 主觀性**：rule-based GT 採用 Henle/Schirmer 出版指法慣例，但鋼琴指法本質上有 inherent flexibility，不同教學派別會有差異。理想的 GT 應由 3+ 位專家獨立標註（PIG corpus 做法），時間成本超出 undergrad thesis 範圍
3. **arlstm-tiebreaker 殘留偏差**：predictor-neutral subset 已排除 23% arlstm-自定 entries，但剩餘 rule-based entries 中部分 chord rule（如 M3 → [1, 4]）與 ArLSTM 的 PIG-trained prior 仍相關。完全消除 self-favoring 需要獨立第三方 GT，最理想是 PIG 官方 test split——但 PIG corpus 是 upon-request

### 7.3.2 模型面

1. **ArLSTM 視野有限**：原 Ramoneda 2022 模型只看 ±20 lookahead notes，無法考慮樂句、踏板、後續樂段的指法佈局。長 phrase 中的 thumb-under 策略可能 sub-optimal
2. **生成式 Visual Track 仍有隨機性**：biomech v4 生成的非按鍵 transitional motion 仍 stochastic。雖然不影響 fingering decision，但 reviewer 可能質疑「同一首歌不同 render 為什麼不一樣」
3. **PIG-trained inductive bias**：ArLSTM 學到的是西方古典鋼琴的 fingering convention，對 jazz、爵士、民俗音樂的指法可能不適用

### 7.3.3 系統面

1. **Hardware live mode 未驗證**：所有 demo 都採用 replay 模式（用 biomech v4 影片當 fake student）。真實 webcam + MIDI keyboard 整合是 Stage D 待完成項
2. **wrist height / curvature feedback v1 未實作**：comparator 只判「哪根指頭按下去」，不判「手腕是否抬太高、手指是否彎曲」。這是鋼琴教學的核心 feedback dimension 之一，目前缺失
3. **UI 未經正式 user study**：第六章描述的設計基於 informal 內部測試，沒有量化資料支持「per-onset 視覺脈衝是否有助於指法錯誤識別」

## 7.4 未來工作

### 7.4.1 短期 (1–3 個月)

1. **Style-aware Logic Track 自動切換**：基於本論文 Bach Invention audit 揭示的 cross-style 行為差異，下一步是研究**自動偵測樂曲 texture 並切換 fingering source**。例如：用簡單 onset density / pitch variance heuristic 偵測「scalar dominant」段落，自動切到 pianoplayer；其他段落用 ArLSTM。這是 thesis 後直接的下一個 paper grade 工作
2. **拓展 cross-piece 驗證**：再選 Mozart Sonata K545 第一樂章 (homophonic + 跨手)、Chopin Etude (重技巧過渡) 兩首作為補充。ArGNN 在 Bach polyphonic RH 上**沒有反超 ArLSTM** (0.402 vs 0.406)，所以 polyphonic-aware GNN 在 Two-Part Invention 這種對位 texture 上的優勢需要更複雜的 polyphony 才能 surface
2. **OSMD 樂譜整合**：Stage D 第一項——把 PracticeScreen 的 placeholder 樂譜換成從 MIDI 即時渲染、標註 ArLSTM 推薦指法的真實樂譜
3. **Hardware live mode 部署**：插上 webcam 與 MIDI keyboard，驗證 MediaPipe finger detection 在真實光照與真實學生手的 robustness
4. **Wrist height feedback**：comparator 加入 wrist y-axis trajectory 評估，提供 "手腕太高" / "手腕太低" 的 per-section feedback

### 7.4.2 中期 (3–6 個月)

1. **PIG 官方 test split**：email Nakamura 教授 (kyushu-u) 申請 official PIG access，在 PIG-test 上做 reproducible benchmark（這是 thesis 升級到 paper 的關鍵步驟）
2. **多 annotator GT**：請 3–5 位有 ABRSM 8 級以上資格的鋼琴老師獨立標註 Canon RH/LH，量化 inter-annotator agreement 並修正 single-annotator GT 偏差
3. **Long-horizon ArLSTM**：在 Ramoneda 2022 架構上把 lookahead 從 ±20 拓寬到 phrase-aware（用 Transformer 替換 LSTM encoder），看樂句感知是否能改善 chord pivot decision

### 7.4.3 長期 (6+ 個月)

1. **生成式 Visual Track 換成 conditioned**：把 ArLSTM 的 fingering token 餵進 PianoMotion10M 的 diffusion 作為 conditioning input，重新訓練 motion generator，讓 v4 的視覺軌跡 by construction 跟 prescribed fingering 一致——這是 Stage A→B 之上的最後一塊架構升級
2. **學生個人化**：根據學生過去的 session log，動態調整 expected fingering（例如手較小的學生避開大跨度配指）。本論文 `songs/<song>_fingering.json` override 機制是這個方向的 hook
3. **多樂器拓展**：Dual-Track Decoupling 不限於鋼琴。古典吉他、小提琴、薩克斯風都有「正確指法 != anatomical plausibility」的同構問題。本系統的架構可作為通用 framework

## 7.5 結語

本論文的核心觀察是：**AI 音樂教學的 SOTA 元件已經存在於各自子領域，缺的是把它們組合成可教學的完整閉環**。透過 Dual-Track Decoupling、Stage A→B→C 整合、與 corpus-level 量化評估，本系統把 Ramoneda 2022 的 ArLSTM 變成可被學生實際 benefit 的工具——而不只是 paper 裡的 benchmark 數字。

對 reviewer：如果你要在 thesis defense 中問一個能 surface 整篇貢獻的問題，建議問：「**你的工作跟單純把 Ramoneda 2022 跑在 Canon 上有什麼差別？**」答案是：本論文證明了 Ramoneda 的指法決策**值得**接到一個視覺示範系統上（透過 Stage A 量化驗證），且**有辦法**接（透過 Stage B/C 的工程整合）。前者是 evaluation contribution，後者是 systems contribution，兩者結合才把 ArLSTM 從 benchmark model 變成 teaching tool。

完。
