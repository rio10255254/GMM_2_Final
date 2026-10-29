from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[5]


OUT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/20260710_v42_full_validation/synthetic_holdout'))
RAW_DIR = OUT / "raw_blurred"
GT_DIR = OUT / "ground_truth"
SIZE = 512


def canvas() -> np.ndarray:
    return np.zeros((SIZE, SIZE), dtype=np.uint8)


def rounded_box(img: np.ndarray, rng: np.random.Generator) -> None:
    x, y = rng.integers(70, 150, size=2)
    w, h = rng.integers(210, 310, size=2)
    r = int(rng.integers(24, 58))
    cv2.rectangle(img, (int(x + r), int(y)), (int(x + w - r), int(y + h)), 255, -1)
    cv2.rectangle(img, (int(x), int(y + r)), (int(x + w), int(y + h - r)), 255, -1)
    for cx, cy in [(x + r, y + r), (x + w - r, y + r), (x + r, y + h - r), (x + w - r, y + h - r)]:
        cv2.circle(img, (int(cx), int(cy)), r, 255, -1)


def capsule(img: np.ndarray, rng: np.random.Generator) -> None:
    center = tuple(int(v) for v in rng.integers(150, 360, size=2))
    length, radius = int(rng.integers(150, 260)), int(rng.integers(28, 58))
    angle = float(rng.uniform(10, 170))
    dx, dy = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
    p1 = (int(center[0] - dx * length / 2), int(center[1] - dy * length / 2))
    p2 = (int(center[0] + dx * length / 2), int(center[1] + dy * length / 2))
    cv2.line(img, p1, p2, 255, radius * 2, cv2.LINE_AA)
    cv2.circle(img, p1, radius, 255, -1, cv2.LINE_AA)
    cv2.circle(img, p2, radius, 255, -1, cv2.LINE_AA)


def star(img: np.ndarray, rng: np.random.Generator) -> None:
    center = rng.integers(180, 330, size=2).astype(float)
    outer, inner = float(rng.integers(110, 155)), float(rng.integers(44, 75))
    rotation = float(rng.uniform(0, np.pi))
    pts = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = rotation + i * np.pi / 5
        pts.append([int(center[0] + r * np.cos(a)), int(center[1] + r * np.sin(a))])
    cv2.fillPoly(img, [np.asarray(pts, dtype=np.int32)], 255, cv2.LINE_AA)


def asymmetric_ring(img: np.ndarray, rng: np.random.Generator) -> None:
    center = tuple(int(v) for v in rng.integers(175, 340, size=2))
    axes = tuple(int(v) for v in rng.integers(105, 165, size=2))
    angle = float(rng.uniform(0, 180))
    cv2.ellipse(img, center, axes, angle, 0, 360, 255, -1, cv2.LINE_AA)
    inner_axes = (int(axes[0] * rng.uniform(0.42, 0.60)), int(axes[1] * rng.uniform(0.42, 0.60)))
    cv2.ellipse(img, center, inner_axes, angle, 0, 360, 0, -1, cv2.LINE_AA)
    notch_x = int(center[0] + rng.uniform(-0.35, 0.35) * axes[0])
    notch_y = int(center[1] + rng.uniform(-0.35, 0.35) * axes[1])
    cv2.circle(img, (notch_x, notch_y), int(rng.integers(10, 22)), 0, -1)


def nested_polygons(img: np.ndarray, rng: np.random.Generator) -> None:
    center = rng.integers(175, 340, size=2).astype(float)
    n = int(rng.integers(5, 9))
    angles = np.sort(rng.uniform(0, 2 * np.pi, n))
    radii = rng.integers(90, 165, n)
    outer = np.asarray([[int(center[0] + r * np.cos(a)), int(center[1] + r * np.sin(a))] for a, r in zip(angles, radii)], dtype=np.int32)
    inner = np.asarray([[int(center[0] + 0.50 * r * np.cos(a)), int(center[1] + 0.50 * r * np.sin(a))] for a, r in zip(angles, radii)], dtype=np.int32)
    cv2.fillPoly(img, [outer], 255, cv2.LINE_AA)
    cv2.fillPoly(img, [inner], 0, cv2.LINE_AA)


GENERATORS = [rounded_box, capsule, star, asymmetric_ring, nested_polygons]


def degrade(gt: np.ndarray, rng: np.random.Generator, polarity: str) -> tuple[np.ndarray, dict[str, float | str]]:
    sigma = float(rng.uniform(1.6, 3.8))
    blur = cv2.GaussianBlur(gt, (0, 0), sigma)
    yy, xx = np.mgrid[:SIZE, :SIZE].astype(np.float32)
    illumination = 10.0 * np.sin(xx / float(rng.uniform(80, 170))) + 8.0 * np.cos(yy / float(rng.uniform(90, 190)))
    noise_std = float(rng.uniform(3.0, 9.0))
    raw = blur.astype(np.float32) + illumination + rng.normal(0.0, noise_std, gt.shape)
    if polarity == "dark":
        raw = 255.0 - raw
    return np.clip(raw, 0, 255).round().astype(np.uint8), {"blur_sigma_px": sigma, "noise_std": noise_std, "polarity": polarity}


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    GT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260710)
    records = []
    for idx in range(20):
        gt = canvas()
        generator = GENERATORS[idx % len(GENERATORS)]
        generator(gt, rng)
        polarity = "bright" if idx % 2 == 0 else "dark"
        raw, meta = degrade(gt, rng, polarity)
        name = f"holdout_{idx + 1:02d}.bmp"
        cv2.imwrite(str(GT_DIR / name), gt)
        cv2.imwrite(str(RAW_DIR / name), raw)
        records.append({"file": name, "shape": generator.__name__, **meta})
    (OUT / "manifest.json").write_text(json.dumps({
        "purpose": "Held-out synthetic boundary test with newly generated geometry and known unblurred boundaries.",
        "seed": 20260710,
        "image_size": [SIZE, SIZE],
        "records": records,
        "important_limit": "This is a controlled simulation, not an independent microscope capture. It is used only for ground-truth boundary sensitivity.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(records)} held-out synthetic samples at {OUT}")


if __name__ == "__main__":
    main()
