"""Train the R45 family-routed residual adapter."""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from r45_adapter_data import DEFAULT_DATA_ROOT, R45MotionPairDataset  # noqa: E402
from r45_adapter_model import (  # noqa: E402
    FamilyAdapterConfig,
    FamilyAdapterWrapper,
    load_frozen_base_model,
    save_adapter_checkpoint,
)


EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter"
DEFAULT_BASE_CHECKPOINT = (
    REPO_ROOT
    / "Traing_Progress"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r42_best_20260506_201801"
    / "weights"
    / "best_tradeoff.pth.tar"
)
DEFAULT_OUTPUT = EXPERIMENT_ROOT / "results" / "checkpoints" / "r45_oracle_adapter_large_mixed.pth"


def resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def to_device(batch: dict, device: torch.device) -> dict:
    out = {}
    for key, value in batch.items():
        if torch.is_tensor(value):
            out[key] = value.to(device, non_blocking=True)
        else:
            out[key] = value
    return out


def masked_l1(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    mask = mask.to(device=pred.device, dtype=pred.dtype)
    denom = mask.sum().clamp_min(1.0)
    return (torch.abs(pred - target) * mask).sum() / denom


def band_weight(boundary: torch.Tensor, centerline: torch.Tensor, distance: torch.Tensor, *, sigma: float = 3.0) -> torch.Tensor:
    distance_weight = torch.exp(-distance.clamp_min(0.0) / float(sigma))
    return torch.maximum(torch.maximum(boundary.float() * 1.25, centerline.float()), distance_weight).clamp(0.0, 1.5)


def sobel_mag(x: torch.Tensor) -> torch.Tensor:
    kx = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]], device=x.device, dtype=x.dtype)
    ky = kx.t()
    kx = kx.view(1, 1, 3, 3)
    ky = ky.view(1, 1, 3, 3)
    gx = F.conv2d(x, kx, padding=1)
    gy = F.conv2d(x, ky, padding=1)
    return torch.sqrt(gx * gx + gy * gy + 1e-8)


def warp_tensor_by_dxdy(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    b, _c, h, w = x.shape
    dx = dx.to(device=x.device, dtype=x.dtype).view(-1)
    dy = dy.to(device=x.device, dtype=x.dtype).view(-1)
    yy, xx = torch.meshgrid(
        torch.arange(h, device=x.device, dtype=x.dtype),
        torch.arange(w, device=x.device, dtype=x.dtype),
        indexing="ij",
    )
    xx = xx.unsqueeze(0).expand(b, -1, -1) - dx.view(b, 1, 1)
    yy = yy.unsqueeze(0).expand(b, -1, -1) - dy.view(b, 1, 1)
    x_norm = (2.0 * (xx + 0.5) / float(w)) - 1.0
    y_norm = (2.0 * (yy + 0.5) / float(h)) - 1.0
    grid = torch.stack((x_norm, y_norm), dim=-1)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="zeros", align_corners=False)


def motion_loss(pred_a: torch.Tensor, pred_b: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    warped = warp_tensor_by_dxdy(pred_a, dx, dy)
    return masked_l1(warped, pred_b, mask)


def train_one_epoch(wrapper: FamilyAdapterWrapper, loader: DataLoader, optimizer, device: torch.device, weights: dict) -> dict:
    wrapper.train()
    wrapper.base_model.eval()
    sums = {"loss": 0.0, "recon": 0.0, "boundary": 0.0, "edge": 0.0, "motion": 0.0, "residual": 0.0}
    count = 0
    for batch in loader:
        batch = to_device(batch, device)
        families = list(batch["family"])
        src = torch.cat([batch["src_a"], batch["src_b"]], dim=0)
        lbl = torch.cat([batch["lbl_a"], batch["lbl_b"]], dim=0)
        family_twice = families + families
        base = wrapper.base_predict(src)
        pred = wrapper.adapt_with_families(src, base, family_twice)
        pred_a, pred_b = torch.chunk(pred, 2, dim=0)

        w_a = band_weight(batch["boundary_a"], batch["centerline_a"], batch["distance_a"])
        w_b = band_weight(batch["boundary_b"], batch["centerline_b"], batch["distance_b"])
        w_all = torch.cat([w_a, w_b], dim=0)
        motion_mask = torch.maximum(batch["boundary_b"], batch["centerline_b"]).float().clamp(0.0, 1.0)

        l_recon = F.smooth_l1_loss(pred, lbl)
        l_boundary = masked_l1(pred, lbl, w_all)
        l_edge = masked_l1(sobel_mag(pred), sobel_mag(lbl), w_all)
        l_motion = motion_loss(pred_a, pred_b, batch["dx"], batch["dy"], motion_mask)
        l_residual = F.smooth_l1_loss(pred, base)
        loss = (
            float(weights["recon"]) * l_recon
            + float(weights["boundary"]) * l_boundary
            + float(weights["edge"]) * l_edge
            + float(weights["motion"]) * l_motion
            + float(weights["residual"]) * l_residual
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(wrapper.adapters.parameters(), 1.0)
        optimizer.step()

        bs = int(batch["src_a"].shape[0])
        for key, value in (
            ("loss", loss),
            ("recon", l_recon),
            ("boundary", l_boundary),
            ("edge", l_edge),
            ("motion", l_motion),
            ("residual", l_residual),
        ):
            sums[key] += float(value.detach().cpu()) * bs
        count += bs
    return {key: value / max(1, count) for key, value in sums.items()}


def write_history_csv(history: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({k for row in history for k in row}))
        writer.writeheader()
        writer.writerows(history)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train R45 family-routed residual adapter.")
    parser.add_argument("--profile", default="r44_motion_research_train")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--base-checkpoint", type=Path, default=DEFAULT_BASE_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--max-pairs-per-stage", type=int, default=0)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=4500)
    parser.add_argument("--hidden-channels", type=int, default=16)
    parser.add_argument("--num-blocks", type=int, default=3)
    parser.add_argument("--residual-scale", type=float, default=0.18)
    args = parser.parse_args(argv)

    if not args.base_checkpoint.exists():
        raise FileNotFoundError(f"base checkpoint not found: {args.base_checkpoint}")
    seed_everything(args.seed)
    device = resolve_device(args.device)
    profile_dir = args.data_root / args.profile
    max_pairs = None if int(args.max_pairs_per_stage) <= 0 else int(args.max_pairs_per_stage)
    dataset = R45MotionPairDataset(
        profile_dir,
        crop_size=args.crop_size,
        random_crop=True,
        max_pairs_per_stage=max_pairs,
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, num_workers=0, pin_memory=(device.type == "cuda"))

    cfg = FamilyAdapterConfig(
        target_families=("large_regions", "mixed_fields"),
        hidden_channels=int(args.hidden_channels),
        num_blocks=int(args.num_blocks),
        residual_scale=float(args.residual_scale),
    )
    base_model = load_frozen_base_model(args.base_checkpoint, device)
    wrapper = FamilyAdapterWrapper(base_model, cfg).to(device)
    optimizer = torch.optim.AdamW(wrapper.adapters.parameters(), lr=float(args.lr), weight_decay=1e-4)
    weights = {"recon": 1.0, "boundary": 0.65, "edge": 0.20, "motion": 0.15, "residual": 0.03}

    print(
        json.dumps(
            {
                "profile": args.profile,
                "pairs": len(dataset),
                "device": str(device),
                "base_checkpoint": str(args.base_checkpoint),
                "output": str(args.output),
                "config": cfg.to_json_dict(),
                "loss_weights": weights,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    history: list[dict] = []
    best = float("inf")
    for epoch in range(1, int(args.epochs) + 1):
        row = {"epoch": epoch, **train_one_epoch(wrapper, loader, optimizer, device, weights)}
        history.append(row)
        print("[R45][train] " + " ".join(f"{k}={v:.6f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()))
        if float(row["loss"]) < best:
            best = float(row["loss"])
            save_adapter_checkpoint(args.output, wrapper=wrapper, base_checkpoint=args.base_checkpoint, history=history)
    save_adapter_checkpoint(args.output.with_name(args.output.stem + "_latest" + args.output.suffix), wrapper=wrapper, base_checkpoint=args.base_checkpoint, history=history)
    write_history_csv(history, args.output.with_suffix(".history.csv"))
    print(f"[R45] best adapter checkpoint: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
