from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_r60_sem_truth_dataset.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_r60_sem_truth_dataset", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    image = np.full((256, 256), 82, np.uint8)
    cv2.circle(image, (78, 78), 19, 145, -1, lineType=cv2.LINE_AA)
    cv2.circle(image, (178, 78), 24, 45, -1, lineType=cv2.LINE_AA)
    cv2.circle(image, (78, 178), 20, 150, -1, lineType=cv2.LINE_AA)
    cv2.circle(image, (178, 178), 23, 42, -1, lineType=cv2.LINE_AA)
    image_path = tmp_path / "Image__fixture.bmp"
    _write_bmp(image_path, image)

    template_rows = [
        {
            "image": "原圖",
            "feature": "圓柱",
            "id": 1,
            "x_px": 78,
            "y_px": 78,
            "radius_px": 19,
            "clean_for_summary": 1,
        },
        {
            "image": "原圖",
            "feature": "圓孔",
            "id": 1,
            "x_px": 178,
            "y_px": 78,
            "radius_px": 24,
            "clean_for_summary": 1,
        },
        {
            "image": "原圖",
            "feature": "圓柱",
            "id": 2,
            "x_px": 78,
            "y_px": 178,
            "radius_px": 20,
            "clean_for_summary": 1,
        },
        {
            "image": "原圖",
            "feature": "圓孔",
            "id": 2,
            "x_px": 178,
            "y_px": 178,
            "radius_px": 23,
            "clean_for_summary": 1,
        },
    ]
    template_csv = tmp_path / "template.csv"
    _write_csv(
        template_csv,
        template_rows,
        ["image", "feature", "id", "x_px", "y_px", "radius_px", "clean_for_summary"],
    )

    sem_rows = [
        {"index": 1, "圓孔_sem_radius_nm": 1650.0, "圓柱_sem_radius_nm": 1320.0},
        {"index": 2, "圓孔_sem_radius_nm": 1630.0, "圓柱_sem_radius_nm": 1340.0},
    ]
    sem_csv = tmp_path / "sem_reference.csv"
    _write_csv(sem_csv, sem_rows, ["index", "圓孔_sem_radius_nm", "圓柱_sem_radius_nm"])
    return image_path, template_csv, sem_csv


def _write_inverted_polarity_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    image = np.full((256, 256), 82, np.uint8)
    cv2.circle(image, (78, 78), 19, 35, -1, lineType=cv2.LINE_AA)
    cv2.circle(image, (178, 78), 24, 145, -1, lineType=cv2.LINE_AA)
    image_path = tmp_path / "Image__inverted_fixture.bmp"
    _write_bmp(image_path, image)

    template_rows = [
        {
            "image": "原圖",
            "feature": "圓柱",
            "id": 1,
            "x_px": 78,
            "y_px": 78,
            "radius_px": 19,
            "clean_for_summary": 1,
        },
        {
            "image": "原圖",
            "feature": "圓孔",
            "id": 1,
            "x_px": 178,
            "y_px": 78,
            "radius_px": 24,
            "clean_for_summary": 1,
        },
    ]
    template_csv = tmp_path / "template_inverted.csv"
    _write_csv(
        template_csv,
        template_rows,
        ["image", "feature", "id", "x_px", "y_px", "radius_px", "clean_for_summary"],
    )
    sem_csv = tmp_path / "sem_reference_inverted.csv"
    _write_csv(
        sem_csv,
        [{"index": 1, "圓孔_sem_radius_nm": 1650.0, "圓柱_sem_radius_nm": 1320.0}],
        ["index", "圓孔_sem_radius_nm", "圓柱_sem_radius_nm"],
    )
    return image_path, template_csv, sem_csv


def test_prepare_package_builds_sem_truth_real_crop_and_anchor_pairs(tmp_path: Path):
    module = load_module()
    image_path, template_csv, sem_csv = _write_fixture_inputs(tmp_path)

    summary = module.prepare_package(
        microscope_image=image_path,
        template_csv=template_csv,
        sem_reference_csv=sem_csv,
        output_root=tmp_path / "out",
        package_name="r60_test_train",
        real_crop_count=4,
        anchor_count=2,
        crop_size=96,
        image_size=96,
        seed=6001,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["r60_sem_truth_boundary_training"] is True
    assert manifest["target_is_sem_truth"] is True
    assert manifest["real_crop_pairs"] == 4
    assert manifest["anchor_pairs"] == 2
    assert manifest["total_pairs"] == 6
    assert manifest["geometry_count"] == 6
    assert (package / "src" / "stage_60_hs100mg_real_crop").is_dir()
    assert (package / "src" / "stage_60_hs100mg_sem_anchor").is_dir()

    forbidden = {"class_shifts_px", "same_sample_calibration", "posthoc_cd_correction", "r59_cd_closed_loop"}
    for record in manifest["pairs"]:
        assert record["label_source"] == "sem_truth"
        assert record["target_radius_bias_nm"] == 0.0
        assert record["target_radius_nm"] == record["sem_radius_nm"]
        assert not forbidden.intersection(record)
        assert (package / record["package_src"]).exists()
        assert (package / record["package_lbl"]).exists()
        assert (package / record["geometry_boundary"]).exists()
        assert (package / record["geometry_centerline"]).exists()
        assert (package / record["geometry_distance"]).exists()


def test_real_crop_label_uses_per_feature_sem_radius(tmp_path: Path):
    module = load_module()
    image_path, template_csv, sem_csv = _write_fixture_inputs(tmp_path)

    summary = module.prepare_package(
        microscope_image=image_path,
        template_csv=template_csv,
        sem_reference_csv=sem_csv,
        output_root=tmp_path / "out",
        package_name="r60_test_train",
        real_crop_count=4,
        anchor_count=0,
        crop_size=96,
        image_size=96,
        seed=6002,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    records = {(row["feature"], int(row["sem_reference_id"])): row for row in manifest["pairs"]}
    assert records[("pillar", 1)]["target_radius_nm"] == 1320.0
    assert records[("via", 1)]["target_radius_nm"] == 1650.0
    assert records[("pillar", 2)]["target_radius_nm"] == 1340.0
    assert records[("via", 2)]["target_radius_nm"] == 1630.0


def test_real_crop_sources_preserve_microscope_texture(tmp_path: Path):
    module = load_module()
    image_path, template_csv, sem_csv = _write_fixture_inputs(tmp_path)

    summary = module.prepare_package(
        microscope_image=image_path,
        template_csv=template_csv,
        sem_reference_csv=sem_csv,
        output_root=tmp_path / "out",
        package_name="r60_test_train",
        real_crop_count=1,
        anchor_count=0,
        crop_size=96,
        image_size=96,
        seed=6003,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    record = manifest["pairs"][0]
    assert record["source_group"] == "hs100mg_real_crop"
    src = cv2.imdecode(np.fromfile(str(package / record["package_src"]), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    lbl = cv2.imdecode(np.fromfile(str(package / record["package_lbl"]), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    assert src is not None and lbl is not None
    assert src.shape == (96, 96)
    assert lbl.shape == (96, 96)
    assert float(src.std()) > 1.0
    assert not np.array_equal(src, lbl)


def test_real_crop_label_keeps_neighbor_features_inside_crop(tmp_path: Path):
    module = load_module()
    image_path, template_csv, sem_csv = _write_fixture_inputs(tmp_path)

    summary = module.prepare_package(
        microscope_image=image_path,
        template_csv=template_csv,
        sem_reference_csv=sem_csv,
        output_root=tmp_path / "out",
        package_name="r60_test_train",
        real_crop_count=1,
        anchor_count=0,
        crop_size=192,
        image_size=192,
        seed=6004,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    record = manifest["pairs"][0]
    assert record["source_group"] == "hs100mg_real_crop"
    assert record["label_neighbor_features"] >= 3


def test_real_crop_repeat_upsamples_real_microscope_pairs(tmp_path: Path):
    module = load_module()
    image_path, template_csv, sem_csv = _write_fixture_inputs(tmp_path)

    summary = module.prepare_package(
        microscope_image=image_path,
        template_csv=template_csv,
        sem_reference_csv=sem_csv,
        output_root=tmp_path / "out",
        package_name="r60_test_train",
        real_crop_count=4,
        real_crop_repeat=3,
        anchor_count=0,
        crop_size=96,
        image_size=96,
        seed=6005,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    real_records = [row for row in manifest["pairs"] if row["source_group"] == "hs100mg_real_crop"]
    assert manifest["real_crop_unique_pairs"] == 4
    assert manifest["real_crop_repeat"] == 3
    assert manifest["real_crop_pairs"] == 12
    assert len(real_records) == 12
    assert sorted({row["repeat_index"] for row in real_records}) == [0, 1, 2]


def test_real_crop_label_polarity_follows_microscope_source(tmp_path: Path):
    module = load_module()
    image_path, template_csv, sem_csv = _write_inverted_polarity_fixture(tmp_path)

    summary = module.prepare_package(
        microscope_image=image_path,
        template_csv=template_csv,
        sem_reference_csv=sem_csv,
        output_root=tmp_path / "out",
        package_name="r60_test_train",
        real_crop_count=2,
        anchor_count=0,
        crop_size=96,
        image_size=96,
        seed=6006,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    for record in manifest["pairs"]:
        src = cv2.imdecode(np.fromfile(str(package / record["package_src"]), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        lbl = cv2.imdecode(np.fromfile(str(package / record["package_lbl"]), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        assert src is not None and lbl is not None
        src_delta = float(src[48, 48]) - float(src[6, 6])
        lbl_delta = float(lbl[48, 48]) - float(lbl[6, 6])
        assert src_delta * lbl_delta > 0
