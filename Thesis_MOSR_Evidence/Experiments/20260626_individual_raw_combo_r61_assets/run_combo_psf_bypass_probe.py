from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


PROJECT_ROOT = Path(str(_PROJECT_ROOT))
MODEL_DIR = PROJECT_ROOT / "Model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest import (  # noqa: E402
    extract_state_dict,
    infer_arch_from_state,
    resolve_device,
    run_one,
)
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord  # noqa: E402


def filtered_load(model: torch.nn.Module, state_dict: dict[str, torch.Tensor]) -> dict:
    target = model.state_dict()
    kept = {}
    skipped = []
    for key, value in state_dict.items():
        if key not in target:
            skipped.append(key)
            continue
        if hasattr(value, "shape") and tuple(value.shape) != tuple(target[key].shape):
            skipped.append(key)
            continue
        kept[key] = value

    result = model.load_state_dict(kept, strict=False)
    return {
        "kept_count": len(kept),
        "skipped_count": len(skipped),
        "missing_keys": list(result.missing_keys),
        "unexpected_keys": list(result.unexpected_keys),
        "skipped_key_prefixes": sorted({key.split(".")[0] for key in skipped}),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--meta", type=Path, default=None)
    args = parser.parse_args()

    device = resolve_device(args.device)
    ckpt_obj = torch.load(args.weights, map_location="cpu")
    state_dict = extract_state_dict(ckpt_obj)
    arch = infer_arch_from_state(state_dict, ckpt_obj=ckpt_obj)

    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=False,
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=bool(arch["use_band_limit"]),
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        psf_fitted_path=None,
        weak_psf_enable=False,
        boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
        boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
        boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
        boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
        boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
        boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
        boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
        boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
        boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
    ).to(device)
    model.eval()

    load_info = filtered_load(model, state_dict)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metrics = run_one(model, device, args.input, args.output, align_factor=64, gt_path=None)

    meta = {
        "weights": str(args.weights),
        "input": str(args.input),
        "output": str(args.output),
        "device": str(device),
        "probe": "combo_core_without_physics_layer_or_weak_psf",
        "arch_original_use_physics_layer": bool(arch["use_physics_layer"]),
        "arch_original_weak_psf_enable": bool(arch["weak_psf_enable"]),
        "load_info": load_info,
        "metrics": metrics,
    }
    meta_path = args.meta or args.output.with_suffix(".meta.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
