"""Inspect R104 E48 proposals, gates, branch deltas, and exposure response."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model"))
from r104_model import build_model  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "posttraining_validation" / "model_internals"
R73 = Path(r"D:\GMM_2_Final\Experiments\R73_R61ExpandedSyntheticACMGeneralization\data\r73_synthetic_acm_val\src")
R74 = Path(r"D:\GMM_2_Final\Experiments\R74_R61HardMicroscopyACMGeneralization\data\r74_hard_acm_val\src")
SEM = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack")


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def build_r104(device: torch.device) -> torch.nn.Module:
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]), low_bound=float(bounds["radiometry"]),
        illumination_bound=float(bounds["illumination"]), contour_bound=float(bounds["contour_proposal"]),
        texture_bound=float(bounds["texture_proposal"]), combined_bound=float(bounds["combined"]),
        gate_initial_probability=float(CONFIG["model"]["gate_initial_probability"]),
    )
    payload = torch.load(Path(RUN["weights_dir"]) / "epoch_048.pth.tar", map_location="cpu", weights_only=False)
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).to(memory_format=torch.channels_last).eval()


def center_crop(image: np.ndarray, maximum: int = 768) -> np.ndarray:
    size = min(maximum, image.shape[0] // 8 * 8, image.shape[1] // 8 * 8)
    y, x = (image.shape[0] - size) // 2, (image.shape[1] - size) // 2
    return image[y:y + size, x:x + size]


@torch.inference_mode()
def inspect(model: torch.nn.Module, device: torch.device, suite: str, family: str, image_id: str, path: Path) -> dict[str, object]:
    raw = center_crop(read_gray(path))
    tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device).contiguous(memory_format=torch.channels_last)
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
        details = model.forward_details(tensor)
    fields = {
        "low": (details.low_proposal, details.low_gate, details.low_delta),
        "illumination": (details.illumination_proposal, details.illumination_gate, details.illumination_delta),
        "contour": (details.contour_proposal, details.contour_gate, details.contour_delta),
        "texture": (details.texture_proposal, details.texture_gate, details.texture_delta),
    }
    row: dict[str, object] = {
        "suite": suite, "family": family, "image_id": image_id, "path": str(path),
        "raw_mean": float(tensor.mean()), "raw_std": float(tensor.std()),
        "output_mean_abs_change": float((details.output.float() - tensor).abs().mean()),
        "output_mean_signed_change": float((details.output.float() - tensor).mean()),
        "output_p99_abs_change": float(torch.quantile((details.output.float() - tensor).abs().flatten(), .99)),
        "total_delta_mean_abs": float(details.total_delta.float().abs().mean()),
        "low_clip_fraction": float((details.output <= 0).float().mean()),
        "high_clip_fraction": float((details.output >= 1).float().mean()),
        "sdf_positive_fraction": float((details.signed_distance > 0).float().mean()),
        "sdf_mean_abs": float(details.signed_distance.float().abs().mean()),
    }
    branch_abs_sum = 0.0
    for name, (proposal, gate, delta) in fields.items():
        proposal, gate, delta = proposal.float(), gate.float(), delta.float()
        branch_abs = float(delta.abs().mean())
        branch_abs_sum += branch_abs
        row.update({
            f"{name}_proposal_mean_abs": float(proposal.abs().mean()),
            f"{name}_gate_mean": float(gate.mean()), f"{name}_gate_std": float(gate.std()),
            f"{name}_delta_mean_abs": branch_abs, f"{name}_delta_mean_signed": float(delta.mean()),
        })
    row["cancellation_fraction"] = float(1.0 - float(details.total_delta.float().abs().mean()) / max(branch_abs_sum, 1e-12))
    return row


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = build_r104(device)
    sources: list[tuple[str, str, str, Path]] = []
    for path in sorted(R73.rglob("*.bmp")):
        sources.append(("R73_novel_shapes", path.parent.name, path.stem, path))
    for path in sorted(R74.rglob("*.bmp")):
        sources.append(("R74_hard_microscopy", path.parent.name, path.stem, path))
    for exposure in range(13, 25):
        sources.append(("SEM_exposure", str(exposure), str(exposure), SEM / f"{exposure}.bmp"))
    preview = json.loads((ROOT / "data" / "fixed_real_preview.json").read_text(encoding="utf-8"))
    for item in preview["images"]:
        sources.append(("real_optical", str(item["label"]), str(item["label"]), Path(item["path"])))
    rows = []
    for index, item in enumerate(sources, 1):
        rows.append(inspect(model, device, *item))
        if index % 40 == 0:
            print(f"[internals] {index}/{len(sources)}", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "branch_statistics.csv", index=False)
    numeric = [column for column in table.columns if column not in {"suite", "family", "image_id", "path"}]
    family = table.groupby(["suite", "family"], sort=False)[numeric].median().reset_index()
    family.to_csv(OUTPUT / "family_summary.csv", index=False)
    suite = table.groupby("suite", sort=False)[numeric].median().reset_index()
    suite.to_csv(OUTPUT / "suite_summary.csv", index=False)
    summary = {
        "status": "complete", "checkpoint_epoch": 48, "images": len(table),
        "branch_table": str(OUTPUT / "branch_statistics.csv"),
        "family_summary": str(OUTPUT / "family_summary.csv"),
        "suite_summary": str(OUTPUT / "suite_summary.csv"),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
