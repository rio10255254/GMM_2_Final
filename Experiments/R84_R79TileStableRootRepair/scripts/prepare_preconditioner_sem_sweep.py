"""Prepare an all-36 SEM diagnostic for three shared-preconditioner strengths."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
OUTPUT = ROOT / "results" / "shared_global_preconditioner_probe" / "SEM_strength_sweep"
DEVICE = "cuda:0"
GAMMAS = {"G020": 0.20, "G050": 0.50, "G100": 1.00}


def load_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_sem_gamma_inference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def infer_gamma(module, model, image: np.ndarray, gamma: float, core: int = 512, halo: int = 192) -> np.ndarray:
    canvas, original_shape = module.canonical_canvas(image)
    tensor = torch.from_numpy(canvas.astype(np.float32) / 255.0)[None, None].to(DEVICE)
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        physics = model.physics_layer(tensor).float()
        conditioned = tensor + gamma * (physics - tensor)
    _, _, height, width = conditioned.shape
    output = torch.empty((height, width), dtype=torch.float32)
    for core_y in range(0, height, core):
        for core_x in range(0, width, core):
            y0 = max(0, core_y - halo)
            x0 = max(0, core_x - halo)
            y1 = min(height, core_y + core + halo)
            x1 = min(width, core_x + core + halo)
            with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
                prediction = model(conditioned[:, :, y0:y1, x0:x1]).float().clamp(0.0, 1.0)[0, 0].cpu()
            crop_y = core_y - y0
            crop_x = core_x - x0
            output[core_y:core_y + core, core_x:core_x + core] = prediction[
                crop_y:crop_y + core, crop_x:crop_x + core
            ]
    h, w = original_shape
    return np.clip(np.rint(output[:h, :w].numpy() * 255.0), 0, 255).astype(np.uint8)


def main() -> int:
    module = load_module()
    model = module.build_model(ROOT / "weights" / "selected" / "r84_tile_stable_model.pth.tar", DEVICE, tile_stable=True, use_ema=True)[0]
    config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    sem = dict(config["sem_acm"])
    sem["selected_pillar_ids"] = list(range(1, 37))
    raw_root = Path(sem["raw_input_dir"])
    for exposure in sem["optical_exposures"]:
        source = raw_root / f"{exposure}.bmp"
        raw = module.read_gray(source)
        for method, gamma in GAMMAS.items():
            module.write_bmp(
                OUTPUT / "results" / "reconstructions" / "sem_acm" / method / source.name,
                infer_gamma(module, model, raw, gamma),
            )
    for method in ("R79", "R84"):
        source_root = ROOT / "results" / "final_confirmation" / "SEM_reserved" / "results" / "reconstructions" / "sem_acm" / method
        target_root = OUTPUT / "results" / "reconstructions" / "sem_acm" / method
        target_root.mkdir(parents=True, exist_ok=True)
        for source in source_root.glob("*.bmp"):
            shutil.copy2(source, target_root / source.name)
    (OUTPUT / "config").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "config" / "experiment.json").write_text(json.dumps({
        "experiment_id": "R84_shared_preconditioner_SEM_strength_diagnostic",
        "models": {name: {} for name in ["R79", "R84", *GAMMAS]},
        "sem_acm": sem,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"prepared": True, "methods": ["R79", "R84", *GAMMAS]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
