from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "R99_scratch_seed990053_20260814_105831"
WEIGHTS = ROOT / "weights" / "formal" / "seed_990053" / RUN_ID / "weights"
OUTPUT = ROOT / "reports" / "deep_dive" / "synthetic_stage_counterfactual.json"
EPOCHS = (24, 32, 40)
STAGES = ("raw", "radiometry", "geometry", "edge", "output")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    trainer = load_module("r99_trainer_counterfactual", ROOT / "training" / "train_r99.py")
    model_module = load_module("r99_model_counterfactual", ROOT / "model" / "r99_model.py")
    package = Path(trainer.DESIGN["dataset"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = trainer.R99SceneDataset(package, manifest, "validation", 256, 128, 0, all_observations=True)
    sampler = trainer.HomogeneousViewBatchSampler(dataset, batch_size=4)
    loader = trainer.make_loader(dataset, sampler, 0, device.type == "cuda")
    all_results: dict[str, object] = {}

    for epoch in EPOCHS:
        checkpoint = torch.load(WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        model = model_module.build_model().to(device).eval()
        model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
        sums: defaultdict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
        counts: defaultdict[str, int] = defaultdict(int)
        role_sums: defaultdict[str, defaultdict[str, defaultdict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        role_counts: defaultdict[str, int] = defaultdict(int)
        halo = 64
        core = slice(halo, halo + 128)

        with torch.inference_mode():
            for batch in loader:
                scenes, views = int(batch["source"].shape[0]), int(batch["source"].shape[1])
                source = batch["source"].to(device)
                target = batch["target"].to(device)[..., core, core].reshape(-1, 1, 128, 128)
                mask = batch["mask"].to(device)[..., core, core].reshape(-1, 1, 128, 128)
                flat = source.reshape(-1, 1, 256, 256)
                details = model(flat, return_details=True)
                raw = flat[..., core, core].float()
                low_delta = details["low_delta"][..., core, core].float()
                transport_delta = details["transport_delta"][..., core, core].float()
                edge_delta = details["edge_delta"][..., core, core].float()
                stage_values = {
                    "raw": raw,
                    "radiometry": (raw + low_delta).clamp(0.0, 1.0),
                }
                stage_values["geometry"] = (stage_values["radiometry"] + transport_delta).clamp(0.0, 1.0)
                stage_values["edge"] = (stage_values["geometry"] + edge_delta).clamp(0.0, 1.0)
                stage_values["output"] = details["output"][..., core, core].float()
                boundary_level = batch["boundary_level"].to(device).repeat_interleave(views)
                polarity = batch["polarity"].to(device).repeat_interleave(views)
                target_boundary = trainer.soft_boundary(mask)
                target_high = target - trainer.lowpass(target, 9)
                identities = batch["identity"].reshape(-1).to(device)
                roles = [role for role in batch["role"] for _ in range(views)]

                for stage_name, value in stage_values.items():
                    probability = trainer.foreground_probability(value, boundary_level, polarity)
                    boundary_error = torch.abs(trainer.soft_boundary(probability) - target_boundary).mean(dim=(1, 2, 3))
                    pixel_error = torch.abs(value - target).mean(dim=(1, 2, 3))
                    texture_error = torch.abs((value - trainer.lowpass(value, 9)) - target_high).mean(dim=(1, 2, 3))
                    identity_change = torch.abs(value - raw).mean(dim=(1, 2, 3))
                    for item in range(value.shape[0]):
                        row = {
                            "pixel_error_gray": float(pixel_error[item].cpu() * 255.0),
                            "boundary_error": float(boundary_error[item].cpu()),
                            "texture_error_gray": float(texture_error[item].cpu() * 255.0),
                            "identity_change_gray": float(identity_change[item].cpu() * 255.0) if bool(identities[item]) else 0.0,
                        }
                        for metric, number in row.items():
                            sums[stage_name][metric] += number
                            role_sums[roles[item]][stage_name][metric] += number
                counts["views"] += scenes * views
                counts["identity_views"] += int(identities.sum().item())
                for role in roles:
                    role_counts[role] += 1

        summary: dict[str, object] = {"view_count": counts["views"], "identity_view_count": counts["identity_views"], "stages": {}}
        for stage_name in STAGES:
            summary["stages"][stage_name] = {
                metric: value / counts["views"]
                for metric, value in sums[stage_name].items()
                if metric != "identity_change_gray"
            }
            summary["stages"][stage_name]["identity_change_gray"] = sums[stage_name]["identity_change_gray"] / max(counts["identity_views"], 1)
        summary["roles"] = {}
        for role, count in role_counts.items():
            summary["roles"][role] = {
                stage_name: {
                    metric: value / (max(counts["identity_views"], 1) if metric == "identity_change_gray" else count)
                    for metric, value in role_sums[role][stage_name].items()
                }
                for stage_name in STAGES
            }
        all_results[str(epoch)] = summary
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    OUTPUT.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    compact = {}
    for epoch, summary in all_results.items():
        raw_boundary = summary["stages"]["raw"]["boundary_error"]
        compact[epoch] = {
            stage: {
                "boundary_ratio_to_raw": summary["stages"][stage]["boundary_error"] / raw_boundary,
                "pixel_error_gray": summary["stages"][stage]["pixel_error_gray"],
                "texture_error_gray": summary["stages"][stage]["texture_error_gray"],
                "identity_change_gray": summary["stages"][stage]["identity_change_gray"],
            }
            for stage in STAGES
        }
    print(json.dumps({"output": str(OUTPUT), "summary": compact}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
