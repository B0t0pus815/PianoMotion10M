# 第五章 系統實作 (Implementation)

本章描述把第三章架構落實為可執行系統時遇到的工程問題與解決方案。重點放在三個容易踩雷的整合層：(1) MIDI 與多個 predictor 之間的時間對齊、(2) 把外部 PyTorch 模型 (Ramoneda 2022) 接進不同 conda 環境的 lazy loading、(3) Stage B 渲染 pipeline 的 ffmpeg encoder 選擇。

## 5.1 MIDI 時間對齊

整個 pipeline 涉及多個 MIDI 處理路徑：

- **pretty_midi.PrettyMIDI** — 標準 MIDI 解析，輸出 (start, end, pitch, velocity) tuple
- **pianoplayer.reader_pretty_midi** — pianoplayer 內部 reader，會把 pretty_midi 的 notes 轉成自己的 `iNote` 物件
- **Ramoneda inference** — 自己用 pretty_midi 讀，但 sort key 與 tie-break 可能不同
- **MediaPipe hand tracker** — 從影片每秒 30 frame 提取手部姿態

把這些對齊到統一的 onset_index 是 audit framework 能 work 的必要條件。

### 5.1.1 為什麼 union-based bucketing 不行

最早期 `build_gt_interactive.collect_onsets` 嘗試以 pianoplayer + ArLSTM 兩個 predictor 的 (time, pitch) 集合**聯集**作為 bucketing 基準，希望涵蓋所有 predictor 看到的事件。實際結果是：兩個 predictor 對於極近距時間 (相差 < 1 ms) 事件的 sort tie-break 不同，造成同一物理事件被聯集後拆成兩個 onset bucket，下游 evaluation 直接對不上。

### 5.1.2 採用 pp-stream-canonical 的修正

最終方案是**用一個 predictor 的事件流作為 canonical bucketing**（選 pianoplayer 因為它的 `reader_pretty_midi` 是穩定參照），其他 predictor 的 finger 預測以 `(round(time, 4), pitch)` 為 key 做 dict lookup，無對應就 fallback 為 0（=未知）。這保證 GT 與 evaluation 都跟 `engine_predictions()` 用同一個 bucket 索引：

```python
# build_gt_interactive.collect_onsets (修正版)
pp_eo = sorted(generate_fingering(midi, source='pianoplayer'),
               key=lambda e: (e.time, e.pitch))
arlstm_lookup = {(round(t, 4), int(p)): int(f)
                 for (t, p), f in zip(arlstm_info, arlstm_fingers)}

bucket_start = None
for e in pp_eo:
    if bucket_start is None or (e.time - bucket_start) > ONSET_BUCKET_SEC:
        buckets.append([])
        bucket_start = e.time
    buckets[-1].append({
        'time': e.time, 'pitch': e.pitch,
        'pp': e.expected_finger_idx + 1,
        'arlstm': arlstm_lookup.get((round(e.time, 4), e.pitch), 0),
    })
```

`ONSET_BUCKET_SEC = 0.05` 是經驗值——大到能把同一和弦的微小時差吸收，小到不會把鄰近 onset 誤合併。

### 5.1.3 evaluation 端的 array-position bug

evaluation 端原本以 `for i in range(n_gt)` 迭代 GT 陣列，並用 `i` 直接 lookup `predictions.get(i)`。當 GT 中存在 artifact-skip 條目時（rule-based GT 可能 skip 某些 onset），陣列位置不再對應原始 bucket index，造成 predictor 列在 visual table 上錯位。修正是改用 `entry['onset_index']` 做 lookup key (`four_way_audit.main` line 70)。

## 5.2 Ramoneda 模型 inference 整合

Ramoneda 2022 的開源 codebase (`PRamoneda/Automatic-Piano-Fingering`) 使用 PyTorch 與專有的 nns/ 目錄結構，未發佈為 pip package。整合方式：

### 5.2.1 Git submodule-style vendoring

把整個 Ramoneda repo `git clone --depth 1` 到 `external/Automatic-Piano-Fingering/`，加進 `.gitignore` 不入 git history。Ramoneda 提供的 4 個預訓練 checkpoint (`left_ArLSTM.pth`, `right_ArLSTM.pth`, `left_ArGNN.pth`, `right_ArGNN.pth`) 是 commit 進該 repo 的，所以 shallow clone 一次就齊。

### 5.2.2 Wrapper 模組 `ramoneda_predict.py`

對外暴露單一 entry point：

```python
def predict(midi_path: str, hand: str, kind: str = 'ArLSTM') \
        -> Tuple[List[int], List[Tuple[float, int]]]:
    """Returns (fingers[1..5], info[(time_sec, pitch_midi)])."""
```

Internal flow：
1. `sys.path.insert(0, external/Automatic-Piano-Fingering)` 動態加 import path
2. 構建模型：ArLSTM 用 `only_pitch` embedding + `lstm_encoder(input=1)`；ArGNN 用 `_EmbPitchSafe`（自寫的 bounds-safe wrapper 避免 Embedding out-of-range）+ `gnn_encoder(input_size=64)`
3. 從 `.pth` 載入 state_dict（Ramoneda 存的是 `{'epoch', 'model_state_dict', 'optimizer_state_dict', 'criterion'}` 格式）
4. 構建 graph edge_list（onset edges within chord, next edges between buckets）
5. Forward 並 argmax 取 finger logit

整個流程 lazy loaded——只有 `--fingering arlstm` 才會 trigger，避免一般用戶被 torch 與 nns/ 的 dependency 拖累。

## 5.3 Stage B 渲染 Pipeline

`simple_natural.py` 的渲染流程拆解：

```
MIDI ── extract_events ──→ List[(start_frame, frozenset(pitches))]
                                        │
                                        ▼
       ┌──── apply_<source>_fingering ──┤
       │   (source ∈ {dp, nearest,      │
       │              biomech, arlstm})  │
       │                                 │
       │ List[Dict[pitch → finger_name]] │ ← fmaps
       └────────────────────────────────┘
                                        │
                                        ▼
                          IK + wrist trajectory solver
                          (5758 frames @ 30fps, ~16s pre-pass)
                                        │
                                        ▼
                          MANO render (datasets.show)
                          ~15 fps, ~6 分鐘 / 全曲
                                        │
                                        ▼
                          add_keyboard_overlay.py
                          (per-frame 鍵盤 + 手指標籤)
                                        │
                                        ▼
                          ffmpeg concat + mux
                                        │
                                        ▼
                          *_kb.mp4 final output
```

### 5.3.1 `apply_arlstm_fingering` 設計

drop-in replacement for `apply_biomech_fingering`，shape 完全相同（list of `{pitch: finger_name}` dict）。對齊機制以 `frame_idx = round(time_sec * FPS)` 為 key，並容忍 ±5 frame 的 jitter。對 ArLSTM 沒有預測的 note（極稀有的 6+ note 和弦超出 PIG 訓練分布），fallback 到 biomech v4 的 Viterbi 結果——確保 fmaps 永遠完整，下游 IK 不會卡住。

```python
def apply_arlstm_fingering(events, is_right, midi_path, frame_tol=5):
    hand = 'right' if is_right else 'left'
    try:
        fingers, info = _arlstm_predict(midi_path, hand=hand, kind='ArLSTM')
    except (ImportError, RuntimeError, FileNotFoundError):
        return apply_biomech_fingering(events, is_right)
    # ... (build lookup, walk events, fallback as needed)
```

### 5.3.2 ffmpeg encoder 修正

原本 `add_keyboard_overlay.make_video` 使用 `-c:v libopenh264`，這在許多 system ffmpeg build (包括 conda 環境) 中未編入，造成每次 Stage B 跑都在最後 mux 步驟掛 `Unknown encoder 'libopenh264'`。修正為 `-c:v libx264 -preset medium -crf 23`，libx264 是 ffmpeg 標準配置中必含的 encoder。

修正後 Canon (3:11) 與 Summer (2:32) 兩首皆能一次跑通 end-to-end，且 libx264 比 libopenh264 壓縮率更好（Canon 從 21MB 降到 8.3MB，相同畫質）。

## 5.4 WebSocket Broadcaster 與 Comparator

Phase B 即時模式採用 WebSocket 把 runner 的 per-onset feedback 推送給 React PracticeScreen。

### 5.4.1 Broadcaster (`webui/realtime/broadcaster.py`)

採用 `asyncio` + `websockets` 在獨立 daemon thread 中起一個 WS server (default port 8766)。Runner 主執行緒呼叫 `broadcaster.publish(event_dict)` 是 thread-safe 的，內部 enqueue 到 asyncio.Queue 由 server loop 派發給所有連接的 client。

`--ws-linger N` 參數讓 server 在 runner 主流程結束後仍保留 N 秒，讓晚 connect 的 browser 能 backfill 歷史事件——對 demo 場景 (錄影/直播 demo 跑完才開 browser 確認) 很實用。

### 5.4.2 Comparator (`webui/realtime/comparator.py`)

對每個 MIDI onset 比較：

- **expected**：Logic Track (default ArLSTM) 預測的 (hand, finger)
- **got**：MediaPipe 從 webcam/replay 影片中 detect 的實際按鍵手指

採用「chord set tolerance」(`precompute_chord_finger_sets`) 處理和弦：對和弦中的每個 note，prediction 在和弦的整個指法集合內任一指都算對。這避免了「順序不同但物理對」的假陽性。

### 5.4.3 Clip Recorder (`webui/realtime/clip_recorder.py`)

rolling buffer 紀錄 user video frames，加 sliding-window error rate 偵測：當 window 內錯誤率超過 threshold (default 0.6) 就觸發 clip 錄製——pre-trigger N 秒 + post-trigger M 秒。錄製完用 ffmpeg `hstack` 把 user video 與 reference video (Stage B 的 `*_arlstm_kb.mp4`) 並排成 1280×360 對照影片，落地到 `clips/<song>_<timestamp>_err<rate>.mp4`。

這是 PracticeScreen `ClipsStrip` 元件的資料來源——學生看到自己彈錯的 clip 跟正確示範並排的 side-by-side。

## 5.5 GT 自動生成器 (`build_gt_rulebased.py`)

第四章描述了規則表本身，本節說明實作上幾個值得記錄的設計決策：

1. **stateful 單音規則**：stepwise continuity 規則需要知道**前一個 onset 的指法**，因此 walker 是有 state 的——每個 onset 處理完後更新 `prev_entry`。但前一個 onset 若是和弦，state 不 carry over（chord → single transition 無法做 stepwise inference）
2. **decision 欄位**：每個 GT entry 附 `decision` 字串（`'predictor-consensus'` / `'single-note-rule'` / `'chord-rule(interval=4)'` / `'arlstm-tiebreaker'` / `'user-curated'` / `'artifact-skip'`）。這讓 `--exclude-tiebreakers` mask 能精準濾除自我循環來源，也讓 audit log 可追溯每個 GT 決策來源
3. **seed mechanism**：`--seed canon_rh_gt.json` 允許用之前手寫的 GT 條目覆寫對應 onset，rule-based 不會碰那些條目。這保留人類專家最早的 12 onset 種子 GT 作為「黃金錨點」

## 5.6 復現性 (Reproducibility)

整個 pipeline 從零復現步驟：

```bash
# 1. Clone repos
git clone <this-repo>
cd PianoMotion10M
mkdir -p external && cd external
git clone --depth 1 https://github.com/PRamoneda/Automatic-Piano-Fingering.git
cd ..

# 2. Conda env
conda create -n pianomotion python=3.10
conda activate pianomotion
pip install -r requirements.txt  # torch, pretty_midi, mediapipe==0.10.14, ...

# 3. Generate GT
python build_gt_rulebased.py \
    --midi "input_songs/Canon....mid" \
    --hand right --out eval_data/canon_rh_rulebased_gt.json

# 4. Run four-way audit
python four_way_audit.py \
    --midi "input_songs/Canon....mid" \
    --gt eval_data/canon_rh_rulebased_gt.json \
    --fingertips results/canon_biomech_v4_fingertips.json \
    --exclude-tiebreakers

# 5. Stage B render
python simple_natural.py \
    --mp3 "input_songs/Canon....mp3" \
    --midi "input_songs/Canon....mid" \
    --fingering arlstm \
    --out_video results/canon_arlstm_kb.mp4

# 6. Stage C — open UI
python webui/serve.py 8765
python -m webui.realtime.runner \
    --video results/canon_biomech_v4_kb.mp4 \  # as fake user
    --midi "input_songs/Canon....mid" \
    --reference results/canon_arlstm_fingertips.json \
    --fast --no-preview --ws-port 8766 \
    --clip-record
# 開 http://localhost:8765/webui/
```

所有 random seed 不影響結果（Stage A inference 是 deterministic 的 argmax，Stage B 渲染 IK 也是 deterministic，唯一 stochastic 來源 biomech v4 內部 sampling 在 Stage A→B 整合後**只影響非按鍵動作 (transitional motion)**，不影響 fingering decision）。
