from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from Tools.organize_final_data_figures_for_thesis import (
    build_original_inventory,
    classify_relative_path,
    copy_and_verify_inventory,
    remove_verified_sources,
    verify_reconciliation,
)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_classifies_only_current_v42_sources_as_retained() -> None:
    assert classify_relative_path(
        Path("PSF_Experiment_Results_Analysis/README.md")
    ) == ("retained", Path("03_PSF_EXPERIMENT_RESULTS/README.md"))
    assert classify_relative_path(
        Path(
            "20260710_v42_full_validation/reconstructions/"
            "reconstruct_progress_epoch_120_in_bmp_20260709_202713/20x_1um/frame_0001.bmp"
        )
    ) == (
        "retained",
        Path("02_V42_E120_SOURCE_MATERIAL/reconstructions/20x_1um/frame_0001.bmp"),
    )
    assert classify_relative_path(
        Path(
            "20260710_v42_full_validation/reconstructions/"
            "reconstruct_progress_epoch_120_in_bmp_20260709_202713/5x_1um/frame_0001.bmp"
        )
    )[0] == "archive"
    assert classify_relative_path(
        Path(
            "20260710_v42_full_validation/tables/cd/"
            "100mg_center36_individual_cd_wide.csv"
        )
    )[0] == "archive"
    assert classify_relative_path(
        Path("20260712_sem_anchored_center9_validation/REPORT.md")
    )[0] == "archive"


def test_copy_verifies_before_sources_are_removed(tmp_path: Path) -> None:
    source = tmp_path / "Final_Data_Figures"
    archive = tmp_path / "Archive" / "Final_Data_Figures_Superseded_20260713"
    _write(source / "old_result/report.md", b"old")
    _write(source / "PSF_Experiment_Results_Analysis/README.md", b"psf")
    records = build_original_inventory(source, archive)

    copy_and_verify_inventory(records)

    assert (source / "old_result/report.md").is_file()
    assert (source / "PSF_Experiment_Results_Analysis/README.md").is_file()
    assert (archive / "old_result/report.md").read_bytes() == b"old"
    retained = source / "03_PSF_EXPERIMENT_RESULTS/README.md"
    assert retained.read_bytes() == b"psf"
    verify_reconciliation(records)

    remove_verified_sources(records)
    assert not (source / "old_result/report.md").exists()
    assert not (source / "PSF_Experiment_Results_Analysis/README.md").exists()
    assert retained.is_file()


def test_existing_different_destination_is_never_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "Final_Data_Figures"
    archive = tmp_path / "Archive" / "Final_Data_Figures_Superseded_20260713"
    original = source / "old_result/report.md"
    destination = archive / "old_result/report.md"
    _write(original, b"original")
    _write(destination, b"different")
    records = build_original_inventory(source, archive)

    with pytest.raises(FileExistsError):
        copy_and_verify_inventory(records)

    assert original.read_bytes() == b"original"
    assert destination.read_bytes() == b"different"


def test_matching_destination_allows_safe_resume_without_rewrite(tmp_path: Path) -> None:
    source = tmp_path / "Final_Data_Figures"
    archive = tmp_path / "Archive" / "Final_Data_Figures_Superseded_20260713"
    original = source / "old_result/report.md"
    destination = archive / "old_result/report.md"
    _write(original, b"same")
    _write(destination, b"same")
    before = destination.stat().st_mtime_ns
    records = build_original_inventory(source, archive)

    copy_and_verify_inventory(records)

    assert destination.stat().st_mtime_ns == before
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == records[0].sha256
