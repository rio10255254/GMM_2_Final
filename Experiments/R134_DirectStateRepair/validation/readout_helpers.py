import numpy as np
import skimage.segmentation.morphsnakes as morphsnakes

def mask_center_radius(mask: np.ndarray) -> tuple[tuple[float, float], float]:
    yy, xx = np.nonzero(mask)
    if len(xx) < 8:
        raise ValueError('mask is empty')
    center = (float(np.mean(xx)), float(np.mean(yy)))
    radius = float(np.sqrt(len(xx) / np.pi))
    return (center, radius)

def radial_signature(measurement, samples: int=720) -> np.ndarray:
    circle = measurement.circles.lsc
    points = measurement.inflection_points_xy
    delta = points - np.array([circle.cx, circle.cy])
    angle = np.mod(np.arctan2(delta[:, 1], delta[:, 0]), 2.0 * np.pi)
    radius = np.linalg.norm(delta, axis=1)
    order = np.argsort(angle)
    angle = angle[order]
    radius = radius[order]
    angle = np.concatenate([angle[-1:] - 2.0 * np.pi, angle, angle[:1] + 2.0 * np.pi])
    radius = np.concatenate([radius[-1:], radius, radius[:1]])
    targets = np.linspace(0.0, 2.0 * np.pi, samples, endpoint=False)
    return np.interp(targets, angle, radius)

def reset_curvature_cycle() -> None:
    morphsnakes._curvop = morphsnakes._fcycle([lambda values: morphsnakes.sup_inf(morphsnakes.inf_sup(values)), lambda values: morphsnakes.inf_sup(morphsnakes.sup_inf(values))])
