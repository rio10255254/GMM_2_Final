"""Frozen-R109 A/B probe for the R115 normal-profile evidence tower."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from model.r115_model import build_model, count_parameters, load_r109_for_probe
from training.losses import profile_evidence_components, profile_objective
from training.r115_dataset import R115Dataset
PROJECT_ROOT = Path(__file__).resolve().parents[3]


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def flatten(batch: dict, device: torch.device) -> dict[str, torch.Tensor]:
    result = {}
    for name in ("source", "target", "mask", "sdf", "edge"):
        tensor = batch[name]
        result[name] = tensor.reshape(-1, *tensor.shape[2:]).to(device, non_blocking=True)
    for name in ("identity", "midpoint", "polarity", "width_gain_target"):
        result[name] = batch[name].reshape(-1).to(device, non_blocking=True)
    return result


def make_loader(dataset: R115Dataset, batch_size: int, workers: int, shuffle: bool, seed: int) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=workers,
        pin_memory=True,
        drop_last=shuffle,
        generator=generator,
    )


@torch.no_grad()
def evaluate(model, device: torch.device, record_ids: list[str]) -> dict[str, float]:
    dataset = R115Dataset("validation", epoch=0, arm="B")
    wanted = set(record_ids)
    dataset.records = [row for row in dataset.records if row["record_id"] in wanted]
    loader = make_loader(dataset, 8, 0, False, CONFIG["seed"] + 99)
    populations = json.loads((ROOT / "data" / "validation_populations.json").read_text(encoding="utf-8"))
    supplemental = set(populations["supplemental_record_ids"])
    totals = {
        "common_count": 0.0,
        "supplemental_count": 0.0,
        "common_base_mae_gray": 0.0,
        "common_final_mae_gray": 0.0,
        "supplemental_base_mae_gray": 0.0,
        "supplemental_final_mae_gray": 0.0,
        "clear_delta_gray": 0.0,
        "clear_count": 0.0,
        "shift_factor_mean": 0.0,
        "width_factor_mean": 0.0,
        "selector_batches": 0.0,
    }
    model.eval()
    for raw_batch in loader:
        batch = flatten(raw_batch, device)
        details = model.forward_details(batch["source"])
        batch_size = len(raw_batch["record_id"])
        final_error = (details.output - batch["target"]).abs().flatten(1).mean(1).reshape(batch_size, 2)
        base_error = (details.baseline_output - batch["target"]).abs().flatten(1).mean(1).reshape(batch_size, 2)
        clear_delta = (details.output - details.baseline_output).abs().flatten(1).mean(1).reshape(batch_size, 2)[:, 1]
        for index, record_id in enumerate(raw_batch["record_id"]):
            prefix = "supplemental" if record_id in supplemental else "common"
            totals[f"{prefix}_count"] += 1
            totals[f"{prefix}_base_mae_gray"] += float(base_error[index, 0].cpu()) * 255
            totals[f"{prefix}_final_mae_gray"] += float(final_error[index, 0].cpu()) * 255
        totals["clear_delta_gray"] += float(clear_delta.sum().cpu()) * 255
        totals["clear_count"] += batch_size
        totals["shift_factor_mean"] += float(details.shift_factor.mean().cpu())
        totals["width_factor_mean"] += float(details.width_factor.mean().cpu())
        totals["selector_batches"] += 1
    result = {}
    for prefix in ("common", "supplemental"):
        count = max(totals[f"{prefix}_count"], 1)
        base = totals[f"{prefix}_base_mae_gray"] / count
        final = totals[f"{prefix}_final_mae_gray"] / count
        result[f"{prefix}_scenes"] = totals[f"{prefix}_count"]
        result[f"{prefix}_base_mae_gray"] = base
        result[f"{prefix}_final_mae_gray"] = final
        result[f"{prefix}_gain_gray"] = base - final
    result["clear_delta_gray"] = totals["clear_delta_gray"] / max(totals["clear_count"], 1)
    result["shift_factor_mean"] = totals["shift_factor_mean"] / max(totals["selector_batches"], 1)
    result["width_factor_mean"] = totals["width_factor_mean"] / max(totals["selector_batches"], 1)
    return result


def train_arm(
    arm: str,
    run_root: Path,
    validation_ids: list[str],
    device: torch.device,
    max_batches: int = 0,
) -> dict:
    probe = CONFIG["short_probe"]
    seed = int(CONFIG["seed"])
    seed_everything(seed)
    checkpoint = Path(PROJECT_ROOT / probe["baseline_checkpoint"])
    if sha256(checkpoint) != probe["baseline_checkpoint_sha256"]:
        raise RuntimeError("R109 baseline checkpoint hash mismatch")
    model = build_model().to(device)
    baseline_metadata = load_r109_for_probe(model, checkpoint)
    for parameter in model.detector_parameters() + model.geometry_parameters():
        parameter.requires_grad_(False)
    for parameter in model.profile_parameters():
        parameter.requires_grad_(True)
    optimizer = torch.optim.AdamW(
        model.profile_parameters(),
        lr=float(probe["learning_rate"]),
        weight_decay=float(probe["weight_decay"]),
    )
    dataset = R115Dataset("train", epoch=0, arm=arm)
    arm_root = run_root / f"arm_{arm}"
    (arm_root / "weights").mkdir(parents=True, exist_ok=True)
    rows = []
    best = None
    started = time.perf_counter()
    for epoch in range(1, int(probe["epochs"]) + 1):
        dataset.set_epoch(epoch)
        loader = make_loader(dataset, int(probe["batch_size"]), int(probe["workers"]), True, seed + epoch)
        model.train()
        totals: dict[str, float] = {}
        batches = 0
        for raw_batch in loader:
            batch = flatten(raw_batch, device)
            optimizer.zero_grad(set_to_none=True)
            details = model.forward_details(batch["source"])
            components, _shift, _width = profile_evidence_components(
                details, batch["source"], batch["target"], batch["sdf"], batch["identity"]
            )
            loss = profile_objective(components)
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("non-finite R115 probe loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.profile_parameters(), 1.0)
            optimizer.step()
            totals["loss"] = totals.get("loss", 0.0) + float(loss.detach().cpu())
            for name, value in components.items():
                totals[name] = totals.get(name, 0.0) + float(value.detach().cpu())
            batches += 1
            if max_batches > 0 and batches >= max_batches:
                break
        validation = evaluate(model, device, validation_ids)
        row = {
            "epoch": epoch,
            "batches": batches,
            **{f"train_{name}": value / max(batches, 1) for name, value in totals.items()},
            **{f"validation_{name}": value for name, value in validation.items()},
        }
        rows.append(row)
        torch.save(
            {
                "profile": {name: tensor for name, tensor in model.state_dict().items() if name.startswith("profile_") or "adjust_head" in name},
                "epoch": epoch,
                "arm": arm,
                "baseline": baseline_metadata,
                "formal": False,
            },
            arm_root / "weights" / f"epoch_{epoch:03d}.pth",
        )
        candidate = (
            validation["common_gain_gray"],
            validation["supplemental_gain_gray"],
            -validation["clear_delta_gray"],
        )
        if best is None or candidate > best[0]:
            best = (candidate, epoch, validation)
        print(json.dumps({"arm": arm, **row}), flush=True)
    with (arm_root / "training_log.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    state = {
        "status": "complete",
        "arm": arm,
        "formal": False,
        "epochs": int(probe["epochs"]),
        "steps": sum(row["batches"] for row in rows),
        "best_epoch": best[1],
        "best_validation": best[2],
        "elapsed_seconds": time.perf_counter() - started,
        "baseline": baseline_metadata,
        "profile_parameters": sum(parameter.numel() for parameter in model.profile_parameters()),
    }
    (arm_root / "run_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="r115_data_architecture_ablation")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--arms", nargs="+", default=["A", "B"])
    args = parser.parse_args()
    run_root = ROOT / "runs" / args.run_id
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True)
    populations = json.loads((ROOT / "data" / "validation_populations.json").read_text(encoding="utf-8"))
    common = populations["common_record_ids"][:88]
    supplemental = populations["supplemental_record_ids"]
    validation_ids = common + supplemental
    if args.smoke:
        CONFIG["short_probe"]["epochs"] = 1
        CONFIG["short_probe"]["workers"] = 0
        CONFIG["short_probe"]["batch_size"] = 2
    device = torch.device(args.device)
    arms = [str(value).upper() for value in args.arms]
    states = {
        arm: train_arm(
            arm, run_root, validation_ids, device,
            max_batches=2 if args.smoke else 0,
        )
        for arm in arms
    }
    decision = {
        "status": "complete",
        "run_id": args.run_id,
        "arms": states,
    }
    if "A" in states and "B" in states:
        a = states["A"]["best_validation"]
        b = states["B"]["best_validation"]
        decision["comparison"] = {
            "common_gain_delta_b_minus_a_gray": b["common_gain_gray"] - a["common_gain_gray"],
            "supplemental_gain_delta_b_minus_a_gray": b["supplemental_gain_gray"] - a["supplemental_gain_gray"],
            "clear_delta_b_minus_a_gray": b["clear_delta_gray"] - a["clear_delta_gray"],
        }
        decision["data_b_preferred"] = (
            b["supplemental_gain_gray"] > a["supplemental_gain_gray"]
            and b["common_gain_gray"] >= a["common_gain_gray"] - 0.01
            and b["clear_delta_gray"] <= a["clear_delta_gray"] + 0.001
        )
    (run_root / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(run_root / "decision.json")


if __name__ == "__main__":
    main()
