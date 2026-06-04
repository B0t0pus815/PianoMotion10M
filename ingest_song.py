"""
ingest_song.py — turn any MIDI into a playable practice song in one command.

Renders a no-hand Synthesia practice video (finger-numbered falling notes onto a
lit keyboard, fingering straight from the Logic Track), and registers it into
webui/songs.json as a Synthesia-only song so it shows up in the app. Optionally
attaches a MusicXML score (OSMD cursor) and a real audio track.

    python ingest_song.py --midi input_songs/MyPiece.mid \
        --title "My Piece" --composer "Someone" --diff Intermediate
    # → results/<id>_synthesia.mp4  (+ _synth.wav if no --mp3)  + songs.json entry

New songs are Synthesia-only: the biomech "hands" video needs a GPU render and
is not produced here — the same form Bach/Beethoven already ship in.
"""

import argparse
import json
import os
import re
import sys

import pretty_midi

import synthesia_view as sv

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')
SONGS_JSON = os.path.join(PROJECT_ROOT, 'webui', 'songs.json')

# deterministic accent palette (cycled by catalog position)
ACCENTS = ['#4FC3F7', '#FFD700', '#5CE5A7', '#C792EA', '#FF9E80', '#80D8FF', '#FFB3C1']


def slugify(text: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()
    return s or 'song'


def fmt_dur(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(round(seconds % 60))
    if s == 60:
        m, s = m + 1, 0
    return f'{m}:{s:02d}'


def load_songs(path: str) -> list:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


def upsert_song(songs: list, entry: dict) -> list:
    """Replace an entry with the same id, else append. Idempotent re-ingest."""
    out = [s for s in songs if s.get('id') != entry['id']]
    out.append(entry)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--midi', required=True, help='source .mid')
    ap.add_argument('--mp3', default=None,
                    help='real audio track; omit to synthesize from the MIDI')
    ap.add_argument('--title', default=None, help='display title (default: filename)')
    ap.add_argument('--composer', default='', help='composer')
    ap.add_argument('--diff', default='Intermediate',
                    choices=['Beginner', 'Intermediate', 'Advanced'])
    ap.add_argument('--id', default=None, help='catalog id (default: slug of filename)')
    ap.add_argument('--key', default=None, help='musical key label, e.g. "D 大調"')
    ap.add_argument('--source', default='arlstm',
                    choices=['arlstm', 'pianoplayer', 'onnx'], help='fingering source')
    ap.add_argument('--musicxml', default=None,
                    help='MusicXML score to attach (enables the OSMD cursor)')
    ap.add_argument('--tempo', type=float, default=None,
                    help='score tempo (♩=) for the header; default: estimate from MIDI')
    ap.add_argument('--songs-json', default=SONGS_JSON,
                    help='catalog file to update (default: webui/songs.json)')
    args = ap.parse_args()

    if not os.path.exists(args.midi):
        sys.exit(f'MIDI not found: {args.midi}')
    if args.mp3 and not os.path.exists(args.mp3):
        sys.exit(f'audio not found: {args.mp3}')

    stem = os.path.splitext(os.path.basename(args.midi))[0]
    song_id = args.id or slugify(stem)
    title = args.title or stem.replace('_', ' ').strip()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_video = os.path.join(RESULTS_DIR, f'{song_id}_synthesia.mp4')

    # 1) audio: real track or synthesize from the MIDI
    if args.mp3:
        audio_path = args.mp3
        audio_url = '../' + os.path.relpath(os.path.abspath(args.mp3), PROJECT_ROOT)
    else:
        audio_path = os.path.splitext(out_video)[0] + '_synth.wav'
        print('[ingest] no --mp3 → synthesizing audio from MIDI')
        sv.synth_audio_from_midi(args.midi, audio_path)
        audio_url = '../' + os.path.relpath(audio_path, PROJECT_ROOT)

    # 2) render the Synthesia practice video (fingering embedded via Logic Track)
    print(f'[ingest] rendering Synthesia video → {out_video}')
    sv.render(args.midi, audio_path, out_video, source=args.source)

    # 3) timing for the catalog entry
    pm = pretty_midi.PrettyMIDI(args.midi)
    onsets = sorted(float(n.start) for inst in pm.instruments if not inst.is_drum
                    for n in inst.notes)
    end_time = pm.get_end_time()

    songs = load_songs(args.songs_json)
    entry = {
        'id': song_id,
        'title': title,
        'composer': args.composer,
        'diff': args.diff,
        'dur': fmt_dur(end_time),
        'popularity': 50,
        'accent': ACCENTS[len([s for s in songs if s.get('id') != song_id]) % len(ACCENTS)],
        'synthesiaUrl': f'../results/{song_id}_synthesia.mp4',
        'audioUrl': audio_url,
    }
    if args.key:
        entry['key'] = args.key

    # 4) optional score → OSMD cursor (needs the music window + tempo)
    if args.musicxml:
        if not os.path.exists(args.musicxml):
            sys.exit(f'musicxml not found: {args.musicxml}')
        entry['scoreUrl'] = '../' + os.path.relpath(os.path.abspath(args.musicxml), PROJECT_ROOT)
        if onsets:
            entry['scoreStartSec'] = round(onsets[0], 2)
            entry['scoreEndSec'] = round(onsets[-1], 2)
        tempo = args.tempo
        if tempo is None:
            try:
                tempo = round(float(pm.estimate_tempo()))
            except Exception:
                tempo = None
        if tempo:
            entry['tempo'] = tempo

    songs = upsert_song(songs, entry)
    os.makedirs(os.path.dirname(os.path.abspath(args.songs_json)), exist_ok=True)
    with open(args.songs_json, 'w') as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'✅ ingested "{title}" (id={song_id}, {entry["dur"]}, {len(onsets)} notes) '
          f'→ {args.songs_json}')
    print(f'   video: {out_video}')
    print(f'   audio: {audio_url}')
    if 'scoreUrl' in entry:
        print(f'   score: {entry["scoreUrl"]} (♩={entry.get("tempo", "?")})')


if __name__ == '__main__':
    main()
