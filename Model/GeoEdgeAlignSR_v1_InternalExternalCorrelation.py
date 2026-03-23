"""
Internal-External Correlation Tracker
======================================
Quantifies the degree to which internal validation metrics (center_err, step_err)
predict external GMF step_std.  Produces:
  1. Markdown report  -> .../analysis/INTERNAL_EXTERNAL_CORRELATION.md
  2. JSON data        -> .../analysis/INTERNAL_EXTERNAL_CORRELATION.json

No GUI / matplotlib dependency -- pure CLI.
"""

import json
import math
import os
import glob
from datetime import datetime

# ────────────────────────────────────────────────────────────
# 0. Paths
# ────────────────────────────────────────────────────────────
BASE_DIR = r"D:\GMM_2_Final\Traing_Progress\organized_20260316"
OUTPUT_DIR = os.path.join(BASE_DIR, "analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MD_PATH   = os.path.join(OUTPUT_DIR, "INTERNAL_EXTERNAL_CORRELATION.md")
JSON_PATH = os.path.join(OUTPUT_DIR, "INTERNAL_EXTERNAL_CORRELATION.json")

# ────────────────────────────────────────────────────────────
# 1. Hard-coded known data  (fallback / ground truth)
# ────────────────────────────────────────────────────────────
HARDCODED = {
    "R25": {
        "winner": "r25_sw010",
        "int_center_err": 0.0938,   # from decision JSON: 0.09381872
        "int_step_err":   0.0953,   # from decision JSON: 0.09529114
        "ext_step_std":   0.211973, # from external compare: 0.21197267
    },
    "R26": {
        "winner": "r26_sm035",
        "int_center_err": 0.0691,
        "int_step_err":   0.0857,
        "ext_step_std":   0.191336,
    },
    "R27": {
        "winner": "r27_sm028",
        "int_center_err": 0.0603,
        "int_step_err":   0.0737,
        "ext_step_std":   0.196257,
    },
    "R28": {
        "winner": "r28_sm030",
        "int_center_err": 0.0825,
        "int_step_err":   0.0684,
        "ext_step_std":   0.228184,
    },
    "R29": {
        "winner": "r29_sm042",
        "int_center_err": 0.0682,
        "int_step_err":   0.0789,
        "ext_step_std":   0.217310,
    },
}

# Map from external comparison model key -> round label for merging
EXTERNAL_MODEL_TO_ROUND = {
    "r25_sw010":  "R25",
    "r26_sm035":  "R26",
    "r27_sm028":  "R27",
    "r28_sm030":  "R28",
    "r29_winner": "R29",
}

# ────────────────────────────────────────────────────────────
# 2. Auto-collect from decision JSONs + external compare JSON
# ────────────────────────────────────────────────────────────

def auto_collect_internal(base_dir):
    """Scan round*/selected/reports/*DECISION*.json for winner internal metrics."""
    collected = {}
    for rnd in range(25, 100):
        rnd_dir = os.path.join(base_dir, f"round{rnd}", "selected", "reports")
        if not os.path.isdir(rnd_dir):
            continue
        dec_files = sorted(glob.glob(os.path.join(rnd_dir, "*DECISION*.json")))
        if not dec_files:
            continue
        # use the latest decision file
        dec_path = dec_files[-1]
        try:
            with open(dec_path, "r", encoding="utf-8") as f:
                dec = json.load(f)
        except Exception:
            continue
        winner = dec.get("winner_candidate", dec.get("selected_candidate", ""))
        rows = dec.get("rows", [])
        # find winner row
        winner_row = None
        for row in rows:
            if row.get("candidate") == winner:
                winner_row = row
                break
        if winner_row is None and rows:
            winner_row = rows[0]
        if winner_row:
            label = f"R{rnd}"
            collected[label] = {
                "winner": winner,
                "int_center_err": winner_row.get("best_center_err"),
                "int_step_err":   winner_row.get("best_step_err"),
                "decision_json":  dec_path,
            }
    return collected


def auto_collect_external(base_dir):
    """Scan external_compare_*/reports/*SUMMARY*.json for 0p8px step_std."""
    collected = {}
    # find all external compare directories
    ext_dirs = sorted(glob.glob(os.path.join(base_dir, "external_compare_*")))
    # prefer the one with the most models (latest / most complete)
    best_json = None
    best_n_models = 0
    for ed in ext_dirs:
        rpt_dir = os.path.join(ed, "reports")
        if not os.path.isdir(rpt_dir):
            continue
        for fn in os.listdir(rpt_dir):
            if "SUMMARY" in fn and fn.endswith(".json"):
                fpath = os.path.join(rpt_dir, fn)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    n = len(data.get("models", []))
                    if n > best_n_models:
                        best_n_models = n
                        best_json = (fpath, data)
                except Exception:
                    pass

    if best_json is None:
        return collected

    fpath, data = best_json
    results = data.get("results", {})
    for model_key, round_label in EXTERNAL_MODEL_TO_ROUND.items():
        if model_key in results:
            px08 = results[model_key].get("0p8px", {})
            # prefer filtered_step_std if outliers were removed, else raw
            step_std = px08.get("filtered_step_std", px08.get("raw_step_std"))
            if step_std is not None:
                collected[round_label] = {
                    "ext_step_std":     step_std,
                    "ext_raw_step_std": px08.get("raw_step_std"),
                    "ext_outliers_removed": px08.get("outliers_removed", 0),
                    "ext_lag1_autocorr":    px08.get("lag1_autocorr"),
                    "source_json":      fpath,
                }
    return collected


def merge_data(hardcoded, auto_int, auto_ext):
    """Merge hardcoded + auto-collected, preferring auto when available."""
    all_rounds = sorted(set(list(hardcoded.keys()) + list(auto_int.keys())))
    merged = {}
    for label in all_rounds:
        rec = {}
        # start with hardcoded
        if label in hardcoded:
            rec.update(hardcoded[label])
            rec["int_source"] = "hardcoded"
            rec["ext_source"] = "hardcoded"
        # overwrite internal from auto
        if label in auto_int:
            ai = auto_int[label]
            if ai.get("int_center_err") is not None:
                rec["int_center_err"] = ai["int_center_err"]
                rec["int_step_err"]   = ai["int_step_err"]
                rec["winner"]         = ai["winner"]
                rec["int_source"]     = "auto:" + ai.get("decision_json", "?")
        # overwrite external from auto
        if label in auto_ext:
            ae = auto_ext[label]
            if ae.get("ext_step_std") is not None:
                rec["ext_step_std"]          = ae["ext_step_std"]
                rec["ext_raw_step_std"]      = ae.get("ext_raw_step_std")
                rec["ext_outliers_removed"]  = ae.get("ext_outliers_removed", 0)
                rec["ext_lag1_autocorr"]     = ae.get("ext_lag1_autocorr")
                rec["ext_source"]            = "auto:" + ae.get("source_json", "?")
        # only keep if we have both internal and external
        if "int_center_err" in rec and "ext_step_std" in rec:
            merged[label] = rec
    return merged


# ────────────────────────────────────────────────────────────
# 3. Statistical helpers  (no scipy dependency)
# ────────────────────────────────────────────────────────────

def mean(xs):
    return sum(xs) / len(xs)


def pearson(xs, ys):
    """Pearson correlation coefficient + two-tailed p-value (t-test approx)."""
    n = len(xs)
    if n < 3:
        return float("nan"), float("nan")
    mx, my = mean(xs), mean(ys)
    sx = math.sqrt(sum((x - mx)**2 for x in xs) / (n - 1))
    sy = math.sqrt(sum((y - my)**2 for y in ys) / (n - 1))
    if sx == 0 or sy == 0:
        return float("nan"), float("nan")
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / ((n - 1) * sx * sy)
    # t-statistic
    if abs(r) >= 1.0:
        return r, 0.0
    t_stat = r * math.sqrt((n - 2) / (1 - r**2))
    # approximate two-tailed p-value via Student-t with n-2 df
    p = _t_pvalue(abs(t_stat), n - 2)
    return r, p


def _t_pvalue(t, df):
    """Rough two-tailed p-value for Student-t using the incomplete beta function approx."""
    # use the relationship:  p = I_{df/(df+t^2)}(df/2, 1/2)
    # For small n this is fine as a quick approximation
    x = df / (df + t * t)
    p = _regularized_incomplete_beta(x, df / 2.0, 0.5)
    return p


def _regularized_incomplete_beta(x, a, b, n_iter=200):
    """Continued-fraction approximation of I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # use Lentz's method for continued fraction
    # I_x(a,b) = x^a (1-x)^b / (a B(a,b)) * CF
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - lbeta) / a

    # CF: 1 + d1/(1+ d2/(1+ ...))  with Lentz
    # Using the standard continued fraction for I_x(a,b)
    # This is a well-known expansion -- here we use a simpler series approach
    # via the identity and a direct summation for moderate precision.
    # For n=5 data points we only need rough p-values.
    # Fallback: use a simple numeric integration (trapezoidal).
    return _beta_inc_quadrature(x, a, b)


def _beta_inc_quadrature(x, a, b, n_steps=2000):
    """Numerical integration of the regularized incomplete beta function."""
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    norm = math.exp(lbeta)
    h = x / n_steps
    total = 0.0
    for i in range(n_steps):
        t0 = i * h
        t1 = (i + 1) * h
        tm = (t0 + t1) / 2.0
        # integrand: t^(a-1) * (1-t)^(b-1) / B(a,b)
        def f(t):
            if t <= 0 or t >= 1:
                return 0.0
            return math.exp((a - 1) * math.log(t) + (b - 1) * math.log(1 - t) - lbeta)
        total += (f(t0) + 4 * f(tm) + f(t1)) * h / 6.0  # Simpson
    return total


def rank_data(xs):
    """Assign average ranks (1-based) to values."""
    n = len(xs)
    indexed = sorted(range(n), key=lambda i: xs[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and xs[indexed[j + 1]] == xs[indexed[j]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Spearman rank correlation + approximate p-value."""
    rx = rank_data(xs)
    ry = rank_data(ys)
    return pearson(rx, ry)


# ────────────────────────────────────────────────────────────
# 4. Composite metric analysis
# ────────────────────────────────────────────────────────────

def compute_composites(merged):
    """Try various composite internal metrics to find best predictor."""
    labels = sorted(merged.keys())
    n = len(labels)
    center = [merged[l]["int_center_err"] for l in labels]
    step   = [merged[l]["int_step_err"]   for l in labels]
    ext    = [merged[l]["ext_step_std"]    for l in labels]

    composites = {}

    # 1. center_err only
    r, p = pearson(center, ext)
    rho, rho_p = spearman(center, ext)
    composites["center_err"] = {
        "values": center,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    # 2. step_err only
    r, p = pearson(step, ext)
    rho, rho_p = spearman(step, ext)
    composites["step_err"] = {
        "values": step,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    # 3. mean(center_err, step_err)
    avg = [(c + s) / 2 for c, s in zip(center, step)]
    r, p = pearson(avg, ext)
    rho, rho_p = spearman(avg, ext)
    composites["mean(center, step)"] = {
        "values": avg,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    # 4. weighted: 0.3*center + 0.7*step
    w1 = [0.3 * c + 0.7 * s for c, s in zip(center, step)]
    r, p = pearson(w1, ext)
    rho, rho_p = spearman(w1, ext)
    composites["0.3*center + 0.7*step"] = {
        "values": w1,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    # 5. weighted: 0.7*center + 0.3*step
    w2 = [0.7 * c + 0.3 * s for c, s in zip(center, step)]
    r, p = pearson(w2, ext)
    rho, rho_p = spearman(w2, ext)
    composites["0.7*center + 0.3*step"] = {
        "values": w2,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    # 6. euclidean distance from origin
    euclid = [math.sqrt(c**2 + s**2) for c, s in zip(center, step)]
    r, p = pearson(euclid, ext)
    rho, rho_p = spearman(euclid, ext)
    composites["sqrt(center^2 + step^2)"] = {
        "values": euclid,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    # 7. max(center_err, step_err)
    mx = [max(c, s) for c, s in zip(center, step)]
    r, p = pearson(mx, ext)
    rho, rho_p = spearman(mx, ext)
    composites["max(center, step)"] = {
        "values": mx,
        "pearson_r": r, "pearson_p": p,
        "spearman_rho": rho, "spearman_p": rho_p,
    }

    return composites


# ────────────────────────────────────────────────────────────
# 5. ASCII scatter helper
# ────────────────────────────────────────────────────────────

def ascii_scatter(xs, ys, labels, x_label, y_label, width=50, height=15):
    """Return a multi-line string with an ASCII scatter plot."""
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    # add margin
    x_range = x_max - x_min or 0.001
    y_range = y_max - y_min or 0.001
    x_min -= x_range * 0.05
    x_max += x_range * 0.05
    y_min -= y_range * 0.05
    y_max += y_range * 0.05
    x_range = x_max - x_min
    y_range = y_max - y_min

    grid = [[' '] * width for _ in range(height)]
    point_map = {}  # (row, col) -> label

    for x, y, lbl in zip(xs, ys, labels):
        col = int((x - x_min) / x_range * (width - 1))
        row = int((y_max - y) / y_range * (height - 1))  # flip y
        col = max(0, min(width - 1, col))
        row = max(0, min(height - 1, row))
        grid[row][col] = '*'
        point_map[(row, col)] = lbl

    lines = []
    lines.append(f"  {y_label}")
    lines.append(f"  {y_max:.4f} |")
    for r in range(height):
        row_str = ''.join(grid[r])
        lines.append(f"           |{row_str}|")
    lines.append(f"  {y_min:.4f} |{'_' * width}|")
    lines.append(f"           {x_min:.4f}{' ' * (width - 20)}{x_max:.4f}")
    lines.append(f"           {x_label}")
    lines.append("")
    lines.append("  Legend:")
    for x, y, lbl in zip(xs, ys, labels):
        lines.append(f"    {lbl}: ({x:.4f}, {y:.6f})")
    return '\n'.join(lines)


# ────────────────────────────────────────────────────────────
# 6. Report generation
# ────────────────────────────────────────────────────────────

def generate_md_report(merged, composites, timestamp):
    labels = sorted(merged.keys())
    center = [merged[l]["int_center_err"] for l in labels]
    step   = [merged[l]["int_step_err"]   for l in labels]
    ext    = [merged[l]["ext_step_std"]    for l in labels]

    lines = []
    lines.append("# Internal-External Correlation Analysis")
    lines.append(f"\nGenerated: {timestamp}")
    lines.append(f"\nData points: {len(labels)} rounds ({', '.join(labels)})")
    lines.append("")

    # ── data table ──
    lines.append("## 1. Raw Data")
    lines.append("")
    lines.append("| Round | Winner | Int center_err | Int step_err | Ext 0.8px step_std | Int Source | Ext Source |")
    lines.append("|-------|--------|---------------|-------------|-------------------|-----------|-----------|")
    for l in labels:
        m = merged[l]
        int_src = "auto" if m.get("int_source", "").startswith("auto") else "hardcoded"
        ext_src = "auto" if m.get("ext_source", "").startswith("auto") else "hardcoded"
        lines.append(
            f"| {l} | {m.get('winner','?')} | {m['int_center_err']:.6f} | "
            f"{m['int_step_err']:.6f} | {m['ext_step_std']:.6f} | "
            f"{int_src} | {ext_src} |"
        )
    lines.append("")

    # ── directional analysis ──
    lines.append("## 2. Round-over-Round Change Direction")
    lines.append("")
    lines.append("Key question: when internal metric improves (decreases), does external metric also improve (decrease)?")
    lines.append("")
    lines.append("| Transition | delta center_err | delta step_err | delta ext_step_std | center agrees? | step agrees? |")
    lines.append("|-----------|-----------------|---------------|-------------------|---------------|-------------|")
    agree_center = 0
    agree_step = 0
    total_transitions = 0
    for i in range(len(labels) - 1):
        l0, l1 = labels[i], labels[i + 1]
        dc = center[i + 1] - center[i]
        ds = step[i + 1] - step[i]
        de = ext[i + 1] - ext[i]
        c_agree = "YES" if (dc > 0 and de > 0) or (dc < 0 and de < 0) or (dc == 0 and de == 0) else "NO"
        s_agree = "YES" if (ds > 0 and de > 0) or (ds < 0 and de < 0) or (ds == 0 and de == 0) else "NO"
        if c_agree == "YES":
            agree_center += 1
        if s_agree == "YES":
            agree_step += 1
        total_transitions += 1
        lines.append(
            f"| {l0}->{l1} | {dc:+.6f} | {ds:+.6f} | {de:+.6f} | "
            f"{c_agree} | {s_agree} |"
        )
    lines.append("")
    lines.append(f"Direction agreement rate: center_err = {agree_center}/{total_transitions} "
                 f"({100*agree_center/max(total_transitions,1):.0f}%), "
                 f"step_err = {agree_step}/{total_transitions} "
                 f"({100*agree_step/max(total_transitions,1):.0f}%)")
    lines.append("")

    # ── correlation coefficients ──
    lines.append("## 3. Correlation Coefficients")
    lines.append("")
    lines.append("| Internal Metric | Pearson r | Pearson p | Spearman rho | Spearman p | Interpretation |")
    lines.append("|----------------|----------|----------|-------------|-----------|---------------|")
    for name in ["center_err", "step_err"]:
        c = composites[name]
        interp = _interpret_correlation(c["pearson_r"], c["pearson_p"], len(labels))
        lines.append(
            f"| {name} | {c['pearson_r']:+.4f} | {c['pearson_p']:.4f} | "
            f"{c['spearman_rho']:+.4f} | {c['spearman_p']:.4f} | {interp} |"
        )
    lines.append("")

    # ── composite metrics ──
    lines.append("## 4. Composite Metric Correlation Search")
    lines.append("")
    lines.append("Testing various combinations of internal metrics to find the best predictor of external GMF step_std.")
    lines.append("")
    lines.append("| Composite Formula | Pearson r | Pearson p | Spearman rho | Spearman p |")
    lines.append("|------------------|----------|----------|-------------|-----------|")
    # sort by absolute pearson_r descending
    sorted_composites = sorted(composites.items(), key=lambda kv: -abs(kv[1]["pearson_r"]))
    for name, c in sorted_composites:
        lines.append(
            f"| {name} | {c['pearson_r']:+.4f} | {c['pearson_p']:.4f} | "
            f"{c['spearman_rho']:+.4f} | {c['spearman_p']:.4f} |"
        )
    lines.append("")

    best_name, best_c = sorted_composites[0]
    lines.append(f"**Best predictor**: `{best_name}` with Pearson r = {best_c['pearson_r']:+.4f}")
    lines.append("")

    # ── scatter plots (ASCII) ──
    lines.append("## 5. Scatter Plots (ASCII)")
    lines.append("")
    lines.append("### center_err vs ext step_std")
    lines.append("```")
    lines.append(ascii_scatter(center, ext, labels, "center_err", "ext_step_std"))
    lines.append("```")
    lines.append("")
    lines.append("### step_err vs ext step_std")
    lines.append("```")
    lines.append(ascii_scatter(step, ext, labels, "step_err", "ext_step_std"))
    lines.append("```")
    lines.append("")

    # ── key observations ──
    lines.append("## 6. Key Observations")
    lines.append("")

    # find worst mismatch
    worst_round = None
    worst_mismatch = 0
    for i in range(len(labels) - 1):
        dc = center[i + 1] - center[i]
        de = ext[i + 1] - ext[i]
        if (dc < 0 and de > 0):  # internal improved but external worsened
            mismatch = abs(dc) + abs(de)
            if mismatch > worst_mismatch:
                worst_mismatch = mismatch
                worst_round = f"{labels[i]}->{labels[i+1]}"

    obs = []
    obs.append(f"- **{len(labels)} rounds** analyzed: {', '.join(labels)}")

    r_center = composites["center_err"]["pearson_r"]
    r_step   = composites["step_err"]["pearson_r"]

    if abs(r_center) < 0.5 and abs(r_step) < 0.5:
        obs.append("- **Both** center_err and step_err show **weak** correlation with external GMF step_std")
        obs.append("- Internal metrics are **NOT reliable proxies** for external GMF performance")
    elif abs(r_center) >= 0.7 or abs(r_step) >= 0.7:
        better = "center_err" if abs(r_center) > abs(r_step) else "step_err"
        obs.append(f"- `{better}` shows **strong** correlation with external GMF (|r| >= 0.7)")
    else:
        obs.append("- Correlation is **moderate** -- internal metrics are weak-to-moderate predictors")

    if worst_round:
        obs.append(f"- **Worst mismatch**: {worst_round} -- internal improved but external worsened")

    # R27 specific note
    if "R27" in merged and "R26" in merged:
        r27_c = merged["R27"]["int_center_err"]
        r26_c = merged["R26"]["int_center_err"]
        r27_e = merged["R27"]["ext_step_std"]
        r26_e = merged["R26"]["ext_step_std"]
        if r27_c < r26_c and r27_e > r26_e:
            obs.append(f"- **R27 paradox confirmed**: center_err improved ({r26_c:.4f} -> {r27_c:.4f}) "
                       f"but ext step_std worsened ({r26_e:.6f} -> {r27_e:.6f})")

    for o in obs:
        lines.append(o)
    lines.append("")

    # ── conclusions ──
    lines.append("## 7. Conclusions & Recommendations")
    lines.append("")

    if abs(r_center) < 0.5 and abs(r_step) < 0.5:
        lines.append("### Verdict: Internal metrics are UNRELIABLE proxies for external GMF")
        lines.append("")
        lines.append("With only weak correlation (|r| < 0.5), optimizing internal center_err or step_err alone ")
        lines.append("does NOT guarantee improvement in external GMF step_std. This confirms the R27 finding.")
        lines.append("")
        lines.append("### Recommendations")
        lines.append("")
        lines.append("1. **Do not rely solely on internal metrics** to judge model quality")
        lines.append("2. **External GMF validation is mandatory** before declaring a round as improved")
        lines.append("3. **Consider a gating rule**: only accept a round if both internal AND external improve")
        lines.append("4. **Investigate non-linear relationships**: the internal-external gap may involve "
                     "factors not captured by simple correlation (e.g., step magnitude distribution shape)")
        lines.append(f"5. **Best composite predictor** found: `{best_name}` (r = {best_c['pearson_r']:+.4f}), "
                     "but still insufficient for reliable prediction")
    else:
        better = "center_err" if abs(r_center) > abs(r_step) else "step_err"
        lines.append(f"### Verdict: `{better}` shows meaningful correlation with external GMF")
        lines.append("")
        lines.append(f"However, with n={len(labels)} the statistical power is limited. "
                     "External validation remains essential.")
        lines.append("")
        lines.append("### Recommendations")
        lines.append("")
        lines.append(f"1. **Use `{better}` as primary internal screening metric**")
        lines.append("2. **Still run external GMF** for final validation")
        lines.append(f"3. **Best composite predictor**: `{best_name}` (r = {best_c['pearson_r']:+.4f})")

    lines.append("")
    lines.append("---")
    lines.append(f"*Analysis by GeoEdgeAlignSR_v1_InternalExternalCorrelation.py, {timestamp}*")
    return '\n'.join(lines)


def _interpret_correlation(r, p, n):
    """Human-readable interpretation of correlation."""
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    direction = "positive" if r > 0 else "negative"
    sig = "significant" if p < 0.05 else "NOT significant"
    if n <= 5:
        sig += f" (n={n}, low power)"
    return f"{strength} {direction}, {sig}"


def generate_json_output(merged, composites, timestamp):
    labels = sorted(merged.keys())

    # build scatter data
    scatter = {}
    for l in labels:
        m = merged[l]
        scatter[l] = {
            "center_err": m["int_center_err"],
            "step_err":   m["int_step_err"],
            "ext_step_std": m["ext_step_std"],
            "winner": m.get("winner", "?"),
        }

    # build correlation summary
    corr_summary = {}
    for name, c in composites.items():
        corr_summary[name] = {
            "pearson_r":    round(c["pearson_r"], 6),
            "pearson_p":    round(c["pearson_p"], 6),
            "spearman_rho": round(c["spearman_rho"], 6),
            "spearman_p":   round(c["spearman_p"], 6),
        }

    # directional agreement
    center = [merged[l]["int_center_err"] for l in labels]
    step   = [merged[l]["int_step_err"]   for l in labels]
    ext    = [merged[l]["ext_step_std"]    for l in labels]
    transitions = []
    for i in range(len(labels) - 1):
        dc = center[i+1] - center[i]
        ds = step[i+1] - step[i]
        de = ext[i+1] - ext[i]
        transitions.append({
            "from": labels[i], "to": labels[i+1],
            "delta_center_err": round(dc, 6),
            "delta_step_err":   round(ds, 6),
            "delta_ext_step_std": round(de, 6),
            "center_agrees": (dc > 0 and de > 0) or (dc < 0 and de < 0),
            "step_agrees":   (ds > 0 and de > 0) or (ds < 0 and de < 0),
        })

    # best predictor
    sorted_c = sorted(composites.items(), key=lambda kv: -abs(kv[1]["pearson_r"]))
    best_name = sorted_c[0][0]

    r_center = composites["center_err"]["pearson_r"]
    r_step   = composites["step_err"]["pearson_r"]
    reliable = abs(r_center) >= 0.5 or abs(r_step) >= 0.5

    output = {
        "title": "Internal-External Correlation Analysis",
        "timestamp": timestamp,
        "n_rounds": len(labels),
        "rounds": labels,
        "data": scatter,
        "correlations": corr_summary,
        "transitions": transitions,
        "best_predictor": {
            "name": best_name,
            "pearson_r":    round(sorted_c[0][1]["pearson_r"], 6),
            "spearman_rho": round(sorted_c[0][1]["spearman_rho"], 6),
        },
        "conclusion": {
            "internal_is_reliable_proxy": reliable,
            "center_err_pearson_r": round(r_center, 6),
            "step_err_pearson_r":   round(r_step, 6),
            "recommendation": (
                "internal_sufficient_with_external_validation"
                if reliable else
                "external_gmf_validation_mandatory"
            ),
        },
    }
    return output


# ────────────────────────────────────────────────────────────
# 7. Main
# ────────────────────────────────────────────────────────────

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Internal-External Correlation Analysis")
    print(f"  Base dir: {BASE_DIR}")
    print()

    # collect data
    print("[1/5] Auto-collecting internal metrics from decision JSONs...")
    auto_int = auto_collect_internal(BASE_DIR)
    for k, v in sorted(auto_int.items()):
        print(f"  {k}: winner={v['winner']}, center_err={v['int_center_err']:.6f}, step_err={v['int_step_err']:.6f}")
    print(f"  -> Found {len(auto_int)} rounds")
    print()

    print("[2/5] Auto-collecting external metrics from comparison JSONs...")
    auto_ext = auto_collect_external(BASE_DIR)
    for k, v in sorted(auto_ext.items()):
        print(f"  {k}: ext_step_std={v['ext_step_std']:.6f}")
    print(f"  -> Found {len(auto_ext)} rounds")
    print()

    print("[3/5] Merging with hardcoded data...")
    merged = merge_data(HARDCODED, auto_int, auto_ext)
    print(f"  -> {len(merged)} rounds with complete data: {', '.join(sorted(merged.keys()))}")
    print()

    if len(merged) < 3:
        print("ERROR: Need at least 3 data points for correlation. Aborting.")
        return

    # compute correlations
    print("[4/5] Computing correlations...")
    composites = compute_composites(merged)
    for name in ["center_err", "step_err"]:
        c = composites[name]
        print(f"  {name:20s}: Pearson r={c['pearson_r']:+.4f} (p={c['pearson_p']:.4f}), "
              f"Spearman rho={c['spearman_rho']:+.4f} (p={c['spearman_p']:.4f})")
    print()

    # find best composite
    best_name, best_c = sorted(composites.items(), key=lambda kv: -abs(kv[1]["pearson_r"]))[0]
    print(f"  Best composite predictor: {best_name} (Pearson r={best_c['pearson_r']:+.4f})")
    print()

    # generate outputs
    print("[5/5] Generating reports...")
    md_content = generate_md_report(merged, composites, timestamp)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  Markdown: {MD_PATH}")

    json_output = generate_json_output(merged, composites, timestamp)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    print(f"  JSON:     {JSON_PATH}")
    print()

    # summary
    r_center = composites["center_err"]["pearson_r"]
    r_step   = composites["step_err"]["pearson_r"]
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  center_err vs ext_step_std:  Pearson r = {r_center:+.4f}")
    print(f"  step_err   vs ext_step_std:  Pearson r = {r_step:+.4f}")
    print(f"  Best composite:              {best_name} (r = {best_c['pearson_r']:+.4f})")
    if abs(r_center) < 0.5 and abs(r_step) < 0.5:
        print()
        print("  VERDICT: Internal metrics are NOT reliable proxies for external GMF.")
        print("           External validation remains MANDATORY.")
    else:
        better = "center_err" if abs(r_center) > abs(r_step) else "step_err"
        print()
        print(f"  VERDICT: {better} shows meaningful correlation with external GMF.")
        print("           External validation still recommended.")
    print("=" * 60)


if __name__ == "__main__":
    main()
