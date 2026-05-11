"""R45 data helpers for target-family adapter training."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
R45_TARGET_STAGES = ("stage_45_motion_regions", "stage_47_motion_mixed")
IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}


def stage_from_package_path(package_path: str) -> str:
    for part in Path(str(package_path)).parts:
        if part.startswith("stage_"):
            return part
    raise ValueError(f"could not find stage component in path: {package_path}")


def load_manifest(manifest_path: str | Path) -> dict:
    return json.loads(Path(manifest_path).read_text(encoding="utf-8"))


def iter_target_motion_frames(manifest_path: str | Path, stages: tuple[str, ...] = R45_TARGET_STAGES):
    manifest = load_manifest(manifest_path)
    wanted = set(stages)
    for row in manifest["frames"]:
        if row["stage"] in wanted:
            yield row


def _read_gray01(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype == np.uint16:
        return img.astype(np.float32) / 65535.0
    if img.dtype == np.uint8:
        return img.astype(np.float32) / 255.0
    arr = img.astype(np.float32)
    maxv = float(np.nanmax(arr)) if arr.size else 1.0
    return arr / maxv if maxv > 1.5 else arr


def _read_mask01(path: Path) -> np.ndarray:
    return (_read_gray01(path) > 0.0).astype(np.float32)


def _read_distance(path: Path) -> np.ndarray:
    return np.load(str(path)).astype(np.float32, copy=False)


def _pad_if_needed(arrs: list[np.ndarray], crop_size: int) -> list[np.ndarray]:
    h, w = arrs[0].shape
    if h >= crop_size and w >= crop_size:
        return arrs
    pad_h = max(0, crop_size - h)
    pad_w = max(0, crop_size - w)
    return [np.pad(arr, ((0, pad_h), (0, pad_w)), mode="reflect") for arr in arrs]


def _crop_all(arrs: list[np.ndarray], crop_size: int, random_crop: bool) -> list[np.ndarray]:
    arrs = _pad_if_needed(arrs, crop_size)
    h, w = arrs[0].shape
    if random_crop:
        y0 = np.random.randint(0, h - crop_size + 1)
        x0 = np.random.randint(0, w - crop_size + 1)
    else:
        y0 = max(0, (h - crop_size) // 2)
        x0 = max(0, (w - crop_size) // 2)
    return [arr[y0 : y0 + crop_size, x0 : x0 + crop_size] for arr in arrs]


def _tensor(arr: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(arr.astype(np.float32, copy=False)).unsqueeze(0)


class R45MotionPairDataset(Dataset):
    def __init__(
        self,
        profile_dir: str | Path,
        *,
        stages: tuple[str, ...] = R45_TARGET_STAGES,
        crop_size: int = 256,
        random_crop: bool = True,
        max_pairs_per_stage: int | None = None,
    ):
        self.profile_dir = Path(profile_dir)
        self.crop_size = int(crop_size)
        self.random_crop = bool(random_crop)
        manifest = load_manifest(self.profile_dir / "manifest.json")
        frames = [row for row in manifest["frames"] if row["stage"] in set(stages)]
        grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
        for row in frames:
            grouped[(str(row["stage"]), int(row["sequence_id"]))].append(row)
        by_stage_count: dict[str, int] = defaultdict(int)
        pairs: list[tuple[dict, dict]] = []
        for key in sorted(grouped):
            seq = sorted(grouped[key], key=lambda r: int(r["frame_index"]))
            stage = key[0]
            for a, b in zip(seq, seq[1:]):
                if max_pairs_per_stage is not None and by_stage_count[stage] >= int(max_pairs_per_stage):
                    continue
                pairs.append((a, b))
                by_stage_count[stage] += 1
        if not pairs:
            raise RuntimeError(f"no R45 target motion pairs found: {self.profile_dir}")
        self.pairs = pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def _paths(self, row: dict) -> dict[str, Path]:
        return {
            "src": self.profile_dir / row["package_src"],
            "lbl": self.profile_dir / row["package_lbl"],
            "boundary": self.profile_dir / row["package_boundary"],
            "centerline": self.profile_dir / row["package_centerline"],
            "distance": self.profile_dir / row["package_distance"],
        }

    def __getitem__(self, idx: int) -> dict:
        a, b = self.pairs[idx]
        pa = self._paths(a)
        pb = self._paths(b)
        arrs = _crop_all(
            [
                _read_gray01(pa["src"]),
                _read_gray01(pb["src"]),
                _read_gray01(pa["lbl"]),
                _read_gray01(pb["lbl"]),
                _read_mask01(pa["boundary"]),
                _read_mask01(pb["boundary"]),
                _read_mask01(pa["centerline"]),
                _read_mask01(pb["centerline"]),
                _read_distance(pa["distance"]),
                _read_distance(pb["distance"]),
            ],
            self.crop_size,
            self.random_crop,
        )
        delta = b["delta_from_prev_px"]
        return {
            "src_a": _tensor(arrs[0]),
            "src_b": _tensor(arrs[1]),
            "lbl_a": _tensor(arrs[2]),
            "lbl_b": _tensor(arrs[3]),
            "boundary_a": _tensor(arrs[4]),
            "boundary_b": _tensor(arrs[5]),
            "centerline_a": _tensor(arrs[6]),
            "centerline_b": _tensor(arrs[7]),
            "distance_a": _tensor(arrs[8]),
            "distance_b": _tensor(arrs[9]),
            "dx": torch.tensor(float(delta.get("dx", 0.0)), dtype=torch.float32),
            "dy": torch.tensor(float(delta.get("dy", 0.0)), dtype=torch.float32),
            "family": str(b["feature_family"]),
            "stage": str(b["stage"]),
        }
