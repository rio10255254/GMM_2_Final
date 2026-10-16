from __future__ import annotations

import csv
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares
from scipy.special import expit


ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\tests\artifacts\cd_verification_20260714")
FIT_ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\output\pillar_via_junction_psf_20260713")
ANALYZE_PATH = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data"
    r"\center9_pillar_fit_20x_50x\psf_deconvolution_cd\analyze_cd.py"
)
CROP_ORIGINS = {"20x": (1794, 838), "50x": (874, 586)}

spec = importlib.util.spec_from_file_location("center9_analyze_cd", ANALYZE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)
measure_cd = module.measure_cd


@dataclass(frozen=True)
class SigmoidCircle:
    cd_px: float
    center_xy: np.ndarray
    radius_px: float
    edge_width_px: float
    angular_mad_px: float
    valid_angles: int


def sigmoid_circle_measurement(
    image: np.ndarray,
    nominal_center_xy: np.ndarray,
    pitch_px: float,
    angle_count: int = 72,
) -> SigmoidCircle:
    radial_step = 0.08
    radii = np.arange(0.0, 0.38 * pitch_px + radial_step, radial_step)
    angles = np.linspace(0.0, 2.0 * np.pi, angle_count, endpoint=False)
    x = nominal_center_xy[0] + np.cos(angles)[:, None] * radii[None, :]
    y = nominal_center_xy[1] + np.sin(angles)[:, None] * radii[None, :]
    profiles = map_coordinates(image, [y, x], order=3, mode="reflect")
    fit_mask = (radii >= 0.05 * pitch_px) & (radii <= 0.37 * pitch_px)
    fit_r = radii[fit_mask]
    edge_radii: list[float] = []
    edge_widths: list[float] = []
    edge_angles: list[float] = []

    for angle, profile in zip(angles, profiles):
        fit_y = profile[fit_mask]
        core = float(np.median(profile[radii <= 0.08 * pitch_px]))
        background = float(
            np.median(profile[(radii >= 0.30 * pitch_px) & (radii <= 0.36 * pitch_px)])
        )
        amplitude = background - core
        if amplitude <= 1e-6:
            continue

        def residual(parameters: np.ndarray) -> np.ndarray:
            low, high, edge, log_width = parameters
            width = np.exp(log_width)
            prediction = low + (high - low) * expit((fit_r - edge) / width)
            return prediction - fit_y

        local_min = float(np.min(fit_y))
        local_max = float(np.max(fit_y))
        bounds_low = [local_min - 0.25 * amplitude, core, 0.15 * pitch_px, np.log(0.05)]
        bounds_high = [background, local_max + 0.25 * amplitude, 0.34 * pitch_px, np.log(0.12 * pitch_px)]
        initial = [core, background, 0.26 * pitch_px, np.log(max(0.5, 0.03 * pitch_px))]
        try:
            fitted = least_squares(
                residual,
                initial,
                bounds=(bounds_low, bounds_high),
                loss="soft_l1",
                f_scale=max(0.01 * amplitude, 1e-5),
                max_nfev=120,
            )
        except ValueError:
            continue
        if not fitted.success:
            continue
        edge_radii.append(float(fitted.x[2]))
        edge_widths.append(float(2.0 * np.log(9.0) * np.exp(fitted.x[3])))
        edge_angles.append(float(angle))

    if len(edge_radii) < int(0.9 * angle_count):
        raise RuntimeError(f"Only {len(edge_radii)}/{angle_count} sigmoid edges were valid")
    used_angles = np.asarray(edge_angles)
    edge_radii_array = np.asarray(edge_radii)
    points = np.column_stack(
        (
            nominal_center_xy[0] + edge_radii_array * np.cos(used_angles),
            nominal_center_xy[1] + edge_radii_array * np.sin(used_angles),
        )
    )

    def circle_residual(parameters: np.ndarray) -> np.ndarray:
        cx, cy, radius = parameters
        return np.hypot(points[:, 0] - cx, points[:, 1] - cy) - radius

    circle = least_squares(
        circle_residual,
        [nominal_center_xy[0], nominal_center_xy[1], np.median(edge_radii_array)],
        bounds=(
            [nominal_center_xy[0] - 0.12 * pitch_px, nominal_center_xy[1] - 0.12 * pitch_px, 0.15 * pitch_px],
            [nominal_center_xy[0] + 0.12 * pitch_px, nominal_center_xy[1] + 0.12 * pitch_px, 0.34 * pitch_px],
        ),
        loss="soft_l1",
        f_scale=0.05,
    )
    radius = float(circle.x[2])
    return SigmoidCircle(
        cd_px=2.0 * radius,
        center_xy=np.asarray(circle.x[:2]),
        radius_px=radius,
        edge_width_px=float(np.median(edge_widths)),
        angular_mad_px=float(np.median(np.abs(edge_radii_array - np.median(edge_radii_array)))),
        valid_angles=len(edge_radii),
    )


def summarize(
    label: str,
    algorithm: str,
    parameter: float,
    measurement: str,
    measurements: list,
    sem_nm: np.ndarray,
    nm_per_px: float,
) -> dict:
    cd_nm = np.asarray([item.cd_px for item in measurements]) * nm_per_px
    errors = cd_nm - sem_nm
    return {
        "magnification": label,
        "algorithm": algorithm,
        "parameter": parameter,
        "measurement": measurement,
        "mean_cd_nm": float(np.mean(cd_nm)),
        "bias_nm": float(np.mean(errors)),
        "mae_nm": float(np.mean(np.abs(errors))),
        "max_abs_error_nm": float(np.max(np.abs(errors))),
        "rmse_nm": float(np.sqrt(np.mean(errors**2))),
        "mean_edge_width_px": float(np.mean([item.edge_width_px for item in measurements])),
        "mean_angular_mad_nm": float(
            np.mean([
                item.angular_mad_px if hasattr(item, "angular_mad_px") else item.angle_mad_px
                for item in measurements
            ]) * nm_per_px
        ),
        "cd_values_nm": json.dumps(cd_nm.tolist()),
    }


rows: list[dict] = []
for label in ("20x", "50x"):
    sweep = loadmat(ROOT / f"{label}_deconvolution_sweep.mat")
    raw = np.asarray(sweep["I"], dtype=float)
    nsr_values = np.asarray(sweep["nsr_values"]).reshape(-1)
    rl_iterations = np.asarray(sweep["rl_iterations"]).reshape(-1)
    with (FIT_ROOT / label / "selected_frame.json").open(encoding="utf-8") as handle:
        meta = json.load(handle)
    crop_x1, crop_y1 = CROP_ORIGINS[label]
    centers = np.asarray(meta["pillar_centers_xy"], dtype=float)
    centers -= np.array([crop_x1 - 1, crop_y1 - 1])
    pitch_px = float(meta["pitch_px"])
    nm_per_px = float(meta["object_pixel_um"]) * 1000.0
    sem_nm = np.asarray(meta["image_oriented_sem_cd_nm"], dtype=float).reshape(-1)

    candidates: list[tuple[str, float, np.ndarray]] = [("raw", 0.0, raw)]
    for algorithm in ("direct_wiener", "contrast_wiener"):
        stack = np.asarray(sweep[algorithm], dtype=float)
        candidates.extend((algorithm, float(value), stack[:, :, idx]) for idx, value in enumerate(nsr_values))
    rl_stack = np.asarray(sweep["contrast_rl"], dtype=float)
    candidates.extend(("contrast_rl", float(value), rl_stack[:, :, idx]) for idx, value in enumerate(rl_iterations))

    for algorithm, parameter, image in candidates:
        try:
            relative = [measure_cd(image, center, pitch_px) for center in centers]
            rows.append(summarize(label, algorithm, parameter, "relative50", relative, sem_nm, nm_per_px))
        except RuntimeError as exception:
            print(f"SKIP {label} {algorithm} {parameter:g} relative50: {exception}")
        try:
            sigmoid = [sigmoid_circle_measurement(image, center, pitch_px) for center in centers]
            rows.append(summarize(label, algorithm, parameter, "sigmoid_circle", sigmoid, sem_nm, nm_per_px))
        except RuntimeError as exception:
            print(f"SKIP {label} {algorithm} {parameter:g} sigmoid_circle: {exception}")

output_path = ROOT / "cd_method_deconvolution_sweep.csv"
with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

for label in ("20x", "50x"):
    for measurement in ("relative50", "sigmoid_circle"):
        subset = [r for r in rows if r["magnification"] == label and r["measurement"] == measurement]
        raw_row = next(r for r in subset if r["algorithm"] == "raw")
        feasible = [
            r for r in subset
            if r["algorithm"] != "raw"
            and r["mae_nm"] < raw_row["mae_nm"]
            and r["mean_edge_width_px"] < raw_row["mean_edge_width_px"]
        ]
        best = min(feasible, key=lambda r: r["mae_nm"], default=None)
        print(json.dumps({"label": label, "measurement": measurement, "raw": raw_row, "best_joint_improvement": best}, ensure_ascii=False))

print(output_path)
