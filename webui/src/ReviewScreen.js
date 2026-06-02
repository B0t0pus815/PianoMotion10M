// ReviewScreen — Post-session mistakes review with scores, mistakes list, and gesture clips.

const MISTAKES = [
  {
    id: 'e1', measure: 7, beat: 2,
    type: '手指錯誤', severity: 'high',
    detail: '使用了中指 — 樂譜要求食指',
    expected: '食指', actual: '中指',
    handKind: 'right',
    skeleton: 'wrong-finger',
  },
  {
    id: 'e2', measure: 12, beat: 3.5,
    type: '拍點迫後', severity: 'medium',
    detail: '音符落鍵比拍點晚 180ms',
    expected: '0ms', actual: '+180ms',
    handKind: 'left',
    skeleton: 'timing',
  },
  {
    id: 'e3', measure: 18, beat: 1,
    type: '手腕緊張', severity: 'low',
    detail: '琴鍵綠期間手腕角度 > 22°',
    expected: '< 10°', actual: '22°',
    handKind: 'right',
    skeleton: 'posture',
  },
  {
    id: 'e4', measure: 24, beat: 2.5,
    type: '漏彈', severity: 'high',
    detail: 'C5 未被識別',
    expected: 'C5', actual: '—',
    handKind: 'right',
    skeleton: 'wrong-finger',
  },
];

const SEVERITY = {
  high:   { c: HK.red,    label: '高' },
  medium: { c: HK.gold,   label: '中' },
  low:    { c: HK.blue,   label: '低' },
};

// Hand skeleton variant — small clip with overlay highlighting a problem joint.
function HandClip({ variant, size = 80 }) {
  // base joints
  const wrist = [40, 70];
  const fingers = [
    [[24, 62], [18, 50], [16, 40], [16, 32]],   // thumb
    [[32, 50], [32, 36], [32, 26], [32, 18]],   // index
    [[40, 48], [40, 32], [40, 22], [40, 14]],   // middle
    [[48, 50], [48, 36], [48, 26], [48, 18]],   // ring
    [[56, 54], [58, 42], [60, 32], [62, 24]],   // pinky
  ];

  // highlight rules per variant
  const flag = (fi, ji) => {
    if (variant === 'wrong-finger') return fi === 2 && ji === 3;
    if (variant === 'timing') return fi === 1 && ji === 3;
    if (variant === 'posture') return ji === 0;
    return false;
  };
  const flagged = HK.red;

  return (
    <div style={{
      width: size, height: size,
      background: '#000', borderRadius: 12, overflow: 'hidden',
      position: 'relative', border: `1px solid ${HK.hairlineStrong}`,
      flexShrink: 0,
    }}>
      {/* faux keyboard background */}
      <svg viewBox="0 0 80 80" width="100%" height="100%" style={{ display: 'block' }}>
        <defs>
          <linearGradient id={`hc-bg-${variant}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#172238"/>
            <stop offset="1" stopColor="#060912"/>
          </linearGradient>
        </defs>
        <rect width="80" height="80" fill={`url(#hc-bg-${variant})`}/>
        {/* keys */}
        {Array.from({ length: 7 }).map((_, i) => (
          <rect key={i} x={i * 11} y="58" width="10" height="22" rx="1.2"
            fill="#aab0c0" opacity="0.55" stroke="#1a1f30" strokeWidth="0.4"/>
        ))}
        {[0, 1, 3, 4, 5].map(i => (
          <rect key={i} x={i * 11 + 7.5} y="58" width="6" height="12" rx="0.8"
            fill="#0a0d18" opacity="0.95"/>
        ))}
        {/* hand */}
        {/* connections */}
        {fingers.map((f, fi) => (
          <g key={fi}>
            <line x1={wrist[0]} y1={wrist[1]} x2={f[0][0]} y2={f[0][1]} stroke={HK.blue} strokeWidth="1.1" opacity="0.8"/>
            <line x1={f[0][0]} y1={f[0][1]} x2={f[1][0]} y2={f[1][1]} stroke={HK.blue} strokeWidth="1.1" opacity="0.8"/>
            <line x1={f[1][0]} y1={f[1][1]} x2={f[2][0]} y2={f[2][1]} stroke={HK.blue} strokeWidth="1.1" opacity="0.8"/>
            <line x1={f[2][0]} y1={f[2][1]} x2={f[3][0]} y2={f[3][1]} stroke={HK.blue} strokeWidth="1.1" opacity="0.8"/>
          </g>
        ))}
        {/* palm */}
        {fingers.slice(0, -1).map((f, fi) => (
          <line key={fi}
            x1={f[0][0]} y1={f[0][1]}
            x2={fingers[fi + 1][0][0]} y2={fingers[fi + 1][0][1]}
            stroke={HK.blue} strokeWidth="0.8" opacity="0.4"/>
        ))}
        {/* joints */}
        <circle cx={wrist[0]} cy={wrist[1]} r="2.2"
          fill={variant === 'posture' ? flagged : HK.gold}/>
        {fingers.map((f, fi) =>
          f.map(([x, y], ji) => {
            const isFlag = flag(fi, ji);
            return (
              <g key={fi + '-' + ji}>
                {isFlag && (
                  <circle cx={x} cy={y} r="6" fill="none" stroke={flagged} strokeWidth="1" opacity="0.6">
                    <animate attributeName="r" values="4;8;4" dur="1.4s" repeatCount="indefinite"/>
                    <animate attributeName="opacity" values="0.8;0.1;0.8" dur="1.4s" repeatCount="indefinite"/>
                  </circle>
                )}
                <circle cx={x} cy={y} r={ji === 3 ? 1.9 : 1.4}
                  fill={isFlag ? flagged : (ji === 3 ? HK.gold : HK.blue)}
                  stroke="#0A1622" strokeWidth="0.3"/>
              </g>
            );
          })
        )}
        {/* badge */}
        <g>
          <rect x="3" y="3" width="34" height="11" rx="3" fill="rgba(0,0,0,0.7)"/>
          <circle cx="9" cy="8.5" r="1.7" fill={HK.gold}/>
          <text x="14" y="11" fill={HK.text} fontFamily="ui-monospace, monospace" fontSize="6" fontWeight="600">示範</text>
        </g>
      </svg>
      {/* play affordance */}
      <div style={{
        position: 'absolute', bottom: 6, right: 6,
        width: 22, height: 22, borderRadius: 11,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: `1px solid ${HK.hairlineStrong}`,
      }}>
        <Icon name="play" size={10} color={HK.text}/>
      </div>
    </div>
  );
}

function MistakeRow({ mistake, expanded, onClick }) {
  const sev = SEVERITY[mistake.severity];
  return (
    <div onClick={onClick} style={{
      borderRadius: 16, overflow: 'hidden', cursor: 'pointer',
      background: expanded ? HK.surface2 : HK.surface2,
      border: `1px solid ${expanded ? sev.c + '40' : HK.hairline}`,
      transition: 'border 0.18s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 12 }}>
        {/* Measure marker */}
        <div style={{
          width: 44, flexShrink: 0,
          fontFamily: HK.fontMono, textAlign: 'center',
          padding: '6px 0', borderRadius: 10,
          background: sev.c + '14', color: sev.c,
        }}>
          <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: 1, opacity: 0.7 }}>小節</div>
          <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{mistake.measure}</div>
        </div>
        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: HK.text }}>{mistake.type}</span>
            <span style={{
              padding: '1px 6px', borderRadius: 4,
              background: sev.c + '20', color: sev.c,
              fontFamily: HK.fontMono, fontSize: 9, fontWeight: 700, letterSpacing: 0.5,
            }}>{sev.label}</span>
          </div>
          <div style={{
            fontSize: 12, color: HK.textDim, marginTop: 3,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{mistake.detail}</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 6, fontFamily: HK.fontMono, fontSize: 10 }}>
            <span style={{ color: HK.textMuted }}>你</span>
            <span style={{ color: HK.red, fontWeight: 600 }}>{mistake.actual}</span>
            <span style={{ color: HK.textMuted }}>·</span>
            <span style={{ color: HK.textMuted }}>正確</span>
            <span style={{ color: HK.green, fontWeight: 600 }}>{mistake.expected}</span>
          </div>
        </div>
        <div style={{ color: HK.textMuted, transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.18s' }}>
          <Icon name="chevD" size={18}/>
        </div>
      </div>

      {/* Expanded gesture clip */}
      {expanded && (
        <div style={{
          padding: 12, paddingTop: 0,
          display: 'flex', gap: 12, alignItems: 'flex-start',
        }}>
          <HandClip variant={mistake.skeleton} size={92}/>
          <div style={{ flex: 1, padding: '4px 0' }}>
            <div style={{ fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted, letterSpacing: 1.3, fontWeight: 600 }}>
              正確手勢示範
            </div>
            <div style={{ fontSize: 13, color: HK.text, marginTop: 4, lineHeight: 1.4 }}>
              {mistake.skeleton === 'wrong-finger' && '拇指彎入 F 鍵，保持食指在 G 鍵上準備。'}
              {mistake.skeleton === 'timing' && '提前預測拍點—左手保持在上八分音符位置。'}
              {mistake.skeleton === 'posture' && '放鬆手腕，讓手臂順勢在鍵面上滑動。'}
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <button style={smallBtn}>
                <Icon name="play" size={10} color={HK.text}/>
                播放示範
              </button>
              <button style={smallBtn}>
                <Icon name="retry" size={10} color={HK.text}/>
                重複練習
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreCard({ icon, label, value, suffix = '%', color = HK.blue, trend }) {
  return (
    <div style={{
      flex: 1, padding: 14, borderRadius: 18,
      background: HK.surface2, border: `1px solid ${HK.hairline}`,
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ color, marginBottom: 8 }}><Icon name={icon} size={18} color={color}/></div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
        <span style={{ fontFamily: HK.fontMono, fontSize: 26, fontWeight: 700, color: HK.text, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        <span style={{ fontFamily: HK.fontMono, fontSize: 12, color: HK.textMuted, fontWeight: 600 }}>{suffix}</span>
      </div>
      <div style={{
        fontFamily: HK.fontUI, fontSize: 11, color: HK.textDim,
        marginTop: 4, letterSpacing: 0.2,
      }}>{label}</div>
      {trend != null && (
        <div style={{
          position: 'absolute', top: 14, right: 14,
          fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600,
          color: trend > 0 ? HK.green : HK.red,
          display: 'flex', alignItems: 'center', gap: 2,
        }}>
          {trend > 0 ? '▲' : '▼'} {Math.abs(trend)}
        </div>
      )}
    </div>
  );
}

function ReviewScreen({ song, onRetry, onDone }) {
  const [openId, setOpenId] = React.useState('e1');
  const overall = 87;

  return (
    <div style={{
      position: 'absolute', inset: 0, paddingTop: 54, paddingBottom: 100,
      overflow: 'auto', background: HK.bg,
    }}>
      {/* Header */}
      <div style={{ padding: '6px 16px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button style={btnGlass4}><Icon name="close" size={20} color={HK.text}/></button>
        <div style={{ fontFamily: HK.fontMono, fontSize: 10, color: HK.gold, letterSpacing: 1.5, fontWeight: 600 }}>本次練習報告</div>
        <button style={btnGlass4}><Icon name="more" size={20} color={HK.text}/></button>
      </div>

      {/* Hero */}
      <div style={{ padding: '20px 24px 18px', position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 18 }}>
          {/* Big score */}
          <div style={{ position: 'relative', width: 110, height: 110, flexShrink: 0 }}>
            <svg width="110" height="110">
              <defs>
                <linearGradient id="rg" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stopColor={HK.blue}/>
                  <stop offset="1" stopColor={HK.gold}/>
                </linearGradient>
              </defs>
              <circle cx="55" cy="55" r="48" fill="none" stroke={HK.surface3} strokeWidth="6"/>
              <circle cx="55" cy="55" r="48" fill="none" stroke="url(#rg)" strokeWidth="6"
                strokeDasharray={2 * Math.PI * 48} strokeDashoffset={2 * Math.PI * 48 * (1 - overall/100)}
                strokeLinecap="round" transform="rotate(-90 55 55)"/>
            </svg>
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ fontFamily: HK.fontMono, fontSize: 36, fontWeight: 700, color: HK.text, lineHeight: 1, fontVariantNumeric: 'tabular-nums', letterSpacing: -1 }}>{overall}</div>
              <div style={{ fontFamily: HK.fontMono, fontSize: 9, color: HK.gold, letterSpacing: 1.5, marginTop: 2, fontWeight: 600 }}>總分</div>
            </div>
          </div>
          {/* Title */}
          <div style={{ flex: 1, paddingTop: 6 }}>
            <div style={{ fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted, letterSpacing: 1.4, fontWeight: 600 }}>漂亮的演奏</div>
            <div style={{ fontFamily: HK.fontDisplay, fontSize: 26, color: HK.text, marginTop: 4, letterSpacing: -0.4, lineHeight: 1.05 }}>
              你完成了<br/>
              <span style={{ fontStyle: 'italic', color: HK.gold }}>{song?.title || '給愛麗絲'}</span>
            </div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: '4px 9px', marginTop: 10, borderRadius: 999,
              background: 'rgba(92,229,167,0.14)', color: HK.green,
              fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600, letterSpacing: 0.5,
            }}>
              <Icon name="bolt" size={11} color={HK.green}/>
              比平均 +4
            </div>
          </div>
        </div>
      </div>

      {/* Score cards */}
      <div style={{ padding: '0 20px 16px', display: 'flex', gap: 8 }}>
        <ScoreCard icon="target" label="準確率" value="92" color={HK.blue} trend={3}/>
        <ScoreCard icon="metronome" label="节奏" value="84" color={HK.gold} trend={5}/>
        <ScoreCard icon="posture" label="姿勢" value="79" color={HK.red} trend={-2}/>
      </div>

      {/* Mistakes section */}
      <div style={{
        padding: '6px 24px 10px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
      }}>
        <div style={{ fontFamily: HK.fontUI, fontSize: 15, fontWeight: 600, color: HK.text }}>依小節標記的錯誤</div>
        <div style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textMuted }}>共 {MISTAKES.length} 項</div>
      </div>
      <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {MISTAKES.map(m => (
          <MistakeRow key={m.id} mistake={m}
            expanded={openId === m.id}
            onClick={() => setOpenId(openId === m.id ? null : m.id)}/>
        ))}
      </div>

      {/* AI insight */}
      <div style={{ padding: '18px 20px 8px' }}>
        <div style={{
          padding: 14, borderRadius: 18,
          background: `linear-gradient(135deg, ${HK.gold}1c, ${HK.surface2})`,
          border: `1px solid ${HK.gold}25`,
          display: 'flex', gap: 12, alignItems: 'flex-start',
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8,
            background: HK.gold, color: HK.surface,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0, fontFamily: HK.fontDisplay, fontSize: 16, fontWeight: 600,
          }}>AI</div>
          <div>
            <div style={{ fontFamily: HK.fontMono, fontSize: 9, color: HK.gold, letterSpacing: 1.3, fontWeight: 600 }}>AI 教練</div>
            <div style={{ fontSize: 13, color: HK.text, marginTop: 3, lineHeight: 1.45 }}>
              你右手拇指在琴琴綠中偏慢。試試看以一半速度進行<span style={{ color: HK.gold, fontStyle: 'italic' }}>「拇指滾進」練習</span>，再重試一次。
            </div>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, padding: '16px 20px 36px',
        background: 'linear-gradient(180deg, rgba(10,22,34,0) 0%, rgba(10,22,34,0.95) 40%, rgba(10,22,34,1) 100%)',
      }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onDone} style={{
            flex: 1, padding: '16px', borderRadius: 999,
            background: HK.surface3, color: HK.text,
            border: `1px solid ${HK.hairlineStrong}`,
            fontFamily: HK.fontUI, fontSize: 15, fontWeight: 600,
            cursor: 'pointer',
          }}>完成</button>
          <button onClick={onRetry} style={{
            flex: 1.6, padding: '16px', borderRadius: 999,
            background: `linear-gradient(135deg, ${HK.blue}, #67D5FB)`,
            color: HK.surface, border: 'none',
            fontFamily: HK.fontUI, fontSize: 15, fontWeight: 700,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            boxShadow: `0 8px 22px ${HK.blue}40`,
          }}>
            <Icon name="retry" size={14} color={HK.surface}/>
            重新練習
          </button>
        </div>
      </div>
    </div>
  );
}

const btnGlass4 = {
  width: 38, height: 38, borderRadius: 19,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer',
};
const smallBtn = {
  display: 'inline-flex', alignItems: 'center', gap: 4,
  padding: '5px 9px', borderRadius: 7,
  background: HK.surface3, border: `1px solid ${HK.hairline}`,
  color: HK.text, fontFamily: HK.fontUI, fontSize: 11, fontWeight: 500,
  cursor: 'pointer',
};

Object.assign(window, { ReviewScreen });
