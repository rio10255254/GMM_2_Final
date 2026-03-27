from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io
import torch


VAL_LOG_SUFFIX = "_val_log_v5.csv"
ATTRIB_HEADER_RE = re.compile(
    r"expect_dx_px=(?P<dx>[^ ]+)\s+expect_dy_px=(?P<dy>[^ ]+)\s+expected_step_px=(?P<step>[^ ]+)\s+expected_enable=(?P<enable>\d+)"
)


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def _find_single(run_dir: Path, pattern: str) -> Path:
    matches = sorted(run_dir.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No match for {pattern} under {run_dir}")
    if len(matches) > 1:
        raise RuntimeError(f"Expected single match for {pattern} under {run_dir}, found {len(matches)}")
    return matches[0]


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = []
        for raw in reader:
            row = dict(raw)
            for key, value in list(row.items()):
                if key == "epoch":
                    row[key] = int(float(value))
                else:
                    maybe = _safe_float(value)
                    row[key] = maybe if math.isfinite(maybe) else value
            rows.append(row)
    return rows


def _parse_monitor_meta(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        maybe = _safe_float(value)
        meta[key] = maybe if math.isfinite(maybe) else value
    return meta


def _parse_attribution_header(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ATTRIB_HEADER_RE.search(line)
        if not match:
            continue
        groups = match.groupdict()
        for key, value in groups.items():
            if value == "None":
                info[key] = None
            elif key == "enable":
                info[key] = int(value)
            else:
                maybe = _safe_float(value)
                info[key] = maybe if math.isfinite(maybe) else value
        break
    return info


def _infer_val_signature(epochs: list[int]) -> str:
    if len(epochs) < 2:
        return "single"
    diffs = [b - a for a, b in zip(epochs[:-1], epochs[1:])]
    uniq = sorted(set(diffs))
    if len(uniq) == 1:
        return f"every_{uniq[0]}"
    return "mixed:" + ",".join(str(x) for x in uniq)


def _weights_summary(weights_dir: Path) -> dict[str, Any]:
    best = weights_dir / "best_tradeoff.pth.tar"
    latest = weights_dir / "latest.pth.tar"
    return {
        "best_tradeoff_path": str(best) if best.exists() else None,
        "best_tradeoff_mtime": best.stat().st_mtime if best.exists() else None,
        "latest_path": str(latest) if latest.exists() else None,
        "latest_mtime": latest.stat().st_mtime if latest.exists() else None,
    }


def load_run_profile(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    run_meta_path = run_dir / "run_meta.json"
    run_meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
    val_log_path = _find_single(run_dir, f"*{VAL_LOG_SUFFIX}")
    monitor_meta_path = _find_single(run_dir, "*monitor_meta.txt")
    attrib_path = run_dir / "attribution_log.txt"
    weights_dir = run_dir / "weights"

    rows = _load_csv_rows(val_log_path)
    epochs = [int(r["epoch"]) for r in rows]
    best_tradeoff = max(rows, key=lambda r: _safe_float(r.get("tradeoff_score", math.nan)))
    proxy_nonzero = sum(1 for r in rows if _safe_float(r.get("proxy_score_mean", math.nan)) > 0)
    gmf_nonzero = sum(1 for r in rows if abs(_safe_float(r.get("gmf_obj", math.nan))) > 1e-12)

    profile = {
        "run_dir": str(run_dir),
        "run_meta": run_meta,
        "model_name": run_meta.get("model_name"),
        "run_tag": run_meta.get("run_tag"),
        "amp": bool(run_meta.get("amp")),
        "seed": run_meta.get("seed"),
        "seed_deterministic": bool(run_meta.get("seed_deterministic")),
        "cudnn_deterministic": bool(run_meta.get("cudnn_deterministic")),
        "cudnn_benchmark": bool(run_meta.get("cudnn_benchmark")),
        "tf32_matmul": bool(run_meta.get("tf32_matmul")),
        "tf32_cudnn": bool(run_meta.get("tf32_cudnn")),
        "device": run_meta.get("device"),
        "torch_version": run_meta.get("torch_version"),
        "val_log_path": str(val_log_path),
        "val_epoch_count": len(epochs),
        "val_epoch_first": epochs[0],
        "val_epoch_last": epochs[-1],
        "val_every_signature": _infer_val_signature(epochs),
        "best_tradeoff_epoch": int(best_tradeoff["epoch"]),
        "best_tradeoff_score": _safe_float(best_tradeoff.get("tradeoff_score")),
        "proxy_nonzero_epochs": proxy_nonzero,
        "gmf_nonzero_epochs": gmf_nonzero,
        "monitor_meta": _parse_monitor_meta(monitor_meta_path),
        "attribution": _parse_attribution_header(attrib_path) if attrib_path.exists() else {},
    }
    profile.update(_weights_summary(weights_dir))
    return profile


def build_delta_matrix(old_profile: dict[str, Any], new_profile: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "model_name",
        "run_tag",
        "amp",
        "seed_deterministic",
        "cudnn_deterministic",
        "cudnn_benchmark",
        "tf32_matmul",
        "tf32_cudnn",
        "device",
        "torch_version",
        "val_epoch_count",
        "val_epoch_last",
        "val_every_signature",
        "best_tradeoff_epoch",
        "proxy_nonzero_epochs",
        "gmf_nonzero_epochs",
    ]

    changed = []
    unchanged = []
    for field in fields:
        row = {"field": field, "old": old_profile.get(field), "new": new_profile.get(field)}
        if row["old"] != row["new"]:
            changed.append(row)
        else:
            unchanged.append(row)

    for label, key in [
        ("expected_enable", "enable"),
        ("expected_step_px", "step"),
        ("expect_dx_px", "dx"),
        ("expect_dy_px", "dy"),
    ]:
        row = {
            "field": label,
            "old": old_profile.get("attribution", {}).get(key),
            "new": new_profile.get("attribution", {}).get(key),
        }
        if row["old"] != row["new"]:
            changed.append(row)
        else:
            unchanged.append(row)

    return {"changed": changed, "unchanged": unchanged}


def _extract_psf_grid(path: Path) -> np.ndarray:
    mat = scipy.io.loadmat(str(path), squeeze_me=False, struct_as_record=False)
    if "psf_grid" in mat:
        psf_grid = mat["psf_grid"]
    elif "fitted_psf" in mat:
        psf_grid = mat["fitted_psf"]
    elif "fov_psf_data" in mat and hasattr(mat["fov_psf_data"], "psf_grid"):
        psf_grid = mat["fov_psf_data"].psf_grid
    else:
        fov = mat.get("fov_psf_data")
        if isinstance(fov, np.ndarray) and fov.size == 1:
            obj = fov.item()
            if hasattr(obj, "psf_grid"):
                psf_grid = obj.psf_grid
            else:
                raise KeyError(f"psf_grid not found in {path}")
        else:
            keys = [k for k in mat.keys() if not k.startswith("__")]
            raise KeyError(f"Expected psf_grid/fitted_psf/fov_psf_data in {path}, found {keys}")
    psf_grid = np.asarray(psf_grid, dtype=np.float32)
    if psf_grid.ndim == 2:
        psf_grid = psf_grid[:, :, None, None]
    elif psf_grid.ndim == 3:
        psf_grid = psf_grid[:, :, :, None]
    elif psf_grid.ndim != 4:
        raise ValueError(f"Unsupported PSF shape: {psf_grid.shape}")
    return psf_grid


def _psf_centroid(psf: np.ndarray) -> tuple[float, float]:
    h, w = psf.shape
    yy, xx = np.indices((h, w), dtype=np.float64)
    total = float(psf.sum())
    if total <= 0:
        return float("nan"), float("nan")
    cy = float((yy * psf).sum() / total)
    cx = float((xx * psf).sum() / total)
    return cy, cx


def _radius_at_energy(psf: np.ndarray, q: float) -> float:
    h, w = psf.shape
    cy, cx = _psf_centroid(psf)
    yy, xx = np.indices((h, w), dtype=np.float64)
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2).reshape(-1)
    vals = psf.reshape(-1)
    order = np.argsort(rr)
    rr = rr[order]
    vals = vals[order]
    cdf = np.cumsum(vals)
    if cdf.size == 0 or cdf[-1] <= 0:
        return float("nan")
    cdf /= cdf[-1]
    idx = int(np.searchsorted(cdf, q, side="left"))
    idx = min(max(idx, 0), rr.size - 1)
    return float(rr[idx])


def _mean_psf_summary(psf_grid: np.ndarray) -> dict[str, Any]:
    mean_psf = psf_grid.mean(axis=(2, 3))
    mean_psf /= max(float(mean_psf.sum()), 1e-12)
    cy, cx = _psf_centroid(mean_psf)
    peak_y, peak_x = np.unravel_index(int(np.argmax(mean_psf)), mean_psf.shape)
    return {
        "cy": cy,
        "cx": cx,
        "peak_y": int(peak_y),
        "peak_x": int(peak_x),
        "peak": float(mean_psf[peak_y, peak_x]),
        "r50": _radius_at_energy(mean_psf, 0.50),
        "r90": _radius_at_energy(mean_psf, 0.90),
    }


def _stack_stability(psf_grid: np.ndarray) -> dict[str, Any]:
    peaks_y = []
    peaks_x = []
    cents_y = []
    cents_x = []
    for r in range(psf_grid.shape[2]):
        for c in range(psf_grid.shape[3]):
            psf = psf_grid[:, :, r, c]
            py, px = np.unravel_index(int(np.argmax(psf)), psf.shape)
            cy, cx = _psf_centroid(psf)
            peaks_y.append(py)
            peaks_x.append(px)
            cents_y.append(cy)
            cents_x.append(cx)
    return {
        "peak_y_min": int(min(peaks_y)),
        "peak_y_max": int(max(peaks_y)),
        "peak_x_min": int(min(peaks_x)),
        "peak_x_max": int(max(peaks_x)),
        "centroid_y_std": float(np.std(cents_y)),
        "centroid_x_std": float(np.std(cents_x)),
    }


def summarize_psf_pair(old_psf_path: Path, new_psf_path: Path) -> dict[str, Any]:
    old_grid = _extract_psf_grid(Path(old_psf_path))
    new_grid = _extract_psf_grid(Path(new_psf_path))
    old_mean = _mean_psf_summary(old_grid)
    new_mean = _mean_psf_summary(new_grid)
    return {
        "old_mean_psf": old_mean,
        "new_mean_psf": new_mean,
        "old_stack": _stack_stability(old_grid),
        "new_stack": _stack_stability(new_grid),
        "r50_delta": float(new_mean["r50"] - old_mean["r50"]),
        "r90_delta": float(new_mean["r90"] - old_mean["r90"]),
        "centroid_shift_y": float(new_mean["cy"] - old_mean["cy"]),
        "centroid_shift_x": float(new_mean["cx"] - old_mean["cx"]),
    }


def load_psf_tensor(psf_path: Path) -> torch.Tensor:
    grid = _extract_psf_grid(Path(psf_path))
    h, w, rows, cols = grid.shape
    stack = grid.reshape(h, w, rows * cols)
    stack = np.transpose(stack, (2, 0, 1))
    stack = stack / np.clip(stack.sum(axis=(1, 2), keepdims=True), 1e-12, None)
    return torch.from_numpy(stack).unsqueeze(0).float()


def collect_selector_candidates(val_log_path: Path, requested_epochs: tuple[int, ...] = (10, 15, 20, 25, 30, 50, 75, 100)) -> dict[str, Any]:
    rows = _load_csv_rows(Path(val_log_path))
    by_epoch = {int(row["epoch"]): row for row in rows}
    selected = []
    for epoch in requested_epochs:
        if epoch in by_epoch:
            selected.append(by_epoch[epoch])
    best_tradeoff = max(rows, key=lambda r: _safe_float(r.get("tradeoff_score", math.nan)))
    if int(best_tradeoff["epoch"]) not in {int(item["epoch"]) for item in selected}:
        selected.append(best_tradeoff)
    selected.sort(key=lambda item: int(item["epoch"]))
    return {"best_tradeoff": best_tradeoff, "selected_epochs": selected}


def apply_psf_buffers(model: torch.nn.Module, psf_tensor: torch.Tensor, grid_rows: int = 10, grid_cols: int = 10) -> None:
    if psf_tensor.ndim != 4:
        raise ValueError(f"Expected psf_tensor [1,N,H,W], got {tuple(psf_tensor.shape)}")
    if psf_tensor.shape[0] != 1:
        raise ValueError("psf_tensor batch dimension must be 1")
    psf_tensor = psf_tensor.detach().clone()
    sums = psf_tensor.sum(dim=(2, 3), keepdim=True)
    sums[sums == 0] = 1.0
    psf_tensor = psf_tensor / sums

    physics = getattr(model, "physics_layer", None)
    if physics is not None:
        device = physics.PSFs.device
        dtype = physics.PSFs.dtype
        psf_tensor = psf_tensor.to(device=device, dtype=dtype)
        center_idx = (grid_rows // 2) * grid_cols + (grid_cols // 2)
        physics.PSFs = psf_tensor
        physics.PSF_mean = psf_tensor.mean(dim=1, keepdim=True)
        physics.PSF_center = psf_tensor[:, center_idx:center_idx + 1]
        physics.psf_grid_rows = grid_rows
        physics.psf_grid_cols = grid_cols

    weak = getattr(model, "weak_psf_block", None)
    if weak is not None and hasattr(weak, "PSFs"):
        weak_psf = psf_tensor.to(device=weak.PSFs.device, dtype=weak.PSFs.dtype)
        k = int(getattr(weak, "k", weak.PSFs.shape[1]))
        indices = list(getattr(weak, "psf_indices", tuple(range(k))))
        weak.PSFs = weak_psf[:, indices[:k]]
        weak.psf_grid_rows = grid_rows
        weak.psf_grid_cols = grid_cols


@dataclass
class MarkdownTable:
    headers: list[str]
    rows: list[list[Any]]

    def render(self) -> str:
        lines = [
            "| " + " | ".join(self.headers) + " |",
            "| " + " | ".join(["---"] * len(self.headers)) + " |",
        ]
        for row in self.rows:
            lines.append("| " + " | ".join(str(x) for x in row) + " |")
        return "\n".join(lines)
