"""Real 5x/20x/50x/JunHua appearance and full-frame tile-parity audit."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "results" / "detailed_validation" / "02_real_contract"
MANIFEST = Path(r"D:\GMM_2_Final\Experiments\R114_ConfidenceGatedRecoverableScratch\validation\manifests\real_representatives.json")
HELPER = Path(r"D:\GMM_2_Final\Experiments\R96_LocalizedEvidenceProtectedScratch\scripts\evaluate_real_holdout.py")
CANDIDATES = {
    24: ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "weights" / "epoch_024.pth",
    42: ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "failure_snapshot.pth",
    48: ROOT / "runs" / "r116_calibration_from_e42_20260903_235500" / "weights" / "epoch_048.pth",
}

from inference.tiled import forward_tiled
from model.r116_model import build_model


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


helper = load_module("r116_real_contract_helper", HELPER)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", value.astype(np.uint8))
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def checkpoint_model(path: Path, device: torch.device):
    saved = torch.load(path, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True:
        raise RuntimeError(f"Checkpoint is not scratch: {path}")
    model = build_model().to(device)
    model.load_state_dict(saved["model"], strict=True)
    model.requires_grad_(False)
    return model.eval()


@torch.inference_mode()
def infer(model, raw: np.ndarray, device: torch.device, core: int) -> np.ndarray:
    tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
    return forward_tiled(model, tensor, core_size=core, halo=224)[0, 0].cpu().numpy()


def montage_row(raw: np.ndarray, output: np.ndarray, side: tuple[int, int] = (360, 270)) -> np.ndarray:
    difference = np.clip(127.5 + 8.0 * (output.astype(np.float32) - raw.astype(np.float32)), 0, 255)
    panels = [cv2.resize(value, side, interpolation=cv2.INTER_AREA) for value in (raw, output, difference)]
    return np.concatenate(panels, axis=1).astype(np.uint8)


def main() -> int:
    contract = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = contract["records"]
    missing = [row["source"] for row in records if not Path(row["source"]).is_file()]
    if missing:
        raise RuntimeError(f"Missing real inputs: {missing}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0")
    image_rows = []
    parity_rows = []
    run_records = []
    for epoch, checkpoint in CANDIDATES.items():
        model = checkpoint_model(checkpoint, device)
        preview_rows = []
        tested_families = set()
        for index, row in enumerate(records, start=1):
            source = Path(row["source"])
            raw = helper.read_gray(source)
            destination = OUTPUT / f"E{epoch:03d}" / "reconstructions" / row["family"] / f"{row['id']}.bmp"
            output_float = infer(model, raw, device, 1024)
            output = np.rint(np.clip(output_float, 0, 1) * 255.0).astype(np.uint8)
            write_gray(destination, output)
            metrics = helper.appearance_metrics(raw, output, 1024)
            image_rows.append({
                "epoch": epoch,
                "id": row["id"],
                "family": row["family"],
                "role": row["role"],
                "height": raw.shape[0],
                "width": raw.shape[1],
                "source": str(source),
                "source_sha256": sha256(source),
                "output": str(destination),
                "output_sha256": sha256(destination),
                **metrics,
            })
            if row["family"] not in tested_families:
                alternate = infer(model, raw, device, 768)
                difference = np.abs(alternate - output_float) * 255.0
                parity_rows.append({
                    "epoch": epoch,
                    "id": row["id"],
                    "family": row["family"],
                    "core_a": 1024,
                    "core_b": 768,
                    "halo": 224,
                    "mean_abs_gray": float(difference.mean()),
                    "p99_abs_gray": float(np.quantile(difference, 0.99)),
                    "max_abs_gray": float(difference.max()),
                })
                tested_families.add(row["family"])
            preview_rows.append(montage_row(raw, output))
            print(json.dumps({"epoch": epoch, "done": index, "total": len(records), "id": row["id"]}), flush=True)
        preview = np.concatenate(preview_rows, axis=0)
        success, encoded = cv2.imencode(".png", preview)
        if not success:
            raise RuntimeError("Could not encode real montage")
        montage_path = OUTPUT / f"E{epoch:03d}" / "real_raw_output_diff.png"
        montage_path.parent.mkdir(parents=True, exist_ok=True)
        encoded.tofile(str(montage_path))
        run_records.append({
            "epoch": epoch,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256(checkpoint),
            "images": len(records),
            "tile_parity_families": len(tested_families),
            "montage": str(montage_path),
        })
        del model
        torch.cuda.empty_cache()
    image_frame = pd.DataFrame(image_rows)
    parity_frame = pd.DataFrame(parity_rows)
    family = image_frame.groupby(["epoch", "family"], sort=False).median(numeric_only=True).reset_index()
    image_frame.to_csv(OUTPUT / "per_image.csv", index=False, encoding="utf-8-sig")
    family.to_csv(OUTPUT / "family_summary.csv", index=False, encoding="utf-8-sig")
    parity_frame.to_csv(OUTPUT / "tile_parity.csv", index=False, encoding="utf-8-sig")
    thresholds = contract["thresholds"]
    checks = {
        "mean": bool((parity_frame["mean_abs_gray"] <= float(thresholds["max_tile_mean_gray"])).all()),
        "p99": bool((parity_frame["p99_abs_gray"] <= float(thresholds["max_tile_p99_gray"])).all()),
        "maximum": bool((parity_frame["max_abs_gray"] <= float(thresholds["max_tile_absolute_gray"])).all()),
    }
    payload = {
        "status": "complete" if all(checks.values()) else "failed_tile_parity",
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256(MANIFEST),
        "records": len(records),
        "candidates": run_records,
        "tile_parity_thresholds_gray": thresholds,
        "tile_parity_checks": checks,
        "tile_parity_worst": {
            "mean_abs_gray": float(parity_frame["mean_abs_gray"].max()),
            "p99_abs_gray": float(parity_frame["p99_abs_gray"].max()),
            "max_abs_gray": float(parity_frame["max_abs_gray"].max()),
        },
        "interpretation_boundary": "Real inputs are unlabeled; appearance metrics and tile parity do not establish reconstruction accuracy."
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
