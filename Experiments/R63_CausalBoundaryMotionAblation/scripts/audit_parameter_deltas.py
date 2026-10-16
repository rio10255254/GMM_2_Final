"""Quantify which trainable module groups changed in each matched R63 run."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = EXPERIMENT_ROOT / "results" / "training_manifest.json"
GROUPS = {
    "quality_gate": ("quality_gate",),
    "boundary_adapter": ("boundary_adapter",),
    "decoder_p1": ("p1",),
    "output_head": ("out",),
    "upsample_convs": ("u1.conv", "u2.conv", "u3.conv"),
}


def belongs(name: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in name for pattern in patterns)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise RuntimeError("Training manifest is incomplete")
    # Use the canonical source recorded by the experiment, not path inference from the run.
    package_root = (
        EXPERIMENT_ROOT.parents[1]
        / "Thesis_MOSR_Evidence"
        / "LabSystem_MOSR"
        / "Model_Packages"
        / "V42_SoftLabelSNR_FullStandalone_20260709"
    )
    base_checkpoint = package_root / "weights" / "base_v41_standalone_best_tradeoff.pth.tar"
    base = torch.load(base_checkpoint, map_location="cpu")["state_dict"]
    records = []
    for item in manifest["records"]:
        checkpoint = Path(item["checkpoint"])
        state = torch.load(checkpoint, map_location="cpu")["state_dict"]
        for group, patterns in GROUPS.items():
            final_sq = 0.0
            base_sq = 0.0
            delta_sq = 0.0
            common_count = 0
            new_count = 0
            for name, tensor in state.items():
                if not belongs(name, patterns):
                    continue
                final_tensor = tensor.detach().cpu().double()
                final_sq += float(torch.sum(final_tensor * final_tensor))
                if name in base and tuple(base[name].shape) == tuple(tensor.shape):
                    base_tensor = base[name].detach().cpu().double()
                    delta = final_tensor - base_tensor
                    base_sq += float(torch.sum(base_tensor * base_tensor))
                    delta_sq += float(torch.sum(delta * delta))
                    common_count += 1
                else:
                    new_count += 1
            final_norm = float(np.sqrt(final_sq))
            base_norm = float(np.sqrt(base_sq))
            delta_norm = float(np.sqrt(delta_sq))
            records.append(
                {
                    "variant": item["variant"],
                    "seed": item["seed"],
                    "module_group": group,
                    "common_tensor_count": common_count,
                    "new_tensor_count": new_count,
                    "module_present": bool(common_count + new_count),
                    "base_l2_norm": base_norm,
                    "final_l2_norm": final_norm,
                    "delta_l2_norm": delta_norm,
                    "relative_delta_pct": 100.0 * delta_norm / base_norm if base_norm > 1e-12 else float("nan"),
                }
            )
    table = pd.DataFrame(records)
    non_arch = table.loc[
        table["module_group"].eq("upsample_convs")
        & ~table["variant"].isin({"shift_safe_matched", "standard_upsample_matched"})
    ]
    if not np.allclose(non_arch["delta_l2_norm"].to_numpy(float), 0.0, atol=1e-12):
        raise RuntimeError("Frozen upsampling convolutions changed in a non-architecture condition")
    arch = table.loc[
        table["module_group"].eq("upsample_convs")
        & table["variant"].isin({"shift_safe_matched", "standard_upsample_matched"})
    ]
    if not (arch["delta_l2_norm"] > 0.0).all():
        raise RuntimeError("Architecture pair did not train the matched upsampling convolutions")
    boundary_removed = table.loc[
        table["variant"].eq("no_boundary_residual_adapter")
        & table["module_group"].eq("boundary_adapter")
    ]
    if len(boundary_removed) != 2 or boundary_removed["module_present"].any():
        raise RuntimeError("Boundary-adapter removal still contains boundary-adapter tensors")
    gate_removed = table.loc[
        table["variant"].eq("no_quality_gate")
        & table["module_group"].eq("quality_gate")
    ]
    if len(gate_removed) != 2 or gate_removed["module_present"].any():
        raise RuntimeError("Quality-gate removal still contains quality-gate tensors")
    output = EXPERIMENT_ROOT / "results" / "tables" / "parameter_delta_audit.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False, float_format="%.12g")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
