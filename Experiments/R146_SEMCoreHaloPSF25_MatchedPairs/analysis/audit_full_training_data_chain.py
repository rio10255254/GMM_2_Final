"""Independently replay every R146 pair and its frozen training identity."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.io import loadmat
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[1]
R145 = ROOT.parent / "R145_Center9PSF25_CorrectedPairs"
SOURCE_META = ROOT.parent / "R128_SourceOnlyFullTraining/data/package"
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def array_sha(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def convolve(clear: np.ndarray, psf: np.ndarray) -> np.ndarray:
    padded = np.pad(clear.astype(np.float64), 50, mode="reflect")
    return fftconvolve(padded, psf, mode="same")[50:-50, 50:-50].astype(np.float32)


def old_sensor_noise(meta: dict, view: int, shape: tuple[int, int]) -> np.ndarray:
    seed = np.random.SeedSequence(int(meta["seed"])).spawn(7)[4 + view]
    return np.random.default_rng(seed).normal(0, float(meta["noise_sigma_gray"])/255, shape)


def main() -> None:
    lock = load(ROOT / "calibration/BANK_LOCK.json")
    assert lock["research_only"] is True and lock["psf_calibration_uses_sem_geometry"] is True
    mat = Path(PROJECT_ROOT / lock["source_mat_path"])
    assert sha(mat) == lock["source_mat_sha256"]
    grid = loadmat(mat)["psf_grid"]
    assert grid.shape == (101, 101, 5, 5)
    kernels = np.transpose(grid, (2, 3, 0, 1)).reshape(25, 101, 101).copy()
    assert np.allclose(kernels.sum((1, 2)), 1, rtol=0, atol=1e-10)
    with np.load(ROOT / "calibration/measured_psf_bank.npz", allow_pickle=False) as z:
        installed = z["all_kernels"]
    assert np.array_equal(installed, kernels)
    assert sha(ROOT / "calibration/measured_psf_bank.npz") == lock["bank_sha256"]
    kernels /= kernels.sum(axis=(1, 2), keepdims=True)

    manifest = load(ROOT / "data/manifest.json")
    previous = load(R145 / "data/manifest.json")
    earlier = {(e["split"], e["index"]): e for e in previous["entries"]}
    assert len(manifest["entries"]) == len(earlier) == 768
    by_key = {(e["split"], e["index"]): e for e in manifest["entries"]}
    assert len(by_key) == 768
    counts = {"train": 0, "dev": 0, "test": 0}
    blurred_parents = 0
    identity_parents = 0
    target_exact = 0
    source_exact = 0
    noiseless_exact = 0
    max_noiseless_difference = 0.0
    for entry in manifest["entries"]:
        key = (entry["split"], entry["index"])
        prior = earlier[key]
        assert entry["parent_id"] == prior["parent_id"]
        assert entry["target_array_sha256"] == prior["target_array_sha256"]
        assert entry["applied_psf_index"] == prior["applied_psf_index"]
        array_path = ROOT / "data" / entry["arrays"]
        meta_path = ROOT / "data" / entry["metadata"]
        assert sha(array_path) == entry["arrays_sha256"]
        assert sha(meta_path) == entry["metadata_sha256"]
        meta = load(meta_path)
        source_meta_path = SOURCE_META / entry["split"] / f"{entry['index']:04d}.json"
        source_meta = load(source_meta_path)
        assert meta["source_generator_parent_sha256"] == sha(source_meta_path)
        assert meta["real_or_SEM_answers_used"] is False
        assert meta["external_source_inputs"] == []
        assert meta["psf_bank_sha256"] == lock["bank_sha256"]
        with np.load(array_path, allow_pickle=False) as z:
            target, observed, noiseless = (z[name] for name in ("target", "source", "noiseless"))
        with np.load(R145 / "data" / prior["arrays"], allow_pickle=False) as z:
            assert np.array_equal(target, z["target"])
        assert array_sha(target) == entry["target_array_sha256"]
        target_exact += 1
        counts[entry["split"]] += 1
        index = entry["applied_psf_index"]
        if index is None:
            assert entry["category"] in ("clean_identity", "noisy_identity")
            identity_parents += 1
        else:
            assert isinstance(index, int) and 0 <= index < 25
            blurred_parents += 1
        for view in range(2):
            expected = target[view].copy() if index is None else convolve(target[view], kernels[index])
            difference = float(np.max(np.abs(expected-noiseless[view])))
            max_noiseless_difference = max(max_noiseless_difference, difference)
            assert difference < 2e-7, (entry["parent_id"], view, difference)
            noiseless_exact += int(np.array_equal(expected, noiseless[view]))
            noise = old_sensor_noise(source_meta, view, target.shape[1:])
            expected_source = np.rint(np.clip(noiseless[view].astype(float)+noise, 0, 1)*255).astype(np.uint8)
            assert np.array_equal(expected_source, observed[view]), (entry["parent_id"], view)
            source_exact += 1
    assert counts == {"train": 512, "dev": 128, "test": 128}
    assert blurred_parents == 692 and identity_parents == 76
    assert source_exact == 1536

    cfg = load(ROOT / "config/train.json")
    updates = [json.loads(line) for line in
               (ROOT / "runs/formal_8192/updates.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(updates) == cfg["updates"] == 8192
    for position, row in enumerate(updates):
        epoch = position // 512
        offset = position % 512
        selected_index = int(np.random.default_rng(np.random.SeedSequence([cfg["order_seed"], epoch]))
                             .permutation(512)[offset])
        assert row["step"] == position+1 and row["epoch"] == epoch
        assert row["parent_id"] == by_key[("train", selected_index)]["parent_id"]
        assert row["psf_active"] == (epoch >= 2)
    run = load(ROOT / "runs/formal_8192/run_config.json")
    assert run["init"] == "scratch" and run["adaptive_labels"] == 512
    assert run["data_root"] == str((ROOT / "data").resolve())
    assert run["bank_sha256"] == lock["bank_sha256"]
    assert run["source_data_manifest_sha256"] == sha(ROOT / "data/manifest.json")
    checkpoint_path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    receipt = load(ROOT / "runs/formal_8192/training_complete.json")["checkpoint"]
    assert sha(checkpoint_path) == receipt["sha256"] and receipt["step"] == 8192
    cp = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    assert cp["bank_sha256"] == lock["bank_sha256"]
    assert cp["data_manifest_sha256"] == sha(ROOT / "data/manifest.json")
    assert cp["checkpoint_kind"] == "trained_model" and cp["step"] == 8192
    assert cp["model_config"] == load(ROOT / "config/model.json")
    assert cp["train_config"] == cfg

    result = dict(passed=True, source_mat_sha256=lock["source_mat_sha256"],
                  bank_sha256=lock["bank_sha256"], checkpoint_sha256=receipt["sha256"],
                  parents=768, split_counts=counts, blurred_parents=blurred_parents,
                  identity_parents=identity_parents, clear_targets_bit_identical_to_R145=target_exact,
                  regenerated_noiseless_views_exact=noiseless_exact,
                  regenerated_noiseless_views_with_tolerance=1536,
                  max_noiseless_difference=max_noiseless_difference,
                  stored_noisy_views_exact=source_exact,
                  logged_updates_with_correct_parent_order=len(updates),
                  scratch_initializer_verified=True, completed_utc=now())
    save(ROOT / "results/data_training_chain_audit.json", result)
    print(result, flush=True)


if __name__ == "__main__":
    main()
