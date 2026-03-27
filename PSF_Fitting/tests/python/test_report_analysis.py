import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

PSF_FITTING_ROOT = Path(__file__).resolve().parents[2]
HELPER_ROOT = PSF_FITTING_ROOT / "PSF_Report_Helper"
sys.path.insert(0, str(HELPER_ROOT))

from run_report_analysis import render_montage, run_analysis, select_data_sources


def _build_synthetic_dataset(
    root: Path,
    grid_shape: tuple[int, int] = (3, 3),
    csv_rows: int | None = None,
    invalid_shapes: bool = False,
) -> tuple[Path, Path]:
    fits_dir = root / "Fits"
    fits_dir.mkdir(parents=True, exist_ok=True)

    yy, xx = np.mgrid[-5:6, -5:6]
    grid_rows, grid_cols = grid_shape
    psf_grid = np.zeros((11, 11, grid_rows, grid_cols), dtype=float)
    fval_map = np.zeros((grid_rows, grid_cols), dtype=float)
    iterations_map = np.zeros((grid_rows, grid_cols), dtype=float)
    coef_grid = np.zeros((15, grid_rows, grid_cols), dtype=float)

    for row in range(grid_rows):
        for col in range(grid_cols):
            sigma_x = 1.0 + 0.2 * row
            sigma_y = 1.1 + 0.15 * col
            psf = np.exp(-((xx / sigma_x) ** 2 + (yy / sigma_y) ** 2))
            psf_grid[:, :, row, col] = psf / psf.sum()
            fval_map[row, col] = 100 + row * 10 + col
            iterations_map[row, col] = 50 + row + col
            coef_grid[:, row, col] = np.linspace(0, 1, 15)

    if invalid_shapes:
        fval_map = fval_map[:-1, :]

    mat_path = fits_dir / "PSF_fitted_2D_FOVstack.mat"
    savemat(
        mat_path,
        {
            "psf_grid": psf_grid,
            "coef_grid": coef_grid,
            "fval_map": fval_map,
            "iterations_map": iterations_map,
            "grid_rows": grid_rows,
            "grid_cols": grid_cols,
        },
    )

    csv_path = fits_dir / "batch_results.csv"
    total_rows = csv_rows if csv_rows is not None else grid_rows * grid_cols
    lines = ["filename,fval,iterations,seconds"]
    for idx in range(total_rows):
        lines.append(f"img_{idx+1}.bmp,{100+idx},{50+idx},1.{idx}")
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mat_path, csv_path


def test_run_analysis_creates_required_outputs(tmp_path: Path) -> None:
    mat_path, csv_path = _build_synthetic_dataset(tmp_path)
    output_root = tmp_path / "helper_outputs"

    result = run_analysis(
        repo_root=tmp_path,
        helper_root=tmp_path,
        output_root=output_root,
        preferred_mat=mat_path,
        preferred_csv=csv_path,
    )

    required_paths = [
        result.inventory_path,
        result.summary_report_path,
        result.report_draft_path,
        output_root / "figures" / "psf_montage.png",
        output_root / "figures" / "psf_montage_log_normalized.png",
        output_root / "figures" / "psf_representative_comparison.png",
        output_root / "figures" / "fval_heatmap.png",
        output_root / "tables" / "summary_stats.csv",
    ]

    for path in required_paths:
        assert path.exists(), f"missing output: {path}"

    summary_text = result.summary_report_path.read_text(encoding="utf-8")
    assert "中心位置" in summary_text
    assert "fval" in summary_text


def test_render_montage_supports_single_column_fov(tmp_path: Path) -> None:
    mat_path, _ = _build_synthetic_dataset(tmp_path, grid_shape=(3, 1))
    output_path = tmp_path / "single_col_montage.png"

    from scipy.io import loadmat

    psf_grid = loadmat(mat_path)["psf_grid"]
    render_montage(psf_grid, output_path, normalize_each=False, log_scale=False)

    assert output_path.exists()


def test_run_analysis_fails_on_inconsistent_mat_and_csv(tmp_path: Path) -> None:
    mat_path, csv_path = _build_synthetic_dataset(tmp_path, csv_rows=2, invalid_shapes=True)

    with pytest.raises(ValueError, match="資料一致性檢查失敗"):
        run_analysis(
            repo_root=tmp_path,
            helper_root=tmp_path,
            output_root=tmp_path / "helper_outputs",
            preferred_mat=mat_path,
            preferred_csv=csv_path,
        )


def test_select_data_sources_uses_sibling_csv_when_only_mat_path_is_given(tmp_path: Path) -> None:
    mat_path, csv_path = _build_synthetic_dataset(tmp_path)

    selection = select_data_sources(tmp_path, preferred_mat=mat_path, preferred_csv=None)

    assert selection.mat_path == mat_path.resolve()
    assert selection.csv_path == csv_path.resolve()
    assert "同目錄" in selection.reason


def test_select_data_sources_fails_if_single_sided_override_has_no_sibling(tmp_path: Path) -> None:
    mat_path, csv_path = _build_synthetic_dataset(tmp_path)
    csv_path.unlink()

    with pytest.raises(FileNotFoundError, match="同目錄"):
        select_data_sources(tmp_path, preferred_mat=mat_path, preferred_csv=None)


def test_select_data_sources_uses_sibling_mat_when_only_csv_path_is_given(tmp_path: Path) -> None:
    mat_path, csv_path = _build_synthetic_dataset(tmp_path)

    selection = select_data_sources(tmp_path, preferred_mat=None, preferred_csv=csv_path)

    assert selection.mat_path == mat_path.resolve()
    assert selection.csv_path == csv_path.resolve()
    assert "同目錄" in selection.reason
