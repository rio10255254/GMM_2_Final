"""Reconstruct and measure the frozen 30-scan, 930-frame real evaluation."""
from __future__ import annotations

import concurrent.futures
import json
import sys
import time
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


MODEL_NAME = "R143-PSF25-MatchedPairs"


def final_checkpoint() -> tuple[Path, dict]:
    verify_source_lock()
    verify_evaluation_lock()
    complete = load(ROOT / "runs/formal_8192/training_complete.json")
    assert complete["updates"] == 8192
    receipt = complete["checkpoint"]
    path = Path(receipt["path"])
    assert receipt["step"] == 8192 and sha(path) == receipt["sha256"]
    return path, receipt


def baseline_reader_parity() -> None:
    config = load(ROOT / "evaluation/measurement_config.json")
    plan = load(ROOT / "evaluation/capture_plan.json")
    tracking = pd.read_csv(ROOT / "evaluation/tracking.csv")
    checks = []
    for frame_number in (0, 30, 899, 929):
        f = plan["frames"][frame_number]
        seeds = tracking[(tracking.run == f["run"]) & (tracking["index"] == f["index"])].sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
        raw = cv2.imread(f["source"]["path"], cv2.IMREAD_GRAYSCALE).astype(np.float64) / 255
        _, measured = measure_image(raw, seeds, config)
        with np.load(ROOT / "evaluation/baseline_centers/Raw" / (f["run"] + ".npz"), allow_pickle=False) as z:
            expected = z["points"][f["index"]]
        error = float(np.abs(measured["points"] - expected).max())
        assert error < 1e-7, (frame_number, error)
        checks.append(dict(frame=frame_number, max_point_error_px=error))
    save(ROOT / "results/baseline_reader_parity.json", checks)


def reconstruct_all() -> None:
    path, cp_receipt = final_checkpoint()
    plan = load(ROOT / "evaluation/capture_plan.json")
    assert len(plan["frames"]) == 930
    setup(1309001)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cp = torch.load(path, map_location="cpu", weights_only=False)
    cfg = model_config()
    assert cp["model_config"] == cfg and cp["checkpoint_kind"] == "trained_model"
    model = Model(cfg, ROOT).to(device).eval()
    model.load_state_dict(cp["model"], strict=True)
    results = []
    begin = time.perf_counter()
    for frame_number, f in enumerate(plan["frames"]):
        directory = ROOT / "results/reconstruction" / f["run"]
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{f['index'] + 1:02d}"
        out = directory / (stem + ".npz")
        receipt_path = directory / (stem + ".json")
        if receipt_path.exists():
            old = load(receipt_path)
            if old["checkpoint_sha256"] != cp_receipt["sha256"] or sha(out) != old["output_sha256"]:
                raise RuntimeError("Existing real output has wrong model or hash: " + str(out))
            results.append(old)
            continue
        if out.exists():
            raise RuntimeError("Output lacks its receipt: " + str(out))
        started = time.perf_counter()
        if sha(f["source"]["path"]) != f["source"]["sha256"]:
            raise RuntimeError("Capture source changed: " + f["source"]["path"])
        raw = cv2.imread(f["source"]["path"], cv2.IMREAD_UNCHANGED)
        if raw is None or raw.dtype != np.uint8 or raw.shape != (1544, 2064):
            raise ValueError("Unexpected capture format")
        x = torch.from_numpy(raw.astype(np.float32)[None, None] / 255).to(device)
        if device == "cuda":
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        forward_started = time.perf_counter()
        with torch.inference_mode():
            output = model(x)
        if device == "cuda":
            torch.cuda.synchronize()
        seconds = time.perf_counter() - forward_started
        peak = torch.cuda.max_memory_allocated() if device == "cuda" else None
        image = output.cpu().numpy()[0, 0]
        if not np.isfinite(image).all():
            raise FloatingPointError("Nonfinite output: " + str(out))
        with out.open("xb") as handle:
            np.savez_compressed(handle, output=image)
        if frame_number in (0, 465, 929):
            preview = np.rint(image * 65535).clip(0, 65535).astype(np.uint16)
            if not cv2.imwrite(str(directory / (stem + ".png")), preview):
                raise OSError("Preview save failed")
        optics = model.refiner.optics
        indices = optics.last_indices[0].cpu().tolist()
        weights = optics.last_sparse_weights[0][optics.last_indices[0]].cpu().tolist()
        record = dict(model=MODEL_NAME, run=f["run"], index=f["index"],
                      source=f["source"], output_path=str(out), output_sha256=sha(out),
                      checkpoint_sha256=cp_receipt["sha256"], bank_sha256=cp["bank_sha256"],
                      PSF_indices=indices, PSF_weights=weights, PSF_effective_beta=optics.last_beta,
                      shape=list(image.shape), forward_seconds=seconds,
                      end_to_end_seconds=time.perf_counter() - started,
                      peak_gpu_allocated_bytes=peak, device=device, completed_utc=now())
        save(receipt_path, record)
        results.append(record)
        if frame_number % 10 == 0 or frame_number == 929:
            save(ROOT / "results/reconstruction_status.json",
                 dict(state="running", completed=frame_number + 1, total=930,
                      elapsed_seconds=time.perf_counter() - begin, updated_utc=now()))
            print("RECON", frame_number + 1, "/ 930", flush=True)
    assert len(results) == 930
    pd.DataFrame(results).to_csv(ROOT / "results/reconstruction_runtime.csv", index=False)
    save(ROOT / "results/reconstruction_complete.json",
         dict(images=930, checkpoint_sha256=cp_receipt["sha256"], completed_utc=now()))


def measure_run(run: str) -> dict:
    cv2.setNumThreads(1)
    plan = load(ROOT / "evaluation/capture_plan.json")
    cfg = load(ROOT / "evaluation/measurement_config.json")
    tracking = pd.read_csv(ROOT / "evaluation/tracking.csv")
    tracking = tracking[tracking.run == run]
    frames = [f for f in plan["frames"] if f["run"] == run]
    rows, points, coarse, times = [], [], [], []
    for f in frames:
        path = ROOT / "results/reconstruction" / run / f"{f['index'] + 1:02d}.npz"
        with np.load(path, allow_pickle=False) as z:
            image = z["output"].astype(np.float64)
        seeds = tracking[tracking["index"] == f["index"]].sort_values("pillar_id")[["seed_x_px", "seed_y_px"]].to_numpy()
        assert seeds.shape == (9, 2)
        started = time.perf_counter()
        values, detail = measure_image(image, seeds, cfg)
        times.append(time.perf_counter() - started)
        rows.extend(dict(model=MODEL_NAME, run=run, run_index=f["run_index"], index=f["index"], **row) for row in values)
        points.append(detail["points"])
        coarse.append(detail["coarse"])
    dest = ROOT / "results/centers"
    dest.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(dest / (run + ".csv"), index=False)
    np.savez_compressed(dest / (run + ".npz"), points=np.stack(points), coarse=np.stack(coarse))
    result = dict(run=run, images=31, circles=279, ACM_measurement_seconds=times, completed_utc=now())
    save(dest / (run + ".json"), result)
    return result


def main() -> None:
    final_checkpoint()
    if not (ROOT / "results/baseline_reader_parity.json").is_file():
        baseline_reader_parity()
    if not (ROOT / "results/reconstruction_complete.json").is_file():
        reconstruct_all()
    plan = load(ROOT / "evaluation/capture_plan.json")
    dest = ROOT / "results/centers"
    dest.mkdir(exist_ok=True)
    pending = [r["run"] for r in plan["runs"] if not (dest / (r["run"] + ".json")).is_file()]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(measure_run, pending):
            print("MEASURED", result["run"], flush=True)
    if len(list(dest.glob("*_XY_0.csv"))) != 30:
        raise RuntimeError("Incomplete 30-scan center table")
    save(ROOT / "results/measurement_complete.json",
         dict(scans=30, images=930, circles=8370,
              backend="same frozen ACM and LSC as R140v2", completed_utc=now()))


if __name__ == "__main__":
    main()
