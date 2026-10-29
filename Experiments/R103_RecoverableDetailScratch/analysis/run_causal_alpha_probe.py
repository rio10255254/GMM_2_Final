"""Targeted R103 diagnosis: branch behavior and residual-strength counterfactuals.

This probe never trains or changes R103.  It scales the already learned E48
residual to separate a bad correction-strength decision from a missing
correction direction, then reuses the locked ACM protocols.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr
import torch


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model",):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from r103_model import build_model  # noqa: E402
PROJECT_ROOT = Path(__file__).resolve().parents[3]


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RUN = json.loads((ROOT / "runs" / "active_run.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "causal_diagnostics" / "alpha_probe"
RAW_SEM = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))
SEM_DIR = Path(r"H:\From_2TB_D_disk\13_thesis\SEM_data")
SHARED = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts'))
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
ALPHAS = {"A025": 0.25, "A050": 0.50, "A075": 0.75, "A100": 1.00, "A125": 1.25}
SUITES = {
    "R73_novel_shapes": {
        "root": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val')),
        "config": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/config/experiment.json')),
        "prior": ROOT / "results" / "posttraining_validation" / "external_acm" / "R73_novel_shapes" / "results" / "tables" / "primary_contour_metrics.csv",
        "initialization": "automatic_otsu",
    },
    "R74_hard_microscopy": {
        "root": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val')),
        "config": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/config/experiment.json')),
        "prior": ROOT / "results" / "posttraining_validation" / "external_acm" / "R74_hard_microscopy" / "results" / "tables" / "primary_contour_metrics.csv",
        "initialization": "smoothed_otsu",
    },
}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Unable to read {path}")
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Unable to encode {path}")
    encoded.tofile(path)


def load_model(device: torch.device) -> torch.nn.Module:
    checkpoint = Path(RUN["weights_dir"]) / "epoch_048.pth.tar"
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if int(payload["epoch"]) != 48:
        raise RuntimeError("Causal probe requires E48")
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]), contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]), combined_bound=float(bounds["combined"]),
    )
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    return model.to(device).eval()


def edge_mask(image: np.ndarray) -> np.ndarray:
    f = image.astype(np.float32) / 255.0
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.sqrt(gx * gx + gy * gy)
    threshold = float(np.quantile(magnitude, 0.90))
    return magnitude >= max(threshold, 1e-5)


def detail_statistics(image: np.ndarray, details: object, label: dict[str, object]) -> dict[str, object]:
    raw = image.astype(np.float32) / 255.0
    edge = edge_mask(image)
    arrays = {
        "low": details.low_delta[0, 0].float().cpu().numpy(),
        "contour": details.contour_delta[0, 0].float().cpu().numpy(),
        "texture": details.texture_delta[0, 0].float().cpu().numpy(),
        "total": details.total_delta[0, 0].float().cpu().numpy(),
        "contour_confidence": details.contour_confidence[0, 0].float().cpu().numpy(),
        "texture_confidence": details.texture_confidence[0, 0].float().cpu().numpy(),
    }
    gx = cv2.Sobel(raw, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(raw, cv2.CV_32F, 0, 1, ksize=3)
    result: dict[str, object] = {
        **label,
        "raw_mean": float(raw.mean()), "raw_std": float(raw.std()),
        "raw_p01": float(np.quantile(raw, .01)), "raw_p99": float(np.quantile(raw, .99)),
        "raw_gradient_mean": float(np.sqrt(gx * gx + gy * gy).mean()),
    }
    for name in ("low", "contour", "texture", "total"):
        value = arrays[name]
        result[f"{name}_mean_abs"] = float(np.abs(value).mean())
        result[f"{name}_edge_mean_abs"] = float(np.abs(value[edge]).mean())
    for name in ("contour_confidence", "texture_confidence"):
        value = arrays[name]
        result[f"{name}_mean"] = float(value.mean())
        result[f"{name}_edge_mean"] = float(value[edge].mean())
        result[f"{name}_p10"] = float(np.quantile(value, .10))
        result[f"{name}_p90"] = float(np.quantile(value, .90))
    result["contour_effective_scale_mean"] = .75 + .50 * result["contour_confidence_mean"]
    result["texture_effective_scale_mean"] = .75 + .50 * result["texture_confidence_mean"]
    return result


def infer(model: torch.nn.Module, image: np.ndarray, device: torch.device):
    tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
    with torch.inference_mode(), torch.autocast(
        device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"
    ):
        return tensor, model.forward_details(tensor)


def alpha_image(tensor: torch.Tensor, total_delta: torch.Tensor, alpha: float) -> np.ndarray:
    result = (tensor + float(alpha) * total_delta).clamp(0.0, 1.0)[0, 0].float().cpu().numpy()
    return np.rint(result * 255.0).astype(np.uint8)


def auc(clean: np.ndarray, hard: np.ndarray) -> float:
    labels = np.r_[np.zeros(len(clean), dtype=int), np.ones(len(hard), dtype=int)]
    values = np.r_[clean, hard]
    ranks = rankdata(values)
    n0, n1 = len(clean), len(hard)
    rank_sum_hard = float(ranks[labels == 1].sum())
    return (rank_sum_hard - n1 * (n1 + 1) / 2.0) / (n0 * n1)


def run_sem(model: torch.nn.Module, device: torch.device) -> pd.DataFrame:
    arm = OUTPUT / "sem_alpha"
    models = {name: {"alpha": alpha} for name, alpha in ALPHAS.items()}
    write_json(arm / "config" / "experiment.json", {
        "experiment_id": "R103_E48_SEM_AlphaProbe",
        "models": models,
        "sem_acm": {
            "raw_input_dir": str(RAW_SEM), "sem_dir": str(SEM_DIR),
            "optical_exposures": list(range(13, 25)),
        },
    })
    rows: list[dict[str, object]] = []
    for exposure in range(13, 25):
        image = read_gray(RAW_SEM / f"{exposure}.bmp")
        tensor, details = infer(model, image, device)
        rows.append(detail_statistics(image, details, {"exposure": exposure}))
        for name, alpha in ALPHAS.items():
            write_gray(
                arm / "results" / "reconstructions" / "sem_acm" / name / f"{exposure}.bmp",
                alpha_image(tensor, details.total_delta, alpha),
            )
    frame = pd.DataFrame(rows)
    prior = pd.read_csv(
        ROOT / "results" / "posttraining_validation" / "sem_contour" / "results" / "tables" / "per_exposure_summary.csv"
    )
    iou = prior.pivot(index="exposure", columns="method", values="iou")
    frame["r103_iou_delta_from_raw"] = frame["exposure"].map((iou["R103E48"] - iou["Raw"]).to_dict())
    frame.to_csv(arm / "branch_exposure_statistics.csv", index=False)
    expression = f"addpath('{SHARED.as_posix()}'); run_sem_acm_multimethod('{arm.as_posix()}')"
    subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
    return frame


def suite_config(item: dict[str, object], suite: str) -> dict[str, object]:
    source = json.loads(Path(item["config"]).read_text(encoding="utf-8"))
    return {
        "experiment_id": f"R103_E48_{suite}_AlphaProbe",
        "dataset": {**source["dataset"], "root": str(item["root"])},
        "acm": {
            **source["acm"], "initialization_mode": item["initialization"],
            "seed_radius_fraction": source["acm"].get("seed_radius_fraction", .2),
        },
    }


def run_external(model: torch.nn.Module, device: torch.device) -> pd.DataFrame:
    all_rows: list[dict[str, object]] = []
    for suite, item in SUITES.items():
        arm = OUTPUT / "external_alpha" / suite
        acm_table = arm / "results" / "tables" / "primary_contour_metrics.csv"
        reuse_completed_acm = acm_table.exists()
        cfg = suite_config(item, suite)
        write_json(arm / "config" / "experiment.json", cfg)
        stage_to_family = {row["stage"]: row["name"] for row in cfg["dataset"]["families"]}
        output_dirs: dict[str, dict[str, str]] = {"Raw": {}}
        output_dirs.update({name: {} for name in ALPHAS})
        sources = sorted((Path(item["root"]) / "src").rglob("*.bmp"))
        if len(sources) != 100:
            raise RuntimeError(f"{suite}: expected 100 source images")
        for index, source in enumerate(sources, start=1):
            relative = source.relative_to(Path(item["root"]) / "src")
            family = stage_to_family[relative.parent.name]
            image = read_gray(source)
            tensor, details = infer(model, image, device)
            all_rows.append(detail_statistics(
                image, details, {"suite": suite, "family": family, "image_id": f"{family}/{source.stem}"}
            ))
            if not reuse_completed_acm:
                for name, alpha in ALPHAS.items():
                    write_gray(arm / "reconstructions" / name / relative, alpha_image(tensor, details.total_delta, alpha))
            if index % 25 == 0:
                print(f"[{suite}] reconstructed {index}/100", flush=True)
        for family in cfg["dataset"]["families"]:
            family_name, stage = family["name"], family["stage"]
            output_dirs["Raw"][family_name] = str((Path(item["root"]) / "src" / stage).resolve())
            for name in ALPHAS:
                output_dirs[name][family_name] = str((arm / "reconstructions" / name / stage).resolve())
        if not reuse_completed_acm:
            write_json(arm / "results" / "inference_manifest.json", {
                "methods": ["Raw", *ALPHAS.keys()], "output_dirs": output_dirs,
            })
            expression = f"addpath('{SHARED.as_posix()}'); run_acm_multimethod('{arm.as_posix()}')"
            subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
        else:
            print(f"[{suite}] reusing completed ACM table", flush=True)
    frame = pd.DataFrame(all_rows)
    frame["raw_iou"] = np.nan
    frame["r103_iou"] = np.nan
    for suite, item in SUITES.items():
        prior = pd.read_csv(Path(item["prior"]))
        fixed = prior.loc[prior["alignment"] == "fixed_pixel_coordinates"]
        raw = fixed.loc[fixed["method"] == "Raw", ["image_id", "iou"]].rename(columns={"iou": "raw_iou"})
        r103 = fixed.loc[fixed["method"] == "R103E48", ["image_id", "iou"]].rename(columns={"iou": "r103_iou"})
        subset = frame["suite"] == suite
        frame.loc[subset, "raw_iou"] = frame.loc[subset, "image_id"].map(raw.set_index("image_id")["raw_iou"])
        frame.loc[subset, "r103_iou"] = frame.loc[subset, "image_id"].map(r103.set_index("image_id")["r103_iou"])
    frame["r103_iou_delta_from_raw"] = frame["r103_iou"] - frame["raw_iou"]
    frame.to_csv(OUTPUT / "external_branch_statistics.csv", index=False)
    return frame


def summarize(sem: pd.DataFrame, external: pd.DataFrame) -> None:
    sem_metrics = [
        column for column in sem.columns
        if column.endswith(("_mean", "_mean_abs")) or column in ("raw_mean", "raw_std", "raw_gradient_mean")
    ]
    correlations = []
    for column in sem_metrics:
        rho, p = spearmanr(sem[column], sem["r103_iou_delta_from_raw"])
        correlations.append({"variable": column, "spearman_rho": float(rho), "p_value": float(p)})
    pd.DataFrame(correlations).sort_values("spearman_rho").to_csv(
        OUTPUT / "sem_iou_driver_correlations.csv", index=False
    )
    group_columns = [
        "raw_mean", "raw_std", "raw_gradient_mean", "low_mean_abs", "contour_mean_abs",
        "texture_mean_abs", "total_mean_abs", "contour_confidence_mean",
        "texture_confidence_mean", "contour_effective_scale_mean", "texture_effective_scale_mean",
        "raw_iou", "r103_iou", "r103_iou_delta_from_raw",
    ]
    external.groupby(["suite", "family"], sort=False)[group_columns].median().reset_index().to_csv(
        OUTPUT / "external_family_branch_summary.csv", index=False
    )
    clean = external["suite"] == "R73_novel_shapes"
    hard = external["suite"] == "R74_hard_microscopy"
    auc_rows = []
    for column in (
        "contour_confidence_mean", "texture_confidence_mean", "total_mean_abs",
        "contour_edge_mean_abs", "texture_edge_mean_abs",
    ):
        auc_rows.append({
            "score": column,
            "clean_median": float(external.loc[clean, column].median()),
            "hard_median": float(external.loc[hard, column].median()),
            "hard_vs_clean_auc": float(auc(external.loc[clean, column].to_numpy(), external.loc[hard, column].to_numpy())),
        })
    pd.DataFrame(auc_rows).to_csv(OUTPUT / "gate_discrimination.csv", index=False)

    alpha_summaries: dict[str, object] = {}
    sem_metrics_frame = pd.read_csv(OUTPUT / "sem_alpha" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    sem_alpha = sem_metrics_frame.groupby(["exposure", "method"], sort=False)["iou"].median().reset_index()
    sem_alpha.to_csv(OUTPUT / "sem_alpha_iou_by_exposure.csv", index=False)
    sem_wide = sem_alpha.pivot(index="exposure", columns="method", values="iou")
    alpha_summaries["sem_best_method_by_exposure"] = {
        str(int(exposure)): str(sem_wide.loc[exposure].idxmax()) for exposure in sem_wide.index
    }
    alpha_summaries["sem_best_iou_by_exposure"] = {
        str(int(exposure)): float(sem_wide.loc[exposure].max()) for exposure in sem_wide.index
    }
    for suite in SUITES:
        table = pd.read_csv(
            OUTPUT / "external_alpha" / suite / "results" / "tables" / "primary_contour_metrics.csv"
        )
        fixed = table.loc[table["alignment"] == "fixed_pixel_coordinates"]
        methods = fixed.groupby("method", sort=False)["iou"].median().sort_values(ascending=False)
        family = fixed.groupby(["family", "method"], sort=False)["iou"].median().reset_index()
        family.to_csv(OUTPUT / f"{suite}_alpha_family_iou.csv", index=False)
        alpha_summaries[suite] = {
            "method_median_iou": {str(k): float(v) for k, v in methods.items()},
            "best_method_by_family": {
                str(name): str(group.loc[group["iou"].idxmax(), "method"])
                for name, group in family.groupby("family")
            },
        }
    write_json(OUTPUT / "summary.json", {
        "status": "complete", "checkpoint_epoch": 48, "alphas": ALPHAS,
        "sem_exposures": 12, "external_images": 200,
        "alpha_results": alpha_summaries,
        "interpretation_contract": {
            "alpha_zero": "Raw; no learned correction",
            "varying_best_alpha": "Correction strength/gating is a driver",
            "all_alpha_poor": "Correction direction or missing cues is a driver",
        },
    })


def main() -> None:
    resume_summary = "--resume-summary" in sys.argv
    if OUTPUT.exists() and any(OUTPUT.iterdir()) and not resume_summary:
        raise RuntimeError(f"Refusing to overwrite causal probe: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(device)
    if resume_summary:
        sem = pd.read_csv(OUTPUT / "sem_alpha" / "branch_exposure_statistics.csv")
    else:
        sem = run_sem(model, device)
    external = run_external(model, device)
    summarize(sem, external)
    print(json.dumps({"status": "complete", "output": str(OUTPUT)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
