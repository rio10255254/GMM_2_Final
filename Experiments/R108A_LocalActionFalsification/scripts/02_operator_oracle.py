"""Falsify or support a constrained local optical action library.

The experiment evaluates identity, denoising, symmetric sharpening,
fixed-center profile remapping, illumination correction and explicit optical
inverse candidates on the 200 R73/R74 truth-backed images.  It measures image,
edge-profile, transition-center, transition-width and overshoot behavior.  No
candidate is learned and no old checkpoint is loaded.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion, distance_transform_edt
from skimage.restoration import wiener


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results" / "operator_oracle"
REPORT = ROOT / "reports" / "02_OPERATOR_ORACLE.md"
RESULT.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
EXPERIMENTS = Path(r"D:\GMM_2_Final\Experiments")
MANIFESTS = {
    "R73": EXPERIMENTS / "R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/manifest.json",
    "R74": EXPERIMENTS / "R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/manifest.json",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_gray(path: str | Path) -> np.ndarray:
    p = Path(path)
    image = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(p)
    return image.astype(np.float32) / 255.0


def gaussian_psf(sigma: float) -> np.ndarray:
    radius = max(3, int(math.ceil(3.0 * sigma)))
    axis = np.arange(-radius, radius + 1, dtype=np.float32)
    row = np.exp(-0.5 * (axis / sigma) ** 2)
    row /= row.sum()
    kernel = np.outer(row, row)
    return (kernel / kernel.sum()).astype(np.float32)


def remap(image: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    return cv2.remap(image, map_x.astype(np.float32), map_y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def local_evidence(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    magnitude = np.sqrt(gx * gx + gy * gy + 1e-8)
    centered = image - cv2.GaussianBlur(image, (0, 0), 3.4, borderType=cv2.BORDER_REFLECT_101)
    local_scale = np.sqrt(cv2.GaussianBlur(centered * centered, (0, 0), 3.4, borderType=cv2.BORDER_REFLECT_101) + (2.0 / 255.0) ** 2)
    relative = np.clip(magnitude / (local_scale + 2.0 / 255.0), 0.0, 4.0)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 1.8, borderType=cv2.BORDER_REFLECT_101)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), 1.8, borderType=cv2.BORDER_REFLECT_101)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), 1.8, borderType=cv2.BORDER_REFLECT_101)
    coherence = np.sqrt((jxx - jyy) ** 2 + 4.0 * jxy * jxy + 1e-10) / (jxx + jyy + 1e-6)
    evidence = np.clip((relative - 0.28) / 1.25, 0.0, 1.0) * np.clip(coherence, 0.0, 1.0)
    nx = gx / np.maximum(magnitude, 1e-5)
    ny = gy / np.maximum(magnitude, 1e-5)
    return evidence.astype(np.float32), nx.astype(np.float32), ny.astype(np.float32), local_scale.astype(np.float32)


def fixed_center_edge(image: np.ndarray, scale: float, distance: float, strength: float = 1.0) -> np.ndarray:
    evidence, nx, ny, _ = local_evidence(image)
    h, w = image.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    minus = remap(image, xx - nx * distance, yy - ny * distance)
    plus = remap(image, xx + nx * distance, yy + ny * distance)
    lower = np.minimum(minus, plus)
    upper = np.maximum(minus, plus)
    contrast = np.maximum(upper - lower, 1.0 / 255.0)
    probability = np.clip((image - lower) / contrast, 1e-4, 1.0 - 1e-4)
    logits = np.log(probability) - np.log1p(-probability)
    sharpened = 1.0 / (1.0 + np.exp(-np.clip(logits / scale, -30, 30)))
    rendered = lower + contrast * sharpened
    contrast_support = np.clip((contrast - 4.0 / 255.0) / (20.0 / 255.0), 0.0, 1.0)
    gate = np.clip(strength * evidence * contrast_support, 0.0, 1.0)
    return np.clip(image + gate * (rendered - image), 0.0, 1.0).astype(np.float32)


def unsharp(image: np.ndarray, sigma: float, amount: float) -> np.ndarray:
    blur = cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    return np.clip(image + amount * (image - blur), 0.0, 1.0).astype(np.float32)


def local_illumination(image: np.ndarray, sigma: float, amount: float) -> np.ndarray:
    field = cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    anchor = float(np.median(field))
    return np.clip(image - amount * (field - anchor), 0.0, 1.0).astype(np.float32)


def gaussian_denoise(image: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101).astype(np.float32)


def wiener_action(image: np.ndarray, sigma: float, balance: float) -> np.ndarray:
    value = wiener(image.astype(np.float64), gaussian_psf(sigma).astype(np.float64), balance=balance, clip=False)
    return np.clip(value, 0.0, 1.0).astype(np.float32)


@dataclass
class Action:
    name: str
    family: str
    fn: Callable[[np.ndarray], np.ndarray]


def actions() -> list[Action]:
    rows = [Action("Raw", "identity", lambda x: x.copy())]
    for sigma in (0.55, 0.90):
        rows.append(Action(f"denoise_s{sigma:.2f}", "denoise", lambda x, s=sigma: gaussian_denoise(x, s)))
    for sigma in (0.8, 1.2, 2.0):
        for amount in (0.25, 0.50, 0.80):
            rows.append(Action(f"unsharp_s{sigma:.1f}_a{amount:.2f}", "symmetric_unsharp", lambda x, s=sigma, a=amount: unsharp(x, s, a)))
    for scale in (0.45, 0.60, 0.75):
        for distance in (2.0, 4.0, 6.0):
            rows.append(Action(f"fixededge_w{scale:.2f}_d{int(distance)}", "fixed_center_edge", lambda x, s=scale, d=distance: fixed_center_edge(x, s, d, 1.0)))
    for sigma, amount in ((16.0, 0.25), (16.0, 0.50), (32.0, 0.25), (32.0, 0.50)):
        rows.append(Action(f"illum_s{int(sigma)}_a{amount:.2f}", "illumination", lambda x, s=sigma, a=amount: local_illumination(x, s, a)))
    rows.extend([
        Action("illum16a25_fixededge_w60_d4", "combined", lambda x: fixed_center_edge(local_illumination(x, 16.0, 0.25), 0.60, 4.0)),
        Action("denoise55_fixededge_w60_d4", "combined", lambda x: fixed_center_edge(gaussian_denoise(x, 0.55), 0.60, 4.0)),
    ])
    for sigma in (1.0, 1.6, 2.2):
        for balance in (0.01, 0.03):
            rows.append(Action(f"wiener_s{sigma:.1f}_b{balance:.2f}", "wiener", lambda x, s=sigma, b=balance: wiener_action(x, s, b)))
    return rows


class ProfileSampler:
    def __init__(self, mask: np.ndarray, label: np.ndarray, maximum_points: int = 1600):
        binary = mask >= 0.5
        boundary = binary & ~binary_erosion(binary)
        ys, xs = np.nonzero(boundary)
        if len(xs) == 0:
            raise RuntimeError("Mask has no boundary")
        if len(xs) > maximum_points:
            selection = np.linspace(0, len(xs) - 1, maximum_points).round().astype(int)
            ys, xs = ys[selection], xs[selection]
        sdf = distance_transform_edt(binary).astype(np.float32) - distance_transform_edt(~binary).astype(np.float32)
        gx = cv2.Sobel(sdf, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(sdf, cv2.CV_32F, 0, 1, ksize=3)
        norm = np.sqrt(gx * gx + gy * gy + 1e-8)
        nx = gx[ys, xs] / norm[ys, xs]
        ny = gy[ys, xs] / norm[ys, xs]
        self.distances = np.arange(-8.0, 8.01, 0.5, dtype=np.float32)
        self.map_x = xs[:, None].astype(np.float32) + nx[:, None] * self.distances[None]
        self.map_y = ys[:, None].astype(np.float32) + ny[:, None] * self.distances[None]
        self.label_profiles = self._profiles(label)
        self.label_center, self.label_width, self.label_valid = self._center_width(self.label_profiles)
        self.edge_band = cv2.dilate(boundary.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0

    def _profiles(self, image: np.ndarray) -> np.ndarray:
        return remap(image, self.map_x, self.map_y)

    def _normalize(self, profiles: np.ndarray) -> np.ndarray:
        outside = np.median(profiles[:, :7], axis=1, keepdims=True)
        inside = np.median(profiles[:, -7:], axis=1, keepdims=True)
        signed = inside - outside
        good = np.abs(signed) >= 3.0 / 255.0
        signed = np.where(good, signed, np.sign(signed + 1e-12) * 3.0 / 255.0)
        return (profiles - outside) / signed

    def _center_width(self, profiles: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        p = self._normalize(profiles)
        derivative = np.maximum(np.diff(p, axis=1), 0.0)
        mass = derivative.sum(axis=1)
        valid = mass > 0.20
        cumulative = np.cumsum(derivative, axis=1) / np.maximum(mass[:, None], 1e-8)
        midpoints = 0.5 * (self.distances[:-1] + self.distances[1:])
        positions = []
        for level in (0.10, 0.50, 0.90):
            index = np.argmax(cumulative >= level, axis=1)
            positions.append(midpoints[index])
        return positions[1], positions[2] - positions[0], valid

    def metrics(self, image: np.ndarray, label: np.ndarray, raw: np.ndarray) -> dict[str, float]:
        profiles = self._profiles(image)
        center, width, valid = self._center_width(profiles)
        valid = valid & self.label_valid
        normalized = self._normalize(profiles)
        target_normalized = self._normalize(self.label_profiles)
        if not np.any(valid):
            center_error = width_error = profile_mae = float("inf")
            center_bias = float("nan")
        else:
            center_delta = center[valid] - self.label_center[valid]
            center_error = float(np.median(np.abs(center_delta)))
            center_bias = float(np.median(center_delta))
            width_error = float(np.median(np.abs(width[valid] - self.label_width[valid])))
            profile_mae = float(np.median(np.mean(np.abs(normalized[valid] - target_normalized[valid]), axis=1)))
        lower = np.minimum(raw, label) - 2.0 / 255.0
        upper = np.maximum(raw, label) + 2.0 / 255.0
        overshoot = np.maximum(lower - image, 0.0) + np.maximum(image - upper, 0.0)
        return {
            "full_mae_gray": float(np.mean(np.abs(image - label)) * 255.0),
            "edge_band_mae_gray": float(np.mean(np.abs(image[self.edge_band] - label[self.edge_band])) * 255.0),
            "profile_mae": profile_mae,
            "center_abs_error_px": center_error,
            "center_signed_bias_px": center_bias,
            "width_abs_error_px": width_error,
            "overshoot_mean_gray": float(overshoot.mean() * 255.0),
            "overshoot_fraction": float((overshoot > 0).mean()),
            "output_change_gray": float(np.mean(np.abs(image - raw)) * 255.0),
            "valid_profile_fraction": float(np.mean(valid)),
        }


def load_records() -> tuple[pd.DataFrame, dict[str, str]]:
    frames = []
    hashes = {}
    for suite, path in MANIFESTS.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        frame = pd.DataFrame(payload["records"])
        frame["suite"] = suite
        frames.append(frame)
        hashes[str(path)] = sha256(path)
    result = pd.concat(frames, ignore_index=True)
    if len(result) != 200 or result["image_id"].nunique() != 100:
        # image_id repeats family vocabulary across suites; suite/image_id is unique.
        if (result["suite"] + "/" + result["image_id"]).nunique() != 200:
            raise RuntimeError("Unexpected manifest population")
    return result, hashes


def normalized_chebyshev(group: pd.DataFrame, axes: list[str]) -> pd.Series:
    normalized = []
    for axis in axes:
        values = group[axis].to_numpy(float)
        low = float(np.nanmin(values))
        high = float(np.nanquantile(values, 0.90))
        scale = max(high - low, 1e-8)
        normalized.append(np.clip((values - low) / scale, 0.0, 5.0))
    return pd.Series(np.max(np.stack(normalized, axis=1), axis=1), index=group.index)


def evaluate() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, Callable[[np.ndarray], np.ndarray]]]:
    records, hashes = load_records()
    bank = actions()
    action_map = {action.name: action.fn for action in bank}
    rows = []
    for record_index, record in records.iterrows():
        source = read_gray(record["src"])
        label = read_gray(record["lbl"])
        mask = read_gray(record["mask"])
        sampler = ProfileSampler(mask, label)
        for action in bank:
            output = action.fn(source)
            if output.shape != source.shape or not np.isfinite(output).all():
                raise RuntimeError(f"Invalid output {action.name} {record['suite']}/{record['image_id']}")
            metrics = sampler.metrics(output, label, source)
            rows.append({
                "suite": record["suite"],
                "image_id": record["image_id"],
                "family": record["family"],
                "source": record["src"],
                "label": record["lbl"],
                "mask": record["mask"],
                "action": action.name,
                "action_family": action.family,
                **metrics,
            })
        if (record_index + 1) % 5 == 0:
            print(json.dumps({"stage": "operator_metrics", "done": record_index + 1, "total": len(records)}), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(RESULT / "per_image_action_metrics.csv", index=False, encoding="utf-8-sig")

    axes = ["edge_band_mae_gray", "profile_mae", "center_abs_error_px", "width_abs_error_px", "overshoot_mean_gray"]
    selected_rows = []
    for (suite, image_id), group in frame.groupby(["suite", "image_id"], sort=False):
        group = group.copy()
        group["chebyshev"] = normalized_chebyshev(group, axes)
        selected = group.loc[group["chebyshev"].idxmin()].copy()
        raw = group[group["action"] == "Raw"].iloc[0]
        selected_rows.append({
            "suite": suite,
            "image_id": image_id,
            "family": selected["family"],
            "source": selected["source"],
            "label": selected["label"],
            "selected_action": selected["action"],
            "selected_family": selected["action_family"],
            "selected_chebyshev": float(selected["chebyshev"]),
            **{f"selected_{axis}": float(selected[axis]) for axis in axes},
            **{f"raw_{axis}": float(raw[axis]) for axis in axes},
            "selected_full_mae_gray": float(selected["full_mae_gray"]),
            "raw_full_mae_gray": float(raw["full_mae_gray"]),
            "selected_output_change_gray": float(selected["output_change_gray"]),
            "joint_edge_center_width_improvement": bool(
                selected["edge_band_mae_gray"] < raw["edge_band_mae_gray"]
                and selected["center_abs_error_px"] <= raw["center_abs_error_px"]
                and selected["width_abs_error_px"] < raw["width_abs_error_px"]
            ),
        })
    selected = pd.DataFrame(selected_rows)
    selected.to_csv(RESULT / "per_image_selected_actions.csv", index=False, encoding="utf-8-sig")

    global_summary = []
    for (suite, action), group in frame.groupby(["suite", "action"]):
        global_summary.append({
            "suite": suite,
            "action": action,
            "action_family": group["action_family"].iloc[0],
            **{f"median_{axis}": float(group[axis].median()) for axis in axes},
            "median_full_mae_gray": float(group["full_mae_gray"].median()),
            "p90_center_abs_error_px": float(group["center_abs_error_px"].quantile(0.9)),
        })
    global_frame = pd.DataFrame(global_summary)
    global_frame.to_csv(RESULT / "global_action_summary.csv", index=False, encoding="utf-8-sig")

    summary: dict[str, object] = {
        "status": "complete",
        "images": int(len(selected)),
        "actions": int(len(bank)),
        "action_families": sorted({action.family for action in bank}),
        "manifest_hashes": hashes,
        "suites": {},
        "selection": {
            "method": "per-image closest-to-ideal by worst normalized regret across edge-band MAE, local profile MAE, center error, width error, and overshoot",
            "truth_used": True,
            "deployment_claim": False,
        },
    }
    for suite, rows_s in selected.groupby("suite"):
        raw_metrics = frame[(frame["suite"] == suite) & (frame["action"] == "Raw")]
        suite_summary = {
            "images": int(len(rows_s)),
            "selected_nonidentity_fraction": float((rows_s["selected_action"] != "Raw").mean()),
            "joint_edge_center_width_improvement_fraction": float(rows_s["joint_edge_center_width_improvement"].mean()),
            "selected_action_counts": {str(k): int(v) for k, v in rows_s["selected_action"].value_counts().to_dict().items()},
            "selected_family_counts": {str(k): int(v) for k, v in rows_s["selected_family"].value_counts().to_dict().items()},
            "axes": {},
            "best_single_actions": {},
        }
        for axis in axes + ["full_mae_gray"]:
            selected_column = f"selected_{axis}"
            raw_column = f"raw_{axis}"
            if selected_column not in rows_s:
                selected_values = frame.set_index(["suite", "image_id", "action"]).loc[
                    [(suite, row.image_id, row.selected_action) for row in rows_s.itertuples()], axis
                ].to_numpy(float)
                raw_values = raw_metrics.set_index("image_id").loc[rows_s["image_id"], axis].to_numpy(float)
            else:
                selected_values = rows_s[selected_column].to_numpy(float)
                raw_values = rows_s[raw_column].to_numpy(float)
            suite_summary["axes"][axis] = {
                "raw_median": float(np.median(raw_values)),
                "selected_median": float(np.median(selected_values)),
                "median_improvement": float(np.median(raw_values - selected_values)),
                "improved_fraction": float(np.mean(selected_values < raw_values - 1e-12)),
            }
            candidates = global_frame[global_frame["suite"] == suite]
            best = candidates.loc[candidates[f"median_{axis}"].idxmin()]
            suite_summary["best_single_actions"][axis] = {"action": str(best["action"]), "median": float(best[f"median_{axis}"])}
        summary["suites"][suite] = suite_summary
    return frame, selected, summary, action_map


def make_visuals(frame: pd.DataFrame, selected: pd.DataFrame, action_map: dict[str, Callable[[np.ndarray], np.ndarray]]) -> None:
    selected = selected.copy()
    selected["edge_gain"] = selected["raw_edge_band_mae_gray"] - selected["selected_edge_band_mae_gray"]
    selected["center_gain"] = selected["raw_center_abs_error_px"] - selected["selected_center_abs_error_px"]
    examples = pd.concat([
        selected[selected["selected_action"] != "Raw"].nlargest(4, "edge_gain"),
        selected[selected["selected_action"] != "Raw"].nlargest(4, "center_gain"),
    ]).drop_duplicates(["suite", "image_id"]).head(8)
    if examples.empty:
        return
    tile = 256
    canvas = np.zeros((len(examples) * tile, 4 * tile), dtype=np.uint8)
    labels = ("Raw", "Selected action", "Truth", "Difference x8")
    for row_index, row in enumerate(examples.itertuples()):
        raw = read_gray(row.source)
        truth = read_gray(row.label)
        output = action_map[row.selected_action](raw)
        diff = np.clip(0.5 + 8.0 * (output - raw), 0.0, 1.0)
        images = (raw, output, truth, diff)
        for column, image in enumerate(images):
            value = cv2.resize(image, (tile, tile), interpolation=cv2.INTER_AREA)
            value = np.round(value * 255).astype(np.uint8)
            canvas[row_index * tile:(row_index + 1) * tile, column * tile:(column + 1) * tile] = value
            text = labels[column] if row_index == 0 else (row.selected_action if column == 1 else "")
            if text:
                cv2.putText(canvas, text[:28], (column * tile + 6, row_index * tile + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, 255, 2, cv2.LINE_AA)
                cv2.putText(canvas, text[:28], (column * tile + 6, row_index * tile + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, 0, 1, cv2.LINE_AA)
    cv2.imencode(".png", canvas)[1].tofile(str(RESULT / "selected_examples.png"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    for ax, suite in zip(axes, ("R73", "R74")):
        rows_s = selected[selected["suite"] == suite]
        counts = rows_s["selected_family"].value_counts()
        ax.bar(counts.index, counts.values, color="#4c8b70")
        ax.set_title(f"{suite}: selected action families")
        ax.set_ylabel("images")
        ax.tick_params(axis="x", rotation=35)
    fig.savefig(RESULT / "selected_action_families.png", dpi=180)
    plt.close(fig)


def write_report(summary: dict[str, object]) -> None:
    lines = [
        "# R108A Constrained Optical Action Oracle",
        "",
        f"Evaluated {summary['actions']} actions on {summary['images']} truth-backed images.",
        "",
    ]
    for suite in ("R73", "R74"):
        item = summary["suites"][suite]
        lines.extend([
            f"## {suite}",
            "",
            f"- Non-identity selected: {100*item['selected_nonidentity_fraction']:.1f}%.",
            f"- Simultaneous edge/center/width improvement: {100*item['joint_edge_center_width_improvement_fraction']:.1f}%.",
            f"- Edge-band median: Raw {item['axes']['edge_band_mae_gray']['raw_median']:.3f} gray, selected {item['axes']['edge_band_mae_gray']['selected_median']:.3f} gray.",
            f"- Transition-center median: Raw {item['axes']['center_abs_error_px']['raw_median']:.3f} px, selected {item['axes']['center_abs_error_px']['selected_median']:.3f} px.",
            f"- Transition-width median: Raw {item['axes']['width_abs_error_px']['raw_median']:.3f} px, selected {item['axes']['width_abs_error_px']['selected_median']:.3f} px.",
            f"- Selected action families: {json.dumps(item['selected_family_counts'], ensure_ascii=False)}.",
            "",
        ])
    lines.extend([
        "## Interpretation",
        "",
        "If the truth-selected action library materially improves edge profile, center and width together on both suites, the local-action mechanism has enough representational headroom for a learned selector.  If gains occur only on R73 or require unstable inverse filters, the proposed bank is not ready for a selector probe.",
        "",
    ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    frame, selected, summary, action_map = evaluate()
    make_visuals(frame, selected, action_map)
    (RESULT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

