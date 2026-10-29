"""Rebuild R128/R141 pairs with the locked 25 measured PSFs.

The source scenes, clear native targets, split membership, motion, and sensor
noise draws stay fixed. The measured PSF is already sampled on the camera
grid, so it is applied after the existing sensor area integration. The
central supervised core has 128 native pixels of source context; a 50-pixel
reflect margin prevents FFT boundary contamination.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import signal
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(str(PROJECT_ROOT / 'Experiments/R141_PSF25_AdaptiveTop4_Standalone'))
ORIGINAL = Path(str(PROJECT_ROOT / 'Experiments/R128_SourceOnlyFullTraining/data/package'))
IDENTITY = {"clean_identity", "noisy_identity"}
UNINFORMATIVE = IDENTITY | {"flat_negative"}
ASSIGNMENT_SEEDS = {"train": 1431001, "dev": 1431002, "test": 1431003}


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(2**20), b""):
            h.update(part)
    return h.hexdigest()


def sha_array(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def save_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def assignments(entries: list[dict]) -> dict[tuple[str, int], int | None]:
    result = {}
    for split, seed in ASSIGNMENT_SEEDS.items():
        selected = sorted((e for e in entries if e["split"] == split), key=lambda e: e["index"])
        active = [e for e in selected if e["category"] not in IDENTITY]
        # A shuffled cyclic list gives every kernel nearly equal exposure in
        # each split, while assignment remains independent of scene content.
        rng = np.random.default_rng(seed)
        order = np.tile(np.arange(25, dtype=np.int64), (len(active) + 24) // 25)[:len(active)]
        rng.shuffle(order)
        for e, index in zip(active, order):
            result[(split, e["index"])] = int(index)
        for e in selected:
            if e["category"] in IDENTITY:
                result[(split, e["index"])] = None
    assert len(result) == len(entries)
    return result


def original_noise(meta: dict, view: int, shape: tuple[int, int]) -> np.ndarray:
    seed = np.random.SeedSequence(int(meta["seed"])).spawn(7)[4 + view]
    return np.random.default_rng(seed).normal(
        0, float(meta["noise_sigma_gray"]) / 255, shape
    )


def convolve_native(target: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    radius = 50
    padded = np.pad(target.astype(np.float64), radius, mode="reflect")
    out = signal.fftconvolve(padded, kernel, mode="same")
    return out[radius:-radius, radius:-radius].astype(np.float32)


def main() -> None:
    src_manifest_path = BASE / "data/manifest.json"
    src_manifest = json.loads(src_manifest_path.read_text(encoding="utf-8"))
    items = sorted(src_manifest["entries"], key=lambda e: (e["split"], e["index"]))
    assert len(items) == 768
    bank_path = ROOT / "calibration/measured_psf_bank.npz"
    assert sha_file(bank_path) == "25cc6c95a224caae0e4a0380a88980551586a35cdb34eebde2635639e2c29553"
    with np.load(bank_path, allow_pickle=False) as z:
        kernels = z["all_kernels"].astype(np.float64)
    assert kernels.shape == (25, 101, 101)
    kernels /= kernels.sum(axis=(1, 2), keepdims=True)
    allocation = assignments(items)
    dest = ROOT / "data"
    manifest_entries = []
    counts = Counter()
    old_noise_replay_errors = []
    for number, entry in enumerate(items, 1):
        split, index = entry["split"], int(entry["index"])
        source_meta = json.loads((ORIGINAL / split / f"{index:04d}.json").read_text(encoding="utf-8"))
        old_meta = json.loads((BASE / "data" / entry["metadata"]).read_text(encoding="utf-8"))
        assert source_meta["parent_id"] == old_meta["parent_id"] == entry["parent_id"]
        assert source_meta["geometry_sha256"] == old_meta["geometry_sha256"]
        assigned = allocation[(split, index)]
        with np.load(BASE / "data" / entry["arrays"], allow_pickle=False) as z:
            target = z["target"].copy()
            prior_noiseless = z["noiseless"]
            prior_source = z["source"]
        assert target.shape == prior_noiseless.shape == prior_source.shape == (2, 384, 384)
        assert sha_array(target) == source_meta["array_sha256"]["target"]
        sources, noiseless = [], []
        for view in range(2):
            noise = original_noise(source_meta, view, target.shape[1:])
            old_replay = np.rint(np.clip(prior_noiseless[view].astype(float) + noise, 0, 1) * 255).astype(np.uint8)
            if not np.array_equal(old_replay, prior_source[view]):
                old_noise_replay_errors.append((entry["parent_id"], view))
            clean = target[view].copy() if assigned is None else convolve_native(target[view], kernels[assigned])
            observed = np.rint(np.clip(clean.astype(float) + noise, 0, 1) * 255).astype(np.uint8)
            noiseless.append(clean)
            sources.append(observed)
        assert not old_noise_replay_errors, old_noise_replay_errors[:3]
        arrays = {"source": np.stack(sources), "noiseless": np.stack(noiseless), "target": target}
        label = -1 if entry["category"] in UNINFORMATIVE else assigned
        assert label is not None
        meta = dict(old_meta)
        meta.update(
            psf_index=[label, label],
            applied_psf_index=assigned,
            psf_label_status="not_observable" if label < 0 else "known_simulated_assignment",
            psf_bank_sha256=sha_file(bank_path),
            formation="native_target_reflect50_measured_PSF_then_fixed_sensor_noise_and_quantization",
            source_generator_parent_sha256=sha_file(ORIGINAL / split / f"{index:04d}.json"),
        )
        output_dir = dest / split
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"{index:04d}.npz"
        sidecar = output_dir / f"{index:04d}.json"
        if path.exists() or sidecar.exists():
            raise FileExistsError(f"Refuse to overwrite generated parent: {entry['parent_id']}")
        temporary = path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
        save_json(sidecar, meta)
        manifest_entries.append(dict(
            parent_id=entry["parent_id"], split=split, index=index,
            category=entry["category"], geometry_sha256=entry["geometry_sha256"],
            arrays=str(path.relative_to(dest)), metadata=str(sidecar.relative_to(dest)),
            arrays_sha256=sha_file(path), metadata_sha256=sha_file(sidecar),
            original_arrays=entry["original_arrays"], original_metadata=entry["original_metadata"],
            applied_psf_index=assigned, psf_label_status=meta["psf_label_status"],
            target_array_sha256=sha_array(target),
        ))
        counts[(split, "identity" if assigned is None else "measured_psf")] += 1
        if number % 32 == 0:
            save_json(dest / "generation_progress.json", dict(completed=number, total=len(items)))
            print("GENERATED", number, "/", len(items), flush=True)
    manifest = dict(
        source_manifest={"path": str(src_manifest_path), "sha256": sha_file(src_manifest_path)},
        source_generator="R128_SourceOnlyFullTraining",
        measured_psf_bank_sha256=sha_file(bank_path),
        formation="same parent targets, motion, splits and exact replayed sensor noise; measured native PSF replaces synthetic blur for nonidentity parents",
        assignment_seeds=ASSIGNMENT_SEEDS,
        array_fields=["source", "noiseless", "target"],
        counts={f"{split}_{kind}": value for (split, kind), value in sorted(counts.items())},
        entries=manifest_entries,
    )
    save_json(dest / "manifest.json", manifest)
    save_json(dest / "generation_complete.json", dict(parents=len(items), bank_sha256=sha_file(bank_path), original_noise_replay_errors=0))
    print("COMPLETE", len(items), "parents", flush=True)


if __name__ == "__main__":
    main()
