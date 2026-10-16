"""Check the actual training batch entrypoint against independent epoch noise replay."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataset import Bank
from utils import load, now, save, sha


def main() -> None:
    cfg = load(ROOT / "config/train.json")
    bank = Bank(cfg)
    selected = {}
    for entry in bank.manifest["entries"]:
        if entry["split"] == "train" and entry["category"] not in selected:
            selected[entry["category"]] = entry
    assert len(selected) == 7
    checks = []
    for category, entry in sorted(selected.items()):
        index = int(entry["index"])
        with np.load(ROOT / "data" / entry["arrays"], allow_pickle=False) as z:
            noiseless = z["noiseless"]
            target = z["target"]
        meta = load(ROOT / "data" / entry["metadata"])
        for epoch in (0, 2, 15):
            seed = [cfg["noise_seed"], epoch, index]
            rng = np.random.default_rng(np.random.SeedSequence(seed))
            noisy = noiseless.astype(np.float64) + rng.normal(
                0, meta["noise_sigma_gray"] / 255, noiseless.shape)
            observed = np.rint(np.clip(noisy, 0, 1)*255).astype(np.uint8)
            expected_source = np.ascontiguousarray(
                observed[:, None, 32:352, 32:352].astype(np.float32)/np.float32(255))
            expected_target = np.ascontiguousarray(target[:, None, 32:352, 32:352])
            actual = bank.batch("train", index, "cpu", epoch=epoch)
            assert actual["parent_id"] == entry["parent_id"]
            assert actual["noise_seed"] == seed
            assert np.array_equal(actual["source"].numpy(), expected_source)
            assert np.array_equal(actual["target"].numpy(), expected_target)
            assert actual["psf_index"].tolist() == meta["psf_index"]
            checks.append(dict(category=category, epoch=epoch, parent_id=entry["parent_id"],
                               psf_label=meta["psf_index"]))
    result = dict(passed=True, representative_training_batches=len(checks),
                  categories=len(selected), epochs=[0, 2, 15],
                  source_pixels_exact=True, clear_target_pixels_exact=True,
                  labels_exact=True, checks=checks, script_sha256=sha(Path(__file__)),
                  completed_utc=now())
    save(ROOT / "results/epoch_noise_replay_audit.json", result)
    print("EPOCH_REPLAY_PASS", len(checks), "batches", flush=True)


if __name__ == "__main__":
    main()
