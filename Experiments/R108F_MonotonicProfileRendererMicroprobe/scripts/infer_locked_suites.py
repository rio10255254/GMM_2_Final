"""Frozen tiled R108F inference for locked ACM and appearance suites."""
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


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "locked_inference"
CORE_PATH = ROOT / "scripts" / "run_probe.py"
HELPER_PATH = Path(r"D:\GMM_2_Final\Experiments\R96_LocalizedEvidenceProtectedScratch\scripts\evaluate_real_holdout.py")
SUITES = {
    "R73": Path(r"D:\GMM_2_Final\Experiments\R73_R61ExpandedSyntheticACMGeneralization\data\r73_synthetic_acm_val\src"),
    "R74": Path(r"D:\GMM_2_Final\Experiments\R74_R61HardMicroscopyACMGeneralization\data\r74_hard_acm_val\src"),
    "SEM": Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack"),
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


core = load_module("r108f_locked_core", CORE_PATH)
helper = load_module("r108f_locked_appearance", HELPER_PATH)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def infer_tree(model, suite: str, source: Path):
    rows = []
    files = sorted(source.rglob("*.bmp"))
    for index, path in enumerate(files, 1):
        raw = core.dcore.read_gray(path)
        value = core.tiled(model, raw, core=256, halo=192)
        destination = OUTPUT / suite / path.relative_to(source)
        core.dcore.write_gray(destination, value)
        rows.append({"input": str(path), "input_sha256": sha(path), "output": str(destination), "output_sha256": sha(destination)})
        if index % 20 == 0 or index == len(files):
            print(json.dumps({"suite": suite, "done": index, "total": len(files)}), flush=True)
    pd.DataFrame(rows).to_csv(OUTPUT / f"{suite}_manifest.csv", index=False)
    return len(rows)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = core.MonotonicProfileRenderer().to(core.DEVICE)
    checkpoint = core.WEIGHTS / "monotonic_profile_renderer.pth"
    model.load_state_dict(torch.load(checkpoint, map_location=core.DEVICE, weights_only=False)["model"])
    model.eval()
    counts = {suite: infer_tree(model, suite, source) for suite, source in SUITES.items()}
    rows, previews = [], []
    for path in core.ecore.REAL_IMAGES:
        raw_float = core.dcore.read_gray(path)
        output_float = core.tiled(model, raw_float, core=256, halo=192)
        destination = OUTPUT / "real" / path.name
        core.dcore.write_gray(destination, output_float)
        raw = np.round(raw_float * 255).astype(np.uint8)
        output = np.round(np.clip(output_float, 0, 1) * 255).astype(np.uint8)
        rows.append({"image": path.name, **helper.appearance_metrics(raw, output, 256)})
        raw_small = cv2.resize(raw, (480, 360), interpolation=cv2.INTER_AREA)
        output_small = cv2.resize(output, (480, 360), interpolation=cv2.INTER_AREA)
        diff = cv2.resize(np.clip(np.abs(output.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8), (480, 360), interpolation=cv2.INTER_AREA)
        previews.append(np.concatenate([raw_small, output_small, diff], axis=1))
    appearance = pd.DataFrame(rows)
    appearance.to_csv(OUTPUT / "real_appearance.csv", index=False)
    cv2.imencode(".png", np.concatenate(previews, axis=0))[1].tofile(str(OUTPUT / "real_raw_output_diff.png"))
    summary = {
        "status": "complete",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha(checkpoint),
        "counts": counts,
        "tiled": {"core": 256, "halo": 192},
        "real_median": {key: float(appearance[key].median()) for key in appearance.columns if key != "image"},
    }
    (OUTPUT / "state.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
