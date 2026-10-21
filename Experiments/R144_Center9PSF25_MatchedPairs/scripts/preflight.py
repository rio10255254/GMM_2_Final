"""Check the measured-PSF pair experiment before the expensive run."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
R143 = Path(r"D:\GMM_2_Final\Experiments\R143_PSF25_MatchedPairs")
sys.path.insert(0, str(ROOT))
from dataset import Bank
from model import Model
from training_policy import apply_epoch_policy
from utils import load, model_config, save, setup, sha, train_config, verify_bank_lock


def main() -> None:
    cfg = train_config()
    mc = model_config()
    done = load(ROOT / "data/generation_complete.json")
    manifest = load(ROOT / "data/manifest.json")
    assert done["parents"] == len(manifest["entries"]) == 768
    assert done["original_noise_replay_errors"] == 0
    bank_lock = verify_bank_lock()
    assert manifest["measured_psf_bank_sha256"] == bank_lock["bank_sha256"]
    assert bank_lock["source_mat_sha256"] == sha(bank_lock["source_mat_path"])
    assert bank_lock["object_um_per_px"] == .1725
    assert bank_lock["psf_calibration_uses_sem_diameters"] is True
    assert bank_lock["sem_size_targets_in_training"] is False
    assert cfg["updates"] == 8192 and mc["psf_count"] == 25 and mc["psf_topk"] == 4
    assert cfg["splits"] == {"train": 512, "dev": 128, "test": 128}
    reference_manifest = load(R143 / "data/manifest.json")
    old_entries = {(e["split"], e["index"]): e for e in reference_manifest["entries"]}
    assert len(old_entries) == 768
    for rel in ("model.py", "train.py", "dataset.py", "losses.py", "training_policy.py",
                "utils.py", "optical/adaptive_psf.py", "config/train.json"):
        assert sha(ROOT / rel) == sha(R143 / rel), "R143 architecture or training policy drift: " + rel
    bank = Bank(cfg)
    counts = {}
    label_counts = {}
    for split in cfg["splits"]:
        es = [e for e in manifest["entries"] if e["split"] == split]
        labels = Counter()
        no_blur = 0
        for e in es:
            m = load(ROOT / "data" / e["metadata"])
            earlier = old_entries[(split, e["index"])]
            assert m["parent_id"] == e["parent_id"]
            assert e["parent_id"] == earlier["parent_id"]
            assert e["target_array_sha256"] == earlier["target_array_sha256"]
            assert e["applied_psf_index"] == earlier["applied_psf_index"]
            assert sha(ROOT / "data" / e["arrays"]) == e["arrays_sha256"]
            assert sha(ROOT / "data" / e["metadata"]) == e["metadata_sha256"]
            assert len(m["psf_index"]) == 2 and m["psf_index"][0] == m["psf_index"][1]
            if m["applied_psf_index"] is None:
                no_blur += 1
                assert e["category"] in ("clean_identity", "noisy_identity")
                assert m["psf_index"] == [-1, -1]
            else:
                labels[int(m["applied_psf_index"])] += 1
                assert 0 <= m["applied_psf_index"] < 25
                assert m["psf_index"][0] == (-1 if e["category"] == "flat_negative" else m["applied_psf_index"])
        assert len(es) == cfg["splits"][split] and len(labels) == 25
        assert max(labels.values()) - min(labels.values()) <= 1
        counts[split] = {"parents": len(es), "measured_psf": sum(labels.values()), "identity": no_blur}
        label_counts[split] = dict(sorted(labels.items()))
    setup(cfg["model_seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Model(mc, ROOT).to(device).train()
    apply_epoch_policy(model, 2)
    sample = bank.batch("train", 0, device, epoch=2)
    assert bool((sample["psf_index"] >= 0).all())
    with torch.enable_grad():
        output = model(sample["source"])
        loss = model.refiner.optics.selector_loss(sample["psf_index"])
        loss.backward()
    first = float(model.refiner.optics.selector[0].weight.grad.norm())
    last = float(model.refiner.optics.selector[-1].weight.grad.norm())
    assert torch.isfinite(output).all() and np.isfinite([first, last, float(loss)]).all()
    assert first > 0 and last > 0
    record = dict(passed=True, source_model="R141", model_name=mc["model_name"],
                  counts=counts, per_psf_counts=label_counts,
                  matched_r143_design=True,
                  r143_data_manifest_sha256=sha(R143 / "data/manifest.json"),
                  source_mat_sha256=bank_lock["source_mat_sha256"],
                  source_manifest_sha256=manifest["source_manifest"]["sha256"],
                  new_manifest_sha256=sha(ROOT / "data/manifest.json"),
                  bank_sha256=manifest["measured_psf_bank_sha256"],
                  supervised_selector_loss=float(loss), selector_first_grad_norm=first,
                  selector_last_grad_norm=last, device=device)
    save(ROOT / "results/preflight.json", record)
    print("PREFLIGHT_PASS", counts, "selector_loss", float(loss), flush=True)


if __name__ == "__main__":
    main()
