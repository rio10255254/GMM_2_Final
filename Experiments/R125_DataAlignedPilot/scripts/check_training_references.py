"""Post-start diagnostic: do fixed R125 checkpoints fit specified training data?

The first six manifest scenes (000..005, one category each) are selected by
index, not performance. This diagnostic was added after first-A training began.
It is not an independent holdout, selection metric, promotion gate, or evidence
of real-image usefulness. No training, targets, checkpoints, or profiles change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "R124_RealFirstPrototype"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT))
from prototype.network import build_model
from prototype.factorized_observation import from_observation
from model.calibration import observation_from_profile
from training.context import window_for, crop_arrays
from training.objectives import translated

SELECTED_SCENE_IDS = [f"scene_{index:03d}" for index in range(6)]
METRICS = ["native_image_mae_gray", "latent4x_mae_gray", "observation_noiseless_mae_gray",
           "observation_noisy_mae_gray", "observation_noisy_rmse_noise_units",
           "pair_reference_residual_mae_gray"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def tensor_digest(tensor):
    value = tensor.detach().cpu().contiguous()
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode())
    digest.update(str(tuple(value.shape)).encode())
    digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def save(path, value):
    def plain(item):
        if isinstance(item, dict):
            return {str(k): plain(v) for k, v in item.items()}
        if isinstance(item, (tuple, list)):
            return [plain(v) for v in item]
        if isinstance(item, np.generic):
            item = item.item()
        if isinstance(item, float) and not np.isfinite(item):
            return None
        return item
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(plain(value), stream, indent=2, allow_nan=False, ensure_ascii=False)
        stream.write("\n")


def package_file(package, relative):
    path = (package / relative).resolve()
    if not path.is_relative_to(package):
        raise ValueError("Package path escapes declared root")
    return path


def fixed_entries(package):
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("latent_sampling_factor") != 4 or manifest.get("scene_count") != 64:
        raise ValueError("Expected the admitted64-scene optical4x package")
    entries = manifest["scenes"][:6]
    if [entry["scene_id"] for entry in entries] != SELECTED_SCENE_IDS:
        raise ValueError("The first-six scene identity contract changed")
    if len({entry["category"] for entry in entries}) != 6:
        raise ValueError("First six scenes must contain one of each declared category")
    for index, entry in enumerate(entries):
        if entry["index"] != index:
            raise ValueError("Manifest scene ordering changed")
        for key, kind in (("arrays_path", "arrays"), ("metadata_path", "metadata")):
            path = package_file(package, entry[key])
            if sha(path) != entry["sha256"][kind]:
                raise ValueError(f"Scene source hash changed: {path}")
    return entries, sha(manifest_path)


def checkpoint_records(manifest_hash):
    index_path = ROOT / "runs" / "initializations" / "manifest.json"
    initial = json.loads(index_path.read_text(encoding="utf-8"))
    if initial["training_manifest_sha256"] != manifest_hash or len(initial["records"]) != 6:
        raise ValueError("Initial checkpoint manifest does not bind this exact package")
    records = []
    pairs = set()
    for entry in initial["records"]:
        key = (entry["arm"], int(entry["seed"]))
        if key in pairs:
            raise ValueError("Duplicate initial arm/seed")
        pairs.add(key)
        path = Path(entry["path"]).resolve()
        if sha(path) != entry["sha256"]:
            raise ValueError("Initial checkpoint hash changed")
        records.append(dict(record(path), arm=key[0], seed=key[1], step=0))
        run = ROOT / "runs" / f"{key[0]}_s{key[1]}"
        final = run / "checkpoints" / "step0064.pth"
        summary_path = run / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("completed_updates") != 64 or summary.get("checkpoint_sha256") != sha(final):
            raise ValueError(f"Final64 checkpoint is not complete and source-bound: {run}")
        records.append(dict(record(final), arm=key[0], seed=key[1], step=64,
                            training_summary=record(summary_path)))
    if len(pairs) != 6 or {arm for arm, _ in pairs} != {"A", "B", "C"}:
        raise ValueError("Expected three arms by two seeds")
    return sorted(records, key=lambda item: (item["arm"], item["seed"], item["step"]))


def bind_checkpoint(checkpoint, known_profile, device="cpu"):
    """Restore learned tensors; always use this case's known simulated optics."""
    config = checkpoint["model_config"]
    if config.get("sampling_factor") != 4 or config.get("prior_sampling_factor") != 2:
        raise ValueError("Expected optical4x/prior2x model configuration")
    if known_profile.get("simulation_known_operator") is not True or known_profile.get("sampling_factor") != 4:
        raise ValueError("Expected explicitly known simulation profile, not assumed real optics")
    observation = from_observation(observation_from_profile(known_profile), checkpoint_ops=True)
    model = build_model(config, observation=observation)
    learned = {name: value for name, value in checkpoint["model_state"].items() if not name.startswith("observation.")}
    expected = {name: value for name, value in model.state_dict().items() if not name.startswith("observation.")}
    if set(expected) != set(learned):
        raise ValueError("Non-observation checkpoint names differ")
    for name, value in learned.items():
        if not isinstance(value, torch.Tensor) or value.shape != expected[name].shape or value.dtype != expected[name].dtype:
            raise ValueError(f"Learned tensor contract differs: {name}")
    before = {name: tensor_digest(value) for name, value in observation.state_dict().items() if isinstance(value, torch.Tensor)}
    loaded = model.load_state_dict(learned, strict=False)
    if loaded.unexpected_keys or set(loaded.missing_keys) != {name for name in model.state_dict() if name.startswith("observation.")}:
        raise ValueError("Only observation checkpoint entries may be omitted")
    if any(not torch.equal(model.state_dict()[name], value) for name, value in learned.items()):
        raise ValueError("Learned tensors did not restore exactly")
    if before != {name: tensor_digest(value) for name, value in observation.state_dict().items() if isinstance(value, torch.Tensor)}:
        raise ValueError("Checkpoint replaced the case's known simulation profile")
    model.eval()
    return model.to(device), {"learned_tensor_count": len(learned), "learned_tensors_exact": True,
                             "ignored_observation_keys": loaded.missing_keys,
                             "known_profile_buffers_unchanged": True}


def core_numpy(value, core, factor=1):
    y0, y1, x0, x1 = core
    return value[..., y0*factor:y1*factor, x0*factor:x1*factor].detach().cpu().numpy().copy()


def mae(a, b):
    return float(np.mean(np.abs(a.astype(np.float64)-b.astype(np.float64)))*255)


def evaluate(package, output, device_name):
    package = package.resolve()
    output = output.resolve()
    if not output.is_relative_to(ROOT / "results"):
        raise ValueError("Diagnostic outputs must be under R125/results; training sources remain read-only")
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    try:
        entries, manifest_hash = fixed_entries(package)
        checkpoints = checkpoint_records(manifest_hash)
        sources = [record(Path(__file__)), record(package / "manifest.json"), record(ROOT / "runs/initializations/manifest.json")]
        sources += [record(ROOT / "training" / name) for name in ("context.py", "objectives.py")]
        sources += [record(path) for path in sorted((ROOT / "prototype").glob("*.py"))]
        sources += [record(BASE / "model" / name) for name in ("calibration.py", "observation.py", "network.py")]
        for entry in entries:
            sources += [record(package_file(package, entry[key])) for key in ("arrays_path", "metadata_path")]
        sources += [{key: item[key] for key in ("path", "sha256", "bytes")} for item in checkpoints]
        sources += [item["training_summary"] for item in checkpoints if item["step"] == 64]
        save(output / "source_ledger_before.json", sources)
        save(output / "diagnostic_contract.json", {
            "declared_after_first_A_training_started": True,
            "selection_rule": "First six manifest scenes000..005, deterministically one per category; not selected from performance",
            "scope": "Specified training references only; all12 initial/final checkpoints on identical six scene pairs",
            "not_selection_metric": True, "not_real_world_success_evidence": True, "not_holdout": True,
            "no_training_or_tuning": True, "no_checkpoint_selection": True, "calibration_qualified": False,
            "package_manifest_sha256": manifest_hash, "scenes": entries, "checkpoints": checkpoints,
            "native_core": "Original128 supervised pixels; training.context.window_for and crop_arrays unchanged",
            "input_scale": "Stored source uint8 /255, exactly as training; all floating targets already in0..1",
            "native_and_latent_error_units": "Mean absolute difference multiplied by255, including latent4x optical intensity",
            "observation_noiseless": "Predicted observation vs independently rendered noiseless optical image",
            "observation_noisy": "Predicted observation vs actual noisy/quantized input; distinct metric and label",
            "pair_metric": "Residual1 minus translated residual0, where residual=prediction-reference; native interpolation matches training",
            "motion_unobservable_policy": "Pair metric absent(None), not counted as perfect zero",
            "references_enter_model_forward": False})
        device = torch.device("cuda" if device_name == "auto" and torch.cuda.is_available() else "cpu" if device_name == "auto" else device_name)
        torch.set_num_threads(2)
        if device.type == "cuda":
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.allow_tf32 = False
            torch.backends.cuda.matmul.allow_tf32 = False
        rows, records = [], []
        reference_written = set()
        for item in checkpoints:
            checkpoint = torch.load(item["path"], map_location="cpu", weights_only=False)
            seed = checkpoint.get("model_seed", checkpoint.get("seed"))
            if (checkpoint["arm"], int(seed), checkpoint["step"]) != (item["arm"], item["seed"], item["step"]):
                raise ValueError("Checkpoint content identity differs from declared record")
            if checkpoint["training_source_manifest_sha256"] != manifest_hash:
                raise ValueError("Checkpoint binds different training package")
            for source_path, expected_hash in checkpoint.get("implementation_source_sha256", {}).items():
                if sha(source_path) != expected_hash:
                    raise ValueError(f"Checkpoint implementation changed: {source_path}")
            run_name = f"{item['arm']}_s{item['seed']}_step{item['step']:04d}"
            for entry in entries:
                metadata_path = package_file(package, entry["metadata_path"])
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if metadata["scene_id"] != entry["scene_id"] or metadata.get("external_training_inputs") != [] or metadata.get("existing_test_answer_access") is not False:
                    raise ValueError("Scene provenance does not match declared procedural training source")
                model, binding = bind_checkpoint(checkpoint, metadata["profile"], device)
                window = window_for(model, metadata)
                arrays_path = package_file(package, entry["arrays_path"])
                with np.load(arrays_path) as data:
                    cropped = crop_arrays({key: data[key] for key in ("source", "target", "latent_target", "noiseless")}, window)
                if cropped["source"].dtype != np.uint8 or any(cropped[key].dtype != np.float32 for key in ("target", "latent_target", "noiseless")):
                    raise ValueError("Reference units/storage dtypes differ from the training contract")
                if any(not np.isfinite(cropped[key]).all() or cropped[key].min() < 0 or cropped[key].max() > 1 for key in ("target", "latent_target", "noiseless")):
                    raise ValueError("Floating reference intensity outside normalized domain")
                source = torch.from_numpy(cropped["source"].astype(np.float32)/255)[:, None].to(device)
                # References are held separately and are only used after forward.
                if device.type == "cuda":
                    torch.cuda.synchronize(device)
                then = time.perf_counter()
                with torch.inference_mode():
                    details = model.forward_details(source, trace=False)
                target = torch.from_numpy(cropped["target"])[:, None].to(device)
                latent = torch.from_numpy(cropped["latent_target"])[:, None].to(device)
                noiseless = torch.from_numpy(cropped["noiseless"])[:, None].to(device)
                if details.output.shape != target.shape or details.latent.shape != latent.shape:
                    raise ValueError("Native/latent target shape mismatch")
                if not torch.isfinite(details.output).all() or not torch.isfinite(details.latent).all():
                    raise ValueError("Nonfinite diagnostic output")
                with torch.inference_mode():
                    observation = model.observation(details.latent)
                    reference_observation = model.observation(latent)
                    residual = details.output-target
                    pair = residual[1:2]-translated(residual[0:1], metadata["shift_xy"]) if metadata["motion_observable"] else None
                    reference_pair = target[1:2]-translated(target[0:1], metadata["shift_xy"]) if metadata["motion_observable"] else None
                if device.type == "cuda":
                    torch.cuda.synchronize(device)
                core = window["core"]
                reference_arrays = {"source_native": core_numpy(source, core), "target_native": core_numpy(target, core),
                                    "target_latent4x": core_numpy(latent, core, 4), "noiseless_native": core_numpy(noiseless, core)}
                outputs = {"output_native": core_numpy(details.output, core), "output_latent4x": core_numpy(details.latent, core, 4),
                           "predicted_observation": core_numpy(observation, core), "reference_forward_observation": core_numpy(reference_observation, core)}
                if pair is not None:
                    outputs["pair_reference_residual"] = core_numpy(pair, core)
                    outputs["native_reference_pair_interpolation_difference"] = core_numpy(reference_pair, core)
                if any(value.shape[-2:] != (128, 128) for key, value in outputs.items() if "latent4x" not in key):
                    raise ValueError("Original128 diagnostic core changed")
                if outputs["output_latent4x"].shape[-2:] != (512, 512):
                    raise ValueError("Latent4x core changed")
                directory = output / "checkpoints" / run_name / entry["scene_id"]
                directory.mkdir(parents=True, exist_ok=False)
                np.savez_compressed(directory / "outputs.npz", **outputs)
                reference_directory = output / "references" / entry["scene_id"]
                if entry["scene_id"] not in reference_written:
                    reference_directory.mkdir(parents=True, exist_ok=False)
                    np.savez_compressed(reference_directory / "core_references.npz", **reference_arrays)
                    save(reference_directory / "source.json", {"arrays": record(arrays_path), "metadata": record(metadata_path),
                                                               "window": window, "original_native_core": [256, 384, 256, 384]})
                    reference_written.add(entry["scene_id"])
                else:
                    with np.load(reference_directory / "core_references.npz") as fixed:
                        if any(not np.array_equal(fixed[key], value) for key, value in reference_arrays.items()):
                            raise ValueError("Core training references changed across checkpoints")
                variance = float(model.observation.noise_variance)
                for view in range(2):
                    pred, truth = outputs["output_native"][view], reference_arrays["target_native"][view]
                    obs, clean, noisy = outputs["predicted_observation"][view], reference_arrays["noiseless_native"][view], reference_arrays["source_native"][view]
                    rows.append({"arm": item["arm"], "seed": item["seed"], "step": item["step"], "scene_id": entry["scene_id"],
                                 "category": entry["category"], "view": view, "native_image_mae_gray": mae(pred, truth),
                                 "latent4x_mae_gray": mae(outputs["output_latent4x"][view], reference_arrays["target_latent4x"][view]),
                                 "observation_noiseless_mae_gray": mae(obs, clean), "observation_noisy_mae_gray": mae(obs, noisy),
                                 "observation_noisy_rmse_noise_units": float(np.sqrt(np.mean((obs.astype(float)-noisy.astype(float))**2)/variance)),
                                 "reference_forward_vs_noiseless_mae_gray": mae(outputs["reference_forward_observation"][view], clean),
                                 "Raw_native_image_mae_gray": mae(noisy, truth), "noise_quantization_vs_noiseless_mae_gray": mae(noisy, clean),
                                 "motion_observable": bool(metadata["motion_observable"]),
                                 "pair_reference_residual_mae_gray": float(np.abs(outputs["pair_reference_residual"].astype(float)).mean()*255) if pair is not None else None,
                                 "native_reference_pair_interpolation_mismatch_gray": float(np.abs(outputs["native_reference_pair_interpolation_difference"].astype(float)).mean()*255) if pair is not None else None,
                                 "interpretation": "Training-reference diagnostic, not a real-validation or selection score"})
                # Pair score is repeated on two view rows only for convenient joins;
                # aggregation uses per-scene mean, so it is never counted twice.
                with np.load(directory / "outputs.npz") as saved_outputs:
                    if any(not np.array_equal(saved_outputs[key], value) for key, value in outputs.items()):
                        raise ValueError("Saved diagnostic output differs from measured arrays")
                detail_record = {"arm": item["arm"], "seed": item["seed"], "step": item["step"], "scene_id": entry["scene_id"],
                                 "checkpoint_sha256": item["sha256"], "binding": binding, "window": window,
                                 "actual_source_tensor_sha256": tensor_digest(source), "actual_source_shape": list(source.shape),
                                 "known_simulation_profile_source": record(metadata_path),
                                 "known_simulation_profile_id": model.observation.calibration_id,
                                 "original_simulation_kernel_tensor_sha256": tensor_digest(model.observation.kernel),
                                 "sampling_factor": model.observation.sampling_factor,
                                 "simulation_gain": float(model.observation.gain), "simulation_bias": float(model.observation.bias),
                                 "simulation_noise_variance": variance,
                                 "operator_implementation": model.observation.factorization_metadata(),
                                 "reference_fields_entered_forward": False, "calibration_qualified": False, "uncertainty_calibrated": False,
                                 "elapsed_seconds": time.perf_counter()-then, "output_arrays": record(directory / "outputs.npz")}
                save(directory / "metadata.json", detail_record)
                records.append({key: detail_record[key] for key in ("arm", "seed", "step", "scene_id", "elapsed_seconds", "output_arrays")})
                print(f"Training-reference diagnostic: {run_name} / {entry['scene_id']}", flush=True)
                del model, details, source, target, latent, noiseless, observation, reference_observation, pair, reference_pair, cropped
        frame = pd.DataFrame(rows)
        frame.to_csv(output / "per_view_metrics.csv", index=False, mode="x")
        identifiers = ["arm", "seed", "step", "scene_id", "category"]
        per_scene = frame.groupby(identifiers, sort=False)[METRICS].mean().reset_index()
        initial = per_scene[per_scene.step == 0].set_index(["arm", "seed", "scene_id"])
        for metric in METRICS:
            per_scene[f"{metric}_change_vs_own_step0"] = [row[metric]-initial.loc[(row.arm, row.seed, row.scene_id), metric]
                                                           if pd.notna(row[metric]) else np.nan for _, row in per_scene.iterrows()]
        per_scene.to_csv(output / "per_scene_comparison.csv", index=False, mode="x")
        overall = per_scene.groupby(["arm", "seed", "step"], sort=False)[METRICS].mean().reset_index()
        scene_counts = per_scene.groupby(["arm", "seed", "step"], sort=False).agg(
            scene_count=("scene_id", "size"), pair_observable_scene_count=("pair_reference_residual_mae_gray", "count")).reset_index()
        overall = overall.merge(scene_counts, on=["arm", "seed", "step"], validate="one_to_one")
        overall["pair_unobservable_scene_count"] = overall.scene_count-overall.pair_observable_scene_count
        overall.to_csv(output / "training_reference_summary.csv", index=False, mode="x")
        for source_record in sources:
            if sha(source_record["path"]) != source_record["sha256"]:
                raise ValueError(f"Protected diagnostic source changed: {source_record['path']}")
        save(output / "verification.json", {"protected_sources_unchanged": True, "source_count": len(sources),
                                            "all_shared_core_references_exact_across_checkpoints": True,
                                            "all_saved_output_arrays_exact": True, "model_forward_calls": len(records),
                                            "view_rows": len(rows), "checkpoint_count": len(checkpoints), "scene_count": len(entries),
                                            "expected_counts_match": len(records)==72 and len(rows)==144 and len(per_scene)==72})
        if len(records) != 72 or len(rows) != 144 or len(per_scene) != 72:
            raise ValueError("Diagnostic did not cover all12 checkpoints by six scene pairs")
        save(output / "summary.json", {"status": "training_reference_diagnostic_complete", "completed_utc": datetime.now(timezone.utc).isoformat(),
                                       "elapsed_seconds": time.perf_counter()-started, "device": str(device),
                                       "diagnostic_added_after_training_started": True, "selected_scene_ids": SELECTED_SCENE_IDS,
                                       "model_forward_calls": len(records), "checkpoint_count": len(checkpoints), "training_scene_pairs": len(entries),
                                       "training_reference_results": overall.to_dict("records"), "protected_sources_unchanged": True,
                                       "not_selection_metric": True, "real_world_success_evaluated": False,
                                       "calibration_qualified": False, "uncertainty_calibrated": False})
    except BaseException as error:
        save(output / "failure.json", {"status": "failed", "error": str(error), "traceback": traceback.format_exc(),
                                      "diagnostic_not_selection_metric": True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    arguments = parser.parse_args()
    evaluate(arguments.package, arguments.output, arguments.device)


if __name__ == "__main__":
    main()
