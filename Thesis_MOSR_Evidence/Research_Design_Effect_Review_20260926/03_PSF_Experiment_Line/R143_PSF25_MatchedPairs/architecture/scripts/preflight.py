"""Check the measured-PSF pair experiment before the expensive run."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
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
    assert manifest["measured_psf_bank_sha256"] == verify_bank_lock()["bank_sha256"]
    assert cfg["updates"] == 8192 and mc["psf_count"] == 25 and mc["psf_topk"] == 4
    assert cfg["splits"] == {"train": 512, "dev": 128, "test": 128}
    bank = Bank(cfg)
    counts = {}
    label_counts = {}
    for split in cfg["splits"]:
        es = [e for e in manifest["entries"] if e["split"] == split]
        labels = Counter()
        no_blur = 0
        for e in es:
            m = load(ROOT / "data" / e["metadata"])
            assert m["parent_id"] == e["parent_id"]
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
                  source_manifest_sha256=manifest["source_manifest"]["sha256"],
                  new_manifest_sha256=sha(ROOT / "data/manifest.json"),
                  bank_sha256=manifest["measured_psf_bank_sha256"],
                  supervised_selector_loss=float(loss), selector_first_grad_norm=first,
                  selector_last_grad_norm=last, device=device)
    save(ROOT / "results/preflight.json", record)
    print("PREFLIGHT_PASS", counts, "selector_loss", float(loss), flush=True)


if __name__ == "__main__":
    main()
