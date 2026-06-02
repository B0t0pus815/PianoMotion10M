// HomeScreen — Song selection with search, filters, and song cards.
// Songs are loaded from ../songs.json at mount; falls back to FALLBACK_SONGS.

const FALLBACK_SONGS = [
  {
    id: 's1',
    title: 'Canon in D',
    composer: 'Pachelbel',
    diff: 'Intermediate', dur: '3:12', key: 'D 大調', popularity: 98,
    accent: '#4FC3F7',
    videoUrl: '../results/canon_biomech_v4_kb.mp4',
    audioUrl: '../input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mp3',
  },
  {
    id: 's2',
    title: '菊次郎的夏天',
    composer: '久石讓',
    diff: 'Beginner', dur: '2:32', key: 'D 大調', popularity: 92,
    accent: '#FFD700',
    videoUrl: '../results/summer_v7final_kb.mp4',
    audioUrl: '../input_songs/[Piano Cover] 久石讓 Joe Hisaishi - 菊次郎的夏天(Summer)一聽前奏就知道的旋律.mp3',
  },
];

const FILTERS = [
  { k: 'All',          label: '全部' },
  { k: 'Beginner',     label: '初階' },
  { k: 'Intermediate', label: '中階' },
  { k: 'Advanced',     label: '進階' },
];

// Tiny waveform / sparkline visual unique to each song card.
function SongVisual({ accent, seed = 0 }) {
  const bars = Array.from({ length: 18 }, (_, i) => {
    const v = Math.sin((i + seed) * 0.9) * 0.5 + Math.sin((i + seed) * 2.1) * 0.3;
    return 0.35 + Math.abs(v) * 0.6;
  });
  return (
    <div style={{
      width: 56, height: 56, borderRadius: 14,
      background: `linear-gradient(135deg, ${accent}28 0%, ${accent}08 100%)`,
      border: `1px solid ${accent}30`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      gap: 1.5, padding: 12,
      flexShrink: 0,
    }}>
      {bars.map((h, i) => (
        <div key={i} style={{
          width: 1.5, height: `${h * 100}%`,
          background: accent, borderRadius: 1,
          opacity: 0.4 + h * 0.6,
        }}/>
      ))}
    </div>
  );
}

function SongCard({ song, onClick, featured = false }) {
  if (featured) {
    return (
      <div onClick={onClick} style={{
        position: 'relative', borderRadius: 24, overflow: 'hidden',
        background: `linear-gradient(135deg, ${song.accent}22 0%, ${HK.surface2} 60%)`,
        border: `1px solid ${song.accent}25`,
        padding: 18, cursor: 'pointer',
        boxShadow: `0 8px 32px ${song.accent}14, 0 1px 0 rgba(255,255,255,0.04) inset`,
      }}>
        <div style={{
          position: 'absolute', top: 12, right: 14,
          display: 'flex', alignItems: 'center', gap: 4,
          fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600,
          color: HK.gold, letterSpacing: 1.2,
        }}>
          <Icon name="flame" size={12} color={HK.gold}/>
          本週熱門
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginTop: 14 }}>
          <SongVisual accent={song.accent} seed={7}/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: HK.fontDisplay, fontSize: 24, lineHeight: 1.05, color: HK.text, letterSpacing: -0.3 }}>{song.title}</div>
            <div style={{ fontSize: 13, color: HK.textDim, marginTop: 2 }}>{song.composer}</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 14, flexWrap: 'wrap' }}>
          <DiffBadge level={song.diff}/>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: HK.textDim, fontSize: 12, fontFamily: HK.fontMono }}>
            <Icon name="clock" size={12}/>{song.dur}
          </div>
          <div style={{ color: HK.textMuted, fontSize: 12, fontFamily: HK.fontMono }}>·</div>
          <div style={{ color: HK.textDim, fontSize: 12, fontFamily: HK.fontMono }}>{song.key}</div>
          <div style={{ flex: 1 }}/>
          <button style={{
            border: 'none', background: HK.blue, color: HK.surface,
            width: 38, height: 38, borderRadius: 19,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', boxShadow: `0 4px 14px ${HK.blue}40`,
          }}>
            <Icon name="play" size={18} color={HK.surface}/>
          </button>
        </div>
      </div>
    );
  }
  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 14,
      padding: '12px 14px', borderRadius: 18,
      background: HK.surface2,
      border: `1px solid ${HK.hairline}`,
      cursor: 'pointer',
    }}>
      <SongVisual accent={song.accent} seed={song.id.charCodeAt(1)}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            fontSize: 15, fontWeight: 600, color: HK.text,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>{song.title}</div>
        </div>
        <div style={{ fontSize: 12, color: HK.textDim, marginTop: 2 }}>{song.composer}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 7 }}>
          <DiffBadge level={song.diff} dense/>
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, color: HK.textMuted, fontSize: 11, fontFamily: HK.fontMono }}>
            <Icon name="clock" size={11}/>{song.dur}
          </div>
        </div>
      </div>
      <div style={{ color: HK.textMuted }}><Icon name="chevR" size={18}/></div>
    </div>
  );
}

function FilterChip({ label, active, onClick, count }) {
  return (
    <button onClick={onClick} style={{
      cursor: 'pointer',
      padding: '8px 14px', borderRadius: 999,
      background: active ? HK.text : 'transparent',
      color: active ? HK.surface : HK.textDim,
      fontFamily: HK.fontUI, fontSize: 13, fontWeight: 600,
      display: 'inline-flex', alignItems: 'center', gap: 6,
      border: active ? '1px solid transparent' : `1px solid ${HK.hairlineStrong}`,
      transition: 'all 0.15s',
      whiteSpace: 'nowrap',
    }}>
      {label}
      {count != null && (
        <span style={{
          fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600,
          opacity: 0.6, marginLeft: 1,
        }}>{count}</span>
      )}
    </button>
  );
}

function HomeScreen({ onPickSong }) {
  const [query, setQuery] = React.useState('');
  const [filter, setFilter] = React.useState('All');
  const [songs, setSongs] = React.useState(FALLBACK_SONGS);

  React.useEffect(() => {
    fetch('songs.json')
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => { if (Array.isArray(data) && data.length) setSongs(data); })
      .catch(err => console.warn('[HomeScreen] songs.json not loaded, using fallback:', err));
  }, []);

  const counts = React.useMemo(() => ({
    All: songs.length,
    Beginner: songs.filter(s => s.diff === 'Beginner').length,
    Intermediate: songs.filter(s => s.diff === 'Intermediate').length,
    Advanced: songs.filter(s => s.diff === 'Advanced').length,
  }), [songs]);
  const filtered = songs.filter(s =>
    (filter === 'All' || s.diff === filter) &&
    (query === '' || s.title.toLowerCase().includes(query.toLowerCase()) || s.composer.toLowerCase().includes(query.toLowerCase()))
  );

  return (
    <div style={{
      position: 'absolute', inset: 0, paddingTop: 54, paddingBottom: 92,
      overflow: 'auto', background: HK.bg,
    }}>
      {/* Header */}
      <div style={{ padding: '8px 20px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Logo size={26}/>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={btnGlass}><Icon name="flame" size={18} color={HK.gold}/></button>
          <button style={btnGlass}><Icon name="profile" size={18} color={HK.text}/></button>
        </div>
      </div>

      {/* Greeting */}
      <div style={{ padding: '20px 20px 14px' }}>
        <div style={{ fontSize: 13, color: HK.textDim, fontFamily: HK.fontUI }}>晚安，Desmond</div>
        <div style={{ fontFamily: HK.fontDisplay, fontSize: 30, lineHeight: 1.1, color: HK.text, letterSpacing: -0.5, marginTop: 2 }}>
          今天要<br/>
          <span style={{ fontStyle: 'italic', color: HK.gold }}>練哪首曲子？</span>
        </div>
      </div>

      {/* Search */}
      <div style={{ padding: '0 20px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 14px', borderRadius: 14,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
        }}>
          <Icon name="search" size={18} color={HK.textMuted}/>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜尋曲名、作曲家、調性…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: HK.text, fontFamily: HK.fontUI, fontSize: 14,
            }}
          />
          <div style={{
            padding: '3px 7px', borderRadius: 5,
            background: HK.surface3, color: HK.textMuted,
            fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600,
          }}>⌘K</div>
        </div>
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex', gap: 8, padding: '16px 20px 14px',
        overflowX: 'auto', scrollbarWidth: 'none',
      }}>
        {FILTERS.map(f => (
          <FilterChip key={f.k} label={f.label} active={filter === f.k} count={counts[f.k]} onClick={() => setFilter(f.k)}/>
        ))}
      </div>

      {/* Section title */}
      <div style={{
        padding: '4px 20px 10px',
        display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
      }}>
        <div style={{ fontFamily: HK.fontUI, fontSize: 15, fontWeight: 600, color: HK.text }}>
          {filter === 'All' ? '精選曲目' : `${FILTERS.find(f => f.k === filter)?.label}曲目`}
        </div>
        <div style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textMuted }}>
          共 {filtered.length} 首
        </div>
      </div>

      {/* Featured card */}
      {(() => {
        const featured = filtered[0];
        const rest = filtered.slice(1);
        return (
          <>
            {featured && (
              <div style={{ padding: '0 20px 14px' }}>
                <SongCard song={featured} featured onClick={() => onPickSong && onPickSong(featured)}/>
              </div>
            )}
            <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {rest.map(s => (
                <SongCard key={s.id} song={s} onClick={() => onPickSong && onPickSong(s)}/>
              ))}
              {filtered.length === 0 && (
                <div style={{
                  padding: 40, textAlign: 'center', color: HK.textMuted,
                  fontFamily: HK.fontUI, fontSize: 13,
                }}>找不到「{query}」相關曲目</div>
              )}
            </div>
          </>
        );
      })()}

      <BottomNav active="home"/>
    </div>
  );
}

const btnGlass = {
  width: 38, height: 38, borderRadius: 19,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer',
};

Object.assign(window, { HomeScreen });
