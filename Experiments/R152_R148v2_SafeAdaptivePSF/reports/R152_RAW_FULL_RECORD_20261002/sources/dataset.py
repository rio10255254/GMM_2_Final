"""Read-only reuse of the frozen R148v2 synthetic payload and geometry."""
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

from utils import data_config, digest_array, load, sha


class Bank:
    def __init__(self, cfg):
        self.cfg = cfg
        reference = data_config()
        source = Path(reference["source_experiment"])
        self.root = source / "data/payload"
        self.geometry_root = source / "data/geometry"
        if sha(self.root / "manifest.json") != reference["payload_manifest_sha256"]:
            raise RuntimeError("Referenced R148v2 payload manifest changed")
        if sha(self.geometry_root / "manifest.json") != reference["geometry_manifest_sha256"]:
            raise RuntimeError("Referenced R148v2 geometry manifest changed")
        self.manifest = load(self.root / "manifest.json")
        geometry_manifest = load(self.geometry_root / "manifest.json")
        self.entries = {(e["split"], e["index"]): e for e in self.manifest["entries"]}
        self.geometry = {(e["split"], e["index"]): e for e in geometry_manifest["entries"]}
        if len(self.entries) != 768 or len(self.geometry) != 768:
            raise RuntimeError("Expected 768 frozen parents")

    @lru_cache(maxsize=48)
    def read(self, split, index):
        entry = self.entries[(split, int(index))]
        geometry = self.geometry[(split, int(index))]
        arrays_path = self.root / entry["arrays"]
        metadata_path = self.root / entry["metadata"]
        geometry_path = self.geometry_root / geometry["path"]
        if sha(arrays_path) != entry["arrays_sha256"] or sha(metadata_path) != entry["metadata_sha256"] or sha(geometry_path) != geometry["sha256"]:
            raise RuntimeError("Referenced training item changed")
        with np.load(arrays_path, allow_pickle=False) as z:
            arrays = {k: z[k].astype(np.float32) for k in ("target", "noiseless")}
        with np.load(geometry_path, allow_pickle=False) as z:
            geo = {k: z[k] for k in ("sdf", "valid")}
        return arrays, geo, load(metadata_path), entry

    def order(self, epoch):
        return np.random.default_rng(np.random.SeedSequence([self.cfg["order_seed"], epoch])).permutation(512)

    def batch(self, split, index, device, epoch=None):
        arrays, geometry, metadata, entry = self.read(split, index)
        ep = 0 if epoch is None else int(epoch)
        source = []
        for view, spec in enumerate(metadata["views"]):
            seed = np.random.SeedSequence([self.cfg["noise_seed"], {"train":0,"dev":1,"test":2}[split], ep, int(index), view])
            rng = np.random.default_rng(seed)
            value = arrays["noiseless"][view].astype(np.float64) + rng.normal(0, spec["noise_sigma_gray"]/255, arrays["noiseless"][view].shape)
            source.append(np.rint(np.clip(value, 0, 1)*255).astype(np.uint8))
        x = np.ascontiguousarray(np.stack(source)[:, None].astype(np.float32)/255)
        target = np.ascontiguousarray(arrays["target"][:, None])
        actual = np.array([-2 if v["psf_index"] < 0 else v["psf_index"] for v in metadata["views"]], np.int64)
        if split == "train":
            rng = np.random.default_rng(np.random.SeedSequence([self.cfg["operator_seed"], ep, int(index)]))
            operator = actual.copy()
            operator[rng.random(4) >= self.cfg["known_operator_probability"]] = -1
        else:
            operator = np.full_like(actual, -1)
        return {
            "source": torch.from_numpy(x).to(device),
            "target": torch.from_numpy(target).to(device),
            "sdf": torch.from_numpy(geometry["sdf"].astype(np.float32)[:, None]).to(device),
            "geometry_valid": torch.from_numpy(geometry["valid"].astype(bool)).to(device),
            "shifts_xy": torch.tensor([v["shift_xy"] for v in metadata["views"]], dtype=torch.float32, device=device),
            "actual_psf_indices": torch.from_numpy(actual).to(device),
            "operator_psf_indices": torch.from_numpy(operator).to(device),
            "core": (144, 240),
            "observation_core": (160, 224),
            "parent_id": entry["parent_id"],
            "category": entry["category"],
            "input_sha256": digest_array(x),
            "epoch": epoch,
        }
