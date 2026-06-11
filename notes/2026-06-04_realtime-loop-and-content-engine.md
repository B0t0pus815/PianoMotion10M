# Session summary — Real-time learning loop + content engine (2026-06-01 → 06-04)

> NotebookLM source document. Self-contained narrative of one work session on the
> PianoMotion10M AI-piano-learning project. Covers what was built, **why**, how it
> was verified, the decisions/gotchas, the architecture, and the current state.
> 14 commits, +4,733 / −38 lines, 86 fast tests passing. All on the fork
> `B0t0pus815/PianoMotion10M`, branch `master`, head `2b217bc`.

---

## 0. TL;DR

The project is an **AI piano-learning system** built on PianoMotion10M. The
deliverable is a *working software (+ eventually hardware) system*, not a thesis.
This session did two big things and verified the whole thing end-to-end:

1. **Content engine** — a torch-free, CPU-only "Synthesia" practice-video
   generator (finger-numbered falling notes onto a lit keyboard), wired into the
   app, plus a one-command **`ingest_song.py`** that turns *any* MIDI into a
   playable practice song. The catalog went from 4 hardcoded demos to "drop in
   any piece."

2. **Real-time judging loop** — made the per-note feedback pipeline trustworthy:
   automatic audio↔MIDI sync (no manual slate), tempo-invariant note alignment
   (separates *wrong note* from *wrong finger*), a post-performance **report
   card** in the app, and an **end-to-end integration test** confirming
   runner → WebSocket → app → report card works with live data.

Headline outcome: the core learning loop is feature-complete and verified on
synthetic / replay data. The remaining frontier is **real data** (a real user
recording, or the Jetson hardware) — everything is staged and ready for it.

---

## 1. Background / the central design tension

PianoMotion10M generates hand-motion from MIDI. A long-standing problem (decided
*before* this session): the **rendered hands do not visually land on the lit
keys** — the assigned finger's tip is on the right key only ~67% of the time
("the 33% landing wart"). The diffusion line ("Route A", encoder surgery) cut L1
error 84% but still couldn't make hands land coherently, so it was rejected. The
rule-based biomech v4 template is locked. So "make the rendered template more
accurate" is a **converged decision, not an open task**.

This session's first arc routes *around* that problem instead of reopening it.

---

## 2. Content engine — the Synthesia practice view

### 2.1 Why
Rather than fix the GPU motion problem, adopt the industry (Synthesia / flowkey)
paradigm: **show finger-numbered note bars falling onto a lit keyboard.** The
finger number comes straight from the deterministic fingering engine, so it is
100% the recommended fingering — **there is no rendered hand to mismatch the
key.** This sidesteps the 33% wart entirely. It is also pure CPU (numpy/cv2 +
ffmpeg), so it needs no GPU.

### 2.2 `synthesia_view.py` (new, repo root)
- Renders falling note bars (RH amber, LH green) descending to a lit keyboard;
  the finger number on each bar comes from `generate_fingering()` (the Logic
  Track, ArLSTM by default).
- Reuses geometry from `add_keyboard_overlay.py` (`build_keyboard_image`, key
  geometry). White-key width 32 px; pipes raw BGR frames to `/usr/bin/ffmpeg`
  (the conda ffmpeg lacks libx264). ~110 fps render.
- **Critical sync rule:** video frame t=0 == song t=0 (no lead-in offset),
  because the app plays a *muted* `<video>` plus a *separate* `<audio>` track —
  an intro offset would make the falling notes hit keys before the sound.
- `--mp3` is optional. With no audio, it **synthesizes** a track from the MIDI.
  The synth was upgraded from a thin pure sine (`pretty_midi.synthesize`) to a
  small **additive synth**: each note = 6 decaying harmonics with an attack
  ramp + release fade, velocity-scaled, anti-aliased, normalized to 0.89 peak —
  piano-ish, soundfont-free, exactly MIDI-synced (commits `cbf28a1`, `150cd41`).

### 2.3 Four demo songs
- **Canon in D**, **菊次郎的夏天 (Summer)** — real recordings as audio.
- **Bach Invention No.1 BWV 772**, **Beethoven Sonata Op.2 No.1 mvt.I** — these
  are MIDI-only eval-corpus pieces with no recording, so their audio is the
  additive-synth track. They are **"Synthesia-only"** catalog entries (no
  biomech hands video, since that needs a GPU render).

### 2.4 App wiring (`webui/songs.json`, `webui/src/PracticeScreen.js`)
- songs.json gained `synthesiaUrl` (+ `audioUrl` to the synth wav for the
  MIDI-only pieces). Commits `687f0f2`, `f1dd0ae`.
- PracticeScreen got a **"手部示範 ↔ Synthesia 指法" view toggle** with an honest
  per-mode badge. A song with no `videoUrl` (Synthesia-only) **defaults to the
  Synthesia view and hides the toggle** rather than falling back to Canon's hands
  video. The toggle is built from whichever sources exist and only shows when
  more than one is available.
- A small reload fix: switching the view swaps the `<video src>`; on reload it
  seeks to the separate audio's position and resumes, so toggling mid-play keeps
  position and sync.

### 2.5 `ingest_song.py` (new, repo root) — the generalization
One command turns *any* MIDI into a playable practice song (commit `2b217bc`):
```
python ingest_song.py --midi MyPiece.mid --title "My Piece" --composer X
```
- Renders the Synthesia video (fingering embedded via the Logic Track).
- No `--mp3` → synthesizes audio from the MIDI.
- `--musicxml` attaches a score → enables the OSMD cursor (`scoreStartSec` /
  `scoreEndSec` from the MIDI's first/last onset; tempo estimated).
- Registers the song into `webui/songs.json` as a Synthesia-only entry.
  **Idempotent** — re-ingesting an id replaces it.
- **Boundary (honest):** new songs are Synthesia-only by design (the biomech
  "hands" video needs GPU). Live *judging* of an arbitrary new song still needs
  its biomech reference fingertips JSON (a GPU render). So ingest delivers the
  **practice content** (video + fingering + optional score), not the judge
  reference.

---

## 3. OSMD score cursor — tempo-precise + auto-scrolling

(`webui/src/OSMDScore.js`, commits `b8f07ae`, `60b89f8`.) Only **Canon** has a
MusicXML score, so this is "make the Canon cursor track the video."

- **Problem:** the old cursor advanced a flat "2 cursor steps/sec" — tempo-blind,
  ignored note durations, ignored the intro.
- **Fix:** on load, walk the cursor once and record each step's musical timestamp
  (whole notes). Then **linearly map the real music window `[scoreStartSec,
  scoreEndSec]`** (video seconds) onto the score's timestamp span. This honors
  note durations (a half note dwells 2× a quarter) and self-calibrates any
  constant tempo offset between the score's nominal BPM and the recording. The
  cursor moves incrementally (tracks its step index) instead of reset+re-advance
  every tick. `followCursor: true` auto-scrolls the score to keep the current
  note on screen.
- Canon music window = **[13.75 s, 183.16 s]** (the video has a ~13.75 s intro).
- Also fixed a cosmetic bug: the score header chip was a hardcoded "♩ = 76";
  now it reads `song.tempo` (Canon = 120, matching the rendered staff) and hides
  when unknown.
- **Verified** in headless Chrome (CDP): cursor advances reading-order-
  monotonically across all staff rows and stays visible at every sampled time.

---

## 4. Real-time judging — making per-note feedback trustworthy

The Phase B pipeline (`webui/realtime/`) judges a performance: webcam/MIDI →
MediaPipe hand tracking → comparator → WebSocket → React PracticeScreen. The
"Logic Track" (deterministic fingering, ArLSTM by default) decides the expected
finger; there is no generative model in the judgment path.

### 4.1 Note alignment — separate "wrong note" from "wrong finger"
(`webui/realtime/note_align.py` + integration, commits `6ded780`, `8d174de`.)

- **Problem:** the live loop greedily matched each played note to a nearby
  expected onset (±0.5 s, same pitch) and **silently dropped misses and extras**.
  So "did you play the right notes" was never measured — only fingering on the
  notes that happened to line up, conflating a wrong-note error with a
  wrong-finger error.
- **Solution:** a global **Needleman–Wunsch alignment** of the played vs expected
  pitch sequences (chords sorted by pitch). It is **tempo-invariant** (aligns by
  note *order*, not absolute time), so playing the right notes at any tempo
  scores 100%. It surfaces **correct / wrong / missing / extra** counts, the
  matched pairs, and a played→reference **time warp** (least-squares tempo
  scale/offset, used later for A/V sync). Standalone CLI:
  `python -m webui.realtime.note_align played.mid reference.mid`.
- **Wired into the live judge (replay mode):** the runner now attributes each
  played note via the global alignment instead of the greedy search — misses/
  extras/tempo-drift no longer shift later notes onto the wrong onset, and every
  matched note gets judged.
- **Gotcha fixed:** `generate_fingering` offsets some `ExpectedOnset` times by
  **−50 ms**, which reordered near-simultaneous notes and fabricated ~6% spurious
  miss/extra even on identity. Fix: align against the **faithful raw reference
  notes** (`notes_from_midi`) and bridge raw→expected by **(pitch, occurrence-
  rank)**, which is stable under per-note time offsets (`build_match_map`).
- **Verified end-to-end:** replay canon-vs-canon = `[align] 296/296` matched
  (was 279 before the bridge fix), note accuracy **100.0%**, every onset judged.

### 4.2 Audio↔MIDI auto-sync — no manual slate
(`webui/realtime/av_sync.py`, commits `8c0b5c9`, `394765b`; runner `--auto-sync`
in `4e30b58`.)

- **Why:** a user records video + MIDI on separate devices started at slightly
  different times. The pipeline must put MIDI onsets on the video clock. Asking
  every user to clap a "slate" is fragile.
- **Approach:** the audio in the recording and the captured MIDI are the same
  performance, so their onset trains differ only by a constant offset δ
  (video_time ≈ midi_time + δ); tempo drift ≈ 0. Detect audio onsets (librosa)
  and find δ.
- **Important lesson — the first version was wrong.** A naive *onset-time
  difference vote* is **ambiguous for near-evenly-spaced pieces**: on Canon it
  locked onto **−3.55 s** (= −2 × the ~1.76 s onset period) by a 1-vote margin,
  because shifting by a multiple of the onset period also aligns most onsets.
  That wrong lock looked like a "91% match success" and **almost got mis-read as
  an A/V desync in the demo videos.** Verifying independently (the first MIDI
  onset == the second audio onset, 13.75 == 13.75) showed the videos are
  **actually aligned** (true δ ≈ 0) — no desync.
- **Fix:** `estimate_offset_xcorr` — cross-correlate the audio onset-*strength
  envelope* against a *velocity-weighted* MIDI impulse train. The amplitude
  pattern (dynamics/voicing — which is NOT periodic) disambiguates the period
  multiples.
- **Validated on real audio:** Canon MP3 vs `canon_clean.mid` → δ = **+0.05 s**
  (correct), and an injected +4.2 s shift recovered to +4.25 s.
- **Runner `--auto-sync`:** estimates δ and runs MIDI polling + hand history on
  the MIDI clock via `frame.timestamp − δ` (clip recording stays on the video
  clock). `--sync-audio` overrides the source; estimation failure falls back to
  δ = 0. Verified e2e: replay with `--auto-sync` computes δ = +0.046 s, still
  `[align] 296/296`, note accuracy 100%.

### 4.3 Post-performance report card (`webui/src/PracticeScreen.js`, `011c31f`)
Closes the learning loop *visibly*. On WS `done` or video-end, the app shows a
report built from the streamed onset events + the runner's note-level summary:
- **note-accuracy** and **fingering-accuracy** rings; correct / wrong-finger /
  missing / extra chips;
- **per-segment accuracy bars** (onsets bucketed by time) with the **weakest
  stretch** highlighted and labeled (e.g. "最弱：0:52–1:04 這段");
- the specific **wrong-fingering notes** ("used X → should be Y");
- a **wrist** summary; **再練一次** (remounts the video from 0) / **關閉**.

`summarizePerformance` is a pure function; `useFeedbackStream` now retains fired
onsets and handles the `done` event. Verified in headless Chrome with mock data
(rings 91/73, weakest flagged, 8 wrong-note rows, no JS errors).

### 4.4 End-to-end integration verified
Ran the full chain together (headless Chrome via CDP): `serve.py` + the app
(retrying the WS) + the **real runner** (replay canon, broadcaster on 8766).
Observed: app went `connected=true` with the real `ready` (onsetCount = 296),
live stats incremented from real `onset` events, and the **report card rendered
from the real `done` event** with real wrong-finger rows, **zero JS errors**.
The careful component-level verification paid off — **no seam bugs.** The live
hardware path uses this same WS→app chain, so this de-risks the eventual
Jetson bring-up. (Note: the broadcaster is *live-only*, no replay buffer, so a
client must connect before/during a run.)

---

## 5. Repo hygiene — fork made self-contained (`b84ae72`)

Discovered mid-session: `webui/` was only **partially tracked** in git — the
committed files imported untracked ones (`tokens.js`/`HK`, `PianoRoll.js`,
`App.js`, and the realtime `hand_tracker` / `reference` / `broadcaster` /
`clip_recorder` / package `__init__.py`). So a fresh clone of the fork could not
run the app or the pipeline. Nothing was `.gitignore`d — an oversight. Added the
19 missing source files; the fork is now self-contained.

---

## 6. Architecture / data flow (real-time judging)

```
 webcam frames ─► MediaPipe (hand_tracker) ─► HandHistory ─┐
                                                            ├─► comparator.compare_onset
 MIDI (live port or .mid replay) ─► onsets ────────────────┘     (which finger pressed,
        │                                                          via fingertip y-velocity)
        ├─ generate_fingering (Logic Track, ArLSTM) ─► expected finger per onset
        ├─ note_align ─► correct/wrong/missing/extra + played↔expected match + warp
        └─ av_sync (--auto-sync) ─► δ, shifts the MIDI clock onto the video clock
                                                            │
            broadcaster (WebSocket :8766) ◄── per-onset results + 'done' summary
                                                            │
   React app: useFeedbackStream ─► live stats + FeedbackOverlay ─► ReportCard (on 'done')
```

Key facts: fingering judgment is **finger-identity by motion** (which of the 5
fingers moved down most) — it does **not** need keyboard-pixel calibration, which
is what makes a casually-recorded real user video viable. The MIDI provides the
*when* and *which note*; MediaPipe provides the *which finger*.

---

## 7. New / changed files (this session)

New scripts: `synthesia_view.py`, `ingest_song.py`.
New realtime modules: `webui/realtime/note_align.py`, `webui/realtime/av_sync.py`.
New tests: `tests/test_note_align.py`, `tests/test_av_sync.py`, `tests/test_ingest.py`.
First-time-tracked (fork fix): the rest of `webui/` (frontend screens + tokens +
realtime hand_tracker/reference/broadcaster/clip_recorder + serve.py + README).
Modified: `webui/src/PracticeScreen.js`, `OSMDScore.js`, `songs.json`,
`webui/realtime/runner.py`, `sources.py`.

Generated artifacts (gitignored, under `results/`): `canon_synthesia.mp4`,
`summer_synthesia.mp4`, `bach_invention_synthesia.mp4`,
`beethoven_op2no1_synthesia.mp4` (+ `*_synth.wav` for the MIDI-only ones).

---

## 8. How to run things

```bash
# serve the app
python webui/serve.py 8765            # → http://localhost:8765/webui/

# generate a practice song from any MIDI
python ingest_song.py --midi input_songs/MyPiece.mid --title "My Piece"

# grade a played MIDI against a reference (note accuracy, wrong/missing/extra)
python -m webui.realtime.note_align played.mid results/canon_clean.mid

# find the A/V offset between a recording and its MIDI
python -m webui.realtime.av_sync recording.mp4 played.mid

# run the live judging pipeline (replay mode), broadcasting to the app
python -m webui.realtime.runner \
  --video results/canon_biomech_v4_kb.mp4 --midi results/canon_clean.mid \
  --reference results/canon_biomech_v4_fingertips.json \
  --fingering-source pianoplayer --auto-sync \
  --fast --no-preview --ws-port 8766 --ws-linger 600

# tests
python -m pytest tests/ -q --ignore=tests/test_audit_pipeline_integration.py   # 86 fast tests
```

---

## 9. Current state & what's left

**Done & verified (synthetic / replay data):** content engine (4 Synthesia
songs + any-MIDI ingest), tempo-precise OSMD cursor, note alignment, alignment-
driven fingering attribution, audio↔MIDI auto-sync, report card, end-to-end
chain. 86 fast tests pass. Fork self-contained.

**The remaining frontier is real data** — everything is staged for it:
- *Highest leverage:* run a **real user recording** (video + the keyboard's
  exported MIDI, dropped into `user_recordings/`) through the pipeline to get
  real numbers and tune the currently-untunable thresholds (press detection,
  tracking quality). The `note_align` CLI already grades a real MIDI the moment
  it arrives.
- *Hardware:* the Jetson Xavier NX + Casio CT-S300 (61-key, MIDI 36–96) + USB
  camera + tablet bring-up. The `deploy/` package is turnkey but unproven on the
  board. The live path uses the same WS→app chain just verified.

**Data-independent backlog (if staying in code):** auto-generate MusicXML from
MIDI in ingest (so ingested songs also get the OSMD score/cursor); local
persistence + History/Profile screens (progress over time); finger-curvature
feedback (geometry computable now, thresholds need real hand data); codify the
e2e smoke test into the suite.

**Explicitly NOT open (converged decisions):** raising the rendered-hand landing
accuracy (Route A trade-off — Synthesia routes around it); writing the thesis
(deliverable is the working system).

---

## 10. Commit log (newest first), all on `myfork/master`

```
2b217bc feat: ingest_song.py — any MIDI → playable practice song (one command)
011c31f feat: post-performance report card (note + finger accuracy, weakest section)
4e30b58 feat: runner --auto-sync — align MIDI to the recording via av_sync
394765b fix:  av_sync uses onset-envelope cross-correlation (robust to periodic music)
8c0b5c9 feat: audio<->MIDI auto-sync (av_sync) — find the A/V offset, no manual slate
b84ae72 chore: track the rest of webui/ so the fork is self-contained
8d174de feat: drive live fingering attribution from the global alignment (replay)
6ded780 feat: tempo-invariant note alignment — decouple note accuracy from fingering
60b89f8 fix:  score header shows the real tempo (from song.tempo), not a hardcoded ♩=76
b8f07ae feat: tempo-precise, auto-scrolling OSMD score cursor
150cd41 feat: piano-ish additive synth for MIDI-only audio (replaces pure sine)
f1dd0ae feat: add Bach Invention + Beethoven Op.2 No.1 as Synthesia-only songs
cbf28a1 feat: synthesia_view auto-synthesizes audio for MIDI-only pieces
687f0f2 feat: no-hand Synthesia view — finger-numbered falling notes, zero hand-mismatch
```
