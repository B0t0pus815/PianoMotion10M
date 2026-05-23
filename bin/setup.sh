#!/usr/bin/env bash
# First-time setup for thesis reproducibility.
#
# Walks through:
#   1. conda env creation (skips if already present)
#   2. python deps install
#   3. external Ramoneda submodule clone (skips if already present)
#   4. sanity-check that key inputs exist
#   5. run unit tests to verify environment
#
# Usage:
#   bin/setup.sh                  # full setup, asks for confirmation
#   bin/setup.sh --yes            # non-interactive
#   bin/setup.sh --verify         # only check + report missing pieces
#
# Idempotent — safe to re-run if a step fails partway.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

YES=false
VERIFY_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --yes|-y)     YES=true ;;
        --verify)     VERIFY_ONLY=true ;;
        --help|-h)
            sed -n '2,15p' "$0"
            exit 0 ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

prompt() {
    if $YES; then return 0; fi
    read -rp "$1 [Y/n] " ans
    [[ -z "$ans" || "$ans" =~ ^[Yy] ]]
}

step() { echo; echo "── [$1] $2"; }
ok()   { echo "    ✓ $1"; }
warn() { echo "    ⚠ $1" >&2; }
fail() { echo "    ✗ $1" >&2; exit 1; }

# ─── 1. conda env ───────────────────────────────────────────────────────
step "1/5" "conda env 'pianomotion'"
if conda env list 2>/dev/null | grep -q '^pianomotion'; then
    ok "env 'pianomotion' already exists"
else
    if $VERIFY_ONLY; then
        warn "env 'pianomotion' not found"
    elif prompt "Create conda env 'pianomotion' with Python 3.10?"; then
        conda create -n pianomotion python=3.10 -y
        ok "env created"
    else
        fail "skipped — env required"
    fi
fi

# ─── 2. python deps ─────────────────────────────────────────────────────
step "2/5" "Python dependencies"
SOURCE_CMD='source ~/anaconda3/etc/profile.d/conda.sh && conda activate pianomotion'
REQUIRED_PKGS=(torch pretty_midi mediapipe librosa matplotlib pytest tqdm scipy)
MISSING=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! bash -c "$SOURCE_CMD && python -c 'import $pkg'" 2>/dev/null; then
        MISSING+=("$pkg")
    fi
done
if [[ ${#MISSING[@]} -eq 0 ]]; then
    ok "all required packages installed (${#REQUIRED_PKGS[@]} verified)"
else
    if $VERIFY_ONLY; then
        warn "missing: ${MISSING[*]}"
    elif prompt "Install missing packages (${MISSING[*]}) via pip?"; then
        bash -c "$SOURCE_CMD && pip install ${MISSING[*]}"
        ok "installed"
    else
        fail "skipped — deps required"
    fi
fi

# Special note: MediaPipe pinned to 0.10.14
bash -c "$SOURCE_CMD && python -c 'import mediapipe; v = mediapipe.__version__; assert v == \"0.10.14\", v'" \
    && ok "mediapipe == 0.10.14 (correct pin)" \
    || warn "mediapipe version mismatch — pin to 0.10.14 if EGL crashes on Ubuntu 22.04"

# ─── 3. Ramoneda submodule ──────────────────────────────────────────────
step "3/5" "Ramoneda Automatic-Piano-Fingering (external dep)"
RAM_DIR="external/Automatic-Piano-Fingering"
RAM_MODELS="$RAM_DIR/models"
if [[ -d "$RAM_MODELS" ]] && \
   [[ -f "$RAM_MODELS/right_ArLSTM.pth" ]]; then
    ok "Ramoneda repo + checkpoints present"
else
    if $VERIFY_ONLY; then
        warn "Ramoneda repo missing — Stage A → B → C will fall back to biomech only"
    elif prompt "Clone Ramoneda repo into external/?"; then
        mkdir -p external
        cd external
        git clone --depth 1 https://github.com/PRamoneda/Automatic-Piano-Fingering.git
        cd "$REPO_ROOT"
        ok "cloned (checkpoints included in the repo)"
    else
        warn "skipped — ArLSTM source unavailable"
    fi
fi

# ─── 4. Input files ─────────────────────────────────────────────────────
step "4/5" "Required input files"
for f in \
    "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mid" \
    "input_songs/Canon In D - Pachelbel  EASY Piano Tutorial.mp3" \
    "input_songs/Bach_Invention_01_BWV772.mid" \
    "results/canon_biomech_v4_fingertips.json" \
    "eval_data/canon_rh_rulebased_gt.json" \
    "eval_data/canon_lh_rulebased_gt.json" \
    "eval_data/bach_inv01_rh_rulebased_gt.json" \
    "eval_data/bach_inv01_lh_rulebased_gt.json"
do
    if [[ -f "$f" ]]; then
        ok "$f"
    else
        warn "missing: $f"
    fi
done

# ─── 5. Run unit tests ──────────────────────────────────────────────────
step "5/5" "Run unit tests (verifies the env actually works)"
if $VERIFY_ONLY || prompt "Run pytest tests/ (should take ~1 sec)?"; then
    bash -c "$SOURCE_CMD && python -m pytest tests/ -q 2>&1" | tail -10 \
        && ok "tests pass — env is functional" \
        || warn "some tests failed — review output"
fi

cat <<EOF

╔═══════════════════════════════════════════════════════════╗
║ Setup complete.                                            ║
║                                                            ║
║ Next steps:                                                ║
║  - View thesis:   cat thesis/ch{1..7}_*.md  | less        ║
║  - Reproduce audit:   bin/regenerate_all.sh               ║
║  - Demo for defense:  bin/demo_defense.sh canon           ║
║  - Build PDFs:        make thesis                         ║
╚═══════════════════════════════════════════════════════════╝
EOF
