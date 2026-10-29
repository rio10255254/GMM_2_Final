from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT))
OUT = ROOT / "Experiments" / "R66_V20_TraceabilityFigures_20260725" / "qa"

PATHS = {
    "sequence_raw": ROOT / r"20260702_100MG_displacement_analysis\raw_inputs\x_0p5um\bmp\frame_0000.bmp",
    "static_raw": ROOT / r"Thesis_MOSR_Evidence\20260618_100MG\Image__2026-06-18__17-10-31.bmp",
    "ablation_full": ROOT / r"Experiments\R63_CausalBoundaryMotionAblation\results\evaluation\reconstructions\full_control\seed1261200\static_50x_sem\Image__2026-06-18__17-10-31.bmp",
    "ablation_wrong_no_geometry": ROOT / r"Experiments\R63_CausalBoundaryMotionAblation\results\evaluation\reconstructions\no_geometry_anchor\seed1261200\static_50x_sem\Image__2026-06-18__17-10-31.bmp",
    "ablation_correct_no_raw_anchor": ROOT / r"Experiments\R63_CausalBoundaryMotionAblation\results\evaluation\reconstructions\no_raw_position_anchor\seed1261200\static_50x_sem\Image__2026-06-18__17-10-31.bmp",
    "nafnet": ROOT / r"Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\Modern_Restoration_Benchmarks_20260719\results\nafnet\real_inference\sequences\50x_x_0p5um\frame_0000.bmp",
    "edsr": ROOT / r"Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\Modern_Restoration_Benchmarks_20260719\results\edsr\real_inference\sequences\50x_x_0p5um\frame_0000.bmp",
    "mosr": ROOT / r"Thesis_MOSR_Evidence\Final_Data_Figures\02_V42_E120_SOURCE_MATERIAL\reconstructions\50x_0p5um\frame_0000.bmp",
}


def read_gray(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(path)
    return np.asarray(Image.open(path).convert("L"), dtype=np.float64)


def crop_matlab(im: np.ndarray, limits: tuple[int, int, int, int]) -> np.ndarray:
    """Crop from inclusive MATLAB x/y limits expressed in 1-based image coordinates."""
    x1, x2, y1, y2 = limits
    return im[y1 - 1 : y2, x1 - 1 : x2]


def image_stats(im: np.ndarray) -> dict[str, float | int]:
    return {
        "height": int(im.shape[0]),
        "width": int(im.shape[1]),
        "min": float(np.min(im)),
        "p01": float(np.percentile(im, 1)),
        "p02": float(np.percentile(im, 2)),
        "p50": float(np.percentile(im, 50)),
        "p98": float(np.percentile(im, 98)),
        "p99": float(np.percentile(im, 99)),
        "max": float(np.max(im)),
        "mean": float(np.mean(im)),
        "std": float(np.std(im)),
        "zero_pct": float(np.mean(im <= 0) * 100),
        "sat255_pct": float(np.mean(im >= 255) * 100),
        "unique_levels": int(np.unique(im).size),
    }


def disk_ring_stats(
    im: np.ndarray,
    center_xy: tuple[float, float],
    core_radius: float = 8.0,
    ring_inner: float = 25.0,
    ring_outer: float = 32.0,
) -> dict[str, float]:
    yy, xx = np.indices(im.shape)
    # Convert NumPy zero-based centers to MATLAB-like 1-based image coordinates.
    xx = xx + 1
    yy = yy + 1
    rr = np.hypot(xx - center_xy[0], yy - center_xy[1])
    core = im[rr <= core_radius]
    ring = im[(rr >= ring_inner) & (rr <= ring_outer)]
    core_med = float(np.median(core))
    bg_med = float(np.median(ring))
    denom = bg_med + core_med
    return {
        "core_median": core_med,
        "background_median": bg_med,
        "signed_michelson_dark_pillar": float((bg_med - core_med) / denom) if denom else float("nan"),
        "background_minus_core": float(bg_med - core_med),
    }


def center_audit(
    im: np.ndarray,
    configured_xy: tuple[float, float],
    search_radius: float = 31.0,
) -> dict[str, float]:
    yy, xx = np.indices(im.shape)
    xx = xx + 1
    yy = yy + 1
    rr = np.hypot(xx - configured_xy[0], yy - configured_xy[1])
    search = rr <= search_radius

    local = im[search]
    background = float(np.percentile(local, 90))
    weights = np.clip(background - im, 0, None) * search
    weight_sum = float(weights.sum())
    dark_x = float((weights * xx).sum() / weight_sum)
    dark_y = float((weights * yy).sum() / weight_sum)

    core = im[rr <= 8]
    annulus = im[(rr >= 25) & (rr <= 31)]
    threshold = float((np.median(core) + np.median(annulus)) / 2)
    mask = search & (im <= threshold)
    mask_x = float(xx[mask].mean())
    mask_y = float(yy[mask].mean())

    def offset(x: float, y: float) -> tuple[float, float, float]:
        dx = x - configured_xy[0]
        dy = y - configured_xy[1]
        return dx, dy, float(np.hypot(dx, dy))

    dark_dx, dark_dy, dark_dr = offset(dark_x, dark_y)
    mask_dx, mask_dy, mask_dr = offset(mask_x, mask_y)
    return {
        "configured_x": configured_xy[0],
        "configured_y": configured_xy[1],
        "darkness_centroid_x": dark_x,
        "darkness_centroid_y": dark_y,
        "darkness_dx_px": dark_dx,
        "darkness_dy_px": dark_dy,
        "darkness_offset_px": dark_dr,
        "darkness_offset_nm_at_50x": dark_dr * 69.0,
        "half_level_mask_centroid_x": mask_x,
        "half_level_mask_centroid_y": mask_y,
        "half_level_dx_px": mask_dx,
        "half_level_dy_px": mask_dy,
        "half_level_offset_px": mask_dr,
        "half_level_offset_nm_at_50x": mask_dr * 69.0,
        "half_level_threshold": threshold,
    }


def shared_display_range(images: list[np.ndarray]) -> dict[str, float]:
    pooled = np.concatenate([im.ravel() for im in images])
    return {
        "shared_p01": float(np.percentile(pooled, 1)),
        "shared_p99": float(np.percentile(pooled, 99)),
    }


def main() -> None:
    images = {name: read_gray(path) for name, path in PATHS.items()}
    p29_initial_audit = center_audit(
        images["sequence_raw"], configured_xy=(1173.5, 714.5)
    )
    p29_refined_xy = (
        p29_initial_audit["darkness_centroid_x"],
        p29_initial_audit["darkness_centroid_y"],
    )

    static_locator = crop_matlab(images["static_raw"], (716, 936, 634, 854))
    ablation_names = [
        "static_raw",
        "ablation_full",
        "ablation_wrong_no_geometry",
        "ablation_correct_no_raw_anchor",
    ]
    ablation_crops = {
        name: crop_matlab(images[name], (768, 889, 687, 808))
        for name in ablation_names
    }
    multimodel_names = ["sequence_raw", "nafnet", "edsr", "mosr"]
    multimodel_crops = {
        name: crop_matlab(images[name], (1065, 1281, 607, 823))
        for name in multimodel_names
    }

    report = {
        "source_paths": {name: str(path) for name, path in PATHS.items()},
        "figure_display_policy": {
            "range": [0, 255],
            "rule": "native_8bit_no_per_image_or_pooled_contrast_stretch",
        },
        "figure_6_27_center_audit": {
            "initial_grid_coordinate_audit": p29_initial_audit,
            "raw_fixed_sampling_origin_xy": p29_refined_xy,
            "display_marker": "white_centered_blue_dot",
            "identity_maps_show_center_markers": False,
        },
        "figure_6_34_static_locator": {
            "native_crop_stats": image_stats(static_locator),
            "display_range_used_by_showImage": [0, 255],
            "p29_local_contrast": disk_ring_stats(
                images["static_raw"], center_xy=(828.850536746, 747.905862923)
            ),
        },
        "figure_6_50_ablation": {
            "current_three_panel_sources": [
                "static_raw",
                "ablation_full",
                "ablation_correct_no_raw_anchor",
            ],
            "native_display_range": [0, 255],
            "native_crop_stats": {
                name: image_stats(crop) for name, crop in ablation_crops.items()
            },
            "historical_wrong_source_not_used": "ablation_wrong_no_geometry",
            "p29_local_contrast": {
                name: disk_ring_stats(
                    images[name], center_xy=(828.850536746, 747.905862923)
                )
                for name in ablation_names
            },
        },
        "figure_6_59_multimodel": {
            "native_display_range": [0, 255],
            "native_crop_stats": {
                name: image_stats(crop) for name, crop in multimodel_crops.items()
            },
            "p29_local_contrast": {
                name: disk_ring_stats(images[name], center_xy=p29_refined_xy)
                for name in multimodel_names
            },
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / "v20_image_integrity_audit.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(output)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
