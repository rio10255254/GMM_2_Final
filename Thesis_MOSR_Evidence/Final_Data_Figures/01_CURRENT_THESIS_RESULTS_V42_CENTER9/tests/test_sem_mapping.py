from __future__ import annotations

import sys
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from center9_core import (  # noqa: E402
    center9_identity_map,
    infer_quadrant_transform,
    transform_grid_coordinate,
)


SEM_WORKBOOK = (
    PACKAGE.parents[1]
    / "20260618_100MG"
    / "SEM_data"
    / "via_pilar.xlsx"
)


def test_quadrant_geometry_uniquely_proves_horizontal_mirror() -> None:
    physical_layout = (
        ("vertical_lines", "pillar"),
        ("via", "horizontal_lines"),
    )
    capture_20260618 = (
        ("pillar", "vertical_lines"),
        ("horizontal_lines", "via"),
    )

    transform = infer_quadrant_transform(physical_layout, capture_20260618)

    assert transform == "flip_x"


def test_center9_exact_sem_to_optical_identity_map() -> None:
    rows = center9_identity_map(SEM_WORKBOOK, capture_transform="flip_x")

    actual = [
        (
            row.sem_excel_cell,
            row.sem_index,
            row.optical_grid_row,
            row.optical_grid_col,
        )
        for row in rows
    ]
    assert actual == [
        ("J8", 24, 4, 6),
        ("K8", 23, 4, 5),
        ("L8", 22, 4, 4),
        ("J9", 30, 5, 6),
        ("K9", 29, 5, 5),
        ("L9", 28, 5, 4),
        ("J10", 36, 6, 6),
        ("K10", 35, 6, 5),
        ("L10", 34, 6, 4),
    ]


def test_center9_values_are_read_from_workbook_and_doubled_to_diameter() -> None:
    rows = center9_identity_map(SEM_WORKBOOK, capture_transform="flip_x")
    by_cell = {row.sem_excel_cell: row for row in rows}

    assert by_cell["J8"].sem_radius_nm == pytest.approx(1310.107187203283)
    assert by_cell["J8"].sem_diameter_um == pytest.approx(2.620214374406566)
    assert by_cell["L10"].sem_radius_nm == pytest.approx(1338.3982848246214)
    assert by_cell["L10"].sem_diameter_um == pytest.approx(2.676796569649243)


def test_ambiguous_quadrant_layout_is_rejected() -> None:
    repeated = (("circle", "circle"), ("line", "line"))

    with pytest.raises(ValueError, match="unique"):
        infer_quadrant_transform(repeated, repeated)


@pytest.mark.parametrize(
    ("transform", "expected"),
    [
        ("identity", (2, 3)),
        ("rot90_cw", (3, 5)),
        ("rot180", (5, 4)),
        ("rot270_cw", (4, 2)),
        ("flip_x", (2, 4)),
        ("flip_y", (5, 3)),
        ("transpose", (3, 2)),
        ("anti_transpose", (4, 5)),
    ],
)
def test_coordinate_transforms_preserve_direction(
    transform: str, expected: tuple[int, int]
) -> None:
    assert transform_grid_coordinate(2, 3, grid_size=6, transform=transform) == expected


def test_coordinate_transform_rejects_non_integer_grid_values() -> None:
    with pytest.raises(ValueError, match="integer"):
        transform_grid_coordinate(1.9, 3, grid_size=6, transform="identity")
