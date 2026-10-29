"""Unchanged geometry functions from the original R125 helper."""
import math
import numpy as np

def area_average(image: np.ndarray, factor: int) -> np.ndarray:
    if image.ndim != 2 or any(size % factor for size in image.shape):
        raise ValueError("Area integration needs a 2D array divisible by the sampling factor")
    height, width = image.shape
    return image.reshape(height // factor, factor, width // factor, factor).mean((1, 3), dtype=np.float64)

def _parameters(index: int, category: str, rng: np.random.Generator, size: int, core: int) -> dict:
    scale = core / 128
    center = [size / 2 + float(rng.uniform(-8, 8)) * scale,
              size / 2 + float(rng.uniform(-8, 8)) * scale]
    shape = {
        "category": category, "center_xy": center,
        "rotation_rad": float(rng.uniform(-math.pi, math.pi)), "scale": scale,
    }
    if category == "irregular_curved":
        shape.update(radius=float(rng.uniform(37, 48)) * scale,
                     ellipticity=float(rng.uniform(0.8, 1.2)),
                     harmonic3=float(rng.uniform(0.07, 0.14)),
                     harmonic5=float(rng.uniform(0.025, 0.07)),
                     phase=float(rng.uniform(-math.pi, math.pi)))
    elif category == "corners_lines_junctions":
        shape.update(bar_width=float(rng.uniform(10, 15)) * scale,
                     arm_length=float(rng.uniform(78, 94)) * scale,
                     branch_offset=float(rng.uniform(14, 20)) * scale)
    elif category == "dense_close_structures":
        shape.update(pitch=float(rng.uniform(14, 21)) * scale,
                     gap=float(rng.uniform(2.5, 4.5)) * scale,
                     motif="squares" if rng.random() < 0.5 else "disks")
    elif category == "textured_edges":
        shape.update(wave_amplitude=float(rng.uniform(4, 9)) * scale,
                     wave_period=float(rng.uniform(36, 56)) * scale)
    elif category == "clean_identity":
        # All coordinates lie on native-pixel boundaries; the identity control
        # is precisely representable on native, 4x and 8x grids.
        shape.update(center_xy=[size // 2, size // 2], rotation_rad=0.0,
                     box_half_width=max(3, round(27 * scale)),
                     box_half_height=max(3, round(36 * scale)),
                     notch_width=max(2, round(9 * scale)))
    elif category == "flat_negative":
        shape.update(foreground=False)
    else:
        raise ValueError(category)
    return shape

def object_score(x: np.ndarray, y: np.ndarray, shape: dict, shift_xy: tuple[float, float]) -> np.ndarray:
    """Continuous foreground-positive occupancy function, not a claimed exact SDF."""
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    dx = x - shape["center_xy"][0] - shift_xy[0]
    dy = y - shape["center_xy"][1] - shift_xy[1]
    cosine, sine = math.cos(shape["rotation_rad"]), math.sin(shape["rotation_rad"])
    u, v = cosine * dx + sine * dy, -sine * dx + cosine * dy
    category = shape["category"]
    if category == "irregular_curved":
        ue = u / shape["ellipticity"]
        theta = np.arctan2(v, ue)
        boundary_radius = shape["radius"] * (
            1 + shape["harmonic3"] * np.cos(3 * theta + shape["phase"])
            + shape["harmonic5"] * np.sin(5 * theta - shape["phase"])
        )
        return boundary_radius - np.hypot(ue, v)
    if category == "corners_lines_junctions":
        width, length, offset = shape["bar_width"], shape["arm_length"], shape["branch_offset"]
        vertical = np.minimum(width / 2 - np.abs(u + offset), length / 2 - np.abs(v))
        horizontal = np.minimum(length / 2 - np.abs(u), width / 2 - np.abs(v - offset))
        branch = np.minimum(width / 2 - np.abs((u - v) / math.sqrt(2)), length * 0.3 - np.abs((u + v) / math.sqrt(2)))
        return np.maximum(np.maximum(vertical, horizontal), branch)
    if category == "dense_close_structures":
        pitch, gap = shape["pitch"], shape["gap"]
        tx = (u + pitch / 2) % pitch - pitch / 2
        ty = (v + pitch / 2) % pitch - pitch / 2
        half = (pitch - gap) / 2
        return half - (np.maximum(np.abs(tx), np.abs(ty)) if shape["motif"] == "squares" else np.hypot(tx, ty))
    if category == "textured_edges":
        return u + shape["wave_amplitude"] * np.sin(2 * math.pi * v / shape["wave_period"])
    if category == "clean_identity":
        box = np.minimum(shape["box_half_width"] - np.abs(u), shape["box_half_height"] - np.abs(v))
        notch = np.minimum(shape["notch_width"] - np.abs(u), shape["box_half_height"] - v)
        # Subtract a narrow slot entering from the upper end, making two corners.
        notch = np.minimum(notch, v)
        return np.minimum(box, -notch)
    return np.full(np.broadcast_shapes(x.shape, y.shape), 1.0 if shape["foreground"] else -1.0, dtype=np.float64)
