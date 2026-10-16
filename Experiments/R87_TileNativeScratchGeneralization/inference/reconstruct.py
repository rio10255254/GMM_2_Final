"""Clean manual R87 reconstruction entry point.

Edit INPUT_DIR and OUTPUT_DIR, then press Run.  Large images are reconstructed
with the same 896 input / 512 kept-core rule used during training.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


# MANUAL SETTINGS
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
CHECKPOINT = None  # None selects the latest completed run's best validation weight.
DEVICE = "cuda:0"


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
CONFIG = json.loads((EXPERIMENT_DIR / "config" / "experiment.json").read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def default_checkpoint() -> Path:
    summaries = sorted((EXPERIMENT_DIR / "runs").glob("training_progress_*/run_summary.json"), key=lambda path: path.stat().st_mtime)
    for path in reversed(summaries):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") == "complete" and int(payload.get("completed_epoch", 0)) == 100:
            return Path(payload["weights_dir"]) / "best_validation.pth.tar"
    raise FileNotFoundError("No completed R87 run")


def main() -> int:
    input_dir = INPUT_DIR if INPUT_DIR.is_absolute() else EXPERIMENT_DIR / INPUT_DIR
    output_dir = OUTPUT_DIR if OUTPUT_DIR.is_absolute() else EXPERIMENT_DIR / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    if input_dir.resolve() == output_dir.resolve() or input_dir.resolve() in output_dir.resolve().parents:
        raise ValueError("Output directory must be separate from input directory")
    checkpoint = Path(CHECKPOINT) if CHECKPOINT is not None else default_checkpoint()
    device = torch.device(DEVICE)
    model_module = load_module("r87_inference_model", EXPERIMENT_DIR / "model" / "r87_model.py")
    trainer = load_module("r87_inference_runtime", EXPERIMENT_DIR / "training" / "train_r87.py")
    model = model_module.build_model(base=int(CONFIG["architecture"]["base_channels"])).to(device)
    payload = torch.load(checkpoint, map_location=device)
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    model.eval()

    records = []
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}:
            continue
        raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if raw is None:
            continue
        if raw.ndim == 3:
            raw = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        maximum = 65535.0 if raw.dtype == np.uint16 else 255.0
        normalized = raw.astype(np.float32) / maximum
        reconstruction = trainer.tiled_predict(model, normalized, device, patch=896, core=512, amp_enabled=False)
        output = np.rint(np.clip(reconstruction, 0.0, 1.0) * maximum).astype(raw.dtype)
        destination = output_dir / path.name
        if destination.resolve() == path.resolve():
            raise ValueError(f"Refusing to overwrite source: {path}")
        if not cv2.imwrite(str(destination), output):
            raise IOError(f"Could not write {destination}")
        records.append({"input": str(path), "output": str(destination), "shape": list(raw.shape), "dtype": str(raw.dtype)})
    manifest = {"checkpoint": str(checkpoint), "checkpoint_epoch": int(payload["epoch"]), "images": records}
    (output_dir / "inference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

