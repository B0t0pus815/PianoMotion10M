// HistoryScreen — Practice calendar heatmap, progress chart, recent sessions.

const RECENT_SESSIONS = [
  { id: 'h1', title: '給愛麗絲',           composer: '貝多芬',  score: 87, accent: '#4FC3F7', when: '今天 19:42', dur: '14 分鐘', delta: +3 },
  { id: 'h2', title: 'G 大調小步舞曲',      composer: '巴赫',    score: 94, accent: '#5CE5A7', when: '昨天 21:08', dur: '8 分鐘',  delta: +6 },
  { id: 'h3', title: '月光奏鳴曲·第一樂章', composer: '貝多芬',  score: 76, accent: '#4FC3F7', when: '5/11 18:15', dur: '22 分鐘', delta: -2 },
  { id: 'h4', title: 'C 大調前奏曲',        composer: '巴赫',    score: 91, accent: '#5CE5A7', when: '5/10 20:00', dur: '11 分鐘', delta: +4 },
  { id: 'h5', title: '夜曲 Op.9 No.2',     composer: '蕭邦',    score: 68, accent: '#FFD700', when: '5/9 19:30',  dur: '26 分鐘', delta: 0 },
];

// 7×11 weeks heatmap, deterministic intensity per cell
function HeatCell({ intensity }) {
  const colors = [
    HK.surface3,            // 0
    'rgba(79,195,247,0.18)',// 1
    'rgba(79,195,247,0.35)',// 2
    'rgba(79,195,247,0.6)', // 3
    HK.blue,                // 4
  ];
  const idx = Math.min(4, Math.max(0, intensity));
  return (
    <div style={{
      width: 14, height: 14, borderRadius: 3,
      background: colors[idx],
      border: `1px solid ${idx === 0 ? HK.hairline : 'transparent'}`,
    }}/>
  );
}

function Heatmap() {
  // 11 columns × 7 rows. Today highlighted (last col, row 3).
  const data = [];
  for (let c = 0; c < 11; c++) {
    const col = [];
    for (let r = 0; r < 7; r++) {
      const seed = (c * 7 + r) * 1.21;
      const v = (Math.sin(seed) + Math.cos(seed * 1.7)) / 2;
      col.push(Math.round((v + 1) * 2.2));
    }
    data.push(col);
  }
  const months = ['二月', '三月', '四月', '五月'];
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {/* day labels */}
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingTop: 18, paddingBottom: 2 }}>
        {['一', '三', '五', '日'].map(d => (
          <div key={d} style={{ fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted, height: 14, lineHeight: '14px' }}>{d}</div>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {/* month labels */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 4, height: 12 }}>
          {months.map((m, i) => (
            <div key={m} style={{ width: 14 + (14 + 4) * 2, fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted }}>{m}</div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {data.map((col, ci) => (
            <div key={ci} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {col.map((v, ri) => {
                const isToday = ci === 10 && ri === 3;
                return (
                  <div key={ri} style={{ position: 'relative' }}>
                    <HeatCell intensity={v}/>
                    {isToday && (
                      <div style={{
                        position: 'absolute', inset: -3,
                        border: `1.5px solid ${HK.gold}`, borderRadius: 5,
                        pointerEvents: 'none',
                      }}/>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Stacked bar chart — last 7 days accuracy & duration
function ProgressChart() {
  const days = [
    { d: '一', acc: 72 }, { d: '二', acc: 78 }, { d: '三', acc: 81 },
    { d: '四', acc: 76 }, { d: '五', acc: 84 }, { d: '六', acc: 89 }, { d: '日', acc: 87 },
  ];
  const max = 100;
  return (
    <div style={{ position: 'relative', height: 130 }}>
      {/* y axis lines */}
      {[100, 75, 50].map(y => (
        <div key={y} style={{
          position: 'absolute', left: 24, right: 0,
          top: `${(1 - y / max) * 100}%`,
          height: 1, background: HK.hairline,
        }}>
          <span style={{
            position: 'absolute', left: -22, top: -7,
            fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted,
          }}>{y}</span>
        </div>
      ))}
      {/* Bars */}
      <div style={{
        position: 'absolute', inset: 0, paddingLeft: 24,
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
        gap: 6,
      }}>
        {days.map((d, i) => {
          const h = (d.acc / max) * 100;
          const isLast = i === days.length - 1;
          return (
            <div key={i} style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'flex-end',
              height: '100%',
            }}>
              <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'flex-end' }}>
                <div style={{
                  width: '100%', height: `${h}%`,
                  background: isLast
                    ? `linear-gradient(180deg, ${HK.gold}, ${HK.blue})`
                    : `linear-gradient(180deg, ${HK.blue}aa, ${HK.blue}33)`,
                  borderRadius: '4px 4px 1px 1px',
                  position: 'relative',
                }}>
                  {isLast && (
                    <div style={{
                      position: 'absolute', top: -22, left: '50%', transform: 'translateX(-50%)',
                      padding: '2px 6px', borderRadius: 5,
                      background: HK.gold, color: HK.surface,
                      fontFamily: HK.fontMono, fontSize: 10, fontWeight: 700, whiteSpace: 'nowrap',
                    }}>{d.acc}%</div>
                  )}
                </div>
              </div>
              <div style={{
                fontFamily: HK.fontMono, fontSize: 10, color: isLast ? HK.gold : HK.textMuted,
                marginTop: 6, fontWeight: isLast ? 700 : 500,
              }}>{d.d}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SessionRow({ s }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 14px', borderRadius: 16,
      background: HK.surface2, border: `1px solid ${HK.hairline}`,
    }}>
      <div style={{
        width: 42, height: 42, flexShrink: 0,
        borderRadius: 10,
        background: `linear-gradient(135deg, ${s.accent}33, ${s.accent}11)`,
        border: `1px solid ${s.accent}30`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: HK.fontMono, fontSize: 14, fontWeight: 700, color: s.accent,
        fontVariantNumeric: 'tabular-nums',
      }}>{s.score}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14, fontWeight: 600, color: HK.text,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{s.title}</div>
        <div style={{ fontSize: 11, color: HK.textDim, marginTop: 1 }}>{s.composer}</div>
        <div style={{ display: 'flex', gap: 8, marginTop: 5, fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted }}>
          <span>{s.when}</span><span>·</span><span>{s.dur}</span>
        </div>
      </div>
      <div style={{
        fontFamily: HK.fontMono, fontSize: 11, fontWeight: 700,
        color: s.delta > 0 ? HK.green : s.delta < 0 ? HK.red : HK.textMuted,
        display: 'flex', alignItems: 'center', gap: 2,
      }}>
        {s.delta > 0 ? '▲' : s.delta < 0 ? '▼' : '–'} {s.delta !== 0 ? Math.abs(s.delta) : ''}
      </div>
    </div>
  );
}

function HistoryScreen() {
  const [tab, setTab] = React.useState('week');
  const tabs = [
    { k: 'week',  label: '本週' },
    { k: 'month', label: '本月' },
    { k: 'all',   label: '全部' },
  ];

  return (
    <div style={{
      position: 'absolute', inset: 0, paddingTop: 54, paddingBottom: 92,
      overflow: 'auto', background: HK.bg,
    }}>
      {/* Header */}
      <div style={{ padding: '8px 20px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontFamily: HK.fontMono, fontSize: 10, color: HK.gold, letterSpacing: 1.4, fontWeight: 600 }}>練習記錄</div>
          <div style={{ fontFamily: HK.fontDisplay, fontSize: 28, color: HK.text, letterSpacing: -0.4, marginTop: 2 }}>
            你的<span style={{ fontStyle: 'italic', color: HK.gold }}>進步軌跡</span>
          </div>
        </div>
        <button style={iconBtn}><Icon name="filter" size={18} color={HK.text}/></button>
      </div>

      {/* Top stats */}
      <div style={{ padding: '16px 20px 14px', display: 'flex', gap: 8 }}>
        <StatBlock icon="flame" label="連續天數" value="14" suffix="天" color={HK.gold}/>
        <StatBlock icon="clock" label="本週" value="3.2" suffix="小時" color={HK.blue}/>
        <StatBlock icon="target" label="平均分數" value="85" suffix="" color={HK.green}/>
      </div>

      {/* Heatmap */}
      <div style={{ padding: '0 20px 16px' }}>
        <div style={{
          padding: 16, borderRadius: 18,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: HK.text }}>練習熱力圖</div>
            <div style={{ fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted }}>近 11 週</div>
          </div>
          <Heatmap/>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginTop: 12, paddingTop: 12, borderTop: `1px solid ${HK.hairline}`,
            fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted,
          }}>
            <span>共 47 次練習</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span>少</span>
              {[0, 1, 2, 3, 4].map(i => <HeatCell key={i} intensity={i}/>)}
              <span>多</span>
            </div>
          </div>
        </div>
      </div>

      {/* Progress chart */}
      <div style={{ padding: '0 20px 16px' }}>
        <div style={{
          padding: 16, borderRadius: 18,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: HK.text }}>每日準確率</div>
              <div style={{ fontSize: 11, color: HK.textDim, marginTop: 2 }}>本週平均 81% · <span style={{ color: HK.green, fontWeight: 600 }}>↑ 4%</span></div>
            </div>
            <div style={{ display: 'flex', gap: 4, padding: 3, background: HK.surface3, borderRadius: 10, border: `1px solid ${HK.hairline}` }}>
              {tabs.map(t => (
                <button key={t.k} onClick={() => setTab(t.k)} style={{
                  border: 'none', cursor: 'pointer',
                  padding: '5px 9px', borderRadius: 7,
                  background: tab === t.k ? HK.surface2 : 'transparent',
                  color: tab === t.k ? HK.text : HK.textDim,
                  fontFamily: HK.fontUI, fontSize: 11, fontWeight: 600,
                }}>{t.label}</button>
              ))}
            </div>
          </div>
          <div style={{ marginTop: 10 }}>
            <ProgressChart/>
          </div>
        </div>
      </div>

      {/* Recent sessions */}
      <div style={{ padding: '6px 24px 10px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div style={{ fontFamily: HK.fontUI, fontSize: 15, fontWeight: 600, color: HK.text }}>最近的練習</div>
        <div style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.blue, fontWeight: 600 }}>查看全部</div>
      </div>
      <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {RECENT_SESSIONS.map(s => <SessionRow key={s.id} s={s}/>)}
      </div>

      <BottomNav active="history"/>
    </div>
  );
}

function StatBlock({ icon, label, value, suffix, color }) {
  return (
    <div style={{
      flex: 1, padding: 12, borderRadius: 14,
      background: HK.surface2, border: `1px solid ${HK.hairline}`,
    }}>
      <div style={{ color, marginBottom: 6 }}><Icon name={icon} size={16} color={color}/></div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
        <span style={{ fontFamily: HK.fontMono, fontSize: 22, fontWeight: 700, color: HK.text, lineHeight: 1, fontVariantNumeric: 'tabular-nums', letterSpacing: -0.5 }}>{value}</span>
        {suffix && <span style={{ fontFamily: HK.fontUI, fontSize: 11, color: HK.textMuted, fontWeight: 500 }}>{suffix}</span>}
      </div>
      <div style={{ fontSize: 11, color: HK.textDim, marginTop: 3 }}>{label}</div>
    </div>
  );
}

const iconBtn = {
  width: 38, height: 38, borderRadius: 19,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer',
};

Object.assign(window, { HistoryScreen });
