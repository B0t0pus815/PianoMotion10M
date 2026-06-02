// Shared design tokens, primitives and SVG icons for HandKeys AI.

const HK = {
  bg: '#0A1622',          // deepest navy
  surface: '#0D1B2A',     // base navy (spec)
  surface2: '#142537',    // raised surface
  surface3: '#1B2F44',    // highest surface
  hairline: 'rgba(255,255,255,0.07)',
  hairlineStrong: 'rgba(255,255,255,0.12)',
  text: '#EAF2FB',
  textDim: 'rgba(234,242,251,0.62)',
  textMuted: 'rgba(234,242,251,0.38)',
  blue: '#4FC3F7',
  blueDim: 'rgba(79,195,247,0.18)',
  gold: '#FFD700',
  goldDim: 'rgba(255,215,0,0.16)',
  red: '#FF6B7A',
  green: '#5CE5A7',
  yellow: '#FFD86B',
  fontDisplay: '"Instrument Serif", "Noto Serif TC", "Cormorant Garamond", Georgia, serif',
  fontUI: '-apple-system, "SF Pro Text", "SF Pro Display", "Noto Sans TC", "PingFang TC", system-ui, sans-serif',
  fontMono: '"JetBrains Mono", "SF Mono", ui-monospace, monospace',
};

// ─── Icons (line, 22px stroke 1.8) ─────────────────────────────
function Icon({ name, size = 22, color = 'currentColor', strokeWidth = 1.8 }) {
  const p = { fill: 'none', stroke: color, strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    home: <><path d="M3 11l9-7 9 7v9a2 2 0 01-2 2h-4v-6h-6v6H5a2 2 0 01-2-2z" {...p}/></>,
    practice: <><circle cx="12" cy="12" r="9" {...p}/><path d="M10 8v8l6-4z" {...p} fill={color}/></>,
    history: <><path d="M3 12a9 9 0 109-9" {...p}/><path d="M3 6v6h6" {...p}/><path d="M12 7v5l3 2" {...p}/></>,
    profile: <><circle cx="12" cy="8" r="4" {...p}/><path d="M4 21c1-4 4.5-6 8-6s7 2 8 6" {...p}/></>,
    search: <><circle cx="11" cy="11" r="7" {...p}/><path d="M20 20l-3.5-3.5" {...p}/></>,
    back: <><path d="M15 5l-7 7 7 7" {...p}/></>,
    close: <><path d="M6 6l12 12M18 6L6 18" {...p}/></>,
    more: <><circle cx="5" cy="12" r="1.4" fill={color}/><circle cx="12" cy="12" r="1.4" fill={color}/><circle cx="19" cy="12" r="1.4" fill={color}/></>,
    play: <><path d="M7 4v16l13-8z" fill={color}/></>,
    pause: <><rect x="6" y="4" width="4" height="16" rx="1" fill={color}/><rect x="14" y="4" width="4" height="16" rx="1" fill={color}/></>,
    star: <><path d="M12 3l2.7 5.7 6.3.9-4.6 4.4 1.1 6.3L12 17.3 6.5 20.3l1.1-6.3L3 9.6l6.3-.9z" {...p}/></>,
    check: <><path d="M4 12l5 5L20 6" {...p}/></>,
    retry: <><path d="M21 12a9 9 0 11-3-6.7" {...p}/><path d="M21 4v5h-5" {...p}/></>,
    camera: <><path d="M4 7h3l2-2h6l2 2h3a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V8a1 1 0 011-1z" {...p}/><circle cx="12" cy="13" r="3.5" {...p}/></>,
    metronome: <><path d="M8 3h8l2 18H6z" {...p}/><path d="M9 17h6" {...p}/><path d="M12 19V8l5-3" {...p}/></>,
    handL: <><path d="M9 21V11M9 11V5a1.5 1.5 0 113 0v6M12 11V4a1.5 1.5 0 113 0v7M15 11V6a1.5 1.5 0 113 0v9c0 3.5-2 6-5 6H9c-2 0-3-1-4-3l-3-5 2-1 3 3" {...p}/></>,
    handR: <><path d="M15 21V11M15 11V5a1.5 1.5 0 10-3 0v6M12 11V4a1.5 1.5 0 10-3 0v7M9 11V6a1.5 1.5 0 10-3 0v9c0 3.5 2 6 5 6h3c2 0 3-1 4-3l3-5-2-1-3 3" {...p}/></>,
    filter: <><path d="M4 6h16M7 12h10M10 18h4" {...p}/></>,
    chevR: <><path d="M9 6l6 6-6 6" {...p}/></>,
    chevD: <><path d="M6 9l6 6 6-6" {...p}/></>,
    bolt: <><path d="M13 3L4 14h7l-1 7 9-11h-7z" {...p}/></>,
    clock: <><circle cx="12" cy="12" r="9" {...p}/><path d="M12 7v5l3 2" {...p}/></>,
    target: <><circle cx="12" cy="12" r="9" {...p}/><circle cx="12" cy="12" r="5" {...p}/><circle cx="12" cy="12" r="1.5" fill={color}/></>,
    posture: <><circle cx="12" cy="5" r="2" {...p}/><path d="M12 7v6M8 11l4-2 4 2M8 21l4-8 4 8" {...p}/></>,
    waveform: <><path d="M3 12h2l2-6 3 12 3-9 3 6 2-3h3" {...p}/></>,
    note: <><path d="M9 18V5l10-2v13" {...p}/><circle cx="7" cy="18" r="2" fill={color} stroke="none"/><circle cx="17" cy="16" r="2" fill={color} stroke="none"/></>,
    flame: <><path d="M12 3s5 4 5 9a5 5 0 11-10 0c0-2 1-3 1-3s1 2 3 2c0-3-2-4 1-8z" {...p}/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: 'block' }}>
      {paths[name]}
    </svg>
  );
}

// ─── HandKeys wordmark / logo ──────────────────────────────────
function Logo({ size = 28, withWord = true, color = HK.blue }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width={size} height={size} viewBox="0 0 32 32">
        <defs>
          <linearGradient id="lg-key" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={HK.blue}/>
            <stop offset="1" stopColor={HK.gold}/>
          </linearGradient>
        </defs>
        {/* abstract piano-key + hand mark */}
        <rect x="3" y="6" width="6" height="20" rx="1.2" fill="url(#lg-key)" opacity="0.95"/>
        <rect x="11" y="6" width="6" height="20" rx="1.2" fill={HK.blue} opacity="0.55"/>
        <rect x="19" y="6" width="6" height="20" rx="1.2" fill={HK.blue} opacity="0.28"/>
        <circle cx="26" cy="9" r="2.4" fill={HK.gold}/>
      </svg>
      {withWord && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
          <span style={{ fontFamily: HK.fontDisplay, fontSize: 22, color: HK.text, letterSpacing: -0.4, fontWeight: 400 }}>HandKeys</span>
          <span style={{ fontFamily: HK.fontMono, fontSize: 10, color: HK.gold, letterSpacing: 1.6, transform: 'translateY(-6px)', display: 'inline-block', fontWeight: 600 }}>AI</span>
        </div>
      )}
    </div>
  );
}

// ─── Status bar tuned for dark navy ────────────────────────────
function StatusBar({ time = '9:41' }) {
  return (
    <div style={{
      position: 'absolute', top: 0, left: 0, right: 0, zIndex: 30,
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '21px 32px 0', height: 54, boxSizing: 'border-box',
      pointerEvents: 'none',
    }}>
      <span style={{ fontFamily: HK.fontUI, fontWeight: 600, fontSize: 17, color: HK.text }}>{time}</span>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', color: HK.text }}>
        <svg width="18" height="11" viewBox="0 0 18 11"><rect x="0" y="6.5" width="3" height="4" rx="0.6" fill="currentColor"/><rect x="4.5" y="4.5" width="3" height="6" rx="0.6" fill="currentColor"/><rect x="9" y="2" width="3" height="8.5" rx="0.6" fill="currentColor"/><rect x="13.5" y="0" width="3" height="10.5" rx="0.6" fill="currentColor"/></svg>
        <svg width="16" height="11" viewBox="0 0 16 11"><path d="M8 2.8a8 8 0 015.6 2.3l1-1A9.5 9.5 0 008 1a9.5 9.5 0 00-6.6 3.1l1 1A8 8 0 018 2.8z" fill="currentColor"/><path d="M8 6.2a4.6 4.6 0 013.3 1.4l1-1A6 6 0 008 4.8a6 6 0 00-4.3 1.8l1 1A4.6 4.6 0 018 6.2z" fill="currentColor"/><circle cx="8" cy="9.5" r="1.3" fill="currentColor"/></svg>
        <svg width="26" height="12" viewBox="0 0 26 12"><rect x="0.5" y="0.5" width="22" height="11" rx="3" stroke="currentColor" strokeOpacity="0.5" fill="none"/><rect x="2" y="2" width="19" height="8" rx="1.6" fill="currentColor"/><path d="M24 4v4c.8-.3 1.4-1.1 1.4-2s-.6-1.7-1.4-2z" fill="currentColor" fillOpacity="0.5"/></svg>
      </div>
    </div>
  );
}

// ─── HomeIndicator over dark background ────────────────────────
function HomeIndicator() {
  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0, height: 28,
      display: 'flex', justifyContent: 'center', alignItems: 'flex-end',
      paddingBottom: 8, pointerEvents: 'none', zIndex: 60,
    }}>
      <div style={{ width: 134, height: 5, borderRadius: 4, background: 'rgba(255,255,255,0.55)' }}/>
    </div>
  );
}

// ─── Difficulty badge pill ─────────────────────────────────────
function DiffBadge({ level, dense = false }) {
  const colors = {
    Beginner:     { fg: HK.green, bg: 'rgba(92,229,167,0.14)', label: '初階' },
    Intermediate: { fg: HK.gold,  bg: HK.goldDim,                label: '中階' },
    Advanced:     { fg: HK.red,   bg: 'rgba(255,107,122,0.14)',  label: '進階' },
  };
  const c = colors[level] || colors.Beginner;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: dense ? '2px 8px' : '4px 10px',
      borderRadius: 999, fontFamily: HK.fontUI,
      fontSize: dense ? 10 : 11, fontWeight: 600, letterSpacing: 0.3,
      color: c.fg, background: c.bg,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: 3, background: c.fg }}/>
      {c.label}
    </span>
  );
}

// ─── Bottom Nav ────────────────────────────────────────────────
function BottomNav({ active = 'home' }) {
  const items = [
    { k: 'home', label: '首頁' },
    { k: 'practice', label: '練習' },
    { k: 'history', label: '記錄' },
    { k: 'profile', label: '個人' },
  ];
  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 40,
      paddingBottom: 28, paddingTop: 10,
      background: 'linear-gradient(180deg, rgba(10,22,34,0) 0%, rgba(10,22,34,0.85) 25%, rgba(10,22,34,0.98) 60%)',
      backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      borderTop: `0.5px solid ${HK.hairline}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-around', padding: '0 12px' }}>
        {items.map((it) => {
          const a = active === it.k;
          return (
            <div key={it.k} data-nav-target={it.k} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
              padding: '6px 10px', flex: 1, cursor: 'pointer',
            }}>
              <div style={{ color: a ? HK.blue : HK.textMuted }}>
                <Icon name={it.k} size={24} strokeWidth={a ? 2 : 1.7}/>
              </div>
              <span style={{
                fontFamily: HK.fontUI, fontSize: 10, fontWeight: a ? 600 : 500,
                color: a ? HK.blue : HK.textMuted, letterSpacing: 0.2,
              }}>{it.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Device shell (dark, no chrome) ────────────────────────────
function Phone({ children, width = 390, height = 844 }) {
  return (
    <div style={{
      width, height, position: 'relative', overflow: 'hidden',
      background: HK.bg, color: HK.text, fontFamily: HK.fontUI,
      WebkitFontSmoothing: 'antialiased',
    }}>
      <StatusBar/>
      {children}
      <HomeIndicator/>
    </div>
  );
}

Object.assign(window, { HK, Icon, Logo, StatusBar, HomeIndicator, DiffBadge, BottomNav, Phone });
