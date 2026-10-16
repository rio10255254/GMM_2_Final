"""Measure one real forward/backward update at every formal R98 patch stage."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\Rio\anaconda3\python.exe")


def child(patch: int, core: int) -> dict:
    import torch
    spec = importlib.util.spec_from_file_location("trainer_bench", ROOT / "training" / "train_r98_core.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["trainer_bench"] = module
    spec.loader.exec_module(module)
    device = torch.device("cuda:0")
    seed = int(module.DESIGN["independence"]["seed"])
    module.seed_all(seed)
    package = Path(module.DESIGN["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = module.DATA.R98SceneDataset(package, manifest, "train", patch, core, 17, master_seed=seed)
    raw = next(iter(torch.utils.data.DataLoader(dataset, batch_size=1, num_workers=0)))
    batch, scenes, views = module.flatten_batch(raw, device)
    model = module.MODEL.build_model(int(module.DESIGN["architecture"]["model_width"])).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)
    free_before = torch.cuda.mem_get_info(device)[0]
    reserved_before = torch.cuda.memory_reserved(device)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        calibration, calibration_patch, calibration_core = module.calibration_crop(batch, scenes, views, patch, 17, 1)
        geometry = module.geometry_loss(model, batch, patch, core)
        triplet, _ = module.direct_triplet_loss(model, calibration, calibration_patch, calibration_core, 0.4)
        calibration_loss = 0.30 * geometry + 1.10 * triplet
    calibration_loss.backward()
    optimizer.step(); optimizer.zero_grad(set_to_none=True)
    calibration_peak = torch.cuda.max_memory_allocated(device) / 2**30
    del calibration_loss, geometry, triplet, calibration
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(device)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        details = model(batch["source"], return_details=True, stage_truth=module.stage_truth(batch, "s"), stage_truth_fraction=0.4)
        branches, _ = module.branch_loss(details, batch, patch, core, "s")
        output, _ = module.output_loss(details, batch, patch, core)
        total = branches + 0.85 * output
    total.backward(); optimizer.step()
    composition_peak = torch.cuda.max_memory_allocated(device) / 2**30
    incremental_reserved = max(0, torch.cuda.max_memory_reserved(device) - reserved_before)
    return {
        "patch": patch, "core": core,
        "calibration_peak_allocated_gib": calibration_peak,
        "composition_peak_allocated_gib": composition_peak,
        "estimated_peak_free_gib": max(0.0, (free_before - incremental_reserved) / 2**30),
        "finite": bool(torch.isfinite(total).all()),
    }


def main() -> int:
    if "--child" in sys.argv:
        index = sys.argv.index("--child")
        print(json.dumps(child(int(sys.argv[index + 1]), int(sys.argv[index + 2]))))
        return 0
    results = []
    for patch, core in ((512, 256), (768, 384), (896, 512)):
        process = subprocess.run(
            [str(PYTHON), str(Path(__file__)), "--child", str(patch), str(core)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if process.returncode:
            print(process.stdout)
            print(process.stderr, file=sys.stderr)
            return process.returncode
        results.append(json.loads(process.stdout.strip().splitlines()[-1]))
    report = {"passed": all(row["finite"] and row["estimated_peak_free_gib"] > 1.0 for row in results), "stages": results}
    path = ROOT / "reports" / "patch_stage_benchmark.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
