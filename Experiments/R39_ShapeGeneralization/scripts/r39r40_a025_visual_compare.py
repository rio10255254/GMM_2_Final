"""Five-panel visual contact sheets for R39R40_avg_a025 vs reference candidates.

Produces two sheets:
- R40 micro_val_unseen (5 stages × 4 frames × 5 panels = 20 rows)
- R39 shape_val_unseen (7 stages × 3 frames × 5 panels = 21 rows)

Each row shows GT / COMBO / a030 / a043 / R39R40_avg_a025 side by side.
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

A025_ROOT = EXPERIMENT_ROOT / "results" / "a030_x_a043_sweep"
A025_MICRO_RECON = A025_ROOT / "micro_recon" / "a025"
A025_SHAPE_RECON = A025_ROOT / "shape_recon" / "a025"
A043_MICRO_RECON = (
    REPO_ROOT
    / "Experiments"
    / "R40_MicroscopyFeatureCoverage"
    / "results"
    / "weight_sweep"
    / "combo_best_low_alpha"
    / "micro_recon"
    / "a043"
)
A043_SHAPE_RECON = A025_ROOT / "shape_recon" / "a043"

R39_SHAPE_ROOT_A030 = EXPERIMENT_ROOT / "results" / "weight_sweep" / "shape_recon" / "a030"
R39_SHAPE_ROOT_COMBO = EXPERIMENT_ROOT / "results" / "weight_sweep" / "shape_recon" / "a000"


def find_inner(root: Path, stage: str):
    prefix = f"reconstruct_progress_best_tradeoff_in_{stage}_"
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith(prefix):
            inner = next((q for q in p.iterdir() if q.is_dir()), None)
            return inner
    return None


def find_inner_tag(root: Path, stage: str, tag: str):
    name = f"reconstruct_progress_best_tradeoff_in_{stage}_{tag}"
    outer = root / name
    if not outer.exists():
        return None
    return next((q for q in outer.iterdir() if q.is_dir()), None)


def build_sheet(
    *,
    title: str,
    subtitle: str,
    profile_dir: Path,
    stage_inner_by_panel: dict,
    chosen: list,
    output_path: Path,
    cell_size: int = 260,
):
    panels = list(stage_inner_by_panel.keys())  # includes "GT" first
    label_left = 200
    header_h = 70
    row_label_h = 34
    canvas_w = label_left + cell_size * len(panels) + 16
    canvas_h = header_h + (cell_size + row_label_h) * len(chosen) + 8
    canvas = np.full((canvas_h, canvas_w, 3), 250, dtype=np.uint8)

    def put_text(img, text, xy, scale=0.55, color=(20, 20, 20), thickness=1):
        cv2.putText(img, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

    put_text(canvas, title, (12, 28), scale=0.6)
    put_text(canvas, subtitle, (12, 52), scale=0.45, color=(80, 80, 80))
    for c, label in enumerate(panels):
        x_center = label_left + c * cell_size + cell_size // 2 - len(label) * 4
        put_text(canvas, label, (x_center, header_h - 12), scale=0.55)

    for r_idx, p in enumerate(chosen):
        stage = p["stage"]
        fid = Path(p["package_lbl"]).stem
        family_short = stage.replace("stage_", "").replace("_micro_", " ").replace("_", " ")
        y_top = header_h + r_idx * (cell_size + row_label_h)
        put_text(canvas, family_short, (8, y_top + cell_size // 2 - 6), scale=0.45)
        put_text(canvas, fid, (8, y_top + cell_size // 2 + 14), scale=0.40, color=(80, 80, 80))

        gt_path = profile_dir / p["package_lbl"]
        for c_idx, label in enumerate(panels):
            x = label_left + c_idx * cell_size
            if label == "GT":
                src_path = gt_path
            else:
                inner = stage_inner_by_panel[label].get(stage)
                src_path = inner / f"{fid}.bmp" if inner is not None else None
            if src_path is None or not Path(src_path).exists():
                continue
            img = cv2.imread(str(src_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            sized = cv2.resize(img, (cell_size - 12, cell_size - 12), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(sized, cv2.COLOR_GRAY2BGR)
            canvas[y_top + 4 : y_top + 4 + sized.shape[0], x + 6 : x + 6 + sized.shape[1]] = rgb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)
    print(f"contact sheet -> {output_path}")


def pick_chosen(by_stage, examples_per_stage):
    chosen = []
    for stage in sorted(by_stage.keys()):
        frames = by_stage[stage]
        if len(frames) <= examples_per_stage:
            picks = frames
        else:
            step = max(1, len(frames) // examples_per_stage)
            picks = frames[::step][: examples_per_stage]
        for p in picks:
            chosen.append(p)
    return chosen


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--micro-output",
        type=Path,
        default=A025_ROOT / "visuals" / "contact_sheet_a025_micro_five_panel.png",
    )
    parser.add_argument(
        "--shape-output",
        type=Path,
        default=A025_ROOT / "visuals" / "contact_sheet_a025_shape_five_panel.png",
    )
    parser.add_argument("--examples-per-stage-micro", type=int, default=4)
    parser.add_argument("--examples-per-stage-shape", type=int, default=3)
    parser.add_argument("--cell-size", type=int, default=260)
    args = parser.parse_args(argv)

    # ---------- R40 micro_val_unseen ----------
    print("[visual compare] R40 micro_val_unseen ...", flush=True)
    micro_profile_dir = base.R40_DATA_ROOT / base.R40_PROFILE
    micro_manifest = json.loads((micro_profile_dir / "manifest.json").read_text(encoding="utf-8"))
    by_stage_micro = defaultdict(list)
    for p in micro_manifest["pairs"]:
        by_stage_micro[p["stage"]].append(p)
    micro_stages = sorted(by_stage_micro.keys())
    micro_chosen = pick_chosen(by_stage_micro, args.examples_per_stage_micro)

    micro_panels = {
        "GT": None,
        "COMBO": {s: find_inner_tag(base.R40_RECON_ROOT, s, base.COMBO_TAG) for s in micro_stages},
        "a030": {s: find_inner_tag(base.R40_RECON_ROOT, s, base.A030_TAG) for s in micro_stages},
        "a043": {s: find_inner(A043_MICRO_RECON, s) for s in micro_stages},
        "R39R40_a025": {s: find_inner(A025_MICRO_RECON, s) for s in micro_stages},
    }
    build_sheet(
        title="R40 micro_val_unseen 五聯對比：GT / COMBO / a030 / R40 a043 / R39R40 a025",
        subtitle="5 stages x 4 frames; lines_grid / large_regions / textures / edge_defects / mixed_fields",
        profile_dir=micro_profile_dir,
        stage_inner_by_panel=micro_panels,
        chosen=micro_chosen,
        output_path=args.micro_output,
        cell_size=args.cell_size,
    )

    # ---------- R39 shape_val_unseen ----------
    print("[visual compare] R39 shape_val_unseen ...", flush=True)
    shape_profile_dir = base.R39_DATA_ROOT / base.R39_PROFILE
    shape_manifest = json.loads((shape_profile_dir / "manifest.json").read_text(encoding="utf-8"))
    by_stage_shape = defaultdict(list)
    for p in shape_manifest["pairs"]:
        by_stage_shape[p["stage"]].append(p)
    shape_stages = sorted(by_stage_shape.keys())
    shape_chosen = pick_chosen(by_stage_shape, args.examples_per_stage_shape)

    shape_panels = {
        "GT": None,
        "COMBO": {s: find_inner(R39_SHAPE_ROOT_COMBO, s) for s in shape_stages},
        "a030": {s: find_inner(R39_SHAPE_ROOT_A030, s) for s in shape_stages},
        "a043": {s: find_inner(A043_SHAPE_RECON, s) for s in shape_stages},
        "R39R40_a025": {s: find_inner(A025_SHAPE_RECON, s) for s in shape_stages},
    }
    build_sheet(
        title="R39 shape_val_unseen 五聯對比：GT / COMBO / a030 / R40 a043 / R39R40 a025",
        subtitle="7 stages x 3 frames; triangles / circles / rectangles / ellipses / polygons / mixed_simple / mixed_complex",
        profile_dir=shape_profile_dir,
        stage_inner_by_panel=shape_panels,
        chosen=shape_chosen,
        output_path=args.shape_output,
        cell_size=args.cell_size,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
