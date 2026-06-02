// ProfileScreen — Achievements, stats, skill levels, settings entry.

const ACHIEVEMENTS = [
  { id: 'a1', name: '初次登台', icon: 'star',     color: '#FFD700', earned: true,  progress: 1,    desc: '完成首次練習' },
  { id: 'a2', name: '七日連續', icon: 'flame',    color: '#FF8C5A', earned: true,  progress: 1,    desc: '連續練習 7 天' },
  { id: 'a3', name: '巧手達人', icon: 'check',    color: '#5CE5A7', earned: true,  progress: 1,    desc: '單曲 95% 以上' },
  { id: 'a4', name: '夜貓樂手', icon: 'note',     color: '#B89DFB', earned: false, progress: 0.6,  desc: '深夜時段練習 10 次' },
  { id: 'a5', name: '節拍大師', icon: 'metronome',color: '#4FC3F7', earned: false, progress: 0.4,  desc: '時間準確度 90% 以上' },
  { id: 'a6', name: '百曲挑戰', icon: 'target',   color: '#FFD700', earned: false, progress: 0.27, desc: '完成 100 首曲目' },
];

const SKILLS = [
  { name: '指法',     value: 82, color: '#4FC3F7' },
  { name: '節奏',     value: 76, color: '#FFD700' },
  { name: '手部姿勢', value: 68, color: '#FF6B7A' },
  { name: '力度控制', value: 71, color: '#5CE5A7' },
  { name: '視譜速度', value: 64, color: '#B89DFB' },
];

function AchievementCard({ a }) {
  return (
    <div style={{
      padding: 14, borderRadius: 16,
      background: HK.surface2,
      border: `1px solid ${a.earned ? a.color + '40' : HK.hairline}`,
      position: 'relative', overflow: 'hidden',
      opacity: a.earned ? 1 : 0.65,
    }}>
      {a.earned && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          width: 16, height: 16, borderRadius: 8,
          background: a.color, color: HK.surface,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name="check" size={10} color={HK.surface} strokeWidth={2.5}/>
        </div>
      )}
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: `linear-gradient(135deg, ${a.color}40, ${a.color}10)`,
        border: `1px solid ${a.color}30`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 8,
      }}>
        <Icon name={a.icon} size={18} color={a.color}/>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: HK.text }}>{a.name}</div>
      <div style={{ fontSize: 10.5, color: HK.textDim, marginTop: 2, lineHeight: 1.35 }}>{a.desc}</div>
      {!a.earned && (
        <div style={{ marginTop: 8 }}>
          <div style={{ height: 3, background: HK.surface3, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              width: `${a.progress * 100}%`, height: '100%',
              background: a.color, borderRadius: 2,
            }}/>
          </div>
          <div style={{
            fontFamily: HK.fontMono, fontSize: 9, color: HK.textMuted,
            marginTop: 4, textAlign: 'right',
          }}>{Math.round(a.progress * 100)}%</div>
        </div>
      )}
    </div>
  );
}

function SkillBar({ s }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
        <span style={{ fontSize: 12, color: HK.text, fontWeight: 500 }}>{s.name}</span>
        <span style={{ fontFamily: HK.fontMono, fontSize: 12, color: s.color, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{s.value}</span>
      </div>
      <div style={{ height: 6, background: HK.surface3, borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${s.value}%`, height: '100%',
          background: `linear-gradient(90deg, ${s.color}aa, ${s.color})`,
          borderRadius: 3,
        }}/>
      </div>
    </div>
  );
}

function ProfileScreen() {
  return (
    <div style={{
      position: 'absolute', inset: 0, paddingTop: 54, paddingBottom: 92,
      overflow: 'auto', background: HK.bg,
    }}>
      {/* Header */}
      <div style={{ padding: '8px 20px 0', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button style={iconBtn2}><Icon name="bolt" size={18} color={HK.text}/></button>
        <button style={iconBtn2}><Icon name="more" size={18} color={HK.text}/></button>
      </div>

      {/* Profile hero */}
      <div style={{ padding: '14px 24px 18px', textAlign: 'center' }}>
        {/* avatar */}
        <div style={{
          width: 86, height: 86, borderRadius: 43,
          margin: '0 auto',
          background: `conic-gradient(from 90deg, ${HK.blue}, ${HK.gold}, ${HK.blue})`,
          padding: 3,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: '100%', height: '100%', borderRadius: '50%',
            background: `linear-gradient(135deg, ${HK.surface3}, ${HK.surface2})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: HK.fontDisplay, fontSize: 30, color: HK.text, fontStyle: 'italic',
          }}>亞</div>
        </div>
        <div style={{ fontFamily: HK.fontDisplay, fontSize: 26, color: HK.text, marginTop: 10, letterSpacing: -0.3 }}>
          亞歷克斯 <span style={{ fontStyle: 'italic', color: HK.gold }}>·</span> Level 7
        </div>
        <div style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textDim, marginTop: 2 }}>練琴 142 天 · 47 首曲目</div>

        {/* Level progress */}
        <div style={{
          marginTop: 14, padding: '10px 14px',
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
          borderRadius: 14,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted, marginBottom: 6 }}>
            <span>Lv. 7</span>
            <span>距 Lv. 8 還差 320 XP</span>
          </div>
          <div style={{ height: 6, background: HK.surface3, borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              width: '68%', height: '100%',
              background: `linear-gradient(90deg, ${HK.blue}, ${HK.gold})`,
              borderRadius: 3,
            }}/>
          </div>
        </div>
      </div>

      {/* Skills radar replaced with bars (cleaner on mobile) */}
      <div style={{ padding: '0 20px 16px' }}>
        <div style={{ fontFamily: HK.fontMono, fontSize: 10, fontWeight: 600, color: HK.textMuted, letterSpacing: 1.5, marginBottom: 10 }}>能力雷達</div>
        <div style={{
          padding: 16, borderRadius: 18,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
        }}>
          {SKILLS.map(s => <SkillBar key={s.name} s={s}/>)}
          <div style={{
            paddingTop: 8, borderTop: `1px solid ${HK.hairline}`,
            display: 'flex', justifyContent: 'space-between',
            fontFamily: HK.fontMono, fontSize: 10, color: HK.textMuted,
          }}>
            <span>綜合等級</span>
            <span style={{ color: HK.gold, fontWeight: 700 }}>72 · 中階琴手</span>
          </div>
        </div>
      </div>

      {/* Achievements */}
      <div style={{ padding: '0 24px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontFamily: HK.fontUI, fontSize: 15, fontWeight: 600, color: HK.text }}>成就徽章</div>
        <div style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textMuted }}>3 / 6</div>
      </div>
      <div style={{
        padding: '0 20px 16px',
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
      }}>
        {ACHIEVEMENTS.map(a => <AchievementCard key={a.id} a={a}/>)}
      </div>

      {/* Settings list */}
      <div style={{ padding: '0 20px 8px' }}>
        <div style={{
          borderRadius: 16,
          background: HK.surface2, border: `1px solid ${HK.hairline}`,
          overflow: 'hidden',
        }}>
          {[
            { icon: 'camera',    label: '攝影機與隱私', detail: '前置' },
            { icon: 'waveform',  label: '聲音與震動', detail: '預設' },
            { icon: 'metronome', label: '預設節拍器', detail: '76' },
            { icon: 'bolt',      label: '每日目標', detail: '20 分鐘' },
            { icon: 'profile',   label: '帳號與訂閱', detail: 'Pro', last: true },
          ].map((row, i, arr) => (
            <div key={row.label} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '14px 14px',
              borderBottom: i === arr.length - 1 ? 'none' : `1px solid ${HK.hairline}`,
              cursor: 'pointer',
            }}>
              <div style={{
                width: 30, height: 30, borderRadius: 8,
                background: HK.surface3,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon name={row.icon} size={15} color={HK.blue}/>
              </div>
              <div style={{ flex: 1, fontSize: 14, color: HK.text, fontWeight: 500 }}>{row.label}</div>
              <div style={{ fontFamily: HK.fontMono, fontSize: 11, color: HK.textMuted }}>{row.detail}</div>
              <Icon name="chevR" size={14} color={HK.textMuted}/>
            </div>
          ))}
        </div>
      </div>

      <BottomNav active="profile"/>
    </div>
  );
}

const iconBtn2 = {
  width: 38, height: 38, borderRadius: 19,
  background: HK.surface2, border: `1px solid ${HK.hairline}`,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  cursor: 'pointer',
};

Object.assign(window, { ProfileScreen });
