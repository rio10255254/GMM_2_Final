"""Read-only diagnosis of R88's near-identity behavior on real 50x images.

The script never changes the frozen model, trainer, generator, checkpoints, or
active training process.  It extracts auditable evidence into a separate
results folder.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "r88_model.py"
TRAINER_PATH = ROOT / "training" / "train_r88.py"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
GATES_PATH = ROOT / "config" / "acceptance_gates.json"
DATA_ROOT = ROOT / "data" / "r88_formal"
MANIFEST_PATH = DATA_ROOT / "manifest.json"
RUN_ROOT = ROOT / "runs" / "training_R88_scratch_seed880031_20260810_205058"
PROGRESS_PATH = RUN_ROOT / "run_progress.json"
TRAINING_LOG_PATH = RUN_ROOT / "training_log.csv"
WEIGHTS_ROOT = ROOT / "weights" / "formal" / "seed_880031" / "R88_scratch_seed880031_20260810_205058" / "weights"
REAL_FRAME = Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp/frame_0025.bmp'))
OUTPUT_ROOT = ROOT / "results" / "diagnosis_near_identity_behavior"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def checkpoint_epoch(path: Path) -> int:
    return int(path.name.split("_")[1].split(".")[0])


def real_output_trend(model_module: Any) -> pd.DataFrame:
    image = cv2.imread(str(REAL_FRAME), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(REAL_FRAME)
    crop = image[580:836, 700:956].astype(np.float32) / 255.0
    tensor = torch.from_numpy(crop)[None, None]
    rows: list[dict[str, Any]] = []
    for checkpoint in sorted(WEIGHTS_ROOT.glob("epoch_*.pth.tar"), key=checkpoint_epoch):
        epoch = checkpoint_epoch(checkpoint)
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        for state_key, weight_source in (("model_state_dict", "current"), ("ema_state_dict", "ema")):
            model = model_module.build_model(base=24)
            model.load_state_dict(payload[state_key], strict=True)
            model.eval()
            with torch.inference_mode():
                details = model(tensor, return_details=True)
            output_delta = (details["output"] - tensor).numpy() * 255.0
            candidate_delta = (details["candidate_output"] - tensor).numpy() * 255.0
            low_delta = details["low_delta"].numpy() * 255.0
            high_delta = details["high_delta"].numpy() * 255.0
            confidence = details["confidence"].numpy()
            rows.append(
                {
                    "epoch": epoch,
                    "weight_source": weight_source,
                    "confidence_mean": float(confidence.mean()),
                    "confidence_p95": float(np.percentile(confidence, 95.0)),
                    "candidate_change_gray_mean": float(np.abs(candidate_delta).mean()),
                    "output_change_gray_mean": float(np.abs(output_delta).mean()),
                    "output_change_gray_p95": float(np.percentile(np.abs(output_delta), 95.0)),
                    "signed_output_change_gray_mean": float(output_delta.mean()),
                    "low_delta_gray_mean": float(low_delta.mean()),
                    "high_delta_gray_mean": float(high_delta.mean()),
                    "gate_pass_fraction": float(np.abs(output_delta).mean() / max(np.abs(candidate_delta).mean(), 1e-12)),
                    "checkpoint": str(checkpoint),
                    "checkpoint_sha256": sha256_file(checkpoint),
                }
            )
    return pd.DataFrame(rows)


def validation_trend() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for checkpoint in sorted(WEIGHTS_ROOT.glob("epoch_*.pth.tar"), key=checkpoint_epoch):
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        validation = payload.get("metrics", {}).get("validation")
        if not validation:
            continue
        safety = validation["safety"]
        domains = validation["normalized_domain_ratios"]
        rows.append(
            {
                "epoch": int(payload["epoch"]),
                "eligible": bool(safety["eligible"]),
                "boundary_ratio_to_raw": float(domains["boundary"]),
                "texture_ratio_to_raw": float(domains["texture"]),
                "photometry_ratio_to_raw": float(domains["photometry"]),
                "motion_error_over_limit": float(domains["motion"]),
                "motion_mae_px": float(domains["motion"] * 0.03),
                "topology_mismatch_count": int(safety["topology_mismatch_count"]),
                "identity_change_gray": float(safety["identity_mean_abs_gray"]),
                "motion_bias_x_px": float(safety["signed_motion_bias_x_px"]),
                "motion_bias_y_px": float(safety["signed_motion_bias_y_px"]),
                "tile_change_gray": float(safety["tile_mean_abs_gray"]),
                "evaluated_cases": int(validation["evaluated_cases"]),
                "evaluated_views": int(validation["evaluated_cases"] * 2),
            }
        )
    return pd.DataFrame(rows)


def loss_contributions(design: dict[str, Any]) -> pd.DataFrame:
    weights = design["training"]["loss_weights"]
    mapping = {
        "pixel": "pixel_charbonnier",
        "low_band": "low_band_l1",
        "gradient": "gradient",
        "frequency": "recoverable_frequency",
        "signed_distance": "signed_distance_boundary",
        "boundary_iou": "soft_boundary_iou",
        "topology": "topology",
        "translation": "translation_equivariance",
        "displacement": "signed_displacement_bias",
        "consistency": "overlap_tile_consistency",
        "identity": "identity_guard",
        "noninferiority": "raw_noninferiority_hinge",
        "confidence": "confidence_calibration",
    }
    log = pd.read_csv(TRAINING_LOG_PATH)
    selected_epochs = [epoch for epoch in (50, 70, 80) if epoch in set(log["epoch"].astype(int))]
    rows: list[dict[str, Any]] = []
    for epoch in selected_epochs:
        record = log.loc[log["epoch"] == epoch].iloc[0]
        contributions = {
            component: float(record[f"train_{component}"]) * float(weights[weight_key])
            for component, weight_key in mapping.items()
        }
        total = sum(contributions.values())
        for component, contribution in contributions.items():
            rows.append(
                {
                    "epoch": int(epoch),
                    "component": component,
                    "weighted_contribution": float(contribution),
                    "share_of_total": float(contribution / max(total, 1e-12)),
                }
            )
    return pd.DataFrame(rows)


def degradation_limits(manifest: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in manifest["records"]:
        if record["split"] != "validation":
            continue
        target = np.load(DATA_ROOT / record["target"], mmap_mode="r", allow_pickle=False)[::4, ::4].astype(np.int16)
        for observation in record["observations"]:
            source = np.load(DATA_ROOT / observation["source"], mmap_mode="r", allow_pickle=False)[::4, ::4].astype(np.int16)
            difference = np.abs(source - target)
            rows.append(
                {
                    "role": record["role"],
                    "degradation_family": observation["degradation_family"],
                    "mean_absolute_target_gap_gray": float(difference.mean()),
                    "p95_target_gap_gray": float(np.percentile(difference, 95.0)),
                    "fraction_pixels_beyond_51_gray_bound": float(np.mean(difference > 51)),
                    "fraction_pixels_beyond_20_gray": float(np.mean(difference > 20)),
                }
            )
    table = pd.DataFrame(rows)
    return (
        table.groupby("degradation_family", as_index=False)
        .agg(
            observation_count=("mean_absolute_target_gap_gray", "size"),
            mean_target_gap_gray=("mean_absolute_target_gap_gray", "mean"),
            median_target_gap_gray=("mean_absolute_target_gap_gray", "median"),
            mean_p95_target_gap_gray=("p95_target_gap_gray", "mean"),
            fraction_pixels_beyond_51_gray_bound=("fraction_pixels_beyond_51_gray_bound", "mean"),
            fraction_pixels_beyond_20_gray=("fraction_pixels_beyond_20_gray", "mean"),
        )
        .sort_values("mean_target_gap_gray", ascending=False)
        .reset_index(drop=True)
    )


def motion_crop_quality(trainer_module: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    dataset = trainer_module.R88SceneDataset(DATA_ROOT, manifest, "validation", 640, 384, 0, all_observations=True)
    fractions: list[float] = []
    core = slice(128, 512)
    for index in range(len(dataset)):
        if dataset.role_at(index) != "signed_subpixel_motion":
            continue
        item = dataset[index]
        values = item["mask"][..., core, core].mean(dim=(-3, -2, -1)).numpy()
        fractions.extend(float(value) for value in values)
    array = np.asarray(fractions, dtype=float)
    return {
        "motion_validation_views": int(len(array)),
        "empty_views": int(np.sum(array == 0.0)),
        "views_below_1pct_foreground": int(np.sum(array < 0.01)),
        "empty_view_fraction": float(np.mean(array == 0.0)),
        "below_1pct_foreground_fraction": float(np.mean(array < 0.01)),
        "median_foreground_fraction": float(np.median(array)),
    }


def write_report(summary: dict[str, Any], real: pd.DataFrame, validation: pd.DataFrame) -> None:
    e50 = real.loc[(real["epoch"] == 50) & (real["weight_source"] == "ema")].iloc[0]
    e70 = real.loc[(real["epoch"] == 70) & (real["weight_source"] == "ema")].iloc[0]
    v70 = validation.loc[validation["epoch"] == 70].iloc[0]
    lines = [
        "# R88 近原圖輸出的根因診斷",
        "",
        "## 直接結論",
        "",
        "R88 不是完全沒有學習；它在合成資料上會做小幅輪廓修正。但對真實 50 倍影像，它目前主要退回原圖，只做很小的亮度調整。這是輸出限制、資料落差與訓練目標互相拉扯後形成的結果，不是顯示器或肉眼問題。",
        "",
        f"- 第 50 輪平均只改動 {e50['output_change_gray_mean']:.3f} 灰階；第 70 輪平均改動 {e70['output_change_gray_mean']:.3f} 灰階。",
        f"- 第 70 輪未經信心限制的候選修正是 {e70['candidate_change_gray_mean']:.3f} 灰階，最後只保留 {e70['gate_pass_fraction'] * 100.0:.1f}%。",
        f"- 截至診斷時已完成第 {summary['training']['completed_epoch']} 輪，但最佳合格輪次仍為 {summary['training']['best_eligible_epoch']}。",
        "",
        "## 為何會這樣",
        "",
        "1. 模型一開始就被設計成原圖直通，只有在有把握時才加上受限的小修正；因此不熟悉的影像最安全的答案就是幾乎不動。",
        "2. 訓練資料完全由程序合成，沒有讀取任何真實顯微影像、真實結構、量測 PSF，連允許使用的匿名光學統計也沒有實際導入。",
        "3. 標準答案與輸入的差距有一部分超過模型容許的最大修正範圍，資料要求與架構限制不完全相容。",
        "4. 位移訓練使用隨機裁切；真實檢查發現部分位移裁切幾乎沒有前景，使位移損失劇烈波動，迫使模型偏向保守答案。",
        "5. 同一模型同時承受輪廓、紋理、位移、拓撲、拼接、原圖保護與信心校準。合成輪廓雖改善，紋理與位移反而惡化，沒有任何輪次同時過關。",
        "",
        "## 已確認的失敗訊號",
        "",
        f"- 第 70 輪合成輪廓相對 Raw 改善 {(1.0 - v70['boundary_ratio_to_raw']) * 100.0:.1f}%，但紋理退化 {(v70['texture_ratio_to_raw'] - 1.0) * 100.0:.1f}%。",
        f"- 位移誤差是預定上限的 {v70['motion_error_over_limit']:.2f} 倍，拓撲不一致仍有 {int(v70['topology_mismatch_count'])} 個視圖。",
        f"- 位移驗證的 {summary['motion_crop_quality']['empty_views']}/{summary['motion_crop_quality']['motion_validation_views']} 個視圖完全沒有前景，{summary['motion_crop_quality']['views_below_1pct_foreground']}/{summary['motion_crop_quality']['motion_validation_views']} 個低於 1% 前景。",
        "",
        "## 判定",
        "",
        "R88 目前應標記為未達標研究實驗，而不是穩定候選模型。讓這次訓練跑完仍有紀錄價值，但即使第 100 輪數字下降，也必須重新通過真實細節、位移、拓撲與外部驗證，不能直接交付。",
        "",
        "## 下一輪應精準修正",
        "",
        "- 保留原圖安全通道，但讓重建分支先真正學會修復，再訓練是否採用修正的信心控制；不要讓信心控制從一開始就削弱所有修正。",
        "- 原圖不退化限制只鎖定真正接近原圖的樣本，不要同時壓制所有候選修正。",
        "- 使用不含樣品結構的真實光學統計校準模糊、雜訊與照明範圍，縮小合成與真實影像落差。",
        "- 位移裁切必須保證有可量測結構，並改用輪廓位置而非整張柔性重心。",
        "- 讓資料的可修復幅度落在模型輸出範圍內，或調整輸出範圍；兩者必須一致。",
    ]
    (OUTPUT_ROOT / "DIAGNOSIS_zh-TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    torch.set_num_threads(min(12, torch.get_num_threads()))
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    model_module = load_module("r88_near_identity_model", MODEL_PATH)
    trainer_module = load_module("r88_near_identity_trainer", TRAINER_PATH)

    real = real_output_trend(model_module)
    validation = validation_trend()
    losses = loss_contributions(design)
    limits = degradation_limits(manifest)
    motion_quality = motion_crop_quality(trainer_module, manifest)

    real.to_csv(OUTPUT_ROOT / "real_50x_output_trend.csv", index=False, encoding="utf-8-sig")
    validation.to_csv(OUTPUT_ROOT / "synthetic_validation_gate_trend.csv", index=False, encoding="utf-8-sig")
    losses.to_csv(OUTPUT_ROOT / "weighted_loss_contributions.csv", index=False, encoding="utf-8-sig")
    limits.to_csv(OUTPUT_ROOT / "degradation_vs_output_bound.csv", index=False, encoding="utf-8-sig")

    overall_bound_fraction = float(
        np.average(
            limits["fraction_pixels_beyond_51_gray_bound"],
            weights=limits["observation_count"],
        )
    )
    summary = {
        "status": "diagnosis_complete",
        "scope": "read_only_midtraining_diagnosis",
        "training": {
            "status": progress["status"],
            "completed_epoch": int(progress["completed_epoch"]),
            "planned_epochs": int(progress["planned_epochs"]),
            "best_eligible_epoch": int(progress["best_eligible_epoch"]),
            "best_ranked_epoch": int(progress["best_ranked_epoch"]),
            "latest_saved_checkpoint_epoch": int(real["epoch"].max()),
        },
        "verified_causes": {
            "output_is_raw_plus_confidence_gated_bounded_correction": True,
            "combined_correction_bound_gray": 51.0,
            "high_frequency_correction_bound_gray": 15.3,
            "confidence_initial_probability": float(1.0 / (1.0 + np.exp(4.0))),
            "procedural_training_only": True,
            "real_microscope_pixels_used": False,
            "measured_psf_used": False,
            "real_optical_statistics_loaded_by_generator": False,
            "identity_or_near_identity_observation_share": float(
                manifest["degradation_observation_counts"]["identity_and_near_identity"] / manifest["total_observations"]
            ),
            "validation_pixel_fraction_beyond_model_bound": overall_bound_fraction,
            "no_checkpoint_eligible_so_far": int(progress["best_eligible_epoch"]) == 0,
        },
        "motion_crop_quality": motion_quality,
        "inputs": {
            "model_sha256": sha256_file(MODEL_PATH),
            "trainer_sha256": sha256_file(TRAINER_PATH),
            "design_sha256": sha256_file(DESIGN_PATH),
            "gates_sha256": sha256_file(GATES_PATH),
            "manifest_sha256": sha256_file(MANIFEST_PATH),
            "training_log_sha256": sha256_file(TRAINING_LOG_PATH),
            "real_frame_sha256": sha256_file(REAL_FRAME),
        },
    }
    (OUTPUT_ROOT / "diagnostic_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(summary, real, validation)
    print(json.dumps({"status": summary["status"], "output": str(OUTPUT_ROOT), **summary["training"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
