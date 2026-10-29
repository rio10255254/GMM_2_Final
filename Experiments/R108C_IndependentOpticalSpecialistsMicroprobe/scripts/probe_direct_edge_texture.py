"""Causal probe: bypass adoption gates and apply qualified edge/texture specialists directly."""
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
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "direct_edge_texture_probe"
ADOPT_PATH = ROOT / "scripts" / "train_adoptions.py"
SEM = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))
R73 = Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/src'))
R74 = Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src'))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


adopt = load_module("r108c_direct_adopt", ADOPT_PATH)
DEVICE = adopt.DEVICE


def read(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value.astype(np.float32) / 255.0


def write(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.round(np.clip(value, 0.0, 1.0) * 255.0).astype(np.uint8))
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(str(path))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@torch.inference_mode()
def direct_stages(models, x: torch.Tensor, strength: float = 1.0):
    stages = {}
    for name in ("edge", "texture"):
        proposal = adopt.expert_proposal(name, models[name], x)
        x = (x + strength * (proposal - x)).clamp(0.0, 1.0)
        stages[name] = x
    return stages


@torch.inference_mode()
def tiled(models, image: np.ndarray, strength: float = 1.0, core: int = 512, halo: int = 192):
    tensor = torch.from_numpy(image[None, None]).to(DEVICE)
    height, width = image.shape
    padded = F.pad(tensor, (halo, halo, halo, halo), mode="reflect")
    outputs = {name: torch.zeros_like(tensor) for name in ("edge", "texture")}
    for y in range(0, height, core):
        for x in range(0, width, core):
            crop_h = min(core, height - y)
            crop_w = min(core, width - x)
            tile = padded[..., y:y + crop_h + 2 * halo, x:x + crop_w + 2 * halo]
            for name, value in direct_stages(models, tile, strength).items():
                outputs[name][..., y:y + crop_h, x:x + crop_w] = value[..., halo:halo + crop_h, halo:halo + crop_w]
    return {name: value[0, 0].cpu().numpy() for name, value in outputs.items()}


def action_metrics(raw: np.ndarray, value: np.ndarray) -> dict[str, float]:
    difference = np.abs(value - raw)
    gx = cv2.Sobel(raw, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(raw, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.hypot(gx, gy)
    support = gradient >= np.quantile(gradient, 0.90)
    gx2 = cv2.Sobel(value, cv2.CV_32F, 1, 0, ksize=3)
    gy2 = cv2.Sobel(value, cv2.CV_32F, 0, 1, ksize=3)
    detail_raw = raw - cv2.GaussianBlur(raw, (0, 0), 1.0)
    detail_value = value - cv2.GaussianBlur(value, (0, 0), 1.0)
    return {
        "change_gray": float(difference.mean() * 255.0),
        "p95_change_gray": float(np.quantile(difference, 0.95) * 255.0),
        "edge_gain": float(np.hypot(gx2, gy2)[support].mean() / max(float(gradient[support].mean()), 1e-9)),
        "detail_ratio": float(np.mean(np.abs(detail_value)) / max(float(np.mean(np.abs(detail_raw))), 1e-9)),
    }


def infer_tree(models, source: Path, destination: Path) -> list[dict[str, object]]:
    rows = []
    files = sorted(path for path in source.rglob("*.bmp") if path.is_file())
    for index, path in enumerate(files, 1):
        stages = tiled(models, read(path))
        output = destination / path.relative_to(source)
        write(output, stages["texture"])
        rows.append({"input": str(path), "input_sha256": sha(path), "output": str(output), "output_sha256": sha(output)})
        if index % 20 == 0 or index == len(files):
            print(json.dumps({"suite": destination.name, "done": index, "total": len(files)}), flush=True)
    return rows


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    models = adopt.load_models()
    sem_rows = []
    for path in sorted(SEM.glob("*.bmp")):
        raw = read(path)
        stages = tiled(models, raw)
        for name, value in stages.items():
            destination = OUTPUT / "sem" / name / path.name
            write(destination, value)
            sem_rows.append({"exposure": int(path.stem), "stage": name, **action_metrics(raw, value)})
    sem_table = pd.DataFrame(sem_rows)
    sem_table.to_csv(OUTPUT / "sem_action.csv", index=False)

    manifests = {
        "R73": infer_tree(models, R73, OUTPUT / "R73"),
        "R74": infer_tree(models, R74, OUTPUT / "R74"),
    }
    for suite, rows in manifests.items():
        pd.DataFrame(rows).to_csv(OUTPUT / f"{suite}_manifest.csv", index=False)

    data = adopt.core.prepare_specialist_data()["holdout"]
    tensors = adopt.core.to_tensors(data, ["target", "edge", "mixed_input"])
    source = tensors["mixed_input"]
    target = tensors["target"]
    edge = tensors["edge"]
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(source), 24):
            outputs.append(direct_stages(models, source[start:start + 24])["texture"].cpu())
    output = torch.cat(outputs).to(DEVICE)
    raw_error = torch.abs(source - target)
    model_error = torch.abs(output - target)
    weight = 0.15 + 0.85 * edge
    synthetic = {
        "images": len(source),
        "raw_mae_gray": float(raw_error.mean() * 255.0),
        "model_mae_gray": float(model_error.mean() * 255.0),
        "raw_edge_mae_gray": float(raw_error.mul(weight).sum() / weight.sum() * 255.0),
        "model_edge_mae_gray": float(model_error.mul(weight).sum() / weight.sum() * 255.0),
        "improved_fraction": float((model_error.flatten(1).mean(1) < raw_error.flatten(1).mean(1)).float().mean()),
    }
    summary = {
        "status": "complete",
        "causal_question": "Are qualified edge/texture specialists useful when adoption suppression is removed?",
        "radiometry": False,
        "denoise": False,
        "strength": 1.0,
        "synthetic_holdout": synthetic,
        "sem_action_median": sem_table.groupby("stage").median(numeric_only=True).to_dict(orient="index"),
        "external_counts": {key: len(value) for key, value in manifests.items()},
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
