// PracticeScreen — Live practice w/ sheet music, AI gesture video, accuracy.
// Hero <video> plays the Stage B render (ArLSTM-prescribed fingering rendered
// through biomech v4's anatomy engine) with keyboard overlay.
// Real-time per-onset feedback arrives over a WebSocket from
//   `python -m webui.realtime.runner --ws-port 8766 ...`
// Events are buffered and fired as the <video>'s currentTime crosses each
// event's timestamp — works in both live mode (events arrive as user plays)
// and --fast replay mode (events flood in upfront and play back in sync with
// the video).

// Phase B WebSocket endpoint
const HK_WS_URL = (typeof window !== 'undefined' && window.HK_WS_URL) || 'ws://localhost:8766';
const FINGER_NUM = { thumb: 1, index: 2, middle: 3, ring: 4, pinky: 5 };

// ─── WebSocket feedback stream hook ──────────────────────────────
function useFeedbackStream(url) {
  const [connected, setConnected] = React.useState(false);
  const [meta, setMeta] = React.useState({ expected_count: 0, notes: [] });
  const [stats, setStats] = React.useState({ total: 0, correct: 0, wrong: 0, noHand: 0 });
  const [statusMap, setStatusMap] = React.useState({});
  const [recording, setRecording] = React.useState(null);  // null | {time, errorRate, windowSize}
  const [clips, setClips] = React.useState([]);  // [{path, time, errorRate, duration, ...}]
  const pendingRef = React.useRef([]);

  React.useEffect(() => {
    let stopped = false;
    let ws = null;
    let retry = null;

    const connect = () => {
      if (stopped) return;
      ws = new WebSocket(url);
      ws.onopen = () => setConnected(true);
      ws.onerror = () => {};
      ws.onclose = () => {
        setConnected(false);
        if (!stopped) retry = setTimeout(connect, 1500);
      };
      ws.onmessage = (ev) => {
        let d;
        try { d = JSON.parse(ev.data); } catch { return; }
        if (d.type === 'ready') {
          // New run — reset state
          pendingRef.current = [];
          setMeta({
            expected_count: d.expected_count,
            video: d.video,
            midi: d.midi,
            notes: Array.isArray(d.notes) ? d.notes : [],
          });
          setStats({ total: 0, correct: 0, wrong: 0, noHand: 0 });
          setStatusMap({});
          setRecording(null);
          setClips([]);
        } else if (d.type === 'clip_trigger') {
          setRecording({
            time: d.time,
            errorRate: d.error_rate,
            windowSize: d.window_size,
          });
        } else if (d.type === 'clip_done') {
          setRecording(null);
          setClips(cs => [...cs, {
            path: d.path,
            time: d.time,
            errorRate: d.error_rate,
            duration: d.duration,
            song: d.song,
            composed: d.composed,
          }]);
        } else if (d.type === 'onset') {
          pendingRef.current.push(d);
          // Keep sorted by time in case server sent out of order
          if (pendingRef.current.length > 1 &&
              pendingRef.current[pendingRef.current.length - 2].time > d.time) {
            pendingRef.current.sort((a, b) => a.time - b.time);
          }
        }
      };
    };
    connect();

    return () => {
      stopped = true;
      if (retry) clearTimeout(retry);
      if (ws) ws.close();
    };
  }, [url]);

  // Pop all pending events whose time has been reached. Returns the last one
  // (most recent) so the UI can flash a single overlay even if multiple
  // onsets fire in the same video frame.
  const popReady = React.useCallback((currentTime) => {
    const fired = [];
    while (pendingRef.current.length > 0 && pendingRef.current[0].time <= currentTime) {
      fired.push(pendingRef.current.shift());
    }
    if (fired.length === 0) return null;
    setStats(s => {
      let { total, correct, wrong, noHand } = s;
      for (const r of fired) {
        total += 1;
        if (r.correct) correct += 1;
        else if (!r.detected_finger) noHand += 1;
        else wrong += 1;
      }
      return { total, correct, wrong, noHand };
    });
    setStatusMap(m => {
      const next = { ...m };
      for (const r of fired) {
        if (r.i == null) continue;
        next[r.i] = r.correct
          ? 'correct'
          : (r.detected_finger ? 'wrong' : 'missed');
      }
      return next;
    });
    return fired[fired.length - 1];
  }, []);

  return { connected, meta, stats, statusMap, recording, clips, popReady };
}

// ─── Recording banner (visible while clip_recorder is active) ────
function RecordingBanner({ recording }) {
  if (!recording) return null;
  return (
    <div style={{
      position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
      padding: '6px 14px', borderRadius: 14,
      background: HK.red, color: HK.text,
      fontFamily: HK.fontMono, fontSize: 11, fontWeight: 700, letterSpacing: 1,
      display: 'flex', alignItems: 'center', gap: 8, zIndex: 5,
      boxShadow: `0 4px 18px ${HK.red}66`,
      animation: 'hkRecPulse 1.0s ease-in-out infinite',
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: 4, background: '#fff',
        animation: 'hkblink 0.8s infinite',
      }}/>
      錄製中 · 錯誤率 {Math.round(recording.errorRate * 100)}%
      <style>{`@keyframes hkRecPulse {
        0%, 100% { box-shadow: 0 4px 18px ${HK.red}66 }
        50%      { box-shadow: 0 4px 28px ${HK.red}cc }
      }`}</style>
    </div>
  );
}

// ─── Saved-clips strip ───────────────────────────────────────────
function ClipsStrip({ clips }) {
  if (!clips || clips.length === 0) return null;
  return (
    <div style={{
      padding: '4px 12px', borderRadius: 12,
      background: HK.surface2, border: `1px solid ${HK.hairline}`,
      display: 'flex', gap: 8, alignItems: 'center', overflowX: 'auto',
    }}>
      <div style={{
        fontFamily: HK.fontMono, fontSize: 9, color: HK.gold,
        letterSpacing: 1.3, fontWeight: 600, flexShrink: 0,
      }}>
        AI 教學片段 ({clips.length})
      </div>
      {clips.slice(-6).map((c, i) => {
        const fname = c.path.split('/').pop();
        const url = '../' + c.path;
        return (
          <a key={i} href={url} target="_blank" rel="noreferrer" style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '4px 8px', borderRadius: 8,
            background: `${HK.red}22`, border: `1px solid ${HK.red}66`,
            color: HK.text, fontFamily: HK.fontMono, fontSize: 9,
            textDecoration: 'none', flexShrink: 0,
          }}>
            <span style={{ color: HK.red }}>●</span>
            t={c.time.toFixed(1)}s · {Math.round(c.errorRate * 100)}%
          </a>
        );
      })}
    </div>
  );
}

// ─── Per-onset feedback overlay (flash + label) ──────────────────
function FeedbackOverlay({ event, generation }) {
  if (!event) return null;
  const isWrong = !event.correct && event.detected_finger;
  const isNoHand = !event.detected_finger;
  const color = event.correct ? HK.green : isWrong ? HK.red : HK.gold;
  const hand = event.expected_hand[0].toUpperCase();
  const expNum = FINGER_NUM[event.expected_finger];
  const gotNum = event.detected_finger ? FINGER_NUM[event.detected_finger] : null;

  let label;
  if (event.correct) label = `${hand}${expNum}`;
  else if (isWrong)  label = `${hand}${expNum} ≠ ${gotNum}`;
  else               label = `${hand}${expNum} · 未偵測`;

  // Wrist feedback v1 (2026-05-24): show small badge below the main
  // finger feedback when the wrist status is abnormal.
  const wristBadge = (() => {
    if (!event.wrist_status || event.wrist_status === 'good' ||
        event.wrist_status === 'unknown') return null;
    const isArched = event.wrist_status === 'arched';
    const text = isArched ? '手腕太高' : '手腕太低';
    const wColor = isArched ? HK.gold : HK.red;
    return (
      <div style={{
        marginTop: 6, padding: '4px 12px', borderRadius: 8,
        background: `${wColor}22`, border: `1px solid ${wColor}`,
        color: HK.text, fontFamily: HK.fontMono, fontSize: 11,
        letterSpacing: 0.5,
      }}>
        ⚠ {text} ({event.wrist_deviation_px > 0 ? '+' : ''}{event.wrist_deviation_px}px)
      </div>
    );
  })();

  return (
    <div key={generation} style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
      paddingBottom: '14%',
    }}>
      {isWrong && (
        <div style={{
          position: 'absolute', inset: 0,
          background: `radial-gradient(circle at 50% 70%, ${HK.red}55 0%, transparent 65%)`,
          animation: 'hkFbFlash 750ms ease-out forwards',
        }}/>
      )}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        animation: 'hkFbPop 1200ms ease-out forwards',
      }}>
        <div style={{
          padding: '10px 22px',
          borderRadius: 14,
          background: `${color}26`,
          border: `2px solid ${color}`,
          color: HK.text,
          fontFamily: HK.fontMono, fontSize: 22, fontWeight: 700,
          letterSpacing: 1,
          backdropFilter: 'blur(8px)',
          boxShadow: `0 0 30px ${color}66`,
        }}>{label}</div>
        {wristBadge}
      </div>
      <style>{`
        @keyframes hkFbFlash { from {opacity: 1} to {opacity: 0} }
        @keyframes hkFbPop {
          0%   { transform: translateY(20px) scale(0.7); opacity: 0 }
          15%  { transform: translateY(0)    scale(1.08); opacity: 1 }
          75%  { transform: translateY(0)    scale(1);    opacity: 1 }
          100% { transform: translateY(-6px) scale(0.96); opacity: 0 }
        }
      `}</style>
    </div>
  );
}

// ─── Tiny WS connection badge ────────────────────────────────────
function ConnectionBadge({ connected, expectedCount }) {
  const color = connected ? HK.green : HK.textMuted;
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 8px', borderRadius: 8,
      background: HK.surface2, border: `1px solid ${HK.hairline}`,
      fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted, letterSpacing: 0.8,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 3,
        background: color,
        animation: connected ? 'hkblink 1.8s infinite' : 'none',
      }}/>
      {connected
        ? <span>AI · {expectedCount} 個 onset</span>
        : <span>等候 runner</span>}
    </div>
  );
}

// ─── Procedural sheet music (kept as a future-feature placeholder) ──
const MEASURE_1 = [
  { p: 3, beat: 0,   dur: 0.5, stem: 'down', state: 'past' },
  { p: 4, beat: 0.5, dur: 0.5, stem: 'down', state: 'past' },
  { p: 3, beat: 1,   dur: 0.5, stem: 'down', state: 'past' },
  { p: 4, beat: 1.5, dur: 0.5, stem: 'down', state: 'past' },
  { p: 3, beat: 2,   dur: 0.5, stem: 'down', state: 'wrong' },
  { p: 6, beat: 2.5, dur: 0.5, stem: 'down', state: 'current' },
  { p: 5, beat: 3,   dur: 0.5, stem: 'down', state: 'upcoming' },
  { p: 4, beat: 3.5, dur: 0.5, stem: 'down', state: 'upcoming' },
];
const MEASURE_2 = [
  { p: 3, beat: 0,   dur: 1,   stem: 'down', state: 'upcoming' },
  { p: 5, beat: 1,   dur: 0.5, stem: 'down', state: 'upcoming' },
  { p: 4, beat: 1.5, dur: 0.5, stem: 'down', state: 'upcoming' },
  { p: 3, beat: 2,   dur: 0.5, stem: 'down', state: 'upcoming' },
  { p: 2, beat: 2.5, dur: 0.5, stem: 'down', state: 'upcoming' },
  { p: 3, beat: 3,   dur: 1,   stem: 'down', state: 'upcoming' },
];

function Staff({ measures, width = 340, height = 110 }) {
  const measureWidth = (width - 50) / measures.length;
  const stateColors = {
    past:     HK.textMuted,
    current:  HK.gold,
    upcoming: HK.text,
    wrong:    HK.red,
    correct:  HK.green,
  };
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" style={{ display: 'block', overflow: 'visible' }}>
      {[0, 1, 2, 3, 4].map(i => (
        <line key={i} x1="0" x2={width} y1={28 + i * 12} y2={28 + i * 12}
          stroke="rgba(234,242,251,0.22)" strokeWidth="1"/>
      ))}
      <g transform="translate(2, 14)" fill="rgba(234,242,251,0.85)">
        <path d="M10 8c0-3 2-5 4-5s4 2 4 5-1 6-4 10c-2 3-4 6-4 10 0 3 2 5 5 5s5-2 5-5c0-2-1-4-3-4-1 0-2 1-2 2s1 1 1 2"
          fill="none" stroke="rgba(234,242,251,0.85)" strokeWidth="1.4" strokeLinecap="round"/>
        <circle cx="14" cy="36" r="2.5"/>
      </g>
      <text x="30" y="42" fill="rgba(234,242,251,0.85)" fontFamily="serif" fontSize="14" fontWeight="700">3</text>
      <text x="30" y="56" fill="rgba(234,242,251,0.85)" fontFamily="serif" fontSize="14" fontWeight="700">8</text>
      {measures.map((measure, mIdx) => {
        const x0 = 46 + mIdx * measureWidth;
        return (
          <g key={mIdx}>
            <line x1={x0} x2={x0} y1="28" y2="76" stroke="rgba(234,242,251,0.35)" strokeWidth="0.8"/>
            <text x={x0 + 2} y="22" fill="rgba(234,242,251,0.4)" fontFamily="ui-monospace, monospace" fontSize="9" fontWeight="500">m.{mIdx + 1}</text>
            {measure.map((n, i) => {
              const x = x0 + 12 + n.beat * (measureWidth - 18) / 4;
              const y = 24 + n.p * 6;
              const c = stateColors[n.state];
              const isHollow = n.dur >= 2;
              return (
                <g key={i}>
                  {n.state === 'current' && (
                    <circle cx={x} cy={y} r="9" fill="none" stroke={c} strokeWidth="1" opacity="0.5">
                      <animate attributeName="r" values="7;11;7" dur="1.3s" repeatCount="indefinite"/>
                      <animate attributeName="opacity" values="0.7;0.1;0.7" dur="1.3s" repeatCount="indefinite"/>
                    </circle>
                  )}
                  <ellipse cx={x} cy={y} rx="4.4" ry="3.2" transform={`rotate(-22 ${x} ${y})`}
                    fill={isHollow ? 'none' : c} stroke={c} strokeWidth={isHollow ? 1.6 : 0}/>
                  {n.dur < 4 && (
                    <line
                      x1={n.stem === 'down' ? x - 4 : x + 4}
                      x2={n.stem === 'down' ? x - 4 : x + 4}
                      y1={y}
                      y2={n.stem === 'down' ? y + 22 : y - 22}
                      stroke={c} strokeWidth="1.4"/>
                  )}
                  {n.dur === 0.5 && (
                    <path
                      d={n.stem === 'down'
                        ? `M ${x - 4} ${y + 22} q 4 -2 5 -8`
                        : `M ${x + 4} ${y - 22} q 4 2 5 8`}
                      stroke={c} strokeWidth="1.4" fill="none"/>
                  )}
                </g>
              );
            })}
          </g>
        );
      })}
      <line x1={width - 2} x2={width - 2} y1="28" y2="76" stroke="rgba(234,242,251,0.35)" strokeWidth="1.4"/>
    </svg>
  );
}

// ─── Stage B render (ArLSTM × biomech v4) as the practice hero ──
function GestureVideo({ src, playing, onTimeUpdate, onDuration, audioSrc, children }) {
  const videoRef = React.useRef(null);
  const audioRef = React.useRef(null);

  // Keep play/pause in sync with parent state, and lock the audio track to it.
  React.useEffect(() => {
    const v = videoRef.current;
    const a = audioRef.current;
    if (!v) return;
    if (playing) {
      v.play().catch(err => console.warn('[video.play]', err));
      if (a) a.play().catch(() => {});
    } else {
      v.pause();
      if (a) a.pause();
    }
  }, [playing]);

  return (
    <div style={{
      position: 'relative',
      borderRadius: 16, overflow: 'hidden',
      background: '#000',
      border: `1px solid ${HK.hairlineStrong}`,
      boxShadow: '0 8px 26px rgba(0,0,0,0.5)',
      aspectRatio: '16 / 9',
    }}>
      <video
        ref={videoRef}
        src={src}
        playsInline
        muted
        loop={false}
        onTimeUpdate={(e) => onTimeUpdate && onTimeUpdate(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => onDuration && onDuration(e.currentTarget.duration)}
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
      />
      {audioSrc && (
        <audio ref={audioRef} src={audioSrc} preload="auto"/>
      )}
      {/* Overlay HUD: REC + confidence */}
      <div style={{
        position: 'absolute', top: 8, left: 10,
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '4px 8px', borderRadius: 6,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(6px)',
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: 3, background: HK.red,
          animation: 'hkblink 1.2s infinite',
        }}/>
        <span style={{ fontFamily: HK.fontMono, fontSize: 9, fontWeight: 600, color: HK.text, letterSpacing: 0.7 }}>
          AI · ArLSTM × biomech v4
        </span>
      </div>
      <div style={{
        position: 'absolute', top: 8, right: 10,
        padding: '4px 8px', borderRadius: 6,
        background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        <span style={{ color: HK.green, fontFamily: HK.fontMono, fontSize: 8 }}>●</span>
        <span style={{ fontFamily: HK.fontMono, fontSize: 9, fontWeight: 600, color: HK.text }}>98%</span>
        <span style={{ fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted }}>追蹤中</span>
      </div>
      <style>{`@keyframes hkblink { 0%,100% { opacity: 1 } 50% { opacity: 0.25 } }`}</style>
      {children}
    </div>
  );
}

// ─── Big accuracy score ring ───────────────────────────────────
function ScoreRing({ value = 92, label = 'Accuracy', size = 76, color = HK.blue }) {
  const r = size / 2 - 5;
  const c = 2 * Math.PI * r;
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ display: 'block' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={HK.surface3} strokeWidth="4"/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ transition: 'stroke-dashoffset 0.4s' }}/>
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ fontFamily: HK.fontMono, fontSize: 20, fontWeight: 700, color: HK.text, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
        <div style={{ fontFamily: HK.fontMono, fontSize: 8, color: HK.textMuted, letterSpacing: 1, marginTop: 2 }}>{label.toUpperCase()}</div>
      </div>
    </div>
  );
}

function MetricChip({ icon, label, value, color = HK.text }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '6px 10px', borderRadius: 10,
      background: HK.surface2, border: `1px solid ${HK.hairline}`,
    }}>
      <div style={{ color }}><Icon name={icon} size={12} color={color}/></div>
      <span style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textMuted }}>{label}</span>
      <span style={{ fontFamily: HK.fontMono, fontSize: 12, fontWeight: 600, color: HK.text, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

function PracticeScreen({ song, onEnd, onBack }) {
  const [playing, setPlaying] = React.useState(true);
  const [elapsed, setElapsed] = React.useState(0);
  const [duration, setDuration] = React.useState(song?.dur ? parseDur(song.dur) : 205);

  // Real-time feedback from the Python runner (WebSocket on 8766)
  const { connected, meta, stats, statusMap, recording, clips, popReady } = useFeedbackStream(HK_WS_URL);
  const [currentEvent, setCurrentEvent] = React.useState(null);
  const [eventGen, setEventGen] = React.useState(0);

  // Shared time reference for the PianoRoll's requestAnimationFrame loop
  // (so the canvas doesn't depend on React render cycles for smooth scrolling).
  const currentTimeRef = React.useRef(0);

  const handleTimeUpdate = React.useCallback((t) => {
    currentTimeRef.current = t;
    setElapsed(t);
    const ev = popReady(t);
    if (ev) {
      setCurrentEvent(ev);
      setEventGen(g => g + 1);
    }
  }, [popReady]);

  // Real accuracy from received events; fall back to placeholder when nothing yet.
  const accuracy = stats.total > 0
    ? Math.round(100 * stats.correct / stats.total)
    : (connected ? 0 : 92);
  const streakText = stats.total === 0
    ? '—'
    : String(stats.correct);

  const progress = duration > 0 ? Math.min(1, elapsed / duration) : 0;
  const mins = Math.floor(elapsed / 60);
  const secs = String(Math.floor(elapsed % 60)).padStart(2, '0');
  const totalMins = Math.floor(duration / 60);
  const totalSecs = String(Math.floor(duration % 60)).padStart(2, '0');

  const videoSrc = song?.videoUrl || '../results/canon_arlstm_kb.mp4';
  const audioSrc = song?.audioUrl;

  return (
    <div style={{
      position: 'absolute', inset: 0, background: HK.bg,
      paddingTop: 54, paddingBottom: 28, overflow: 'auto',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Top bar */}
      <div style={{ padding: '6px 16px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button onClick={onBack} style={btnGlass3}><Icon name="back" size={20} color={HK.text}/></button>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: HK.fontMono, fontSize: 9, color: HK.gold, letterSpacing: 1.5, fontWeight: 600 }}>正在練習</div>
          <div style={{ fontFamily: HK.fontDisplay, fontSize: 17, color: HK.text, marginTop: 1 }}>{song?.title || '給愛麗絲'}</div>
        </div>
        <button style={btnGlass3}><Icon name="more" size={20} color={HK.text}/></button>
      </div>

      {/* Accuracy summary */}
      <div style={{ padding: '14px 20px 10px' }}>
        <div style={{
          padding: 14, borderRadius: 20,
          background: `linear-gradient(135deg, ${HK.blue}1a, ${HK.surface2} 70%)`,
          border: `1px solid ${HK.blue}25`,
          display: 'flex', alignItems: 'center', gap: 12,
          position: 'relative', overflow: 'hidden',
        }}>
          <ScoreRing value={Math.round(accuracy)} label="準確率" color={HK.blue}/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted, letterSpacing: 1.4, fontWeight: 600,
            }}>
              <span>AI 教練評估</span>
              <ConnectionBadge connected={connected} expectedCount={meta.expected_count}/>
            </div>
            <div style={{ fontFamily: HK.fontDisplay, fontSize: 19, color: HK.text, marginTop: 2, letterSpacing: -0.3, lineHeight: 1.15 }}>
              {stats.total === 0
                ? <>等待 <span style={{ color: HK.gold, fontStyle: 'italic' }}>第一個音</span></>
                : (accuracy >= 80
                    ? <>你正在 <span style={{ color: HK.green, fontStyle: 'italic' }}>穩定演奏中</span></>
                    : (accuracy >= 50
                        ? <>跟上 <span style={{ color: HK.gold, fontStyle: 'italic' }}>大方向</span> 中</>
                        : <><span style={{ color: HK.red, fontStyle: 'italic' }}>指法</span> 需要注意</>))}
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 7, flexWrap: 'wrap' }}>
              <MetricChip icon="bolt" label="正確" value={streakText}/>
              <MetricChip icon="close" label="錯誤" value={String(stats.wrong)} color={stats.wrong > 0 ? HK.red : HK.text}/>
              <MetricChip icon="clock" label="" value={`${mins}:${secs}`}/>
            </div>
          </div>
        </div>
      </div>

      {/* Hero video — Stage B (ArLSTM × biomech v4) + keyboard overlay */}
      <div style={{ padding: '0 20px 12px' }}>
        <GestureVideo
          src={videoSrc}
          audioSrc={audioSrc}
          playing={playing}
          onTimeUpdate={handleTimeUpdate}
          onDuration={setDuration}
        >
          <FeedbackOverlay event={currentEvent} generation={eventGen}/>
          <RecordingBanner recording={recording}/>
        </GestureVideo>
      </div>

      {clips.length > 0 && (
        <div style={{ padding: '0 20px 10px' }}>
          <ClipsStrip clips={clips}/>
        </div>
      )}

      {/* Falling-keys piano roll — synced with video time, driven by WS notes */}
      <div style={{ padding: '0 20px 12px' }}>
        {meta.notes && meta.notes.length > 0
          ? <PianoRoll
              notes={meta.notes}
              statusMap={statusMap}
              currentTimeRef={currentTimeRef}
              height={220}
              keyboardHeight={50}
              lookAhead={4.0}
            />
          : <div style={{
              height: 220, borderRadius: 12,
              border: `1px dashed ${HK.hairlineStrong}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted, letterSpacing: 1.2,
            }}>
              {connected ? '等候 notes payload' : '等候 runner 連線'}
            </div>}
      </div>

      {/* Sheet music card — OSMD if scoreUrl available, else legacy Staff placeholder */}
      <div style={{ padding: '0 20px 12px' }}>
        <div style={{
          padding: '12px 12px 6px', borderRadius: 16,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '0 8px 4px',
            fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted, letterSpacing: 1.3, fontWeight: 600,
          }}>
            <span>{song?.scoreUrl ? '樂譜 · MusicXML (OSMD)' : '樂譜 · 概念示意'}</span>
            <span style={{ color: HK.gold }}>♩ = 76</span>
          </div>
          <OSMDScore
            scoreUrl={song?.scoreUrl}
            highlightTime={elapsed}
            height={180}
            fallback={<Staff measures={[MEASURE_1, MEASURE_2]}/>}
          />
        </div>
      </div>

      {/* Transport */}
      <div style={{ flex: 1 }}/>
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
          <button style={{ ...transportBtn, width: 40, height: 40 }}>
            <Icon name="retry" size={16} color={HK.text}/>
          </button>
          <button onClick={() => setPlaying(p => !p)} style={{
            width: 56, height: 56, borderRadius: 28,
            background: HK.blue, color: HK.surface,
            border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 8px 22px ${HK.blue}50, 0 0 0 1px ${HK.blue}30`,
          }}>
            <Icon name={playing ? 'pause' : 'play'} size={22} color={HK.surface}/>
          </button>
          <button onClick={onEnd} style={{ ...transportBtn, width: 40, height: 40 }}>
            <Icon name="close" size={16} color={HK.red}/>
          </button>
        </div>
        <div style={{ width: '100%', marginTop: 12 }}>
          <div style={{ height: 4, background: HK.surface3, borderRadius: 2, position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute', left: 0, top: 0, bottom: 0,
              width: `${progress * 100}%`,
              background: `linear-gradient(90deg, ${HK.blue}, ${HK.gold})`,
              borderRadius: 2,
            }}/>
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            marginTop: 4, fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted, fontVariantNumeric: 'tabular-nums',
          }}>
            <span>{mins}:{secs}</span>
            <span>{totalMins}:{totalSecs}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function parseDur(s) {
  const m = /^(\d+):(\d+)$/.exec(String(s).trim());
  return m ? +m[1] * 60 + +m[2] : 0;
}

const btnGlass3 = {
  width: 38, height: 38, borderRadius: 19,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer',
};
const transportBtn = {
  borderRadius: 20, background: HK.surface2, border: `1px solid ${HK.hairline}`,
  cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};

Object.assign(window, { PracticeScreen });
