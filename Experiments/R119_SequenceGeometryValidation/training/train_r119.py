"""Independent R119 trainer for matched probes and one later formal run."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, random, time
from pathlib import Path
import cv2, numpy as np, torch
from torch.utils.data import DataLoader
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from model.network import build_model
from training.r119_dataset import R119Scenes, FamilyOrder, flatten
from training.objectives import objective, location_xy, gradient, per_scene
from inference.run import tiled, read, write

CONFIG = json.loads((ROOT / "config/experiment.json").read_text(encoding="utf-8-sig"))
SELECTED = json.loads((ROOT / "config/selected_scene_ids.json").read_text(encoding="utf-8-sig"))
SHORT_IDS = set(int(x) for x in SELECTED["short_sequence_enrichment_ids"])


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp"); tmp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8"); tmp.replace(path)


def write_history(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f: csv.DictWriter(f, fieldnames=keys).writeheader(); csv.DictWriter(f, fieldnames=keys).writerows(rows)


def stage(epoch, epochs):
    if epochs == 42:
        return "geometry" if epoch <= 6 else "action" if epoch <= 24 else "detail"
    unit = max(1, epochs // 3)
    return "geometry" if epoch <= unit else "action" if epoch <= unit * 2 else "detail"


def worker_init(_): cv2.setNumThreads(1); torch.set_num_threads(1)


def loader(dataset, batch, workers, train, seed):
    kwargs = {"dataset": dataset, "batch_size": batch, "num_workers": workers, "pin_memory": True, "worker_init_fn": worker_init}
    if train: kwargs["sampler"] = FamilyOrder(dataset, seed)
    if workers: kwargs.update(persistent_workers=True, prefetch_factor=2)
    return DataLoader(**kwargs)


@torch.inference_mode()
def validate(model, device, candidate, data_seed, limit=96):
    dataset = R119Scenes("validation", 0, limit, candidate, data_seed); rows = []
    for raw in loader(dataset, 4, 0, False, 0):
        batch = flatten(raw, device); details = model.forward_details(batch["source"]); raw_xy, _ = location_xy(batch["source"], batch["target"]); out_xy, _ = location_xy(details.output, batch["target"]); rg = gradient(batch["source"] - batch["target"]); og = gradient(details.output - batch["target"])
        per = {"raw_mae_gray": per_scene((batch["source"] - batch["target"]).abs()) * 255, "output_mae_gray": per_scene((details.output - batch["target"]).abs()) * 255, "raw_gradient_error": per_scene(rg[0].abs() + rg[1].abs()), "output_gradient_error": per_scene(og[0].abs() + og[1].abs()), "raw_xy_error_px": raw_xy.norm(dim=1), "output_xy_error_px": out_xy.norm(dim=1), "output_change_gray": per_scene((details.output - batch["source"]).abs()) * 255}
        for i in range(batch["source"].shape[0]): rows.append({"role": raw["role"][i // 2], "family": raw["family"][i // 2], **{key: float(value[i]) for key, value in per.items()}})
    grouped = {"views": len(rows)}
    for key in rows[0]:
        if key in ("role", "family"): continue
        grouped[key] = float(np.mean([r[key] for r in rows]))
    return {"status": "complete", "candidate": candidate, "development_validation": True, "groups": {"all": grouped}, "rows": rows}


@torch.inference_mode()
def preview(model, device, run, epoch):
    panels = []
    for item in CONFIG["validation"]["real_raw_inputs"]:
        source = ROOT / item["path"]; raw = read(source); tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device); out = tiled(model, tensor)[0, 0].cpu().numpy(); image = np.rint(np.clip(out, 0, 1) * 255).astype(np.uint8); write(run / "previews" / f"e{epoch:03d}_{item['name']}.png", image); panels.append(np.concatenate([cv2.resize(raw, (224, 224)), cv2.resize(image, (224, 224))], axis=1))
    write(run / "previews" / f"epoch_{epoch:03d}_real.png", np.concatenate(panels, axis=0))


def train(args):
    if args.candidate not in {"A", "B", "D"}: raise ValueError("R119 probes are A, B or D; C awaits P04 support")
    device = torch.device("cuda" if args.device == "auto" and torch.cuda.is_available() else args.device if args.device != "auto" else "cpu"); torch.set_num_threads(4); cv2.setNumThreads(1)
    random.seed(args.model_seed); np.random.seed(args.model_seed); torch.manual_seed(args.model_seed)
    if device.type == "cuda": torch.cuda.manual_seed_all(args.model_seed); torch.backends.cudnn.benchmark = True
    epochs = int(args.epochs); limit = int(args.limit); batch = int(args.batch); workers = int(args.workers)
    formal_marker = ROOT / "runs/launcher_logs/active_formal_run.json"
    if args.mode == "formal" and formal_marker.exists():
        raise FileExistsError(f"formal marker already exists: {formal_marker}")
    run = ROOT / "runs" / args.run_id; run.mkdir(parents=True, exist_ok=False); lock = ROOT / "runs/active_run.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, args.run_id.encode()); os.close(fd)
    model = build_model().to(device); groups = model.groups(); weights = CONFIG["training"]["weights"]; t = CONFIG["training"]
    optimizer = torch.optim.AdamW([{"params": groups["geometry"], "lr": t["learning_rate"] * t["geometry_lr_multiplier"], "group": "geometry"}, {"params": groups["action"], "lr": t["learning_rate"], "group": "action"}, {"params": groups["detail"], "lr": t["learning_rate"] * t["detail_lr_multiplier"], "group": "detail"}], weight_decay=t["weight_decay"])
    state = {"status": "running", "run_id": args.run_id, "candidate": args.candidate, "scratch": True, "checkpoint_loaded": False, "model_seed": args.model_seed, "data_seed": args.data_seed, "sampler_seed": args.sampler_seed, "epochs": epochs, "limit": limit, "batch": batch, "workers": workers, "code_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [ROOT / "model/network.py", ROOT / "training/objectives.py", ROOT / "training/r119_dataset.py", ROOT / "training/train_r119.py"]}}
    atomic(run / "state.json", state); atomic(ROOT / "runs/active_run.json", {"run_id": args.run_id, "path": str(run), "status": "running"})
    if args.mode == "formal":
        atomic(formal_marker, {"schema_version": 1, "run_id": args.run_id, "path": str(run), "status": "running", "candidate": args.candidate, "created_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    history, step_total, started = [], 0, time.perf_counter()
    try:
        for epoch in range(1, epochs + 1):
            current = stage(epoch, epochs); active = {"geometry"} if current == "geometry" else {"geometry", "action"}; active.add("detail") if current == "detail" else None; model.detail_enabled = current == "detail"
            for group, parameters in groups.items():
                for parameter in parameters: parameter.requires_grad_(group in active)
            progress = (epoch - 1) / max(epochs - 1, 1); factor = .25 + .75 * .5 * (1 + math.cos(math.pi * progress))
            for group in optimizer.param_groups:
                multiplier = t["geometry_lr_multiplier"] if group["group"] == "geometry" else t["detail_lr_multiplier"] if group["group"] == "detail" else 1; group["lr"] = t["learning_rate"] * factor * multiplier
            dataset = R119Scenes("train", epoch, limit, args.candidate, args.data_seed, SHORT_IDS); dl = loader(dataset, batch, workers, True, args.sampler_seed + epoch); totals = {}; count = 0; epoch_start = time.perf_counter()
            if device.type == "cuda": torch.cuda.reset_peak_memory_stats()
            model.train()
            for index, raw in enumerate(dl, 1):
                batch_data = flatten(raw, device); optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                    details = model.forward_details(batch_data["source"]); loss, terms = objective(model, details, batch_data, weights, current == "geometry")
                if not torch.isfinite(loss): raise FloatingPointError("nonfinite loss")
                loss.backward(); norm = torch.nn.utils.clip_grad_norm_(model.parameters(), t["gradient_clip"])
                if not torch.isfinite(norm): raise FloatingPointError("nonfinite gradient")
                optimizer.step(); count += 1; step_total += 1; totals["total"] = totals.get("total", 0) + float(loss.detach())
                for key, value in terms.items(): totals[key] = totals.get(key, 0) + float(value.detach())
            evaluation = validate(model, device, args.candidate, args.data_seed, min(96, max(1, limit or 96))); elapsed = time.perf_counter() - epoch_start; row = {"epoch": epoch, "stage": current, "steps": count, "duration_seconds": elapsed, **{key: value / max(count, 1) for key, value in totals.items()}, **{f"val_{key}": value for key, value in evaluation["groups"]["all"].items()}}
            if device.type == "cuda": row["peak_reserved_gib"] = torch.cuda.max_memory_reserved() / 2**30
            history.append(row); write_history(run / "training_log.csv", history); atomic(run / "validation" / f"epoch_{epoch:03d}.json", evaluation)
            live = {"epoch": epoch, "epochs": epochs, "stage": current, "steps": count, "candidate": args.candidate, "last_epoch_seconds": elapsed, "estimated_epoch_remaining_seconds": 0, "estimated_total_remaining_seconds": float(np.median([r["duration_seconds"] for r in history[-3:]]) * max(epochs - epoch, 0)), "model_seed": args.model_seed}
            if device.type == "cuda": live["gpu_free_gib"] = torch.cuda.mem_get_info()[0] / 2**30
            atomic(run / "live.json", live); print(json.dumps({"epoch": epoch, "stage": current, "candidate": args.candidate, "loss": row["total"], "val_output_mae_gray": row["val_output_mae_gray"], "seconds": elapsed}, ensure_ascii=False), flush=True)
            if epoch in ({4, 8, 12} if args.mode == "probe" else set(range(3, epochs + 1, 3))) or epoch == epochs:
                preview(model, device, run, epoch); destination = run / "weights" / f"epoch_{epoch:03d}.pth"; destination.parent.mkdir(parents=True, exist_ok=True); torch.save({"model": model.state_dict(), "model_config": model.config, "scratch": True, "checkpoint_loaded": False, "epoch": epoch, "run_id": args.run_id, "candidate": args.candidate, "model_seed": args.model_seed, "data_seed": args.data_seed, "sampler_seed": args.sampler_seed, "validation": evaluation, "config_snapshot": CONFIG}, destination)
        state.update(status="complete", epochs_completed=epochs, steps=step_total, elapsed_seconds=time.perf_counter() - started); atomic(run / "SUMMARY.json", state)
    except BaseException as exc:
        state.update(status="failed", error=repr(exc), steps=step_total); atomic(run / "failure.json", state); raise
    finally:
        atomic(run / "state.json", state); atomic(ROOT / "runs/active_run.json", {"run_id": args.run_id, "path": str(run), "status": state["status"]})
        if args.mode == "formal" and formal_marker.exists():
            atomic(formal_marker, {"schema_version": 1, "run_id": args.run_id, "path": str(run), "status": state["status"], "epochs_completed": state.get("epochs_completed", 0), "updated_at_utc": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        if lock.exists() and lock.read_text() == args.run_id: lock.unlink()
    return 0


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--mode", choices=["probe", "formal"], default="probe"); parser.add_argument("--candidate", choices=["A", "B", "D"], required=True); parser.add_argument("--run-id", required=True); parser.add_argument("--model-seed", type=int, required=True); parser.add_argument("--data-seed", type=int, default=1196001); parser.add_argument("--sampler-seed", type=int, default=1197001); parser.add_argument("--epochs", type=int, default=12); parser.add_argument("--limit", type=int, default=512); parser.add_argument("--batch", type=int, default=8); parser.add_argument("--workers", type=int, default=2); parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()
    if args.mode == "formal": args.epochs, args.limit, args.model_seed = 42, 0, 1195001
    return train(args)


if __name__ == "__main__": raise SystemExit(main())
