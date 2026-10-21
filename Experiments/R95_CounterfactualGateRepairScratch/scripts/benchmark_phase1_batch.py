"""Time the exact R95 phase-one formal batch on real data."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import time

import torch


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    model_module = load("r95_phase1_model", ROOT / "model" / "r95_model.py")
    data_module = load("r95_phase1_data", ROOT / "training" / "r95_dataset.py")
    trainer = load("r95_phase1_trainer", ROOT / "training" / "train_r95.py")
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text())
    package = Path(design["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text())
    dataset = data_module.R95SceneDataset(package, manifest, "train", 512, 256, 1)
    started = time.perf_counter()
    items = [dataset[0], dataset[1]]
    loaded = time.perf_counter()
    batch = {}
    for name in items[0]:
        if torch.is_tensor(items[0][name]):
            value = torch.stack([item[name] for item in items])
            if value.ndim >= 3 and value.shape[:2] == (2, 2):
                value = value.reshape(4, *value.shape[2:])
            batch[name] = value.cuda()
    model = model_module.build_model(base=16).cuda().train()
    model.set_active_training_groups({"need_control", "evidence_control", "geometry"})
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.2e-4)
    model_ready = time.perf_counter()
    combined = torch.cat([batch["source"], batch["target"], batch["noise_free_source"]], dim=0)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        direct = model.forward_control_features(combined)
        count = batch["source"].shape[0]
        direct_s = {name: value[:count] for name, value in direct.items()}
        direct_t = {name: value[count:2 * count] for name, value in direct.items()}
        direct_b = {name: value[2 * count:] for name, value in direct.items()}
        total, _ = trainer.counterfactual_controls_loss(
            direct_s, direct_t, direct_b, batch, 512, 256,
        )
    forward = time.perf_counter()
    total.backward()
    backward = time.perf_counter()
    optimizer.step()
    torch.cuda.synchronize()
    stepped = time.perf_counter()
    print(json.dumps({
        "data_seconds": loaded-started, "model_seconds": model_ready-loaded,
        "forward_seconds": forward-model_ready, "backward_seconds": backward-forward,
        "step_seconds": stepped-backward, "loss": float(total.detach()),
        "peak_gib": torch.cuda.max_memory_allocated()/2**30,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

