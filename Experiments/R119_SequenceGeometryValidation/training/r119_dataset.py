"""R119 data policy: identical base population, candidate-specific observations."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, Sampler

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/package"
BASE = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8-sig"))


def _asym_kernel():
    size = 17; axis = np.arange(-(size // 2), size // 2 + 1, dtype=np.float32); yy, xx = np.meshgrid(axis, axis, indexing="ij")
    value = np.exp(-.5 * ((xx / 1.45) ** 2 + (yy / 1.0) ** 2)) + .23 * np.exp(-.5 * (((xx - 3.0) / 2.8) ** 2 + ((yy + .4) / 1.3) ** 2))
    value = np.maximum(value, 0).astype(np.float32); value /= value.sum()
    return value


ASYM = _asym_kernel()


def fine_reliability(clean_observation, target, noise_sigma):
    target_fine = target - cv2.GaussianBlur(target, (0, 0), .8); source_fine = clean_observation - cv2.GaussianBlur(clean_observation, (0, 0), .8)
    target_power = cv2.GaussianBlur(target_fine * target_fine, (0, 0), 1.6); source_power = cv2.GaussianBlur(source_fine * source_fine, (0, 0), 1.6)
    variance = float(noise_sigma) ** 2 + 1e-9; target_present = target_power / (target_power + variance); source_visible = source_power / (source_power + variance)
    return np.clip(1 - target_present * (1 - source_visible), 0, 1).astype(np.float32)


class R119Scenes(Dataset):
    """Two-view base scenes with a declared observation policy.

    A keeps independent view photometry/noise (R118 control). B shares the
    declared exposure/noise state across the two observations. D additionally
    applies the recorded centered asymmetric-tail kernel to the frozen short
    enrichment IDs. No real image or new label is read here.
    """
    def __init__(self, split="train", epoch=0, limit=0, candidate="A", data_seed=1196001, enriched_ids=None):
        self.records = [r for r in BASE["records"] if r["split"] == split]
        if limit: self.records = self.records[:limit]
        self.epoch, self.split, self.candidate, self.data_seed = epoch, split, candidate, int(data_seed)
        self.enriched_ids = set(enriched_ids or [])

    def __len__(self): return len(self.records)

    def __getitem__(self, index):
        record = self.records[index]; scene_id = int(record["scene_index"])
        rng = np.random.default_rng(self.data_seed + scene_id * 1009 + self.epoch * 7919)
        shared_gain = float(rng.uniform(.8, 1.15)); shared_offset = float(rng.uniform(-.03, .03)); shared_noise = float(rng.uniform(.3, 3.0)) / 255.0
        inputs = []; targets = []; sdfs = []; masks = []; reliabilities = []
        for side, suffix in enumerate(("a", "b")):
            target = np.load(PACKAGE / record[f"target_{suffix}"]).astype(np.float32) / 255.0
            source = np.load(PACKAGE / record[f"source_{suffix}"]).astype(np.float32)
            if source.max() > 1.5: source /= 255.0
            if self.candidate == "D" and scene_id in self.enriched_ids:
                source = cv2.filter2D(source, -1, ASYM, borderType=cv2.BORDER_REFLECT)
            if self.candidate == "B":
                gain, offset, noise = shared_gain, shared_offset, shared_noise
            else:
                gain = float(rng.uniform(.8, 1.15)) if self.split == "train" else 1.0; offset = float(rng.uniform(-.03, .03)) if self.split == "train" else 0.0; noise = float(rng.uniform(.3, 3.0)) / 255.0
            target = np.clip(gain * target + offset, 0, 1); source = np.clip(gain * source + offset, 0, 1)
            if record["role"] == "identity":
                source = target.copy(); reliabilities.append(np.ones_like(target))
            else:
                reliabilities.append(fine_reliability(source, target, noise)); source += rng.normal(0, noise, source.shape).astype(np.float32); source += rng.normal(0, noise * .15, (source.shape[0], 1)).astype(np.float32); source += rng.normal(0, noise * .1, (1, source.shape[1])).astype(np.float32)
            inputs.append(np.clip(source, 0, 1)); targets.append(target)
            sdf = np.load(PACKAGE / record[f"sdf_{suffix}"]).astype(np.float32)
            if record["polarity"] != 1: sdf = sdf * record["polarity"]
            sdfs.append(sdf); masks.append(np.load(PACKAGE / record[f"mask_{suffix}"]).astype(np.float32) / 255.0)
        tensor = lambda values: torch.from_numpy(np.stack(values))[:, None]
        return {"source": tensor(inputs), "target": tensor(targets), "sdf": tensor(sdfs), "mask": tensor(masks), "fine_reliability": tensor(reliabilities), "identity": torch.tensor([record["role"] == "identity"] * 2), "flat": torch.tensor([record["role"] == "flat_negative"] * 2), "shift_xy": torch.tensor([record["pair_dx_px"], record["pair_dy_px"]], dtype=torch.float32), "scene_index": scene_id, "family": record["family"], "role": record["role"]}


class FamilyOrder(Sampler):
    def __init__(self, dataset, seed): self.dataset, self.seed = dataset, int(seed)
    def __len__(self): return len(self.dataset)
    def __iter__(self):
        rng = np.random.default_rng(self.seed); groups = defaultdict(list)
        for index, record in enumerate(self.dataset.records): groups[record["family"]].append(index)
        for values in groups.values(): rng.shuffle(values)
        while groups:
            names = list(groups); rng.shuffle(names)
            for name in names:
                yield groups[name].pop()
                if not groups[name]: del groups[name]


def flatten(batch, device):
    result = {key: batch[key].flatten(0, 1).to(device, non_blocking=True) for key in ("source", "target", "sdf", "mask", "fine_reliability")}
    result["identity"] = batch["identity"].flatten().to(device); result["flat"] = batch["flat"].flatten().to(device); result["shift_xy"] = batch["shift_xy"].to(device); result["scenes"] = batch["source"].shape[0]
    return result
