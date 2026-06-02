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
    differences (the offset most pairs agree on). Robust to missing/spurious
    onsets. Returns (offset_seconds, votes, fraction_of_midi_onsets_matched)."""
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
    # histogram peak at `tol` resolution, then refine to the mean of the peak bin
    bins = np.round(diffs / tol).astype(int)
    vals, counts = np.unique(bins, return_counts=True)
    peak = vals[int(np.argmax(counts))]
    near = diffs[np.abs(diffs - peak * tol) <= tol]
    return (float(near.mean()), int(near.size), near.size / len(m))


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('recording', help='audio or video file (the performance)')
    ap.add_argument('midi', help='the played .mid')
    ap.add_argument('--max-offset', type=float, default=15.0)
    args = ap.parse_args()
    ao = audio_onsets(args.recording)
    mo = midi_onsets(args.midi)
    off, votes, frac = estimate_offset(ao, mo, max_offset=args.max_offset)
    print(f'audio onsets: {len(ao)}   midi onsets: {len(mo)}')
    print(f'offset δ (video ≈ midi + δ): {off:+.3f}s   '
          f'votes={votes} ({100 * frac:.0f}% of midi onsets matched)')
    if frac < 0.3:
        print('  ⚠ low match fraction — onset detection or the pairing is weak; '
              'check the recording / try a manual slate')


if __name__ == '__main__':
    main()
