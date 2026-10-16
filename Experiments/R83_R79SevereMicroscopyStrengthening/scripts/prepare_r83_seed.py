"""Create and verify an exact, reset R83 seed from R79 epoch-23 EMA weights."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "model"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
PARENT = CONFIG["parent_model"]
SOURCE = Path(PARENT["checkpoint"])
TARGET = ROOT / PARENT["seed_checkpoint"]
REPORT = ROOT / "reports" / "seed_parity_audit.json"
MONITOR = ROOT / "data" / "live_validation" / "50x_array_raw.bmp"

sys.path.insert(0, str(MODEL_DIR))
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_state(state: dict) -> dict:
    return {
        (name[7:] if name.startswith("module.") else name): value.detach().cpu().clone()
        for name, value in state.items()
    }


def build_model() -> torch.nn.Module:
    return GeoEdgeAlignSR_v1_v5_NoCoord(
        psf_fitted_path=str(MODEL_DIR / "analytic_psf_bank.mat"),
        psf_grid_rows=3,
        psf_grid_cols=3,
        psf_use_stack_mean=True,
        psf_deconv_reg=30.0,
        psf_phys_alpha_init=0.05,
        psf_phys_alpha_min=0.0,
        psf_phys_alpha_max=0.20,
        use_upsample_conv=True,
        use_band_limit=False,
        weak_psf_enable=True,
        weak_psf_k=4,
        weak_psf_beta_init=0.0,
        weak_psf_beta_scale_max=0.0,
        learnable_blur=False,
        use_bottleneck_se=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=16,
        boundary_residual_adapter_max=0.018,
        boundary_residual_adapter_gate_bias=-2.0,
        boundary_residual_adapter_delta_bias=True,
        boundary_residual_adapter_zero_mean=False,
        boundary_residual_adapter_edge_gate=False,
        boundary_residual_adapter_polarity_split=False,
        boundary_residual_adapter_orientation_inputs=True,
        raw_anchor_output_mode="none",
        quality_gate_enable=False,
    ).eval()


def monitor_tensor() -> torch.Tensor:
    image = cv2.imdecode(np.fromfile(MONITOR, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read parity monitor: {MONITOR}")
    image = cv2.resize(image, (256, 256), interpolation=cv2.INTER_AREA)
    return torch.from_numpy(image.astype(np.float32) / 255.0)[None, None]


def main() -> int:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    source_hash = sha256(SOURCE)
    if source_hash != PARENT["checkpoint_sha256"]:
        raise RuntimeError(f"R79 checkpoint hash changed: {source_hash}")
    source_checkpoint = torch.load(SOURCE, map_location="cpu")
    if int(source_checkpoint.get("epoch", -1)) != int(PARENT["expected_epoch"]):
        raise RuntimeError(f"Expected R79 epoch {PARENT['expected_epoch']}, got {source_checkpoint.get('epoch')}")
    if not source_checkpoint.get("ema_state_dict"):
        raise RuntimeError("R79 checkpoint has no EMA state")
    ema = clean_state(source_checkpoint["ema_state_dict"])

    parent_model = build_model()
    parent_model.load_state_dict(ema, strict=True)
    tensor = monitor_tensor()
    with torch.no_grad():
        parent_output = parent_model(tensor).float()

    payload = {
        "epoch": 0,
        "state_dict": ema,
        "ema_state_dict": {name: value.clone() for name, value in ema.items()},
        "optimizer": None,
        "r83_seed": {
            "source_checkpoint": str(SOURCE),
            "source_checkpoint_sha256": source_hash,
            "source_epoch": int(source_checkpoint["epoch"]),
            "source_state_key": "ema_state_dict",
            "epoch_reset": True,
            "optimizer_reset": True,
            "created_for": CONFIG["experiment_id"],
        },
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, TARGET)

    saved = torch.load(TARGET, map_location="cpu")
    seeded_model = build_model()
    seeded_model.load_state_dict(saved["state_dict"], strict=True)
    with torch.no_grad():
        seeded_output = seeded_model(tensor).float()
    max_parameter_difference = max(
        float(torch.max(torch.abs(saved["state_dict"][name].float() - ema[name].float())).item())
        for name in ema
    )
    max_inference_difference = float(torch.max(torch.abs(parent_output - seeded_output)).item())
    if max_parameter_difference != 0.0 or max_inference_difference != 0.0:
        raise RuntimeError(
            f"R83 seed parity failed: parameter={max_parameter_difference}, inference={max_inference_difference}"
        )
    report = {
        "passed": True,
        "experiment_id": CONFIG["experiment_id"],
        "source_checkpoint": str(SOURCE),
        "source_checkpoint_sha256": source_hash,
        "source_epoch": int(source_checkpoint["epoch"]),
        "source_state_key": "ema_state_dict",
        "seed_checkpoint": str(TARGET),
        "seed_checkpoint_sha256": sha256(TARGET),
        "state_key_count": len(ema),
        "max_parameter_abs_difference": max_parameter_difference,
        "max_inference_abs_difference": max_inference_difference,
        "monitor": str(MONITOR),
        "monitor_output_range": [float(parent_output.min()), float(parent_output.max())],
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
