"""Run the configured four-scene-per-role E48 procedural validation and retain role breakdowns."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import torch
from torch.utils.data import DataLoader
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "training" / "train_r97_core.py"
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
OUTPUT = ROOT / "results" / "posttraining_validation" / "procedural_by_role"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAIN = load_module("r97_post_role_train", TRAIN_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def evaluate_split(
    model,
    device: torch.device,
    package: Path,
    manifest: dict,
    split: str,
    patch: int,
    core: int,
    per_role: int,
    seed: int,
) -> tuple[list[dict], dict[str, list[str]]]:
    dataset = TRAIN.DATA.R97SceneDataset(
        package, manifest, split, patch, core, 0,
        all_observations=True, master_seed=seed,
    )
    sampler = TRAIN.DATA.RoleBalancedValidationSampler(dataset, per_role=per_role)
    loader = DataLoader(dataset, batch_sampler=sampler, num_workers=0)
    sums: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    selected_scene_ids: dict[str, list[str]] = {}
    with torch.inference_mode():
        for raw in loader:
            role = str(raw["role"][0])
            scene_id = str(raw["scene_id"][0])
            batch, scenes, views = TRAIN.flatten_batch(raw, device)
            details = model(batch["source"], return_details=True)
            _branches, branch_values = TRAIN.branch_loss(details, batch, patch, core, "s")
            _output, values = TRAIN.output_loss(details, batch, patch, core)
            identity = TRAIN.core_crop(model(batch["target"]) - batch["target"], patch, core).abs().mean()
            motion = TRAIN.motion_centroid_loss(details, batch, patch, core, scenes, views)
            metrics = {
                **values,
                **{f"branch_{name}": value for name, value in branch_values.items()},
                "identity": identity,
                "identity_gray": identity * 255.0,
                "motion": motion,
            }
            role_sums = sums.setdefault(role, {})
            for name, value in metrics.items():
                role_sums[name] = role_sums.get(name, 0.0) + float(value) * scenes
            counts[role] = counts.get(role, 0) + scenes
            selected_scene_ids.setdefault(role, []).append(scene_id)
            print(f"[procedural] {split} {role} {len(selected_scene_ids[role])}/{per_role}", flush=True)
    rows: list[dict] = []
    for role in sorted(sums):
        rows.append({"split": split, "role": role, "scenes": counts[role], **{
            name: value / counts[role] for name, value in sums[role].items()
        }})
    return rows, selected_scene_ids


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite procedural validation: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    design = read_json(DESIGN_PATH)
    checkpoint_path = Path(PROJECT_ROOT / protocol["checkpoint"])
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != 48:
        raise RuntimeError("Checkpoint is not E48")
    package = Path(PROJECT_ROOT / design["data"]["source_package"])
    manifest = read_json(package / "manifest.json")
    patch, core = 768, 384
    per_role = int(design["training"]["final_validation_scenes_per_role"])
    model = TRAIN.MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    rows: list[dict] = []
    selected_scene_ids: dict[str, dict[str, list[str]]] = {}
    for split in ("validation", "internal_test"):
        split_rows, split_ids = evaluate_split(
            model, device, package, manifest, split, patch, core, per_role,
            int(design["independence"]["seed"]),
        )
        rows.extend(split_rows)
        selected_scene_ids[split] = split_ids
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "per_role_metrics.csv", index=False)
    metric_columns = [column for column in table.columns if column not in {"split", "role", "scenes"}]
    aggregate = {
        split: {
            column: float((group[column] * group["scenes"]).sum() / group["scenes"].sum())
            for column in metric_columns
        }
        for split, group in table.groupby("split", sort=False)
    }
    role_sets = {split: sorted(group["role"].unique()) for split, group in table.groupby("split", sort=False)}
    result = {
        "status": "complete",
        "checkpoint_epoch": 48,
        "checkpoint_state": protocol["checkpoint_state"],
        "splits": ["validation", "internal_test"],
        "roles": role_sets,
        "role_count_per_split": {split: len(roles) for split, roles in role_sets.items()},
        "configured_scenes_per_role": per_role,
        "all_roles_have_configured_count": bool((table["scenes"] == per_role).all()),
        "all_roles_have_unique_scene_ids": all(
            len(set(ids)) == per_role
            for split_ids in selected_scene_ids.values()
            for ids in split_ids.values()
        ),
        "total_scenes": int(table["scenes"].sum()),
        "selected_scene_ids": selected_scene_ids,
        "aggregate": aggregate,
        "per_role": rows,
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps({
        "status": result["status"],
        "role_count_per_split": result["role_count_per_split"],
        "total_scenes": result["total_scenes"],
        "all_roles_have_configured_count": result["all_roles_have_configured_count"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
