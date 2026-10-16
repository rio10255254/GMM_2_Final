"""Build the R54 masked small-overfit package.

R54 uses the 20260613 strict-rectangle CAD references only inside their
reliable masks. Outside the reliable mask, the label is kept identical to the
real source image so the probe does not train on guessed full-frame GT.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = Path(__file__).resolve().parents[2]
R48_SCRIPT_DIR = EXPERIMENTS_ROOT / "R48_RealCornerTransfer" / "scripts"
if str(R48_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R48_SCRIPT_DIR))

from r48_real_corner_data import compute_geometry_from_label  # noqa: E402


PROFILE_NAME = "r54_masked_small_overfit_train"
STAGE_NAME = "stage_58_r54_masked_real_cad_probe"
DEFAULT_SELECTED_CSV = (
    EXPERIMENT_ROOT
    / "results"
    / "root_cause_probe"
    / "r54_small_overfit_probe_pairs.csv"
)
DEFAULT_OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r54_geometry_root_cause_probe"
DEFAULT_PACKAGE_DIR = DEFAULT_OUTPUT_ROOT / PROFILE_NAME
DEFAULT_PREVIEW_PATH = EXPERIMENT_ROOT / "results" / "masked_overfit_probe" / "r54_masked_overfit_preview.png"

LABEL_POLICY = "label equals CAD GT inside reliable_mask plus CAD edge band; label equals source outside supervision mask"
GEOMETRY_POLICY = "geometry sidecars are computed from CAD GT inside the same supervision mask"


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _safe_remove_tree(path: Path, root: Path | None = None) -> None:
    resolved = path.resolve()
    root_resolved = (root or path.parent).resolve()
    if not str(resolved).lower().startswith(str(root_resolved).lower()):
        raise ValueError(f"refusing to remove outside root: {resolved}")
    if resolved == root_resolved:
        raise ValueError(f"refusing to remove root itself: {resolved}")
    if len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
    shutil.rmtree(resolved)


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"failed to read image: {path}")
    return image


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _crop_patch(image: np.ndarray, x0: int, y0: int, size: int) -> np.ndarray:
    return image[y0 : y0 + size, x0 : x0 + size]


def make_masked_label(src_patch: np.ndarray, gt_patch: np.ndarray, mask_patch: np.ndarray) -> np.ndarray:
    if src_patch.shape != gt_patch.shape or src_patch.shape != mask_patch.shape:
        raise ValueError(
            f"shape mismatch: src={src_patch.shape}, gt={gt_patch.shape}, mask={mask_patch.shape}"
        )
    label = src_patch.copy()
    trusted = mask_patch > 0
    label[trusted] = gt_patch[trusted]
    return label


def build_supervision_mask(reliable_mask: np.ndarray, guide: np.ndarray, *, edge_band_radius: int = 5) -> np.ndarray:
    if reliable_mask.shape != guide.shape:
        raise ValueError(f"shape mismatch: reliable_mask={reliable_mask.shape}, guide={guide.shape}")
    supervision = (reliable_mask > 0).astype(np.uint8) * 255
    radius = max(0, int(edge_band_radius))
    if radius > 0:
        edges = cv2.Canny(guide.astype(np.uint8), 40, 120)
        kernel_size = radius * 2 + 1
        edge_band = cv2.dilate(edges, np.ones((kernel_size, kernel_size), dtype=np.uint8), iterations=1)
        supervision[edge_band > 0] = 255
    return supervision


def _geometry_input_from_masked_gt(gt_patch: np.ndarray, mask_patch: np.ndarray) -> np.ndarray:
    geom = np.zeros_like(gt_patch)
    geom[mask_patch > 0] = gt_patch[mask_patch > 0]
    return geom


def _write_geometry_sidecars(
    gt_patch: np.ndarray,
    mask_patch: np.ndarray,
    geom_dir: Path,
    rel_path: Path,
) -> dict[str, str]:
    boundary, centerline, distance = compute_geometry_from_label(_geometry_input_from_masked_gt(gt_patch, mask_patch))
    boundary_rel = Path("geom") / "boundary" / rel_path
    centerline_rel = Path("geom") / "centerline" / rel_path
    distance_rel = Path("geom") / "distance" / rel_path.with_suffix(".npy")
    _write_image(geom_dir.parent / boundary_rel, boundary)
    _write_image(geom_dir.parent / centerline_rel, centerline)
    distance_path = geom_dir.parent / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
    }


def _patch_trusted_ratio(mask: np.ndarray, x0: int, y0: int, size: int) -> float:
    patch = _crop_patch(mask, x0, y0, size)
    return float(np.count_nonzero(patch > 0)) / float(size * size)


def _edge_map_from_guide(guide: np.ndarray | None, mask: np.ndarray) -> np.ndarray:
    if guide is None:
        return np.zeros_like(mask, dtype=np.uint8)
    if guide.shape != mask.shape:
        raise ValueError(f"guide shape mismatch: guide={guide.shape}, mask={mask.shape}")
    edges = cv2.Canny(guide.astype(np.uint8), 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), dtype=np.uint8), iterations=1)
    edges[mask == 0] = 0
    return edges


def _patch_edge_ratio(edge_map: np.ndarray, x0: int, y0: int, size: int) -> float:
    patch = _crop_patch(edge_map, x0, y0, size)
    return float(np.count_nonzero(patch > 0)) / float(size * size)


def _clip_origin(cx: int, cy: int, width: int, height: int, patch_size: int) -> tuple[int, int]:
    x0 = int(np.clip(cx - patch_size // 2, 0, width - patch_size))
    y0 = int(np.clip(cy - patch_size // 2, 0, height - patch_size))
    return x0, y0


def plan_masked_patches(
    mask: np.ndarray,
    *,
    guide: np.ndarray | None = None,
    patch_size: int,
    patches_per_pair: int,
    min_trusted_ratio: float,
    base_seed: int,
    pair_id: str,
) -> list[dict[str, float | int]]:
    if patch_size <= 0:
        raise ValueError("patch_size must be positive")
    if patches_per_pair <= 0:
        raise ValueError("patches_per_pair must be positive")
    height, width = mask.shape
    if patch_size > height or patch_size > width:
        raise ValueError(f"patch_size={patch_size} exceeds mask shape={mask.shape}")
    coords = np.column_stack(np.nonzero(mask > 0))
    if len(coords) == 0:
        raise ValueError(f"reliable mask has no trusted pixels for {pair_id}")
    edge_map = _edge_map_from_guide(guide, mask)
    edge_coords = np.column_stack(np.nonzero(edge_map > 0))

    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    centers: list[tuple[int, int]] = [
        (int((x_min + x_max) // 2), int((y_min + y_max) // 2)),
        (int(x_min), int(y_min)),
        (int(x_max), int(y_min)),
        (int(x_min), int(y_max)),
        (int(x_max), int(y_max)),
    ]
    for frac_x, frac_y in ((0.25, 0.5), (0.75, 0.5), (0.5, 0.25), (0.5, 0.75)):
        centers.append(
            (
                int(x_min + (x_max - x_min) * frac_x),
                int(y_min + (y_max - y_min) * frac_y),
            )
        )

    rng_seed = int(base_seed) + (abs(hash(str(pair_id))) % 1_000_000)
    rng = np.random.default_rng(rng_seed)
    if len(edge_coords) > 0:
        ey_min, ex_min = edge_coords.min(axis=0)
        ey_max, ex_max = edge_coords.max(axis=0)
        centers.extend(
            [
                (int((ex_min + ex_max) // 2), int((ey_min + ey_max) // 2)),
                (int(ex_min), int(ey_min)),
                (int(ex_max), int(ey_min)),
                (int(ex_min), int(ey_max)),
                (int(ex_max), int(ey_max)),
            ]
        )
        for _ in range(max(32, patches_per_pair * 12)):
            cy, cx = edge_coords[int(rng.integers(0, len(edge_coords)))]
            centers.append((int(cx), int(cy)))
    for _ in range(max(16, patches_per_pair * 6)):
        cy, cx = coords[int(rng.integers(0, len(coords)))]
        centers.append((int(cx), int(cy)))

    candidates: dict[tuple[int, int], tuple[float, float]] = {}
    for cx, cy in centers:
        x0, y0 = _clip_origin(cx, cy, width, height, patch_size)
        trusted_ratio = _patch_trusted_ratio(mask, x0, y0, patch_size)
        edge_ratio = _patch_edge_ratio(edge_map, x0, y0, patch_size)
        if trusted_ratio >= float(min_trusted_ratio):
            prev = candidates.get((x0, y0))
            if prev is None or (edge_ratio, trusted_ratio) > (prev[1], prev[0]):
                candidates[(x0, y0)] = (trusted_ratio, edge_ratio)

    if not candidates:
        best = None
        for cx, cy in centers:
            x0, y0 = _clip_origin(cx, cy, width, height, patch_size)
            ratio = _patch_trusted_ratio(mask, x0, y0, patch_size)
            if best is None or ratio > best[2]:
                best = (x0, y0, ratio)
        assert best is not None
        raise ValueError(
            f"no patch reaches min_trusted_ratio={min_trusted_ratio:.4f} for {pair_id}; "
            f"best={best[2]:.4f}"
        )

    ordered = sorted(candidates.items(), key=lambda item: (-item[1][1], -item[1][0], item[0][1], item[0][0]))
    if len(ordered) < patches_per_pair:
        repeats = math.ceil(patches_per_pair / max(1, len(ordered)))
        ordered = (ordered * repeats)[:patches_per_pair]
    else:
        ordered = ordered[:patches_per_pair]
    return [
        {
            "x0": int(origin[0]),
            "y0": int(origin[1]),
            "trusted_ratio": float(score[0]),
            "edge_ratio": float(score[1]),
        }
        for origin, score in ordered
    ]


def _float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, "")
        if value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def materialize_overfit_package(
    selected_csv: Path | str = DEFAULT_SELECTED_CSV,
    output_dir: Path | str = DEFAULT_PACKAGE_DIR,
    *,
    patch_size: int = 256,
    patches_per_pair: int = 6,
    min_trusted_ratio: float = 0.01,
    edge_band_radius: int = 5,
    base_seed: int = 5454,
    force: bool = False,
) -> dict[str, object]:
    selected_path = Path(selected_csv).resolve()
    out = Path(output_dir).resolve()
    if out.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {out}")
        remove_root = DEFAULT_OUTPUT_ROOT if str(out).lower().startswith(str(DEFAULT_OUTPUT_ROOT.resolve()).lower()) else out.parent
        _safe_remove_tree(out, root=remove_root)
    out.mkdir(parents=True, exist_ok=True)

    rows = read_csv(selected_path)
    if not rows:
        raise ValueError(f"no selected probe rows found: {selected_path}")

    records: list[dict[str, object]] = []
    pair_counts: Counter[str] = Counter()
    geom_dir = out / "geom"
    for row in rows:
        pair_id = str(row.get("pair_id", "")).strip()
        if not pair_id:
            raise ValueError(f"selected row missing pair_id: {row}")
        source = _read_gray(Path(str(row["source_image"])))
        gt = _read_gray(Path(str(row["gt_image"])))
        reliable_mask = _read_gray(Path(str(row["reliable_mask"])))
        if source.shape != gt.shape or source.shape != reliable_mask.shape:
            raise ValueError(
                f"shape mismatch for {pair_id}: src={source.shape}, gt={gt.shape}, mask={reliable_mask.shape}"
            )
        mask = build_supervision_mask(reliable_mask, gt, edge_band_radius=int(edge_band_radius))
        actual_patch_size = int(min(patch_size, source.shape[0], source.shape[1]))
        patches = plan_masked_patches(
            mask,
            guide=gt,
            patch_size=actual_patch_size,
            patches_per_pair=int(patches_per_pair),
            min_trusted_ratio=float(min_trusted_ratio),
            base_seed=int(base_seed),
            pair_id=pair_id,
        )
        for patch_idx, patch in enumerate(patches):
            x0 = int(patch["x0"])
            y0 = int(patch["y0"])
            src_patch = _crop_patch(source, x0, y0, actual_patch_size)
            gt_patch = _crop_patch(gt, x0, y0, actual_patch_size)
            mask_patch = _crop_patch(mask, x0, y0, actual_patch_size)
            lbl_patch = make_masked_label(src_patch, gt_patch, mask_patch)
            name = f"{pair_id}_p{patch_idx:03d}.bmp"
            rel_path = Path(STAGE_NAME) / name
            src_rel = Path("src") / rel_path
            lbl_rel = Path("lbl") / rel_path
            mask_rel = Path("mask") / rel_path
            _write_image(out / src_rel, src_patch)
            _write_image(out / lbl_rel, lbl_patch)
            _write_image(out / mask_rel, mask_patch)
            geom_record = _write_geometry_sidecars(gt_patch, mask_patch, geom_dir, rel_path)
            inside_changed = int(np.count_nonzero((mask_patch > 0) & (lbl_patch != src_patch)))
            outside_mismatch = int(np.count_nonzero((mask_patch == 0) & (lbl_patch != src_patch)))
            record = {
                "role": "masked_real_cad_probe",
                "stage": STAGE_NAME,
                "pair_id": pair_id,
                "patch_index": int(patch_idx),
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "package_mask": mask_rel.as_posix(),
                "source_image": str(Path(str(row["source_image"])).resolve()),
                "gt_image": str(Path(str(row["gt_image"])).resolve()),
                "reliable_mask": str(Path(str(row["reliable_mask"])).resolve()),
                "x0": x0,
                "y0": y0,
                "patch_size": actual_patch_size,
                "trusted_ratio": float(patch["trusted_ratio"]),
                "edge_ratio": float(patch.get("edge_ratio", 0.0)),
                "edge_band_radius": int(edge_band_radius),
                "inside_mask_changed_pixels": inside_changed,
                "outside_mask_mismatch_pixels": outside_mismatch,
                "source_coverage": _float(row, "coverage"),
                "edge_p95_px": _float(row, "edge_p95_px"),
                "edge_within_2px_ratio": _float(row, "edge_within_2px_ratio"),
                "component_count": int(_float(row, "component_count")),
                **geom_record,
            }
            records.append(record)
            pair_counts[pair_id] += 1

    manifest = {
        "profile": PROFILE_NAME,
        "generator": "r54_masked_overfit_probe_v1",
        "selected_csv": str(selected_path),
        "output_dir": str(out),
        "total_pairs": len(records),
        "source_pair_count": len(rows),
        "patch_size": int(patch_size),
        "patches_per_pair": int(patches_per_pair),
        "min_trusted_ratio": float(min_trusted_ratio),
        "edge_band_radius": int(edge_band_radius),
        "base_seed": int(base_seed),
        "count_by_role": {"masked_real_cad_probe": len(records)},
        "count_by_pair_id": dict(pair_counts),
        "label_policy": LABEL_POLICY,
        "geometry_policy": GEOMETRY_POLICY,
        "geometry_sidecars": True,
        "geom_dir": str(geom_dir),
        "geometry_count": len(records),
        "pairs": records,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def validate_package(package_dir: Path | str = DEFAULT_PACKAGE_DIR) -> dict[str, object]:
    root = Path(package_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    records = list(manifest.get("pairs", []))
    outside_mismatch = 0
    inside_changed_pairs = 0
    missing_files: list[str] = []
    trusted_ratios: list[float] = []
    for record in records:
        required = [
            record.get("package_src", ""),
            record.get("package_lbl", ""),
            record.get("package_mask", ""),
            record.get("geometry_boundary", ""),
            record.get("geometry_centerline", ""),
            record.get("geometry_distance", ""),
        ]
        for rel in required:
            if not rel or not (root / str(rel)).exists():
                missing_files.append(str(rel))
        if missing_files:
            continue
        src = _read_gray(root / str(record["package_src"]))
        lbl = _read_gray(root / str(record["package_lbl"]))
        mask = _read_gray(root / str(record["package_mask"]))
        mismatch = int(np.count_nonzero((mask == 0) & (lbl != src)))
        changed = int(np.count_nonzero((mask > 0) & (lbl != src)))
        outside_mismatch += mismatch
        if changed > 0:
            inside_changed_pairs += 1
        trusted_ratios.append(float(record.get("trusted_ratio", 0.0)))
    return {
        "package_dir": str(root),
        "profile": manifest.get("profile", ""),
        "total_pairs": len(records),
        "manifest_total_pairs": int(manifest.get("total_pairs", -1)),
        "outside_mask_mismatch_pixels": int(outside_mismatch),
        "inside_mask_changed_pairs": int(inside_changed_pairs),
        "missing_file_count": len(missing_files),
        "missing_files": missing_files[:20],
        "min_trusted_ratio": min(trusted_ratios) if trusted_ratios else 0.0,
        "median_trusted_ratio": float(np.median(trusted_ratios)) if trusted_ratios else 0.0,
        "label_policy": manifest.get("label_policy", ""),
        "geometry_policy": manifest.get("geometry_policy", ""),
    }


def create_preview(
    package_dir: Path | str = DEFAULT_PACKAGE_DIR,
    output_path: Path | str = DEFAULT_PREVIEW_PATH,
    *,
    max_items: int = 12,
    tile_size: int = 160,
) -> dict[str, object]:
    root = Path(package_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    records = list(manifest.get("pairs", []))[: int(max_items)]
    if not records:
        raise ValueError(f"no records in package: {root}")
    tiles = []
    for record in records:
        src = _read_gray(root / str(record["package_src"]))
        lbl = _read_gray(root / str(record["package_lbl"]))
        mask = _read_gray(root / str(record["package_mask"]))
        tile = np.concatenate([src, lbl, mask], axis=1)
        tile = cv2.resize(tile, (tile_size * 3, tile_size), interpolation=cv2.INTER_AREA)
        tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
        cv2.putText(
            tile,
            f"{record['pair_id']} p{record['patch_index']}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        tiles.append(tile)
    cols = 2
    rows = int(math.ceil(len(tiles) / cols))
    sheet = np.full((rows * tile_size, cols * tile_size * 3, 3), 245, dtype=np.uint8)
    for idx, tile in enumerate(tiles):
        r, c = divmod(idx, cols)
        sheet[r * tile_size : (r + 1) * tile_size, c * tile_size * 3 : (c + 1) * tile_size * 3] = tile
    out = Path(output_path)
    _write_image(out, sheet)
    return {"preview": str(out), "tiles": len(tiles)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and validate the R54 masked small-overfit package.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--selected-csv", type=Path, default=DEFAULT_SELECTED_CSV)
    build.add_argument("--output-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    build.add_argument("--patch-size", type=int, default=256)
    build.add_argument("--patches-per-pair", type=int, default=6)
    build.add_argument("--min-trusted-ratio", type=float, default=0.01)
    build.add_argument("--edge-band-radius", type=int, default=5)
    build.add_argument("--base-seed", type=int, default=5454)
    build.add_argument("--force", action="store_true")

    validate = sub.add_parser("validate")
    validate.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    validate.add_argument("--strict", action="store_true")

    preview = sub.add_parser("preview")
    preview.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    preview.add_argument("--output-path", type=Path, default=DEFAULT_PREVIEW_PATH)
    preview.add_argument("--max-items", type=int, default=12)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.command == "build":
        manifest = materialize_overfit_package(
            args.selected_csv,
            args.output_dir,
            patch_size=args.patch_size,
            patches_per_pair=args.patches_per_pair,
            min_trusted_ratio=args.min_trusted_ratio,
            edge_band_radius=args.edge_band_radius,
            base_seed=args.base_seed,
            force=args.force,
        )
        print(json.dumps({k: v for k, v in manifest.items() if k != "pairs"}, indent=2, ensure_ascii=False))
        return 0
    if args.command == "validate":
        summary = validate_package(args.package_dir)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        if args.strict and (
            summary["missing_file_count"] != 0
            or summary["outside_mask_mismatch_pixels"] != 0
            or summary["inside_mask_changed_pairs"] != summary["total_pairs"]
        ):
            return 2
        return 0
    if args.command == "preview":
        summary = create_preview(args.package_dir, args.output_path, max_items=args.max_items)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    raise RuntimeError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
