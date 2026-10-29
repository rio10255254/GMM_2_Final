"""Prepare developmental Raw/R79 residual-blend candidates for ACM screening."""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark'))
OUTPUT = ROOT / "results" / "preflight_blend_screen"
MODEL_DIR = ROOT / "model"
sys.path.insert(0, str(MODEL_DIR))
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import ImageQualityGate  # noqa: E402

CANDIDATES = {
    "Blend25": lambda q: 0.25,
    "Blend50": lambda q: 0.50,
    "Blend75": lambda q: 0.75,
    "QualityConservative": lambda q: 0.10 + 0.90 / (1.0 + math.exp(-(q - 0.62) / 0.06)),
    "QualityModerate": lambda q: 0.20 + 0.80 / (1.0 + math.exp(-(q - 0.55) / 0.07)),
}


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read image: {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image.astype(np.uint8))
    if not ok:
        raise RuntimeError(f"Could not encode image: {path}")
    encoded.tofile(path)


def quality_score(image: np.ndarray) -> float:
    tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None]
    with torch.no_grad():
        return float(ImageQualityGate.estimate_quality_score(tensor).item())


def blend(raw: np.ndarray, reconstructed: np.ndarray, alpha: float) -> np.ndarray:
    if raw.shape != reconstructed.shape:
        raise RuntimeError(f"Shape mismatch: raw={raw.shape}, reconstruction={reconstructed.shape}")
    value = raw.astype(np.float32) + float(alpha) * (reconstructed.astype(np.float32) - raw.astype(np.float32))
    return np.clip(np.rint(value), 0, 255).astype(np.uint8)


def prepare_external_suite(suite: str) -> list[dict]:
    source_root = R82 / "results" / "acm_external" / suite
    config = json.loads((source_root / "config" / "experiment.json").read_text(encoding="utf-8"))
    prior = json.loads((source_root / "results" / "inference_manifest.json").read_text(encoding="utf-8"))
    suite_root = OUTPUT / suite
    (suite_root / "config").mkdir(parents=True, exist_ok=True)
    (suite_root / "results").mkdir(parents=True, exist_ok=True)
    config["experiment_id"] = f"R83_blend_screen_{suite}"
    (suite_root / "config" / "experiment.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    methods = ["Raw", "R79", *CANDIDATES]
    output_dirs = {"Raw": prior["output_dirs"]["Raw"], "R79": prior["output_dirs"]["R79"]}
    records = []
    for candidate, alpha_fn in CANDIDATES.items():
        output_dirs[candidate] = {}
        for family in config["dataset"]["families"]:
            name = family["name"]
            stage = family["stage"]
            raw_dir = Path(prior["output_dirs"]["Raw"][name])
            r79_dir = Path(prior["output_dirs"]["R79"][name])
            target_dir = suite_root / "results" / "reconstructions" / candidate / stage
            output_dirs[candidate][name] = str(target_dir)
            for raw_path in sorted(raw_dir.glob("*.bmp")):
                raw = read_gray(raw_path)
                reconstruction = read_gray(r79_dir / raw_path.name)
                q = quality_score(raw)
                alpha = float(alpha_fn(q))
                target = target_dir / raw_path.name
                write_bmp(target, blend(raw, reconstruction, alpha))
                records.append({
                    "suite": suite,
                    "family": name,
                    "filename": raw_path.name,
                    "candidate": candidate,
                    "quality_score": q,
                    "alpha": alpha,
                    "output": str(target),
                })
    inference = {"suite": suite, "methods": methods, "output_dirs": output_dirs}
    (suite_root / "results" / "inference_manifest.json").write_text(
        json.dumps(inference, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return records


def prepare_sem() -> list[dict]:
    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    suite_root = OUTPUT / "SEM"
    (suite_root / "config").mkdir(parents=True, exist_ok=True)
    config = {
        "experiment_id": "R83_blend_screen_SEM",
        "models": {name: {} for name in ["R79", *CANDIDATES]},
        "sem_acm": r82_config["sem_acm"],
    }
    (suite_root / "config" / "experiment.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    raw_dir = Path(PROJECT_ROOT / r82_config["sem_acm"]["raw_input_dir"])
    r79_dir = R82 / "results" / "reconstructions" / "sem_acm" / "R79"
    records = []
    for exposure in r82_config["sem_acm"]["optical_exposures"]:
        filename = f"{exposure}.bmp"
        raw = read_gray(raw_dir / filename)
        reconstruction = read_gray(r79_dir / filename)
        r79_target = suite_root / "results" / "reconstructions" / "sem_acm" / "R79" / filename
        r79_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r79_dir / filename, r79_target)
        q = quality_score(raw)
        for candidate, alpha_fn in CANDIDATES.items():
            alpha = float(alpha_fn(q))
            target = suite_root / "results" / "reconstructions" / "sem_acm" / candidate / filename
            write_bmp(target, blend(raw, reconstruction, alpha))
            records.append({
                "suite": "SEM",
                "exposure": int(exposure),
                "candidate": candidate,
                "quality_score": q,
                "alpha": alpha,
                "output": str(target),
            })
    return records


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    records.extend(prepare_external_suite("R73_novel_shapes"))
    records.extend(prepare_external_suite("R74_hard_microscopy"))
    records.extend(prepare_sem())
    manifest = {
        "experiment_id": "R83_R79SevereMicroscopyStrengthening",
        "role": "developmental_preflight_only",
        "candidate_formulas": {
            "Blend25": "alpha=0.25",
            "Blend50": "alpha=0.50",
            "Blend75": "alpha=0.75",
            "QualityConservative": "alpha=0.10+0.90*sigmoid((quality-0.62)/0.06)",
            "QualityModerate": "alpha=0.20+0.80*sigmoid((quality-0.55)/0.07)",
        },
        "record_count": len(records),
        "records": records,
    }
    (OUTPUT / "blend_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"prepared": True, "record_count": len(records), "output": str(OUTPUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
