# GeoEdgeAlignSR_v1_TTAvsBaselineComparison.py
# Compares TTA inference results against R26 baseline GMF scores.
# Usage: python GeoEdgeAlignSR_v1_TTAvsBaselineComparison.py [--tta-mode cross5]

import json
import math
import os
import sys
import argparse

# --- R26 baseline GMF results (already scored) ---
BASELINE_SPECS = {
    "r26_sm035_baseline": {
        "root": r"D:\GMM_2_Final\Traing_Progress\organized_20260316\external_compare_r18_r22_r25_r26\r26_sm035\gmf_results\raw",
        "pitch_map": {
            "8px":    "pitch8px",
            "0p8px":  "pitch0p8px",
            "0p08px": "pitch0p08px",
        },
    },
}

PITCH_KEYS = ["8px", "0p8px", "0p08px"]
PITCH_LABELS = {
    "8px":    "8px (pitch1um)",
    "0p8px":  "0.8px (pitch0p1um)",
    "0p08px": "0.08px (pitch0p01um)",
}
OUTLIER_FILTER_PITCH = "0p8px"
MAIN_PITCH = "0p8px"


def mean(values):
    if not values:
        return None
    return sum(values) / float(len(values))


def stddev(values):
    if not values:
        return None
    avg = mean(values)
    accum = sum((v - avg) ** 2 for v in values)
    return math.sqrt(accum / float(len(values)))


def linear_detrend(values):
    n = len(values)
    if n < 2:
        return list(values)
    xs = list(range(n))
    mx = mean(xs)
    my = mean(values)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, values))
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return [v - my for v in values]
    slope = num / den
    intercept = my - slope * mx
    return [v - (slope * x + intercept) for x, v in zip(xs, values)]


def pearson_correlation(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = mean(xs)
    mean_y = mean(ys)
    num = den_x = den_y = 0.0
    for x, y in zip(xs, ys):
        dx = x - mean_x
        dy = y - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy
    if den_x <= 0.0 or den_y <= 0.0:
        return None
    return num / math.sqrt(den_x * den_y)


def compute_lag1_autocorr(posy_values):
    residuals = linear_detrend(posy_values)
    if len(residuals) < 3:
        return None
    return pearson_correlation(residuals[:-1], residuals[1:])


def parse_gmf_score(path):
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            tokens = [t.strip() for t in line.split(",")]
            if len(tokens) < 2:
                continue
            record = {}
            for i in range(len(tokens) // 2):
                key = tokens[i * 2].strip()
                value = tokens[i * 2 + 1].strip()
                if key:
                    record[key] = value
            filename = record.get("FileName")
            pos_y_text = record.get("PosY")
            if not filename or pos_y_text is None:
                continue
            try:
                data[filename] = float(pos_y_text)
            except ValueError:
                pass
    return [data[k] for k in sorted(data.keys())]


def compute_step_std(posy_values, outlier_filter=False):
    steps = [posy_values[i + 1] - posy_values[i] for i in range(len(posy_values) - 1)]
    if not steps:
        return None, None, 0
    if outlier_filter:
        avg = mean(steps)
        sd = stddev(steps)
        if sd and sd > 0:
            filtered = [s for s in steps if abs(s - avg) <= 3 * sd]
        else:
            filtered = steps
        removed = len(steps) - len(filtered)
        raw_std = stddev(steps)
        filt_std = stddev(filtered)
        return raw_std, filt_std, removed
    raw_std = stddev(steps)
    return raw_std, raw_std, 0


def load_model_data(spec, pitch_key):
    pitch_dir = spec["pitch_map"][pitch_key]
    gmf_path = os.path.join(spec["root"], pitch_dir, "GMF_score.txt")
    if not os.path.exists(gmf_path):
        raise FileNotFoundError(f"GMF_score.txt not found: {gmf_path}")
    return parse_gmf_score(gmf_path)


def main():
    parser = argparse.ArgumentParser(description="TTA vs R26 Baseline GMF Comparison")
    parser.add_argument("--tta-mode", default="cross5", help="TTA mode used (for labeling)")
    parser.add_argument("--tta-gmf-root", default=None, help="Root of TTA GMF results (default: auto from tta-mode)")
    args = parser.parse_args()

    tta_mode = args.tta_mode
    if args.tta_gmf_root:
        tta_gmf_root = args.tta_gmf_root
    else:
        tta_gmf_root = rf"D:\GMM_2_Final\Traing_Progress\organized_20260316\tta_experiment\r26_tta_{tta_mode}\gmf_results\raw"

    tta_spec = {
        "root": tta_gmf_root,
        "pitch_map": {
            "8px":    "pitch8px",
            "0p8px":  "pitch0p8px",
            "0p08px": "pitch0p08px",
        },
    }

    report_dir = rf"D:\GMM_2_Final\Traing_Progress\organized_20260316\tta_experiment\r26_tta_{tta_mode}\reports"
    os.makedirs(report_dir, exist_ok=True)

    all_specs = {
        "r26_baseline": BASELINE_SPECS["r26_sm035_baseline"],
        f"r26_tta_{tta_mode}": tta_spec,
    }
    model_names = list(all_specs.keys())

    results = {}
    for model_name, spec in all_specs.items():
        results[model_name] = {}
        for pitch_key in PITCH_KEYS:
            try:
                posy = load_model_data(spec, pitch_key)
                outlier = pitch_key == OUTLIER_FILTER_PITCH
                raw_std, filt_std, removed = compute_step_std(posy, outlier_filter=outlier)
                autocorr = compute_lag1_autocorr(posy)
                results[model_name][pitch_key] = {
                    "raw_step_std": raw_std,
                    "filtered_step_std": filt_std,
                    "outliers_removed": removed,
                    "lag1_autocorr": autocorr,
                    "n_frames": len(posy),
                }
                print(f"[OK] {model_name} / {pitch_key}: step_std={filt_std:.6f}, autocorr={autocorr:.6f}" if autocorr else f"[OK] {model_name} / {pitch_key}: step_std={filt_std:.6f}")
            except FileNotFoundError as e:
                print(f"[SKIP] {model_name} / {pitch_key}: {e}")
                results[model_name][pitch_key] = {
                    "raw_step_std": None,
                    "filtered_step_std": None,
                    "outliers_removed": 0,
                    "lag1_autocorr": None,
                    "n_frames": 0,
                }

    tta_name = f"r26_tta_{tta_mode}"
    baseline_name = "r26_baseline"

    lines = [
        f"# TTA Experiment: R26 Baseline vs R26 + TTA ({tta_mode})",
        "",
        "## Step Std Comparison",
        "| Scale | R26 Baseline | R26 + TTA | Delta | Improvement % |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for pitch_key in PITCH_KEYS:
        label = PITCH_LABELS[pitch_key]
        base_v = results[baseline_name][pitch_key]["filtered_step_std"]
        tta_v = results[tta_name][pitch_key]["filtered_step_std"]
        if base_v is not None and tta_v is not None:
            delta = tta_v - base_v
            pct = (base_v - tta_v) / base_v * 100 if base_v > 0 else 0
            lines.append(f"| {label} | {base_v:.6f} | {tta_v:.6f} | {delta:+.6f} | {pct:+.1f}% |")
        else:
            lines.append(f"| {label} | {'N/A' if base_v is None else f'{base_v:.6f}'} | {'N/A' if tta_v is None else f'{tta_v:.6f}'} | N/A | N/A |")

    lines += [
        "",
        "## Lag-1 Autocorrelation",
        "| Scale | R26 Baseline | R26 + TTA | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for pitch_key in PITCH_KEYS:
        label = PITCH_LABELS[pitch_key]
        base_v = results[baseline_name][pitch_key]["lag1_autocorr"]
        tta_v = results[tta_name][pitch_key]["lag1_autocorr"]
        if base_v is not None and tta_v is not None:
            delta = tta_v - base_v
            lines.append(f"| {label} | {base_v:.6f} | {tta_v:.6f} | {delta:+.6f} |")
        else:
            lines.append(f"| {label} | {'N/A' if base_v is None else f'{base_v:.6f}'} | {'N/A' if tta_v is None else f'{tta_v:.6f}'} | N/A |")

    # Verdict
    main_base = results[baseline_name][MAIN_PITCH]["filtered_step_std"]
    main_tta = results[tta_name][MAIN_PITCH]["filtered_step_std"]
    main_autocorr_base = results[baseline_name][MAIN_PITCH]["lag1_autocorr"]
    main_autocorr_tta = results[tta_name][MAIN_PITCH]["lag1_autocorr"]

    lines += ["", "## Verdict"]
    if main_base is not None and main_tta is not None:
        improvement = (main_base - main_tta) / main_base * 100
        tta_wins = main_tta < main_base
        lines.append(f"- Main battlefield (0.8px): baseline={main_base:.6f}, TTA={main_tta:.6f}")
        lines.append(f"- Improvement: {improvement:+.1f}%")
        lines.append(f"- TTA {'outperforms' if tta_wins else 'does NOT outperform'} baseline")
        if main_autocorr_tta is not None:
            lines.append(f"- TTA lag-1 autocorr: {main_autocorr_tta:.6f} (threshold > 0.1)")
            if main_autocorr_tta > 0.1:
                lines.append("- Autocorrelation check: PASS")
            else:
                lines.append("- Autocorrelation check: FAIL (too low)")
        lines.append("")
        if tta_wins and improvement > 3:
            lines.append("### Conclusion: TTA is effective")
            lines.append("This confirms the equivariance-sharpness conflict hypothesis.")
            lines.append("Proceed with B1 (direction-oriented equivariance loss) as the highest-priority architecture change.")
        elif tta_wins:
            lines.append("### Conclusion: TTA shows marginal improvement")
            lines.append("The equivariance-sharpness conflict exists but is not the dominant factor.")
            lines.append("Consider combining TTA with other Tier 2 changes.")
        else:
            lines.append("### Conclusion: TTA is NOT effective")
            lines.append("The equivariance-sharpness conflict hypothesis may be incorrect.")
            lines.append("Re-examine the root cause analysis before proceeding with B1.")
    else:
        lines.append("- Insufficient data for verdict. Check GMF scoring output.")

    lines += [
        "",
        "## Outlier Summary (0.8px)",
        "| Model | Removed | Raw step_std | Filtered step_std |",
        "| --- | ---: | ---: | ---: |",
    ]
    for mn in model_names:
        d = results[mn][MAIN_PITCH]
        if d["raw_step_std"] is not None:
            lines.append(f"| {mn} | {d['outliers_removed']} | {d['raw_step_std']:.6f} | {d['filtered_step_std']:.6f} |")
        else:
            lines.append(f"| {mn} | N/A | N/A | N/A |")

    md_text = "\n".join(lines)
    md_path = os.path.join(report_dir, f"TTA_VS_BASELINE_{tta_mode.upper()}_COMPARISON.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"\n[REPORT] {md_path}")

    json_data = {
        "experiment": f"TTA_{tta_mode}",
        "baseline": "r26_sm035",
        "results": results,
    }
    json_path = os.path.join(report_dir, f"TTA_VS_BASELINE_{tta_mode.upper()}_COMPARISON.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"[JSON]   {json_path}")

    print(f"\n{'='*60}")
    if main_base is not None and main_tta is not None:
        improvement = (main_base - main_tta) / main_base * 100
        print(f"0.8px step_std: {main_base:.6f} (baseline) -> {main_tta:.6f} (TTA {tta_mode})")
        print(f"Improvement: {improvement:+.1f}%")
    else:
        print("Comparison incomplete - check GMF scoring.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
