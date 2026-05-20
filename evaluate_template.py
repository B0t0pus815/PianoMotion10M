"""evaluate_template.py — Fingering accuracy vs. a JSON ground-truth template.

Ground-truth JSON schema
------------------------
{
  "song": "Canon in D (excerpt)",
  "hand": "right",                       # "right" | "left"; one file per hand
  "fingering_convention": "1=thumb, 2=index, 3=middle, 4=ring, 5=pinky",
  "ground_truth": [
    {
      "onset_index": 0,                  # zero-based onset position in the song
      "onset_time":  1.234,              # seconds, optional (alignment / debugging)
      "midi_notes":  [69, 73, 76],       # MIDI pitches sounding together, ASCENDING
      "fingering":   [1,  2,  5]         # same length as midi_notes; paired by index
    },
    ...
  ]
}

Pairing rule: `midi_notes` MUST be sorted ascending; `fingering[i]` is the finger
that plays `midi_notes[i]`. Predictions follow the same rule.

Scoring
-------
For one onset (a chord of N notes) we compare the GT list to the predicted list:

  Hard Accuracy : 1.0 iff lists are identical (same length, same values), else 0.0.
  Soft Accuracy : mean over finger slots; per slot →
                    1.0   if exact,
                    0.5   if |pred - gt| == 1   (valid alternative),
                    0.0   otherwise.
                  Length mismatch is penalised: missing slots score 0,
                  extra predicted fingers inflate the denominator.

The corpus-level metrics are the means of per-onset Hard and Soft scores.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


VALID_ALT_CREDIT = 0.5  # ±1 finger = 0.5 partial credit for Soft Accuracy


@dataclass
class OnsetScore:
    onset_index: int
    midi_notes: list[int]
    gt_fingering: list[int]
    pred_fingering: list[int] | None
    hard: float                   # 0.0 or 1.0
    soft: float                   # 0.0 .. 1.0
    per_finger_soft: list[float]  # element-wise soft credit, for inspection


def score_chord(
    gt: list[int],
    pred: list[int] | None,
) -> tuple[float, float, list[float]]:
    """Compare one chord's GT fingering to a predicted fingering.

    Returns (hard, soft, per_finger_soft).
    `pred=None` means the predictor produced nothing for this onset → all zeros.
    """
    if pred is None:
        return 0.0, 0.0, [0.0] * len(gt)

    n = len(gt)
    per: list[float] = []
    for i in range(n):
        if i >= len(pred):
            per.append(0.0)
            continue
        diff = abs(int(pred[i]) - int(gt[i]))
        if diff == 0:
            per.append(1.0)
        elif diff == 1:
            per.append(VALID_ALT_CREDIT)
        else:
            per.append(0.0)

    extras = max(0, len(pred) - n)         # predicted more fingers than the chord has
    soft_denom = n + extras
    soft = sum(per) / soft_denom if soft_denom > 0 else 0.0

    hard = 1.0 if (len(pred) == n and all(int(p) == int(g) for p, g in zip(pred, gt))) else 0.0
    return hard, soft, per


def load_ground_truth(path: str | Path) -> list[dict]:
    """Read the GT JSON and validate that each entry's lists are aligned."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data["ground_truth"]
    for e in entries:
        if len(e["midi_notes"]) != len(e["fingering"]):
            raise ValueError(
                f"onset_index={e.get('onset_index')}: midi_notes/fingering length mismatch"
            )
    return entries


def evaluate(
    gt_entries: list[dict],
    predictions: dict[int, list[int]],
) -> tuple[list[OnsetScore], dict[str, float]]:
    """Score every onset; return (per-onset scores, aggregate summary).

    `predictions` maps onset_index → fingering list. Missing keys count as
    "no prediction" (zero credit on both metrics).
    """
    per_onset: list[OnsetScore] = []
    for e in gt_entries:
        idx = e["onset_index"]
        gt_f = list(e["fingering"])
        pred_f = predictions.get(idx)
        hard, soft, per = score_chord(gt_f, pred_f)
        per_onset.append(OnsetScore(
            onset_index=idx,
            midi_notes=list(e["midi_notes"]),
            gt_fingering=gt_f,
            pred_fingering=pred_f,
            hard=hard,
            soft=soft,
            per_finger_soft=per,
        ))

    n = len(per_onset)
    summary = {
        "n_onsets": float(n),
        "hard_accuracy": sum(s.hard for s in per_onset) / n if n else 0.0,
        "soft_accuracy": sum(s.soft for s in per_onset) / n if n else 0.0,
        "n_missing_predictions": float(sum(1 for s in per_onset if s.pred_fingering is None)),
    }
    return per_onset, summary


def _demo() -> None:
    """Run `python evaluate_template.py` to see a worked example."""
    sample_gt = {
        "song": "Canon in D (excerpt)",
        "hand": "right",
        "fingering_convention": "1=thumb, 2=index, 3=middle, 4=ring, 5=pinky",
        "ground_truth": [
            {"onset_index": 0, "midi_notes": [74],         "fingering": [3]},
            {"onset_index": 1, "midi_notes": [69, 73, 76], "fingering": [1, 2, 5]},
            {"onset_index": 2, "midi_notes": [71],         "fingering": [2]},
            {"onset_index": 3, "midi_notes": [67, 71, 74], "fingering": [1, 3, 5]},
        ],
    }
    gt_path = Path("_demo_gt.json")
    gt_path.write_text(json.dumps(sample_gt, indent=2, ensure_ascii=False), encoding="utf-8")

    predictions = {
        0: [3],          # exact   → hard 1, soft 1
        1: [1, 2, 4],    # last finger 5→4, off by 1 → hard 0, soft (1+1+0.5)/3
        2: [3],          # 2→3, off by 1            → hard 0, soft 0.5
        # onset_index 3 missing       → hard 0, soft 0
    }

    entries = load_ground_truth(gt_path)
    per_onset, summary = evaluate(entries, predictions)

    print("per-onset:")
    for s in per_onset:
        print(
            f"  idx={s.onset_index:>2}  gt={s.gt_fingering}  pred={s.pred_fingering}  "
            f"hard={s.hard:.2f}  soft={s.soft:.3f}  per={s.per_finger_soft}"
        )
    print("\nsummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    gt_path.unlink()


if __name__ == "__main__":
    _demo()
