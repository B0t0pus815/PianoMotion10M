# 致謝 (Acknowledgments)

本論文是我大學最後一年的研究成果，能完成這個結合 deep learning 與鋼琴教學的整合系統，需要許多人的協助與支持。

首先感謝指導教授 **[教授姓名]**——從 2026 年初提出研究方向、中段架構 pivot 時 (2026-05-19 Dual-Track Decoupling 決策)、到最後 evaluation 章節 corpus 評估設計，教授給予的方向修正與耐心讓我能在 4-6 個月的 thesis 時間預算內完成完整的 Stage A → B → C 整合工作。教授對於「整合性研究 vs 全新 SOTA」的辨識，幫助我把精力集中在真正能完成且有 contribution 的範圍。

感謝口試委員 **[委員 1]** 與 **[委員 2]** 的時間與 critical feedback。

感謝 **PianoMotion10M 原作者 Liu, Gan, Wang, Wu, Zhu (ICLR 2025)** 釋出資料集、模型與 codebase。本論文的 motion generation backbone 完全建立在他們的工作之上。

感謝 **Ramoneda, Jeong, Nakamura, Serra, Miron (ACM MM 2022)** 釋出 ArLSTM/ArGNN 預訓練 checkpoint 與 ThumbSet dataset。本論文的 Logic Track judge 採用他們的 SOTA 推論結果，沒有他們開源的工作，本論文整合方案不可能成立。

感謝 **Nakamura 教授 (Kyushu University)** 維護 PIG corpus 並透過 Ramoneda 共同作者身份間接讓本論文受益於 PIG-trained 模型權重。

感謝匿名 reviewer 在中期報告對本論文 "rule-based GT 是否會 self-favor ArLSTM" 質疑——這直接催生了 `--exclude-tiebreakers` predictor-neutral subset 設計，是本論文 evaluation 章節最重要的方法論強化。

感謝同學 **[同學 1]** 與 **[同學 2]** 在 PracticeScreen UI design 階段擔任 informal user testing 對象並提出 feedback。

感謝家人在我長期投入 thesis 與 model debugging 過程中的支持。

最後感謝 **Anthropic Claude** 在我獨自 implement 與 thesis 寫作階段擔任 pair programmer 與草稿產生 assistant——具體 commit 列表見 git log，每個 commit 的 Co-Authored-By 已記錄此份協作關係。AI assistance 的使用範圍包括：corpus evaluation framework 設計、build_gt_rulebased.py rule table 草擬、pytest 測試套件、defense slides + Q&A 草稿、CHANGELOG/THESIS.md/Makefile 等 docs 生成；不包含：研究問題定義、Dual-Track 架構決策、Stage A/B/C 切分、實驗結果解讀。所有 AI 產出的程式碼與 docs 經本人 review 與調整後才 commit；所有 audit 數字皆基於實際 inference run 產生，非 AI 生成。
