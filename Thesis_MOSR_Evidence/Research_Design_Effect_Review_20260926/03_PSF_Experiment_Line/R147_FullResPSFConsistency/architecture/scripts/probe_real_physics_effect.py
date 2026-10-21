"""Post-training native-PSF switch on twelve fixed real frames."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.measurement_interface import measure_image
from model import Model
from utils import load, model_config, now, save, setup, sha
from verify_package import verify_source_lock
from evaluation_lock import verify as verify_evaluation_lock

FRAMES = (0, 30, 100, 130, 300, 330, 500, 530, 700, 730, 899, 929)


def main() -> None:
    verify_source_lock()
    verify_evaluation_lock()
    path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    complete = load(ROOT / "runs/formal_8192/training_complete.json")
    assert complete["updates"] == 8192 and sha(path) == complete["checkpoint"]["sha256"]
    cfg = model_config()
    setup(1309001)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cp = torch.load(path, map_location="cpu", weights_only=False)
    model = Model(cfg, ROOT).to(device).eval()
    model.load_state_dict(cp["model"], strict=True)
    plan = load(ROOT / "evaluation/capture_plan.json")
    measure_cfg = load(ROOT / "evaluation/measurement_config.json")
    tracking = pd.read_csv(ROOT / "evaluation/tracking.csv")
    rows = []
    for number in FRAMES:
        frame = plan["frames"][number]
        image = cv2.imread(frame["source"]["path"], cv2.IMREAD_GRAYSCALE)
        assert image is not None and image.shape == (1544, 2064)
        x = torch.from_numpy(image.astype(np.float32)[None, None]/255).to(device)
        seeds = tracking[(tracking.run == frame["run"]) & (tracking["index"] == frame["index"])]
        seeds = seeds.sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
        with torch.inference_mode():
            on = model(x)
            model.optical_enabled = False
            off = model(x)
            model.optical_enabled = True
        on_image = on.cpu().numpy()[0, 0].astype(np.float64)
        off_image = off.cpu().numpy()[0, 0].astype(np.float64)
        on_circles, _ = measure_image(on_image, seeds, measure_cfg)
        off_circles, _ = measure_image(off_image, seeds, measure_cfg)
        on_values = np.asarray([[r["center_x_px"], r["center_y_px"], r["radius_px"]] for r in on_circles])
        off_values = np.asarray([[r["center_x_px"], r["center_y_px"], r["radius_px"]] for r in off_circles])
        center_nm = np.linalg.norm(on_values[:, :2]-off_values[:, :2], axis=1)*172.5
        diameter_nm = (on_values[:, 2]-off_values[:, 2])*345
        rows.append(dict(frame_no=number, run=frame["run"], index=frame["index"],
                         image_RMS_difference_gray=float(np.sqrt(np.mean((on_image-off_image)**2))*255),
                         mean_center_difference_nm=float(center_nm.mean()),
                         max_center_difference_nm=float(center_nm.max()),
                         mean_diameter_difference_nm=float(diameter_nm.mean()),
                         max_absolute_diameter_difference_nm=float(np.abs(diameter_nm).max())))
        print("PHYSICS_PROBE", number, rows[-1]["image_RMS_difference_gray"], flush=True)
    result = dict(model=cfg["model_name"], psf_mode=cfg["psf_mode"],
                  checkpoint_sha256=sha(path), bank_sha256=cp["bank_sha256"],
                  physical_step_strengths=(cfg["optical_step_max"]*torch.sigmoid(model.optical_step_logits)).detach().cpu().tolist(),
                  median_image_RMS_difference_gray=float(np.median([r["image_RMS_difference_gray"] for r in rows])),
                  max_center_difference_nm=max(r["max_center_difference_nm"] for r in rows),
                  max_diameter_difference_nm=max(r["max_absolute_diameter_difference_nm"] for r in rows),
                  note="Frozen-model switch only; not a retrained ablation",
                  frames=rows, completed_utc=now())
    save(ROOT / "results/real_physics_effect_12.json", result)
    print("REAL_PHYSICS_EFFECT_COMPLETE", result["median_image_RMS_difference_gray"], flush=True)


if __name__ == "__main__":
    main()
