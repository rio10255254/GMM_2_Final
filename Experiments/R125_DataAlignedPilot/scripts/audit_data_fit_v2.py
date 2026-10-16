"""Independent v2 admission audit: 8x physical rendering, 4x optical state.

Rejected v1 artifacts are read-only comparisons. No threshold, condition, noise,
or kernel is adjusted to obtain admission. R124's exact LinearObservation is
called on each supervised core with sufficient physical context.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.signal import convolve
import torch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r125_preserved_v1_audit_helpers", ROOT / "scripts" / "audit_data_fit.py")
base = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(base)
CORE = base.CORE
LATENT_FACTOR = 4
RENDER_FACTOR = 8
HARD_SCENES = (7, 13, 20, 50)
PHYSICAL_REPLAY_SCENES = (0, 3, 4, 5, 7, 13, 20, 50)
OPERATOR_DEVICE = "cpu"


def core_prediction(latent: np.ndarray, profile: dict, core=CORE) -> np.ndarray:
    observation = base.observation_from_profile(profile).to(OPERATOR_DEVICE)
    if observation.sampling_factor != LATENT_FACTOR:
        raise ValueError("v2 requires four optical cells per native pixel axis")
    radius = observation.kernel_radius_internal
    margin = math.ceil(radius / LATENT_FACTOR) + 1
    r0, r1, c0, c1 = core
    if min(r0, c0, latent.shape[-2] // LATENT_FACTOR - r1, latent.shape[-1] // LATENT_FACTOR - c1) < margin:
        raise ValueError("physical context does not cover the actual observation support")
    patch = latent[:, (r0-margin)*LATENT_FACTOR:(r1+margin)*LATENT_FACTOR,
                   (c0-margin)*LATENT_FACTOR:(c1+margin)*LATENT_FACTOR]
    tensor = torch.from_numpy(np.ascontiguousarray(patch[:, None])).float().to(OPERATOR_DEVICE)
    with torch.inference_mode():
        prediction = observation(tensor)[:, 0, margin:margin+r1-r0, margin:margin+c1-c0]
    return prediction.cpu().numpy()


def independent_kernel(metadata: dict) -> np.ndarray:
    optics = metadata["rendering_profile"]
    sx, sy = map(float, optics["sigma_native_xy"])
    radius = int(optics["radius_native"])
    if sx == 0 and sy == 0:
        return np.ones((1, 1), dtype=np.float64)
    axis = np.arange(-radius*RENDER_FACTOR, radius*RENDER_FACTOR+1, dtype=np.float64) / RENDER_FACTOR
    xx, yy = np.meshgrid(axis, axis)
    angle = float(optics["rotation_rad"])
    u, v = np.cos(angle)*xx + np.sin(angle)*yy, np.cos(angle)*yy - np.sin(angle)*xx
    kernel = np.exp(-0.5*((u/sx)**2+(v/sy)**2))
    return kernel / kernel.sum()


def physical_replay(arrays: dict, metadata: dict, old_record: dict | None = None) -> dict:
    """Analytic Float64 rendering of two 16px neighborhoods, at 8x density."""
    kernel = independent_kernel(metadata)
    declared = np.asarray(metadata["rendering_profile"]["kernel"], dtype=np.float64)
    if kernel.shape != declared.shape:
        raise ValueError("8x kernel has the wrong declared support")
    radius = int(metadata["rendering_profile"]["radius_native"])
    width = 16
    old_patches = None
    if old_record and "independent_4x_physical_patch" in old_record:
        old_patches = [v["patch_native"] for v in old_record["independent_4x_physical_patch"]["views"]]
    output = {"kernel_covariance_max_abs": float(np.abs(kernel-declared).max()), "views": []}
    for view in range(2):
        if old_patches is not None:
            start_y, _, start_x, _ = old_patches[view]
        else:
            sdf = np.abs(arrays["sdf"][view, 256:384, 256:384])
            yy, xx = np.indices(sdf.shape)
            chosen = np.unravel_index(np.argmin(sdf + 0.0001*((yy-64)**2+(xx-64)**2)), sdf.shape)
            start_y, start_x = 256+int(chosen[0])-width//2, 256+int(chosen[1])-width//2
        ax = (np.arange((width+2*radius)*RENDER_FACTOR, dtype=np.float64)+0.5)/RENDER_FACTOR
        x, y = ax[None, :]+start_x-radius, ax[:, None]+start_y-radius
        intensity, foreground = base.independent_intensity(x, y, metadata["shape_params"], metadata["photometry"], metadata["view_shift_xy"][view])
        formed = convolve(intensity, kernel, mode="same", method="fft")
        region = (slice(radius*RENDER_FACTOR, (radius+width)*RENDER_FACTOR),)*2
        projected = base.area_mean(formed[region], RENDER_FACTOR)
        target = base.area_mean(intensity[region], RENDER_FACTOR)
        actual = arrays["noiseless"][view, start_y:start_y+width, start_x:start_x+width]
        actual_target = arrays["target"][view, start_y:start_y+width, start_x:start_x+width]
        output["views"].append({"view": view, "patch_native": [start_y,start_y+width,start_x,start_x+width],
                                "noiseless_error": base.discrepancy_stats(projected-actual),
                                "target_error": base.discrepancy_stats(target-actual_target)})
    return output


def same_conditions(metadata: dict, old: dict) -> dict:
    exact_fields = ["scene_id", "index", "category", "seed", "effective_seed", "attempt", "shape_params",
                    "photometry", "polarity", "shift_xy", "view_shift_xy", "exact_delta_xy", "identity", "flat",
                    "noise_sigma_gray", "noise_variance_floor_gray", "quantization_step", "source_ancestors"]
    comparisons = {name: metadata.get(name) == old.get(name) for name in exact_fields}
    for name in ("sigma_native_xy", "rotation_rad", "radius_native"):
        comparisons["optics_"+name] = metadata["rendering_profile"].get(name) == old["rendering_profile"].get(name)
    comparisons["declared_noise_variance"] = metadata["profile"]["noise_variance"] == old["profile"]["noise_variance"]
    return {"all_physical_conditions_preserved": all(comparisons.values()), "fields": comparisons}


def audit_arrays(arrays: dict, metadata: dict, old_metadata: dict) -> tuple[dict, list[str]]:
    failures = []
    for name in ("source", "target", "noiseless", "sdf", "boundary", "latent_target"):
        shape = (2,2560,2560) if name == "latent_target" else (2,640,640)
        dtype = np.uint8 if name == "source" else np.float32
        if name not in arrays or arrays[name].shape != shape or arrays[name].dtype != dtype or not np.isfinite(arrays[name]).all():
            raise ValueError(f"invalid actual {name} shape/dtype/finite contract")
    conditions = same_conditions(metadata, old_metadata)
    if not conditions["all_physical_conditions_preserved"]:
        failures.append("v1_physical_conditions_or_noise_changed")
    if metadata.get("core_slice") != list(CORE):
        failures.append("native_core_or_context_changed")
    for name in ("target", "noiseless", "latent_target", "boundary"):
        if arrays[name].min() < -2e-7 or arrays[name].max() > 1+2e-7:
            failures.append(name+"_range_invalid")
    target_error = base.discrepancy_stats(base.area_mean(arrays["latent_target"], LATENT_FACTOR)-arrays["target"])
    if target_error["max_abs"] > base.LIMITS["target_area_max_abs"]:
        failures.append("native_target_does_not_equal_latent_area_mean")
    profile = metadata["profile"]
    if (profile.get("sampling_factor") != LATENT_FACTOR or profile.get("qualification") != "unqualified_diagnostic"
            or profile.get("kernel_convention") != "physical_psf" or profile.get("gain") != 1 or profile.get("bias") != 0):
        failures.append("invalid_or_qualified_simulation_profile")
    if metadata["rendering_profile"].get("sampling_factor") != RENDER_FACTOR:
        failures.append("renderer_is_not_independent8x")
    prediction = core_prediction(arrays["latent_target"], profile)
    mismatch = prediction-arrays["noiseless"][:,256:384,256:384]
    sigma = math.sqrt(float(profile["noise_variance"]))
    fits = [base.discrepancy_stats(mismatch[v],sigma) for v in range(2)]
    if not all(base.model_discrepancy_admissible(fit) for fit in fits):
        failures.append("4x_model_vs_8x_render_exceeds_unchanged_screen")
    actual_noise = float(metadata["noise_sigma_gray"])
    expected_variance = (max(actual_noise,0.5)**2+1/12)/255**2
    if actual_noise < 0 or not math.isclose(profile["noise_variance"],expected_variance,abs_tol=1e-15,rel_tol=1e-12):
        failures.append("noise_or_quantization_weight_formula_changed")
    identity, flat = metadata["identity"], metadata["flat"]
    if identity:
        if not np.array_equal(arrays["source"].astype(np.float32)/np.float32(255),arrays["target"]) or not np.array_equal(arrays["noiseless"],arrays["target"]):
            failures.append("identity_source_target_not_exact")
        if actual_noise != 0 or metadata["exact_delta_xy"] != [0,0] or profile["kernel"]["values"] != [[1.0]]:
            failures.append("identity_actual_noise_motion_optics_changed")
    geometry = []
    for v in range(2):
        sdf = arrays["sdf"][v,256:384,256:384]
        target = arrays["target"][v,256:384,256:384]
        boundary = arrays["boundary"][v,256:384,256:384]
        foreground = sdf > 0
        row = {"view":v,"foreground_fraction":float(foreground.mean()),"boundary_pixels":int((np.abs(sdf)<=1.5).sum()),
               "target_mean":float(target.mean()),"target_std":float(target.std()),"boundary_mean":float(boundary.mean()),
               "narrow_background_fraction":float(((sdf<=0)&(np.abs(sdf)<3)).mean())}
        inside,outside = sdf>2,sdf<-2
        if inside.any() and outside.any():
            row["inside_minus_outside_median"] = float(np.median(target[inside])-np.median(target[outside]))
            if row["inside_minus_outside_median"]*metadata["polarity"] <= 0:
                failures.append(f"view{v}_sdf_intensity_polarity_mismatch")
        if not flat and (not 0.04<=row["foreground_fraction"]<=0.94 or row["boundary_pixels"]<32):
            failures.append(f"view{v}_core_geometry_missing")
        if flat and (row["target_std"]>1e-6 or row["boundary_pixels"] or row["boundary_mean"]):
            failures.append(f"view{v}_flat_scene_not_flat")
        if metadata["category"] == "dense_close_structures" and row["narrow_background_fraction"]<0.01:
            failures.append(f"view{v}_dense_core_gap_missing")
        if not np.array_equal(boundary,(np.abs(sdf)<=1).astype(np.float32)):
            failures.append(f"view{v}_boundary_band_contract_mismatch")
        recorded = metadata["core_stats"][v]
        if recorded["boundary_pixels"] != row["boundary_pixels"] or recorded["foreground_fraction"] != row["foreground_fraction"]:
            failures.append(f"view{v}_recorded_core_statistics_wrong")
        geometry.append(row)
    if not np.allclose(np.diff(np.asarray(metadata["view_shift_xy"],dtype=float),axis=0)[0],metadata["exact_delta_xy"],atol=1e-12,rtol=0):
        failures.append("pair_motion_delta_inconsistent")
    motion = base.motion_diagnostic(arrays["target"],arrays["sdf"],metadata["exact_delta_xy"])
    if not flat and not identity and motion["target_expected_shift_rms"] >= motion["target_opposite_shift_rms"]:
        failures.append("pair_actual_motion_direction_disagrees")
    if (metadata.get("source_ancestors") != [metadata.get("parent_latent_id")]
            or not metadata.get("parent_latent_id","").startswith("r125_procedural_")
            or metadata.get("external_training_inputs") != [] or metadata.get("existing_test_answer_access") is not False):
        failures.append("new_procedural_only_ancestry_not_explicit")
    noise_error = arrays["source"][:,256:384,256:384].astype(float)/255-arrays["noiseless"][:,256:384,256:384]
    saturated = int(((arrays["source"][:,256:384,256:384]==0)|(arrays["source"][:,256:384,256:384]==255)).sum())
    if saturated:
        failures.append("supervised_core_sensor_saturation")
    return {"conditions_vs_v1":conditions,"target_area_integration":target_error,
            "operator_fit_all_core":base.discrepancy_stats(mismatch,sigma),"operator_fit_per_view":fits,
            "noise_and_quantization_residual":base.discrepancy_stats(noise_error,sigma),
            "actual_noise_sigma_gray":actual_noise,"profile_noise_variance":profile["noise_variance"],
            "geometry_actual_core":geometry,"identity_exact":bool(identity and not any(f.startswith("identity_") for f in failures)),
            "motion":motion},failures


def information_decomposition(arrays: dict, metadata: dict) -> dict:
    """Retained within4x-cell ambiguity, without changing the acquisition profile."""
    radius = int(metadata["rendering_profile"]["radius_native"])
    margin = radius+1
    latent = arrays["latent_target"][:,(256-margin)*4:(384+margin)*4,(256-margin)*4:(384+margin)*4]
    kernel = independent_kernel(metadata)
    repeated_result = []
    for x in latent:
        repeated = x.repeat(2,axis=0).repeat(2,axis=1).astype(np.float64)
        formed = convolve(repeated,kernel,mode="same",method="fft")
        integrated = base.area_mean(formed,8)
        repeated_result.append(integrated[margin:margin+128,margin:margin+128])
    repeated_result = np.stack(repeated_result)
    actual = arrays["noiseless"][:,256:384,256:384]
    prediction = core_prediction(arrays["latent_target"],metadata["profile"])
    sigma = math.sqrt(metadata["profile"]["noise_variance"])
    return {"physical8x_on_repeated4x_vs_true8x_basis_loss":base.discrepancy_stats(repeated_result-actual,sigma),
            "sampled4x_kernel_vs_exact_repeated_cell_operator":base.discrepancy_stats(prediction-repeated_result,sigma),
            "note":"Components may cancel. They are a diagnostic decomposition, not a replacement fitted profile or proof of identifiability."}


def audit_source_identity() -> dict:
    paths=[Path(__file__), ROOT/"scripts/audit_data_fit.py", ROOT/"config/data_admission_v2.json",
           ROOT/"data/generator_v2.py",base.R124/"model/observation.py",base.R124/"model/calibration.py"]
    return {str(path):base.sha256(path) for path in paths}


def evaluate_scene(entry: dict, package: Path, old_entries: dict, old_rows: dict) -> dict:
    """No admission is issued here. Retain exact hashes for later final binding."""
    row={"scene_id":entry["scene_id"],"category":entry["category"],"failures":[],"operator_device":OPERATOR_DEVICE}
    started=time.monotonic()
    try:
        ap=base.confined_path(package,entry["arrays_path"]);mp=base.confined_path(package,entry["metadata_path"])
        actual={"arrays":base.sha256(ap),"metadata":base.sha256(mp)}
        row["source_sha256"]=actual
        if "sha256" in entry and actual!=entry["sha256"]:
            row["failures"].append("package_hash_mismatch")
        metadata=base.read_json(mp)
        oe=old_entries[entry["scene_id"]]
        omp=base.confined_path(ROOT/"data/package",oe["metadata_path"])
        if base.sha256(omp)!=oe["sha256"]["metadata"]:
            row["failures"].append("v1_metadata_changed")
        with np.load(ap,allow_pickle=False) as saved:
            arrays={name:saved[name] for name in saved.files}
        result,errs=audit_arrays(arrays,metadata,base.read_json(omp))
        row.update(result);row["failures"].extend(errs)
        row["polarity"]=metadata["polarity"]
        row["source_ancestors"]=metadata["source_ancestors"]
        if entry["index"] in PHYSICAL_REPLAY_SCENES:
            row["independent8x_physical_replay"]=physical_replay(arrays,metadata,old_rows.get(entry["scene_id"]))
            for view in row["independent8x_physical_replay"]["views"]:
                if view["noiseless_error"]["max_abs"]>1e-4 or view["target_error"]["max_abs"]>1e-4:
                    row["failures"].append(f"independent8x_physical_patch_view{view['view']}_differs_materially")
        if entry["index"] in HARD_SCENES:
            row["retained_v1_failures"]=old_rows[entry["scene_id"]]["failures"]
            row["v1_operator_fit_per_view"]=old_rows[entry["scene_id"]]["operator_fit_per_view"]
            row["remaining_representation_decomposition"]=information_decomposition(arrays,metadata)
    except Exception as exc:
        row["failures"].append(type(exc).__name__+": "+str(exc))
    row["audit_source_sha256"]=audit_source_identity()
    row["elapsed_seconds"]=time.monotonic()-started
    return row


def incremental_audit(package: Path, cache_dir: Path, watch: bool = False) -> None:
    """Audit completed files while generation proceeds; never issue early admission."""
    old_manifest=base.read_json(ROOT/"data/package/manifest.json")
    old_entries={r["scene_id"]:r for r in old_manifest["scenes"]}
    old_report=base.read_json(ROOT/"results/data_audit_v1.json")
    old_rows={r["scene_id"]:r for r in old_report["scenes"]}
    source_identity=audit_source_identity()
    cache_dir.mkdir(parents=True,exist_ok=True)
    while True:
        complete=0
        for old in old_manifest["scenes"]:
            cache_path=cache_dir/(old["scene_id"]+".json")
            if cache_path.exists():
                cached=base.read_json(cache_path)
                if cached.get("audit_source_sha256")!=source_identity:
                    raise ValueError("cached audit has a different source identity; preserve it and use a new cache directory")
                complete+=1
                continue
            ap=package/old["arrays_path"];mp=package/old["metadata_path"]
            if not ap.is_file() or not mp.is_file():continue
            metadata=base.read_json(mp)
            entry={"scene_id":metadata["scene_id"],"index":metadata["index"],"category":metadata["category"],
                   "arrays_path":old["arrays_path"],"metadata_path":old["metadata_path"]}
            row=evaluate_scene(entry,package,old_entries,old_rows)
            with cache_path.open("x",encoding="utf-8") as stream:stream.write(json.dumps(row,indent=2,allow_nan=False))
            complete+=1
            print(json.dumps({"cached":complete,"scene":row["scene_id"],"failures":row["failures"],"seconds":row["elapsed_seconds"],"pilot_admission":"not_issued_pending_final_manifest"}),flush=True)
        if complete==64 or not watch:break
        time.sleep(5)
    print(json.dumps({"status":"per_scene_audit_finished" if complete==64 else "partial_audit", "scenes":complete,"pilot_admitted":False,"reason":"Final manifest-bound aggregation still required"}),flush=True)


def audit_package(manifest_path: Path, output: Path, limit: int = 0, cache_dir: Path | None = None):
    if output.exists():
        raise FileExistsError("preserve previous audit: "+str(output))
    torch.set_num_threads(2)
    started = time.monotonic()
    package = manifest_path.parent
    manifest = base.read_json(manifest_path)
    old_report = base.read_json(ROOT/"results/data_audit_v1.json")
    old_rows = {r["scene_id"]:r for r in old_report["scenes"]}
    old_package = ROOT/"data/package"
    old_manifest = base.read_json(old_package/"manifest.json")
    old_entries = {r["scene_id"]:r for r in old_manifest["scenes"]}
    protected = [ROOT/p for p in ("data/generator.py","data/package/manifest.json","config/data_admission.json",
                                  "scripts/audit_data_fit.py","results/data_audit_v1.json",
                                  "results/data_audit_representation_decomposition.json","results/data_audit_scene007_precision_diagnosis.json")]
    protected += [base.R124/"model/observation.py",base.R124/"model/calibration.py"]
    before = {str(path):base.sha256(path) for path in protected}
    rows = manifest["scenes"]
    selected = rows[:limit or None]
    failures = []
    if len(rows)!=64 or manifest.get("scene_count")!=64 or [r["scene_id"] for r in rows]!=[r["scene_id"] for r in old_manifest["scenes"]]:
        failures.append("64_original_scene_slots_not_retained")
    source_path = Path(manifest.get("generator_path",""))
    if source_path.resolve() != (ROOT/"data/generator_v2.py").resolve():
        failures.append("unexpected_v2_generator_path")
    generator_hash = base.sha256(source_path)
    if generator_hash!=manifest.get("generator_sha256"):
        failures.append("v2_generator_changed_since_generation")
    report = {"schema_version":2,"utc":datetime.now(timezone.utc).isoformat(),"manifest_path":str(manifest_path.resolve()),
              "manifest_sha256":base.sha256(manifest_path),"source_generator_sha256":generator_hash,
              "data_admission_contract_sha256":base.sha256(ROOT/"config/data_admission_v2.json"),
              "unchanged_limits":base.LIMITS,"latent_factor":4,"independent_render_factor":8,
              "scope":"known-simulation bounded pipeline only","real_calibration_qualified":False,
              "real_usefulness_established":False,"v1_admission_remains":old_report["pilot_admitted"],
              "scenes":[],"global_failures":failures}
    ancestors=[]
    for count,entry in enumerate(selected,1):
        cache_path=cache_dir/(entry["scene_id"]+".json") if cache_dir else None
        if cache_path and cache_path.exists():
            row=base.read_json(cache_path)
            if row.get("audit_source_sha256")!=audit_source_identity():
                row["failures"].append("cached_audit_source_mismatch")
            current={"arrays":base.sha256(base.confined_path(package,entry["arrays_path"])),
                     "metadata":base.sha256(base.confined_path(package,entry["metadata_path"]))}
            if row.get("source_sha256")!=entry["sha256"] or current!=entry["sha256"]:
                row["failures"].append("cached_scene_not_bound_to_final_manifest")
            row["cached_result_revalidated_against_final_manifest"]=True
        else:
            row=evaluate_scene(entry,package,old_entries,old_rows)
        ancestors.extend(row.get("source_ancestors",[]))
        report["scenes"].append(row)
        print(json.dumps({"audited":count,"total":len(selected),"scene":row["scene_id"],"failures":row["failures"],"seconds":round(time.monotonic()-started,2)}),flush=True)
    report["protected_v1_and_R124_hashes"]=before
    report["protected_sources_unchanged"]=all(base.sha256(Path(p))==h for p,h in before.items())
    if not report["protected_sources_unchanged"]:failures.append("protected_v1_or_R124_source_changed")
    if len(ancestors)!=len(set(ancestors)):failures.append("duplicate_procedural_ancestor")
    report["source_review"]={"generator":base.generator_source_review(source_path),
                             "assessment":"Continuous Float64 object/texture coordinates precede the fixed8x pair optics, integration, sensor noise and quantization; no old image or teacher input.",
                             "qualification":"mathematical simulation only, not real optics"}
    report["scene_failure_counts"]=dict(Counter(f for row in report["scenes"] for f in row["failures"]))
    report["hardcase_before_after"]=[{k:r[k] for k in ("scene_id","failures","retained_v1_failures","v1_operator_fit_per_view","operator_fit_per_view","remaining_representation_decomposition") if k in r} for r in report["scenes"] if r["scene_id"] in {f"scene_{i:03d}" for i in HARD_SCENES}]
    strata=defaultdict(list)
    for row in report["scenes"]:
        if "operator_fit_per_view" not in row:continue
        key=row["category"]+"|polarity="+str(row["polarity"])
        if "flat" in row["category"]:key+="|"+("bright" if row["geometry_actual_core"][0]["target_mean"]>=0.5 else "dark")
        strata[key].append(row)
    report["strata"]={k:{"scenes":len(rs),"worst_rms_gray":max(v["rms_gray"] for r in rs for v in r["operator_fit_per_view"]),
                          "worst_rms_over_sigma":max(v["rms_over_declared_sigma"] for r in rs for v in r["operator_fit_per_view"]),
                          "worst_p99_over_sigma":max(v["p99_abs_over_declared_sigma"] for r in rs for v in r["operator_fit_per_view"])} for k,rs in strata.items()}
    report["pilot_admitted"]=not failures and not report["scene_failure_counts"] and len(selected)==len(rows)==64
    report["elapsed_seconds"]=time.monotonic()-started
    output.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(report,indent=2,allow_nan=False)
    with output.open("x",encoding="utf-8") as stream:stream.write(encoded)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",type=Path)
    parser.add_argument("--output",type=Path,default=ROOT/"results/data_audit_v2.json")
    parser.add_argument("--limit",type=int,default=0)
    parser.add_argument("--device",choices=("cpu","cuda"),default="cpu")
    parser.add_argument("--incremental",action="store_true")
    parser.add_argument("--package",type=Path)
    parser.add_argument("--watch",action="store_true")
    parser.add_argument("--cache-dir",type=Path)
    args=parser.parse_args()
    OPERATOR_DEVICE=args.device
    torch.set_num_threads(2)
    if OPERATOR_DEVICE=="cuda":
        if not torch.cuda.is_available():raise RuntimeError("CUDA audit requested but unavailable")
        torch.backends.cudnn.allow_tf32=False
        torch.backends.cuda.matmul.allow_tf32=False
        torch.backends.cudnn.benchmark=False
    if args.incremental:
        if not args.package or not args.cache_dir:parser.error("incremental audit needs --package and --cache-dir")
        incremental_audit(args.package,args.cache_dir,args.watch)
        raise SystemExit(0)
    if not args.manifest:parser.error("final aggregation needs --manifest")
    result=audit_package(args.manifest,args.output,args.limit,args.cache_dir)
    print(json.dumps({"output":str(args.output),"pilot_admitted":result["pilot_admitted"],"failures":result["scene_failure_counts"]}))
    raise SystemExit(0 if result["pilot_admitted"] else 2)
