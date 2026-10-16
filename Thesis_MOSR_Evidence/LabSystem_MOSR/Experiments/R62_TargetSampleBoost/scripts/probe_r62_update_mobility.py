from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

import torch
import torch.nn.functional as F


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = LAB_ROOT.parents[1] / "Model"
R61_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts"
REPORT_DIR = EXPERIMENT_DIR / "reports" / "r62_update_mobility_probe"

sys.path.insert(0, str(EXPERIMENT_DIR / "scripts"))
sys.path.insert(0, str(R61_SCRIPT_DIR))
sys.path.insert(0, str(MODEL_DIR))

import launch_r62  # noqa: E402
import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer  # noqa: E402


def parameter_group(name: str) -> str:
    return str(name).split(".", 1)[0]


def tensor_state(model: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {name: param.detach().cpu().clone() for name, param in model.named_parameters()}


def summarize_parameter_delta(before: dict[str, torch.Tensor], after: dict[str, torch.Tensor]) -> list[dict[str, object]]:
    by_group: dict[str, dict[str, object]] = {}
    for name, before_tensor in before.items():
        if name not in after:
            continue
        group = parameter_group(name)
        row = by_group.setdefault(
            group,
            {
                "group": group,
                "tensors": 0,
                "changed_tensors": 0,
                "elements": 0,
                "changed_elements": 0,
                "sum_abs_delta": 0.0,
                "sum_abs_before": 0.0,
                "max_abs_delta": 0.0,
            },
        )
        delta = (after[name].float() - before_tensor.float()).abs()
        changed_elements = int((delta > 0).sum().item())
        row["tensors"] = int(row["tensors"]) + 1
        row["elements"] = int(row["elements"]) + int(delta.numel())
        row["changed_elements"] = int(row["changed_elements"]) + changed_elements
        if changed_elements > 0:
            row["changed_tensors"] = int(row["changed_tensors"]) + 1
        row["sum_abs_delta"] = float(row["sum_abs_delta"]) + float(delta.sum().item())
        row["sum_abs_before"] = float(row["sum_abs_before"]) + float(before_tensor.float().abs().sum().item())
        row["max_abs_delta"] = max(float(row["max_abs_delta"]), float(delta.max().item()) if delta.numel() else 0.0)
    rows = []
    for row in by_group.values():
        elements = max(1, int(row["elements"]))
        sum_abs_before = max(1e-12, float(row["sum_abs_before"]))
        row["mean_abs_delta"] = float(row["sum_abs_delta"]) / elements
        row["relative_l1_delta"] = float(row["sum_abs_delta"]) / sum_abs_before
        row["changed_element_pct"] = float(row["changed_elements"]) / elements * 100.0
        rows.append(row)
    return sorted(rows, key=lambda item: (-float(item["sum_abs_delta"]), str(item["group"])))


def summarize_gradients(model: torch.nn.Module) -> list[dict[str, object]]:
    by_group: dict[str, dict[str, object]] = {}
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        group = parameter_group(name)
        row = by_group.setdefault(
            group,
            {
                "group": group,
                "trainable_tensors": 0,
                "tensors_with_grad": 0,
                "elements": 0,
                "sum_abs_grad": 0.0,
                "max_abs_grad": 0.0,
            },
        )
        row["trainable_tensors"] = int(row["trainable_tensors"]) + 1
        row["elements"] = int(row["elements"]) + int(param.numel())
        if param.grad is None:
            continue
        grad = param.grad.detach().float().abs()
        row["tensors_with_grad"] = int(row["tensors_with_grad"]) + 1
        row["sum_abs_grad"] = float(row["sum_abs_grad"]) + float(grad.sum().item())
        row["max_abs_grad"] = max(float(row["max_abs_grad"]), float(grad.max().item()) if grad.numel() else 0.0)
    rows = []
    for row in by_group.values():
        elements = max(1, int(row["elements"]))
        row["mean_abs_grad"] = float(row["sum_abs_grad"]) / elements
        rows.append(row)
    return sorted(rows, key=lambda item: (-float(item["sum_abs_grad"]), str(item["group"])))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe whether R62 target-boost training can actually move model weights.")
    parser.add_argument("--candidate", default=launch_r62.R62_CANDIDATE_V3)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--mode", choices=["candidate", "unlocked"], default="candidate")
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    return parser.parse_args()


def configure(candidate: str, device: str, lr: float | None):
    launch_r62.patch_r61_registry()
    r61 = launch_r62.r61
    parser = launch_r62.build_arg_parser()
    argv = [
        "--candidate",
        candidate,
        "--data-root",
        str(launch_r62.DEFAULT_DATA_ROOT),
        "--base-checkpoint",
        str(launch_r62.R61_V16_CHECKPOINT),
        "--device",
        device,
        "--num-workers",
        "0",
        "--num-epoch",
        "1",
        "--max-train-batches",
        "1",
        "--run-suffix",
        "update_probe",
    ]
    if lr is not None:
        argv.extend(["--lr", str(lr)])
    args, _remaining = parser.parse_known_args(argv)
    profile_name = r61.PROFILE_BY_CANDIDATE[str(args.candidate)]
    settings = r61.CANDIDATE_SETTINGS[str(args.candidate)]
    data_dir, manifest = r61.ensure_data_package(
        profile_name,
        args.data_root,
        required_roles=tuple(settings.get("required_roles", tuple(sorted(r61.REQUIRED_R61_ROLES)))),
    )
    split_info = r61.prepare_grouped_fixed_split(package_dir=data_dir, manifest=manifest, val_ratio=0.10, seed=1337)
    r61.configure_trainer(trainer, args, data_dir, fixed_split_dir=Path(split_info["split_dir"]))
    trainer.CFG.NUM_WORKERS = 0
    trainer.CFG.DATALOADER_PERSISTENT_WORKERS = False
    trainer.CFG.DATALOADER_PREFETCH_FACTOR = 2
    return args, data_dir, manifest, split_info


def apply_probe_mode(mode: str) -> None:
    if mode != "unlocked":
        return
    trainer.CFG.REGION_KD_ENABLE = False
    trainer.CFG.REGION_KD_WEIGHT = 0.0
    trainer.CFG.IDENTITY_GUARD_ENABLE = False
    trainer.CFG.IDENTITY_GUARD_KD_WEIGHT = 0.0
    trainer.CFG.IDENTITY_GUARD_POSITION_WEIGHT = 0.0
    trainer.CFG.TRAINABLE_NAME_PATTERNS = (
        "e1",
        "e2",
        "e3",
        "mid",
        "d1",
        "d2",
        "d3",
        "p1",
        "p2",
        "p3",
        "u1",
        "u2",
        "u3",
        "out",
        "boundary_adapter",
    )
    trainer.CFG.MOTION_LOSS_WEIGHT = max(float(getattr(trainer.CFG, "MOTION_LOSS_WEIGHT", 0.0)), 0.75)
    trainer.CFG.MOTION_GRAD_WEIGHT = max(float(getattr(trainer.CFG, "MOTION_GRAD_WEIGHT", 0.0)), 0.50)
    trainer.CFG.MOTION_RECON_WEIGHT = max(float(getattr(trainer.CFG, "MOTION_RECON_WEIGHT", 0.0)), 0.025)


def to_device_batch(batch, device: str):
    src, lbl, role, geom = trainer._unpack_batch(batch)
    src = src.to(device, non_blocking=True)
    lbl = lbl.to(device, non_blocking=True)
    if geom is not None:
        geom = {key: value.to(device, non_blocking=True) for key, value in geom.items()}
    return src, lbl, geom


def one_supervised_loss(model, batch, device: str) -> torch.Tensor:
    src, lbl, geom = to_device_batch(batch, device)
    pred = model(src).float().clamp(0.0, 1.0)
    lbl01 = lbl.float().clamp(0.0, 1.0)
    mask_valid = trainer.make_valid_mask(pred)
    rec = F.smooth_l1_loss(pred, lbl01)
    grad = trainer.gradient_magnitude_loss(pred, lbl01, mask_valid)
    edge = trainer.edge_orientation_loss(pred, lbl01, mask_valid)
    boundary, _parts = trainer.boundary_geometry_loss(pred, lbl01, geom)
    return rec + 0.52 * grad + 0.15 * edge + boundary


def one_motion_loss(model, motion_batch, device: str) -> torch.Tensor:
    src_a = motion_batch["src_a"].to(device, non_blocking=True)
    src_b = motion_batch["src_b"].to(device, non_blocking=True)
    lbl_a = motion_batch["lbl_a"].to(device, non_blocking=True).float().clamp(0.0, 1.0)
    lbl_b = motion_batch["lbl_b"].to(device, non_blocking=True).float().clamp(0.0, 1.0)
    dx = motion_batch["dx"].to(device, non_blocking=True)
    dy = motion_batch["dy"].to(device, non_blocking=True)
    geom_b = motion_batch.get("geom_b")
    if geom_b is not None:
        geom_b = {key: value.to(device, non_blocking=True) for key, value in geom_b.items()}
    pred_a = model(src_a).float().clamp(0.0, 1.0)
    pred_b = model(src_b).float().clamp(0.0, 1.0)
    mask = trainer.motion_boundary_mask(geom_b, boundary_weight=float(getattr(trainer.CFG, "MOTION_BOUNDARY_WEIGHT", 1.0)))
    motion = trainer.generic_motion_consistency_loss(
        pred_a,
        pred_b,
        dx,
        dy,
        mask=mask,
        gradient_weight=float(getattr(trainer.CFG, "MOTION_GRAD_WEIGHT", 0.0)),
    )
    recon = 0.5 * (F.smooth_l1_loss(pred_a, lbl_a) + F.smooth_l1_loss(pred_b, lbl_b))
    return float(getattr(trainer.CFG, "MOTION_LOSS_WEIGHT", 0.0)) * motion + float(
        getattr(trainer.CFG, "MOTION_RECON_WEIGHT", 0.0)
    ) * recon


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    configure(args.candidate, args.device, args.lr)
    apply_probe_mode(args.mode)

    trainer._apply_repro_runtime_flags()
    model = trainer._build_model_from_cfg()
    optimizer = trainer._build_optimizer(model)
    trainer._resume_training_state(model, optimizer, ema_model=None)
    model.train()
    trainer.apply_trainable_name_filter(model, getattr(trainer.CFG, "TRAINABLE_NAME_PATTERNS", ()))

    train_loader, _val_loader = trainer.make_train_val_loaders()
    motion_loader = trainer.make_motion_loader()
    if motion_loader is None:
        raise RuntimeError("motion loader is required for this probe")

    before = tensor_state(model)
    optimizer.zero_grad(set_to_none=True)
    train_iter = iter(train_loader)
    motion_iter = iter(motion_loader)
    loss_values = []
    for step in range(max(1, int(args.steps))):
        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)
        try:
            motion_batch = next(motion_iter)
        except StopIteration:
            motion_iter = iter(motion_loader)
            motion_batch = next(motion_iter)
        loss = one_supervised_loss(model, batch, args.device) + one_motion_loss(model, motion_batch, args.device)
        loss.backward()
        loss_values.append(float(loss.detach().cpu().item()))

    grad_rows = summarize_gradients(model)
    torch.nn.utils.clip_grad_norm_(model.parameters(), float(getattr(trainer.CFG, "GRAD_CLIP_NORM", 1.0)))
    optimizer.step()
    after = tensor_state(model)
    delta_rows = summarize_parameter_delta(before, after)

    write_csv(args.out_dir / f"gradient_summary_{args.mode}.csv", grad_rows)
    write_csv(args.out_dir / f"update_summary_{args.mode}.csv", delta_rows)
    report = {
        "candidate": args.candidate,
        "mode": args.mode,
        "steps": int(args.steps),
        "loss_values": loss_values,
        "gradient_summary_csv": str(args.out_dir / f"gradient_summary_{args.mode}.csv"),
        "update_summary_csv": str(args.out_dir / f"update_summary_{args.mode}.csv"),
        "top_gradients": grad_rows[:10],
        "top_updates": delta_rows[:10],
    }
    (args.out_dir / f"probe_report_{args.mode}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
