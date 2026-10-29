"""Run the locked project ACM protocol on Raw versus frozen R114 geometry output."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import build_full_model
PROJECT_ROOT = Path(__file__).resolve().parents[3]

OUTPUT = ROOT / "results" / "geometry_probe" / "E020" / "locked_acm"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
R82_SCRIPTS = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts'))
RUN = ROOT / "runs" / "r114_geometry_probe_scratch_20260830" / "weights"
CHECKPOINTS = {
    "R114E12": RUN / "epoch_012.pth",
    "R114E16": RUN / "epoch_016.pth",
    "R114E20": RUN / "epoch_020.pth",
}
SUITES = {
    "R73": {
        "template": Path(str(PROJECT_ROOT / 'Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json')),
        "root": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val')),
        "generic": ROOT / "results" / "geometry_probe" / "E020" / "R73_contract_v2" / "images",
    },
    "R74": {
        "template": Path(str(PROJECT_ROOT / 'Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json')),
        "root": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val')),
        "generic": ROOT / "results" / "geometry_probe" / "E020" / "R74_contract" / "images",
    },
}


def write_bmp(path: Path, source: Path) -> None:
    encoded = np.fromfile(source, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"cannot read {source}")
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, payload = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"cannot write {path}")
    payload.tofile(path)


def reconstruct(method: str, checkpoint: Path, records: list[dict], output_root: Path) -> None:
    expected = [output_root / str(row["stage"]) / str(row["filename"]) for row in records]
    if all(path.is_file() for path in expected):
        return
    payload = torch.load(checkpoint, map_location="cpu")
    if not payload.get("scratch") or payload.get("foreign_checkpoint_loaded"):
        raise RuntimeError(f"{method} violates scratch contract")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = build_full_model(detail_enabled=False)
    model.load_state_dict(payload["model"], strict=True)
    model = model.to(device).eval()
    with torch.inference_mode():
        for row, destination in zip(records, expected):
            encoded = np.fromfile(row["src"], dtype=np.uint8)
            image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise RuntimeError(f"cannot read {row['src']}")
            tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
            output = model(tensor)[0, 0].clamp(0, 1).cpu().numpy()
            destination.parent.mkdir(parents=True, exist_ok=True)
            ok, bmp = cv2.imencode(".bmp", np.rint(output * 255).astype(np.uint8))
            if not ok:
                raise RuntimeError(f"cannot encode {destination}")
            bmp.tofile(destination)


def prepare(suite: str, spec: dict) -> tuple[Path, int, int]:
    if not MATLAB.is_file():
        raise FileNotFoundError(MATLAB)
    source_manifest = json.loads((spec["root"] / "manifest.json").read_text(encoding="utf-8"))
    reconstructed_roots = {}
    for method, checkpoint in CHECKPOINTS.items():
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
        reconstructed_root = OUTPUT / "inputs_v2" / suite / method
        reconstruct(method, checkpoint, source_manifest["records"], reconstructed_root)
        reconstructed_roots[method] = reconstructed_root

    contract = OUTPUT / f"{suite}_contract"
    config = json.loads(spec["template"].read_text(encoding="utf-8"))
    config["experiment_id"] = f"R114_{suite}_GeometryProbe_E020"
    config["dataset"]["root"] = str(spec["root"])
    config_path = contract / "config" / "experiment.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    methods = ["Raw", *CHECKPOINTS]
    output_dirs = {method: {} for method in methods}
    for family in config["dataset"]["families"]:
        name, stage = family["name"], family["stage"]
        output_dirs["Raw"][name] = str(spec["root"] / "src" / stage)
        for method, reconstructed_root in reconstructed_roots.items():
            output_dirs[method][name] = str(reconstructed_root / stage)
    manifest = {"suite": suite, "methods": methods, "output_dirs": output_dirs}
    result_manifest = contract / "results" / "inference_manifest.json"
    result_manifest.parent.mkdir(parents=True, exist_ok=True)
    result_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    primary = int(config["dataset"]["total_images"]) * len(methods) * 2
    sensitivity = len(config["dataset"]["families"]) * len(config["acm"]["sensitivity_filenames"]) * len(config["acm"]["sensitivity_presets"]) * len(methods)
    return contract, primary, sensitivity


def complete(contract: Path, expected_primary: int, expected_sensitivity: int) -> bool:
    tables = contract / "results" / "tables"
    primary = tables / "primary_contour_metrics.csv"
    sensitivity = tables / "acm_sensitivity_metrics.csv"
    return primary.is_file() and sensitivity.is_file() and len(pd.read_csv(primary)) == expected_primary and len(pd.read_csv(sensitivity)) == expected_sensitivity


def run_matlab(contract: Path, expected_primary: int, expected_sensitivity: int) -> None:
    if complete(contract, expected_primary, expected_sensitivity):
        return
    expression = f"addpath('{R82_SCRIPTS.as_posix()}'); run_acm_multimethod('{contract.as_posix()}')"
    result = subprocess.run([str(MATLAB), "-batch", expression], cwd=contract, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = contract / "logs" / "matlab_acm.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not complete(contract, expected_primary, expected_sensitivity):
        raise RuntimeError(f"ACM failed for {contract.name}; inspect {log}")


def summarize(suite: str, contract: Path) -> dict:
    table = pd.read_csv(contract / "results" / "tables" / "primary_contour_metrics.csv")
    translated = table.loc[table["alignment"].eq("translation_only")].copy()
    metrics = ["iou", "mean_boundary_distance_px", "hd95_px", "area_error_pct", "perimeter_error_pct"]
    overall = translated.groupby("method", as_index=False)[metrics].median()
    family = translated.groupby(["method", "family"], as_index=False)[metrics].median()
    tables = contract / "results" / "tables"
    overall.to_csv(tables / "r114_method_summary.csv", index=False, encoding="utf-8-sig")
    family.to_csv(tables / "r114_family_summary.csv", index=False, encoding="utf-8-sig")
    index = overall.set_index("method")
    raw = index.loc["Raw"]
    family_index = family.set_index(["method", "family"])
    models = {}
    for method in CHECKPOINTS:
        model = index.loc[method]
        effects = []
        for family_name in sorted(translated["family"].unique()):
            before = family_index.loc[("Raw", family_name)]
            after = family_index.loc[(method, family_name)]
            effects.append({
                "family": family_name,
                "boundary_change_pct": float((after["mean_boundary_distance_px"] / before["mean_boundary_distance_px"] - 1) * 100),
                "hd95_change_pct": float((after["hd95_px"] / before["hd95_px"] - 1) * 100),
                "iou_delta": float(after["iou"] - before["iou"]),
            })
        models[method] = {
            "metrics": model.to_dict(),
            "overall_boundary_change_pct": float((model["mean_boundary_distance_px"] / raw["mean_boundary_distance_px"] - 1) * 100),
            "overall_hd95_change_pct": float((model["hd95_px"] / raw["hd95_px"] - 1) * 100),
            "overall_iou_delta": float(model["iou"] - raw["iou"]),
            "families": effects,
        }
    return {
        "suite": suite,
        "raw": raw.to_dict(),
        "models": models,
        "acm_failures": table.groupby("method")["acm_success"].apply(lambda values: int((~values.astype(bool)).sum())).to_dict(),
    }


def main() -> int:
    results = []
    for suite, spec in SUITES.items():
        contract, primary, sensitivity = prepare(suite, spec)
        run_matlab(contract, primary, sensitivity)
        results.append(summarize(suite, contract))
    payload = {"status": "complete", "protocol": "locked Chan-Vese ACM, translation-only primary", "suites": results}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
