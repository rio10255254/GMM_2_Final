"""Gate the full R147 run against frozen R146 data and native PSF physics."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
R146 = ROOT.parent / "R146_SEMCoreHaloPSF25_MatchedPairs"
sys.path.insert(0, str(ROOT))
from dataset import Bank
from losses import objective
from model import Model
from training_policy import optimizer
from utils import load, model_config, now, save, setup, sha, train_config, verify_bank_lock
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    cfg = train_config()
    mc = model_config()
    manifest = load(ROOT / "data/manifest.json")
    reference = load(R146 / "data/manifest.json")
    bank_lock = verify_bank_lock()
    assert len(manifest["entries"]) == len(reference["entries"]) == 768
    assert sha(ROOT / "data/manifest.json") == sha(R146 / "data/manifest.json")
    assert bank_lock["bank_sha256"] == sha(R146 / "calibration/measured_psf_bank.npz")
    assert bank_lock["source_mat_sha256"] == sha(str(PROJECT_ROOT / bank_lock["source_mat_path"]))
    assert bank_lock["research_only"] is True
    assert manifest["measured_psf_bank_sha256"] == bank_lock["bank_sha256"]
    for entry in manifest["entries"]:
        for rel, checksum in ((entry["arrays"], entry["arrays_sha256"]),
                              (entry["metadata"], entry["metadata_sha256"])):
            assert sha(ROOT / "data" / rel) == checksum
            assert sha(R146 / "data" / rel) == checksum
    for rel in ("dataset.py", "losses.py", "utils.py"):
        assert sha(ROOT / rel) == sha(R146 / rel)
    earlier_cfg = load(R146 / "config/train.json")
    for key in ("model_seed", "order_seed", "noise_seed", "splits", "updates", "epochs",
                "warmup", "save_every", "dev_every", "optimizer", "train_crop", "supervised_core"):
        assert cfg[key] == earlier_cfg[key]
    for key in ("image", "gradient", "pair"):
        assert cfg["loss"][key] == earlier_cfg["loss"][key]
    assert cfg["updates"] == 8192 and cfg["splits"] == {"train":512,"dev":128,"test":128}
    assert mc["psf_count"] == 25 and mc["psf_mode"] == "fixed_bank_mean_native_pixel_data_consistency"
    assert mc["optical_iterations"] == 4 and mc["optical_step_initial"] == .3

    operator_test = load(ROOT / "results/native_psf_operator_validation.json")
    step_test = load(ROOT / "results/optical_step_preflight.json")
    assert operator_test["passed"] and step_test["passed"]
    assert operator_test["operator_source_sha256"] == sha(ROOT / "optical/fullres_psf.py")
    assert step_test["operator_source_sha256"] == sha(ROOT / "optical/fullres_psf.py")
    assert operator_test["psf_bank_sha256"] == bank_lock["bank_sha256"]
    assert operator_test["impulse_peak"] == [160,160]
    assert operator_test["max_full_resolution_scipy_difference"] < 1e-6
    assert operator_test["constant_image_max_error"] < 1e-6
    assert operator_test["known_blur_fidelity_after"] < operator_test["known_blur_fidelity_before"]
    assert step_test["selected_initial_step"] == mc["optical_step_initial"]
    assert step_test["maximum_trainable_step"] == mc["optical_step_max"]
    assert step_test["candidates"]["0.3"]["improved_parents"] == 40

    setup(cfg["model_seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Model(mc, ROOT).to(device).train()
    optimizer_ = optimizer(model, base_lr=cfg["optimizer"]["max_lr"],
                           weight_decay=cfg["optimizer"]["weight_decay"],
                           optical_lr_multiplier=mc["optical_lr_multiplier"])
    bank = Bank(cfg)
    gradients = []
    for index in (0, 1):
        batch = bank.batch("train", index, device, epoch=2)
        optimizer_.zero_grad(set_to_none=True)
        output = model(batch["source"])
        loss, _ = objective(output, batch)
        assert bool(torch.isfinite(output).all()) and torch.isfinite(loss)
        loss.backward()
        optical = float(model.optical_step_logits.grad.norm())
        stem = float(model.refiner.stem.weight.grad.norm())
        gradients.append(dict(optical_step=optical, stem=stem, loss=float(loss)))
        assert np.isfinite([optical, stem, float(loss)]).all() and optical > 0
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1, error_if_nonfinite=True)
        optimizer_.step()
    assert gradients[-1]["stem"] > 0
    model.eval()
    with torch.inference_mode():
        image = bank.batch("dev", 0, device)["source"]
        on = model(image)
        model.optical_enabled = False
        off = model(image)
    difference = float((on-off).square().mean().sqrt()*255)
    assert difference > .001 and np.isfinite(difference)
    result = dict(passed=True, model_name=mc["model_name"],
                  psf_mode=mc["psf_mode"], fixed_bank_sha256=bank_lock["bank_sha256"],
                  unchanged_R146_data_manifest_sha256=sha(ROOT / "data/manifest.json"),
                  unchanged_parent_arrays=768, physical_operator_test_sha256=sha(ROOT / "results/native_psf_operator_validation.json"),
                  synthetic_step_test_sha256=sha(ROOT / "results/optical_step_preflight.json"),
                  two_step_gradients=gradients, on_off_dev_rms_gray=difference,
                  device=device, completed_utc=now())
    save(ROOT / "results/preflight.json", result)
    print("PREFLIGHT_PASS", result, flush=True)


if __name__ == "__main__":
    main()
