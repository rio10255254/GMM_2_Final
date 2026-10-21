from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_center9_cd import (  # noqa: E402
    build_center9_table,
    summarize_cd,
    symmetric_improvement_limit,
)


ROOT = PACKAGE.parents[1]
SOURCE_WIDE = (
    ROOT
    / "Final_Data_Figures"
    / "20260710_v42_full_validation"
    / "tables"
    / "cd"
    / "100mg_center36_individual_cd_wide.csv"
)
SEM_WORKBOOK = ROOT / "20260618_100MG" / "SEM_data" / "via_pilar.xlsx"
RAW_IMAGE = ROOT / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
V42_IMAGE = (
    ROOT
    / "Final_Data_Figures"
    / "20260710_v42_full_validation"
    / "reconstructions"
    / "reconstruct_progress_epoch_120_in_20260618_100MG_20260709_202713"
    / "100mg_static"
    / "Image__2026-06-18__17-10-31.bmp"
)


def test_build_center9_table_locks_nine_unique_sem_identities() -> None:
    table = build_center9_table(
        SOURCE_WIDE,
        SEM_WORKBOOK,
        raw_image=RAW_IMAGE,
        v42_image=V42_IMAGE,
    )

    assert len(table) == 9
    assert table["sem_index"].is_unique
    assert table["sem_excel_cell"].is_unique
    assert list(table["sem_index"]) == [22, 23, 24, 28, 29, 30, 34, 35, 36]
    assert list(table["sem_excel_cell"]) == [
        "L8",
        "K8",
        "J8",
        "L9",
        "K9",
        "J9",
        "L10",
        "K10",
        "J10",
    ]
    assert list(table["sem_radius_nm"]) == pytest.approx(
        [
            1321.1577900710545,
            1310.0081858573494,
            1310.107187203283,
            1329.306896598824,
            1304.3597689145038,
            1310.214278589038,
            1338.3982848246214,
            1299.3758269507834,
            1310.8899993469824,
        ]
    )
    assert set(table["sem_mapping_status"]) == {"corrected_horizontal_mirror"}
    assert (table["superseded_source_sem_excel_cell"] != table["sem_excel_cell"]).all()


def test_build_center9_table_uses_same_optical_positions_for_raw_and_v42() -> None:
    table = build_center9_table(
        SOURCE_WIDE,
        SEM_WORKBOOK,
        raw_image=RAW_IMAGE,
        v42_image=V42_IMAGE,
    )

    assert list(zip(table.optical_grid_row, table.optical_grid_col)) == [
        (4, 4),
        (4, 5),
        (4, 6),
        (5, 4),
        (5, 5),
        (5, 6),
        (6, 4),
        (6, 5),
        (6, 6),
    ]
    assert set(table.capture_transform) == {"flip_x"}
    assert set(table.raw_source_image) == {str(RAW_IMAGE)}
    assert set(table.v42_source_image) == {str(V42_IMAGE)}
    assert table[["x_px", "y_px"]].notna().all().all()
    assert table["raw_x_px"].equals(table["v42_x_px"])
    assert table["raw_y_px"].equals(table["v42_y_px"])
    assert table["raw_x_px"].equals(table["x_px"])
    assert table["raw_y_px"].equals(table["y_px"])


def test_build_center9_table_rejects_wrong_v42_trace() -> None:
    with pytest.raises(ValueError, match="V42 image does not match"):
        build_center9_table(
            SOURCE_WIDE,
            SEM_WORKBOOK,
            raw_image=RAW_IMAGE,
            v42_image=RAW_IMAGE,
        )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("grid_row", 4.9, "whole numbers"),
        ("clean_for_summary", 0, "not clean"),
        ("raw_status", "bad_crossing", "invalid measurement"),
        ("v42_e120_diameter_um", float("nan"), "finite positive"),
    ],
)
def test_build_center9_table_rejects_invalid_source_measurements(
    tmp_path: Path, column: str, value: object, message: str
) -> None:
    source = pd.read_csv(SOURCE_WIDE)
    target = source[
        (source["feature_key"] == "pillar")
        & (source["grid_row"] == 4)
        & (source["grid_col"] == 4)
    ].index[0]
    if column in {"grid_row", "grid_col"}:
        source[column] = source[column].astype(float)
    source.loc[target, column] = value
    changed = tmp_path / "changed.csv"
    source.to_csv(changed, index=False)

    with pytest.raises(ValueError, match=message):
        build_center9_table(
            changed,
            SEM_WORKBOOK,
            raw_image=RAW_IMAGE,
            v42_image=V42_IMAGE,
            source_manifest=(
                ROOT
                / "Final_Data_Figures"
                / "20260710_v42_full_validation"
                / "cd_validation_manifest.json"
            ),
        )


def test_improvement_scale_is_symmetric_and_shows_regression() -> None:
    assert symmetric_improvement_limit([-12.0, 3.0, 8.0]) == pytest.approx(12.0)


def test_center9_cd_summary_recomputes_corrected_headline_values() -> None:
    table = build_center9_table(
        SOURCE_WIDE,
        SEM_WORKBOOK,
        raw_image=RAW_IMAGE,
        v42_image=V42_IMAGE,
    )
    summary = summarize_cd(table).set_index("case")

    assert summary.loc["raw", "mean_abs_error_nm"] == pytest.approx(92.9908175875)
    assert summary.loc["v42_e120", "mean_abs_error_nm"] == pytest.approx(78.1769123652)
    assert summary.loc["v42_e120", "improved_vs_raw_count"] == 9
    assert summary.loc["v42_e120", "total_count"] == 9
    assert summary.loc["v42_e120", "mean_abs_improvement_pct"] == pytest.approx(
        15.9305026444
    )
