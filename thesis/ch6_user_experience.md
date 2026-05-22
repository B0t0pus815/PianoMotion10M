# 第六章 使用者互動設計 (User Experience)

本章描述學生實際操作系統的介面 (`webui/src/PracticeScreen.js` + 周邊元件)，以及背後的互動設計決策。本論文 UI 設計目標是把第三章 Logic Track 的 per-onset feedback 翻譯成學生可以**立即理解並修正**的視覺訊號。

## 6.1 設計動機

傳統線上音樂教學軟體 (Synthesia, SmartMusic 等) 採用 falling-keys piano roll，但 feedback 多半只到音符對錯層級——彈了 C4 是對是錯。本論文要解決的是**指法**對錯：學生彈了 C4 但用了錯誤的手指，這個資訊在傳統軟體中不存在。

設計挑戰：

1. **指法錯誤是即時且密集的**——一個 onset 一個決策，學生在 3 分鐘曲子裡會做 300+ 個決策。逐個 popup 會視覺疲勞
2. **指法錯誤不直接導致聲音錯誤**——學生主觀沒有「錯了」的回饋，必須由系統視覺化呈現
3. **「正確指法」不止一種**——基於 Hard/Soft Accuracy 雙指標的設計（第四章 4.3 節）暗示 UI 也需要「完全對 / 方向對 / 錯」三層視覺差異

## 6.2 主要 UI 元件

### 6.2.1 Hero Video (`GestureVideo`)

螢幕上方是 Stage B 渲染的「正確示範」mp4 (`canon_arlstm_kb.mp4`)，1920×1080 縮放至卡片寬度。video 的 `currentTime` 是整個 PracticeScreen 的時間基準——其他元件 (PianoRoll, ScoreRing, FeedbackOverlay) 全部透過 `onTimeUpdate` 同步。

角落 brand label `AI · ArLSTM × biomech v4` 一秒解釋兩個 track 的角色：學生看到的指法決策來自 ArLSTM，視覺渲染來自 biomech v4。對 reviewer 也是 Dual-Track 設計的視覺證據。

### 6.2.2 ScoreRing (準確率環)

以圓環視覺化 corpus-level Hard Accuracy。連線前顯示 placeholder 92%（demo 用），收到第一個 onset event 後切換到實時計算的 `Math.round(100 * correct / total)`。

文字部分有四段語境：

- `total === 0`：「等待第一個音」
- `accuracy ≥ 80`：「你正在**穩定演奏中**」（綠色語氣）
- `accuracy ≥ 50`：「跟上**大方向**中」（黃色語氣）
- `accuracy < 50`：「**指法**需要注意」（紅色語氣）

語氣設計刻意避免 binary「對/錯」感受——80% 對的時候應該被鼓勵繼續，不應感到「20% 錯了」的挫敗。

### 6.2.3 FeedbackOverlay

每個 onset 在 Hero video 上方 overlay 一個 ~1.5 秒的視覺脈衝，呈現：

- 圖標：✓ (correct) / ≈ (soft alternative, ±1 指) / ✗ (wrong)
- 預期指法：`R/middle` (右手中指)
- 學生實際指法：(若有 detection)
- 信心值

設計刻意避開「在影片上顯示文字」的傳統做法——用顏色脈衝 + 圖標代替文字，學生眼睛仍然能跟著示範影片，認知 overhead 最低。

### 6.2.4 PianoRoll (落鍵畫布)

下方是 falling-keys 風格的鋼琴卷簾。每個未來 onset 用一個從上往下落的色塊表示，落到底部鍵盤的瞬間就是該彈的時間點。色塊高度等比於 note 的 duration，水平位置對應鋼琴鍵的 pitch。

`statusMap` (從 WS feedback events 累積) 把已過 onset 的色塊重新染色：

- 灰色：未來 onset
- 綠色：已彈對
- 黃色：彈了 ±1 指替代
- 紅色：彈錯

學生用周邊視覺看 PianoRoll，中央視覺看 Hero Video 跟 FeedbackOverlay——多視覺層分擔認知負擔。

### 6.2.5 RecordingBanner

當 ClipRecorder 在錄製錯誤 clip 時 (sliding-window error rate > threshold)，影片上方滑出紅色橫幅「正在記錄練習段落」。錄製結束後橫幅淡出，clip 出現在下方 ClipsStrip。

### 6.2.6 ClipsStrip

側捲動的縮圖列表，列出本次練習觸發的所有錯誤 clip。每個 clip 是 1280×360 的 hstack（左：學生本人 video，右：ArLSTM 正確示範 video），點下去播放——學生能立即看到自己跟 reference 的差異。

這個元件是本論文相對 Synthesia 類產品的關鍵差異：**錯誤不是匯總到 session 結束才看，而是即時定位到具體 5-10 秒片段並提供並排對比**。

### 6.2.7 Sheet Music Card

最底下的樂譜卡片目前是 placeholder—硬編碼兩小節 G clef 樂譜，與當前播放歌曲無關。這是 Stage D 待完成項，目標是 integrate OpenSheetMusicDisplay (OSMD) 從 MIDI 即時渲染對應樂譜並標註 ArLSTM 推薦指法。

### 6.2.8 Transport Controls

- Play/Pause 按鈕（藍色主按鈕）：控制 hero video + audio 同步
- Retry 按鈕：重置 elapsed time 跟 statsMap（目前尚未 wire 完）
- Close 按鈕：結束 session 進入 review screen

## 6.3 資料流動

```
┌──────────────────┐
│  Backend Runner   │
│  (Python, port    │
│   8766 WS)        │
└──────┬───────────┘
       │
       │  WebSocket
       │  event = {
       │    type, onset_index,
       │    expected_hand, expected_finger,
       │    detected_finger, confidence,
       │    is_correct, ...
       │  }
       │
       ▼
┌──────────────────┐
│ useFeedbackStream │ ──→ stats {total, correct, wrong}
│   (React hook)    │ ──→ statusMap {onset_id: status}
│   uses event-     │ ──→ clips list
│   buffer with     │ ──→ recording flag
│   playhead-aware  │
│   popReady(t)     │
└──────┬───────────┘
       │
       │  popReady(t) returns the event whose
       │  expected time <= current playhead time
       │  (so feedback flashes on-time, not
       │  whenever the WS happens to deliver)
       │
       ▼
┌──────────────────┐
│ FeedbackOverlay   │   (pulse animation on hero video)
│ ScoreRing         │   (accuracy + tone text)
│ PianoRoll         │   (rolling key colors)
│ RecordingBanner   │   (when clip recording active)
│ ClipsStrip        │   (when clips arrive)
└──────────────────┘
```

關鍵設計：WS event 不是「來就播」，而是 enqueue 等到 hero video 的 `currentTime` 越過該 onset 的 expected time 才 trigger UI animation。這保證學生看到的脈衝跟正確示範影片在時間上對齊，不會因為 backend 處理快或慢就 feedback 出現在不對的位置。

## 6.4 互動流程

學生實際 session 的時序：

```
T+0s    開啟 PracticeScreen（song = Canon）
        Hero video 載入 canon_arlstm_kb.mp4
        WebSocket 連線嘗試（等 runner）
        ScoreRing 顯示 placeholder「等待第一個音」

T+0s    使用者按 Play
        Hero video + audio 同步開始
        PianoRoll 開始往下捲動，第一個 onset 預告

T+13.7s 第一個 onset (LH, pitch=50, expected=pinky)
        Backend runner detect 學生指法 → correct
        WebSocket push event
        FeedbackOverlay 綠色 ✓ 脈衝 + 「L/pinky」標籤
        PianoRoll 對應 block 變綠
        ScoreRing 更新到 1/1 = 100%

T+22.5s 第七個 onset
        Backend detect 學生用 thumb 但 expected 是 pinky
        WebSocket push event, is_correct=False
        FeedbackOverlay 紅色 ✗ 脈衝
        PianoRoll block 變紅
        ScoreRing 更新到 6/7 ≈ 86%

T+30s   累積錯誤率超過 sliding-window threshold
        ClipRecorder 觸發
        RecordingBanner 滑入「正在記錄練習段落」
        rolling buffer 開始捕捉 pre-trigger 5 秒

T+45s   ClipRecorder 完成錄製
        ffmpeg 後台合成 hstack 影片
        Clip 出現在 ClipsStrip
        RecordingBanner 淡出

T+192s  曲子結束
        使用者按 Close
        進入 ReviewScreen (out of scope this thesis)
```

## 6.5 設計反思

本章節描述的設計目前在 small-scale 內部 user testing 階段（作者本人 + 2 位非鋼琴背景的同學試用 Canon），尚未做正式 user study。可預期的問題：

1. **資訊密度可能過高**——同時顯示 hero video / overlay / piano roll / accuracy ring 在低解析螢幕（例如 13 吋筆電）可能過密。Stage D 可加 layout density toggle
2. **音樂 onset 密集區段 FeedbackOverlay 可能視覺疲勞**——例如 Canon 後半 16 分音符段，1 秒 4 個 onset = 4 個脈衝。Stage D 可考慮聚合（連續 N 個正確時降到「閒暇」狀態，只在錯誤時 surface）
3. **指法數字標籤** (`R/middle` vs `R/3`) 對非鋼琴背景使用者哪個更直觀，需測試
4. **Sheet Music 概念示意** 是 thesis demo 顯眼的「未完成」——是 Stage D 優先項

Stage D 完成後，可考慮做 8-10 位學生的 think-aloud user study，量化 UI feedback 對指法錯誤識別率的影響——這會是後續工作的方向。
