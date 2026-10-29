"""Reproducible read-only causal audit of final R96 and its training schedule."""
from __future__ import annotations

from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
PACKAGE = Path(PROJECT_ROOT / DESIGN["data"]["source_package"])
MANIFEST = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
WEIGHTS = ROOT / "weights" / "formal" / "seed_960041" / "R96_scratch_seed960041_20260813_131438" / "weights"
OUTPUT = ROOT / "results" / "deep_diagnosis" / "internal_causes.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load("r96_deep_model", ROOT / "model" / "r96_model.py")
DATA = load("r96_deep_data", ROOT / "training" / "r96_dataset.py")


def stage(epoch: int) -> tuple[int, int, int]:
    if epoch <= 8:
        return 512, 256, 4
    if epoch <= 30:
        return 768, 384, 2
    return 896, 512, 1


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(WEIGHTS / "epoch_044.pth.tar", map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=int(DESIGN["architecture"]["model_width"]))
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    model.eval().to(device)

    role_schedule: list[dict[str, object]] = []
    cumulative = Counter()
    for epoch in range(1, 45):
        patch, core, batch = stage(epoch)
        dataset = DATA.R96SceneDataset(PACKAGE, MANIFEST, "train", patch, core, epoch, master_seed=960041)
        sampler = DATA.RoleBalancedBatchSampler(dataset, batch, 960041 + epoch * 101)
        batches = list(iter(sampler))[:96]
        counts = Counter()
        for indices in batches:
            role = dataset.role_at(indices[0])
            counts[role] += len(indices)
            cumulative[role] += len(indices)
        role_schedule.append({"epoch": epoch, "patch": patch, "scene_batch": batch, "role_scene_exposures": dict(counts)})

    dataset = DATA.R96SceneDataset(PACKAGE, MANIFEST, "validation", 256, 128, 0,
                                   all_observations=True, master_seed=960041)
    seen: set[str] = set()
    internal: list[dict[str, object]] = []
    halo = 64
    crop = (slice(None), slice(None), slice(halo, halo + 128), slice(halo, halo + 128))
    names = ["radiometry", "nuisance", "local_contrast", "boundary", "texture"]
    raw_keys = ["radiometry_raw", "nuisance_raw", "local_contrast_raw", "boundary_restoration_raw", "texture_restoration_raw"]
    delta_keys = ["radiometry_delta", "nuisance_delta", "local_contrast_delta", "boundary_delta", "texture_delta"]
    need_keys = ["need_radiometry", "need_noise", "need_local_contrast", "need_boundary", "need_texture"]
    with torch.inference_mode():
        for index in range(len(dataset)):
            item = dataset[index]
            role = str(item["role"])
            if role in seen:
                continue
            seen.add(role)
            source = item["source"].to(device)
            details = model(source, return_details=True)
            def gray(t: torch.Tensor) -> float:
                return float(t[crop].abs().mean() * 255.0)
            row: dict[str, object] = {
                "role": role,
                "target_change_mae_gray": gray(item["supervised_target"].to(device) - source),
                "output_change_mae_gray": gray(details["output"] - source),
                "output_error_mae_gray": gray(details["output"] - item["supervised_target"].to(device)),
                "predicted_need_mean": {name: float(details[key][crop].mean()) for name, key in zip(names, need_keys)},
            }
            for name, raw_key, delta_key in zip(names, raw_keys, delta_keys):
                row[f"{name}_ungated_mae_gray"] = gray(details[raw_key])
                row[f"{name}_applied_mae_gray"] = gray(details[delta_key])
                row[f"{name}_target_mae_gray"] = gray(item[f"{name}_target"].to(device))
            internal.append(row)
            if len(seen) == 8:
                break

    oracle = json.loads((ROOT / "reports" / "oracle_target_validation.json").read_text(encoding="utf-8"))
    capacity = json.loads((ROOT / "reports" / "branch_expressivity_analysis.json").read_text(encoding="utf-8"))
    payload = {
        "checkpoint_epoch": 44,
        "run_id": checkpoint["metadata"]["run_id"],
        "optimizer_updates": checkpoint["optimizer_updates"],
        "final_validation": checkpoint["metrics"]["validation"],
        "role_schedule": role_schedule,
        "cumulative_role_scene_exposures": dict(cumulative),
        "representative_internal_outputs": internal,
        "oracle_joint_improvement": oracle["oracle_semantics_support_joint_improvement"],
        "oracle_stable_improvement": oracle["stable_improvement"],
        "oracle_motion": {k: v for k, v in oracle["motion"].items() if k != "axis_regression_records"},
        "capacity_recommendation": capacity["recommendation"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "output": str(OUTPUT), "roles": len(internal)}, indent=2))


if __name__ == "__main__":
    main()
