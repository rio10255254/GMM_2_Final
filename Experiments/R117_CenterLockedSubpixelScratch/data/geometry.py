"""Pure procedural, supersampled geometry used by the R117 data builder."""

from __future__ import annotations

import math
import cv2
import numpy as np


def polygon_points(center, radius, count, phase, radial=None):
    angles = phase + np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
    radii = np.full(count, radius, dtype=np.float32) if radial is None else np.asarray(radial, dtype=np.float32)
    return np.stack((center[0] + radii * np.cos(angles), center[1] + radii * np.sin(angles)), axis=1).round().astype(np.int32)


def draw_single(mask: np.ndarray, family: str, rng: np.random.Generator, scale: float = 1.0) -> None:
    height, width = mask.shape
    cx, cy = float(rng.uniform(0.28, 0.72) * width), float(rng.uniform(0.28, 0.72) * height)
    radius = float(rng.uniform(0.12, 0.27) * min(height, width) * scale)
    if family == "circle":
        cv2.circle(mask, (round(cx), round(cy)), max(2, round(radius)), 255, -1, cv2.LINE_AA)
    elif family == "ellipse":
        axes = (max(2, round(radius * rng.uniform(0.65, 1.35))), max(2, round(radius * rng.uniform(0.42, 0.92))))
        cv2.ellipse(mask, (round(cx), round(cy)), axes, float(rng.uniform(-70, 70)), 0, 360, 255, -1, cv2.LINE_AA)
    elif family == "rectangle":
        rect = ((cx, cy), (radius * rng.uniform(1.1, 2.2), radius * rng.uniform(0.8, 1.8)), float(rng.uniform(-70, 70)))
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), 255, cv2.LINE_AA)
    elif family == "polygon":
        count = int(rng.integers(4, 10))
        radial = radius * rng.uniform(0.72, 1.20, count)
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], 255, cv2.LINE_AA)
    elif family == "ring":
        cv2.circle(mask, (round(cx), round(cy)), max(3, round(radius)), 255, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx), round(cy)), max(1, round(radius * rng.uniform(0.42, 0.74))), 0, -1, cv2.LINE_AA)
    elif family == "crescent":
        cv2.circle(mask, (round(cx), round(cy)), max(3, round(radius)), 255, -1, cv2.LINE_AA)
        offset = radius * rng.uniform(0.25, 0.52)
        cv2.circle(mask, (round(cx + offset), round(cy + rng.uniform(-0.15, 0.15) * radius)), max(2, round(radius * rng.uniform(0.80, 0.94))), 0, -1, cv2.LINE_AA)
    elif family == "lobed":
        count = 160
        angle = np.arange(count, dtype=np.float32) * 2.0 * math.pi / count
        radial = radius * (1.0 + rng.uniform(0.10, 0.28) * np.sin(int(rng.integers(3, 10)) * angle + rng.uniform(-math.pi, math.pi)))
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, 0.0, radial)], 255, cv2.LINE_AA)
    elif family == "thin_neck":
        left, right = (round(cx - 0.52 * radius), round(cy)), (round(cx + 0.52 * radius), round(cy))
        disk = max(2, round(radius * rng.uniform(0.48, 0.68)))
        cv2.circle(mask, left, disk, 255, -1, cv2.LINE_AA)
        cv2.circle(mask, right, disk, 255, -1, cv2.LINE_AA)
        neck = max(1, round(radius * rng.uniform(0.07, 0.20)))
        cv2.rectangle(mask, (left[0], round(cy - neck)), (right[0], round(cy + neck)), 255, -1)
    elif family == "thin_bar":
        rect = ((cx, cy), (radius * rng.uniform(2.0, 4.2), max(2.0, radius * rng.uniform(0.10, 0.28))), float(rng.uniform(-90, 90)))
        cv2.fillConvexPoly(mask, cv2.boxPoints(rect).round().astype(np.int32), 255, cv2.LINE_AA)
    elif family == "irregular_blob":
        count = int(rng.integers(10, 24))
        radial = radius * rng.uniform(0.58, 1.28, count)
        radial = np.convolve(np.r_[radial[-2:], radial, radial[:2]], np.ones(5) / 5.0, mode="valid")
        cv2.fillPoly(mask, [polygon_points((cx, cy), radius, count, float(rng.uniform(0, math.pi)), radial)], 255, cv2.LINE_AA)
    else:
        raise ValueError(family)


def draw_mask(size: int, factor: int, family: str, rng: np.random.Generator) -> np.ndarray:
    high = size * factor
    mask = np.zeros((high, high), np.uint8)
    if family == "dense_array":
        pitch = int(rng.integers(max(12, factor * 5), max(18, factor * 13)))
        radius = max(2, int(pitch * rng.uniform(0.22, 0.42)))
        ox, oy = int(rng.integers(0, pitch)), int(rng.integers(0, pitch))
        for y in range(oy - pitch, high + pitch, pitch):
            for x in range(ox - pitch, high + pitch, pitch):
                if rng.random() > 0.08:
                    cv2.circle(mask, (x, y), radius, 255, -1, cv2.LINE_AA)
        if rng.random() < 0.45:
            cv2.circle(mask, (int(rng.uniform(0.2, 0.8) * high), int(rng.uniform(0.2, 0.8) * high)), radius, 0, -1, cv2.LINE_AA)
    elif family == "mixed_field":
        choices = ("circle", "ellipse", "rectangle", "polygon", "ring", "thin_bar", "irregular_blob")
        for _ in range(int(rng.integers(3, 9))):
            draw_single(mask, str(rng.choice(choices)), rng, float(rng.uniform(0.40, 0.82)))
    else:
        draw_single(mask, family, rng)
    return mask


def analytic_texture(size: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    texture = np.zeros((size, size), np.float32)
    for _ in range(int(rng.integers(2, 6))):
        angle = float(rng.uniform(0, math.pi))
        period = float(np.exp(rng.uniform(np.log(2.6), np.log(22.0))))
        phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = xx * math.cos(angle) + yy * math.sin(angle)
        texture += float(rng.uniform(0.3, 1.0)) * np.sin(2.0 * math.pi * coordinate / period + phase)
    texture -= float(texture.mean())
    return np.clip(texture / max(float(np.percentile(np.abs(texture), 99.0)), 1.0e-6), -1.0, 1.0)


def translate_high(value: np.ndarray, dx: float, dy: float, factor: int, interpolation: int) -> np.ndarray:
    matrix = np.asarray(((1, 0, dx * factor), (0, 1, dy * factor)), np.float32)
    return cv2.warpAffine(value, matrix, (value.shape[1], value.shape[0]), flags=interpolation, borderMode=cv2.BORDER_REFLECT_101)
