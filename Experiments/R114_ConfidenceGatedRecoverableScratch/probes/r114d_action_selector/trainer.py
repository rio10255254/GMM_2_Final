"""Explicit launcher for the short R114D selector probe.

Importing this file never starts training.  The sealed E24 proposal is loaded
strictly and remains frozen.  Only selector parameters enter the optimizer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader


PROBE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PROBE_ROOT.parents[1]

from training.dataset import R114Dataset  # noqa: E402
from .losses import LossConfig, selector_loss
from .model import (
    R114DActionSelector,
    SelectorConfig,
    load_frozen_e24_proposal,
    parameter_counts,
)
from .targets import TargetConfig, build_selector_targets


def _tensor_hash(module: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _collate(batch: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in batch[0]:
        values = [row[key] for row in batch]
        result[key] = torch.stack(values) if isinstance(values[0], torch.Tensor) else values
    return result


def run_probe(args: argparse.Namespace) -> Path:
    config_payload = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    train_config = config_payload["probe_training"]
    seed = int(train_config["seed"])
    _seed_everything(seed)
    device = torch.device(args.device)
    proposal, proposal_metadata = load_frozen_e24_proposal(device=device)
    model = R114DActionSelector(proposal, SelectorConfig.from_json()).to(device).train()
    counts = parameter_counts(model)
    if counts["proposal_trainable"] != 0:
        raise RuntimeError("sealed proposal unexpectedly has trainable parameters")
    proposal_hash_before = _tensor_hash(model.proposal)
    optimizer = torch.optim.AdamW(
        model.selector_parameters(),
        lr=float(train_config["learning_rate"]),
        weight_decay=float(train_config["weight_decay"]),
    )
    optimizer_ids = {id(parameter) for group in optimizer.param_groups for parameter in group["params"]}
    selector_ids = {id(parameter) for parameter in model.selector.parameters()}
    proposal_ids = {id(parameter) for parameter in model.proposal.parameters()}
    if optimizer_ids != selector_ids or optimizer_ids & proposal_ids:
        raise RuntimeError("optimizer parameter isolation contract failed")

    run_root = PROBE_ROOT / "runs" / args.run_id
    if run_root.exists():
        raise FileExistsError(run_root)
    (run_root / "weights").mkdir(parents=True)
    dataset = R114Dataset("train", limit=int(args.limit))
    loader = DataLoader(
        dataset,
        batch_size=int(args.batch_size),
        shuffle=True,
        num_workers=int(args.workers),
        collate_fn=_collate,
        pin_memory=device.type == "cuda",
        drop_last=True,
    )
    epochs = int(args.epochs)
    target_config = TargetConfig.from_json()
    loss_config = LossConfig.from_json()
    rows: list[dict[str, float | int]] = []
    for epoch in range(1, epochs + 1):
        dataset.set_epoch(epoch)
        for step, batch in enumerate(loader, start=1):
            source = batch["source"].to(device, non_blocking=True)
            target = batch["target"].to(device, non_blocking=True)
            sdf = batch["sdf"].to(device, non_blocking=True)
            identity = batch["identity"].to(device, non_blocking=True)
            prediction = model.forward_details(source)
            labels = build_selector_targets(prediction, target, sdf, identity, target_config)
            losses = selector_loss(prediction, labels, loss_config)
            optimizer.zero_grad(set_to_none=True)
            losses.total.backward()
            torch.nn.utils.clip_grad_norm_(model.selector_parameters(), 1.0)
            optimizer.step()
            rows.append(
                {
                    "epoch": epoch,
                    "step": step,
                    "loss": float(losses.total.detach()),
                    "positive_count": int(losses.positive_count.detach()),
                    "negative_count": int(losses.negative_count.detach()),
                    "acceptance_mean": float(prediction.acceptance.detach().mean()),
                    "amount_mean": float(prediction.amount.detach().mean()),
                }
            )
            if args.max_steps > 0 and len(rows) >= args.max_steps:
                break
        torch.save(
            {
                "selector": model.selector.state_dict(),
                "epoch": epoch,
                "run_id": args.run_id,
                "proposal": proposal_metadata,
                "proposal_state_sha256": proposal_hash_before,
                "optimizer_contains_proposal": False,
            },
            run_root / "weights" / f"epoch_{epoch:03d}.pth",
        )
        if args.max_steps > 0 and len(rows) >= args.max_steps:
            break
    proposal_hash_after = _tensor_hash(model.proposal)
    if proposal_hash_after != proposal_hash_before:
        raise RuntimeError("sealed E24 proposal changed during selector training")
    with (run_root / "training_log.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    state = {
        "status": "complete",
        "research_probe_only": True,
        "run_id": args.run_id,
        "device": str(device),
        "steps": len(rows),
        "epochs_requested": epochs,
        "proposal": proposal_metadata,
        "proposal_state_sha256_before": proposal_hash_before,
        "proposal_state_sha256_after": proposal_hash_after,
        "proposal_unchanged": proposal_hash_before == proposal_hash_after,
        "parameter_counts": counts,
    }
    (run_root / "run_state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )
    return run_root


def parse_args() -> argparse.Namespace:
    payload = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    defaults = payload["probe_training"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--epochs", type=int, default=int(defaults["epochs"]))
    parser.add_argument("--batch-size", type=int, default=int(defaults["batch_size"]))
    parser.add_argument("--workers", type=int, default=int(defaults["workers"]))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=0)
    return parser.parse_args()


if __name__ == "__main__":
    print(run_probe(parse_args()))
