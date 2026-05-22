# 第二章 文獻回顧 (Related Work)

本論文涉及三個交集子領域：(1) 自動鋼琴指法決策、(2) 3D 手部姿態與動作生成、(3) AI 輔助音樂教學系統。本章對每個子領域的代表性工作做扼要回顧，並指出本論文與這些工作的差異與整合關係。

## 2.1 自動鋼琴指法決策 (Automatic Piano Fingering)

鋼琴指法決策的形式化任務是：給定一個 MIDI score（每個 note 有 pitch、onset time、duration），輸出 per-note 的 (hand, finger) 標籤，其中 finger ∈ {1, 2, 3, 4, 5} 對應拇指至小指。

### 2.1.1 規則式與優化方法

最早的 systematic approach 是 Parncutt et al. (1997) [^parncutt97] 的 ergonomic cost model。該工作從鋼琴生理學文獻萃取 12 條規則（如「同指換音昂貴」、「拇指穿越受限制於白鍵」、「ring/pinky 比中指弱」），每條規則對應一個 cost 函數，最終以動態規劃 (Viterbi) 求最小總 cost 的指法序列。

Parncutt's cost model 至今仍是強 baseline，開源的 `pianoplayer` 套件即是其直接實作。然而該 cost 函數的權重是手調，且對左手 ring finger 給定的 expensive 設定容易造成「ring 棄用、pinky 濫用」的 bias——我們在第四章將直接量化這個 bias。

Hart et al. (2000) 與 Sébastien et al. (2012) 提出隱馬可夫模型 (HMM) 變體，把指法選擇視為 hidden state，能在演奏資料上做訓練但仍受限於 Markov assumption。

### 2.1.2 神經網路方法

Nakamura et al. (2014) [^nakamura14] 釋出 **PIG corpus**（Piano-Fingering dataset），包含 150 首古典樂段、每首由 5–8 位專家鋼琴家獨立標註的指法。PIG 成為後續神經網路工作的標準 benchmark。

Ramoneda et al. (2022) [^ramoneda22] 提出兩個 SOTA 模型：

- **ArLSTM**：3-layer Bidirectional LSTM encoder + Autoregressive LSTM decoder + Beam search。Embedding 僅用 normalized MIDI pitch
- **ArGNN**：Gated Graph Neural Network encoder（onset/next edges in chord graph）+ 相同 AR decoder。針對 polyphonic 樂段設計

同篇 paper 還釋出 **ThumbSet** 資料集（2,523 首 MuseScore 部分標註），用作 pre-training data，在 ThumbSet 預訓練後 PIG fine-tune 顯著優於 HMM/RNN baseline。本論文直接使用 Ramoneda 釋出的預訓練 checkpoint 作為 Logic Track default。

### 2.1.3 本論文的位置

本論文**不在指法決策 model 本身做 contribution**——這部分採用 Ramoneda 2022 SOTA inference。我們的工作是：

1. 建立 corpus-level 評估框架，把 ArLSTM 跟其他 candidate (pianoplayer, motion-derived) 在 Hard/Soft Accuracy 上做直接比較
2. 把指法決策 integrate 到一個完整的教學系統 (Stage A→B→C)

## 2.2 鋼琴手部姿態與動作生成

從樂譜或音訊生成擬真鋼琴演奏動作是近年快速發展的子領域。

### 2.2.1 MANO 參數化手部模型

Romero et al. (2017) 提出 MANO，把人手骨架 + 形狀變化用 51 個 PCA 主成分參數化。MANO 成為手部動作研究的標準輸出格式，本論文採用的 PianoMotion10M 即輸出 MANO 參數。

### 2.2.2 PianoMotion10M

Liu et al. (2024) [^liu24] 發佈 **PianoMotion10M**——目前最大規模的鋼琴手部 3D 動作資料集，包含 116 小時鳥瞰鋼琴演奏影片、對齊的音訊與 MIDI、以及 1000 萬幀 MANO 標註。同篇 paper 提出 audio-to-motion 的 Diffusion Model：

- **Encoder (Piano2Posi)**：Wav2Vec 或 MIDI encoder 將音訊或樂譜編碼為時序特徵
- **Diffusion (Unet1D)**：以特徵為 conditioning，DDPM 採樣輸出 MANO 姿態序列

PianoMotion10M 在 visual realism 與 anatomical plausibility 上達到 SOTA，但**未針對 fingering 正確性訓練**——其 loss 函數僅要求輸出與訓練集軌跡相似，而訓練集本身的指法是 YouTube 鋼琴家的個人選擇，不必然是 pedagogically correct。本論文 Phase A 在這個基礎上做了 v2 → v4 的 rule-based 後處理 (`biomechanical_fingering.py`)，但這個改進仍然產生與 pedagogical convention 不一致的指法分布——這是 Stage A → B 整合要解決的問題。

### 2.2.3 機器人鋼琴演奏

Zakka et al. (2023) RoboPianist 與 RP1M 把這條線推到極端：用 RL 訓練雙手機器人在物理模擬器中彈出 200 首樂曲。雖然與本論文目的（教學）不同，但其輸出的動作軌跡可作為 cross-validation 來源。

## 2.3 AI 輔助音樂教學系統

學術界對 AI 音樂教學的關注集中在以下三類系統：

### 2.3.1 演奏評估 (Performance Assessment)

PYIN / CREPE 等 pitch tracker 配合 DTW (Dynamic Time Warping) 可以做整曲對齊與正確率評分。SmartMusic、MyMusicCoach 等商業產品大量採用這條路線。然而這類系統只能評估「彈了什麼音」，無法評估「用了什麼指法」——後者需要 visual 或 sensor 資訊。

### 2.3.2 視覺指法擷取

Kim et al. (2024) 與 At Your Fingertips (ICLR 2024) 從 YouTube 鋼琴演奏影片中用 GAN + domain adaptation 自動 extract 指法 silver-label。這條線本論文未直接採用，因為我們的場景需要 **prescribe** 正確指法（給學生看），而非 **transcribe** 既有演奏。

### 2.3.3 互動教學原型

Synthesia 等商業軟體有 falling-keys piano roll 顯示，但不評估指法。本論文 PracticeScreen 設計借鑑這類 UX 慣例（falling keys、playback bar、accuracy ring），但加上 ArLSTM-based per-onset 指法 feedback 與錯誤 onset 自動 clip 回顧——這是市面上現有商業軟體都沒有的功能。

## 2.4 本論文的整合定位

把上述三個子領域與本論文擺在一起：

| 子領域 | SOTA | 本論文採用 | Contribution 在哪 |
|---|---|---|---|
| 自動指法 | Ramoneda 2022 ArLSTM | 直接 inference | 整合 + 評估，不重訓 |
| 動作生成 | PianoMotion10M + 後處理 v4 | 採用 | 解耦其判官角色 |
| 互動教學 | Synthesia 類產品 | UI 慣例借鑑 | per-onset 指法 feedback |

**本論文不是任何單一子領域的 SOTA**，但是**第一個把三者拼成完整教學閉環、並對拼接決策做量化評估的工作**。

[^parncutt97]: Parncutt, R., Sloboda, J. A., Clarke, E. F., Raekallio, M., & Desain, P. (1997). An Ergonomic Model of Keyboard Fingering for Melodic Fragments. *Music Perception*, 14(4), 341–382.

[^nakamura14]: Nakamura, E., Saito, Y., & Yoshii, K. (2014). Statistical Learning and Estimation of Piano Fingering. *ISMIR*.

[^ramoneda22]: Ramoneda, P., Jeong, D., Nakamura, E., Serra, X., & Miron, M. (2022). Automatic Piano Fingering from Partially Annotated Scores using Autoregressive Neural Networks. *Proceedings of the 30th ACM International Conference on Multimedia*.

[^liu24]: Liu, et al. (2024). PianoMotion10M: Dataset and Benchmark for Hand Motion Generation in Piano Performance.
