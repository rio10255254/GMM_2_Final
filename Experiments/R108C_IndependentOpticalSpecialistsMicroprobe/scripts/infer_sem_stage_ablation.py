"""Save tiled SEM outputs after each R108C no-radiometry stage."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack")
OUTPUT = ROOT / "results" / "sem_stage_ablation_g0p25"
INFER_PATH = ROOT / "scripts" / "infer_no_radiometry_folder.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


infer = load_module("r108c_sem_stage_infer", INFER_PATH)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.round(np.clip(value, 0.0, 1.0) * 255.0).astype(np.uint8))
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(str(path))


@torch.inference_mode()
def tiled_stages(models, selectors, image: np.ndarray, core: int = 512, halo: int = 192):
    tensor = torch.from_numpy(image[None, None]).to(infer.DEVICE)
    height, width = image.shape
    padded = F.pad(tensor, (halo, halo, halo, halo), mode="reflect")
    outputs = {name: torch.zeros_like(tensor) for name in infer.nr.ORDER}
    for y in range(0, height, core):
        for x in range(0, width, core):
            crop_h = min(core, height - y)
            crop_w = min(core, width - x)
            tile = padded[..., y:y + crop_h + 2 * halo, x:x + crop_w + 2 * halo]
            for name in infer.nr.ORDER:
                proposal = infer.nr.cal.adopt.expert_proposal(name, models[name], tile)
                tile = (tile + selectors[name](tile, proposal) * (proposal - tile)).clamp(0.0, 1.0)
                outputs[name][..., y:y + crop_h, x:x + crop_w] = tile[..., halo:halo + crop_h, halo:halo + crop_w]
    return {name: value[0, 0].cpu().numpy() for name, value in outputs.items()}


def main() -> int:
    files = sorted(SOURCE.glob("*.bmp"))
    if [path.stem for path in files] != [str(value) for value in range(13, 25)]:
        raise RuntimeError("SEM exposure inventory differs from 13..24")
    models, selectors = infer.nr.load(0.25)
    manifest = []
    for index, path in enumerate(files, 1):
        raw = infer.read(path)
        stages = tiled_stages(models, selectors, raw)
        for name, value in stages.items():
            destination = OUTPUT / name / path.name
            write_gray(destination, value)
            manifest.append(
                {
                    "exposure": int(path.stem),
                    "stage": name,
                    "source": str(path),
                    "source_sha256": sha256(path),
                    "output": str(destination),
                    "output_sha256": sha256(destination),
                }
            )
        print(json.dumps({"done": index, "total": len(files), "exposure": path.stem}), flush=True)
    import csv

    manifest_path = OUTPUT / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0].keys()))
        writer.writeheader()
        writer.writerows(manifest)
    (OUTPUT / "state.json").write_text(
        json.dumps(
            {"status": "complete", "guard": 0.25, "radiometry": False, "tiled": True, "exposures": 12, "stages": list(infer.nr.ORDER)},
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
