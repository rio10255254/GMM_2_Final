import sys
from pathlib import Path

import torch


ROOT = Path(r"D:\GMM_2_Final\Experiments\R26NewPSFCheck\root_cause_centering")
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from root_cause_centering_lib import (  # noqa: E402
    apply_psf_buffers,
    build_delta_matrix,
    collect_selector_candidates,
    load_run_profile,
    summarize_psf_pair,
)


OLD_RUN = ROOT / "archived_inputs" / "r26sm035_recipe_profile_20260316"
NEW_RUN = Path(
    r"D:\GMM_2_Final\Experiments\R26NewPSFCheck\artifacts\package_cleanup_archive_20260326\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223"
)
OLD_PSF = Path(
    r"D:\GMM_2_Final\Experiments\R26NewPSFCheck\artifacts\package_cleanup_archive_20260326\psf_swap_20260326_093203\PSF_fitted_2D_FOVstack.package_old.mat"
)
NEW_PSF = Path(r"D:\GMM_2_Final\PSF_Fitting\Crop_circle_FreqFiltered\Fits\PSF_fitted_2D_FOVstack.mat")


def test_build_delta_matrix_detects_recipe_drift():
    old_profile = load_run_profile(OLD_RUN)
    new_profile = load_run_profile(NEW_RUN)

    delta = build_delta_matrix(old_profile, new_profile)
    changed_keys = {row["field"] for row in delta["changed"]}

    assert "amp" in changed_keys
    assert "seed_deterministic" in changed_keys
    assert "cudnn_benchmark" in changed_keys
    assert "model_name" in changed_keys


def test_summarize_psf_pair_captures_center_shift_not_width_blowup():
    summary = summarize_psf_pair(OLD_PSF, NEW_PSF)

    assert summary["old_mean_psf"]["peak_x"] == 51
    assert summary["new_mean_psf"]["peak_x"] == 50
    assert summary["old_mean_psf"]["peak_y"] == 49
    assert summary["new_mean_psf"]["peak_y"] == 50
    assert abs(summary["r90_delta"]) < 0.1


def test_collect_selector_candidates_recovers_expected_epochs():
    candidates = collect_selector_candidates(NEW_RUN / "GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_val_log_v5.csv")

    wanted = {10, 15, 16, 20, 25, 30, 50, 75, 100}
    got = {item["epoch"] for item in candidates["selected_epochs"]}

    assert wanted.issubset(got)
    assert candidates["best_tradeoff"]["epoch"] == 16


class _DummyLayer(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer("PSFs", torch.zeros(1, 100, 3, 3))
        self.register_buffer("PSF_mean", torch.zeros(1, 1, 3, 3))
        self.register_buffer("PSF_center", torch.zeros(1, 1, 3, 3))


class _DummyWeak(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer("PSFs", torch.zeros(1, 4, 3, 3))


class _DummyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.physics_layer = _DummyLayer()
        self.weak_psf_block = _DummyWeak()


def test_apply_psf_buffers_overrides_loaded_buffers():
    model = _DummyModel()
    psf_tensor = torch.arange(100 * 3 * 3, dtype=torch.float32).view(1, 100, 3, 3)
    norm = psf_tensor / psf_tensor.sum(dim=(2, 3), keepdim=True)

    apply_psf_buffers(model, psf_tensor)

    assert torch.allclose(model.physics_layer.PSFs, norm)
    assert torch.allclose(model.physics_layer.PSF_mean, norm.mean(dim=1, keepdim=True))
    assert torch.allclose(model.physics_layer.PSF_center, norm[:, 55:56])
    assert torch.allclose(model.weak_psf_block.PSFs, norm[:, :4])
