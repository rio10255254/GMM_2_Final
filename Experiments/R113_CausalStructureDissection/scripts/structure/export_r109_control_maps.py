"""Persist representative R109 control maps for visual and numerical audit."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch

from r109_interventions import render_variants


ROOT = Path(__file__).resolve().parents[2]
STRUCTURE = ROOT / "results" / "structure"
OUT = STRUCTURE / "control_maps"
MODEL_ROOT = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch")
CHECKPOINT = MODEL_ROOT / "weights" / "selected" / "R109.pth"
EXPECTED_SHA = "77ff8611e764e1350d60592f5d8a25d6786db17897eadce189185cdc4dbc87fc"
CASES = ("junhua_pitch100", "sem_paired_optical", "real_50x")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value


def write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(str(path))


def colorize(value: np.ndarray, low: float, high: float, label: str) -> np.ndarray:
    scaled = np.clip((value - low) / max(high - low, 1e-12), 0, 1)
    image = cv2.applyColorMap(np.round(scaled * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    image = cv2.resize(image, (512, 512), interpolation=cv2.INTER_AREA)
    cv2.rectangle(image, (0, 0), (512, 42), (0, 0, 0), -1)
    cv2.putText(image, f"{label} [{low:g}, {high:g}]", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    return image


def main() -> int:
    if sha256_file(CHECKPOINT) != EXPECTED_SHA:
        raise RuntimeError("Checkpoint hash mismatch")
    sys.path.insert(0, str(MODEL_ROOT / "model"))
    import r109_model

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = r109_model.build_model().to(device)
    model.load_state_dict(payload["model"], strict=True)
    model.eval()
    ranges = {"support": (0.0, 1.0), "source_support": (0.0, 1.0), "learned_support": (0.0, 1.0), "width": (1.0, 3.5), "shift": (-1.5, 1.5)}
    records = []
    for case in CASES:
        input_path = STRUCTURE / "inputs" / f"{case}_raw.png"
        image = read_gray(input_path)
        tensor = torch.from_numpy(image.astype(np.float32)[None, None] / 255).to(device)
        _outputs, maps_by_variant, audit = render_variants(model, tensor, ("full",))
        maps = maps_by_variant["full"]
        arrays = {name: maps[name][0, 0].float().cpu().numpy() for name in ranges}
        npz_path = OUT / case / "control_maps.npz"
        npz_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(npz_path, **arrays)
        panels = []
        for name, (low, high) in ranges.items():
            value = arrays[name]
            panels.append(colorize(value, low, high, name))
            records.append(
                {
                    "case": case,
                    "map": name,
                    "minimum": float(value.min()),
                    "maximum": float(value.max()),
                    "mean": float(value.mean()),
                    "std": float(value.std()),
                    "p05": float(np.percentile(value, 5)),
                    "p95": float(np.percentile(value, 95)),
                    "full_reproduction_max_abs": audit["full_reproduction_max_abs"],
                    "npz": str(npz_path),
                }
            )
        panels.append(np.zeros_like(panels[0]))
        montage = np.vstack((np.hstack(panels[:3]), np.hstack(panels[3:6])))
        write_png(OUT / case / "control_map_montage.png", montage)
    import pandas as pd

    table = pd.DataFrame(records)
    table.to_csv(OUT / "control_map_statistics.csv", index=False, encoding="utf-8-sig")
    result = {
        "status": "pass" if len(records) == len(CASES) * len(ranges) and table["full_reproduction_max_abs"].max() == 0 else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "cases": list(CASES),
        "maps": list(ranges),
        "records": len(records),
        "all_full_reproductions_exact": bool(table["full_reproduction_max_abs"].max() == 0),
    }
    (OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
