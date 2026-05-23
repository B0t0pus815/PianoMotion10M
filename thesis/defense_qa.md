# Defense Q&A 預備本

針對 thesis defense 可能被問的問題分類整理，附建議回答結構。每題的答案盡量短（30 秒口頭）並指向可 surface 的證據。

---

## 1. 方法論質疑

### Q1.1：你的 GT 由規則自動生成，不會自我循環抬高 ArLSTM 嗎？

**短答**：用 predictor-neutral subset 控制。

**詳答**：
- GT 23% 條目用 ArLSTM tiebreaker → 這部分 trivially 抬 ArLSTM 分
- 為此我們同時 report `--exclude-tiebreakers` 排除這些條目後的 neutral subset
- Neutral subset 上 ArLSTM (Soft 0.792) 仍勝 pianoplayer (0.578) 達 +0.214——不是 self-favoring 造成的差距
- 剩 77% GT 條目由文獻可引用的 piano-pedagogy 規則 (m3 → [1,3] 等) + predictor consensus 決定

**指向證據**：ch4 4.2.3 節、`four_way_audit.py --exclude-tiebreakers`、commit 2e91953

---

### Q1.2：你的指法 GT 反映了誰的標準？

**短答**：Henle / Schirmer 出版指法慣例（西方古典鋼琴主流）。

**詳答**：
- 本論文 GT 套用的 interval rules 與 stepwise rules 是鋼琴教學經典慣例，可在任何 ABRSM/Trinity 鋼琴教材找到對應
- limitation：未涵蓋爵士、流行、民俗音樂的指法慣例
- limitation：未做 multi-annotator agreement——單一 annotator (本人 + 規則) 反映本人對教學慣例的理解
- 未來工作建議邀請 3-5 位 ABRSM 8 級以上鋼琴老師獨立標註並做 inter-annotator agreement

**指向證據**：ch4 4.2.4 節、ch7 7.3.1 限制段

---

### Q1.3：corpus n=183 還是太小，怎麼防守？

**短答**：搭配 finger distribution 分析 (n=344 notes per piece) 提供 distribution-level 補強。

**詳答**：
- corpus Hard/Soft 是 onset-level (n=183)
- finger distribution 是 note-level (n=344 Canon)，左右手分別 107 + 237 notes
- 兩個層級證據獨立 (一個是 onset prediction accuracy，一個是 finger usage statistics)，都指向同一結論：ArLSTM > pianoplayer，特別在 LH
- ArLSTM LH ring 從 pp 的 2 次升到 14 次 (+600%) 是 n=107 上的統計顯著 effect

**指向證據**：ch4 4.5 節 finger distribution 表

---

### Q1.4：為什麼用 Canon 而不是更標準的鋼琴 benchmark？

**短答**：Canon 是公版 + 兩手 texture 完整 + 已被 PianoMotion10M 訓練資料覆蓋；Bach Invention No.1 已加為 cross-piece，揭示了 ArLSTM 不是 universal winner。

**詳答**：
- Canon in D 是 public domain，沒有版權問題
- 簡單版本 (EASY tutorial) 兩手都有完整 melodic + chord texture，適合 stress-test fingering decision
- PianoMotion10M 訓練資料中肯定有 Canon (它是 YouTube 鋼琴影片最常見曲目之一)
- **Bach Invention No.1 BWV 772** 已加為第三首 (Public Domain from Mutopia)，揭示 Bach RH scalar 段落上 pianoplayer 反而勝過 ArLSTM (Soft 0.734 vs 0.406)，LH 保持 ArLSTM 領先 (0.878 vs 0.391)。這是誠實的 cross-style 結果

**指向證據**：ch4 4.6 節、ch7 7.4.1 未來工作

---

### Q1.5：Bach RH 上 pianoplayer 反而贏，這不是反駁了你的論文嗎？

**短答**：相反——這驗證了我們的 audit framework 有 cross-style sensitivity，且增強了「Logic Track 該保留 runtime-switchable」的架構決策。

**詳答**：
- Canon-only 的結果可能被 reviewer 質疑「cherry-picked」。Bach 反向結果證明 audit framework 不是 ArLSTM 友善的工具
- Logic Track 從一開始就設計成 `--fingering-source arlstm | pianoplayer | motion` 可切換——Bach 結果正好給這個彈性 design 一個經驗 motivation
- ArLSTM 仍然是合理 default：適配 Canon-style homophonic + 所有 LH bass line + Summer J-pop。Bach 兩聲部 invention 是專業 scalar 段落，需要特殊處理
- 後續工作（ch7 7.4.1）規劃 style-aware 自動切換——這把 Bach 反例變成 future paper 的 motivation，是 strength 不是 weakness

**指向證據**：ch4 4.6.4 修正後的 thesis claim、ch7 7.4.1 style-aware 切換

---

## 2. 系統設計質疑

### Q2.1：為什麼不重訓 ArLSTM 適配你的場景？

**短答**：thesis contribution 是整合而非 model improvement；inference-only 路線 maximize ROI。

**詳答**：
- 本論文不在 fingering model 本身做 contribution——這是 Ramoneda 2022 的工作
- 我們做的是「把 SOTA 接進視覺示範系統」這個 systems contribution
- 重訓需要 PIG 官方資料 (upon-request) + GPU 訓練時間 (2-3 週)
- 對 undergrad thesis defense 來說是 over-engineering——reviewer 在乎的是整合決策合理，不是新 SOTA

**指向證據**：ch1 1.3 contributions、ch7 7.4.3 長期未來工作

---

### Q2.2：Dual-Track Decoupling 是新的嗎？這個架構聽起來像 SoC 一樣 trivial。

**短答**：架構模式不新，但這是首次在「指法判官 + 手勢渲染」這個 specific composition 上應用並做 quantitative justification。

**詳答**：
- Separation of concerns 是軟體工程基礎——本論文 contribution 不是發明這個 pattern
- contribution 是：(1) 識別 Phase A 沒有做這個 separation 導致的具體失敗模式 (generative randomness + anatomical 不可能解)、(2) 用 corpus-level evidence 量化驗證 separation 是合理的決策
- 換句話說：「應該分開」很 trivial，「分開後 ArLSTM 該當判官」需要 ch4 整章的 evidence

**指向證據**：ch3 3.1 問題定義、ch4 整章 evidence

---

### Q2.3：pianoplayer 在 LH 上 Soft 0.275 是 system bug 還是真的這麼差？

**短答**：真的這麼差，且來自 Parncutt cost model 的 documented bias。

**詳答**：
- pianoplayer 在 LH ring 只用 2 次 (107 notes 中) 是 cost function 中對 ring 設定高 cost 的直接結果
- 這個 bias 在 Parncutt 1997 原 paper 中有討論——他們承認 LH ring 的 cost 是基於 generic anatomy，不一定 capture 個別演奏家偏好
- 我們的測試與此一致：Soft 0.275 不是 bug，是 cost model 在 LH 場景的結構性失誤
- 但這也是 pianoplayer 維持價值的地方——當 fallback 時還是 deterministic 與 fast，適合做 ablation 對照組

**指向證據**：ch4 4.5 finger distribution、ch5 5.6 pianoplayer 保留為 baseline

---

### Q2.4：你怎麼確保 webcam mode 下 MediaPipe 的 finger detection 夠 robust？

**短答**：目前所有 demo 是 replay mode (用 biomech v4 影片當 fake student)，hardware live mode 未驗證——是 limitation。

**詳答**：
- Stage D 待完成項——需要真實 webcam + MIDI keyboard 才能驗證
- MediaPipe 0.10.14 在 biomech v4 渲染影片上 detection rate 中等 (~90% 上下，依手部 occlusion)
- 真實學生影片預期更好（手有 texture，光線分布更自然）但需要實測
- 如果 detection 不夠 robust，fallback 是 MIDI keyboard 提供 ground truth 哪根鍵被按下，webcam 只用來推斷哪根 finger

**指向證據**：ch7 7.3.3 系統限制

---

## 3. 比較性質疑

### Q3.1：跟 Synthesia 之類商業產品有什麼差別？

**短答**：per-onset 指法 feedback + 自動錯誤 clip 並排對比。商業產品都不做這個。

**詳答**：
- Synthesia / SmartMusic 等只判 "彈了什麼音"，不判 "用了什麼指"
- 我們透過 MediaPipe + 指法判官提供 per-onset 指法錯對回饋
- 錯誤累積到 threshold 時 ClipRecorder 自動生成學生 vs ArLSTM 並排對比影片
- 商業產品的 review screen 通常只給整曲分數，學生不知道哪個段落該重練

**指向證據**：ch2 2.3 相關工作、ch6 6.2 ClipsStrip

---

### Q3.2：跟 At Your Fingertips (ICLR 2024) 比有什麼差別？

**短答**：他們做 transcribe (從影片提取指法 silver-label)，我們做 prescribe (告訴學生該用什麼指)。完全相反方向。

**詳答**：
- AYF 是用 GAN + domain adaptation 從 YouTube 鋼琴影片自動 extract 指法 annotation
- 他們的目標是 scale up 訓練資料 (產出 150K notes silver-label dataset)
- 本論文的目標是 prescribe correct fingering 給學生看，需要的是 deterministic prescriptive model
- 兩個工作互補：未來可以用 AYF 產生的 silver-label 餵 Ramoneda 模型擴大訓練

**指向證據**：ch2 2.3.2 視覺指法擷取

---

## 4. 實作面質疑

### Q4.1：你的 pipeline 有沒有測過 stress 情況 (極長 / 複雜曲目)？

**短答**：Canon 是 3:11 共 344 notes，已經是相當 dense 的測試。

**詳答**：
- Canon EASY tutorial 含 polyphonic 雙手 + 雙音 chord + 16 分音符密集段
- 每秒 onset 數最高約 8-10 (16 分音符 BPM=120 處)
- Pipeline 包含 stress test 已通過：MIDI 對齊、predictor 並行、IK 渲染、ffmpeg mux 都正確
- 未測：>10 分鐘長曲、6+ note simultaneous cluster chord (這些 ArLSTM 會 fallback)

**指向證據**：ch5 5.3 渲染 pipeline

---

### Q4.2：external/ 目錄是 vendored 第三方 code，會不會有 license / 維護問題？

**短答**：Ramoneda repo 是 MIT，與本論文 license 相容；維護由作者上游負責。

**詳答**：
- `external/Automatic-Piano-Fingering/` 採用 git clone shallow + .gitignore 不入 history
- Ramoneda repo MIT license，允許商業與非商業使用 + 修改
- 本論文不修改 Ramoneda code，只 import 跟 inference，所以上游 update 不會破壞我們的 wrapper
- 預訓練 checkpoint 也在他 repo 中，所以無需單獨下載資料

**指向證據**：ch5 5.2.1 vendoring layout

---

### Q4.3：你的程式碼有 test 嗎？

**短答**：core eval framework 有 demo function (相當於 example-based test)，但沒寫 unit test suite。

**詳答**：
- `evaluate_template.py:_demo()` 是 self-contained 範例，跑 `python evaluate_template.py` 就會 sanity-check 評分邏輯
- `four_way_audit.py` 本身是 integration test——若 pipeline 任何環節壞了，audit 數字會明顯偏離
- 未寫 pytest unit suite：limitation 之一，加進 future work
- 重要的 invariant (predictor bucketing 對齊、ExpectedOnset shape 一致) 是在 ch5 5.1.2 修 bug 過程中發現的，下次工作會 codify 成 test

**指向證據**：ch5 5.1 對齊 bug 修復 narrative

---

## 5. 主軸性質疑

### Q5.1：你的 thesis 一句話 contribution 是什麼？

**標準答**：

> 「我把指法決策的 SOTA (Ramoneda 2022 ArLSTM) 整合進手勢生成 SOTA (PianoMotion10M) 的視覺渲染管線，並設計 Dual-Track Decoupling 架構解決生成式模型不適合擔任判官的問題，最後用 corpus-level (n=183 RH+LH) 量化評估驗證整合決策——ArLSTM Soft Accuracy 0.792 顯著優於 baseline 27-55%。」

如果只有 10 秒：「**把 paper-stage 的指法 SOTA 變成可教學的視覺示範系統，並量化驗證為什麼這個整合是合理的。**」

---

### Q5.2：你最有信心的部分是什麼？

**短答**：corpus-level evaluation（ch4 第四章）。

**詳答**：
- 四方比較表 (pianoplayer / motion / ArLSTM / ArGNN) 是直接可重現的 quantitative evidence
- predictor-neutral subset 設計防守 self-favoring 質疑
- LH 上 pianoplayer Soft 0.275 vs ArLSTM 0.975 的對比戲劇性夠強，reviewer 看到會立刻 buy 結論
- finger distribution 分析 (LH ring 2 → 14) 是 distribution-level 補強

---

### Q5.3：你最沒信心的部分是什麼？

**標準答**：UI（ch6）+ hardware live mode。

**詳答**：
- 第六章描述的 UX 設計是基於 informal 內部測試 (作者本人 + 2 位同學)，沒有正式 user study
- Hardware live mode 全部都還是 replay (用 biomech v4 影片當 fake student)
- 這兩個都是 thesis 「打包不完美」的部分，建議在 defense 中**主動承認**，避免被反質詢

---

## 6. 終極質疑

### Q：你的工作是不是只是把幾個 paper 串起來？

**短答**：是「整合 + 量化驗證 + 系統實作」，這在 undergrad thesis 範疇是 substantial contribution。

**詳答**：
- 對 PhD-level paper，這個 contribution 確實偏 systems-engineering，不是 fundamental research
- 但對 undergrad thesis 來說 (4-6 個月時間預算 + 一人 team)：
  - 「整合」需要識別 generative-as-judge 的失敗模式並 invent Dual-Track 架構
  - 「量化驗證」需要從零設計 corpus GT framework + neutral subset 機制
  - 「系統實作」需要把 4 個獨立工具 (pretty_midi, pianoplayer, Ramoneda, MediaPipe) 對齊到統一介面
- 三者疊起來在 undergrad scope 內是 reasonable scope
- defense 時可以坦承：「這不是 paper-grade contribution，是 thesis-grade integration + evaluation」

---

## Defense 流程建議

1. **第一階段 (15 min)**：照 `defense_slides.md` 順序講
2. **Live Demo (5 min)**：開 webui 跑 Canon 5 秒，故意彈錯讓 FeedbackOverlay flash
3. **Q&A (10-15 min)**：先答完問題再分享 limitation
4. **手邊備好**：
   - laptop 跟 webui server 提前 warm up (避免 demo 開機尷尬)
   - thesis 7 章 docx 印出實體（reviewer 翻頁查）
   - 一份 `defense_qa.md` (本檔) 速查表
5. **心理建設**：reviewer 質疑是常態，不是針對你。最強的回應是「同意這是 limitation，並列入 future work」——比硬辯護有用。
