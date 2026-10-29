"""Read-only CPU intervention sweep for R95 branch strength and gates."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(str(PROJECT_ROOT / 'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal'))
WEIGHTS = ROOT / "weights" / "formal" / "seed_950041" / "R95_scratch_seed950041_20260813_003125" / "weights"
BRANCHES = {
    "radiometry": ("radiometry_delta", "radiometry_raw"),
    "nuisance": ("nuisance_delta", "nuisance_raw"),
    "local_contrast": ("local_contrast_delta", "local_contrast_raw"),
    "boundary": ("boundary_delta", "boundary_restoration_raw"),
    "texture": ("texture_delta", "texture_restoration_raw"),
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load("r95_intervention_model", ROOT / "model" / "r95_model.py")
DATA = load("r95_intervention_data", ROOT / "training" / "r95_dataset.py")


def crop(x: torch.Tensor, margin: int = 96) -> torch.Tensor:
    return x[..., margin:-margin, margin:-margin]


def mae(a: torch.Tensor, b: torch.Tensor) -> float:
    return float(crop(a - b).abs().mean() * 255.0)


def output_from(raw: torch.Tensor, branches: dict[str, torch.Tensor]) -> torch.Tensor:
    correction = torch.clamp(sum(branches.values()), -0.34, 0.34)
    return torch.clamp(raw + correction, 0.0, 1.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epoch", type=int, default=40)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "model_internal_analysis_epoch40" / "branch_interventions.json")
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    dataset = DATA.R95SceneDataset(
        SOURCE, manifest, "validation", 768, 384, 0,
        all_observations=True, master_seed=950041,
    )
    selected = {}
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        if role not in selected:
            selected[role] = dataset[index]
    checkpoint = torch.load(WEIGHTS / f"epoch_{args.epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
    model = MODEL.build_model(base=16).eval()
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    rows = []
    for role in sorted(selected):
        item = selected[role]
        raw = item["source"][0:1]
        target = item["supervised_target"][0:1]
        with torch.inference_mode():
            details = model(raw, return_details=True)
        current = {name: details[keys[0]] for name, keys in BRANCHES.items()}
        ungated = {name: details[keys[1]] for name, keys in BRANCHES.items()}
        baseline = mae(raw, target)
        model_mae = mae(output_from(raw, current), target)
        row = {
            "role": role,
            "raw_mae_gray": baseline,
            "model_mae_gray": model_mae,
            "model_improvement_gray": baseline - model_mae,
            "branches": {},
        }
        for name in BRANCHES:
            branch = {}
            for label, replacement in (
                ("removed", torch.zeros_like(current[name])),
                ("current", current[name]),
                ("double_current", 2.0 * current[name]),
                ("fully_open", ungated[name]),
            ):
                candidate = dict(current)
                candidate[name] = replacement
                error = mae(output_from(raw, candidate), target)
                branch[label] = {
                    "mae_gray": error,
                    "improvement_vs_current_gray": model_mae - error,
                }
            # Best scalar strength is diagnostic only; it is not a proposed
            # inference knob and is selected independently per validation role.
            sweep = []
            for scale in np.linspace(0.0, 4.0, 17):
                candidate = dict(current)
                candidate[name] = current[name] * float(scale)
                sweep.append((float(scale), mae(output_from(raw, candidate), target)))
            best_scale, best_error = min(sweep, key=lambda value: value[1])
            branch["oracle_scalar_sweep"] = {
                "best_scale": best_scale,
                "best_mae_gray": best_error,
                "improvement_vs_current_gray": model_mae - best_error,
            }
            row["branches"][name] = branch
        rows.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.with_suffix(".progress.json").write_text(json.dumps({
            "status": "running", "epoch": args.epoch, "last_role": role,
            "completed": len(rows), "total": len(selected),
        }, indent=2), encoding="utf-8")
    payload = {"analysis_id": "R95_BRANCH_INTERVENTION_V1", "epoch": args.epoch, "device": "cpu", "rows": rows}
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    args.output.with_suffix(".progress.json").write_text(json.dumps({
        "status": "complete", "epoch": args.epoch, "completed": len(rows), "total": len(rows),
        "output": str(args.output),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"status": "complete", "rows": len(rows), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
