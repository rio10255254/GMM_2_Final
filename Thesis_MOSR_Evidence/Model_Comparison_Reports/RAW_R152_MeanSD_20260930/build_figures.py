"""Grayscale RAW/R152 figures from all 30 complete, paired scans."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.legend_handler import HandlerTuple
PROJECT_ROOT = Path(__file__).resolve().parents[3]

HERE = Path(__file__).resolve().parent
ROOT = Path(str(PROJECT_ROOT))
SOURCE = ROOT / "Experiments/R152_R148v2_SafeAdaptivePSF/results/comparison/all_displacements.csv"
AUDIT = SOURCE.parents[1] / "final_audit.json"
REFERENCE = HERE.parent / "WithinScan_30Step_16Models_20260930/summary.json"
MODELS = {"Raw": "RAW", "R152-R148v2-SafeAdaptivePSF": "R152"}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 10.5, "axes.labelsize": 11, "axes.titlesize": 12,
    "legend.fontsize": 10, "axes.linewidth": .7, "lines.linewidth": 1.4,
    "xtick.direction": "out", "ytick.direction": "out",
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "savefig.facecolor": "white", "figure.facecolor": "white",
})


def read_data():
    assert json.loads(AUDIT.read_text(encoding="utf-8"))["passed"] is True
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = [r for r in csv.DictReader(stream)
                if r["model"] in MODELS and r["kind"] == "adjacent"]
    assert len(rows) == 1800
    matrices, run_ids, run_indices, pi_matrices = {}, {}, {}, {}
    for model, display in MODELS.items():
        selected = [r for r in rows if r["model"] == model]
        grouped = {}
        for row in selected:
            key = (int(row["run_index"]), row["run"])
            grouped.setdefault(key, []).append(row)
        keys = sorted(grouped)
        assert len(keys) == 30 and [k[0] for k in keys] == list(range(1, 31))
        values, pi_values = [], []
        for key in keys:
            group = sorted(grouped[key], key=lambda r: int(r["j"]))
            assert len(group) == 30
            assert [int(r["j"]) for r in group] == list(range(1, 31))
            assert all(int(r["j"]) == int(r["i"]) + 1 for r in group)
            values.append([float(r["image_displacement_um"]) * 1000 for r in group])
            pi_values.append([float(r["pi_displacement_um"]) * 1000 for r in group])
        matrices[display] = np.asarray(values)
        pi_matrices[display] = np.asarray(pi_values)
        run_ids[display] = [k[1] for k in keys]
        run_indices[display] = [k[0] for k in keys]
    assert run_ids["RAW"] == run_ids["R152"]
    assert np.array_equal(pi_matrices["RAW"], pi_matrices["R152"])
    assert all(v.shape == (30, 30) and np.isfinite(v).all() for v in matrices.values())
    return matrices, run_ids["RAW"]


def write_csv(name, rows):
    path = HERE / name
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def canvas(title, ylabel, xlabel):
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    fig.subplots_adjust(left=.115, right=.98, bottom=.16, top=.77)
    fig.suptitle(title, y=.965)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xlim(.5, 30.5)
    ax.set_xticks([1, 5, 10, 15, 20, 25, 30])
    ax.grid(axis="y", color="0.9", linewidth=.55)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


def save(fig, stem):
    outputs = []
    for ext in ("png", "pdf", "svg"):
        path = HERE / f"{stem}.{ext}"
        fig.savefig(path, dpi=450, metadata=None)
        assert path.exists() and path.stat().st_size > 1000
        outputs.append(path.name)
    plt.close(fig)
    return outputs


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    matrices, runs = read_data()
    point_data, stats, scan_sds = [], {}, {}
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    expected = {r["display"]: r for r in reference["ranked_summary"]}
    for display, values in matrices.items():
        means = values.mean(axis=0)
        sds = values.std(axis=0, ddof=1)
        for j in range(30):
            assert abs(means[j] - statistics.mean(values[:, j])) < 1e-10
            assert abs(sds[j] - statistics.stdev(values[:, j])) < 1e-10
            point_data.append({
                "method": display, "step": j + 1, "n_scans": 30,
                "mean_displacement_nm": float(means[j]),
                "sample_sd_across_scans_nm": float(sds[j]),
                "lower_mean_minus_1sd_nm": float(means[j] - sds[j]),
                "upper_mean_plus_1sd_nm": float(means[j] + sds[j]),
            })
        scan_sds[display] = values.std(axis=1, ddof=1)
        for i, sd in enumerate(scan_sds[display]):
            assert abs(sd - statistics.stdev(values[i])) < 1e-10
        pooled = float(np.sqrt(np.mean(scan_sds[display] ** 2)))
        assert abs(pooled - expected[display]["pooled_within_scan_sd_nm"]) < 1e-10
        stats[display] = {
            "pooled_within_scan_sd_nm": pooled,
            "mean_of_scan_sds_nm": float(scan_sds[display].mean()),
            "sd_of_scan_sds_nm": float(scan_sds[display].std(ddof=1)),
            "minimum_scan_sd_nm": float(scan_sds[display].min()),
            "maximum_scan_sd_nm": float(scan_sds[display].max()),
        }

    improvement = 100 * (1 - scan_sds["R152"] / scan_sds["RAW"])
    assert (improvement > 0).all()
    scan_data = [{
        "scan_index": i + 1, "scan_id": runs[i], "n_adjacent_steps": 30,
        "RAW_within_scan_sd_nm": float(scan_sds["RAW"][i]),
        "R152_within_scan_sd_nm": float(scan_sds["R152"][i]),
        "R152_reduction_percent": float(improvement[i]),
    } for i in range(30)]
    write_csv("RAW_R152_step_mean_sd_data.csv", point_data)
    write_csv("RAW_R152_within_scan_sd_data.csv", scan_data)

    x = np.arange(1, 31)
    styles = {
        "RAW": dict(color="0.38", linestyle="--", marker="o", face="0.88", edge="0.65"),
        "R152": dict(color="0.0", linestyle="-", marker="s", face="0.62", edge="0.25"),
    }
    fig, ax = canvas("RAW and R152: step displacement (30 repeated scans)",
                     "Measured step displacement (nm)", "Step number")
    legend = []
    for display in ("RAW", "R152"):
        style = styles[display]
        means, sds = matrices[display].mean(axis=0), matrices[display].std(axis=0, ddof=1)
        ax.fill_between(x, means - sds, means + sds, facecolor=style["face"],
                        alpha=.75, linewidth=0, zorder=1)
        for bound in (means - sds, means + sds):
            ax.plot(x, bound, color=style["edge"], linewidth=.55,
                    linestyle=":" if display == "RAW" else "-", zorder=2)
        ax.plot(x, means, color=style["color"], linestyle=style["linestyle"],
                marker=style["marker"], markersize=3.2, markerfacecolor="white",
                markeredgewidth=.8, zorder=3)
        legend.append((Line2D([], [], color=style["color"], linestyle=style["linestyle"],
                              marker=style["marker"], markersize=4, markerfacecolor="white"),
                       Patch(facecolor=style["face"], edgecolor="none")))
    ax.set_ylim(980, 1020)
    ax.set_yticks(np.arange(980, 1021, 5))
    ax.legend(legend, ["RAW: mean ± 1 SD", "R152: mean ± 1 SD"],
              handler_map={tuple: HandlerTuple(ndivide=None)}, frameon=False,
              ncol=2, loc="lower center", bbox_to_anchor=(.5, 1.035), handlelength=3.2)
    fig.text(.115, .028, "Each point uses 30 paired scans; shaded bands show sample SD, not standard error.",
             fontsize=9)
    outputs = save(fig, "RAW_R152_step_mean_sd")

    fig, ax = canvas("RAW and R152: fluctuation within each 30-step scan",
                     "Within-scan step SD (nm)", "Repeated scan number")
    for display in ("RAW", "R152"):
        style = styles[display]
        center, width = stats[display]["mean_of_scan_sds_nm"], stats[display]["sd_of_scan_sds_nm"]
        ax.axhspan(center - width, center + width, facecolor=style["face"], alpha=.65, zorder=1)
        for bound in (center - width, center + width):
            ax.axhline(bound, color=style["edge"], linewidth=.55, linestyle=":", zorder=2)
        ax.axhline(center, color=style["edge"], linewidth=.7, linestyle="--", zorder=2)
        ax.plot(x, scan_sds[display], color=style["color"], linestyle=style["linestyle"],
                marker=style["marker"], markersize=3.2, markerfacecolor="white", markeredgewidth=.8,
                label=f"{display}: {center:.3f} ± {width:.3f} nm", zorder=3)
    ax.set_ylim(0, 15)
    ax.set_yticks(np.arange(0, 16, 3))
    ax.legend(frameon=False, ncol=2, loc="lower center", bbox_to_anchor=(.5, 1.035))
    fig.text(.115, .028, "Points: SD of 30 steps in one scan. Bands: mean of the 30 scan SDs ± 1 SD.",
             fontsize=9)
    outputs += save(fig, "RAW_R152_within_scan_sd")

    summary = {
        "methods": ["RAW", "R152"], "paired_scans": 30, "steps_per_scan": 30,
        "adjacent_observations": 1800,
        "main_figure": "At each step, mean measured displacement across 30 scans ± sample SD (ddof=1)",
        "secondary_figure": "One within-scan sample SD per 30-step scan; band is their mean ± sample SD",
        "source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_audit_passed": True,
        "independent_statistics_checks": "All 60 means, 60 SDs and 60 within-scan SDs checked with statistics",
        "within_scan_summary_matches_prior_recalculation": True,
        "results": stats,
        "improved_scans": int((improvement > 0).sum()),
        "per_scan_reduction_min_percent": float(improvement.min()),
        "per_scan_reduction_max_percent": float(improvement.max()),
        "pooled_reduction_percent": float(100 * (1 - stats["R152"]["pooled_within_scan_sd_nm"] /
                                                    stats["RAW"]["pooled_within_scan_sd_nm"])),
        "figures": outputs,
    }
    (HERE / "figure_data_checks.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f'''# RAW 與 R152：平均位移及標準差疊圖

日期：2026-09-30。只呈現同一批30趟RAW及R152，不含其他模型。

## 平均位移與上下範圍

![RAW與R152每一步的平均位移及正負一個標準差](RAW_R152_step_mean_sd.png)

橫軸為第1至30個相鄰位移步驟，縱軸為影像量得的單步位移，單位nm，設定步距約1000nm。RAW為灰色虛線與圓點、淺灰範圍；R152為黑色實線與方點、較深灰範圍。每一點取同一步在30趟中的平均值，上下範圍為平均值減／加一個樣本標準差，每一步都有30筆，未篩選趟次、未平滑曲線。這裡使用原始影像量得的位移，沒有先扣除PI回授，也沒有事後調整R152輸出。

此圖的標準差表示「同一步在30趟重拍中的差異」。它不是單趟30步波動，也不是平均值的標準誤或信賴區間。

**英文圖說：** Mean measured adjacent-step displacement for RAW and R152 over 30 repeated scans. Lines represent the mean displacement at each of the 30 steps, and shaded bands indicate ±1 sample standard deviation across scans (n = 30 at each step). Each scan contains 31 frames and 30 adjacent displacements. The nominal step is 1 μm. No smoothing or post-reconstruction correction was applied.

[高解析PNG](RAW_R152_step_mean_sd.png) · [論文用向量PDF](RAW_R152_step_mean_sd.pdf) · [可編輯SVG](RAW_R152_step_mean_sd.svg) · [60點完整平均與上下界數值](RAW_R152_step_mean_sd_data.csv)

## 單趟30步的波動

![RAW與R152每趟30步的波動及30趟分布](RAW_R152_within_scan_sd.png)

這張圖直接保留使用者指定的單趟指標：每一點先對同一趟30個步距取樣本標準差，橫軸才是第1至30趟重拍。灰帶表示30個單趟標準差的平均值加減這30個值的樣本標準差；它是描述這批30趟的分布，不是單趟標準差的估計誤差。第一張圖的橫軸是「步」，此圖的橫軸是「趟」，兩者不能交換使用。

| 方法 | 30個單趟標準差的平均 nm | 30個單趟標準差之間的標準差 nm | 合併單趟波動 nm | 單趟波動實際範圍 nm |
|---|---:|---:|---:|---:|
| RAW | {stats['RAW']['mean_of_scan_sds_nm']:.3f} | {stats['RAW']['sd_of_scan_sds_nm']:.3f} | {stats['RAW']['pooled_within_scan_sd_nm']:.3f} | {stats['RAW']['minimum_scan_sd_nm']:.3f}～{stats['RAW']['maximum_scan_sd_nm']:.3f} |
| R152 | {stats['R152']['mean_of_scan_sds_nm']:.3f} | {stats['R152']['sd_of_scan_sds_nm']:.3f} | {stats['R152']['pooled_within_scan_sd_nm']:.3f} | {stats['R152']['minimum_scan_sd_nm']:.3f}～{stats['R152']['maximum_scan_sd_nm']:.3f} |

R152在30/30趟都比同趟RAW波動低。單趟改善範圍{improvement.min():.1f}%～{improvement.max():.1f}%；合併改善{summary['pooled_reduction_percent']:.1f}%。此合併值扣除各趟自己的平均步距後合併變異，與圖中30個單趟標準差的算術平均不同。

**英文圖說：** Within-scan displacement fluctuation for RAW and R152 over 30 repeated scans. Each point is the sample standard deviation of the 30 adjacent-step displacements within one scan. Horizontal shaded bands show the mean of the 30 scan standard deviations ±1 sample standard deviation. RAW and R152 are paired by scan.

[高解析PNG](RAW_R152_within_scan_sd.png) · [論文用向量PDF](RAW_R152_within_scan_sd.pdf) · [可編輯SVG](RAW_R152_within_scan_sd.svg) · [30趟逐趟完整數值](RAW_R152_within_scan_sd_data.csv)

## 來源與核對

來源是已完成核對的R152驗證包，共同30趟、每趟31張，兩方法各900筆相鄰位移，共1800筆。本圖保留全部30趟；前六趟曾提供RAW移動方向校準。每一個平均值與樣本標準差均以另一種計算方式逐項核對；兩方法的合併單趟波動亦與既有完整重算一致。未對圖的灰帶除以√30。

- [共同原始位移總表](../../../Experiments/R152_R148v2_SafeAdaptivePSF/results/comparison/all_displacements.csv)
- [核對結果與來源身分](figure_data_checks.json)
'''
    (HERE / "RAW_R152_FIGURES_AND_CAPTIONS.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "passed", "methods": list(matrices), "paired_scans": 30,
                      "observations": 1800, "results": stats, "figures": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
