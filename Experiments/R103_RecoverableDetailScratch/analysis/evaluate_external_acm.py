"""R73/R74 exact-truth ACM generalization for R103 E48."""
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
PROJECT_ROOT = Path(__file__).resolve().parents[3]


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "posttraining_validation" / "external_acm"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
ACM_SCRIPT = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts/run_acm_multimethod.m'))
R82_RESULTS = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/results/acm_external'))
SUITES = {
    "R73_novel_shapes": {
        "root": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val')),
        "config": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/config/experiment.json')),
        "initialization": "automatic_otsu",
    },
    "R74_hard_microscopy": {
        "root": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val')),
        "config": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/config/experiment.json')),
        "initialization": "smoothed_otsu",
    },
}
METRICS = {
    "iou": "higher", "dice": "higher", "mean_boundary_distance_px": "lower",
    "hd95_px": "lower", "area_error_pct": "lower", "perimeter_error_pct": "lower",
    "solidity_abs_error": "lower", "roughness_abs_error": "lower",
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
        low_bound=float(bounds["radiometry"]), contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]), combined_bound=float(bounds["combined"]),
    )
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).eval(), checkpoint, payload


def bootstrap_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = values[rng.integers(0, len(values), size=(12000, len(values)))]
    return tuple(float(value) for value in np.quantile(np.median(samples, axis=1), [.025, .975]))


def analyze_suite(name: str, arm: Path) -> dict:
    current = pd.read_csv(arm / "results" / "tables" / "primary_contour_metrics.csv")
    prior = pd.read_csv(R82_RESULTS / name / "results" / "tables" / "primary_contour_metrics.csv")
    raw_columns = ["image_id", "alignment", *METRICS]
    a = current.loc[current["method"] == "Raw", raw_columns].sort_values(["image_id", "alignment"]).reset_index(drop=True)
    b = prior.loc[prior["method"] == "Raw", raw_columns].sort_values(["image_id", "alignment"]).reset_index(drop=True)
    if len(a) != 200 or len(b) != 200 or not np.allclose(a[list(METRICS)], b[list(METRICS)], rtol=0, atol=1e-10):
        raise RuntimeError(f"{name}: Raw ACM did not reproduce")
    comparison = pd.concat([
        current.loc[current["method"].isin(["Raw", "R103E48"])],
        prior.loc[prior["method"] == "R61"],
    ], ignore_index=True)
    comparison.to_csv(arm / "results" / "tables" / "raw_r61_r103_metrics.csv", index=False)
    primary = comparison.loc[comparison["alignment"] == "fixed_pixel_coordinates"].copy()
    rows: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for method in ("Raw", "R61", "R103E48"):
        subset = primary.loc[primary["method"] == method]
        summaries.append({"method": method, **{f"median_{metric}": float(subset[metric].median()) for metric in METRICS}})
    for source in ("Raw", "R61"):
        base = primary.loc[primary["method"] == source].set_index("image_id").sort_index()
        target = primary.loc[primary["method"] == "R103E48"].set_index("image_id").sort_index()
        if not base.index.equals(target.index):
            raise RuntimeError(f"{name}: paired ACM keys differ")
        for metric, direction in METRICS.items():
            source_values = base[metric].to_numpy(float)
            target_values = target[metric].to_numpy(float)
            improvement = target_values - source_values if direction == "higher" else source_values - target_values
            low, high = bootstrap_ci(improvement, 1037300 + len(rows))
            try:
                _statistic, p_value = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p_value = 1.0
            rows.append({
                "source": source, "target": "R103E48", "metric": metric, "direction": direction,
                "source_median": float(np.median(source_values)), "target_median": float(np.median(target_values)),
                "median_improvement": float(np.median(improvement)),
                "improved_images": int(np.sum(improvement > 0)), "improved_fraction": float(np.mean(improvement > 0)),
                "ci95_low": low, "ci95_high": high, "wilcoxon_p": float(p_value),
            })
    pd.DataFrame(summaries).to_csv(arm / "results" / "tables" / "method_summary.csv", index=False)
    pd.DataFrame(rows).to_csv(arm / "results" / "tables" / "paired_comparisons.csv", index=False)
    family = primary.groupby(["family", "method"], sort=False)[list(METRICS)].median().reset_index()
    family.to_csv(arm / "results" / "tables" / "family_summary.csv", index=False)
    by_key = {(row["source"], row["metric"]): row for row in rows}
    return {
        "images": 100, "raw_reproduced": True, "method_summary": summaries,
        "r103_vs_raw": {metric: by_key[("Raw", metric)] for metric in METRICS},
        "r103_vs_r61": {metric: by_key[("R61", metric)] for metric in METRICS},
    }


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite external ACM validation: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, checkpoint, payload = load_model(device)
    if int(payload["epoch"]) != 48:
        raise RuntimeError("External ACM checkpoint is not E48")
    suite_results: dict[str, object] = {}
    total_started = time.perf_counter()
    for suite, item in SUITES.items():
        arm = OUTPUT / suite
        source_config = json.loads(Path(item["config"]).read_text(encoding="utf-8"))
        arm_config = {
            "experiment_id": f"R103_{suite}",
            "dataset": {**source_config["dataset"], "root": str(item["root"])},
            "acm": {
                **source_config["acm"],
                "initialization_mode": item["initialization"],
                "seed_radius_fraction": source_config["acm"].get("seed_radius_fraction", .2),
            },
        }
        write_json(arm / "config" / "experiment.json", arm_config)
        output_dirs: dict[str, dict[str, str]] = {"Raw": {}, "R103E48": {}}
        sources = sorted((Path(item["root"]) / "src").rglob("*.bmp"))
        if len(sources) != 100:
            raise RuntimeError(f"{suite}: expected 100 sources")
        records: list[dict[str, object]] = []
        for index, source in enumerate(sources):
            relative = source.relative_to(Path(item["root"]) / "src")
            raw = read_gray(source)
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            started = time.perf_counter()
            with torch.inference_mode(), torch.autocast(
                device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"
            ):
                prediction = reconstruct_tensor(model, tensor, core_size=512, halo=128, tile_batch=4)[0, 0].float()
            destination = arm / "reconstructions" / "R103E48" / relative
            write_gray(destination, np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8))
            records.append({
                "source": str(source), "source_sha256": sha256(source),
                "output": str(destination), "output_sha256": sha256(destination),
                "seconds": time.perf_counter() - started,
            })
            if (index + 1) % 20 == 0:
                print(f"[{suite}] reconstructed {index + 1}/100", flush=True)
        for family in source_config["dataset"]["families"]:
            stage, family_name = family["stage"], family["name"]
            output_dirs["Raw"][family_name] = str((Path(item["root"]) / "src" / stage).resolve())
            output_dirs["R103E48"][family_name] = str((arm / "reconstructions" / "R103E48" / stage).resolve())
        write_json(arm / "results" / "inference_manifest.json", {
            "suite": suite, "methods": ["Raw", "R103E48"], "output_dirs": output_dirs,
            "checkpoint": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
        })
        pd.DataFrame(records).to_csv(arm / "reconstruction_manifest.csv", index=False)
        expression = f"addpath('{ACM_SCRIPT.parent.as_posix()}'); run_acm_multimethod('{arm.as_posix()}')"
        subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
        suite_results[suite] = analyze_suite(suite, arm)
    result = {
        "status": "complete", "checkpoint": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_epoch": 48, "formal_run_id": RUN["run_id"],
        "total_images": 200, "suites": suite_results,
        "elapsed_seconds": time.perf_counter() - total_started,
        "claim_boundary": "These suites have exact synthetic shape truth but are developmental, not proof of all future microscope scenes.",
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps({"status": "complete", "total_images": 200}, indent=2), flush=True)


if __name__ == "__main__":
    main()
