# HandKeys AI — Jetson NX 部署包

把整套系统跑在 **Jetson Xavier/Orin NX** 上：开机自启，平板/手机连上去就能练琴 + 实时纠正指法。

> ⚠️ **诚实声明**：本部署包是在**没有实体 Jetson 的情况下**写的（开发机无板）。
> systemd / 脚本 / 架构都基于已验证的软件行为，但 **Jetson 特有的部分（JetPack 上
> 装 mediapipe、ARM 上的 onnxruntime、USB-MIDI/摄像头权限）必须由你在板子上实测**。
> 每个未在硬件上验证的步骤都标了 `⚠ 板上验证`。

---

## 1. 架构：NX 上需要什么、不需要什么

关键事实（已验证）：**渲染（biomech 手部视频）是在开发机离线做好的**，NX **只负责两件轻活**：

| 角色 | 跑什么 | 依赖 | 要 GPU/torch 吗 |
|---|---|---|---|
| **开发机（你现在这台）** | 离线渲染 biomech 视频 + 贴准确指法标签 | torch + MANO + CUDA | 要 |
| **Jetson NX** | ① 服务 UI + 预渲染视频　② 实时摄像头判官 | MediaPipe + numpy + pretty_midi + rtmidi + websockets + **pianoplayer** | **不要** ✅ |

实时判官用 `--fingering-source pianoplayer` 时 **完全不碰 torch**（torch 只在 arlstm 分支懒加载）。
所以 NX 上**不用装 PyTorch/CUDA**——这是这套能跑在边缘设备上的根本原因。

```
   [66键电钢琴] --USB-MIDI--> ┐
   [USB 摄像头]  --USB------> ├─ Jetson NX ──Wi-Fi──> [手机/平板浏览器]
                              │   serve.py  :8765  (UI + 视频)
                              │   runner.py :8766  (WebSocket 实时反馈)
                              ┘
```

---

## 2. 硬件清单

- [ ] Jetson Xavier NX 或 Orin NX（JetPack 5.x+，已刷机）
- [ ] 66 键电钢琴，USB-MIDI 连 NX
- [ ] USB 摄像头（俯拍键盘/手）
- [ ] 手机或平板，和 NX 同一 Wi-Fi
- [ ] （可选）小屏幕/HDMI 给 NX 首次配网

---

## 3. 软件 bring-up（在 NX 上）

```bash
# 0. 拷贝项目到 NX (含预渲染的 results/*.mp4)
#    scp -r PianoMotion10M jetson@<nx-ip>:~/

# 1. 一键装依赖 (⚠ 板上验证: mediapipe/onnxruntime 的 ARM 轮子)
cd ~/PianoMotion10M/deploy
bash setup_nx.sh

# 2. 冒烟测试 (replay 模式, 不插硬件就能验证软件链路)
cd ~/PianoMotion10M
python -m webui.realtime.runner \
    --video results/canon_arlstm_kb.mp4 \
    --ref-midi "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    --reference results/canon_arlstm_fingertips.json \
    --fingering-source pianoplayer --no-preview --ws-port 8766 --max-onsets 20 &
python -m webui.realtime.ws_smoketest --port 8766 --max-msgs 30   # 应能收到 JSON 反馈

# 3. 启服务 (UI)
python webui/serve.py 8765        # 然后手机浏览器开 http://<nx-ip>:8765/webui/
```

UI 的 WebSocket 已改成**自动连回服务它的那台主机**（`window.location.hostname`），
所以手机从 `http://<nx-ip>:8765/webui/` 打开，反馈会自动连 `ws://<nx-ip>:8766`，无需手填。

---

## 4. 实时（插上硬件后）

先找到电钢琴的 MIDI 端口名：
```bash
python -c "import rtmidi; m=rtmidi.MidiIn(); print(m.get_ports())"
# 例如 ['Piano Keyboard:0']
```

启动实时判官（headless，自启见 §5）：
```bash
python -m webui.realtime.runner \
    --video 0 \                                  # 摄像头 0; ⚠ 板上确认 index
    --midi "Piano Keyboard:0" \                  # 上一步查到的端口名
    --ref-midi "input_songs/<song>.mid" \
    --reference results/<song>_arlstm_fingertips.json \
    --fingering-source pianoplayer \
    --no-preview --ws-port 8766 --mirror         # --mirror 看摄像头是否镜像
```

---

## 5. 开机自启（systemd）

```bash
sudo cp deploy/handkeys-serve.service   /etc/systemd/system/
sudo cp deploy/handkeys-runner.service  /etc/systemd/system/
# 按你的用户名/路径/MIDI端口/曲目改两个 .service 里的占位符
sudo systemctl daemon-reload
sudo systemctl enable --now handkeys-serve handkeys-runner
journalctl -u handkeys-runner -f        # 看实时日志
```

---

## 6. 排错 / ⚠ 板上必验

| 症状 | 多半原因 |
|---|---|
| `pip install mediapipe` 失败 | ⚠ Jetson 要装 ARM 专用轮子（NVIDIA forum 有 `mediapipe` aarch64 包）；或退用 §7 的 ONNX 路 |
| 摄像头打不开 | `--video` index 不对 / 没 v4l2 权限（`sudo usermod -aG video $USER`） |
| MIDI 收不到 | 端口名拼错；`aconnect -l` 看 ALSA MIDI |
| 手机连不上 WS | NX 防火墙挡了 8766；`sudo ufw allow 8765,8766/tcp` |
| 判官很卡 | 加 `--fast`；NX 上 MediaPipe 用 GPU delegate（⚠ 板上调） |

---

## 7. ONNX 指法路（torch-free，已接线 ✅）

`external/piano-fingering-model/` 的 ONNX 指法模型（FingeringTransformer）已接进
Logic Track。实时判官加 `--fingering-source onnx` 即走 onnxruntime 推理，**完全不碰 torch**：

```bash
python -m webui.realtime.runner ... --fingering-source onnx ...
# 或单测: python -m webui.realtime.fingering_engine "<song>.mid" --source onnx
```

质量介于 pianoplayer 与 ArLSTM 之间（Canon RH：**Hard 0.48 / Soft 0.66**，优于 pianoplayer
的 0.39 / 0.58，略低于 ArLSTM 0.59 / 0.74），但**免 torch** —— 边缘设备上比 pianoplayer 更准、
比 ArLSTM 更轻。依赖 `onnxruntime`（aarch64 有 ARM 轮子，已在 `requirements-nx.txt`）。
实现见 `onnx_fingering.py`（token 构造与 `external/.../python/inference.py` 一致，仅前向换成 ort）。

---

## 8. 这份部署包的状态

- ✅ **已验证（开发机软件层面）**：torch-free 判官、headless runner、WS 自动连本机、serve.py。
- ⚠ **未验证（需你的板子）**：JetPack 上装依赖、ARM onnxruntime、USB-MIDI/摄像头实采、systemd 在 NX 上自启、端到端实时延迟。

把 ⚠ 项在板子上跑通，这套就是完整的边缘部署。任一步卡住，把日志贴回来我接着修。
