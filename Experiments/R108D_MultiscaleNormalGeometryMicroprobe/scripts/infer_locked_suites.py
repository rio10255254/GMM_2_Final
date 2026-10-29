"""Frozen R108D inference on locked external ACM, SEM, and real appearance suites."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "locked_inference"
CORE_PATH = ROOT / "scripts" / "run_probe.py"
HELPER_PATH = Path(str(PROJECT_ROOT / 'Experiments/R96_LocalizedEvidenceProtectedScratch/scripts/evaluate_real_holdout.py'))
SUITES = {
    "R73": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/src')),
    "R74": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src')),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


core = load_module("r108d_frozen_core", CORE_PATH)
helper = load_module("r108d_appearance_helper", HELPER_PATH)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def infer_tree(model, name: str, source: Path) -> list[dict[str, object]]:
    destination_root = RESULTS / name
    rows = []
    files = sorted(source.rglob("*.bmp"))
    for index, path in enumerate(files, 1):
        raw = core.read_gray(path)
        output = core.tiled(model, raw, core=256, halo=192)
        destination = destination_root / path.relative_to(source)
        core.write_gray(destination, output)
        rows.append({"input": str(path), "input_sha256": sha(path), "output": str(destination), "output_sha256": sha(destination)})
        if index % 20 == 0 or index == len(files):
            print(json.dumps({"suite": name, "done": index, "total": len(files)}), flush=True)
    pd.DataFrame(rows).to_csv(RESULTS / f"{name}_manifest.csv", index=False)
    return rows


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    model = core.MultiscaleNormalGeometry().to(core.DEVICE)
    model.load_state_dict(torch.load(core.WEIGHTS / "multiscale_normal_geometry.pth", map_location=core.DEVICE, weights_only=False)["model"])
    model.eval()
    counts = {name: len(infer_tree(model, name, source)) for name, source in SUITES.items()}
    counts["SEM"] = len(infer_tree(model, "SEM", core.SEM_ROOT))
    real_rows = []
    preview = []
    for path in core.REAL_IMAGES:
        raw_float = core.read_gray(path)
        output_float = core.tiled(model, raw_float, core=256, halo=192)
        output_path = RESULTS / "real" / path.name
        core.write_gray(output_path, output_float)
        raw = np.round(raw_float * 255.0).astype(np.uint8)
        output = np.round(np.clip(output_float, 0.0, 1.0) * 255.0).astype(np.uint8)
        real_rows.append({"image": path.name, **helper.appearance_metrics(raw, output, 256)})
        raw_small = cv2.resize(raw, (480, 360), interpolation=cv2.INTER_AREA)
        out_small = cv2.resize(output, (480, 360), interpolation=cv2.INTER_AREA)
        diff = cv2.resize(np.clip(np.abs(output.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8), (480, 360), interpolation=cv2.INTER_AREA)
        preview.append(np.concatenate([raw_small, out_small, diff], axis=1))
    real = pd.DataFrame(real_rows)
    real.to_csv(RESULTS / "real_appearance.csv", index=False)
    cv2.imencode(".png", np.concatenate(preview, axis=0))[1].tofile(str(RESULTS / "real_raw_output_diff.png"))
    summary = {
        "status": "complete",
        "checkpoint": str(core.WEIGHTS / "multiscale_normal_geometry.pth"),
        "checkpoint_sha256": sha(core.WEIGHTS / "multiscale_normal_geometry.pth"),
        "tiled": {"core": 256, "halo": 192},
        "counts": counts,
        "real_median": {key: float(real[key].median()) for key in real.columns if key != "image"},
    }
    (RESULTS / "state.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
