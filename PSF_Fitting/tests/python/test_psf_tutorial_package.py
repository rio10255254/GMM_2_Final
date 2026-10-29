from __future__ import annotations

from pathlib import Path
import sys

import nbformat
PROJECT_ROOT = Path(__file__).resolve().parents[3]

PSF_FITTING_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PSF_FITTING_ROOT))


def test_tutorial_package_is_self_contained() -> None:
    tutorial_root = PSF_FITTING_ROOT / "PSF_Fitting_Tutorial"

    raw_images = sorted((tutorial_root / "data" / "raw").glob("*.bmp"))
    assert len(raw_images) == 5
    assert (tutorial_root / "data" / "gt" / "GT_901_with_Block_proc.bmp").exists()
    assert (tutorial_root / "data" / "psf" / "psf_multi.mat").exists()

    readme_text = (tutorial_root / "README_TW.md").read_text(encoding="utf-8")
    notebook = nbformat.read(tutorial_root / "PSF_full_workflow_tutorial_tw.ipynb", as_version=4)
    notebook_text = "\n".join("".join(cell.get("source", "")) for cell in notebook.cells)

    assert str(PROJECT_ROOT) not in readme_text
    assert str(PROJECT_ROOT) not in notebook_text
    assert "從頭到尾" in readme_text
    assert "run_full_workflow" in notebook_text


def test_tutorial_workflow_runs_on_packaged_data(tmp_path: Path) -> None:
    from PSF_Fitting_Tutorial.scripts.tutorial_workflow import (
        load_tutorial_dataset,
        run_full_workflow,
    )

    tutorial_root = PSF_FITTING_ROOT / "PSF_Fitting_Tutorial"
    dataset = load_tutorial_dataset(tutorial_root, crop_size=129, max_images=2)

    assert len(dataset.raw_images) == 2
    assert dataset.gt_image.shape == dataset.raw_images[0].image.shape
    assert dataset.initial_psf.ndim == 2

    outputs = run_full_workflow(
        tutorial_root=tutorial_root,
        output_root=tmp_path,
        crop_size=129,
        max_images=2,
        maxiter=8,
    )

    assert outputs.fitted_stack_path.exists()
    assert outputs.summary_csv_path.exists()
    assert outputs.initial_psf_figure.exists()
    assert outputs.prealignment_figure.exists()
    assert outputs.montage_figure.exists()
    assert outputs.quality_figure.exists()
    assert outputs.deconvolution_figure.exists()
    assert outputs.fitted_count == 2
