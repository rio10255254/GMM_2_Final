"""Prepare every frozen R83 confirmation surface after checkpoint selection."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from skimage.metrics import structural_similarity
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark'))
OUTPUT = ROOT / "results" / "final_confirmation"
RECON = OUTPUT / "reconstructions"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
HOLDOUT = ROOT / "data" / "r83_locked_holdout_severe_microscopy"
HOLDOUT_MANIFEST = HOLDOUT / "manifest.json"
EXPECTED_HOLDOUT_MANIFEST_SHA256 = "1a7768fb1afd23829c3b9c75617b1d66be4df42703be865f6eef26cfccf9baf9"

sys.path.insert(0, str(ROOT / "model"))
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import ImageQualityGate  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inference_module():
    path = ROOT / "inference" / "infer_r83.py"
    spec = importlib.util.spec_from_file_location("r83_inference_for_final_confirmation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quality_alpha(image: np.ndarray) -> tuple[float, float]:
    tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None]
    with torch.no_grad():
        quality = float(ImageQualityGate.estimate_quality_score(tensor).item())
    alpha = 0.20 + 0.80 / (1.0 + math.exp(-(quality - 0.55) / 0.07))
    return quality, float(alpha)


def blend(raw: np.ndarray, reconstructed: np.ndarray, alpha: float) -> np.ndarray:
    value = raw.astype(np.float32) + alpha * (reconstructed.astype(np.float32) - raw.astype(np.float32))
    return np.clip(np.rint(value), 0, 255).astype(np.uint8)


def metrics(reference: np.ndarray, image: np.ndarray) -> dict[str, float]:
    ref = reference.astype(np.float32)
    pred = image.astype(np.float32)
    error = pred - ref
    mse = float(np.mean(error * error))
    gx_ref = cv2.Sobel(ref, cv2.CV_32F, 1, 0, ksize=3)
    gy_ref = cv2.Sobel(ref, cv2.CV_32F, 0, 1, ksize=3)
    gx_pred = cv2.Sobel(pred, cv2.CV_32F, 1, 0, ksize=3)
    gy_pred = cv2.Sobel(pred, cv2.CV_32F, 0, 1, ksize=3)
    edge_ref = cv2.magnitude(gx_ref, gy_ref)
    edge_pred = cv2.magnitude(gx_pred, gy_pred)
    return {
        "mae": float(np.mean(np.abs(error))),
        "psnr": 99.0 if mse == 0.0 else float(20.0 * math.log10(255.0 / math.sqrt(mse))),
        "ssim": float(structural_similarity(reference, image, data_range=255)),
        "edge_mae": float(np.mean(np.abs(edge_pred - edge_ref))),
    }


def selected_checkpoint() -> tuple[Path, dict]:
    manifest_path = ROOT / "weights" / "selected" / "selection_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Selected checkpoint manifest is missing; run the formal checkpoint screen first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "checkpoint_frozen_pending_reserved_confirmation":
        raise RuntimeError("Selected checkpoint is not in the frozen confirmation state.")
    checkpoint = Path(manifest["frozen_checkpoint"])
    if sha256(checkpoint) != manifest["frozen_checkpoint_sha256"]:
        raise RuntimeError("Frozen selected checkpoint hash changed.")
    return checkpoint, manifest


def prepare_holdout(module, r79_model, r83_model, holdout: dict) -> dict:
    pairs = holdout["pairs"]
    if len(pairs) != 384:
        raise RuntimeError(f"Locked holdout count changed: {len(pairs)}")
    metric_rows = []
    output_paths: dict[str, dict[str, Path]] = {name: {} for name in ["Raw", "R79", "R83Direct", "R83Safe"]}
    for index, pair in enumerate(pairs, start=1):
        source_path = HOLDOUT / pair["package_src"]
        label_path = HOLDOUT / pair["package_lbl"]
        relative = Path(pair["package_src"]).relative_to("src")
        raw = module.read_gray(source_path)
        label = module.read_gray(label_path)
        r79 = module.infer_tiled(r79_model, raw, "cuda:0", 4096, 0)
        direct = module.infer_tiled(r83_model, raw, "cuda:0", 4096, 0)
        quality, alpha = quality_alpha(raw)
        safe = blend(raw, direct, alpha)
        images = {"Raw": raw, "R79": r79, "R83Direct": direct, "R83Safe": safe}
        for method, image in images.items():
            target = RECON / "locked_synthetic" / method / relative
            module.write_bmp(target, image)
            output_paths[method][pair["pair_id"]] = target
            metric_rows.append({
                "pair_id": pair["pair_id"],
                "method": method,
                "training_role": pair["training_role"],
                "target_policy": pair["target_policy"],
                "observability_class": pair["observability_class"],
                "shape_family": pair["shape_family"],
                "degradation_family": pair["degradation_family"],
                "quality_score": quality,
                "safety_alpha": alpha if method == "R83Safe" else np.nan,
                **metrics(label, image),
            })
        if index % 64 == 0:
            print(f"Locked synthetic reconstruction {index}/{len(pairs)}", flush=True)
    table_dir = OUTPUT / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(metric_rows)
    frame.to_csv(table_dir / "locked_synthetic_per_pair.csv", index=False)
    frame.groupby("method", as_index=False).agg(
        median_mae=("mae", "median"), mean_mae=("mae", "mean"),
        median_psnr=("psnr", "median"), median_ssim=("ssim", "median"),
        median_edge_mae=("edge_mae", "median")
    ).to_csv(table_dir / "locked_synthetic_summary.csv", index=False)
    return {"pairs": pairs, "output_paths": output_paths}


def prepare_holdout_acm(module, prepared: dict) -> None:
    eligible = [
        pair for pair in prepared["pairs"]
        if pair["training_role"] in {"basic_geometry", "fine_noncircular"}
        or (pair["training_role"] == "boundary_fade_mixed" and pair["target_policy"] == "clean_analytic")
    ]
    eligible = sorted(eligible, key=lambda row: row["pair_id"])
    if len(eligible) != 160:
        raise RuntimeError(f"Locked ACM cohort changed: expected 160, found {len(eligible)}")
    acm_root = OUTPUT / "locked_synthetic_acm"
    dataset_root = acm_root / "dataset"
    methods = ["Raw", "R79", "R83Direct", "R83Safe"]
    output_dirs = {method: {} for method in methods}
    mapping_rows = []
    families = []
    for cohort_index in range(5):
        cohort = eligible[cohort_index * 32:(cohort_index + 1) * 32]
        family = f"cohort_{cohort_index + 1}"
        stage = f"stage_r83_holdout_acm_{cohort_index + 1}"
        families.append({"name": family, "label_tw": f"固定保留組 {cohort_index + 1}", "stage": stage})
        for method in methods:
            output_dirs[method][family] = str(acm_root / "results" / "reconstructions" / method / stage)
        for local_index, pair in enumerate(cohort):
            filename = f"{local_index:04d}.bmp"
            source = HOLDOUT / pair["package_src"]
            label = HOLDOUT / pair["package_lbl"]
            mask = HOLDOUT / pair["geometry_mask"]
            for plane, original in [("src", source), ("lbl", label), ("mask", mask)]:
                target = dataset_root / plane / stage / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, target)
            for method in methods:
                target = Path(output_dirs[method][family]) / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(prepared["output_paths"][method][pair["pair_id"]], target)
            mapping_rows.append({"family": family, "filename": filename, "pair_id": pair["pair_id"]})
    source_config = json.loads((R82 / "results" / "acm_external" / "R74_hard_microscopy" / "config" / "experiment.json").read_text(encoding="utf-8"))
    source_config["experiment_id"] = "R83_locked_synthetic_confirmation_ACM"
    source_config["dataset"].update({
        "root": str(dataset_root), "generator_version": CONFIG["dataset"]["generator_version"],
        "image_size": 256, "images_per_family": 32, "total_images": 160,
        "families": families, "mask_semantics": "one predeclared analytic object per image",
    })
    (acm_root / "config").mkdir(parents=True, exist_ok=True)
    (acm_root / "results").mkdir(parents=True, exist_ok=True)
    (acm_root / "config" / "experiment.json").write_text(json.dumps(source_config, indent=2, ensure_ascii=False), encoding="utf-8")
    (acm_root / "results" / "inference_manifest.json").write_text(
        json.dumps({"methods": methods, "output_dirs": output_dirs}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pd.DataFrame(mapping_rows).to_csv(acm_root / "acm_pair_mapping.csv", index=False)


def reconstruct_external(module, model, input_dirs: dict[str, Path], target_root: Path) -> dict[str, str]:
    outputs = {}
    for family, input_dir in input_dirs.items():
        target_dir = target_root / input_dir.name
        outputs[family] = str(target_dir)
        for source in sorted(input_dir.glob("*.bmp")):
            raw = module.read_gray(source)
            direct = module.infer_tiled(model, raw, "cuda:0", 4096, 0)
            module.write_bmp(target_dir / source.name, direct)
    return outputs


def prepare_development_recheck(module, model) -> None:
    for suite in ["R73_novel_shapes", "R74_hard_microscopy"]:
        prior_root = R82 / "results" / "acm_external" / suite
        cfg = json.loads((prior_root / "config" / "experiment.json").read_text(encoding="utf-8"))
        prior_manifest = json.loads((prior_root / "results" / "inference_manifest.json").read_text(encoding="utf-8"))
        suite_root = OUTPUT / "development_recheck" / suite
        cfg["experiment_id"] = f"R83_final_{suite}"
        (suite_root / "config").mkdir(parents=True, exist_ok=True)
        (suite_root / "results").mkdir(parents=True, exist_ok=True)
        (suite_root / "config" / "experiment.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest = {
            "methods": ["Raw", "R79", "R83Direct", "R83Safe"],
            "output_dirs": {"Raw": prior_manifest["output_dirs"]["Raw"], "R79": prior_manifest["output_dirs"]["R79"]},
        }
        raw_dirs = {family: Path(path) for family, path in manifest["output_dirs"]["Raw"].items()}
        direct_dirs = reconstruct_external(
            module, model, raw_dirs,
            suite_root / "results" / "reconstructions" / "R83Direct",
        )
        safe_dirs = {}
        for family, direct_dir_value in direct_dirs.items():
            raw_dir = Path(manifest["output_dirs"]["Raw"][family])
            direct_dir = Path(direct_dir_value)
            safe_dir = suite_root / "results" / "reconstructions" / "R83Safe" / direct_dir.name
            safe_dirs[family] = str(safe_dir)
            for source in sorted(raw_dir.glob("*.bmp")):
                raw = module.read_gray(source)
                direct = module.read_gray(direct_dir / source.name)
                _, alpha = quality_alpha(raw)
                module.write_bmp(safe_dir / source.name, blend(raw, direct, alpha))
        manifest["output_dirs"]["R83Direct"] = direct_dirs
        manifest["output_dirs"]["R83Safe"] = safe_dirs
        (suite_root / "results" / "inference_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_sem(module, model, r82_config: dict) -> None:
    sem_cfg = r82_config["sem_acm"]
    sem_root = OUTPUT / "SEM_reserved"
    raw_root = Path(PROJECT_ROOT / sem_cfg["raw_input_dir"])
    for exposure in sem_cfg["optical_exposures"]:
        source = raw_root / f"{exposure}.bmp"
        raw = module.read_gray(source)
        direct = module.infer_tiled(model, raw, "cuda:0", 4096, 0)
        _, alpha = quality_alpha(raw)
        module.write_bmp(sem_root / "results" / "reconstructions" / "sem_acm" / "R83Direct" / source.name, direct)
        module.write_bmp(sem_root / "results" / "reconstructions" / "sem_acm" / "R83Safe" / source.name, blend(raw, direct, alpha))
    prior_r79 = R82 / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_target = sem_root / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_target.mkdir(parents=True, exist_ok=True)
    for source in prior_r79.glob("*.bmp"):
        shutil.copy2(source, r79_target / source.name)
    selected_cfg = dict(sem_cfg)
    selected_cfg["selected_pillar_ids"] = CONFIG["final_confirmation_protocol"]["sem_reserved"]["pillar_ids"]
    (sem_root / "config").mkdir(parents=True, exist_ok=True)
    (sem_root / "config" / "experiment.json").write_text(json.dumps({
        "experiment_id": "R83_final_reserved_SEM",
        "models": {name: {} for name in ["R79", "R83Direct", "R83Safe"]},
        "sem_acm": selected_cfg,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_real_fov(module, model, r82_config: dict) -> list[dict]:
    item = r82_config["real_fov"]
    raw_root = Path(PROJECT_ROOT / item["locked_raw_root"])
    sources = sorted(raw_root.rglob("*.bmp"))
    if len(sources) != int(item["expected_frames"]):
        raise RuntimeError("Real-FOV frame count changed.")
    sample_records = []
    sequence_paths: dict[str, list[Path]] = {}
    for sequence in item["sequences"]:
        sequence_paths[sequence] = sorted((raw_root / sequence).glob("*.bmp"))
    tile_sample_set = {
        path for paths in sequence_paths.values() for path in (paths[0], paths[-1])
    }
    for index, source in enumerate(sources, start=1):
        relative = source.relative_to(raw_root)
        raw = module.read_gray(source)
        direct = module.infer_tiled(model, raw, "cuda:0", 4096, 0)
        _, alpha = quality_alpha(raw)
        module.write_bmp(RECON / "real_fov" / "R83Direct" / relative, direct)
        module.write_bmp(RECON / "real_fov" / "R83Safe" / relative, blend(raw, direct, alpha))
        if source in tile_sample_set:
            sample_records.append({"category": "real_fov", "name": relative.as_posix(), "path": str(source)})
        if index % 50 == 0:
            print(f"Real-FOV reconstruction {index}/{len(sources)}", flush=True)
    return sample_records


def prepare_tile_consistency(module, model, real_samples: list[dict], r82_config: dict) -> None:
    samples = list(real_samples)
    for source in sorted((ROOT / "data" / "live_validation").glob("*.bmp")):
        samples.append({"category": "live_validation", "name": source.name, "path": str(source)})
    sem_root = Path(PROJECT_ROOT / r82_config["sem_acm"]["raw_input_dir"])
    for exposure in [13, 18, 24]:
        source = sem_root / f"{exposure}.bmp"
        samples.append({"category": "SEM", "name": source.name, "path": str(source)})
    rows = []
    for sample in samples:
        source = Path(sample["path"])
        raw = module.read_gray(source)
        primary = module.infer_tiled(model, raw, "cuda:0", 4096, 0)
        secondary = module.infer_tiled(model, raw, "cuda:0", 512, 64)
        _, alpha = quality_alpha(raw)
        for method, left, right in [
            ("R83Direct", primary, secondary),
            ("R83Safe", blend(raw, primary, alpha), blend(raw, secondary, alpha)),
        ]:
            diff = np.abs(left.astype(np.float32) - right.astype(np.float32))
            rows.append({
                "category": sample["category"], "sample": sample["name"], "method": method,
                "mean_abs_gray": float(diff.mean()), "p99_abs_gray": float(np.quantile(diff, 0.99)),
                "max_abs_gray": float(diff.max()),
            })
    pd.DataFrame(rows).to_csv(OUTPUT / "tables" / "tile_consistency.csv", index=False)


def main() -> int:
    if sha256(HOLDOUT_MANIFEST) != EXPECTED_HOLDOUT_MANIFEST_SHA256:
        raise RuntimeError("Locked holdout manifest hash changed.")
    holdout = json.loads(HOLDOUT_MANIFEST.read_text(encoding="utf-8"))
    if holdout["content_sha256"] != "d05777efe003224d6cfb73c1cf222dae1b5b37f86932da67f6fc21ab37460b97":
        raise RuntimeError("Locked holdout content hash changed.")
    checkpoint, selected_manifest = selected_checkpoint()
    module = load_inference_module()
    parent = Path(PROJECT_ROOT / CONFIG["parent_model"]["checkpoint"])
    r79_model, r79_key = module.build_model(parent, "cuda:0", True)
    r83_model, r83_key = module.build_model(checkpoint, "cuda:0", True)
    if r79_key != "ema_state_dict" or r83_key != "ema_state_dict":
        raise RuntimeError("Final confirmation must use EMA states.")
    prepared = prepare_holdout(module, r79_model, r83_model, holdout)
    prepare_holdout_acm(module, prepared)
    del r79_model
    torch.cuda.empty_cache()
    prepare_development_recheck(module, r83_model)
    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    prepare_sem(module, r83_model, r82_config)
    real_samples = prepare_real_fov(module, r83_model, r82_config)
    prepare_tile_consistency(module, r83_model, real_samples, r82_config)
    manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "role": "frozen_reserved_confirmation",
        "selected_checkpoint": str(checkpoint),
        "selected_checkpoint_sha256": sha256(checkpoint),
        "selected_checkpoint_manifest": selected_manifest,
        "holdout_manifest_sha256": sha256(HOLDOUT_MANIFEST),
        "holdout_content_sha256": holdout["content_sha256"],
        "methods": ["R79", "R83Direct", "R83Safe"],
        "safety_formula": CONFIG["frozen_output_safety_policy"]["formula"],
        "reserved_confirmation_now_processed": True,
    }
    (OUTPUT / "confirmation_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"prepared": True, **manifest}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
