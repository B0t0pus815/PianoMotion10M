// SetupScreen — Pick difficulty + hand for the chosen song.

function HandIcon({ kind, active, size = 56 }) {
  // Custom stylized hand-skeleton glyph for L/Both/R toggle
  const fingers = kind === 'left'
    ? [[12, 30], [18, 14], [26, 8], [34, 14], [42, 30]]
    : kind === 'right'
    ? [[42, 30], [38, 14], [30, 8], [22, 14], [12, 30]]
    : null;

  const color = active ? HK.blue : HK.textMuted;
  if (kind === 'both') {
    return (
      <svg width={size} height={size} viewBox="0 0 64 64" style={{ display: 'block' }}>
        <BothHands color={color}/>
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 54 54" style={{ display: 'block' }}>
      {/* palm */}
      <ellipse cx="27" cy="40" rx="13" ry="9" fill={`${color}22`} stroke={color} strokeWidth="1.4"/>
      {/* fingers */}
      {fingers && fingers.map(([x, y], i) => (
        <g key={i}>
          <line x1="27" y1="40" x2={x} y2={y} stroke={color} strokeWidth="1.4" strokeLinecap="round" opacity="0.7"/>
          <circle cx={x} cy={y} r="2.6" fill={color}/>
        </g>
      ))}
      {/* joints */}
      <circle cx="27" cy="40" r="3" fill={color}/>
    </svg>
  );
}

function BothHands({ color }) {
  return (
    <g>
      {/* left palm */}
      <ellipse cx="18" cy="42" rx="10" ry="7" fill={`${color}22`} stroke={color} strokeWidth="1.3"/>
      {/* left fingers */}
      {[[8, 32], [12, 22], [18, 16], [25, 22], [29, 32]].map(([x, y], i) => (
        <g key={'l' + i}>
          <line x1="18" y1="42" x2={x} y2={y} stroke={color} strokeWidth="1.3" strokeLinecap="round" opacity="0.65"/>
          <circle cx={x} cy={y} r="2" fill={color}/>
        </g>
      ))}
      <circle cx="18" cy="42" r="2.4" fill={color}/>
      {/* right palm */}
      <ellipse cx="46" cy="42" rx="10" ry="7" fill={`${color}22`} stroke={color} strokeWidth="1.3"/>
      {[[56, 32], [52, 22], [46, 16], [39, 22], [35, 32]].map(([x, y], i) => (
        <g key={'r' + i}>
          <line x1="46" y1="42" x2={x} y2={y} stroke={color} strokeWidth="1.3" strokeLinecap="round" opacity="0.65"/>
          <circle cx={x} cy={y} r="2" fill={color}/>
        </g>
      ))}
      <circle cx="46" cy="42" r="2.4" fill={color}/>
    </g>
  );
}

function DifficultyCard({ level, active, onClick, meta }) {
  const colors = {
    Beginner:     { c: HK.green, name: '初階', label: '放慢速度·單手輔助' },
    Intermediate: { c: HK.gold,  name: '中階', label: '原在速度·雙手同步' },
    Advanced:     { c: HK.red,   name: '進階', label: '全速度·併評估表情' },
  }[level];

  // Difficulty dots indicator
  const dotCount = { Beginner: 1, Intermediate: 2, Advanced: 3 }[level];

  return (
    <button onClick={onClick} style={{
      flex: 1, cursor: 'pointer', textAlign: 'left',
      padding: '14px 14px 12px', borderRadius: 18,
      background: active ? `linear-gradient(160deg, ${colors.c}22, ${HK.surface2})` : HK.surface2,
      border: active ? `1.5px solid ${colors.c}` : `1px solid ${HK.hairline}`,
      transition: 'all 0.18s',
      position: 'relative', overflow: 'hidden',
    }}>
      {active && (
        <div style={{
          position: 'absolute', top: 10, right: 10,
          width: 18, height: 18, borderRadius: 9,
          background: colors.c, color: HK.surface,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="check" size={12} color={HK.surface} strokeWidth={2.5}/>
        </div>
      )}
      {/* dots */}
      <div style={{ display: 'flex', gap: 3, marginBottom: 10 }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 18, height: 3, borderRadius: 2,
            background: i < dotCount ? colors.c : HK.hairlineStrong,
          }}/>
        ))}
      </div>
      <div style={{
        fontFamily: HK.fontUI, fontSize: 14, fontWeight: 600,
        color: active ? HK.text : HK.text,
      }}>{colors.name}</div>
      <div style={{
        fontFamily: HK.fontUI, fontSize: 10.5, lineHeight: 1.35,
        color: HK.textDim, marginTop: 4,
      }}>{colors.label}</div>
    </button>
  );
}

function HandToggle({ value, onChange }) {
  const options = [
    { k: 'left',  label: '左手' },
    { k: 'both',  label: '雙手' },
    { k: 'right', label: '右手' },
  ];
  return (
    <div style={{
      display: 'flex', padding: 4, gap: 4,
      background: HK.surface2, borderRadius: 18,
      border: `1px solid ${HK.hairline}`,
    }}>
      {options.map(o => {
        const a = value === o.k;
        return (
          <button key={o.k} onClick={() => onChange(o.k)} style={{
            flex: 1, padding: '14px 8px',
            borderRadius: 14, border: 'none', cursor: 'pointer',
            background: a ? HK.surface3 : 'transparent',
            color: a ? HK.text : HK.textDim,
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
            transition: 'all 0.18s',
            boxShadow: a ? `0 0 0 1px ${HK.blue}30 inset, 0 2px 8px rgba(0,0,0,0.2)` : 'none',
          }}>
            <HandIcon kind={o.k} active={a} size={o.k === 'both' ? 50 : 42}/>
            <div style={{
              fontFamily: HK.fontUI, fontSize: 12, fontWeight: a ? 600 : 500,
              color: a ? HK.blue : HK.textDim,
            }}>{o.label}</div>
          </button>
        );
      })}
    </div>
  );
}

function SetupScreen({ song, onStart, onBack }) {
  const [diff, setDiff] = React.useState(song?.diff || 'Intermediate');
  const [hand, setHand] = React.useState('both');
  const [tempo, setTempo] = React.useState(100);
  const [metronome, setMetronome] = React.useState(true);

  return (
    <div style={{
      position: 'absolute', inset: 0, paddingTop: 54, paddingBottom: 28,
      overflow: 'auto', background: HK.bg,
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Top bar */}
      <div style={{ padding: '6px 16px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button onClick={onBack} style={btnGlass2}><Icon name="back" size={20} color={HK.text}/></button>
        <div style={{ fontFamily: HK.fontUI, fontSize: 13, fontWeight: 600, color: HK.textDim, letterSpacing: 1.6 }}>練習設定</div>
        <button style={btnGlass2}><Icon name="more" size={20} color={HK.text}/></button>
      </div>

      {/* Song hero */}
      <div style={{ padding: '24px 24px 8px' }}>
        <div style={{ fontFamily: HK.fontMono, fontSize: 10, color: HK.gold, letterSpacing: 1.6, fontWeight: 600 }}>
          曲目 · {song?.key || 'A 小調'}
        </div>
        <div style={{ fontFamily: HK.fontDisplay, fontSize: 36, lineHeight: 1, color: HK.text, letterSpacing: -0.6, marginTop: 6 }}>
          {song?.title || '給愛麗絲'}
        </div>
        <div style={{ fontSize: 14, color: HK.textDim, marginTop: 6 }}>
          {song?.composer || '貝多芬'}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
          <div style={statPill}>
            <Icon name="clock" size={11} color={HK.textDim}/>
            <span>{song?.dur || '3:25'}</span>
          </div>
          <div style={statPill}>
            <Icon name="note" size={11} color={HK.textDim}/>
            <span>247 個音符</span>
          </div>
          <div style={statPill}>
            <Icon name="star" size={11} color={HK.gold}/>
            <span style={{ color: HK.gold }}>4.8</span>
          </div>
        </div>
      </div>

      {/* Difficulty */}
      <SectionLabel>難度</SectionLabel>
      <div style={{ padding: '0 20px 16px', display: 'flex', gap: 8 }}>
        {['Beginner', 'Intermediate', 'Advanced'].map(l => (
          <DifficultyCard key={l} level={l} active={diff === l} onClick={() => setDiff(l)}/>
        ))}
      </div>

      {/* Hand */}
      <SectionLabel>手部</SectionLabel>
      <div style={{ padding: '0 20px 18px' }}>
        <HandToggle value={hand} onChange={setHand}/>
      </div>

      {/* Tempo + metronome */}
      <SectionLabel>速度與節拍</SectionLabel>
      <div style={{ padding: '0 20px 22px' }}>
        <div style={{
          padding: 16, borderRadius: 18,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Icon name="metronome" size={18} color={HK.blue}/>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: HK.text }}>速度</div>
                <div style={{ fontSize: 11, color: HK.textMuted }}>調整播放速度</div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
              <span style={{ fontFamily: HK.fontMono, fontSize: 22, fontWeight: 600, color: HK.blue, fontVariantNumeric: 'tabular-nums' }}>{tempo}</span>
              <span style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textMuted }}>%</span>
            </div>
          </div>
          {/* Slider */}
          <div style={{ marginTop: 14, position: 'relative', height: 24 }}>
            <input
              type="range" min="50" max="120" value={tempo}
              onChange={(e) => setTempo(+e.target.value)}
              style={{
                position: 'absolute', inset: 0, width: '100%', height: 24,
                appearance: 'none', WebkitAppearance: 'none', background: 'transparent',
                zIndex: 2, opacity: 0, cursor: 'pointer',
              }}
            />
            <div style={{
              position: 'absolute', left: 0, right: 0, top: '50%', transform: 'translateY(-50%)',
              height: 6, borderRadius: 3, background: HK.surface3,
            }}>
              <div style={{
                width: `${((tempo - 50) / 70) * 100}%`,
                height: '100%', borderRadius: 3,
                background: `linear-gradient(90deg, ${HK.blue}, ${HK.gold})`,
              }}/>
            </div>
            <div style={{
              position: 'absolute', top: '50%', transform: 'translate(-50%, -50%)',
              left: `${((tempo - 50) / 70) * 100}%`,
              width: 18, height: 18, borderRadius: 10,
              background: HK.text, boxShadow: `0 0 0 4px ${HK.blue}40, 0 2px 6px rgba(0,0,0,0.4)`,
            }}/>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted }}>
            <span>50%</span><span>原速</span><span>120%</span>
          </div>

          <div style={{ height: 1, background: HK.hairline, margin: '14px -4px' }}/>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Icon name="waveform" size={18} color={HK.gold}/>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: HK.text }}>節拍器</div>
                <div style={{ fontSize: 11, color: HK.textMuted }}>伴隨拍點發出提示音</div>
              </div>
            </div>
            <Switch on={metronome} onChange={() => setMetronome(!metronome)}/>
          </div>
        </div>
      </div>

      {/* CTA pinned-ish to bottom */}
      <div style={{ flex: 1 }}/>
      <div style={{ padding: '8px 20px 8px' }}>
        <button onClick={onStart} style={{
          width: '100%', border: 'none', cursor: 'pointer',
          padding: '18px', borderRadius: 999,
          background: `linear-gradient(135deg, ${HK.blue} 0%, #67D5FB 100%)`,
          color: HK.surface,
          fontFamily: HK.fontUI, fontSize: 16, fontWeight: 700, letterSpacing: 0.2,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
          boxShadow: `0 10px 28px ${HK.blue}40, 0 0 0 1px rgba(255,255,255,0.1) inset`,
        }}>
          <Icon name="play" size={16} color={HK.surface}/>
          開始練習
        </button>
        <div style={{ textAlign: 'center', fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted, marginTop: 10, letterSpacing: 0.5 }}>
          摄影機將開啟 · 請在倒數前將雙手放上琴鍵
        </div>
      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      padding: '0 24px 10px', marginTop: 14,
      fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600,
      color: HK.textMuted, letterSpacing: 1.6, textTransform: 'uppercase',
    }}>{children}</div>
  );
}

function Switch({ on, onChange }) {
  return (
    <button onClick={onChange} style={{
      width: 46, height: 28, borderRadius: 14,
      background: on ? HK.blue : HK.surface3,
      border: 'none', cursor: 'pointer', position: 'relative',
      transition: 'background 0.18s',
      padding: 0,
    }}>
      <div style={{
        position: 'absolute', top: 3, left: on ? 21 : 3,
        width: 22, height: 22, borderRadius: 11,
        background: '#fff',
        transition: 'left 0.18s',
        boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
      }}/>
    </button>
  );
}

const btnGlass2 = {
  width: 38, height: 38, borderRadius: 19,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer',
};

const statPill = {
  display: 'inline-flex', alignItems: 'center', gap: 5,
  padding: '5px 9px', borderRadius: 8,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  fontFamily: HK.fontMono, fontSize: 11, color: HK.textDim,
  fontWeight: 500,
};

Object.assign(window, { SetupScreen });
