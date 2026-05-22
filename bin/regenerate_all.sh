#!/usr/bin/env bash
# Regenerate all thesis-defense demo artifacts in one shot.
#
# Use this when:
#   - You've changed the GT rules or Stage B implementation
#   - You're prepping defense day and want fresh artifacts
#   - You're onboarding a reviewer who needs to reproduce results
#
# Time estimate: ~15 min on a CUDA-enabled box (Canon ~6 min render +
# Summer ~5 min render + audits + tests ~1 min).
#
# Requires: pianomotion conda env active, external/Automatic-Piano-Fingering/
# present with .pth checkpoints, mp3/midi files in input_songs/.

set -euo pipefail

CANON_MIDI="input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid"
CANON_MP3="input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mp3"
SUMMER_MIDI="input_songs/[Piano Cover] 久石讓 Joe Hisaishi - 菊次郎的夏天(Summer)一聽前奏就知道的旋律_extracted.mid"
SUMMER_MP3="input_songs/[Piano Cover] 久石讓 Joe Hisaishi - 菊次郎的夏天(Summer)一聽前奏就知道的旋律.mp3"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

step() { echo; echo "=== [$1] $2 ==="; }
fail() { echo "FAIL: $1" >&2; exit 1; }

# ─── 0. Sanity check ──────────────────────────────────────────────────
step "0/7" "Sanity check environment"
command -v python >/dev/null || fail "python not on PATH (activate pianomotion env?)"
[[ -f "$CANON_MIDI" ]] || fail "Canon MIDI not found: $CANON_MIDI"
[[ -f "$CANON_MP3"  ]] || fail "Canon MP3 not found: $CANON_MP3"
[[ -d "external/Automatic-Piano-Fingering/models" ]] || fail "Ramoneda submodule missing"
echo "✓ env OK"

# ─── 1. Unit tests ────────────────────────────────────────────────────
step "1/7" "Run unit tests"
python -m pytest tests/ -q || fail "tests failed"

# ─── 2. Regenerate RH + LH rule-based GT ──────────────────────────────
step "2/7" "Regenerate rule-based GT (Canon RH + LH)"
python build_gt_rulebased.py \
    --midi "$CANON_MIDI" --hand right \
    --out eval_data/canon_rh_rulebased_gt.json \
    --seed eval_data/canon_rh_gt.json
python build_gt_rulebased.py \
    --midi "$CANON_MIDI" --hand left \
    --out eval_data/canon_lh_rulebased_gt.json

# ─── 3. Four-way audit (RH + LH × full + neutral) ─────────────────────
step "3/7" "Four-way audit"
mkdir -p build/audit
for hand in rh lh; do
    for mode in full neutral; do
        flag=""
        [[ "$mode" == "neutral" ]] && flag="--exclude-tiebreakers"
        echo
        echo "--- $hand ($mode) ---"
        python four_way_audit.py \
            --midi "$CANON_MIDI" \
            --gt "eval_data/canon_${hand}_rulebased_gt.json" \
            --fingertips results/canon_biomech_v4_fingertips.json \
            $flag \
            2>&1 | tee "build/audit/${hand}_${mode}.txt" | tail -8
    done
done

# ─── 4. Render Canon with ArLSTM (Stage B) ────────────────────────────
step "4/7" "Render Canon with ArLSTM fingering"
mkdir -p results
if [[ -f results/canon_arlstm_kb.mp4 && results/canon_arlstm_kb.mp4 -nt simple_natural.py ]]; then
    echo "✓ results/canon_arlstm_kb.mp4 up to date, skipping"
else
    python simple_natural.py \
        --mp3  "$CANON_MP3" --midi "$CANON_MIDI" \
        --fingering arlstm \
        --out_dir results/canon_arlstm \
        --out_video results/canon_arlstm_kb.mp4
fi

# ─── 5. Render Summer with ArLSTM (cross-piece) ───────────────────────
step "5/7" "Render Summer (cross-piece)"
if [[ -f "$SUMMER_MIDI" && -f "$SUMMER_MP3" ]]; then
    if [[ -f results/summer_arlstm_kb.mp4 && results/summer_arlstm_kb.mp4 -nt simple_natural.py ]]; then
        echo "✓ results/summer_arlstm_kb.mp4 up to date, skipping"
    else
        python simple_natural.py \
            --mp3 "$SUMMER_MP3" --midi "$SUMMER_MIDI" \
            --fingering arlstm \
            --out_dir results/summer_arlstm \
            --out_video results/summer_arlstm_kb.mp4
    fi
else
    echo "(Summer files missing, skipping)"
fi

# ─── 6. Side-by-side comparison videos ────────────────────────────────
step "6/7" "Render side-by-side ArLSTM vs biomech v4"
if [[ -f results/canon_biomech_v4_kb.mp4 ]]; then
    /usr/bin/ffmpeg -y -hide_banner -loglevel warning \
        -i results/canon_biomech_v4_kb.mp4 \
        -i results/canon_arlstm_kb.mp4 \
        -filter_complex "[0:v]scale=960:540,drawtext=text='biomech v4 (old)':x=20:y=20:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=5[l];[1:v]scale=960:540,drawtext=text='ArLSTM (Stage B)':x=20:y=20:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=5[r];[l][r]hstack=2" \
        -map 0:a -c:v libx264 -preset medium -crf 23 -c:a aac \
        results/canon_arlstm_vs_biomech.mp4
    echo "✓ results/canon_arlstm_vs_biomech.mp4"
else
    echo "(canon_biomech_v4_kb.mp4 missing, skipping comparison)"
fi

# ─── 7. Summary ───────────────────────────────────────────────────────
step "7/7" "Summary"
echo
echo "Headline numbers (RH+LH neutral subset, see build/audit/*.txt):"
for hand in rh lh; do
    f="build/audit/${hand}_neutral.txt"
    [[ -f "$f" ]] && {
        echo "  --- $hand ---"
        tail -6 "$f" | head -6
        echo
    }
done
echo
echo "Artifacts:"
for f in results/canon_arlstm_kb.mp4 results/summer_arlstm_kb.mp4 \
         results/canon_arlstm_vs_biomech.mp4 \
         results/canon_arlstm_fingertips.json results/summer_arlstm_fingertips.json; do
    [[ -f "$f" ]] && printf "  %-50s %s\n" "$f" "$(du -h "$f" | cut -f1)"
done
echo
echo "✓ Regeneration complete."
