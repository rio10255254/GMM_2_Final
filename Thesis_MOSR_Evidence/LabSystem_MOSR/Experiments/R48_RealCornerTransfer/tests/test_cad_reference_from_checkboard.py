from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "cad_reference_from_checkboard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cad_reference_from_checkboard", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _synthetic_checkboard_frame() -> np.ndarray:
    img = np.full((180, 240), 18, dtype=np.uint8)
    cv2.fillConvexPoly(img, np.array([[25, 25], [100, 20], [106, 95], [28, 102]], np.int32), 205)
    cv2.fillConvexPoly(img, np.array([[132, 82], [205, 78], [211, 153], [136, 160]], np.int32), 212)
    for x, y in [(12, 12), (220, 35), (45, 160), (120, 40)]:
        cv2.circle(img, (x, y), 2, 230, -1)
    img = cv2.GaussianBlur(img, (0, 0), 1.2)
    return img


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _rectangularity_issues(mask: np.ndarray) -> list[tuple[int, float, float, int]]:
    issues: list[tuple[int, float, float, int]] = []
    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=4)
    for idx in range(1, num):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < 50:
            continue
        component = np.zeros(mask.shape, dtype=np.uint8)
        component[labels == idx] = 255
        contours, _hierarchy = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(contour)
        width, height = rect[1]
        rect_area = float(width) * float(height)
        fill_ratio = float(area) / rect_area if rect_area > 0 else 0.0
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = cv2.contourArea(contour) / hull_area if hull_area > 0 else 0.0
        approx = cv2.approxPolyDP(contour, max(1.0, 0.01 * cv2.arcLength(contour, True)), True)
        if fill_ratio < 0.85 or solidity < 0.95 or len(approx) > 4:
            issues.append((area, fill_ratio, solidity, int(len(approx))))
    return issues


def test_extract_cad_reference_redraws_large_regions_and_rejects_speckles():
    module = load_module()
    img = _synthetic_checkboard_frame()

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.006,
    )

    assert result.gt.shape == img.shape
    assert result.gt.dtype == np.uint8
    assert result.reliable_mask.shape == img.shape
    assert result.metrics["component_count"] == 2
    assert result.metrics["white_area_px"] > 9000
    assert result.gt[12, 12] == 0
    assert result.gt[90, 60] == 255
    assert result.gt[120, 170] == 255
    assert "edge_p95_px" in result.metrics
    assert result.metrics["edge_p95_px"] <= 3.0
    assert _rectangularity_issues(result.gt) == []


def test_extract_cad_reference_rejects_l_shaped_regions_in_strict_gt():
    module = load_module()
    img = np.full((160, 180), 18, dtype=np.uint8)
    cv2.rectangle(img, (20, 20), (140, 55), 210, -1)
    cv2.rectangle(img, (20, 20), (58, 140), 210, -1)
    cv2.rectangle(img, (95, 90), (145, 140), 210, -1)
    img = cv2.GaussianBlur(img, (0, 0), 0.8)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.004,
    )

    assert result.metrics["component_count"] == 1
    assert result.gt[35, 35] == 0
    assert result.gt[120, 40] == 0
    assert result.gt[115, 120] == 255
    assert _rectangularity_issues(result.gt) == []


def test_extract_cad_reference_keeps_checker_cells_separate_and_rectangular():
    module = load_module()
    img = np.full((260, 240), 18, dtype=np.uint8)
    for row, y in enumerate((35, 95, 155)):
        for col, x in enumerate((40, 100, 160)):
            if (row + col) % 2 == 0:
                cv2.rectangle(img, (x, y), (x + 42, y + 42), 210, -1)
    cv2.putText(img, "10 0", (32, 245), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 210, 3, cv2.LINE_AA)
    img = cv2.GaussianBlur(img, (0, 0), 1.0)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.004,
    )

    assert result.metrics["component_count"] == 5
    assert result.gt[240, 55] == 0
    assert _rectangularity_issues(result.gt) == []


def test_extract_cad_reference_leaves_gap_between_touching_diagonal_cells():
    module = load_module()
    img = np.full((150, 150), 18, dtype=np.uint8)
    cv2.rectangle(img, (30, 30), (70, 70), 210, -1)
    cv2.rectangle(img, (71, 71), (111, 111), 210, -1)
    img = cv2.GaussianBlur(img, (0, 0), 0.6)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.4,
        polygon_epsilon_ratio=0.004,
    )

    num, _labels, _stats, _centroids = cv2.connectedComponentsWithStats(result.gt, connectivity=8)
    assert result.metrics["component_count"] == 2
    assert num - 1 == 2
    assert result.gt[70, 70] == 0
    assert result.gt[71, 71] == 0


def test_extract_cad_reference_ignores_small_edge_defects():
    module = load_module()
    img = np.full((150, 180), 18, dtype=np.uint8)
    cv2.rectangle(img, (30, 25), (145, 125), 210, -1)
    cv2.circle(img, (30, 95), 13, 18, -1)
    img = cv2.GaussianBlur(img, (0, 0), 1.0)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.004,
    )

    assert result.metrics["component_count"] == 1
    assert result.gt[95, 35] == 255
    assert result.gt[75, 80] == 255
    assert result.reliable_mask[95, 35] == 0
    assert result.metrics["masked_disagreement_px"] > 0


def test_extract_cad_reference_rejects_frame_clipped_regions():
    module = load_module()
    img = np.full((150, 180), 18, dtype=np.uint8)
    cv2.rectangle(img, (45, 35), (179, 115), 210, -1)
    img = cv2.GaussianBlur(img, (0, 0), 1.0)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.004,
        frame_border_ignore_size=9,
    )

    assert result.metrics["component_count"] == 0
    assert result.metrics["rejected_frame_clipped_components"] == 1
    assert result.gt.max() == 0


def test_reliable_mask_keeps_clear_black_and_white_regions_but_not_edges():
    module = load_module()
    img = np.full((170, 210), 18, dtype=np.uint8)
    cv2.rectangle(img, (55, 45), (150, 125), 210, -1)
    img = cv2.GaussianBlur(img, (0, 0), 1.0)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.004,
        mask_context_dilate_size=39,
        boundary_band_size=7,
    )

    assert result.gt[85, 95] == 255
    assert result.reliable_mask[85, 95] == 255
    assert result.gt[85, 42] == 0
    assert result.reliable_mask[85, 42] == 255
    assert result.reliable_mask[85, 55] == 0


def test_extract_cad_reference_rejects_hollow_marker_components():
    module = load_module()
    img = np.full((180, 240), 18, dtype=np.uint8)
    cv2.rectangle(img, (25, 25), (125, 125), 210, -1)
    cv2.circle(img, (190, 95), 32, 210, 9)
    img = cv2.GaussianBlur(img, (0, 0), 1.0)

    result = module.extract_cad_reference_from_array(
        img,
        min_component_area=700,
        blur_sigma=0.8,
        polygon_epsilon_ratio=0.004,
    )

    assert result.metrics["component_count"] == 1
    assert result.gt[75, 75] == 255
    assert result.gt[95, 190] == 0


def test_cli_writes_gt_masks_overlays_and_manifest(tmp_path: Path):
    module = load_module()
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    img = _synthetic_checkboard_frame()
    _write_image(input_dir / "frame_a.bmp", img)
    _write_image(input_dir / "frame_b.bmp", np.rot90(img))

    rc = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--min-component-area",
            "700",
        ]
    )

    assert rc == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_images"] == 2
    assert manifest["failed_images"] == 0
    assert "mean_edge_p95_px" in manifest
    for stem in ("frame_a", "frame_b"):
        assert (output_dir / "gt" / f"{stem}_cad_gt.bmp").exists()
        assert (output_dir / "mask" / f"{stem}_reliable_mask.bmp").exists()
        assert (output_dir / "overlay" / f"{stem}_overlay.png").exists()


def test_cli_handles_images_with_no_strict_rectangles(tmp_path: Path):
    module = load_module()
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    img = np.full((120, 120), 18, dtype=np.uint8)
    cv2.rectangle(img, (0, 20), (119, 95), 210, -1)
    _write_image(input_dir / "clipped.bmp", img)

    rc = module.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--min-component-area",
            "700",
        ]
    )

    assert rc == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_images"] == 1
    assert manifest["ok_images"] == 1
    assert manifest["mean_edge_p95_px"] is None
