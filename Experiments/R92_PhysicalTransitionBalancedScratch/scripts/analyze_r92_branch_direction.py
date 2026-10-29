"""Measure whether R92's learned detail correction sharpens or suppresses Raw detail."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def correlation(first: np.ndarray, second: np.ndarray) -> float:
    left = first.ravel().astype(np.float64)
    right = second.ravel().astype(np.float64)
    left -= left.mean()
    right -= right.mean()
    return float(np.dot(left, right) / max(np.linalg.norm(left) * np.linalg.norm(right), 1e-12))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    checkpoint = Path(PROJECT_ROOT / protocol["checkpoint_root"]) / "epoch_080.pth.tar"
    if sha256_file(checkpoint) != str(protocol["checkpoint_sha256"]).lower():
        raise RuntimeError("Checkpoint hash mismatch")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    inference = load_module("r92_branch_direction_inference", INFERENCE)
    model, payload = inference.load_model(checkpoint, device)
    if int(payload.get("epoch", -1)) != 80:
        raise RuntimeError("Checkpoint epoch mismatch")

    live_root = Path(PROJECT_ROOT / protocol["arms"]["fixed_live_branch_probe"]["input_directory"])
    rows: list[dict[str, Any]] = []
    for source in sorted(live_root.glob("*.bmp")):
        raw, _dtype = inference.read_gray(source)
        tensor = inference.image_tensor(raw, device)
        canvas, (height, width, _grid_h, _grid_w) = inference.canonical_canvas(tensor, 512, 192)
        with torch.inference_mode():
            details = model(canvas, return_details=True)
        arrays = {
            name: value[0, 0, 192:192 + height, 192:192 + width].float().cpu().numpy() * 255.0
            for name, value in details.items()
            if name != "output"
        }
        raw_float = raw.astype(np.float32)
        raw_high = raw_float - cv2.GaussianBlur(raw_float, (0, 0), 1.6)
        rows.append({
            "filename": source.name,
            "detail_delta_vs_raw_high_frequency_correlation": correlation(arrays["detail_delta"], raw_high),
            "edge_delta_vs_raw_high_frequency_correlation": correlation(arrays["edge_delta"], raw_high),
            "combined_correction_vs_raw_high_frequency_correlation": correlation(arrays["correction"], raw_high),
            "detail_delta_signed_mean_gray": float(arrays["detail_delta"].mean()),
            "combined_correction_signed_mean_gray": float(arrays["correction"].mean()),
        })

    table = pd.DataFrame(rows)
    results = Path(PROJECT_ROOT / protocol["output_root"])
    table_path = results / "tables" / "branch_direction_analysis.csv"
    table.to_csv(table_path, index=False, encoding="utf-8-sig")
    medians = {
        column: float(table[column].median())
        for column in table.columns
        if column != "filename"
    }
    output = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "images": len(table),
        "checkpoint_sha256": sha256_file(checkpoint),
        "median_metrics": medians,
        "interpretation": "A negative correction-to-Raw-high-frequency correlation means the learned branch tends to subtract existing high-frequency content. This is direction evidence, not proof that every removed component is true detail rather than noise.",
        "table": str(table_path),
    }
    write_json(results / "branch_direction_analysis.json", output)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
