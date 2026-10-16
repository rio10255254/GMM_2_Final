"""Pretraining audit for data provenance, subpixel labels, and architecture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inference.tiled import forward_tiled
from model.r117_model import build_model, count_parameters


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def centroid(mask: np.ndarray) -> tuple[float, float]:
    mass = float(mask.sum())
    yy, xx = np.indices(mask.shape, dtype=np.float64)
    return float((xx * mask).sum() / mass), float((yy * mask).sum() / mass)


def main() -> int:
    config_path = ROOT / "config" / "experiment.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    package = ROOT / config["data"]["package_root"]
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest["records"]
    train = {int(row["scene_index"]) for row in records if row["split"] == "train"}
    validation = {int(row["scene_index"]) for row in records if row["split"] == "validation"}
    sampled = [row for row in records if row["role"] != "flat_negative" and row["family"] not in {"dense_array", "mixed_field"}][::max(1, len(records) // 200)][:200]
    center_errors, low_res_differences, fractional_coverages = [], [], []
    for row in sampled:
        ma = np.load(package / row["mask_a"]).astype(np.float32) / 255.0
        mb = np.load(package / row["mask_b"]).astype(np.float32) / 255.0
        ta = np.load(package / row["target_a"]).astype(np.float32) / 255.0
        tb = np.load(package / row["target_b"]).astype(np.float32) / 255.0
        ax, ay = centroid(ma); bx, by = centroid(mb)
        center_errors.append(np.hypot((bx - ax) - float(row["pair_dx_px"]), (by - ay) - float(row["pair_dy_px"])))
        matrix = np.asarray(((1, 0, row["pair_dx_px"]), (0, 1, row["pair_dy_px"])), np.float32)
        low_shift = cv2.warpAffine(ta, matrix, (ta.shape[1], ta.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
        low_res_differences.append(float(np.mean(np.abs(tb - low_shift))))
        fractional_coverages.append(float(np.mean((ma > 0) & (ma < 1))))

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = build_model().to(device).eval()
    value = torch.rand(1, 1, 512, 544, device=device)
    with torch.inference_mode():
        identity_output = model(value)
    generator = torch.Generator(device=device).manual_seed(117)
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if any(token in name for token in ("boundary_head", "sdf_head", "width_head", "shift_head", "detail_head", "subpixel_refiner.2")):
                parameter.copy_(0.01 * torch.randn(parameter.shape, generator=generator, device=device, dtype=parameter.dtype))
    with torch.inference_mode():
        direct = model(value)
        tiled = forward_tiled(model, value, core_size=256, halo=224)
    names = set(dict(model.named_modules()))
    forbidden = [name for name in names if any(token in name.lower() for token in ("batchnorm", "instancenorm", "layernorm", "adaptiveavgpool"))]
    payload = {
        "status": "complete",
        "config_sha256": sha256(config_path), "manifest_sha256": sha256(manifest_path),
        "checks": {
            "formal_counts": manifest["counts"] == {"train": 5000, "validation": 512},
            "zero_group_overlap": not bool(train & validation),
            "no_real_training_pixels": manifest["training_uses_real_pixels"] is False,
            "translation_rendered_before_downsampling": manifest["translation_rendered_before_downsampling"] is True,
            "supersample_factor_is_8": manifest["supersample_factor"] == 8,
            "all_sampled_labels_have_antialiasing": min(fractional_coverages) > 0,
            "translated_label_is_not_low_resolution_warp": float(np.median(low_res_differences)) > 0,
            "median_pair_centroid_error_px": float(np.median(center_errors)),
            "p95_pair_centroid_error_px": float(np.percentile(center_errors, 95)),
            "initial_identity_max_abs": float((identity_output - value).abs().max().cpu()),
            "randomized_head_tile_max_abs": float((direct - tiled).abs().max().cpu()),
            "forbidden_spatial_normalization_or_global_pooling": forbidden,
            "parameters": count_parameters(model),
        },
    }
    required = (
        payload["checks"]["formal_counts"], payload["checks"]["zero_group_overlap"],
        payload["checks"]["no_real_training_pixels"], payload["checks"]["translation_rendered_before_downsampling"],
        payload["checks"]["supersample_factor_is_8"], payload["checks"]["all_sampled_labels_have_antialiasing"],
        payload["checks"]["translated_label_is_not_low_resolution_warp"],
        payload["checks"]["initial_identity_max_abs"] < 1.0e-6,
        payload["checks"]["randomized_head_tile_max_abs"] < 0.05 / 255.0, not forbidden,
    )
    payload["passed"] = all(required)
    output = ROOT / "validation" / "pretraining_validation.json"
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["passed"]:
        raise RuntimeError("R117 pretraining validation failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
