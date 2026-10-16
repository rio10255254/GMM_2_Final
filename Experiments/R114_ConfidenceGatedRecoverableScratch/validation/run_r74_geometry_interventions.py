"""Causal R74 ACM: isolate learned width and normal-shift actions."""
from __future__ import annotations

import copy
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


OUT = ROOT / "results" / "geometry_probe" / "E020" / "r74_interventions"
SOURCE = Path(r"D:\GMM_2_Final\Experiments\R74_R61HardMicroscopyACMGeneralization\data\r74_hard_acm_val")
TEMPLATE = Path(r"D:\GMM_2_Final\Experiments\R104_PhotometricInvariantCausalGateScratch\results\posttraining_validation\external_acm\R74_hard_microscopy\config\experiment.json")
CHECKPOINT = ROOT / "runs" / "r114_geometry_probe_scratch_20260830" / "weights" / "epoch_020.pth"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark\scripts")


def load_base(device: torch.device):
    payload = torch.load(CHECKPOINT, map_location="cpu")
    if not payload.get("scratch") or payload.get("foreign_checkpoint_loaded"):
        raise RuntimeError("checkpoint violates scratch contract")
    model = build_full_model(False)
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval()


def variants(device: torch.device) -> dict[str, torch.nn.Module]:
    full = load_base(device)
    width_only = copy.deepcopy(full)
    with torch.no_grad():
        width_only.shift_head.weight.zero_()
        width_only.shift_head.bias.zero_()
    shift_only = copy.deepcopy(full)
    with torch.no_grad():
        shift_only.width_head.weight.zero_()
        shift_only.width_head.bias.fill_(-20.0)
    return {"Full": full, "WidthOnly": width_only, "ShiftOnly": shift_only}


def generate(records: list[dict], models: dict[str, torch.nn.Module], device: torch.device) -> dict[str, Path]:
    roots = {name: OUT / "inputs" / name for name in models}
    with torch.inference_mode():
        for row in records:
            image = cv2.imdecode(np.fromfile(row["src"], np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise RuntimeError(row["src"])
            value = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
            for name, model in models.items():
                destination = roots[name] / str(row["stage"]) / str(row["filename"])
                if destination.is_file():
                    continue
                output = model(value)[0, 0].clamp(0, 1).cpu().numpy()
                destination.parent.mkdir(parents=True, exist_ok=True)
                ok, encoded = cv2.imencode(".bmp", np.rint(output * 255).astype(np.uint8))
                if not ok:
                    raise RuntimeError(destination)
                encoded.tofile(destination)
    return roots


def prepare(records: list[dict], roots: dict[str, Path]) -> tuple[Path, int, int]:
    contract = OUT / "contract"
    config = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    config["experiment_id"] = "R114_R74_GeometryInterventions_E020"
    config["dataset"]["root"] = str(SOURCE)
    config_path = contract / "config" / "experiment.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    methods = ["Raw", *roots]
    directories = {name: {} for name in methods}
    for family in config["dataset"]["families"]:
        name, stage = family["name"], family["stage"]
        directories["Raw"][name] = str(SOURCE / "src" / stage)
        for method, root in roots.items():
            directories[method][name] = str(root / stage)
    manifest = contract / "results" / "inference_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"suite": "R74", "methods": methods, "output_dirs": directories}, indent=2), encoding="utf-8")
    primary = int(config["dataset"]["total_images"]) * len(methods) * 2
    sensitivity = len(config["dataset"]["families"]) * len(config["acm"]["sensitivity_filenames"]) * len(config["acm"]["sensitivity_presets"]) * len(methods)
    return contract, primary, sensitivity


def ready(contract: Path, primary: int, sensitivity: int) -> bool:
    tables = contract / "results" / "tables"
    p, s = tables / "primary_contour_metrics.csv", tables / "acm_sensitivity_metrics.csv"
    return p.is_file() and s.is_file() and len(pd.read_csv(p)) == primary and len(pd.read_csv(s)) == sensitivity


def main() -> int:
    if not MATLAB.is_file():
        raise FileNotFoundError(MATLAB)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    models = variants(device)
    roots = generate(manifest["records"], models, device)
    contract, primary_count, sensitivity_count = prepare(manifest["records"], roots)
    if not ready(contract, primary_count, sensitivity_count):
        expression = f"addpath('{R82.as_posix()}'); run_acm_multimethod('{contract.as_posix()}')"
        result = subprocess.run([str(MATLAB), "-batch", expression], cwd=contract, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = contract / "logs" / "matlab_acm.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(result.stdout, encoding="utf-8", errors="replace")
        if result.returncode != 0 or not ready(contract, primary_count, sensitivity_count):
            raise RuntimeError(f"intervention ACM failed; inspect {log}")
    primary = pd.read_csv(contract / "results" / "tables" / "primary_contour_metrics.csv")
    translated = primary.loc[primary["alignment"].eq("translation_only")]
    metrics = ["iou", "mean_boundary_distance_px", "hd95_px", "area_error_pct", "perimeter_error_pct"]
    overall = translated.groupby("method", as_index=False)[metrics].median()
    family = translated.groupby(["method", "family"], as_index=False)[metrics].median()
    raw = overall.set_index("method").loc["Raw"]
    family_index = family.set_index(["method", "family"])
    result_models = {}
    for method in models:
        row = overall.set_index("method").loc[method]
        result_models[method] = {
            "boundary_change_pct": float((row["mean_boundary_distance_px"] / raw["mean_boundary_distance_px"] - 1) * 100),
            "hd95_change_pct": float((row["hd95_px"] / raw["hd95_px"] - 1) * 100),
            "iou_delta": float(row["iou"] - raw["iou"]),
            "families": [
                {
                    "family": family_name,
                    "boundary_change_pct": float((family_index.loc[(method, family_name), "mean_boundary_distance_px"] / family_index.loc[("Raw", family_name), "mean_boundary_distance_px"] - 1) * 100),
                    "iou_delta": float(family_index.loc[(method, family_name), "iou"] - family_index.loc[("Raw", family_name), "iou"]),
                }
                for family_name in sorted(translated["family"].unique())
            ],
        }
    payload = {
        "status": "complete",
        "models": result_models,
        "acm_failures": primary.groupby("method")["acm_success"].apply(lambda values: int((~values.astype(bool)).sum())).to_dict(),
    }
    (OUT / "analysis_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
