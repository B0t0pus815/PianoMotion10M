// OSMDScore — wraps OpenSheetMusicDisplay to render a MusicXML score
// inside React.
//
// Falls back to the legacy Staff placeholder (see PracticeScreen.js
// MEASURE_1 / MEASURE_2) when scoreUrl is undefined or OSMD library
// failed to load.
//
// Highlighting hook: pass `highlightTime` (seconds) and the component
// will dim past notes and highlight the current/upcoming note.
// Implemented via the OSMD cursor; advance is automatic on highlight
// time change.

const OSMDScore = ({ scoreUrl, highlightTime = 0, height = 220, fallback = null }) => {
  const containerRef = React.useRef(null);
  const osmdRef = React.useRef(null);
  const [ready, setReady] = React.useState(false);
  const [error, setError] = React.useState(null);

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
        followCursor: false,
      }
    );

    osmd
      .load(scoreUrl)
      .then(() => {
        osmd.render();
        osmd.cursor.show();
        osmdRef.current = osmd;
        setReady(true);
      })
      .catch(err => {
        console.error('OSMD load failed:', err);
        setError(String(err));
      });

    return () => {
      try { osmd.clear?.(); } catch (e) {}
      osmdRef.current = null;
    };
  }, [scoreUrl]);

  // Advance cursor based on highlight time. This is best-effort —
  // OSMD doesn't know real-time seconds, only musical beats. We use
  // a rough "1 beat per ~0.5s" heuristic; for better sync the score
  // would need explicit MIDI tempo + time mapping.
  React.useEffect(() => {
    const osmd = osmdRef.current;
    if (!osmd || !ready) return;
    // Reset to start, then advance N times where N proportional to time.
    // (Cheap approximation; real sync would parse <sound tempo=...> tags.)
    try {
      osmd.cursor.reset();
      const steps = Math.floor(highlightTime * 2);  // ~2 cursor steps/sec
      for (let i = 0; i < steps; i++) osmd.cursor.next();
    } catch (e) {}
  }, [highlightTime, ready]);

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
