"""Central-36 SEM-paired ACM contour validation for R103 E48."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
import torch


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "inference"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from r103_model import build_model  # noqa: E402
from reconstruct import reconstruct_tensor  # noqa: E402


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "posttraining_validation" / "sem_contour"
RECON = OUTPUT / "reconstructions"
TABLES = OUTPUT / "results" / "tables"
RAW_DIR = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack")
R61_TABLES = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\tables")
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\scripts\run_acm_extraction.m")
EXPOSURES = tuple(range(13, 25))
METRICS = {
    "iou": "higher",
    "dice": "higher",
    "mean_boundary_distance_pitch_pct": "lower",
    "hd95_pitch_pct": "lower",
    "area_error_pct": "lower",
    "perimeter_error_pct": "lower",
    "circularity_abs_error": "lower",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(path)


def load_model(device: torch.device) -> tuple[torch.nn.Module, Path, dict]:
    checkpoint = Path(RUN["weights_dir"]) / "epoch_048.pth.tar"
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]),
        contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]),
        combined_bound=float(bounds["combined"]),
    )
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).eval(), checkpoint, payload


def assert_same_raw(reference: pd.DataFrame, candidate: pd.DataFrame, sensitivity: bool = False) -> None:
    keys = ["preset", "exposure", "pillar_id"] if sensitivity else ["exposure", "pillar_id"]
    columns = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    a = reference.loc[reference["method"] == "Raw"].sort_values(keys).reset_index(drop=True)
    b = candidate.loc[candidate["method"] == "Raw"].sort_values(keys).reset_index(drop=True)
    if len(a) != len(b) or not np.allclose(a[columns], b[columns], rtol=0, atol=1e-12):
        raise RuntimeError("Raw ACM extraction failed exact reproduction")


def bootstrap_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = values[rng.integers(0, len(values), size=(12000, len(values)))]
    return tuple(float(value) for value in np.quantile(np.median(samples, axis=1), [.025, .975]))


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite SEM validation: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, checkpoint, payload = load_model(device)
    if int(payload["epoch"]) != 48:
        raise RuntimeError("SEM checkpoint is not E48")
    records: list[dict[str, object]] = []
    for exposure in EXPOSURES:
        source = RAW_DIR / f"{exposure}.bmp"
        raw = read_gray(source)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        started = time.perf_counter()
        with torch.inference_mode(), torch.autocast(
            device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"
        ):
            prediction = reconstruct_tensor(model, tensor, core_size=512, halo=128, tile_batch=4)[0, 0].float()
        destination = RECON / source.name
        write_gray(destination, np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8))
        records.append({
            "exposure": exposure, "source": str(source), "source_sha256": sha256(source),
            "output": str(destination), "output_sha256": sha256(destination),
            "seconds": time.perf_counter() - started,
            "low_clip_fraction": float((prediction <= 0).float().mean()),
            "high_clip_fraction": float((prediction >= 1).float().mean()),
        })
        print(f"[sem] reconstructed exposure {exposure}", flush=True)
    pd.DataFrame(records).to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    expression = (
        f"addpath('{SHARED_ACM.parent.as_posix()}'); "
        f"run_acm_extraction('{OUTPUT.as_posix()}','{RAW_DIR.as_posix()}',"
        f"'{RECON.as_posix()}','R103E48');"
    )
    subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
    current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    if len(current) != 864 or set(current["method"]) != {"Raw", "R103E48"} or current.isna().any().any():
        raise RuntimeError("Primary R103 SEM ACM output is incomplete")
    if len(sensitivity) != 648 or set(sensitivity["method"]) != {"Raw", "R103E48"} or sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity R103 SEM ACM output is incomplete")
    r61 = pd.read_csv(R61_TABLES / "primary_contour_metrics.csv")
    r61_sensitivity = pd.read_csv(R61_TABLES / "acm_sensitivity_metrics.csv")
    assert_same_raw(current, r61)
    assert_same_raw(sensitivity, r61_sensitivity, sensitivity=True)
    combined = pd.concat([
        current.loc[current["method"].isin(["Raw", "R103E48"])],
        r61.loc[r61["method"] == "R61v16"],
    ], ignore_index=True)
    if len(combined) != 12 * 36 * 3:
        raise RuntimeError("Combined SEM comparison is incomplete")
    combined.to_csv(TABLES / "raw_r61_r103_primary_metrics.csv", index=False)
    per_pillar = combined.groupby(["pillar_id", "method"], sort=False)[list(METRICS)].median().unstack("method")
    summary_rows: list[dict[str, object]] = []
    for method in ("Raw", "R61v16", "R103E48"):
        summary_rows.append({"method": method, **{
            f"median_{metric}": float(np.median(per_pillar[(metric, method)].to_numpy(float)))
            for metric in METRICS
        }})
    comparisons: list[dict[str, object]] = []
    for source in ("Raw", "R61v16"):
        for metric, direction in METRICS.items():
            baseline = per_pillar[(metric, source)].to_numpy(float)
            target = per_pillar[(metric, "R103E48")].to_numpy(float)
            improvement = target - baseline if direction == "higher" else baseline - target
            low, high = bootstrap_ci(improvement, 1034800 + len(comparisons))
            try:
                _statistic, p_value = wilcoxon(target, baseline, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p_value = 1.0
            comparisons.append({
                "source": source, "target": "R103E48", "metric": metric, "direction": direction,
                "source_median": float(np.median(baseline)), "target_median": float(np.median(target)),
                "median_improvement": float(np.median(improvement)),
                "improved_pillars": int(np.sum(improvement > 0)),
                "improved_fraction": float(np.mean(improvement > 0)),
                "ci95_low": low, "ci95_high": high, "wilcoxon_p": float(p_value),
            })
    pd.DataFrame(summary_rows).to_csv(TABLES / "per_pillar_summary.csv", index=False)
    pd.DataFrame(comparisons).to_csv(TABLES / "paired_comparisons.csv", index=False)
    exposure = combined.groupby(["exposure", "method"], sort=False)[list(METRICS)].median().reset_index()
    exposure.to_csv(TABLES / "per_exposure_summary.csv", index=False)
    sensitivity.groupby(["preset", "method"], sort=False)[
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    ].median().reset_index().to_csv(TABLES / "sensitivity_summary.csv", index=False)
    paired = pd.DataFrame(comparisons)
    by_key = {(row["source"], row["metric"]): row for row in comparisons}
    normal = exposure.loc[exposure["exposure"].between(13, 22)]
    dark = exposure.loc[exposure["exposure"].between(23, 24)]
    result = {
        "status": "complete", "checkpoint": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_epoch": 48, "formal_run_id": RUN["run_id"],
        "physical_pillars": 36, "exposures": 12, "primary_rows": int(len(current)),
        "raw_reproduced_exactly": True, "method_summary": summary_rows,
        "r103_vs_raw": {metric: by_key[("Raw", metric)] for metric in METRICS},
        "r103_vs_r61": {metric: by_key[("R61v16", metric)] for metric in METRICS},
        "normal_exposure_rows": int(len(normal)), "dark_exposure_rows": int(len(dark)),
        "claim_boundary": "SEM validates paired central-36 shape only; optical intensity and fine texture have no SEM brightness truth.",
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps({
        "status": result["status"], "physical_pillars": 36, "exposures": 12,
        "r103_vs_raw_iou": result["r103_vs_raw"]["iou"],
        "r103_vs_r61_iou": result["r103_vs_r61"]["iou"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
