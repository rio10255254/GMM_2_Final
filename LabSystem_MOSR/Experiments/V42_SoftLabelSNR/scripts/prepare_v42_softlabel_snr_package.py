"""Prepare a reversible V42 soft-label/SNR experiment package.

The package is derived from the thesis-facing V41 standalone data. Source
images and geometry sidecars are copied as-is; only label images are softened
inside a narrow edge band so the network is not trained on purely stair-step
pixel contours.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
DEFAULT_SOURCE_PROFILE = "r62_target_sample_boost_v13_measurement_view_safe_teacher"
DEFAULT_OUTPUT_PROFILE = "r62_target_sample_boost_v14_softlabel_snr_smoke"


def _as_uint8(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.uint8:
        return arr
    arr_f = arr.astype(np.float32)
    if arr_f.max(initial=0.0) <= 1.5:
        arr_f = arr_f * 255.0
    return np.clip(np.rint(arr_f), 0, 255).astype(np.uint8)


def _edge_band(arr: np.ndarray, edge_band_px: int, threshold: float = 2.0) -> np.ndarray:
    arr_f = arr.astype(np.float32)
    gx = np.zeros_like(arr_f)
    gy = np.zeros_like(arr_f)
    gx[:, 1:] = np.abs(arr_f[:, 1:] - arr_f[:, :-1])
    gy[1:, :] = np.abs(arr_f[1:, :] - arr_f[:-1, :])
    edge = ((gx + gy) > float(threshold)).astype(np.uint8) * 255
    radius = max(1, int(edge_band_px))
    size = radius * 2 + 1
    return np.array(Image.fromarray(edge, mode="L").filter(ImageFilter.MaxFilter(size))) > 0


def soften_label_array(
    label: np.ndarray,
    *,
    sigma: float = 0.75,
    edge_band_px: int = 2,
    blend: float = 1.0,
) -> np.ndarray:
    src = _as_uint8(label)
    band = _edge_band(src, edge_band_px=edge_band_px)
    blurred = np.array(
        Image.fromarray(src, mode="L").filter(ImageFilter.GaussianBlur(radius=float(sigma))),
        dtype=np.float32,
    )
    src_f = src.astype(np.float32)
    alpha = np.clip(float(blend), 0.0, 1.0)
    out = src_f.copy()
    out[band] = src_f[band] * (1.0 - alpha) + blurred[band] * alpha
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def edge_softness_score(label: np.ndarray) -> float:
    arr = _as_uint8(label)
    band = _edge_band(arr, edge_band_px=1)
    if not np.any(band):
        return 0.0
    edge_values = arr[band]
    return float(np.mean((edge_values > 3) & (edge_values < 252)))


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _load_gray(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("L"), dtype=np.uint8)


def _select_pairs(pairs: list[dict[str, Any]], max_per_role: int) -> list[dict[str, Any]]:
    if max_per_role <= 0:
        return list(pairs)
    seen: dict[str, int] = defaultdict(int)
    selected: list[dict[str, Any]] = []
    for pair in pairs:
        role = str(pair.get("role", "unknown"))
        if seen[role] >= max_per_role:
            continue
        selected.append(pair)
        seen[role] += 1
    return selected


def prepare_package(
    *,
    data_root: Path = DEFAULT_DATA_ROOT,
    source_profile: str = DEFAULT_SOURCE_PROFILE,
    output_profile: str = DEFAULT_OUTPUT_PROFILE,
    max_per_role: int = 12,
    sigma: float = 0.75,
    edge_band_px: int = 2,
    blend: float = 1.0,
    overwrite: bool = False,
) -> Path:
    source_dir = Path(data_root) / source_profile
    output_dir = Path(data_root) / output_profile
    manifest_path = source_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"source manifest not found: {manifest_path}")
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"output package already exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = _select_pairs(list(manifest.get("pairs", [])), max_per_role=max_per_role)
    new_pairs: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []

    for idx, pair in enumerate(selected):
        src_rel = Path(str(pair["package_src"]))
        lbl_rel = Path(str(pair["package_lbl"]))
        old_src = source_dir / src_rel
        old_lbl = source_dir / lbl_rel
        new_src = output_dir / src_rel
        new_lbl = output_dir / lbl_rel
        _copy_file(old_src, new_src)

        label = _load_gray(old_lbl)
        soft = soften_label_array(label, sigma=sigma, edge_band_px=edge_band_px, blend=blend)
        new_lbl.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(soft, mode="L").save(new_lbl)

        item = dict(pair)
        item["source_profile"] = source_profile
        item["source_index"] = pair.get("source_index", idx)
        item["src"] = str(new_src)
        item["lbl"] = str(new_lbl)
        item["package_src"] = str(src_rel).replace("\\", "/")
        item["package_lbl"] = str(lbl_rel).replace("\\", "/")
        item["soft_label_from_package_lbl"] = str(lbl_rel).replace("\\", "/")
        item["soft_label_sigma"] = float(sigma)
        item["soft_label_edge_band_px"] = int(edge_band_px)
        item["soft_label_blend"] = float(blend)

        for key, rel in list(item.items()):
            if not isinstance(rel, str) or not rel:
                continue
            if not (key.startswith("geometry_") or key.endswith("_meta") or rel.replace("\\", "/").startswith("geom/")):
                continue
            geom_rel = Path(str(rel))
            old_geom = source_dir / geom_rel
            if old_geom.is_file():
                _copy_file(old_geom, output_dir / geom_rel)

        before = edge_softness_score(label)
        after = edge_softness_score(soft)
        item["soft_label_edge_softness_before"] = before
        item["soft_label_edge_softness_after"] = after
        new_pairs.append(item)
        metrics.append(
            {
                "index": idx,
                "role": item.get("role", "unknown"),
                "package_lbl": item["package_lbl"],
                "edge_softness_before": before,
                "edge_softness_after": after,
            }
        )

    role_counts = Counter(str(p.get("role", "unknown")) for p in new_pairs)
    polarity_counts = Counter(str(p.get("polarity", "unknown")) for p in new_pairs)
    shape_family_counts = Counter(str(p.get("shape_family", "unknown")) for p in new_pairs)
    new_manifest = {
        "profile": output_profile,
        "source_profile": source_profile,
        "r61_universal_boundary_training": True,
        "r62_target_sample_boost": bool(manifest.get("r62_target_sample_boost", True)),
        "anti_answer_leakage_design": True,
        "v42_softlabel_snr_experiment": True,
        "label_change": "edge_band_antialiasing_only",
        "snr_branch_expected": True,
        "total_pairs": len(new_pairs),
        "role_counts": dict(sorted(role_counts.items())),
        "polarity_counts": dict(sorted(polarity_counts.items())),
        "shape_family_counts": dict(sorted(shape_family_counts.items())),
        "crop_size": manifest.get("crop_size", 256),
        "geometry_sidecars": bool(manifest.get("geometry_sidecars", True)),
        "geometry_count": len(new_pairs),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "soft_label": {
            "sigma": float(sigma),
            "edge_band_px": int(edge_band_px),
            "blend": float(blend),
            "max_per_role": int(max_per_role),
        },
        "pairs": new_pairs,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(new_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "soft_label_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "clean_package_summary.json").write_text(
        json.dumps(
            {
                "profile": output_profile,
                "source_profile": source_profile,
                "total_pairs": len(new_pairs),
                "role_counts": dict(sorted(role_counts.items())),
                "mean_edge_softness_before": float(np.mean([m["edge_softness_before"] for m in metrics])) if metrics else 0.0,
                "mean_edge_softness_after": float(np.mean([m["edge_softness_after"] for m in metrics])) if metrics else 0.0,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output_dir


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare V42 soft-label/SNR experiment package")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--source-profile", default=DEFAULT_SOURCE_PROFILE)
    parser.add_argument("--output-profile", default=DEFAULT_OUTPUT_PROFILE)
    parser.add_argument("--max-per-role", type=int, default=12, help="0 means copy all pairs")
    parser.add_argument("--sigma", type=float, default=0.75)
    parser.add_argument("--edge-band-px", type=int, default=2)
    parser.add_argument("--blend", type=float, default=1.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    output_dir = prepare_package(
        data_root=args.data_root,
        source_profile=args.source_profile,
        output_profile=args.output_profile,
        max_per_role=args.max_per_role,
        sigma=args.sigma,
        edge_band_px=args.edge_band_px,
        blend=args.blend,
        overwrite=args.overwrite,
    )
    print(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
