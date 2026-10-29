import json
import math
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# R18 / R22h / R25 use old pitch dir naming; R26 / R27 use new naming
MODEL_SPECS = {
    "round18_baseline": {
        "root": str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_round18_round22/round18_baseline/gmf_results/raw'),
        "pitch_map": {
            "8px":    "pitch1um_y_100",
            "0p8px":  "pitch0p1um_y_60",
            "0p08px": "pitch0p01um_y_40",
        },
    },
    "round22_hold": {
        "root": str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_round18_round22/round22_hold/gmf_results/raw'),
        "pitch_map": {
            "8px":    "pitch1um_y_100",
            "0p8px":  "pitch0p1um_y_60",
            "0p08px": "pitch0p01um_y_40",
        },
    },
    "r25_sw010": {
        "root": str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_r18_r22_r25/r25_sw010/gmf_results/raw'),
        "pitch_map": {
            "8px":    "pitch1um_y_100",
            "0p8px":  "pitch0p1um_y_60",
            "0p08px": "pitch0p01um_y_40",
        },
    },
    "r26_sm035": {
        "root": str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_r18_r22_r25_r26/r26_sm035/gmf_results/raw'),
        "pitch_map": {
            "8px":    "pitch8px",
            "0p8px":  "pitch0p8px",
            "0p08px": "pitch0p08px",
        },
    },
    "r27_sm028": {
        "root": str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_r18_r22_r25_r26_r27/r27_sm028/gmf_results/raw'),
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

REPORT_DIR = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_r18_r22_r25_r26_r27/reports')
SUMMARY_MD_PATH = os.path.join(REPORT_DIR, "EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.md")
SUMMARY_JSON_PATH = os.path.join(REPORT_DIR, "EXTERNAL_COMPARE_R18_R22_R25_R26_R27_SUMMARY.json")

STEP_STD_TARGET = 0.1913  # R26 0.8px baseline to beat


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


def parse_gmf_score(path):
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
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


def compute_lag1_autocorr(posy_values):
    residuals = linear_detrend(posy_values)
    if len(residuals) < 3:
        return None
    return pearson_correlation(residuals[:-1], residuals[1:])


def load_model_data(model_name, spec, pitch_key):
    pitch_dir = spec["pitch_map"][pitch_key]
    gmf_path = os.path.join(spec["root"], pitch_dir, "GMF_score.txt")
    if not os.path.exists(gmf_path):
        raise FileNotFoundError(f"GMF_score.txt not found: {gmf_path}")
    return parse_gmf_score(gmf_path)


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)

    results = {}
    for model_name, spec in MODEL_SPECS.items():
        results[model_name] = {}
        for pitch_key in PITCH_KEYS:
            posy = load_model_data(model_name, spec, pitch_key)
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
        print(f"[OK] {model_name}")

    model_names = list(MODEL_SPECS.keys())
    r27 = results["r27_sm028"][MAIN_PITCH]
    r26 = results["r26_sm035"][MAIN_PITCH]
    r27_better = r27["filtered_step_std"] < r26["filtered_step_std"]

    lines = [
        "# External GMF Five-Way Comparison: R18 vs R22h vs R25sw010 vs R26sm035 vs R27sm028",
        "",
        "## Step Std（主要指標）",
        "| 尺度 | " + " | ".join(model_names) + " | vs R26 | vs R18 |",
        "| --- | " + " | ".join(["---:"] * len(model_names)) + " | ---: | ---: |",
    ]
    for pitch_key in PITCH_KEYS:
        label = PITCH_LABELS[pitch_key]
        vals = []
        for mn in model_names:
            v = results[mn][pitch_key]["filtered_step_std"]
            vals.append(f"{v:.6f}" if v is not None else "N/A")
        r27_v = results["r27_sm028"][pitch_key]["filtered_step_std"]
        r26_v = results["r26_sm035"][pitch_key]["filtered_step_std"]
        r18_v = results["round18_baseline"][pitch_key]["filtered_step_std"]
        vs_r26 = f"{r27_v - r26_v:+.6f}" if r27_v is not None and r26_v is not None else "N/A"
        vs_r18 = f"{r27_v - r18_v:+.6f}" if r27_v is not None and r18_v is not None else "N/A"
        lines.append("| " + label + " | " + " | ".join(vals) + f" | {vs_r26} | {vs_r18} |")

    lines += [
        "",
        "## Lag-1 Autocorrelation（anchor 穩定性）",
        "| 尺度 | " + " | ".join(model_names) + " |",
        "| --- | " + " | ".join(["---:"] * len(model_names)) + " |",
    ]
    for pitch_key in PITCH_KEYS:
        label = PITCH_LABELS[pitch_key]
        vals = []
        for mn in model_names:
            v = results[mn][pitch_key]["lag1_autocorr"]
            vals.append(f"{v:.6f}" if v is not None else "N/A")
        lines.append("| " + label + " | " + " | ".join(vals) + " |")

    r27_main = results["r27_sm028"][MAIN_PITCH]["filtered_step_std"]
    r26_main = results["r26_sm035"][MAIN_PITCH]["filtered_step_std"]
    r27_autocorr = results["r27_sm028"][MAIN_PITCH]["lag1_autocorr"]
    lines += [
        "",
        "## 結論",
        f"- 主戰場（0.8px）r27_sm028 step std = {r27_main:.6f}" if r27_main else "- r27_sm028 0.8px data missing",
        f"- r26_sm035 step std = {r26_main:.6f}" if r26_main else "",
        f"- R27 是否優於 R26？ {'是' if r27_better else '否'}",
        f"- anchor lag-1 autocorr（R27）= {r27_autocorr:.6f}" if r27_autocorr is not None else "- autocorr N/A",
        f"- 建議：{'升級 R27 sm028 為新 baseline' if r27_better else '維持 R26 sm035'}",
    ]

    lines += [
        "",
        "## Outlier Summary（0.8px）",
        "| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |",
        "| --- | ---: | ---: | ---: |",
    ]
    for mn in model_names:
        d = results[mn][MAIN_PITCH]
        lines.append(f"| {mn} | {d['outliers_removed']} | {d['raw_step_std']:.6f} | {d['filtered_step_std']:.6f} |")

    lines += [
        "",
        "## 方法註記",
        "- `PosY` 直接由 `GMF_score.txt` 解析。",
        "- `0.8px` 的 outlier 規則為 `|step - mean(step)| > 3 * std(step)`。",
        "- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 anchor residual 計算。",
        "- R18/R22h/R25 使用舊 pitch 目錄命名（`pitch0p1um_y_60` 等）；R26/R27 使用新命名（`pitch0p8px` 等）。",
    ]

    md_content = "\n".join(lines)
    with open(SUMMARY_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)

    summary_data = {
        "title": "External GMF Five-Way Comparison: R18 vs R22h vs R25sw010 vs R26sm035 vs R27sm028",
        "method": {
            "posy_source": "GMF_score.txt -> PosY",
            "step_definition": "step[i] = PosY[i+1] - PosY[i]",
            "outlier_rule_for_0p8px": "|step - mean(step)| > 3 * std(step)",
            "anchor_autocorr_definition": "lag-1 Pearson correlation of PosY residual after per-sequence linear detrending",
        },
        "models": model_names,
        "results": results,
        "conclusion": {
            "r27_main_step_std": r27_main,
            "r26_main_step_std": r26_main,
            "r27_better_than_r26": r27_better,
            "r27_autocorr_0p8px": r27_autocorr,
            "recommendation": "upgrade_r27_sm028" if r27_better else "hold_r26_sm035",
        },
    }
    with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    print(f"\n[DONE] Report written to {SUMMARY_MD_PATH}")
    print(md_content)


if __name__ == "__main__":
    main()
