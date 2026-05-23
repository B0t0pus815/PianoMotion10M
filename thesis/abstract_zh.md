# 中文摘要 (Abstract — 繁體中文)

**論文題目**：AI 鋼琴學習：基於 Dual-Track Decoupling 架構整合 PianoMotion10M 與 ArLSTM 指法決策模型

**作者**：[學生姓名] · **指導教授**：[教授姓名] · **系所**：[系所] · **學年**：2026

---

近年來深度學習於音樂資訊處理 (Music Information Retrieval) 領域有顯著進展，使得 AI 輔助音樂學習成為可能。然而現有 SOTA 工作多半專注於單一面向——演奏動作生成（如 PianoMotion10M，Liu et al., 2024）、指法決策（如 Ramoneda et al., 2022）、或演奏評估——缺少**將三者整合成一個完整教學閉環**的系統實作與量化驗證。

本論文針對「能否設計一個 AI 鋼琴學習系統，使得學生看到的正確示範與系統的判分基於同一個指法決策來源」這個整合性研究問題，提出 **Dual-Track Decoupling 架構**：把指法 judgment 與 hand rendering 解耦，由 deterministic 神經模型 (Ramoneda ArLSTM) 擔任 Logic Track 判官，由 anatomy 引擎 (biomech v4) 擔任 Visual Track 渲染器。系統實作分為三個階段——Stage A 把 ArLSTM 整合進統一的 `generate_fingering(source='arlstm')` API，Stage B 把指法決策注入 `simple_natural --fingering arlstm` 渲染管線產出 mp4，Stage C 把渲染結果接到 React PracticeScreen 學生實際看到的 UI。

為驗證 Logic Track 候選人的選擇合理，本論文設計 **rule-based corpus 評估框架** (`build_gt_rulebased.py`)，採用文獻可引用的鋼琴教學慣例自動生成 GT，並透過 `predictor-neutral subset` 設計防止 LLM-GT 的 self-favoring 偏差。在 Canon RH+LH 合併 n=183 neutral subset 上 ArLSTM 達到 Soft Accuracy **0.792**，顯著優於 pianoplayer (0.578, -27%) 與 motion-derived baseline (0.358, -55%)。LH 上 pianoplayer 僅 0.275，呈現 systematic-failure 樣態，為 Parncutt cost model 對左手 ring finger 的結構性 atrophy 提供直接證據。Cross-piece audit 在 Bach Invention No.1 上揭示 ArLSTM **不是 universal winner**：RH 連續 scalar 段落 pianoplayer 反超 (Soft 0.734 vs 0.406)。這個 nuance 不削弱本論文整合貢獻，反而強化「Logic Track 應保留 runtime-switchable 設計」的架構決策，並指向 style-aware 自動切換為後續直接工作。

**主要貢獻**：(1) Dual-Track Decoupling 架構；(2) 整合 Ramoneda 2022 SOTA 為 default Logic Track；(3) rule-based corpus GT framework 含 predictor-neutral subset；(4) Stage A→B→C 完整 pipeline 整合，三首風格不同曲目 (Canon, Summer, Bach Invention) 端到端驗證；(5) 量化證據揭示 cost-model 的結構性 LH bias 與 SOTA 神經模型的 cross-style 局限。

**關鍵詞**：AI 音樂教學、鋼琴指法決策、Dual-Track 架構、PianoMotion10M、Ramoneda 2022 ArLSTM、即時演奏回饋、Stage A/B/C 整合
