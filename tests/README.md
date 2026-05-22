# Tests

Pytest-based unit & regression tests for the thesis-critical modules.

## Run

```bash
cd /home/dex/PianoMotion10M
conda activate pianomotion
python -m pytest tests/ -v
```

Or pick a single file:

```bash
python -m pytest tests/test_evaluate_template.py -v
python -m pytest tests/test_build_gt_rulebased.py -v
```

## Coverage

| Test file | Module covered | What it pins down |
|---|---|---|
| `test_evaluate_template.py` | `evaluate_template.py` | Hard/Soft scoring logic + corpus eval arithmetic |
| `test_build_gt_rulebased.py` | `build_gt_rulebased.py` | Rule application priority + interval table |

## Regression Pinning Test

`test_regression_canon_neutral_pinning_arlstm_only` pins the **RH GT entry count
(n=186)** reported in `thesis/ch4_evaluation.md` section 4.4.1. If this test
fails after a rebuild of the GT, it means:

1. Either the GT generator behavior drifted (review `build_gt_rulebased.py` diff)
2. Or the input MIDI changed (review `input_songs/Canon*.mid` integrity)

**Action**: if the change is intentional, update both this test's expected count
**AND** the corresponding number in `thesis/ch4_evaluation.md` (4.4.1), 
`thesis/ch1_introduction.md` (1.3 contributions), `thesis/ch7_conclusion.md` (7.1).

## What's NOT tested

- ArLSTM model inference (would require Ramoneda submodule + torch + GPU)
- MIDI parsing (delegated to pretty_midi, trust upstream)
- Visualization / rendering (manual visual review)
- WebSocket layer (integration test only via `webui/realtime/ws_smoketest.py`)

For end-to-end integration test, the canonical command in
`thesis/ch5_implementation.md` §5.6 reproduces the full pipeline.
