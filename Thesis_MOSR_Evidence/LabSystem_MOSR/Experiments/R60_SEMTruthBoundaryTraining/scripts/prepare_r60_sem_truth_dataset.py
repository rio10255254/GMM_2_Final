"""Prepare SEM-truth boundary training data for the 100MG Basler sample."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RECON_ROOT = LAB_ROOT / "Reconstruct_Progress" / "20260618_100MG_user_recon"
DEFAULT_MICROSCOPE_IMAGE = LAB_ROOT.parent / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
DEFAULT_TEMPLATE_CSV = DEFAULT_RECON_ROOT / "cd_measurement_20260620_basler_ace" / "cd_measurement_per_feature_basler_50x.csv"
DEFAULT_SEM_REFERENCE_CSV = DEFAULT_RECON_ROOT / "cd_measurement_20260620_basler_ace" / "sem_reference_36_radius.csv"
DEFAULT_OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r60_sem_truth_boundary" / "hs100mg_basler"
DEFAULT_PACKAGE_NAME = "r60_sem_truth_realcrop_anchor_train"

REAL_CROP_ROLE_DIR = "stage_60_hs100mg_real_crop"
ANCHOR_ROLE_DIR = "stage_60_hs100mg_sem_anchor"

CAMERA_NAME = "Basler ace acA2040-120um"
NM_PER_PX = 69.0
PITCH_NM = 5000.0
FEATURE_ALIASES = {
    "pillar": "pillar",
    "pilar": "pillar",
    "P": "pillar",
    "圓柱": "pillar",
    "circle": "pillar",
    "via": "via",
    "V": "via",
    "圓孔": "via",
    "hole": "via",
}
FEATURE_DISPLAY = {
    "pillar": "圓柱",
    "via": "圓孔",
}
SEM_COLUMN = {
    "pillar": "圓柱_sem_radius_nm",
    "via": "圓孔_sem_radius_nm",
}
SOURCE_RADIUS_BIAS_NM = {
    "pillar": 11.043151807599543,
    "via": -66.13489918240407,
}


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    return img


def _write_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", np.clip(img, 0, 255).astype(np.uint8))
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _read_csv(path: Path) -> list[dict]:
    if not Path(path).exists():
        raise FileNotFoundError(path)
    with Path(path).open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _to_float(row: dict, key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _to_int(row: dict, key: str, default: int = 0) -> int:
    try:
        return int(round(float(row.get(key, default))))
    except (TypeError, ValueError):
        return int(default)


def _feature_key(value: str) -> str:
    key = str(value).strip()
    if key in FEATURE_ALIASES:
        return FEATURE_ALIASES[key]
    lower = key.lower()
    if lower in FEATURE_ALIASES:
        return FEATURE_ALIASES[lower]
    raise ValueError(f"unknown feature name: {value!r}")


def _read_sem_reference_csv(path: Path) -> dict[str, dict[int, float]]:
    rows = _read_csv(path)
    refs: dict[str, dict[int, float]] = {"pillar": {}, "via": {}}
    for row in rows:
        idx = _to_int(row, "index", 0)
        if idx <= 0:
            continue
        for feature, col in SEM_COLUMN.items():
            value = _to_float(row, col)
            if np.isfinite(value):
                refs[feature][idx] = float(value)
    if not refs["pillar"] or not refs["via"]:
        raise RuntimeError(f"SEM reference CSV is missing pillar/via radius columns: {path}")
    return refs


def _read_sem_reference_xlsx(path: Path) -> dict[str, dict[int, float]]:
    import pandas as pd

    df = pd.read_excel(path, sheet_name="SEM data", header=None)
    refs: dict[str, dict[int, float]] = {"pillar": {}, "via": {}}
    header_rows = df.index[df.apply(lambda row: row.astype(str).str.contains("via \\(nm\\)", regex=True).any(), axis=1)]
    if len(header_rows) == 0:
        raise RuntimeError(f"could not locate SEM table header in: {path}")
    header_row = int(header_rows[0])
    header = [str(v).strip() for v in df.iloc[header_row].tolist()]
    index_col = header.index("index")
    via_col = header.index("via (nm)")
    pillar_col = header.index("pillar (nm)")
    for _, row in df.iloc[header_row + 1 :].iterrows():
        try:
            idx = int(round(float(row.iloc[index_col])))
        except (TypeError, ValueError):
            continue
        via = row.iloc[via_col]
        pillar = row.iloc[pillar_col]
        if np.isfinite(via):
            refs["via"][idx] = float(via)
        if np.isfinite(pillar):
            refs["pillar"][idx] = float(pillar)
    if not refs["pillar"] or not refs["via"]:
        raise RuntimeError(f"SEM XLSX did not yield pillar/via references: {path}")
    return refs


def read_sem_reference(path: Path) -> dict[str, dict[int, float]]:
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return _read_sem_reference_xlsx(path)
    return _read_sem_reference_csv(path)


def _sem_mean(refs: dict[str, dict[int, float]], feature: str) -> float:
    vals = list(refs[feature].values())
    if not vals:
        raise RuntimeError(f"missing SEM refs for feature={feature}")
    return float(np.mean(np.asarray(vals, dtype=np.float64)))


def _nearest_sem_id(refs: dict[str, dict[int, float]], feature: str, template_id: int) -> int | None:
    if template_id in refs[feature]:
        return int(template_id)
    return None


def _template_rows(path: Path, template_image_label: str) -> list[dict]:
    rows = []
    for row in _read_csv(path):
        if str(row.get("image", "")).strip() != str(template_image_label).strip():
            continue
        feature = _feature_key(str(row.get("feature", "")))
        x_px = _to_float(row, "x_px")
        y_px = _to_float(row, "y_px")
        radius_px = _to_float(row, "radius_px")
        if not (np.isfinite(x_px) and np.isfinite(y_px) and np.isfinite(radius_px)):
            continue
        clean = _to_int(row, "clean_for_summary", 0)
        rows.append(
            {
                "feature": feature,
                "feature_display": str(row.get("feature", FEATURE_DISPLAY[feature])).strip(),
                "id": _to_int(row, "id", len(rows) + 1),
                "x_px": float(x_px),
                "y_px": float(y_px),
                "radius_px": float(radius_px),
                "clean_for_summary": clean,
            }
        )
    if not rows:
        raise RuntimeError(f"no template rows found for image={template_image_label!r}: {path}")
    return rows


def compute_geometry_from_label(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    gray = img.astype(np.uint8, copy=False)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    threshold = max(5.0, float(np.percentile(mag, 88)))
    centerline = (mag >= threshold).astype(np.uint8) * 255
    centerline = cv2.morphologyEx(centerline, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    if np.count_nonzero(centerline) == 0:
        centerline = cv2.Canny(gray, 40, 120)
    boundary = cv2.dilate(centerline, np.ones((3, 3), np.uint8), iterations=1)
    distance = cv2.distanceTransform((boundary == 0).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
    return boundary.astype(np.uint8), centerline.astype(np.uint8), distance


def _write_geometry_for_label(lbl_path: Path, geom_root: Path, rel: Path) -> dict:
    boundary, centerline, distance = compute_geometry_from_label(_read_gray(lbl_path))
    boundary_rel = Path("geom") / "boundary" / rel
    centerline_rel = Path("geom") / "centerline" / rel
    distance_rel = Path("geom") / "distance" / rel.with_suffix(".npy")
    _write_image(geom_root.parent / boundary_rel, boundary)
    _write_image(geom_root.parent / centerline_rel, centerline)
    distance_path = geom_root.parent / distance_rel
    distance_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(distance_path, distance.astype(np.float32, copy=False))
    return {
        "geometry_boundary": boundary_rel.as_posix(),
        "geometry_centerline": centerline_rel.as_posix(),
        "geometry_distance": distance_rel.as_posix(),
    }


def _extract_centered_crop(img: np.ndarray, x_px: float, y_px: float, crop_size: int) -> np.ndarray:
    size = int(crop_size)
    if size <= 0:
        raise ValueError("crop_size must be positive")
    half = size / 2.0
    x0 = int(round(float(x_px) - half))
    y0 = int(round(float(y_px) - half))
    x1 = x0 + size
    y1 = y0 + size
    pad_l = max(0, -x0)
    pad_t = max(0, -y0)
    pad_r = max(0, x1 - img.shape[1])
    pad_b = max(0, y1 - img.shape[0])
    padded = img
    if pad_l or pad_t or pad_r or pad_b:
        padded = cv2.copyMakeBorder(img, pad_t, pad_b, pad_l, pad_r, borderType=cv2.BORDER_REFLECT_101)
    x0 += pad_l
    x1 += pad_l
    y0 += pad_t
    y1 += pad_t
    crop = padded[y0:y1, x0:x1]
    if crop.shape != (size, size):
        crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)
    return crop.astype(np.uint8, copy=False)


def _label_style_from_crop(crop: np.ndarray, feature: str) -> tuple[int, int]:
    p20 = float(np.percentile(crop, 20))
    p50 = float(np.percentile(crop, 50))
    p80 = float(np.percentile(crop, 80))
    if feature == "pillar":
        bg = int(np.clip(p50, 0, 255))
        fg = int(np.clip(max(p80 + 25.0, bg + 35.0), 0, 255))
    else:
        bg = int(np.clip(p50, 0, 255))
        fg = int(np.clip(min(p20 - 25.0, bg - 35.0), 0, 255))
    return bg, fg


def _draw_sem_label(
    *,
    feature: str,
    image_size: int,
    radius_px: float,
    bg: int,
    fg: int,
    center: tuple[float, float] | None = None,
) -> np.ndarray:
    img = np.full((int(image_size), int(image_size)), int(bg), np.uint8)
    if center is None:
        cx = cy = (int(image_size) - 1) / 2.0
    else:
        cx, cy = center
    del feature
    cv2.circle(
        img,
        (int(round(cx)), int(round(cy))),
        max(1, int(round(float(radius_px)))),
        int(fg),
        -1,
        lineType=cv2.LINE_AA,
    )
    return img


def _foreground_from_source_polarity(
    crop: np.ndarray,
    *,
    bg: int,
    local_x: float,
    local_y: float,
    radius_px: float,
    fallback_feature: str,
) -> int:
    h, w = crop.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rr = np.sqrt((xx - float(local_x)) ** 2 + (yy - float(local_y)) ** 2)
    inner = rr <= max(1.5, float(radius_px) * 0.65)
    ring = (rr >= max(2.0, float(radius_px) * 1.10)) & (rr <= max(3.0, float(radius_px) * 1.55))
    if np.count_nonzero(inner) < 4 or np.count_nonzero(ring) < 4:
        sign = 1.0 if fallback_feature == "pillar" else -1.0
        amp = 42.0
    else:
        fg_mean = float(np.mean(crop[inner]))
        bg_mean = float(np.mean(crop[ring]))
        delta = fg_mean - bg_mean
        if abs(delta) < 3.0:
            sign = 1.0 if fallback_feature == "pillar" else -1.0
            amp = 38.0
        else:
            sign = 1.0 if delta > 0.0 else -1.0
            amp = float(np.clip(abs(delta) * 1.45, 35.0, 86.0))
    return int(np.clip(float(bg) + sign * amp, 0, 255))


def _draw_sem_field_label(
    *,
    crop: np.ndarray,
    center_row: dict,
    all_rows: list[dict],
    refs: dict[str, dict[int, float]],
    crop_size: int,
) -> tuple[np.ndarray, int]:
    bg = int(np.clip(np.percentile(crop, 50), 0, 255))
    label = np.full((int(crop_size), int(crop_size)), bg, np.uint8)
    half = int(crop_size) / 2.0
    count = 0
    for row in all_rows:
        feature = str(row["feature"])
        sem_id = _nearest_sem_id(refs, feature, int(row["id"]))
        sem_radius_nm = float(refs[feature][sem_id]) if sem_id is not None else _sem_mean(refs, feature)
        radius_px = sem_radius_nm / NM_PER_PX
        local_x = half + (float(row["x_px"]) - float(center_row["x_px"]))
        local_y = half + (float(row["y_px"]) - float(center_row["y_px"]))
        margin = radius_px + 2.0
        if local_x < -margin or local_y < -margin or local_x >= int(crop_size) + margin or local_y >= int(crop_size) + margin:
            continue
        fg = _foreground_from_source_polarity(
            crop,
            bg=bg,
            local_x=local_x,
            local_y=local_y,
            radius_px=radius_px,
            fallback_feature=feature,
        )
        cv2.circle(
            label,
            (int(round(local_x)), int(round(local_y))),
            max(1, int(round(radius_px))),
            int(fg),
            -1,
            lineType=cv2.LINE_AA,
        )
        count += 1
    return label, count


def _make_anchor_source(label: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    sigma = float(rng.uniform(2.0, 3.2))
    blurred = cv2.GaussianBlur(label.astype(np.uint8, copy=False), (0, 0), sigmaX=sigma, sigmaY=sigma)
    h, w = label.shape
    x_grad = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    y_grad = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    illum = 1.0 + float(rng.uniform(-0.08, 0.08)) * x_grad + float(rng.uniform(-0.06, 0.06)) * y_grad
    out = blurred.astype(np.float32) * illum
    out += rng.normal(0.0, float(rng.uniform(2.0, 5.0)), size=label.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def _safe_clean_package_dir(package_dir: Path, output_root: Path) -> None:
    package_resolved = package_dir.resolve()
    output_resolved = output_root.resolve()
    try:
        within_output = package_resolved.is_relative_to(output_resolved)
    except AttributeError:
        within_output = str(package_resolved).lower().startswith(str(output_resolved).lower() + os.sep)
    if not within_output or package_resolved == output_resolved:
        raise RuntimeError(f"refusing to clean package outside output root: {package_resolved}")
    if package_dir.exists():
        shutil.rmtree(package_dir)


def _real_crop_rows(
    *,
    rows: list[dict],
    refs: dict[str, dict[int, float]],
    real_crop_count: int,
) -> list[tuple[dict, int, float]]:
    selected: list[tuple[dict, int, float]] = []
    clean_rows = [row for row in rows if int(row.get("clean_for_summary", 0)) == 1]
    candidates = clean_rows if clean_rows else rows
    for row in candidates:
        feature = str(row["feature"])
        sem_id = _nearest_sem_id(refs, feature, int(row["id"]))
        if sem_id is None:
            continue
        selected.append((row, sem_id, float(refs[feature][sem_id])))
        if len(selected) >= int(real_crop_count):
            break
    return selected


def _write_real_crop_pair(
    *,
    package_dir: Path,
    microscope: np.ndarray,
    all_rows: list[dict],
    refs: dict[str, dict[int, float]],
    row: dict,
    sem_reference_id: int,
    sem_radius_nm: float,
    crop_size: int,
    idx: int,
    repeat_index: int = 0,
) -> dict:
    feature = str(row["feature"])
    crop = _extract_centered_crop(microscope, float(row["x_px"]), float(row["y_px"]), int(crop_size))
    target_radius_px = float(sem_radius_nm) / NM_PER_PX
    label, neighbor_count = _draw_sem_field_label(
        crop=crop,
        center_row=row,
        all_rows=all_rows,
        refs=refs,
        crop_size=int(crop_size),
    )
    stem = f"real_{feature}_{int(row['id']):03d}_r{int(repeat_index):02d}_{idx:04d}.bmp"
    rel = Path(REAL_CROP_ROLE_DIR) / feature / stem
    _write_image(package_dir / "src" / rel, crop)
    _write_image(package_dir / "lbl" / rel, label)
    geom = _write_geometry_for_label(package_dir / "lbl" / rel, package_dir / "geom", rel)
    source_radius_nm = float(row["radius_px"]) * NM_PER_PX
    return {
        "package_src": (Path("src") / rel).as_posix(),
        "package_lbl": (Path("lbl") / rel).as_posix(),
        "source_group": "hs100mg_real_crop",
        "feature": feature,
        "feature_display": FEATURE_DISPLAY[feature],
        "template_feature": str(row.get("feature_display", FEATURE_DISPLAY[feature])),
        "template_id": int(row["id"]),
        "repeat_index": int(repeat_index),
        "sem_reference_id": int(sem_reference_id),
        "x_px": float(row["x_px"]),
        "y_px": float(row["y_px"]),
        "source_radius_nm": source_radius_nm,
        "source_radius_bias_nm": source_radius_nm - float(sem_radius_nm),
        "sem_radius_nm": float(sem_radius_nm),
        "target_radius_nm": float(sem_radius_nm),
        "target_radius_bias_nm": 0.0,
        "target_radius_px": target_radius_px,
        "label_source": "sem_truth",
        "label_neighbor_features": int(neighbor_count),
        "domain": "real_microscope_crop",
        **geom,
    }


def _sample_anchor_style(feature: str, rng: np.random.Generator) -> tuple[int, int]:
    if feature == "pillar":
        bg = int(rng.integers(58, 86))
        fg = int(rng.integers(145, 190))
    else:
        bg = int(rng.integers(132, 178))
        fg = int(rng.integers(38, 82))
    return bg, fg


def _write_anchor_pair(
    *,
    package_dir: Path,
    refs: dict[str, dict[int, float]],
    feature: str,
    idx: int,
    image_size: int,
    rng: np.random.Generator,
) -> dict:
    ids = sorted(refs[feature])
    sem_id = ids[idx % len(ids)]
    sem_radius_nm = float(refs[feature][sem_id])
    source_radius_nm = max(NM_PER_PX * 2.0, sem_radius_nm + float(SOURCE_RADIUS_BIAS_NM[feature]))
    bg, fg = _sample_anchor_style(feature, rng)
    target_radius_px = sem_radius_nm / NM_PER_PX
    source_radius_px = source_radius_nm / NM_PER_PX
    jitter = float(rng.normal(0.0, 0.35))
    center = ((int(image_size) - 1) / 2.0 + jitter, (int(image_size) - 1) / 2.0 - jitter)
    label = _draw_sem_label(
        feature=feature,
        image_size=int(image_size),
        radius_px=target_radius_px,
        bg=bg,
        fg=fg,
        center=center,
    )
    source_geom = _draw_sem_label(
        feature=feature,
        image_size=int(image_size),
        radius_px=source_radius_px,
        bg=bg,
        fg=fg,
        center=center,
    )
    source = _make_anchor_source(source_geom, rng)
    stem = f"anchor_{feature}_{idx:04d}.bmp"
    rel = Path(ANCHOR_ROLE_DIR) / feature / stem
    _write_image(package_dir / "src" / rel, source)
    _write_image(package_dir / "lbl" / rel, label)
    geom = _write_geometry_for_label(package_dir / "lbl" / rel, package_dir / "geom", rel)
    return {
        "package_src": (Path("src") / rel).as_posix(),
        "package_lbl": (Path("lbl") / rel).as_posix(),
        "source_group": "hs100mg_sem_anchor",
        "feature": feature,
        "feature_display": FEATURE_DISPLAY[feature],
        "sem_reference_id": int(sem_id),
        "source_radius_nm": source_radius_nm,
        "source_radius_bias_nm": source_radius_nm - sem_radius_nm,
        "sem_radius_nm": sem_radius_nm,
        "target_radius_nm": sem_radius_nm,
        "target_radius_bias_nm": 0.0,
        "source_radius_px": source_radius_px,
        "target_radius_px": target_radius_px,
        "label_source": "sem_truth",
        "domain": "synthetic_sem_anchor",
        **geom,
    }


def _write_anchor_pairs(
    *,
    package_dir: Path,
    refs: dict[str, dict[int, float]],
    anchor_count: int,
    image_size: int,
    seed: int,
) -> list[dict]:
    rng = np.random.default_rng(int(seed))
    records: list[dict] = []
    for idx in range(max(0, int(anchor_count))):
        feature = "pillar" if idx % 2 == 0 else "via"
        records.append(
            _write_anchor_pair(
                package_dir=package_dir,
                refs=refs,
                feature=feature,
                idx=idx // 2,
                image_size=image_size,
                rng=rng,
            )
        )
    return records


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file())


def prepare_package(
    *,
    microscope_image: Path = DEFAULT_MICROSCOPE_IMAGE,
    template_csv: Path = DEFAULT_TEMPLATE_CSV,
    sem_reference_csv: Path = DEFAULT_SEM_REFERENCE_CSV,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    package_name: str = DEFAULT_PACKAGE_NAME,
    real_crop_count: int = 72,
    real_crop_repeat: int = 1,
    anchor_count: int = 1024,
    crop_size: int = 256,
    image_size: int = 256,
    template_image_label: str = "原圖",
    seed: int = 6000,
) -> dict:
    microscope_image = Path(microscope_image).resolve()
    template_csv = Path(template_csv).resolve()
    sem_reference_csv = Path(sem_reference_csv).resolve()
    output_root = Path(output_root).resolve()
    package_dir = output_root / package_name
    if not microscope_image.exists():
        raise FileNotFoundError(microscope_image)
    _safe_clean_package_dir(package_dir, output_root)
    package_dir.mkdir(parents=True, exist_ok=True)

    microscope = _read_gray(microscope_image)
    refs = read_sem_reference(sem_reference_csv)
    rows = _template_rows(template_csv, template_image_label)
    real_records: list[dict] = []
    real_selected = _real_crop_rows(rows=rows, refs=refs, real_crop_count=int(real_crop_count))
    repeat_n = max(1, int(real_crop_repeat))
    out_idx = 0
    for repeat_idx in range(repeat_n):
        for row, sem_id, sem_radius_nm in real_selected:
            real_records.append(
                _write_real_crop_pair(
                    package_dir=package_dir,
                    microscope=microscope,
                    all_rows=rows,
                    refs=refs,
                    row=row,
                    sem_reference_id=sem_id,
                    sem_radius_nm=sem_radius_nm,
                    crop_size=int(crop_size),
                    idx=out_idx,
                    repeat_index=repeat_idx,
                )
            )
            out_idx += 1
    anchor_records = _write_anchor_pairs(
        package_dir=package_dir,
        refs=refs,
        anchor_count=int(anchor_count),
        image_size=int(image_size),
        seed=int(seed),
    )
    pairs = [*real_records, *anchor_records]
    if not pairs:
        raise RuntimeError("no R60 training pairs were generated")

    manifest = {
        "profile": package_name,
        "r60_sem_truth_boundary_training": True,
        "target_is_sem_truth": True,
        "camera": CAMERA_NAME,
        "nm_per_px": NM_PER_PX,
        "pitch_nm": PITCH_NM,
        "microscope_image": str(microscope_image),
        "template_csv": str(template_csv),
        "template_image_label": template_image_label,
        "sem_reference_csv": str(sem_reference_csv),
        "sem_radius_mean_nm": {feature: _sem_mean(refs, feature) for feature in sorted(refs)},
        "real_crop_role_dir": REAL_CROP_ROLE_DIR,
        "anchor_role_dir": ANCHOR_ROLE_DIR,
        "real_crop_unique_pairs": len(real_selected),
        "real_crop_repeat": repeat_n,
        "real_crop_pairs": len(real_records),
        "anchor_pairs": len(anchor_records),
        "total_pairs": len(pairs),
        "pairs": pairs,
        "geometry_sidecars": True,
        "geometry_count": len(pairs),
        "geom_dir": str(package_dir / "geom"),
        "forbidden_same_sample_posthoc_calibration": True,
        "generator": "prepare_r60_sem_truth_dataset_v1",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "package_dir": str(package_dir),
        "real_crop_pairs": len(real_records),
        "anchor_pairs": len(anchor_records),
        "total_pairs": len(pairs),
        "geometry_boundary_files": _count_files(package_dir / "geom" / "boundary"),
        "geometry_centerline_files": _count_files(package_dir / "geom" / "centerline"),
        "geometry_distance_files": _count_files(package_dir / "geom" / "distance"),
        "manifest": str(package_dir / "manifest.json"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare R60 SEM-truth boundary training data")
    parser.add_argument("--microscope-image", type=Path, default=DEFAULT_MICROSCOPE_IMAGE)
    parser.add_argument("--template-csv", type=Path, default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--sem-reference-csv", type=Path, default=DEFAULT_SEM_REFERENCE_CSV)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--package-name", default=DEFAULT_PACKAGE_NAME)
    parser.add_argument("--real-crop-count", type=int, default=72)
    parser.add_argument("--real-crop-repeat", type=int, default=1)
    parser.add_argument("--anchor-count", type=int, default=1024)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--template-image-label", default="原圖")
    parser.add_argument("--seed", type=int, default=6000)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    summary = prepare_package(
        microscope_image=args.microscope_image,
        template_csv=args.template_csv,
        sem_reference_csv=args.sem_reference_csv,
        output_root=args.output_root,
        package_name=args.package_name,
        real_crop_count=args.real_crop_count,
        real_crop_repeat=args.real_crop_repeat,
        anchor_count=args.anchor_count,
        crop_size=args.crop_size,
        image_size=args.image_size,
        template_image_label=args.template_image_label,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
