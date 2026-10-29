from __future__ import annotations

from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[5]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/20260710_v42_full_validation/circle_round1'))
CASES = {
    "raw": ROOT / "inputs_first50_crop2048",
    "v42_e120": ROOT / "reconstructions_crop2048" / "reconstruct_progress_epoch_120_in_inputs_first50_crop2048_20260709_202713" / "v42_e120",
}
TABLE = ROOT / "tables"
FIG = ROOT / "figures"


def fit_circle(points: np.ndarray) -> tuple[float, float, float, np.ndarray]:
    x = points[:, 0].astype(np.float64)
    y = points[:, 1].astype(np.float64)
    design = np.column_stack([x, y, np.ones_like(x)])
    target = -(x * x + y * y)
    a, b, c = np.linalg.lstsq(design, target, rcond=None)[0]
    cx, cy = -a / 2.0, -b / 2.0
    radius = float(np.sqrt(max(0.0, cx * cx + cy * cy - c)))
    radial = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    return float(cx), float(cy), radius, radial - radius


def contour_candidates(path: Path) -> list[dict[str, object]]:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None or image.shape != (2048, 2048):
        raise RuntimeError(f"Invalid image {path}")
    smooth = cv2.GaussianBlur(image, (0, 0), 1.2)
    _, binary = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    candidates: list[dict[str, object]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not 300000 <= area <= 750000:
            continue
        points = contour[:, 0, :]
        cx, cy, radius, residual = fit_circle(points)
        candidates.append({
            "area_px2": float(area), "points": points, "center_x_px": cx, "center_y_px": cy,
            "radius_px": radius, "residual": residual,
            "radial_rms_px": float(np.sqrt(np.mean(residual ** 2))),
        })
    return candidates


def select_raw_circle(path: Path) -> dict[str, object] | None:
    candidates = []
    for item in contour_candidates(path):
        cx, cy = float(item["center_x_px"]), float(item["center_y_px"])
        radius, rms = float(item["radius_px"]), float(item["radial_rms_px"])
        area = float(item["area_px2"])
        fully_visible = cx - radius >= 10 and cy - radius >= 10 and cx + radius < 2038 and cy + radius < 2038
        if fully_visible and 340 <= radius <= 460 and rms <= 25:
            item["selection_score"] = rms + abs(area - 493000.0) / 100000.0
            candidates.append(item)
    return min(candidates, key=lambda item: float(item["selection_score"])) if candidates else None


def select_matching_circle(path: Path, raw_circle: dict[str, object]) -> dict[str, object]:
    raw_x, raw_y = float(raw_circle["center_x_px"]), float(raw_circle["center_y_px"])
    raw_radius = float(raw_circle["radius_px"])
    candidates = []
    for item in contour_candidates(path):
        center_error = np.hypot(float(item["center_x_px"]) - raw_x, float(item["center_y_px"]) - raw_y)
        radius_error = abs(float(item["radius_px"]) - raw_radius)
        if center_error <= 30 and radius_error <= 40:
            item["selection_score"] = center_error + radius_error + float(item["radial_rms_px"])
            candidates.append(item)
    if not candidates:
        raise RuntimeError(f"Matching V42 circle not found: {path.name}")
    return min(candidates, key=lambda item: float(item["selection_score"]))


def result_row(path: Path, item: dict[str, object], case: str) -> dict[str, float | str]:
    residual = np.asarray(item["residual"], dtype=np.float64)
    points = np.asarray(item["points"])
    return {
        "file": path.name,
        "case": case,
        "center_x_px": float(item["center_x_px"]),
        "center_y_px": float(item["center_y_px"]),
        "radius_px": float(item["radius_px"]),
        "radial_rms_px": float(item["radial_rms_px"]),
        "roundness_p95_p05_px": float(np.percentile(residual, 95) - np.percentile(residual, 5)),
        "contour_points": len(points),
    }


def main() -> None:
    TABLE.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    rows, exclusions = [], []
    raw_files = sorted(CASES["raw"].glob("*.bmp"))
    v42_names = {p.name for p in CASES["v42_e120"].glob("*.bmp")}
    if [p.name for p in raw_files] != sorted(v42_names):
        raise RuntimeError("Raw and V42 frame orders differ")
    for raw_path in raw_files:
        raw_circle = select_raw_circle(raw_path)
        if raw_circle is None:
            exclusions.append({"file": raw_path.name, "reason": "central circle clipped or not fully visible in fixed crop"})
            continue
        v42_path = CASES["v42_e120"] / raw_path.name
        v42_circle = select_matching_circle(v42_path, raw_circle)
        rows.append(result_row(raw_path, raw_circle, "raw"))
        rows.append(result_row(v42_path, v42_circle, "v42_e120"))
    df = pd.DataFrame(rows)
    df.to_csv(TABLE / "circle_round1_per_frame.csv", index=False, encoding="utf-8-sig", float_format="%.7f")
    pd.DataFrame(exclusions).to_csv(TABLE / "circle_round1_excluded_frames.csv", index=False, encoding="utf-8-sig")
    summary_rows = []
    for case, group in df.groupby("case", sort=False):
        summary_rows.append({
            "case": case,
            "n_frames": len(group),
            "mean_radius_px": group.radius_px.mean(),
            "radius_std_px": group.radius_px.std(ddof=1),
            "center_x_std_px": group.center_x_px.std(ddof=1),
            "center_y_std_px": group.center_y_px.std(ddof=1),
            "mean_radial_rms_px": group.radial_rms_px.mean(),
            "median_radial_rms_px": group.radial_rms_px.median(),
            "mean_roundness_p95_p05_px": group.roundness_p95_p05_px.mean(),
        })
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(TABLE / "circle_round1_summary.csv", index=False, encoding="utf-8-sig", float_format="%.7f")
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.5), dpi=170, sharex=True)
    labels = {"raw": "Raw", "v42_e120": "V42 epoch 120"}
    for case, group in df.groupby("case", sort=False):
        x = np.arange(1, len(group) + 1)
        axes[0].plot(x, group.radius_px, marker="o", markersize=2.5, linewidth=1.0, label=labels[case])
        axes[1].plot(x, group.radial_rms_px, marker="o", markersize=2.5, linewidth=1.0, label=labels[case])
    axes[0].set_ylabel("Fitted radius (px)")
    axes[1].set_ylabel("Radial RMS residual (px)")
    axes[1].set_xlabel("Capture index")
    axes[0].set_title("Unseen concentric-circle repeatability")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "circle_round1_radius_and_roundness.png", bbox_inches="tight")
    plt.close(fig)
    report = [
        "# Circle Round1 Geometry Repeatability",
        "",
        "The first 50 filename-sorted captures were cropped at fixed coordinates without resizing. Frames where Raw does not contain a complete central circle are excluded by geometry visibility only; Raw and V42 then use the same filenames.",
        f"Valid complete-circle frames: {df['file'].nunique()} / 50.",
        "This dataset has no per-frame traceable diameter truth, so the result supports repeatability and roundness only, not absolute CD accuracy.",
        "",
        summary.to_markdown(index=False, floatfmt=".5f"),
    ]
    (ROOT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
