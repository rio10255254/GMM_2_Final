"""Prepare every locked R84 confirmation surface after the checkpoint is frozen."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from skimage.metrics import structural_similarity
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark'))
R83 = Path(str(PROJECT_ROOT / 'Experiments/R83_R79SevereMicroscopyStrengthening'))
OUTPUT = ROOT / "results" / "final_confirmation"
TABLES = OUTPUT / "tables"
RECON = OUTPUT / "reconstructions"
HOLDOUT = ROOT / "data" / "r84_locked_holdout_tile_stable_confirmation"
DEVICE = "cuda:0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module():
    path = ROOT / "inference" / "infer_r84.py"
    spec = importlib.util.spec_from_file_location("r84_final_inference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image_metrics(reference: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    ref = reference.astype(np.float32)
    pred = prediction.astype(np.float32)
    error = pred - ref
    mse = float(np.mean(error * error))
    gx_ref = cv2.Sobel(ref, cv2.CV_32F, 1, 0, ksize=3)
    gy_ref = cv2.Sobel(ref, cv2.CV_32F, 0, 1, ksize=3)
    gx_pred = cv2.Sobel(pred, cv2.CV_32F, 1, 0, ksize=3)
    gy_pred = cv2.Sobel(pred, cv2.CV_32F, 0, 1, ksize=3)
    return {
        "mae": float(np.mean(np.abs(error))),
        "psnr": 99.0 if mse == 0.0 else float(20.0 * np.log10(255.0 / np.sqrt(mse))),
        "ssim": float(structural_similarity(reference, prediction, data_range=255)),
        "edge_mae": float(
            np.mean(
                np.abs(
                    cv2.magnitude(gx_ref, gy_ref)
                    - cv2.magnitude(gx_pred, gy_pred)
                )
            )
        ),
    }


def infer_r79_native(module, model, image: np.ndarray) -> np.ndarray:
    prediction = module._run(model, image, DEVICE)
    return np.clip(np.rint(prediction * 255.0), 0, 255).astype(np.uint8)


def verify_locks() -> tuple[dict, dict, Path]:
    holdout_lock = json.loads((ROOT / "reports" / "R84_HOLDOUT_LOCK.json").read_text(encoding="utf-8"))
    manifest_path = HOLDOUT / "manifest.json"
    if sha256(manifest_path) != holdout_lock["manifest_sha256"]:
        raise RuntimeError("Locked holdout manifest changed.")
    if sha256(HOLDOUT / "source_audit.json") != holdout_lock["source_audit_sha256"]:
        raise RuntimeError("Locked holdout source audit changed.")
    holdout = json.loads(manifest_path.read_text(encoding="utf-8"))
    if holdout.get("content_sha256") != holdout_lock["content_sha256"]:
        raise RuntimeError("Locked holdout content identity changed.")
    if len(holdout["pairs"]) != holdout_lock["total_pairs"]:
        raise RuntimeError("Locked holdout count changed.")

    selected = json.loads((ROOT / "weights" / "selected" / "manifest.json").read_text(encoding="utf-8"))
    checkpoint = ROOT / selected["delivered_checkpoint"]
    if sha256(checkpoint) != selected["checkpoint_sha256"]:
        raise RuntimeError("Frozen R84 checkpoint changed.")
    decision = json.loads((ROOT / selected["selection_decision"]).read_text(encoding="utf-8"))
    if decision.get("external_or_reserved_results_used") is not False:
        raise RuntimeError("The frozen checkpoint was not selected independently of confirmation evidence.")
    return holdout, selected, checkpoint


def prepare_locked_holdout(module, r79_model, r84_model, holdout: dict) -> dict:
    records = []
    output_paths: dict[str, dict[str, Path]] = {name: {} for name in ("Raw", "R79", "R84")}
    tile_records = []
    for index, pair in enumerate(holdout["pairs"], start=1):
        source = HOLDOUT / pair["package_src"]
        label_path = HOLDOUT / pair["package_lbl"]
        relative = Path(pair["package_src"]).relative_to("src")
        raw = module.read_gray(source)
        label = module.read_gray(label_path)
        r79 = infer_r79_native(module, r79_model, raw)
        full = module.infer_canonical_full(r84_model, raw, DEVICE)
        tiled = module.infer_phase_locked_tiled(r84_model, raw, DEVICE)
        images = {"Raw": raw, "R79": r79, "R84": tiled}
        for method, image in images.items():
            target = RECON / "locked_synthetic" / method / relative
            module.write_bmp(target, image)
            output_paths[method][pair["pair_id"]] = target
            records.append({
                "pair_id": pair["pair_id"],
                "method": method,
                "training_role": pair["training_role"],
                "target_policy": pair["target_policy"],
                "observability_class": pair["observability_class"],
                "shape_family": pair["shape_family"],
                "degradation_family": pair["degradation_family"],
                **image_metrics(label, image),
            })
        tile_records.append({
            "category": "new_locked_synthetic",
            "sample": pair["pair_id"],
            "method": "R84",
            **module.difference_metrics(full, tiled),
        })
        if index % 64 == 0:
            print(f"locked holdout {index}/{len(holdout['pairs'])}", flush=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(records)
    frame.to_csv(TABLES / "locked_synthetic_per_pair.csv", index=False)
    frame.groupby("method", as_index=False).agg(
        median_mae=("mae", "median"),
        mean_mae=("mae", "mean"),
        median_psnr=("psnr", "median"),
        median_ssim=("ssim", "median"),
        median_edge_mae=("edge_mae", "median"),
    ).to_csv(TABLES / "locked_synthetic_summary.csv", index=False)
    return {"output_paths": output_paths, "tile_records": tile_records}


def prepare_holdout_acm(prepared: dict, holdout: dict, r82_config: dict) -> None:
    eligible = [
        pair for pair in holdout["pairs"]
        if pair["training_role"] in {"basic_geometry", "fine_noncircular"}
        or (pair["training_role"] == "boundary_fade_mixed" and pair["target_policy"] == "clean_analytic")
    ]
    eligible = sorted(eligible, key=lambda row: row["pair_id"])
    if len(eligible) != 160:
        raise RuntimeError(f"Expected 160 predeclared ACM holdout images, found {len(eligible)}")
    acm_root = OUTPUT / "locked_synthetic_acm"
    dataset_root = acm_root / "dataset"
    methods = ["Raw", "R79", "R84"]
    output_dirs = {method: {} for method in methods}
    mapping = []
    families = []
    for cohort_index in range(5):
        cohort = eligible[cohort_index * 32:(cohort_index + 1) * 32]
        family = f"cohort_{cohort_index + 1}"
        stage = f"stage_r84_holdout_acm_{cohort_index + 1}"
        families.append({"name": family, "label_tw": f"固定保留組 {cohort_index + 1}", "stage": stage})
        for method in methods:
            output_dirs[method][family] = str(acm_root / "results" / "reconstructions" / method / stage)
        for local_index, pair in enumerate(cohort):
            filename = f"{local_index:04d}.bmp"
            originals = {
                "src": HOLDOUT / pair["package_src"],
                "lbl": HOLDOUT / pair["package_lbl"],
                "mask": HOLDOUT / pair["geometry_mask"],
            }
            for plane, original in originals.items():
                target = dataset_root / plane / stage / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, target)
            for method in methods:
                target = Path(output_dirs[method][family]) / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(prepared["output_paths"][method][pair["pair_id"]], target)
            mapping.append({"family": family, "filename": filename, "pair_id": pair["pair_id"]})
    source = json.loads(
        (R82 / "results" / "acm_external" / "R74_hard_microscopy" / "config" / "experiment.json").read_text(encoding="utf-8")
    )
    source["experiment_id"] = "R84_locked_synthetic_confirmation_ACM"
    source["dataset"].update({
        "root": str(dataset_root),
        "generator_version": holdout["generator_version"],
        "image_size": 256,
        "images_per_family": 32,
        "total_images": 160,
        "families": families,
        "mask_semantics": "one predeclared analytic object per image",
    })
    (acm_root / "config").mkdir(parents=True, exist_ok=True)
    (acm_root / "results").mkdir(parents=True, exist_ok=True)
    (acm_root / "config" / "experiment.json").write_text(json.dumps(source, indent=2, ensure_ascii=False), encoding="utf-8")
    (acm_root / "results" / "inference_manifest.json").write_text(
        json.dumps({"methods": methods, "output_dirs": output_dirs}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    pd.DataFrame(mapping).to_csv(acm_root / "acm_pair_mapping.csv", index=False)


def reconstruct_suite(module, model, raw_dirs: dict[str, str], target_root: Path) -> dict[str, str]:
    outputs = {}
    for family, raw_dir_value in raw_dirs.items():
        raw_dir = Path(raw_dir_value)
        target_dir = target_root / raw_dir.name
        outputs[family] = str(target_dir)
        for source in sorted(raw_dir.glob("*.bmp")):
            raw = module.read_gray(source)
            module.write_bmp(target_dir / source.name, module.infer_phase_locked_tiled(model, raw, DEVICE))
    return outputs


def prepare_r73_r74(module, model) -> None:
    for suite in ("R73_novel_shapes", "R74_hard_microscopy"):
        prior = R82 / "results" / "acm_external" / suite
        config = json.loads((prior / "config" / "experiment.json").read_text(encoding="utf-8"))
        manifest = json.loads((prior / "results" / "inference_manifest.json").read_text(encoding="utf-8"))
        target = OUTPUT / "development_recheck" / suite
        config["experiment_id"] = f"R84_final_{suite}"
        (target / "config").mkdir(parents=True, exist_ok=True)
        (target / "results").mkdir(parents=True, exist_ok=True)
        (target / "config" / "experiment.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        output_dirs = {
            "Raw": manifest["output_dirs"]["Raw"],
            "R79": manifest["output_dirs"]["R79"],
        }
        output_dirs["R84"] = reconstruct_suite(
            module, model, output_dirs["Raw"], target / "results" / "reconstructions" / "R84"
        )
        (target / "results" / "inference_manifest.json").write_text(
            json.dumps({"methods": ["Raw", "R79", "R84"], "output_dirs": output_dirs}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def prepare_sem(module, model, r82_config: dict) -> None:
    sem = r82_config["sem_acm"]
    root = OUTPUT / "SEM_reserved"
    raw_root = Path(PROJECT_ROOT / sem["raw_input_dir"])
    r84_dir = root / "results" / "reconstructions" / "sem_acm" / "R84"
    for exposure in sem["optical_exposures"]:
        source = raw_root / f"{exposure}.bmp"
        raw = module.read_gray(source)
        module.write_bmp(r84_dir / source.name, module.infer_phase_locked_tiled(model, raw, DEVICE))
    r79_dir = root / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_dir.mkdir(parents=True, exist_ok=True)
    for source in (R82 / "results" / "reconstructions" / "sem_acm" / "R79").glob("*.bmp"):
        shutil.copy2(source, r79_dir / source.name)
    selected_sem = dict(sem)
    selected_sem["selected_pillar_ids"] = list(range(1, 37))
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "experiment.json").write_text(json.dumps({
        "experiment_id": "R84_final_reserved_SEM_all36",
        "models": {"R79": {}, "R84": {}},
        "sem_acm": selected_sem,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_real_fov_and_fixed_tiles(module, model, r82_config: dict, tile_rows: list[dict]) -> None:
    real = r82_config["real_fov"]
    raw_root = Path(PROJECT_ROOT / real["locked_raw_root"])
    sources = sorted(raw_root.rglob("*.bmp"))
    if len(sources) != int(real["expected_frames"]):
        raise RuntimeError(f"Expected {real['expected_frames']} real frames, found {len(sources)}")
    fixed = []
    for sequence in real["sequences"]:
        sequence_sources = sorted((raw_root / sequence).glob("*.bmp"))
        fixed.extend((sequence_sources[0], sequence_sources[-1]))
    for index, source in enumerate(sources, start=1):
        raw = module.read_gray(source)
        relative = source.relative_to(raw_root)
        module.write_bmp(RECON / "real_fov" / "R84" / relative, module.infer_phase_locked_tiled(model, raw, DEVICE))
        if index % 50 == 0:
            print(f"real FOV {index}/{len(sources)}", flush=True)
    fixed.extend(sorted((R83 / "data" / "live_validation").glob("*.bmp")))
    sem_root = Path(PROJECT_ROOT / r82_config["sem_acm"]["raw_input_dir"])
    fixed.extend(sem_root / f"{exposure}.bmp" for exposure in (13, 18, 24))
    if len(fixed) != 18:
        raise RuntimeError(f"Expected 18 fixed tile samples, found {len(fixed)}")
    for source in fixed:
        raw = module.read_gray(source)
        full = module.infer_canonical_full(model, raw, DEVICE)
        tiled = module.infer_phase_locked_tiled(model, raw, DEVICE)
        tile_rows.append({
            "category": "fixed_external_extent",
            "sample": str(source),
            "method": "R84",
            **module.difference_metrics(full, tiled),
        })


def main() -> int:
    holdout, selected, checkpoint = verify_locks()
    module = load_module()
    r79, r79_key = module.build_model(ROOT / "weights" / "seed" / "r79e23_ema_seed.pth.tar", DEVICE, tile_stable=False, use_ema=True)
    r84, r84_key = module.build_model(checkpoint, DEVICE, tile_stable=True, use_ema=True)
    if r79_key != "ema_state_dict" or r84_key != "ema_state_dict":
        raise RuntimeError("Final confirmation must use EMA weights.")
    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    prepared = prepare_locked_holdout(module, r79, r84, holdout)
    prepare_holdout_acm(prepared, holdout, r82_config)
    del r79
    torch.cuda.empty_cache()
    prepare_r73_r74(module, r84)
    prepare_sem(module, r84, r82_config)
    prepare_real_fov_and_fixed_tiles(module, r84, r82_config, prepared["tile_records"])
    tile_table = pd.DataFrame(prepared["tile_records"])
    tile_table.to_csv(TABLES / "tile_consistency.csv", index=False)
    manifest = {
        "experiment_id": "R84_R79TileStableRootRepair",
        "role": "frozen_confirmation",
        "selected_checkpoint": str(checkpoint),
        "selected_checkpoint_sha256": selected["checkpoint_sha256"],
        "holdout_manifest_sha256": sha256(HOLDOUT / "manifest.json"),
        "holdout_content_sha256": holdout["content_sha256"],
        "methods": ["R79", "R84"],
        "reserved_confirmation_processed_after_selection": True,
        "locked_synthetic_count": len(holdout["pairs"]),
        "fixed_tile_count": 18,
        "tile_row_count": int(len(tile_table)),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "confirmation_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
