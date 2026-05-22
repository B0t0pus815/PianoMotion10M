# 第一章 緒論 (Introduction)

## 1.1 研究動機

鋼琴是世界普及度最高的樂器之一，但學習鋼琴傳統上需要長期一對一的教師指導，主要原因是**指法選擇**——「該用哪根手指按哪個鍵」這個決策。錯誤的指法不會立即發出錯誤的聲音，但會在長期累積中造成手部過勞、樂句不流暢、進階曲目難以執行。傳統教學中，指法錯誤的偵測與糾正是教師最重要也最花時間的工作。

近年深度學習在音樂資訊處理 (Music Information Retrieval) 領域有顯著進展，使得 AI 輔助音樂學習成為可能。然而現有系統多半專注於單一面向：

- **演奏生成** (generative)：給定樂譜，生成擬真的鋼琴演奏動作（如 PianoMotion10M [Liu et al., 2024]）。但生成的指法**僅追求 anatomical plausibility，不保證 pedagogical correctness**，學生跟著看會學到不一定正確的指法
- **指法決策** (discriminative)：給定樂譜，輸出每個 note 該用哪根手指（如 Ramoneda et al., 2022 [^ramoneda22]）。但只輸出標籤，沒有視覺示範
- **動作評估** (assessment)：基於 webcam 或感測器評估學生演奏，但通常只報全曲分數，缺乏 per-onset 即時回饋

本研究的核心觀察是：**這三個面向已經有各自的 SOTA 工作，缺少的是把它們整合成一個完整的學習閉環**——AI 知道怎麼正確彈、AI 能視覺示範、AI 能即時判分回饋。把這個閉環做出來、並對其中關鍵設計決策做量化評估，是本論文的主要 contribution。

## 1.2 研究問題

本論文圍繞以下三個問題展開：

**RQ1（架構問題）**：能否設計一個 AI 鋼琴學習系統，使得「正確示範」與「判分」基於同一個**指法決策來源**，避免兩者矛盾？

RQ1 看似 trivial，但實際 build 出 Phase A 原型時暴露問題：若用 generative 模型同時擔任示範器與判官，模型的 stochastic sampling 會洩漏到判分結果，導致同一首歌在不同 run 中標準答案不一樣。我們透過 Dual-Track Decoupling 架構解決（第三章），並在 Stage A→B→C 三階段中把單一指法決策貫穿到視覺渲染與 UI 顯示。

**RQ2（選擇問題）**：在多個候選指法決策來源（rule-based, motion-derived, neural SOTA）中，哪一個最適合擔任 Logic Track？

RQ2 是 thesis 主要的 empirical 工作。第四章建構 corpus-level 評估框架 (n=183 RH+LH neutral subset on Canon)，比較四個候選來源在 Hard/Soft Accuracy 與 finger distribution 上的表現，並驗證 cross-piece (Summer) 泛化能力。

**RQ3（教學閉環問題）**：能否把上述系統做成一個學生可以實際使用的工具？

RQ3 涉及 React-based PracticeScreen 的設計、即時 feedback 的 WebSocket 傳輸、以及錯誤 onset 觸發的回顧影片自動生成。第六章將描述使用者介面與互動設計。

## 1.3 主要貢獻

本論文具體貢獻如下：

1. **Dual-Track Decoupling 架構** — 把 fingering judgment 與 hand rendering 解耦，由 deterministic 指法決策器 (Logic Track) 與 anatomy 引擎 (Visual Track) 分工。架構本身可以在不同 fingering 來源間切換而不影響下游元件。

2. **整合 Ramoneda 2022 SOTA 為 Logic Track default judge** — 把 PIG-finetuned ArLSTM 包裝成系統可用的 `generate_fingering(source='arlstm')` API，並對下游 comparator / renderer / UI 完全透明。

3. **Rule-based corpus-level 評估框架** — 提出 `build_gt_rulebased.py` 從 piano-pedagogy 文獻慣例自動生成 GT，配合 `predictor-neutral subset` 設計防止 LLM-GT 的 self-favoring 偏差。整套評估流程一行可重現。

4. **Stage A→B→C 完整 pipeline 整合** — 從指法決策 (Stage A) 到視覺渲染 (Stage B) 到使用者介面 (Stage C) 的端到端鏈條，在兩首風格不同的曲子 (Canon, Summer) 上驗證泛化。

5. **量化結論** — ArLSTM 在 corpus-level neutral subset 上 Soft Accuracy 0.792，顯著優於 pianoplayer (-27%) 與 motion-derived baseline (-55%)。LH 上 pianoplayer 的 Soft 為 0.275，**達到 systematic failure 水準**，為「motion-derived 不適合當 judge」與「cost model 在某些手別上系統性失誤」提供直接證據。

## 1.4 論文結構

- **第二章 文獻回顧** — 鋼琴指法生成、3D 手部姿態合成、AI 音樂教學三個 sub-field 的 SOTA 工作
- **第三章 系統架構** — Dual-Track Decoupling 設計、Stage A/B/C 三階段整合方式
- **第四章 評估方法與結果** — Logic Track 候選人比較、corpus-level 數字、失敗模式分析、cross-piece 泛化驗證
- **第五章 系統實作** — 關鍵工程細節：MIDI 對齊、IK 渲染、ffmpeg pipeline、WebSocket broadcaster
- **第六章 使用者互動設計** — PracticeScreen UI、即時 feedback overlay、錯誤 clip 自動回顧
- **第七章 結論與未來工作** — 主要 finding、限制 (limitations)、可能的延伸方向（hardware live mode、wrist curvature feedback、更多曲目泛化）

[^ramoneda22]: Ramoneda, P., Jeong, D., Nakamura, E., Serra, X., & Miron, M. (2022). Automatic Piano Fingering from Partially Annotated Scores using Autoregressive Neural Networks.
