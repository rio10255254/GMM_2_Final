"""Export 12 SEM-paired optical exposures for exact downstream ACM testing."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch

from r109_interventions import render_variants
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "structure_probe" / "sem_interventions"
INPUT = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))
MODEL_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch'))
CHECKPOINT = MODEL_ROOT / "weights" / "selected" / "R109.pth"
EXPECTED_SHA = "77ff8611e764e1350d60592f5d8a25d6786db17897eadce189185cdc4dbc87fc"
VARIANTS = ("full", "no_shift", "no_width", "learned_support_only", "smoothed_controls")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"Cannot read {path}")
    return value


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Cannot encode {path}")
    encoded.tofile(str(path))


def main() -> int:
    if sha256_file(CHECKPOINT) != EXPECTED_SHA:
        raise RuntimeError("R109 checkpoint hash mismatch")
    names = [f"{index}.bmp" for index in range(13, 25)]
    if not all((INPUT / name).is_file() for name in names):
        raise RuntimeError("The frozen 12-image SEM-paired optical stack is incomplete")
    sys.path.insert(0, str(MODEL_ROOT / "model"))
    import r109_model

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = r109_model.build_model().to(device)
    model.load_state_dict(payload["model"], strict=True)
    model.eval()
    rows = []
    reproduction = []
    for index, name in enumerate(names, start=1):
        source_path = INPUT / name
        image = read_gray(source_path)
        tensor = torch.from_numpy(image.astype(np.float32)[None, None] / 255).to(device)
        outputs, _maps, audit = render_variants(model, tensor, VARIANTS)
        reproduction.append(audit["full_reproduction_max_abs"])
        for variant, value in outputs.items():
            output = np.round(value[0, 0].float().cpu().numpy().clip(0, 1) * 255).astype(np.uint8)
            destination = OUT / variant / name
            write_bmp(destination, output)
            rows.append(
                {
                    "exposure": int(Path(name).stem),
                    "variant": variant,
                    "source": str(source_path),
                    "source_sha256": sha256_file(source_path),
                    "output": str(destination),
                    "output_sha256": sha256_file(destination),
                    "height": image.shape[0],
                    "width": image.shape[1],
                    "mean_abs_change_gray": float(np.mean(np.abs(output.astype(np.float32) - image.astype(np.float32)))),
                }
            )
        print(json.dumps({"done": index, "total": len(names), "exposure": name}), flush=True)
    import pandas as pd

    table = pd.DataFrame(rows)
    table.to_csv(OUT / "output_manifest.csv", index=False, encoding="utf-8-sig")
    validation = {
        "status": "pass" if len(rows) == 60 and max(reproduction) <= 1e-7 else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": sha256_file(CHECKPOINT),
        "source_stack": str(INPUT),
        "exposures": list(range(13, 25)),
        "variants": list(VARIANTS),
        "variant_names_matlab_field_safe": all(name.replace("_", "a").isalnum() and not name[0].isdigit() for name in VARIANTS),
        "output_count": len(rows),
        "full_reproduction_max_abs": max(reproduction),
        "all_output_hashes_verified": all(sha256_file(Path(row["output"])) == row["output_sha256"] for row in rows),
    }
    (OUT / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0 if validation["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
