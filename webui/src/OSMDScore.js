// OSMDScore — wraps OpenSheetMusicDisplay to render a MusicXML score
// inside React.
//
// Falls back to the legacy Staff placeholder (see PracticeScreen.js
// MEASURE_1 / MEASURE_2) when scoreUrl is undefined or OSMD library
// failed to load.
//
// Highlighting hook: pass `highlightTime` (seconds, = video currentTime) and
// the cursor tracks the note currently sounding.
//
// Sync model (tempo-precise, replaces the old flat "2 steps/sec" guess):
// on load we walk the cursor once and record each step's musical timestamp
// (whole notes from start) from OSMD's iterator, so note durations are honored
// (a half note dwells 2x a quarter). Real-time → musical position is a LINEAR
// map of the actual music window [startSec, endSec] (video seconds; the video
// often has an intro before the first note) onto the score's full timestamp
// span. That self-calibrates any constant tempo offset between the score's
// nominal BPM and the recording, and lands the cursor on the right note
// end-to-end. (Residual: piece-internal rubato — out of scope.)

const OSMDScore = ({ scoreUrl, highlightTime = 0, startSec = 0, endSec = null,
                    height = 220, fallback = null }) => {
  const containerRef = React.useRef(null);
  const osmdRef = React.useRef(null);
  const stepTsRef = React.useRef([]);   // musical timestamp (whole notes) per cursor step
  const tsTotalRef = React.useRef(0);   // timestamp of the last step
  const stepRef = React.useRef(0);      // cursor's current step index (for incremental moves)
  const [ready, setReady] = React.useState(false);
  const [error, setError] = React.useState(null);

  const iterOf = (cursor) => cursor.Iterator || cursor.iterator;

  React.useEffect(() => {
    if (!scoreUrl) return;
    if (typeof opensheetmusicdisplay === 'undefined') {
      setError('OSMD library not loaded');
      return;
    }
    if (!containerRef.current) return;

    const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(
      containerRef.current,
      {
        autoResize: true,
        backend: 'svg',
        drawTitle: false,
        drawSubtitle: false,
        drawComposer: false,
        drawPartNames: false,
        drawingParameters: 'compact',
        followCursor: true,   // auto-scroll the score container to keep the cursor in view
      }
    );

    osmd
      .load(scoreUrl)
      .then(() => {
        osmd.render();
        osmd.cursor.show();
        osmdRef.current = osmd;

        // Walk the cursor once to capture each step's musical timestamp.
        const ts = [];
        try {
          osmd.cursor.reset();
          let guard = 0;
          while (!iterOf(osmd.cursor).EndReached && guard < 100000) {
            ts.push(iterOf(osmd.cursor).currentTimeStamp.RealValue);
            osmd.cursor.next();
            guard++;
          }
          osmd.cursor.reset();
        } catch (e) {
          console.warn('OSMD timestamp walk failed, cursor sync degraded:', e);
        }
        stepTsRef.current = ts;
        tsTotalRef.current = ts.length ? ts[ts.length - 1] : 0;
        stepRef.current = 0;
        setReady(true);
      })
      .catch(err => {
        console.error('OSMD load failed:', err);
        setError(String(err));
      });

    return () => {
      try { osmd.clear?.(); } catch (e) {}
      osmdRef.current = null;
      stepTsRef.current = [];
      tsTotalRef.current = 0;
      stepRef.current = 0;
    };
  }, [scoreUrl]);

  // Map real time → target cursor step and move there incrementally.
  React.useEffect(() => {
    const osmd = osmdRef.current;
    const stepTs = stepTsRef.current;
    if (!osmd || !ready || !stepTs.length) return;
    try {
      const tsTotal = tsTotalRef.current || 1;
      // music window → score timestamp span (linear). Fallback span assumes
      // 120 BPM (0.5 whole notes/sec) when endSec is not supplied.
      const span = (endSec != null && endSec > startSec)
        ? (endSec - startSec)
        : (tsTotal * 2);
      const frac = Math.max(0, Math.min(1, (highlightTime - startSec) / span));
      const targetTs = frac * tsTotal;
      // largest index with stepTs[idx] <= targetTs (binary search; monotonic)
      let lo = 0, hi = stepTs.length - 1, idx = 0;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (stepTs[mid] <= targetTs + 1e-9) { idx = mid; lo = mid + 1; }
        else hi = mid - 1;
      }
      // move cursor from its current step to idx
      let cur = stepRef.current;
      if (idx < cur) { osmd.cursor.reset(); cur = 0; }
      while (cur < idx && !iterOf(osmd.cursor).EndReached) { osmd.cursor.next(); cur++; }
      stepRef.current = cur;
    } catch (e) {}
  }, [highlightTime, startSec, endSec, ready]);

  if (!scoreUrl || error) {
    return fallback;
  }

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      height,
      overflow: 'auto',
      background: '#fff',
      borderRadius: 12,
      padding: 8,
    }}>
      <div ref={containerRef} style={{ width: '100%', minHeight: height - 16 }}/>
      {!ready && (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#666', fontFamily: 'ui-monospace, monospace', fontSize: 10,
        }}>
          載入樂譜…
        </div>
      )}
    </div>
  );
};
