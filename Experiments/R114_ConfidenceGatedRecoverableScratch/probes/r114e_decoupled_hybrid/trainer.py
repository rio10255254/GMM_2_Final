"""Explicit short-probe trainer; only R114E selector parameters can change."""

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

from training.dataset import R114Dataset

from .losses import load_loss_config, selector_loss
from .model import PROBE_ROOT, build_hybrid, parameter_counts, source_state_hashes
from .targets import build_selector_targets, load_target_config


REQUIRED_HEADROOM_RECORD_SHA256 = "49ec3621656c6f85679618e0e67fa7959cf10185615c397ed11b2b4c76d4b538"


def _seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _require_headroom() -> dict[str, Any]:
    path = PROBE_ROOT / "results" / "fixed128_headroom" / "headroom.json"
    if not path.is_file():
        raise RuntimeError("fixed-128 R114E headroom gate has not been run")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("training_authorized") is not True:
        raise RuntimeError("fixed-128 R114E headroom gate did not authorize training")
    if payload.get("record_id_sha256") != REQUIRED_HEADROOM_RECORD_SHA256:
        raise RuntimeError("headroom gate used a different validation record set")
    if not all(payload.get("checks", {}).values()):
        raise RuntimeError("headroom evidence contains a failed check")
    return payload


def run_probe(args: argparse.Namespace) -> Path:
    headroom = _require_headroom()
    config = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    training = config["short_probe_training"]
    _seed(int(training["seed"]))
    device = torch.device(args.device)
    model = build_hybrid(device).train()
    counts = parameter_counts(model)
    if counts["e20_trainable"] or counts["e24_trainable"]:
        raise RuntimeError("one or both sealed source models are trainable")
    frozen_before = source_state_hashes(model)
    optimizer = torch.optim.AdamW(
        model.selector_parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    optimizer_ids = {id(p) for group in optimizer.param_groups for p in group["params"]}
    selector_ids = {id(p) for p in model.selector.parameters()}
    frozen_ids = {
        id(p)
        for source in (model.geometry_model, model.profile_model)
        for p in source.parameters()
    }
    if optimizer_ids != selector_ids or optimizer_ids & frozen_ids:
        raise RuntimeError("optimizer isolation contract failed")

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
        pin_memory=device.type == "cuda",
        drop_last=True,
    )
    target_config = load_target_config()
    loss_config = load_loss_config()
    rows: list[dict[str, Any]] = []
    for epoch in range(1, int(args.epochs) + 1):
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
            rows.append({
                "epoch": epoch,
                "step": step,
                "loss": float(losses.total.detach()),
                "positive_count": int(losses.positive_count.detach()),
                "negative_count": int(losses.negative_count.detach()),
                "acceptance_mean": float(prediction.acceptance.detach().mean()),
                "amount_mean": float(prediction.amount.detach().mean()),
            })
            if args.max_steps > 0 and len(rows) >= args.max_steps:
                break
        frozen_now = source_state_hashes(model)
        if frozen_now != frozen_before:
            raise RuntimeError("a sealed source changed during selector training")
        torch.save(
            {
                "selector": model.selector.state_dict(),
                "epoch": epoch,
                "run_id": args.run_id,
                "source_provenance": model.provenance,
                "source_state_sha256": frozen_before,
                "optimizer_contains_sources": False,
                "headroom_record_id_sha256": headroom["record_id_sha256"],
                "headroom_status": headroom["status"],
            },
            run_root / "weights" / f"epoch_{epoch:03d}.pth",
        )
        if args.max_steps > 0 and len(rows) >= args.max_steps:
            break
    with (run_root / "training_log.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    state = {
        "status": "complete",
        "research_short_probe_only": True,
        "long_or_formal_training": False,
        "run_id": args.run_id,
        "device": str(device),
        "steps": len(rows),
        "epochs_requested": int(args.epochs),
        "source_provenance": model.provenance,
        "source_state_sha256_before": frozen_before,
        "source_state_sha256_after": source_state_hashes(model),
        "sources_unchanged": source_state_hashes(model) == frozen_before,
        "optimizer_contains_sources": False,
        "parameter_counts": counts,
        "headroom_evidence": str((PROBE_ROOT / "results" / "fixed128_headroom" / "headroom.json").resolve()),
    }
    (run_root / "run_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return run_root


def parse_args() -> argparse.Namespace:
    payload = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    defaults = payload["short_probe_training"]
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

