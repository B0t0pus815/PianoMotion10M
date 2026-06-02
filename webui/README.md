# HandKeys AI — Web UI

智慧鋼琴教練的網頁原型，串接 PianoMotion10M 的 biomech v4 渲染輸出。

## 結構

```
webui/
├── index.html        Entry — loads React/Babel from CDN, then src/*.js
├── songs.json        曲目清單（title、composer、videoUrl 對應 results/*.mp4）
├── serve.py          一鍵啟動：從 project root 提供 webui/ + results/ + input_songs/
└── src/
    ├── tokens.js          設計 token、Icon、Logo、Phone、BottomNav
    ├── HomeScreen.js      首頁 / 選曲
    ├── SetupScreen.js     練習設定（難度、手部、速度）
    ├── PracticeScreen.js  即時練習 — hero <video> = biomech v4 + KB overlay
    ├── ReviewScreen.js    錯誤回顧
    ├── HistoryScreen.js   練習記錄
    ├── ProfileScreen.js   個人資料
    └── App.js             ConnectedFlow（路由 6 個畫面）
```

## 啟動

```bash
python webui/serve.py            # http://localhost:8765/webui/
python webui/serve.py 8080       # 自訂 port
```

`serve.py` 會在 project root 啟 HTTP server，所以 `../results/*.mp4`、
`../input_songs/*.mp3` 才能從 `webui/songs.json` 正確相對解析。

## 從 ML pipeline 加入新曲目

1. 跑 biomech v4 + keyboard overlay：
   ```bash
   python infer_midi_diffusion.py --midi <song>.mid --output results/<song>.mp4
   python biomechanical_fingering.py --in results/<song>.mp4 --out results/<song>_biomech.mp4
   python add_keyboard_overlay.py --in results/<song>_biomech.mp4 --out results/<song>_biomech_kb.mp4
   ```
   *(實際 CLI 以你目前 pipeline 為準；這裡只是示意 v4 baseline 的步驟)*

2. 在 `songs.json` 加一筆：
   ```json
   {
     "id": "newsong",
     "title": "...",
     "composer": "...",
     "diff": "Beginner|Intermediate|Advanced",
     "dur": "M:SS",
     "key": "...",
     "accent": "#4FC3F7",
     "videoUrl": "../results/<song>_biomech_kb.mp4",
     "audioUrl": "../input_songs/<song>.mp3"
   }
   ```

3. 重新整理瀏覽器即可 — 不必重新建構任何東西。

## 為什麼是 Babel-standalone 而不是 Vite

每支 `src/*.js` 都是用 `<script type="text/babel">` 在瀏覽器內即時轉譯 JSX。
好處：不需要 `npm install`，編輯 JSX 後直接 reload 就生效。
代價：首次載入需從 CDN 拉 Babel（~3 MB），開發時 console 會多一行警告。
這對畢設 demo 跟內部 review 已經夠用；要打包成 production bundle 時再轉 Vite。

## 已知限制 / 下一步

- **PracticeScreen 的樂譜目前是程序化假樂譜** — 需要接到實際的 MIDI 同步畫面
  （建議：用 `react-vexflow` 或 `osmd` 渲染真實樂譜，並用 video.currentTime 驅動 playhead）。
- **沒有真實 webcam 比對** — UI 顯示「追蹤中 98%」是純 mock。下一階段如果要做使用者
  錄影回饋，需要 mediapipe Hands + 比對 biomech v4 ground truth。
- **僅前端 demo** — 還沒有 FastAPI 後端。新曲目需手動跑 pipeline + 編輯 songs.json。
