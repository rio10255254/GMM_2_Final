"""Reuse the thesis line-pattern protocol for full versus smoothed R109 controls."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "physical_validation" / "line_interventions"
SOURCE_SCRIPT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS\source_validation\100mg_linewidth_generalization_20260719\scripts\analyze_100mg_linewidth_generalization.py")
FULL = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch\results\posttraining_motion\E048\reconstructions")
SMOOTH = ROOT / "results" / "physical_validation" / "lsc_interventions" / "reconstructions" / "smoothed_controls"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module(SOURCE_SCRIPT, "r113_line_interventions")
    module.OUTPUT = OUTPUT
    module.TABLES = OUTPUT / "tables"
    module.CROPS = OUTPUT / "images"
    module.METHODS = ("Raw", "Base U-Net", "MOSR")
    module.SEQUENCES = {
        "50x_x_0p5um": {
            "nominal_step_um": 0.5,
            "raw": Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_0p5um\bmp"),
            "base": FULL / "50x_0p5um",
            "mosr": SMOOTH / "50x_x_0p5um",
        },
        "50x_x_1um": {
            "nominal_step_um": 1.0,
            "raw": Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_1um\bmp"),
            "base": FULL / "50x_1um",
            "mosr": SMOOTH / "50x_x_1um",
        },
    }
    module.main()
    label_map = {"Base U-Net": "R109 E48", "MOSR": "R109 smoothed controls"}
    for path in (OUTPUT / "tables").glob("*.csv"):
        table = pd.read_csv(path, encoding="utf-8-sig")
        for column in ("method", "reference_method", "target_method"):
            if column in table.columns:
                table[column] = table[column].replace(label_map)
        table.to_csv(path, index=False, encoding="utf-8-sig")
    sharpness = pd.read_csv(OUTPUT / "tables" / "line_sharpness_summary.csv", encoding="utf-8-sig")
    displacement = pd.read_csv(OUTPUT / "tables" / "line_displacement_pooled.csv", encoding="utf-8-sig")
    frame = pd.read_csv(OUTPUT / "tables" / "line_frame_metrics.csv", encoding="utf-8-sig")
    steps = pd.read_csv(OUTPUT / "tables" / "line_displacement_per_step.csv", encoding="utf-8-sig")
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "selection": "same Raw-locked 60 line steps as thesis validation",
        "frame_rows": len(frame),
        "step_rows": len(steps),
        "sharpness": sharpness.to_dict(orient="records"),
        "displacement": displacement.to_dict(orient="records"),
        "missing_measurements": int(steps.isna().any(axis=1).sum()),
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(frame) != 360 or len(steps) != 180 or result["missing_measurements"]:
        raise RuntimeError(f"Line intervention validation failed: {result}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
