"""av_sync.py — estimate the time offset between a recording (audio/video) and a
MIDI performance, so the realtime pipeline can put MIDI onsets on the video clock
WITHOUT a manual slate.

The audio in a recording and the captured MIDI are the SAME performance, so their
note-onset trains differ only by a constant offset δ — the difference in when the
two recordings were started; tempo drift between them is ≈ 0. We detect note
onsets in the audio (librosa) and find the δ that best lines the two onset trains
up via a robust difference-histogram vote (tolerant of missed/spurious onsets, so
a noisy phone recording or an intro before the first note doesn't throw it off).

Returns δ such that  video_time ≈ midi_time + δ  → the runner converts a video
frame time to MIDI time with (frame_time − δ), aligning hand poses to onsets.

CLI:  python -m webui.realtime.av_sync recording.mp4 played.mid
"""

import os
import subprocess
import tempfile

import numpy as np

FFMPEG = '/usr/bin/ffmpeg'   # system ffmpeg (conda's lacks codecs); see reference_compute


def audio_onsets(path: str, sr: int = 22050) -> np.ndarray:
    """Onset times (seconds) in a recording. Normalizes through ffmpeg → mono wav
    first, so mp3 / mp4 / mov / wav all work uniformly."""
    import librosa
    fd, wav = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        subprocess.run([FFMPEG, '-y', '-i', path, '-ac', '1', '-ar', str(sr), wav],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        y, _ = librosa.load(wav, sr=sr, mono=True)
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    return librosa.onset.onset_detect(y=y, sr=sr, units='time', backtrack=True)


def midi_onsets(path: str) -> np.ndarray:
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(path)
    ts = sorted(float(n.start) for inst in pm.instruments if not inst.is_drum
                for n in inst.notes)
    return np.asarray(ts, dtype=float)


def estimate_offset(audio_onsets_s, midi_onsets_s,
                    max_offset: float = 15.0, tol: float = 0.05) -> tuple:
    """δ where audio_time ≈ midi_time + δ, by voting on pairwise onset
    differences (the offset most pairs agree on). Returns (offset_seconds, votes,
    fraction_of_midi_onsets_matched).

    ⚠ AMBIGUOUS for near-evenly-spaced onsets (e.g. a steady chordal piece like
    Canon): shifting by a multiple of the onset period also aligns most onsets,
    so the vote can lock onto the wrong period multiple. Prefer
    estimate_offset_xcorr, which disambiguates via the amplitude pattern. Kept as
    a low-level helper / fallback when only onset times are available."""
    a = np.asarray(sorted(audio_onsets_s), dtype=float)
    m = np.asarray(sorted(midi_onsets_s), dtype=float)
    if a.size == 0 or m.size == 0:
        return (0.0, 0, 0.0)
    diffs = []
    for mt in m:
        sel = a[(a >= mt - max_offset) & (a <= mt + max_offset)]
        if sel.size:
            diffs.append(sel - mt)
    if not diffs:
        return (0.0, 0, 0.0)
    diffs = np.concatenate(diffs)
    bins = np.round(diffs / tol).astype(int)
    vals, counts = np.unique(bins, return_counts=True)
    peak = vals[int(np.argmax(counts))]
    near = diffs[np.abs(diffs - peak * tol) <= tol]
    return (float(near.mean()), int(near.size), near.size / len(m))


def best_lag_frames(sig_a: np.ndarray, sig_b: np.ndarray, max_lag: int) -> int:
    """Integer lag L (frames) in [-max_lag, max_lag] maximizing the cross-
    correlation of sig_a with sig_b, where sig_a[n] aligns with sig_b[n - L].
    (So L>0 means sig_a is delayed relative to sig_b.)"""
    from scipy.signal import correlate
    a = np.asarray(sig_a, dtype=float)
    b = np.asarray(sig_b, dtype=float)
    if a.size == 0 or b.size == 0:
        return 0
    c = correlate(a, b, mode='full')
    lag_axis = np.arange(c.size) - (b.size - 1)   # sig_a[n] ~ sig_b[n - lag]
    mask = np.abs(lag_axis) <= max_lag
    masked = np.where(mask, c, -np.inf)
    return int(lag_axis[int(np.argmax(masked))])


def estimate_offset_xcorr(recording_path: str, midi_path: str,
                          max_offset: float = 15.0, sr: int = 22050,
                          hop: int = 512) -> tuple:
    """Robust δ (video ≈ midi + δ) via cross-correlating the audio onset-strength
    envelope against a velocity-weighted MIDI onset impulse train. The amplitude
    pattern (which is NOT periodic — dynamics/voicing vary) disambiguates the
    onset-period multiples that defeat estimate_offset. Returns (offset_seconds,
    peak_correlation, normalized_peak)."""
    import librosa
    import pretty_midi

    fd, wav = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        subprocess.run([FFMPEG, '-y', '-i', recording_path, '-ac', '1', '-ar', str(sr), wav],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        y, _ = librosa.load(wav, sr=sr, mono=True)
    finally:
        if os.path.exists(wav):
            os.remove(wav)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop).astype(float)
    fps = sr / hop

    pm = pretty_midi.PrettyMIDI(midi_path)
    notes = [(float(n.start), int(n.velocity))
             for inst in pm.instruments if not inst.is_drum for n in inst.notes]
    train = np.zeros(env.size, dtype=float)
    for t, vel in notes:
        f = int(round(t * fps))
        if 0 <= f < train.size:
            train[f] += vel / 127.0
    if env.std() > 0:
        env = (env - env.mean()) / env.std()      # zero-mean so silence doesn't dominate

    lag = best_lag_frames(env, train, int(round(max_offset * fps)))
    # correlation quality at the chosen lag (normalized)
    from scipy.signal import correlate
    c = correlate(env, train, mode='full')
    peak = float(c.max())
    norm = peak / (np.linalg.norm(env) * np.linalg.norm(train) + 1e-9)
    return (lag / fps, peak, norm)


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('recording', help='audio or video file (the performance)')
    ap.add_argument('midi', help='the played .mid')
    ap.add_argument('--max-offset', type=float, default=15.0)
    args = ap.parse_args()
    off, peak, norm = estimate_offset_xcorr(args.recording, args.midi,
                                            max_offset=args.max_offset)
    print(f'offset δ (video ≈ midi + δ): {off:+.3f}s   '
          f'(envelope x-corr, normalized peak {norm:.3f})')
    if norm < 0.05:
        print('  ⚠ weak correlation — check the recording / try a manual slate')


if __name__ == '__main__':
    main()
