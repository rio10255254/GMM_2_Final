from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "model"))
sys.path.insert(0, str(ROOT / "training"))
from model import build_model, count_parameters
from supervision import build_supervision_targets, renderer_epoch_weight


def model_hash(model) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode()); digest.update(value.detach().contiguous().numpy().tobytes())
    return digest.hexdigest()


def matched_models():
    torch.manual_seed(int(CONFIG["seed"])); baseline = build_model("width_shift")
    torch.manual_seed(int(CONFIG["seed"])); detail = build_model("bounded_detail")
    return baseline, detail


def test_formal_entrypoint_always_requires_explicit_confirmation():
    assert isinstance(CONFIG["formal_training_authorized"], bool)
    source = (ROOT / "scripts" / "run_probe.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "scripts" / "run_formal.ps1").read_text(encoding="utf-8")
    assert "not args.confirm_formal" in source
    assert "R113_CONFIRM_FORMAL" in wrapper


def test_arms_have_identical_parameters_and_initial_state():
    baseline, detail = matched_models()
    torch.manual_seed(int(CONFIG["seed"])); supervised = build_model("bounded_detail_supervised")
    assert count_parameters(baseline) == count_parameters(detail)
    assert count_parameters(baseline) == count_parameters(supervised)
    assert model_hash(baseline) == model_hash(detail)
    assert model_hash(baseline) == model_hash(supervised)
    assert set(baseline.state_dict()) == set(detail.state_dict())
    for name in baseline.state_dict():
        assert torch.equal(baseline.state_dict()[name], detail.state_dict()[name]), name
        assert torch.equal(baseline.state_dict()[name], supervised.state_dict()[name]), name


def test_supervision_target_obeys_branch_bound_and_identity():
    torch.manual_seed(int(CONFIG["seed"])); model = build_model("bounded_detail_supervised").eval()
    source = torch.rand(2, 1, 128, 128)
    target = torch.clamp(source + .08 * torch.sin(torch.linspace(0, 20, 128))[None, None, None, :], 0, 1)
    with torch.inference_mode():
        details = model.forward_details(source)
        target_carrier, target_detail = build_supervision_targets(model, details, target, torch.tensor([False, True]))
    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"]) / 255
    assert float(target_carrier.abs().max()) <= .5 * bound + 1e-7
    assert float(target_detail.abs().max()) <= bound + 1e-7
    assert torch.equal(target_carrier[1], torch.zeros_like(target_carrier[1]))
    assert torch.equal(target_detail[1], torch.zeros_like(target_detail[1]))
    assert float(target_detail[0].abs().mean()) > 0
    assert float(F.avg_pool2d(target_detail[:1], 9, 1, 4).abs().mean()) < float(target_detail[:1].abs().mean())


def test_supervision_schedule_is_staged_and_reference_arms_are_zero():
    expected = [2.0, 1.5, 1.0, .65, .4, .25]
    actual = [renderer_epoch_weight("bounded_detail_supervised", epoch) for epoch in range(1, 7)]
    assert actual == expected
    assert renderer_epoch_weight("width_shift", 1) == 0
    assert renderer_epoch_weight("bounded_detail", 1) == 0


def test_detail_is_bounded_local_and_baseline_is_exactly_disabled():
    baseline, detail = matched_models()
    detail.load_state_dict(baseline.state_dict())
    with torch.no_grad():
        # Activate the otherwise zero-initialized head for the structural test.
        baseline.detail_head.weight.normal_(0, .08); baseline.detail_head.bias.fill_(.03)
        detail.detail_head.load_state_dict(baseline.detail_head.state_dict())
    source = torch.rand(1, 1, 128, 128)
    baseline.eval(); detail.eval()
    with torch.inference_mode():
        a = baseline.forward_details(source); b = detail.forward_details(source)
    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"]) / 255
    assert torch.equal(a.detail, torch.zeros_like(a.detail))
    assert torch.allclose(a.base_output, b.base_output, atol=0, rtol=0)
    assert float(b.detail.abs().max()) <= bound + 1e-7
    assert float(F.avg_pool2d(b.detail, 9, 1, 4).abs().mean()) < float(b.detail.abs().mean())


def test_model_contains_no_global_pooling_or_fft_module():
    _, model = matched_models()
    forbidden = (nn.AdaptiveAvgPool1d, nn.AdaptiveAvgPool2d, nn.AdaptiveAvgPool3d)
    assert not any(isinstance(module, forbidden) for module in model.modules())
    source = (ROOT / "model" / "model.py").read_text(encoding="utf-8").lower()
    assert "torch.fft" not in source
    assert "adaptive_avg_pool" not in source


def test_detail_arm_is_tile_consistent_with_configured_halo():
    torch.set_num_threads(2)
    _, model = matched_models()
    with torch.no_grad():
        model.detail_head.weight.normal_(0, .04); model.detail_head.bias.fill_(.02)
    model.eval(); source = torch.rand(1, 1, 448, 448)
    with torch.inference_mode():
        full = model(source)
        crop = model(source[..., 16:432, 16:432])
    # Central 32 px has 192 px context in the crop, matching minimum_halo_px.
    reference = full[..., 208:240, 208:240]
    tiled = crop[..., 192:224, 192:224]
    # Different convolution shapes can change CPU accumulation order slightly;
    # 5e-5 is only 0.013 gray levels and far below 8-bit quantization.
    assert float((reference - tiled).abs().max()) < 5e-5


def test_locked_selection_is_synthetic_and_complete():
    selection_path = ROOT / CONFIG["data"]["selection_file"]
    assert selection_path.exists()
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    train = [row for row in selection["records"] if row["split"] == "train"]
    validation = [row for row in selection["records"] if row["split"] == "validation"]
    assert len(train) == CONFIG["data"]["train_count"]
    assert len(validation) == CONFIG["data"]["validation_count"]
    assert selection["source_experiment"] == "R107A_SingleImageEdgeGeometryProbe"
    assert selection["supersample_factor"] == 8
    forbidden = ("sem", "junhua", "hs100mg", "real")
    for row in selection["records"]:
        joined = " ".join(str(row.get(key, "")) for key in ("scene_id", "family", "role", "target", "mask")).lower()
        assert not any(token in joined for token in forbidden)
