import glob
import os
import random
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset


class RealImageOnlyFolder(Dataset):
    """R32-only real-domain image loader for EQ experiments."""

    def __init__(self, root_dir: str, crop_size: int = 256, exts: tuple = (".bmp",)):
        self.root_dir = str(root_dir)
        self.crop_size = int(crop_size)
        self.paths = []
        for ext in exts:
            self.paths.extend(sorted(glob.glob(os.path.join(self.root_dir, f"*{ext}"))))
        if not self.paths:
            raise RuntimeError(f"[RealImageOnlyFolder] No images found in {self.root_dir}")

    @staticmethod
    def _imread_gray(path: str) -> np.ndarray:
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise RuntimeError(f"Failed to read image: {path}")
        if img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if img.dtype == np.uint16:
            img = img.astype(np.float32) / 65535.0
        else:
            img = img.astype(np.float32) / 255.0
        return img

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = self._imread_gray(self.paths[idx])
        h, w = img.shape
        cs = self.crop_size
        if h < cs or w < cs:
            pad_h = max(cs - h, 0)
            pad_w = max(cs - w, 0)
            img = np.pad(img, ((0, pad_h), (0, pad_w)), mode="reflect")
            h, w = img.shape
        y0 = np.random.randint(0, h - cs + 1)
        x0 = np.random.randint(0, w - cs + 1)
        img = img[y0:y0 + cs, x0:x0 + cs]
        return torch.from_numpy(img).unsqueeze(0)


def build_real_eq_loader(cfg, train_src_dir: str):
    if not bool(getattr(cfg, "REAL_EQ_ENABLE", False)):
        return None
    real_eq_dir = str(getattr(cfg, "REAL_EQ_DIR", "") or "").strip()
    if not real_eq_dir:
        return None

    resolved = os.path.join(str(train_src_dir), real_eq_dir)
    if not os.path.isdir(resolved):
        resolved = real_eq_dir
    if not os.path.isdir(resolved):
        raise FileNotFoundError(f"[R32_REAL_EQ] REAL_EQ_DIR not found: {real_eq_dir}")
    image_count = len(list(Path(resolved).glob("*.bmp")))
    if image_count <= 0:
        raise RuntimeError(f"[R32_REAL_EQ] No BMP images found in {resolved}")

    ds = RealImageOnlyFolder(resolved, crop_size=int(getattr(cfg, "CROP_SIZE", 256)))
    loader = DataLoader(
        ds,
        batch_size=int(getattr(cfg, "BATCH_SIZE", 4)),
        shuffle=True,
        num_workers=0,
        pin_memory=False,
        drop_last=True,
    )
    return loader


def maybe_replace_eq_source(*, cfg, src, pred01, model, real_eq_iter, real_eq_loader, use_amp):
    eq_src = src
    eq_pred = pred01
    if real_eq_iter is None:
        return eq_src, eq_pred, real_eq_iter
    if random.random() >= float(getattr(cfg, "REAL_EQ_PROB", 0.3)):
        return eq_src, eq_pred, real_eq_iter

    try:
        real_batch = next(real_eq_iter)
    except StopIteration:
        real_eq_iter = iter(real_eq_loader)
        real_batch = next(real_eq_iter)

    eq_src = real_batch.to(src.device, non_blocking=True)
    with torch.cuda.amp.autocast(enabled=use_amp):
        eq_pred = model(eq_src).clamp(0.0, 1.0)
    return eq_src, eq_pred, real_eq_iter
