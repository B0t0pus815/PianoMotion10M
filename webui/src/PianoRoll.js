// PianoRoll — falling-keys canvas synced with the practice <video>.
// Notes scroll from top to a hit line; below it sits an 88-key keyboard.
// Status (correct / wrong / missed) is applied as each note crosses
// the hit line — driven by the runner's WS onset events.
//
// X-geometry mirrors webui/realtime/reference.py / add_keyboard_overlay.py
// (52 white keys filling the canvas width), so a Canon C-major chord on
// the roll lines up with the same C-major keys on the keyboard.

const PR_MIDI_MIN = 21;
const PR_MIDI_MAX = 108;
const PR_BLACK_OFFSETS = new Set([1, 3, 6, 8, 10]);
const PR_WHITE_OFFSET_TABLE = [0, 0, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6];

function prIsBlack(p) { return PR_BLACK_OFFSETS.has(((p % 12) + 12) % 12); }
function prWhiteIdx(p) {
  const inOct = ((p - 21) % 12 + 12) % 12;
  const oct = Math.floor((p - 21) / 12);
  return oct * 7 + PR_WHITE_OFFSET_TABLE[inOct];
}
const PR_TOTAL_WHITE = prWhiteIdx(PR_MIDI_MAX) + 1; // 52

function prPitchCenterX(pitch, frameWidth) {
  const whiteW = frameWidth / PR_TOTAL_WHITE;
  const wi = prWhiteIdx(pitch);
  return prIsBlack(pitch) ? (wi + 1) * whiteW : (wi + 0.5) * whiteW;
}

function prPitchBarWidth(pitch, frameWidth) {
  const whiteW = frameWidth / PR_TOTAL_WHITE;
  return prIsBlack(pitch) ? whiteW * 0.62 : whiteW * 0.92;
}

// Color palette pulled from tokens.js HK (with fallback hexes if HK isn't
// loaded yet — tokens.js loads first per index.html but keep defensive).
function prColors() {
  return {
    bg:        (typeof HK !== 'undefined' && HK.surface) || '#101822',
    grid:      'rgba(234,242,251,0.06)',
    hitLine:   (typeof HK !== 'undefined' && HK.gold) || '#F5B544',
    keyWhite:  '#e8eef5',
    keyBlack:  '#0a1622',
    keyEdge:   'rgba(80,90,110,0.7)',
    right:     (typeof HK !== 'undefined' && HK.blue) || '#5B9DFF',
    left:      (typeof HK !== 'undefined' && HK.green) || '#52D89C',
    wrong:     (typeof HK !== 'undefined' && HK.red) || '#FF5470',
    missed:    (typeof HK !== 'undefined' && HK.textMuted) || '#6d7a8a',
    text:      '#ffffff',
  };
}

const PR_FINGER_NUM = { thumb: '1', index: '2', middle: '3', ring: '4', pinky: '5' };

function PianoRoll({
  notes,
  statusMap,
  currentTimeRef,
  lookAhead = 4.0,
  height = 240,
  keyboardHeight = 56,
}) {
  const canvasRef = React.useRef(null);
  const wrapRef = React.useRef(null);
  const statusRef = React.useRef(statusMap || {});
  React.useEffect(() => { statusRef.current = statusMap || {}; }, [statusMap]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    let raf = 0;

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const w = Math.max(320, Math.floor(rect.width));
      canvas.width = w * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const C = prColors();
    const safeNotes = Array.isArray(notes) ? notes : [];

    const draw = () => {
      const W = parseFloat(canvas.style.width) || canvas.width / dpr;
      const H = height;
      const hitY = H - keyboardHeight;
      const pxPerSec = hitY / lookAhead;
      const t = (currentTimeRef && currentTimeRef.current) || 0;
      const sm = statusRef.current || {};

      // ─ background
      ctx.fillStyle = C.bg;
      ctx.fillRect(0, 0, W, H);

      // ─ 1-second grid (subtle horizontal lines that scroll with playback)
      ctx.strokeStyle = C.grid;
      ctx.lineWidth = 1;
      const firstSec = Math.ceil(t);
      for (let s = firstSec; s < t + lookAhead + 0.5; s++) {
        const y = hitY - (s - t) * pxPerSec;
        if (y < 0 || y > hitY) continue;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      }

      // ─ falling notes
      ctx.lineWidth = 1;
      for (const n of safeNotes) {
        const dy = (n.start - t) * pxPerSec;
        const noteTop = hitY - dy - n.dur * pxPerSec;
        const noteBot = hitY - dy;
        if (noteBot < -8 || noteTop > hitY + 4) continue;

        const cx = prPitchCenterX(n.pitch, W);
        const w = prPitchBarWidth(n.pitch, W);
        const x = cx - w / 2;
        const status = sm[n.i];
        const isPlaying = t >= n.start && t < n.start + n.dur + 0.05;
        const isPast = t >= n.start + Math.min(0.08, n.dur);

        let fill = n.hand === 'right' ? C.right : C.left;
        let alpha = 0.88;
        let glow = false;
        if (status === 'correct') { alpha = 1.0; glow = true; }
        else if (status === 'wrong') { fill = C.wrong; alpha = 1.0; glow = true; }
        else if (status === 'missed') { fill = C.missed; alpha = 0.55; }
        else if (isPlaying && !status) { alpha = 1.0; }

        // fade older past notes that never received a status (e.g. when WS is offline)
        if (isPast && !status && !isPlaying) {
          const age = t - (n.start + Math.min(0.08, n.dur));
          alpha = Math.max(0.18, alpha - age * 0.55);
        }

        ctx.globalAlpha = alpha;
        const top = Math.max(noteTop, -8);
        const bot = Math.min(noteBot, hitY + 1);
        const rectH = Math.max(2, bot - top);

        ctx.fillStyle = fill;
        if (glow) {
          ctx.shadowBlur = 12;
          ctx.shadowColor = fill;
        }
        if (typeof ctx.roundRect === 'function') {
          ctx.beginPath();
          ctx.roundRect(x, top, w, rectH, 3);
          ctx.fill();
        } else {
          ctx.fillRect(x, top, w, rectH);
        }
        ctx.shadowBlur = 0;

        // expected-finger label near the hit line (only on tall notes)
        if (n.finger && rectH > 14 && dy < pxPerSec * 1.6 && dy > -pxPerSec * 0.4) {
          ctx.globalAlpha = Math.min(1, alpha + 0.15);
          ctx.fillStyle = C.text;
          ctx.font = 'bold 11px "JetBrains Mono", ui-monospace, monospace';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(PR_FINGER_NUM[n.finger] || '?', cx, Math.min(bot - 8, hitY - 6));
        }
      }
      ctx.globalAlpha = 1;

      // ─ hit line
      ctx.strokeStyle = C.hitLine;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, hitY);
      ctx.lineTo(W, hitY);
      ctx.stroke();

      // ─ keyboard (88 keys)
      drawKeyboard(ctx, W, hitY, keyboardHeight);

      // ─ highlight currently-playing keys
      for (const n of safeNotes) {
        if (!(t >= n.start && t < n.start + n.dur)) continue;
        const cx = prPitchCenterX(n.pitch, W);
        const whiteW = W / PR_TOTAL_WHITE;
        const w = prIsBlack(n.pitch) ? whiteW * 0.62 : whiteW * 0.92;
        const x = cx - w / 2;
        const h = prIsBlack(n.pitch) ? keyboardHeight * 0.62 : keyboardHeight - 2;
        const status = sm[n.i];
        const fill = status === 'wrong' ? C.wrong : (n.hand === 'right' ? C.right : C.left);
        ctx.globalAlpha = 0.78;
        ctx.fillStyle = fill;
        ctx.fillRect(x, hitY + 1, w, h);
      }
      ctx.globalAlpha = 1;

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, [notes, height, keyboardHeight, lookAhead, currentTimeRef]);

  return (
    <div ref={wrapRef} style={{
      width: '100%',
      borderRadius: 12,
      overflow: 'hidden',
      border: `1px solid ${(typeof HK !== 'undefined' && HK.hairlineStrong) || 'rgba(255,255,255,0.08)'}`,
      boxShadow: '0 6px 18px rgba(0,0,0,0.4)',
      background: '#0a1622',
    }}>
      <canvas ref={canvasRef} style={{ display: 'block' }}/>
    </div>
  );
}

function drawKeyboard(ctx, W, kbY, kbH) {
  const C = prColors();
  const whiteW = W / PR_TOTAL_WHITE;
  ctx.fillStyle = '#1a2530';
  ctx.fillRect(0, kbY, W, kbH);

  // white keys first
  for (let p = PR_MIDI_MIN; p <= PR_MIDI_MAX; p++) {
    if (prIsBlack(p)) continue;
    const wi = prWhiteIdx(p);
    const x = wi * whiteW;
    ctx.fillStyle = C.keyWhite;
    ctx.fillRect(x + 0.5, kbY + 1, whiteW - 1, kbH - 2);
    ctx.strokeStyle = C.keyEdge;
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, kbY + 1, whiteW - 1, kbH - 2);

    // octave C labels (subtle)
    if ((p - 21) % 12 === 3) {  // C = pitch 24, 36, ... ; (24-21)%12==3
      ctx.fillStyle = 'rgba(60,70,90,0.65)';
      ctx.font = '8px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      const oct = Math.floor((p - 12) / 12);
      ctx.fillText(`C${oct}`, x + whiteW / 2, kbY + kbH - 2);
    }
  }
  // black keys
  for (let p = PR_MIDI_MIN; p <= PR_MIDI_MAX; p++) {
    if (!prIsBlack(p)) continue;
    const cx = prPitchCenterX(p, W);
    const w = whiteW * 0.62;
    ctx.fillStyle = C.keyBlack;
    ctx.fillRect(cx - w / 2, kbY + 1, w, kbH * 0.62);
  }
}

Object.assign(window, { PianoRoll });
