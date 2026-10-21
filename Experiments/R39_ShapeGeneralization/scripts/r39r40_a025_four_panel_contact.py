"""Four-panel contact sheet for R39R40_avg_a025 on R40 micro_val_unseen.

Columns: GT / COMBO / a030 / R39R40_avg_a025.  Uses larger cells than the
original a030 evaluation sheet for clearer side-by-side viewing.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R39_ShapeGeneralization"
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import r39_a030_microscopy_evaluation as base  # noqa: E402

A025_MICRO_RECON = (
    EXPERIMENT_ROOT / "results" / "a030_x_a043_sweep" / "micro_recon" / "a025"
)


def find_a025_inner(stage: str):
    prefix = f"reconstruct_progress_best_tradeoff_in_{stage}_"
    for p in A025_MICRO_RECON.iterdir():
        if p.is_dir() and p.name.startswith(prefix):
            inner = next((q for q in p.iterdir() if q.is_dir()), None)
            return inner
    return None


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-path",
        type=Path,
        default=EXPERIMENT_ROOT / "results" / "a030_x_a043_sweep" / "visuals" / "contact_sheet_a025_four_panel.png",
    )
    parser.add_argument("--examples-per-stage", type=int, default=4)
    parser.add_argument("--cell-size", type=int, default=320)
    args = parser.parse_args(argv)

    profile_dir = base.R40_DATA_ROOT / base.R40_PROFILE
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))

    by_stage = defaultdict(list)
    for p in manifest["pairs"]:
        by_stage[p["stage"]].append(p)
    stages = sorted(by_stage.keys())

    chosen = []
    for stage in stages:
        frames = by_stage[stage]
        if len(frames) <= args.examples_per_stage:
            picks = frames
        else:
            step = max(1, len(frames) // args.examples_per_stage)
            picks = frames[::step][: args.examples_per_stage]
        for p in picks:
            chosen.append(p)

    cs = args.cell_size
    panels = ("GT", "COMBO", "a030", "R39R40_a025")
    label_left = 180
    header_h = 70
    row_label_h = 36
    canvas_w = label_left + cs * len(panels) + 16
    canvas_h = header_h + (cs + row_label_h) * len(chosen) + 8
    canvas = np.full((canvas_h, canvas_w, 3), 250, dtype=np.uint8)

    def put_text(img, text, xy, scale=0.55, color=(20, 20, 20), thickness=1):
        cv2.putText(img, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

    put_text(canvas, "R40 micro_val_unseen: GT vs COMBO vs a030 vs R39R40_avg_a025",
             (12, 28), scale=0.6, thickness=1)
    put_text(canvas, "(a025 is the R39 a030 x R40 a043 weight average at alpha=0.25)",
             (12, 50), scale=0.45, color=(80, 80, 80))
    for c, label in enumerate(panels):
        put_text(canvas, label, (label_left + c * cs + cs // 2 - 40, header_h - 12), scale=0.55, thickness=1)

    stage_inner = {
        "COMBO": {s: base.find_recon_inner(base.R40_RECON_ROOT, s, base.COMBO_TAG) for s in stages},
        "a030": {s: base.find_recon_inner(base.R40_RECON_ROOT, s, base.A030_TAG) for s in stages},
        "R39R40_a025": {s: find_a025_inner(s) for s in stages},
    }

    for r_idx, p in enumerate(chosen):
        stage = p["stage"]
        fid = Path(p["package_lbl"]).stem
        family_short = stage.replace("stage_", "").replace("_micro_", " ")
        y_top = header_h + r_idx * (cs + row_label_h)
        put_text(canvas, family_short, (8, y_top + cs // 2 - 6), scale=0.50)
        put_text(canvas, fid, (8, y_top + cs // 2 + 16), scale=0.42, color=(80, 80, 80))

        gt_path = profile_dir / p["package_lbl"]
        for c_idx, label in enumerate(panels):
            x = label_left + c_idx * cs
            if label == "GT":
                src_path = gt_path
            else:
                inner = stage_inner[label].get(stage)
                src_path = inner / f"{fid}.bmp" if inner is not None else None
            if src_path is None or not Path(src_path).exists():
                continue
            img = cv2.imread(str(src_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            sized = cv2.resize(img, (cs - 12, cs - 12), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(sized, cv2.COLOR_GRAY2BGR)
            canvas[y_top + 4 : y_top + 4 + sized.shape[0], x + 6 : x + 6 + sized.shape[1]] = rgb

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output_path), canvas)
    print(f"contact sheet -> {args.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
