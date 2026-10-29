"""Check whether R100's coarse edge support protects real fine structural edges."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R100 = Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch'))
OUTPUT = ROOT / "results" / "r100_edge_support"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image.astype(np.float32) / 255.0


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    design = json.loads((R100 / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    protocol = json.loads((R100 / "config" / "posttraining_validation_protocol.json").read_text(encoding="utf-8"))
    module = load_module("r101_edge_support_model", R100 / "model" / "r100_model.py")
    checkpoint = torch.load(Path(PROJECT_ROOT / protocol["checkpoint"]), map_location="cpu", weights_only=False)
    model = module.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    halo = int(design["architecture"]["tile_contract"]["minimum_halo_px"])
    rows = []
    for path in sorted((R100 / "data" / "live_validation").glob("*.bmp")):
        raw = read_gray(path)
        source = torch.from_numpy(raw)[None, None].to(device)
        padded = F.pad(source, (halo, halo, halo, halo), mode="reflect")
        with torch.inference_mode():
            padded_details = model(padded, return_details=True)
        details = {name: value[..., halo:halo + raw.shape[0], halo:halo + raw.shape[1]] for name, value in padded_details.items()}
        output = details["output"][0, 0].cpu().numpy()
        support = details["edge_support"][0, 0].cpu().numpy()
        denoise = details["denoise_strength"][0, 0].cpu().numpy()
        mild = cv2.GaussianBlur(raw, (0, 0), 0.7, borderType=cv2.BORDER_REFLECT_101)
        gx = cv2.Sobel(mild, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(mild, cv2.CV_32F, 0, 1, ksize=3)
        gradient = np.hypot(gx, gy)
        strong = gradient >= np.percentile(gradient, 90)
        raw_band = raw - cv2.GaussianBlur(raw, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
        out_band = output - cv2.GaussianBlur(output, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
        rows.append({
            "image": path.stem,
            "strong_gradient_fraction": float(np.mean(strong)),
            "strong_gradient_edge_support_recall": float(np.mean(support[strong] >= 0.5)),
            "strong_gradient_median_edge_support": float(np.median(support[strong])),
            "strong_gradient_median_denoise_strength": float(np.median(denoise[strong])),
            "strong_gradient_output_to_raw_fine_rms": float(np.sqrt(np.mean(out_band[strong] ** 2)) / max(np.sqrt(np.mean(raw_band[strong] ** 2)), 1e-9)),
            "nonedge_output_to_raw_fine_rms": float(np.sqrt(np.mean(out_band[~strong] ** 2)) / max(np.sqrt(np.mean(raw_band[~strong] ** 2)), 1e-9)),
        })
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "per_image.csv", index=False)
    summary = {
        "status": "complete",
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "definitions": {
            "strong_gradient": "top ten percent of mildly smoothed raw gradient magnitude",
            "support_recall": "fraction of those pixels receiving edge_support >= 0.5",
        },
        "images": rows,
        "median": {column: float(table[column].median()) for column in table.columns if column != "image"},
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
