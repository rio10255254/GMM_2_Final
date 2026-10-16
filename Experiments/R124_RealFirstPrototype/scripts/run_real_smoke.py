"""Untrained engineering previews on six already-used real microscope images.

No training, checkpoint loading, performance judgement, or confirmation-set access.
The two observation profiles are assumptions, not qualified instrument calibration.
An output directory must be new; source images are read-only and hash-checked again.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


EXPERIMENT = Path(__file__).resolve().parents[1]
PROJECT = EXPERIMENT.parents[1]
SEED = 1245001
PROFILE_FILES = {
    "identity_assumption": EXPERIMENT / "config" / "identity_diagnostic.json",
    "gaussian_assumption": EXPERIMENT / "config" / "gaussian_diagnostic.json",
}
R69_INPUTS = PROJECT / "Experiments" / "R69_ACMContourSEMValidation" / "inputs" / "sem_paired_50x_exposure_stack"
R119_INPUTS = PROJECT / "Experiments" / "R119_SequenceGeometryValidation" / "validation" / "inputs" / "Raw"
SOURCES = [
    ("sem_optical_exposure13", R69_INPUTS / "13.bmp", "SEM-paired optical exposure 13; historical magnification unverified"),
    ("sem_optical_exposure24", R69_INPUTS / "24.bmp", "SEM-paired optical exposure 24; historical magnification unverified"),
    ("5x_dense", R119_INPUTS / "5x_dense_raw.bmp", "Locked 5x dense-structure development preview"),
    ("20x_mixed", R119_INPUTS / "20x_mixed_raw.bmp", "Locked 20x mixed-structure development preview"),
    ("50x_array", R119_INPUTS / "50x_array_raw.bmp", "Locked 50x array development preview"),
    ("pillar_center9_50x", R119_INPUTS / "pillar_center9_50x_raw.bmp", "Locked 50x center-nine development preview"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def json_value(value: Any) -> Any:
    import torch

    if isinstance(value, torch.Tensor):
        data = value.detach().cpu().numpy()
        return {"tensor_shape": list(data.shape), "dtype": str(data.dtype)}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: json_value(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, float, int, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported metadata type: {type(value).__name__}")


def export_tensors(value: Any, prefix: str, arrays: dict[str, np.ndarray]) -> Any:
    """Store each tensor, retaining structure separately rather than flattening semantics."""
    import torch

    if isinstance(value, torch.Tensor):
        data = value.detach().cpu().numpy()
        if not np.isfinite(data).all():
            raise ValueError(f"Nonfinite trace tensor: {prefix}")
        arrays[prefix] = data
        return {"npz_key": prefix, "shape": list(data.shape), "dtype": str(data.dtype)}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: export_tensors(getattr(value, field.name), f"{prefix}__{field.name}", arrays)
                for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key): export_tensors(item, f"{prefix}__{key}", arrays) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [export_tensors(item, f"{prefix}__{index:02d}", arrays) for index, item in enumerate(value)]
    return json_value(value)


def read_raw(path: Path) -> tuple[np.ndarray, str]:
    with Image.open(path) as source:
        mode = source.mode
        if mode == "P":
            rgb = np.asarray(source.convert("RGB"))
            if not (np.array_equal(rgb[..., 0], rgb[..., 1]) and np.array_equal(rgb[..., 0], rgb[..., 2])):
                raise ValueError(f"Non-gray palette would require an undeclared color conversion: {path}")
            pixels = rgb[..., 0].copy()
        else:
            pixels = np.asarray(source).copy()
    if pixels.ndim != 2 or pixels.dtype != np.uint8:
        raise ValueError(f"Expected native 8-bit grayscale input: {path}; {pixels.shape}, {pixels.dtype}")
    if min(pixels.shape) < 128:
        raise ValueError(f"Fixed center128 trace requires both dimensions >= 128: {path}")
    return pixels, mode


def crop_box(shape: tuple[int, int], size: int) -> tuple[int, int, int, int]:
    height, width = shape
    side = min(size, height, width)
    y0, x0 = (height - side) // 2, (width - side) // 2
    return y0, y0 + side, x0, x0 + side


def assert_unqualified(metadata: dict[str, Any]) -> None:
    if metadata.get("observation_qualification") != "unqualified_diagnostic":
        raise ValueError("Expected observation_qualification='unqualified_diagnostic'")
    for flag in ("calibration_qualified", "uncertainty_calibrated"):
        if metadata.get(flag) is not False:
            raise ValueError(f"Diagnostic preview requires {flag}=False")


def assert_no_qualified_profile(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"calibration_qualified", "uncertainty_calibrated", "instrument_calibrated", "qualified"} and item is True:
                raise ValueError(f"Qualified calibration is outside this engineering preview: {key}")
            assert_no_qualified_profile(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_qualified_profile(item)


def synchronize(device: Any) -> None:
    import torch

    if device.type == "cuda":
        torch.cuda.synchronize(device)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New output directory; existing directories are refused")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--limit", type=int, default=None, help="Use the first N sources (1..6), preserving the fixed ordering")
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= len(SOURCES):
        parser.error("--limit must be between 1 and 6")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protected: list[dict[str, Any]] = []
    try:
        import torch
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sys.path.insert(0, str(EXPERIMENT))
        from model.calibration import load_observation
        from model.network import build_model
        from inference.tiling import tiled_forward

        chosen = SOURCES if args.limit is None else SOURCES[:args.limit]
        device_name = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
        if device_name == "auto":
            device_name = "cpu"
        if device_name == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA explicitly requested but unavailable")
        device = torch.device(device_name)
        torch.set_num_threads(min(8, torch.get_num_threads()))
        np.random.seed(SEED)
        if device.type == "cuda":
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True

        protected = [record_file(path) for _, path, _ in chosen]
        protected += [record_file(path) for path in PROFILE_FILES.values()]
        code_sources = sorted(path for directory in ("model", "inference")
                              for path in (EXPERIMENT / directory).glob("*.py"))
        protected += [record_file(path) for path in code_sources]
        protected.append(record_file(Path(__file__)))
        write_json(output / "protected_inputs_before.json", protected)
        profiles = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in PROFILE_FILES.items()}
        for profile in profiles.values():
            assert_no_qualified_profile(profile)
        write_json(output / "run_contract.json", {
            "started_utc": utc_now(), "seed": SEED, "device": str(device),
            "network_untrained": True, "checkpoint_loaded": False, "training_performed": False,
            "calibration_qualified": False, "uncertainty_calibrated": False, "efficacy_evaluated": False,
            "scope": "Already-used real images; engineering execution and modification preview only",
            "not_a_holdout": True, "sources": [name for name, _, _ in chosen],
            "profiles": profiles, "tile_core": 256, "tile_origin": [0, 0],
            "trace_rule": "One center128 crop from first fixed source (SEM optical exposure13), all four stages, each profile",
            "display_rule": "Same centered crop per source, grayscale range 0..255; clipping only in PNG/figure display",
            "python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__,
        })

        rows: list[dict[str, Any]] = []
        display: dict[str, dict[str, np.ndarray]] = {}
        trace_written: list[str] = []
        for profile_name, profile_path in PROFILE_FILES.items():
            torch.manual_seed(SEED)
            if device.type == "cuda":
                torch.cuda.manual_seed_all(SEED)
            observation = load_observation(profile_path, device=str(device))
            model = build_model(config=None, observation=observation).to(device).eval()
            halo = int(model.required_halo)
            for source_index, (source_name, source_path, description) in enumerate(chosen):
                raw_u8, source_mode = read_raw(source_path)
                raw_np = raw_u8.astype(np.float32) / np.float32(255.0)
                raw = torch.from_numpy(raw_np)[None, None].to(device)
                synchronize(device)
                started = time.perf_counter()
                with torch.inference_mode():
                    native = tiled_forward(model, raw, core=256, halo=halo, origin=(0, 0))
                synchronize(device)
                elapsed = time.perf_counter() - started
                if not isinstance(native, torch.Tensor) or native.shape != raw.shape:
                    raise ValueError(f"Native output shape changed for {profile_name}/{source_name}")
                native_np = native[0, 0].detach().cpu().numpy().astype(np.float32, copy=False)
                if not np.isfinite(native_np).all():
                    raise ValueError(f"Nonfinite native output: {profile_name}/{source_name}")
                case_dir = output / source_name / profile_name
                case_dir.mkdir(parents=True, exist_ok=False)
                np.savez_compressed(case_dir / "output_float.npz", output=native_np)
                shown = np.rint(np.clip(native_np, 0, 1) * 255).astype(np.uint8)
                Image.fromarray(shown).save(case_dir / "output_uint8.png")
                delta_gray = (native_np - raw_np) * 255.0
                row = {
                    "source_name": source_name, "description": description, "source": record_file(source_path),
                    "source_pil_mode": source_mode, "input_interpretation": "Native grayscale / 255; no contrast normalization",
                    "profile_name": profile_name, "profile": record_file(profile_path), "profile_contents": profiles[profile_name],
                    "network_untrained": True, "seed": SEED, "checkpoint_loaded": False,
                    "calibration_qualified": False, "uncertainty_calibrated": False, "efficacy_evaluated": False,
                    "shape_hw": list(raw_np.shape), "seconds": elapsed, "device": str(device),
                    "tile_core": 256, "tile_halo": halo, "tile_origin": [0, 0],
                    "output_min": float(native_np.min()), "output_max": float(native_np.max()),
                    "display_clipped_pixels": int(((native_np < 0) | (native_np > 1)).sum()),
                    "modification_only": {
                        "mean_absolute_gray_change": float(np.abs(delta_gray).mean()),
                        "p95_absolute_gray_change": float(np.percentile(np.abs(delta_gray), 95)),
                        "max_absolute_gray_change": float(np.abs(delta_gray).max()),
                        "fraction_changed_over_half_gray": float((np.abs(delta_gray) > 0.5).mean()),
                    },
                }
                write_json(case_dir / "metadata.json", row)
                rows.append(row)
                box = crop_box(raw_np.shape, 256)
                y0, y1, x0, x1 = box
                display.setdefault(source_name, {"raw": raw_np[y0:y1, x0:x1].copy()})[profile_name] = native_np[y0:y1, x0:x1].copy()

                if source_index == 0:
                    ty0, ty1, tx0, tx1 = crop_box(raw_np.shape, 128)
                    trace_input = raw[..., ty0:ty1, tx0:tx1].contiguous()
                    with torch.inference_mode():
                        detail = model.forward_details(trace_input, trace=True)
                    if len(detail.traces) != 4:
                        raise ValueError(f"Expected all four trace stages, received {len(detail.traces)}")
                    expected_trace_keys = {
                        "state_before", "observation_before", "residual_before", "prior_correction", "proposal",
                        "observation_at_proposal", "observation_correction", "state_after", "native_output",
                        "step_size", "projection_correction",
                    }
                    for stage_index, stage in enumerate(detail.traces):
                        missing = expected_trace_keys.difference(stage)
                        if missing:
                            raise ValueError(f"Incomplete trace stage {stage_index}: {sorted(missing)}")
                        if any(not isinstance(stage[key], torch.Tensor) for key in expected_trace_keys):
                            raise TypeError(f"Expected tensors for all declared trace fields at stage {stage_index}")
                    detail_metadata = json_value(detail.metadata)
                    assert_unqualified(detail_metadata)
                    arrays = {"input_native": trace_input.detach().cpu().numpy()}
                    structure = {key: export_tensors(getattr(detail, key), key, arrays)
                                 for key in ("output", "latent", "geometry", "traces")}
                    trace_dir = output / "center128_trace" / profile_name
                    trace_dir.mkdir(parents=True, exist_ok=False)
                    np.savez_compressed(trace_dir / "four_stages.npz", **arrays)
                    write_json(trace_dir / "metadata.json", {
                        "source": record_file(source_path), "crop_y0_y1_x0_x1": [ty0, ty1, tx0, tx1],
                        "rule": "Fixed standalone center128 crop; not asserted identical to the corresponding whole-image crop",
                        "network_untrained": True, "profile": profiles[profile_name], "model_metadata": detail_metadata,
                        "stage_count": 4, "tensor_count": len(arrays), "structure": structure,
                    })
                    trace_written.append(profile_name)
                print(f"{profile_name} / {source_name}: saved untrained preview in {elapsed:.3f}s", flush=True)

        figure, axes = plt.subplots(len(chosen), 3, figsize=(12, 3.6 * len(chosen)), squeeze=False)
        for index, (source_name, _, _) in enumerate(chosen):
            for column, (key, title) in enumerate((("raw", "Raw"), ("identity_assumption", "Identity observation assumption"),
                                                 ("gaussian_assumption", "Assumed Gaussian observation"))):
                axes[index, column].imshow(display[source_name][key], cmap="gray", vmin=0, vmax=1)
                axes[index, column].set_title(f"{source_name}\n{title}", fontsize=10)
                axes[index, column].axis("off")
        figure.suptitle("UNTRAINED engineering previews — no qualified instrument calibration\nSame centered crops and display range; no quality or accuracy claim", fontsize=13)
        figure.tight_layout(rect=(0, 0, 1, 0.95))
        figure.savefig(output / "untrained_real_previews.png", dpi=150)
        plt.close(figure)

        rechecked = [dict(item, after_sha256=sha256(Path(item["path"]))) for item in protected]
        unchanged = all(item["sha256"] == item["after_sha256"] for item in rechecked)
        write_json(output / "protected_inputs_after.json", {"unchanged": unchanged, "files": rechecked})
        if not unchanged:
            raise RuntimeError("A protected input or implementation file changed during execution")
        write_json(output / "summary.json", {
            "status": "untrained_engineering_preview_complete", "completed_utc": utc_now(),
            "source_count": len(chosen), "profile_count": len(PROFILE_FILES), "output_count": len(rows),
            "trace_profiles": trace_written, "network_untrained": True, "calibration_qualified": False,
            "uncertainty_calibrated": False, "efficacy_evaluated": False, "protected_inputs_unchanged": unchanged,
            "interpretation": "Execution and image modifications only; no demonstrated reconstruction or measurement benefit",
            "outputs": rows,
        })
        print(f"Saved {len(rows)} untrained engineering previews: {output}", flush=True)
    except BaseException as error:
        failure = {"status": "failed", "utc": utc_now(), "error_type": type(error).__name__, "error": str(error),
                   "traceback": traceback.format_exc(), "network_untrained": True, "efficacy_evaluated": False}
        if not (output / "failure.json").exists():
            write_json(output / "failure.json", failure)
        raise


if __name__ == "__main__":
    main()
