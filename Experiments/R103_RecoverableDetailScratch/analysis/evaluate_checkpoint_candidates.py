"""Post-training checkpoint selection on locked internal-test and real preview inputs."""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training", ROOT / "evaluation", ROOT / "inference"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from r103_model import build_model  # noqa: E402
from r103_dataset import R103Dataset  # noqa: E402
from validate import evaluate  # noqa: E402


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
WEIGHTS = Path(RUN["weights_dir"])
OUTPUT = ROOT / "results" / "posttraining_validation" / "candidate_selection"
CANDIDATES = (24, 32, 40, 48)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_model(epoch: int, device: torch.device) -> tuple[torch.nn.Module, Path]:
    path = WEIGHTS / f"epoch_{epoch:03d}.pth.tar"
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if int(payload["epoch"]) != epoch:
        raise RuntimeError(f"Checkpoint epoch mismatch: {path}")
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]),
        contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]),
        combined_bound=float(bounds["combined"]),
    )
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).eval(), path


def gradient(image: np.ndarray) -> np.ndarray:
    source = image.astype(np.float32) / 255.0
    gx = cv2.Sobel(source, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(source, cv2.CV_32F, 0, 1, ksize=3)
    return np.hypot(gx, gy)


def appearance_metrics(raw: np.ndarray, output: np.ndarray) -> dict[str, float]:
    raw_f = raw.astype(np.float32)
    out_f = output.astype(np.float32)
    delta = out_f - raw_f
    raw_g = gradient(raw)
    out_g = gradient(output)
    support = raw_g >= np.percentile(raw_g, 85.0)
    expanded = cv2.dilate(support.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    out_strong = out_g >= np.percentile(out_g, 95.0)
    off_source = out_strong & ~expanded
    flat = raw_g <= np.percentile(raw_g, 35.0)
    return {
        "mean_signed_change_gray": float(delta.mean()),
        "mean_abs_change_gray": float(np.abs(delta).mean()),
        "p95_abs_change_gray": float(np.percentile(np.abs(delta), 95.0)),
        "edge_gain_on_raw_support": float(out_g[support].mean() / max(raw_g[support].mean(), 1e-9)),
        "off_source_strong_edge_fraction": float(off_source.mean()),
        "flat_mean_abs_change_gray": float(np.abs(delta[flat]).mean()),
        "low_clip_fraction": float((output <= 0).mean()),
        "high_clip_fraction": float((output >= 255).mean()),
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    if RUN.get("status") != "completed" or int(RUN.get("completed_epoch", 0)) != 48:
        raise RuntimeError("R103 formal training is not complete")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(6)
    dataset = R103Dataset("internal_test", 384, 48)
    loader = DataLoader(dataset, batch_size=6, shuffle=False, num_workers=2, pin_memory=True)
    internal_rows: list[dict[str, object]] = []
    appearance_rows: list[dict[str, object]] = []
    manifests: list[dict[str, object]] = []
    preview_sources = [Path(value) for value in CONFIG["validation"]["real_preview_sources"]]
    preview_dir = OUTPUT / "real_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    for epoch in CANDIDATES:
        model, checkpoint = load_model(epoch, device)
        validation = evaluate(model, loader, device, core_size=288, amp_enabled=device.type == "cuda")
        internal_rows.append({"epoch": epoch, **validation["metrics"], **{
            f"axis_{name}": value for name, value in validation["axes"].items()
        }})
        manifests.append({"epoch": epoch, "path": str(checkpoint), "sha256": sha256(checkpoint)})
        for source_path in preview_sources:
            raw = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)
            if raw is None:
                raise FileNotFoundError(source_path)
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            with torch.inference_mode(), torch.autocast(
                device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"
            ):
                prediction = model(tensor).float()[0, 0]
            output = np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
            appearance_rows.append({
                "epoch": epoch,
                "image": source_path.stem,
                **appearance_metrics(raw, output),
            })
            comparison = np.concatenate([raw, output, np.clip(128 + 5 * (output.astype(np.int16) - raw.astype(np.int16)), 0, 255).astype(np.uint8)], axis=1)
            destination = preview_dir / f"{source_path.stem}_epoch_{epoch:03d}.png"
            if not cv2.imwrite(str(destination), comparison):
                raise RuntimeError(destination)
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"[candidate] epoch {epoch} complete", flush=True)

    internal = pd.DataFrame(internal_rows)
    appearance = pd.DataFrame(appearance_rows)
    internal.to_csv(OUTPUT / "internal_test_metrics.csv", index=False)
    appearance.to_csv(OUTPUT / "real_preview_metrics.csv", index=False)
    appearance.groupby("epoch", sort=True).agg({
        "mean_abs_change_gray": "median",
        "p95_abs_change_gray": "median",
        "edge_gain_on_raw_support": "median",
        "off_source_strong_edge_fraction": "median",
        "flat_mean_abs_change_gray": "median",
        "low_clip_fraction": "max",
        "high_clip_fraction": "max",
    }).reset_index().to_csv(OUTPUT / "real_preview_summary.csv", index=False)
    result = {
        "status": "complete",
        "formal_run_id": RUN["run_id"],
        "formal_completed_epoch": RUN["completed_epoch"],
        "device": str(device),
        "candidate_epochs": list(CANDIDATES),
        "internal_test_scenes": len(dataset),
        "checkpoint_manifest": manifests,
        "tables": {
            "internal_test": str(OUTPUT / "internal_test_metrics.csv"),
            "real_preview": str(OUTPUT / "real_preview_metrics.csv"),
            "real_preview_summary": str(OUTPUT / "real_preview_summary.csv"),
        },
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
