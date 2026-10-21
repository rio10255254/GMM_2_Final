from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_r61_universal_dataset.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_r61_universal_dataset", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.clip(img, 0, 255).astype(np.uint8))
    assert ok
    path.write_bytes(encoded.tobytes())


def _make_fixture_package(root: Path, name: str, role: str, count: int = 4) -> Path:
    package = root / name
    pairs = []
    for idx in range(count):
        stage = f"{role}_stage"
        stem = f"{role}_{idx:03d}.bmp"
        src_rel = Path("src") / stage / stem
        lbl_rel = Path("lbl") / stage / stem
        img = np.full((80, 80), 88, np.uint8)
        label = np.full((80, 80), 88, np.uint8)
        radius = 12 + idx
        if idx % 2 == 0:
            cv2.circle(img, (40, 40), radius - 2, 150, -1, lineType=cv2.LINE_AA)
            cv2.circle(label, (40, 40), radius, 172, -1, lineType=cv2.LINE_AA)
            polarity = "bright"
        else:
            cv2.circle(img, (40, 40), radius + 2, 36, -1, lineType=cv2.LINE_AA)
            cv2.circle(label, (40, 40), radius, 24, -1, lineType=cv2.LINE_AA)
            polarity = "dark"
        _write_bmp(package / src_rel, img)
        _write_bmp(package / lbl_rel, label)
        pairs.append(
            {
                "package_src": src_rel.as_posix(),
                "package_lbl": lbl_rel.as_posix(),
                "source_group": role,
                "domain": role,
                "feature": "circle",
                "polarity": polarity,
                "template_id": idx // 2,
                "sem_reference_id": idx // 2,
            }
        )
    manifest = {
        "profile": name,
        "total_pairs": len(pairs),
        "pairs": pairs,
    }
    (package / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return package


def test_render_polarity_variants_share_same_truth_boundary_but_keep_contrast_direction():
    module = load_module()

    dark = module.render_generalization_pair(
        size=160,
        geometry_seed=11,
        appearance_seed=101,
        polarity="dark",
        shape_family="mixed",
        bias_px=2.0,
        blur_sigma=1.1,
        noise_sigma=0.0,
    )
    bright = module.render_generalization_pair(
        size=160,
        geometry_seed=11,
        appearance_seed=202,
        polarity="bright",
        shape_family="mixed",
        bias_px=2.0,
        blur_sigma=1.1,
        noise_sigma=0.0,
    )

    assert np.array_equal(dark.boundary_mask, bright.boundary_mask)
    assert not np.array_equal(dark.truth_label, bright.truth_label)
    assert not np.array_equal(dark.source_image, bright.source_image)
    assert dark.polarity == "dark"
    assert bright.polarity == "bright"
    assert dark.boundary_mask.sum() > 0

    center = (80, 80)
    corner = (8, 8)
    dark_delta = int(dark.source_image[center]) - int(dark.source_image[corner])
    bright_delta = int(bright.source_image[center]) - int(bright.source_image[corner])
    dark_truth_delta = int(dark.truth_label[center]) - int(dark.truth_label[corner])
    bright_truth_delta = int(bright.truth_label[center]) - int(bright.truth_label[corner])
    assert dark_delta * bright_delta < 0
    assert dark_truth_delta < 0
    assert bright_truth_delta > 0


def test_bias_mask_supports_zero_and_ordered_fractional_offsets():
    module = load_module()
    mask = np.zeros((96, 96), np.uint8)
    cv2.circle(mask, (48, 48), 22, 255, -1, lineType=cv2.LINE_AA)

    dark_0 = module._bias_mask(mask, 0.0, "dark")
    dark_05 = module._bias_mask(mask, 0.5, "dark")
    dark_20 = module._bias_mask(mask, 2.0, "dark")
    bright_05 = module._bias_mask(mask, 0.5, "bright")
    bright_20 = module._bias_mask(mask, 2.0, "bright")

    assert np.array_equal(dark_0, mask)
    area = lambda img: float(np.asarray(img, dtype=np.float32).sum())
    assert area(dark_20) < area(dark_05) < area(mask)
    assert area(mask) < area(bright_05) < area(bright_20)


def test_integer_bias_matches_validation_radius_kernel():
    module = load_module()
    mask = np.zeros((96, 96), np.uint8)
    cv2.circle(mask, (48, 48), 22, 255, -1, lineType=cv2.LINE_AA)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    assert np.array_equal(module._bias_mask(mask, 2.0, "dark"), cv2.erode(mask, kernel))
    assert np.array_equal(module._bias_mask(mask, 2.0, "bright"), cv2.dilate(mask, kernel))


def test_hybrid_bias_profile_keeps_zero_guard_and_oversamples_large_offsets():
    module = load_module()

    cycle = module.bias_cycle_for_profile("hybrid_large_guard")
    counts = {bias: cycle.count(bias) for bias in sorted(set(cycle))}

    assert 0.0 in counts
    assert 0.5 in counts
    assert 1.0 in counts
    assert 2.0 in counts
    assert 2.5 in counts
    assert counts[2.0] + counts[2.5] > counts[0.0] + counts[0.5]


def test_polarity_adaptive_profile_emphasizes_dark_small_and_bright_large_offsets():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("polarity_adaptive", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("polarity_adaptive", polarity="bright")

    dark_small = sum(1 for bias in dark_cycle if bias <= 1.0)
    dark_large = sum(1 for bias in dark_cycle if bias >= 2.0)
    bright_small = sum(1 for bias in bright_cycle if bias <= 1.0)
    bright_large = sum(1 for bias in bright_cycle if bias >= 2.0)

    assert 0.0 in dark_cycle
    assert 1.0 in dark_cycle
    assert 2.0 in dark_cycle
    assert 1.0 in bright_cycle
    assert 2.0 in bright_cycle
    assert 2.5 in bright_cycle
    assert dark_small > dark_large
    assert bright_large > bright_small


def test_identity_guard_profile_keeps_noop_cases_for_both_polarities():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("identity_guard_v2", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("identity_guard_v2", polarity="bright")

    assert dark_cycle.count(0.0) >= 2
    assert bright_cycle.count(0.0) >= 2
    assert 0.25 in dark_cycle
    assert 0.25 in bright_cycle
    assert max(dark_cycle) >= 2.5
    assert max(bright_cycle) >= 2.5


def test_small_bias_dark_thin_profile_combines_noop_guard_and_dark_large_offsets():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("small_bias_dark_thin_v3", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("small_bias_dark_thin_v3", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("small_bias_dark_thin_v3")

    assert dark_cycle.count(0.0) >= 3
    assert bright_cycle.count(0.0) >= 3
    assert dark_cycle.count(0.25) >= 2
    assert bright_cycle.count(0.25) >= 2
    assert dark_cycle.count(2.0) + dark_cycle.count(2.5) >= 3
    assert max(bright_cycle) >= 2.0
    assert shape_cycle.count("thin_bar") > shape_cycle.count("circle")
    assert shape_cycle.count("thin_bar") > shape_cycle.count("annulus")


def test_small_bias_guard_profile_excludes_large_offsets_and_keeps_shape_diversity():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("small_bias_guard_v4", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("small_bias_guard_v4", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("small_bias_guard_v4")

    assert max(dark_cycle) <= 0.5
    assert max(bright_cycle) <= 0.5
    assert dark_cycle.count(0.0) >= 3
    assert bright_cycle.count(0.0) >= 3
    assert dark_cycle.count(0.5) >= 2
    assert bright_cycle.count(0.5) >= 2
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus"}.issubset(set(shape_cycle))
    assert shape_cycle.count("thin_bar") >= 2


def test_small_bias_replay_profile_keeps_noop_cases_without_dropping_large_offsets():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("small_bias_replay_v5", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("small_bias_replay_v5", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("small_bias_replay_v5")

    assert dark_cycle.count(0.0) >= 2
    assert bright_cycle.count(0.0) >= 2
    assert dark_cycle.count(0.5) >= 2
    assert bright_cycle.count(0.5) >= 2
    assert max(dark_cycle) >= 2.5
    assert max(bright_cycle) >= 2.5
    assert sum(1 for bias in dark_cycle if bias >= 1.5) >= sum(1 for bias in dark_cycle if bias <= 0.5)
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("thin_bar") >= 2


def test_failure_balanced_replay_profile_targets_r21_r22_failure_bins():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("failure_balanced_replay_v6", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("failure_balanced_replay_v6", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("failure_balanced_replay_v6")

    assert dark_cycle.count(0.0) >= 3
    assert bright_cycle.count(0.0) >= 3
    assert dark_cycle.count(0.5) >= 2
    assert bright_cycle.count(0.5) >= 2
    assert max(dark_cycle) >= 2.5
    assert max(bright_cycle) >= 2.5
    assert sum(1 for bias in dark_cycle if bias >= 1.5) >= 3
    assert sum(1 for bias in bright_cycle if bias >= 1.5) >= 3
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("ellipse") > shape_cycle.count("circle")
    assert shape_cycle.count("ellipse") >= shape_cycle.count("thin_bar")


def test_failure_balanced_shape_neutral_profile_keeps_small_bias_without_ellipse_overfocus():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("failure_balanced_shape_neutral_v7", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("failure_balanced_shape_neutral_v7", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("failure_balanced_shape_neutral_v7")

    assert dark_cycle.count(0.0) >= 3
    assert bright_cycle.count(0.0) >= 3
    assert dark_cycle.count(0.5) >= 2
    assert bright_cycle.count(0.5) >= 2
    assert sum(1 for bias in dark_cycle if bias >= 1.5) >= 3
    assert sum(1 for bias in bright_cycle if bias >= 1.5) >= 3
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("ellipse") == shape_cycle.count("circle")
    assert shape_cycle.count("ellipse") <= shape_cycle.count("thin_bar")
    assert max(shape_cycle.count(shape) for shape in set(shape_cycle)) - min(shape_cycle.count(shape) for shape in set(shape_cycle)) <= 1


def test_bright_curve_replay_profile_targets_r24_remaining_failures_without_dropping_guards():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("bright_curve_replay_v8", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("bright_curve_replay_v8", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("bright_curve_replay_v8")

    assert {0.0, 0.5, 1.0, 1.5, 2.0, 2.5}.issubset(set(dark_cycle))
    assert {0.0, 0.5, 1.0, 1.5, 2.0, 2.5}.issubset(set(bright_cycle))
    assert sum(1 for bias in bright_cycle if bias >= 1.0) > sum(1 for bias in bright_cycle if bias <= 0.5)
    assert bright_cycle.count(1.0) >= 2
    assert bright_cycle.count(2.0) + bright_cycle.count(2.5) >= 3
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("ellipse") >= 2
    assert shape_cycle.count("annulus") >= 2
    assert shape_cycle.count("rect") >= 2


def test_bright_ellipse_guard_profile_targets_r31_failures_without_dropping_small_bias():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("bright_ellipse_guard_v9", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("bright_ellipse_guard_v9", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("bright_ellipse_guard_v9")

    assert bright_cycle.count(0.0) >= 2
    assert bright_cycle.count(0.5) >= 2
    assert bright_cycle.count(1.0) >= 3
    assert dark_cycle.count(0.0) >= 2
    assert dark_cycle.count(0.5) >= 2
    assert {1.5, 2.0, 2.5}.issubset(set(bright_cycle))
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("ellipse") >= 4
    assert shape_cycle.count("polygon") >= 2


def test_rotated_rect_guard_profile_targets_rect_without_dropping_curves():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("rotated_rect_guard_v10", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("rotated_rect_guard_v10", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("rotated_rect_guard_v10")

    assert {0.0, 0.5, 1.0, 1.5, 2.0, 2.5}.issubset(set(dark_cycle))
    assert {0.0, 0.5, 1.0, 1.5, 2.0, 2.5}.issubset(set(bright_cycle))
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("rect") > shape_cycle.count("ellipse")
    assert shape_cycle.count("rect") > shape_cycle.count("annulus")
    assert shape_cycle.count("ellipse") >= 2
    assert shape_cycle.count("polygon") >= 2
    assert shape_cycle.count("annulus") >= 2


def test_step_guard_v16_profile_targets_bright_small_bias_and_curve_failures():
    module = load_module()

    dark_cycle = module.bias_cycle_for_profile("step_guard_v16", polarity="dark")
    bright_cycle = module.bias_cycle_for_profile("step_guard_v16", polarity="bright")
    shape_cycle = module._shape_cycle_for_bias_profile("step_guard_v16")

    assert bright_cycle.count(0.0) >= 3
    assert bright_cycle.count(0.5) >= 3
    assert dark_cycle.count(0.0) >= 2
    assert dark_cycle.count(0.5) >= 2
    assert max(bright_cycle) >= 2.5
    assert {"circle", "ellipse", "rect", "polygon", "thin_bar", "annulus", "mixed"}.issubset(set(shape_cycle))
    assert shape_cycle.count("annulus") >= 3
    assert shape_cycle.count("ellipse") >= 3


def test_render_generalization_pair_supports_annulus_and_thin_bar_shapes():
    module = load_module()

    annulus = module.render_generalization_pair(
        size=160,
        geometry_seed=31,
        appearance_seed=401,
        polarity="bright",
        shape_family="annulus",
        bias_px=0.0,
        blur_sigma=1.1,
        noise_sigma=0.0,
    )
    thin_bar = module.render_generalization_pair(
        size=160,
        geometry_seed=32,
        appearance_seed=402,
        polarity="dark",
        shape_family="thin_bar",
        bias_px=0.0,
        blur_sigma=1.1,
        noise_sigma=0.0,
    )

    assert annulus.shape_family == "annulus"
    assert thin_bar.shape_family == "thin_bar"
    assert annulus.boundary_mask.sum() > 0
    assert thin_bar.boundary_mask.sum() > 0
    assert not np.array_equal(annulus.truth_label, thin_bar.truth_label)


def test_prepare_package_mixes_legacy_sem_and_universal_synthetic_roles(tmp_path: Path):
    module = load_module()
    legacy_shape = _make_fixture_package(tmp_path, "legacy_shape_pkg", "legacy_shape", count=4)
    sequence_guard = _make_fixture_package(tmp_path, "sequence_guard_pkg", "sequence_guard", count=4)
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=4)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_universal_train",
        legacy_sources=[
            {"role": "legacy_shape", "package_dir": legacy_shape, "limit": 3},
            {"role": "sequence_guard", "package_dir": sequence_guard, "limit": 2},
            {"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2},
        ],
        synthetic_count=8,
        image_size=96,
        seed=6101,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["r61_universal_boundary_training"] is True
    assert manifest["anti_answer_leakage_design"] is True
    assert manifest["total_pairs"] == 15
    assert manifest["role_counts"]["universal_synthetic"] == 8
    assert manifest["role_counts"]["legacy_shape"] == 3
    assert manifest["role_counts"]["sequence_guard"] == 2
    assert manifest["role_counts"]["sem_truth_anchor"] == 2
    assert manifest["polarity_counts"]["bright"] > 0
    assert manifest["polarity_counts"]["dark"] > 0
    assert len({round(float(row.get("bias_px", -1)), 2) for row in manifest["pairs"] if row.get("role") == "universal_synthetic"}) > 1
    assert manifest["geometry_count"] == manifest["total_pairs"]

    for record in manifest["pairs"]:
        assert (package / record["package_src"]).exists()
        assert (package / record["package_lbl"]).exists()
        assert (package / record["geometry_boundary"]).exists()
        assert (package / record["geometry_centerline"]).exists()
        assert (package / record["geometry_distance"]).exists()


def test_prepare_package_records_requested_bias_profile(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_hybrid_bias_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=24,
        image_size=96,
        seed=6103,
        synthetic_bias_profile="hybrid_large_guard",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    counts = {float(key): int(value) for key, value in manifest["synthetic_bias_px_counts"].items() if key != "unknown"}
    assert manifest["synthetic_bias_profile"] == "hybrid_large_guard"
    assert counts[0.0] > 0
    assert counts[2.0] + counts[2.5] > counts[0.0] + counts[0.5]


def test_prepare_package_identity_guard_adds_unseen_shape_families_and_bright_zero_guard(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_identity_guard_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=56,
        image_size=96,
        seed=6104,
        synthetic_bias_profile="identity_guard_v2",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    shape_families = {row.get("shape_family") for row in synthetic}
    bright_zero = [row for row in synthetic if row.get("polarity") == "bright" and float(row.get("bias_px")) == 0.0]
    dark_zero = [row for row in synthetic if row.get("polarity") == "dark" and float(row.get("bias_px")) == 0.0]

    assert {"annulus", "thin_bar", "circle", "ellipse", "rect", "polygon"}.issubset(shape_families)
    assert len(bright_zero) >= 2
    assert len(dark_zero) >= 2
    assert manifest["synthetic_bias_profile"] == "identity_guard_v2"


def test_prepare_package_small_bias_dark_thin_adds_guard_and_focus_cases(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_small_bias_dark_thin_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=112,
        image_size=96,
        seed=6105,
        synthetic_bias_profile="small_bias_dark_thin_v3",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    shape_counts = manifest["shape_family_counts"]
    small_guard = [row for row in synthetic if float(row.get("bias_px")) <= 0.5]
    dark_thin_large = [
        row
        for row in synthetic
        if row.get("polarity") == "dark" and row.get("shape_family") == "thin_bar" and float(row.get("bias_px")) >= 1.5
    ]

    assert manifest["synthetic_bias_profile"] == "small_bias_dark_thin_v3"
    assert len(small_guard) >= len(synthetic) // 2
    assert len(dark_thin_large) >= 4
    assert int(shape_counts["thin_bar"]) > int(shape_counts["circle"])
    assert int(shape_counts["thin_bar"]) > int(shape_counts["annulus"])


def test_prepare_package_small_bias_guard_has_no_large_synthetic_offsets(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_small_bias_guard_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=84,
        image_size=96,
        seed=6106,
        synthetic_bias_profile="small_bias_guard_v4",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    large_offsets = [row for row in synthetic if float(row.get("bias_px", 0.0)) > 0.5]
    shape_counts = manifest["shape_family_counts"]

    assert manifest["synthetic_bias_profile"] == "small_bias_guard_v4"
    assert not large_offsets
    assert {0.0, 0.25, 0.5}.issubset({float(row["bias_px"]) for row in synthetic})
    assert int(shape_counts["thin_bar"]) > 0
    assert int(shape_counts["annulus"]) > 0


def test_prepare_package_failure_balanced_replay_has_bright_small_and_ellipse_focus(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_failure_balanced_replay_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=120,
        image_size=96,
        seed=6107,
        synthetic_bias_profile="failure_balanced_replay_v6",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    bright_small = [
        row
        for row in synthetic
        if row.get("polarity") == "bright" and float(row.get("bias_px", 99.0)) <= 0.5
    ]
    large_offsets = [row for row in synthetic if float(row.get("bias_px", 0.0)) >= 1.5]
    shape_counts = manifest["shape_family_counts"]

    assert manifest["synthetic_bias_profile"] == "failure_balanced_replay_v6"
    assert len(bright_small) >= len(synthetic) // 5
    assert len(large_offsets) >= len(synthetic) // 4
    assert int(shape_counts["ellipse"]) > int(shape_counts["circle"])
    assert int(shape_counts["ellipse"]) >= int(shape_counts["thin_bar"])


def test_prepare_package_failure_balanced_shape_neutral_keeps_shape_balance(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_failure_balanced_shape_neutral_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=140,
        image_size=96,
        seed=6109,
        synthetic_bias_profile="failure_balanced_shape_neutral_v7",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    bright_small = [
        row
        for row in synthetic
        if row.get("polarity") == "bright" and float(row.get("bias_px", 99.0)) <= 0.5
    ]
    large_offsets = [row for row in synthetic if float(row.get("bias_px", 0.0)) >= 1.5]
    shape_counts = {key: int(value) for key, value in manifest["shape_family_counts"].items() if key != "unknown"}

    assert manifest["synthetic_bias_profile"] == "failure_balanced_shape_neutral_v7"
    assert len(bright_small) >= len(synthetic) // 5
    assert len(large_offsets) >= len(synthetic) // 4
    assert shape_counts["ellipse"] == shape_counts["circle"]
    assert max(shape_counts.values()) - min(shape_counts.values()) <= 2


def test_prepare_package_bright_curve_replay_emphasizes_bright_mid_large_curve_shapes(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_bright_curve_replay_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=144,
        image_size=96,
        seed=6111,
        synthetic_bias_profile="bright_curve_replay_v8",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    bright_mid_large = [
        row
        for row in synthetic
        if row.get("polarity") == "bright" and float(row.get("bias_px", 0.0)) >= 1.0
    ]
    dark_guard = [
        row
        for row in synthetic
        if row.get("polarity") == "dark" and float(row.get("bias_px", 0.0)) in {0.0, 0.5, 2.5}
    ]
    shape_counts = {key: int(value) for key, value in manifest["shape_family_counts"].items() if key != "unknown"}

    assert manifest["synthetic_bias_profile"] == "bright_curve_replay_v8"
    assert len(bright_mid_large) >= len(synthetic) // 4
    assert len(dark_guard) >= len(synthetic) // 6
    assert shape_counts["ellipse"] >= shape_counts["circle"]
    assert shape_counts["annulus"] >= shape_counts["circle"]
    assert shape_counts["rect"] >= shape_counts["circle"]


def test_prepare_package_rotated_rect_guard_emphasizes_rect_and_keeps_curve_shapes(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_rotated_rect_guard_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2}],
        synthetic_count=160,
        image_size=96,
        seed=6115,
        synthetic_bias_profile="rotated_rect_guard_v10",
    )

    manifest = json.loads((Path(summary["package_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    synthetic = [row for row in manifest["pairs"] if row.get("role") == "universal_synthetic"]
    rect_rows = [row for row in synthetic if row.get("shape_family") == "rect"]
    curve_rows = [
        row
        for row in synthetic
        if row.get("shape_family") in {"ellipse", "annulus", "polygon"}
    ]
    shape_counts = {key: int(value) for key, value in manifest["shape_family_counts"].items() if key != "unknown"}

    assert manifest["synthetic_bias_profile"] == "rotated_rect_guard_v10"
    assert len(rect_rows) > len(synthetic) // 4
    assert len(curve_rows) >= len(synthetic) // 3
    assert shape_counts["rect"] > shape_counts["ellipse"]
    assert shape_counts["rect"] > shape_counts["annulus"]
    assert shape_counts["polygon"] >= shape_counts["circle"]


def test_prepare_package_motion_guard_adds_known_shift_pairs_without_replacing_old_roles(tmp_path: Path):
    module = load_module()
    legacy_shape = _make_fixture_package(tmp_path, "legacy_shape_pkg", "legacy_shape", count=2)
    sequence_guard = _make_fixture_package(tmp_path, "sequence_guard_pkg", "sequence_guard", count=2)
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_motion_guard_train",
        legacy_sources=[
            {"role": "legacy_shape", "package_dir": legacy_shape, "limit": 2},
            {"role": "sequence_guard", "package_dir": sequence_guard, "limit": 2},
            {"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2},
        ],
        synthetic_count=8,
        motion_count=4,
        image_size=96,
        seed=6111,
        synthetic_bias_profile="rotated_rect_guard_v10",
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    motion_rows = [row for row in manifest["pairs"] if row.get("role") == "motion_synthetic"]
    assert manifest["role_counts"]["legacy_shape"] == 2
    assert manifest["role_counts"]["sequence_guard"] == 2
    assert manifest["role_counts"]["sem_truth_anchor"] == 2
    assert manifest["role_counts"]["universal_synthetic"] == 8
    assert manifest["role_counts"]["motion_synthetic"] == 8
    assert manifest["motion_pair_count"] == 4
    assert len(motion_rows) == 8

    frame1_rows = [row for row in motion_rows if int(row.get("motion_frame", -1)) == 1]
    assert len(frame1_rows) == 4
    for row in frame1_rows:
        meta_rel = row["motion_meta"]
        meta = json.loads((package / meta_rel).read_text(encoding="utf-8"))
        delta = meta["delta_from_prev_px"]
        assert abs(float(delta["dx"])) > 0.0 or abs(float(delta["dy"])) > 0.0
        assert (package / row["package_src"]).exists()
        assert (package / row["package_lbl"]).exists()
        assert (package / row["geometry_boundary"]).exists()
        assert (package / row["geometry_centerline"]).exists()
        assert (package / row["geometry_distance"]).exists()


def test_prepare_package_texture_motion_adds_camera_like_shift_pairs_without_same_sample_leakage(tmp_path: Path):
    module = load_module()
    legacy_shape = _make_fixture_package(tmp_path, "legacy_shape_pkg", "legacy_shape", count=2)
    sequence_guard = _make_fixture_package(tmp_path, "sequence_guard_pkg", "sequence_guard", count=2)
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_motion_texture_train",
        legacy_sources=[
            {"role": "legacy_shape", "package_dir": legacy_shape, "limit": 2},
            {"role": "sequence_guard", "package_dir": sequence_guard, "limit": 2},
            {"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2},
        ],
        synthetic_count=8,
        motion_count=4,
        motion_texture_count=3,
        image_size=96,
        seed=6112,
        synthetic_bias_profile="motion_guard_v11",
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    texture_rows = [row for row in manifest["pairs"] if row.get("role") == "motion_texture_synthetic"]
    assert manifest["role_counts"]["legacy_shape"] == 2
    assert manifest["role_counts"]["motion_synthetic"] == 8
    assert manifest["role_counts"]["motion_texture_synthetic"] == 6
    assert manifest["motion_pair_count"] == 7
    assert manifest["motion_texture_pair_count"] == 3
    assert len(texture_rows) == 6
    assert {row.get("texture_domain") for row in texture_rows} == {"procedural_camera_texture_v1"}
    assert {row.get("label_source") for row in texture_rows} == {"known_synthetic_motion_truth"}
    assert all(row.get("anti_answer_leakage") is True for row in texture_rows)

    frame0 = next(row for row in texture_rows if int(row.get("motion_frame", -1)) == 0)
    src = cv2.imread(str(package / frame0["package_src"]), cv2.IMREAD_GRAYSCALE)
    lbl = cv2.imread(str(package / frame0["package_lbl"]), cv2.IMREAD_GRAYSCALE)
    assert src is not None
    assert lbl is not None
    background = np.abs(lbl.astype(np.int16) - 128) < 8
    assert float(src[background].std()) > 3.0


def test_prepare_package_step_guard_motion_texture_adds_known_step_like_pairs_without_real_step_leakage(tmp_path: Path):
    module = load_module()
    legacy_shape = _make_fixture_package(tmp_path, "legacy_shape_pkg", "legacy_shape", count=2)
    sequence_guard = _make_fixture_package(tmp_path, "sequence_guard_pkg", "sequence_guard", count=2)
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=2)

    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_step_guard_motion_texture_train",
        legacy_sources=[
            {"role": "legacy_shape", "package_dir": legacy_shape, "limit": 2},
            {"role": "sequence_guard", "package_dir": sequence_guard, "limit": 2},
            {"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 2},
        ],
        synthetic_count=12,
        motion_count=2,
        motion_texture_count=2,
        step_guard_count=8,
        image_size=96,
        seed=6116,
        synthetic_bias_profile="step_guard_v16",
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    step_rows = [row for row in manifest["pairs"] if row.get("role") == "step_guard_motion_texture_synthetic"]
    frame1 = [row for row in step_rows if int(row.get("motion_frame", -1)) == 1]
    deltas = {
        (round(float(row.get("motion_dx_px", 0.0)), 3), round(float(row.get("motion_dy_px", 0.0)), 3))
        for row in frame1
    }

    assert manifest["role_counts"]["legacy_shape"] == 2
    assert manifest["role_counts"]["sequence_guard"] == 2
    assert manifest["role_counts"]["sem_truth_anchor"] == 2
    assert manifest["role_counts"]["motion_synthetic"] == 4
    assert manifest["role_counts"]["motion_texture_synthetic"] == 4
    assert manifest["role_counts"]["step_guard_motion_texture_synthetic"] == 16
    assert manifest["motion_pair_count"] == 12
    assert manifest["step_guard_motion_pair_count"] == 8
    assert len(step_rows) == 16
    assert (0.0, 0.0) in deltas
    assert any(max(abs(dx), abs(dy)) == 0.8 for dx, dy in deltas)
    assert any(max(abs(dx), abs(dy)) == 8.0 for dx, dy in deltas)
    assert {"annulus", "ellipse"}.issubset({row.get("shape_family") for row in step_rows})
    assert {row.get("texture_domain") for row in step_rows} == {"procedural_step_guard_texture_v1"}
    assert {row.get("label_source") for row in step_rows} == {"known_synthetic_step_guard_motion_truth"}
    assert all(row.get("anti_answer_leakage") is True for row in step_rows)
    assert all(row.get("no_real_sample_pixels") is True for row in step_rows)
    assert all(row.get("real_step_data_used") is False for row in step_rows)


def test_grouped_split_keeps_same_geometry_out_of_both_train_and_val(tmp_path: Path):
    module = load_module()
    legacy_shape = _make_fixture_package(tmp_path, "legacy_shape_pkg", "legacy_shape", count=6)
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=6)
    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_split_train",
        legacy_sources=[
            {"role": "legacy_shape", "package_dir": legacy_shape, "limit": 6},
            {"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 6},
        ],
        synthetic_count=12,
        image_size=96,
        seed=6102,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    split = module.prepare_grouped_fixed_split(
        package_dir=package,
        manifest=manifest,
        val_ratio=0.25,
        seed=1337,
    )
    split_dir = Path(split["split_dir"])
    train_idx = np.load(split_dir / "train_idx.npy")
    val_idx = np.load(split_dir / "val_idx.npy")
    source_paths = split["source_paths_sorted"]
    pair_by_src = {row["package_src"]: row for row in manifest["pairs"]}

    train_groups = {module.group_key_for_pair(pair_by_src[source_paths[int(i)]]) for i in train_idx}
    val_groups = {module.group_key_for_pair(pair_by_src[source_paths[int(i)]]) for i in val_idx}

    assert train_groups
    assert val_groups
    assert train_groups.isdisjoint(val_groups)
    assert split["group_overlap_count"] == 0
    assert "universal_synthetic:bright" in split["train_strata"] + split["val_strata"]
    assert "universal_synthetic:dark" in split["train_strata"] + split["val_strata"]


def test_grouped_split_keeps_motion_sequence_frames_together(tmp_path: Path):
    module = load_module()
    sem_truth = _make_fixture_package(tmp_path, "sem_truth_pkg", "sem_truth_anchor", count=4)
    summary = module.prepare_package(
        output_root=tmp_path / "out",
        package_name="r61_test_motion_split_train",
        legacy_sources=[{"role": "sem_truth_anchor", "package_dir": sem_truth, "limit": 4}],
        synthetic_count=12,
        motion_count=8,
        image_size=96,
        seed=6120,
        synthetic_bias_profile="motion_guard_v11",
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    split = module.prepare_grouped_fixed_split(
        package_dir=package,
        manifest=manifest,
        val_ratio=0.35,
        seed=1337,
    )
    train_idx = set(np.load(Path(split["split_dir"]) / "train_idx.npy").tolist())
    val_idx = set(np.load(Path(split["split_dir"]) / "val_idx.npy").tolist())
    source_paths = split["source_paths_sorted"]
    pair_by_src = {row["package_src"]: row for row in manifest["pairs"]}
    sequence_to_splits: dict[str, set[str]] = {}
    for idx, src in enumerate(source_paths):
        row = pair_by_src[src]
        seq_id = row.get("motion_sequence_id")
        if not seq_id:
            continue
        bucket = "train" if idx in train_idx else "val" if idx in val_idx else "missing"
        sequence_to_splits.setdefault(str(seq_id), set()).add(bucket)

    assert sequence_to_splits
    assert all(len(splits) == 1 for splits in sequence_to_splits.values())
