from __future__ import annotations

import datetime as dt
import json
import shutil
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns


VE_DIR = Path(__file__).resolve().parent
QUICK_DIR = VE_DIR.parent
OUTPUT_DIR = QUICK_DIR / "slide_ready_L0_L1_single_images_20260625" / "05_result_charts_single"
L0_JSON = VE_DIR / "L0_newdata" / "L0_newdata_summary.json"
L1_JSON = VE_DIR / "L1_newdata" / "L1_newdata_summary.json"
PAIRED_CSV = VE_DIR / "L1_paired_frame_check" / "paired_frame_metrics.csv"

FONT_FAMILY = ["Aptos", "Inter", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"]
MONO_FONT_FAMILY = ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "monospace"]

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

NEUTRAL = {
    "xlight": "#F4F5F7",
    "light": "#E2E5EA",
    "base": "#C5CAD3",
    "mid": "#7A828F",
    "dark": "#464C55",
}

COLORS = {
    "blue": {
        "xlight": "#EAF1FE",
        "light": "#CEDFFE",
        "base": "#A3BEFA",
        "mid": "#5477C4",
        "dark": "#2E4780",
    },
    "gold": {
        "xlight": "#FFF4C2",
        "light": "#FFEA8F",
        "base": "#FFE15B",
        "mid": "#B8A037",
        "dark": "#736422",
    },
    "orange": {
        "xlight": "#FFEDDE",
        "light": "#FFBDA1",
        "base": "#F0986E",
        "mid": "#CC6F47",
        "dark": "#804126",
    },
    "olive": {
        "xlight": "#D8ECBD",
        "light": "#BEEB96",
        "base": "#A3D576",
        "mid": "#71B436",
        "dark": "#386411",
    },
}

COEF_SHORT = {
    1: "x1: Z2 Y-tilt",
    2: "x2: Z3 X-tilt",
    3: "x3: Z4 astig 45 deg",
    4: "x4: Z5 defocus",
    5: "x5: Z6 astig 0 deg",
    6: "x6: Z7 trefoil",
    7: "x7: Z8 coma Y",
    8: "x8: Z9 coma X",
    9: "x9: Z10 trefoil",
    10: "x10: Z11 quadrafoil",
    11: "x11: Z12 secondary astig",
    12: "x12: Z13 spherical",
    13: "x13: Z14 secondary astig",
    14: "x14: Z15 quadrafoil",
    15: "x15: AC amplitude",
}


def use_chart_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "figure.edgecolor": "none",
            "savefig.facecolor": TOKENS["surface"],
            "savefig.edgecolor": "none",
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "axes.grid": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": TOKENS["grid"],
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": FONT_FAMILY,
            "font.monospace": MONO_FONT_FAMILY,
            "patch.linewidth": 1.0,
        },
    )


def add_chart_header(
    fig: plt.Figure,
    ax: plt.Axes,
    title: str,
    subtitle: str,
    *,
    title_width: int = 78,
    subtitle_width: int = 112,
    top: float = 0.82,
) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=top)
    left = ax.get_position().x0
    wrapped_title = textwrap.fill(title, width=title_width, break_long_words=False)
    wrapped_subtitle = textwrap.fill(subtitle, width=subtitle_width, break_long_words=False)
    title_lines = wrapped_title.count("\n") + 1
    fig.text(
        left,
        0.975,
        wrapped_title,
        ha="left",
        va="top",
        fontsize=15,
        fontweight="semibold",
        color=TOKENS["ink"],
        linespacing=1.08,
    )
    fig.text(
        left,
        0.915 - 0.038 * (title_lines - 1),
        wrapped_subtitle,
        ha="left",
        va="top",
        fontsize=10.5,
        color=TOKENS["muted"],
        linespacing=1.18,
    )
    sns.despine(ax=ax)


def style_axes(ax: plt.Axes, *, y_grid: bool = True, x_grid: bool = False) -> None:
    ax.grid(False, axis="y")
    ax.grid(False, axis="x")
    if y_grid:
        ax.grid(True, axis="y", color=TOKENS["grid"], linewidth=0.8)
    if x_grid:
        ax.grid(True, axis="x", color=TOKENS["grid"], linewidth=0.8)
    ax.tick_params(axis="both", colors=TOKENS["muted"], labelsize=9, length=0)
    ax.xaxis.label.set_color(TOKENS["ink"])
    ax.yaxis.label.set_color(TOKENS["ink"])
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(TOKENS["axis"])


def save_chart(fig: plt.Figure, filename: str) -> Path:
    path = OUTPUT_DIR / filename
    fig.savefig(path, dpi=240, bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)
    return path


def write_note(filename: str, title: str, description: str, use: str, caution: str, source: Path) -> None:
    note_path = OUTPUT_DIR / f"{filename}.txt"
    note_path.write_text(
        "\n".join(
            [
                f"Title: {title}",
                f"What it shows: {description}",
                f"Slide use: {use}",
                f"Caution: {caution}",
                f"Source: {source}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def backup_existing_outputs() -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = OUTPUT_DIR / f"backup_before_english_units_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for path in sorted(OUTPUT_DIR.glob("chart_*.png*")):
        if path.is_file():
            shutil.copy2(path, backup_dir / path.name)
    return backup_dir


def load_inputs() -> tuple[dict, dict, pd.DataFrame]:
    l0 = json.loads(L0_JSON.read_text(encoding="utf-8"))
    l1 = json.loads(L1_JSON.read_text(encoding="utf-8"))
    paired = pd.read_csv(PAIRED_CSV)
    return l0, l1, paired


def build_rounds_df(l0: dict) -> pd.DataFrame:
    rows = []
    for row in l0["all_completed_repeat_fit_runs"]:
        role = "Formal L0 anchor" if row["role"] == "formal_L0" else "L1 source diagnostic"
        rows.append(
            {
                "round_name": row["round_name"].replace("Circle_", ""),
                "role": role,
                "median": row["clean_noise_floor_median"],
                "mean": row["clean_noise_floor_mean"],
            }
        )
    return pd.DataFrame(rows)


def chart_l0_noise_by_round(l0: dict) -> None:
    rounds = build_rounds_df(l0)
    plot_df = rounds.melt(
        id_vars=["round_name", "role"],
        value_vars=["median", "mean"],
        var_name="Statistic",
        value_name="Spread",
    )
    plot_df["Statistic"] = plot_df["Statistic"].map(
        {"median": "Median repeated-fit spread", "mean": "Mean repeated-fit spread"}
    )

    fig, ax = plt.subplots(figsize=(11.3, 6.4))
    palette = {
        "Median repeated-fit spread": COLORS["blue"]["base"],
        "Mean repeated-fit spread": COLORS["gold"]["base"],
    }
    sns.barplot(
        data=plot_df,
        x="round_name",
        y="Spread",
        hue="Statistic",
        palette=palette,
        ax=ax,
        edgecolor=TOKENS["ink"],
        linewidth=0.9,
    )
    for patch, stat in zip(ax.patches, list(plot_df["Statistic"]) * 2):
        if "Mean" in stat:
            patch.set_edgecolor(COLORS["gold"]["dark"])
        else:
            patch.set_edgecolor(COLORS["blue"]["dark"])
    for container in ax.containers:
        ax.bar_label(container, fmt="%.4f", padding=3, fontsize=8.5, color=TOKENS["ink"])

    ax.set_xlabel("Capture round")
    ax.set_ylabel("Repeated-fit spread (unitless coefficient units)")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.015),
        frameon=False,
        ncol=2,
        borderaxespad=0,
        fontsize=9,
    )
    style_axes(ax)
    add_chart_header(
        fig,
        ax,
        "L0 repeated-fit noise floor by capture round",
        "Each round was fit 15 times on the same 9 representative FOVs. Circle_Round1 is the formal L0 anchor; Round2/3 are shown only as L1 source diagnostics.",
        top=0.78,
    )
    fig.subplots_adjust(bottom=0.14)
    filename = "chart_02_l0_noise_floor_by_round.png"
    save_chart(fig, filename)
    write_note(
        filename,
        "L0 repeated-fit noise floor by capture round",
        "Compares the median and mean spread from repeated fitting within each capture round. The visible unit is unitless coefficient spread.",
        "Use this on the L0 result slide to explain the algorithm's own repeated-fit floor before discussing L1.",
        "Only Circle_Round1 is the formal L0 anchor. Round2 and Round3 are repeated-fit diagnostics for the L1 source rounds.",
        L0_JSON,
    )


def chart_l1_vs_l0_by_fov(l1: dict) -> None:
    fov_df = pd.DataFrame(l1["summary"]["fov_rows"]).copy()
    fov_df["FOV"] = fov_df["fov_index"].map(lambda x: f"#{x}")
    fig, ax = plt.subplots(figsize=(12.5, 6.6))
    x = np.arange(len(fov_df))
    width = 0.36
    bars_l0 = ax.bar(
        x - width / 2,
        fov_df["l0_floor_median"],
        width=width,
        label="L0 repeated-fit floor",
        color=COLORS["blue"]["base"],
        edgecolor=COLORS["blue"]["dark"],
        linewidth=0.9,
    )
    bars_l1 = ax.bar(
        x + width / 2,
        fov_df["capture_std_median"],
        width=width,
        label="L1 capture spread",
        color=COLORS["orange"]["base"],
        edgecolor=COLORS["orange"]["dark"],
        linewidth=0.9,
    )
    ax.set_xticks(x, fov_df["FOV"])
    ax.set_xlabel("Representative FOV index")
    ax.set_ylabel("Median spread (unitless coefficient units)")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ax.bar_label(bars_l0, fmt="%.3f", padding=3, fontsize=8, color=TOKENS["ink"])
    ax.bar_label(bars_l1, fmt="%.3f", padding=3, fontsize=8, color=TOKENS["ink"])
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0, 1.015),
        frameon=False,
        ncol=2,
        borderaxespad=0,
        fontsize=9,
    )
    style_axes(ax)
    add_chart_header(
        fig,
        ax,
        "L1 capture spread remains below the L0 floor",
        "Per-FOV medians across the 6 trusted coefficients. L0 bars show repeated-fit uncertainty; L1 bars show spread across Circle_Round1/2/3 captures.",
        top=0.78,
    )
    fig.subplots_adjust(bottom=0.14)
    filename = "chart_03_l1_capture_vs_l0_floor_by_fov.png"
    save_chart(fig, filename)
    write_note(
        filename,
        "L1 capture spread remains below the L0 floor",
        "Shows the main L1 comparison by representative FOV: capture-to-capture spread versus the local L0 repeated-fit floor.",
        "Use this as the main L1 result figure because it directly answers whether three same-condition captures exceeded L0.",
        "This chart covers 9 representative FOVs and 6 trusted coefficients, not all 121 grid positions.",
        L1_JSON,
    )


def chart_l1_abs_z_by_coefficient(l1: dict) -> None:
    coef_df = pd.DataFrame(l1["summary"]["coef_rows"]).copy()
    coef_df["label_short"] = coef_df["coef_number"].map(COEF_SHORT)
    coef_df["group"] = np.where(coef_df["used_for_main_readout"], "Trusted readout", "Not used for main readout")
    coef_df = coef_df.sort_values("median_abs_z", ascending=True)
    fig, ax = plt.subplots(figsize=(12.0, 7.4))

    colors = np.where(coef_df["used_for_main_readout"], COLORS["blue"]["base"], NEUTRAL["light"])
    edges = np.where(coef_df["used_for_main_readout"], COLORS["blue"]["dark"], NEUTRAL["mid"])
    bars = ax.barh(
        coef_df["label_short"],
        coef_df["median_abs_z"],
        color=colors,
        edgecolor=edges,
        linewidth=0.9,
    )
    ax.axvline(2.0, color=TOKENS["ink"], linestyle=":", linewidth=1.2)
    ax.text(2.03, len(coef_df) - 1.0, "warning reference: |z| = 2", va="center", ha="left", fontsize=9, color=TOKENS["muted"])
    for bar, value in zip(bars, coef_df["median_abs_z"]):
        ax.text(
            value + 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            fontsize=8.5,
            color=TOKENS["ink"],
        )
    ax.set_xlabel("Median |z| vs. local L0 floor (dimensionless)")
    ax.set_ylabel("PSF coefficient")
    ax.set_xlim(0, max(2.35, float(coef_df["median_abs_z"].max()) * 1.25))
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=COLORS["blue"]["base"], edgecolor=COLORS["blue"]["dark"], label="Trusted readout"),
        plt.Rectangle((0, 0), 1, 1, facecolor=NEUTRAL["light"], edgecolor=NEUTRAL["mid"], label="Background only"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.015), frameon=False, ncol=2, borderaxespad=0, fontsize=9)
    style_axes(ax, y_grid=False, x_grid=True)
    add_chart_header(
        fig,
        ax,
        "Capture-to-capture shifts are below the warning level",
        "Median |z| is normalized by each coefficient/FOV L0 floor, so the unit is dimensionless. Blue bars are the 6 trusted coefficients used for the main readout.",
        top=0.78,
    )
    fig.subplots_adjust(left=0.28, bottom=0.12)
    filename = "chart_04_l1_abs_z_by_coefficient.png"
    save_chart(fig, filename)
    write_note(
        filename,
        "Capture-to-capture shifts are below the warning level",
        "Ranks coefficients by median normalized capture shift. The unit is dimensionless because each value is divided by its local L0 floor.",
        "Use this on an L1 detail slide to show that the conclusion is not hiding one unstable coefficient.",
        "Gray coefficients are shown for context only because they are locked, saturated, or not reliable for the main readout.",
        L1_JSON,
    )


def chart_l1_capture_std_heatmap(l1: dict) -> None:
    coef_df = pd.DataFrame(l1["summary"]["coef_rows"]).copy()
    fov_df = pd.DataFrame(l1["summary"]["fov_rows"]).copy()
    trusted = coef_df[coef_df["used_for_main_readout"]].copy()
    capture_std = np.array(l1["arrays"]["capture_std"], dtype=float)
    heat = capture_std[trusted["coef_index"].astype(int).tolist(), :]
    heat_df = pd.DataFrame(
        heat,
        index=[COEF_SHORT[int(x)] for x in trusted["coef_number"]],
        columns=[f"#{int(x)}" for x in fov_df["fov_index"]],
    )

    fig, ax = plt.subplots(figsize=(12.2, 6.9))
    cmap = sns.blend_palette(
        [TOKENS["panel"], COLORS["blue"]["xlight"], COLORS["blue"]["light"], COLORS["blue"]["base"], COLORS["blue"]["mid"]],
        as_cmap=True,
    )
    sns.heatmap(
        heat_df,
        ax=ax,
        cmap=cmap,
        linewidths=1.0,
        linecolor=TOKENS["panel"],
        annot=True,
        fmt=".3f",
        annot_kws={"fontsize": 8, "color": TOKENS["ink"]},
        cbar_kws={"label": "Capture std. (unitless coefficient units)"},
    )
    ax.set_xlabel("Representative FOV index")
    ax.set_ylabel("Trusted PSF coefficient")
    ax.tick_params(axis="x", rotation=0, colors=TOKENS["muted"], labelsize=9, length=0)
    ax.tick_params(axis="y", rotation=0, colors=TOKENS["muted"], labelsize=8.5, length=0)
    ax.collections[0].colorbar.ax.yaxis.label.set_color(TOKENS["ink"])
    ax.collections[0].colorbar.ax.tick_params(colors=TOKENS["muted"], labelsize=8, length=0)
    add_chart_header(
        fig,
        ax,
        "L1 capture spread by coefficient and FOV",
        "Trusted coefficients only. Cell values are standard deviation across Circle_Round1/2/3 captures, reported in unitless coefficient units.",
        top=0.78,
    )
    fig.subplots_adjust(left=0.25, bottom=0.15)
    filename = "chart_05_l1_capture_std_heatmap.png"
    save_chart(fig, filename)
    write_note(
        filename,
        "L1 capture spread by coefficient and FOV",
        "Breaks the L1 spread into coefficient-by-FOV cells for the 6 trusted readouts.",
        "Use this as a technical detail figure to show where the L1 conclusion comes from.",
        "The color scale is capture standard deviation, not normalized |z| and not net variation after subtracting L0.",
        L1_JSON,
    )


def paired_heatmap(paired: pd.DataFrame, metric: str, filename: str, title: str, subtitle: str, cbar_label: str, fmt: str) -> None:
    agg = paired.groupby(["row", "col"], as_index=False).agg(value=(metric, "median"))
    matrix = agg.pivot(index="row", columns="col", values="value").sort_index(ascending=True)
    fig, ax = plt.subplots(figsize=(10.3, 7.8))
    cmap = sns.blend_palette(
        [TOKENS["panel"], COLORS["gold"]["xlight"], COLORS["gold"]["light"], COLORS["orange"]["base"], COLORS["orange"]["mid"]],
        as_cmap=True,
    )
    sns.heatmap(
        matrix,
        ax=ax,
        cmap=cmap,
        linewidths=0.9,
        linecolor=TOKENS["panel"],
        annot=True,
        fmt=fmt,
        annot_kws={"fontsize": 7.4, "color": TOKENS["ink"]},
        cbar_kws={"label": cbar_label},
    )
    ax.set_xlabel("FOV column in the 11 x 11 grid")
    ax.set_ylabel("FOV row in the 11 x 11 grid")
    ax.tick_params(axis="x", rotation=0, colors=TOKENS["muted"], labelsize=8.5, length=0)
    ax.tick_params(axis="y", rotation=0, colors=TOKENS["muted"], labelsize=8.5, length=0)
    ax.collections[0].colorbar.ax.yaxis.label.set_color(TOKENS["ink"])
    ax.collections[0].colorbar.ax.tick_params(colors=TOKENS["muted"], labelsize=8, length=0)
    add_chart_header(fig, ax, title, subtitle, title_width=60, subtitle_width=88, top=0.79)
    fig.subplots_adjust(bottom=0.13)
    save_chart(fig, filename)


def chart_paired_frame_heatmaps(paired: pd.DataFrame) -> None:
    paired_heatmap(
        paired,
        "edge_mean_abs_diff",
        "chart_06_paired_frame_edge_diff_heatmap.png",
        "Paired-frame edge difference by FOV",
        "Median absolute gray-level difference along the circle edge. Each cell aggregates the same-position frame-1/frame-2 pairs across 3 rounds.",
        "Edge MAD (gray levels)",
        ".2f",
    )
    write_note(
        "chart_06_paired_frame_edge_diff_heatmap.png",
        "Paired-frame edge difference by FOV",
        "Shows how much the circle-edge gray values changed between the two consecutive frames at each grid location.",
        "Use this as an image-layer support figure: it explains that same-position consecutive frames were visually stable.",
        "This is an image-difference check, not a PSF coefficient fitting result for frame 2.",
        PAIRED_CSV,
    )

    paired_heatmap(
        paired,
        "center_shift_px",
        "chart_07_paired_frame_center_shift_heatmap.png",
        "Paired-frame center shift by FOV",
        "Median center displacement between two consecutive frames. Each cell aggregates the same-position frame-1/frame-2 pairs across 3 rounds.",
        "Center shift (px)",
        ".2f",
    )
    write_note(
        "chart_07_paired_frame_center_shift_heatmap.png",
        "Paired-frame center shift by FOV",
        "Shows the estimated center displacement between the two consecutive frames at each grid location.",
        "Use this as a supporting figure for short-term image repeatability and sub-pixel capture stability.",
        "This center shift is an image-layer estimate, not the final PSF coefficient drift.",
        PAIRED_CSV,
    )


def chart_paired_distribution(paired: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.5))
    palette = {1: COLORS["blue"]["base"], 2: COLORS["gold"]["base"], 3: COLORS["olive"]["base"]}
    edge_palette = {1: COLORS["blue"]["dark"], 2: COLORS["gold"]["dark"], 3: COLORS["olive"]["dark"]}
    sample = paired.sample(min(len(paired), 363), random_state=7)

    for ax, metric, y_label, panel_title in [
        (axes[0], "edge_mean_abs_diff", "Edge MAD (gray levels)", "Edge gray-level difference"),
        (axes[1], "center_shift_px", "Center shift (px)", "Center shift"),
    ]:
        sns.boxplot(
            data=paired,
            x="round_number",
            y=metric,
            hue="round_number",
            palette=palette,
            ax=ax,
            legend=False,
            linewidth=0.9,
            fliersize=2,
        )
        for patch, round_number in zip(ax.patches, sorted(palette)):
            patch.set_edgecolor(edge_palette[round_number])
        sns.stripplot(
            data=sample,
            x="round_number",
            y=metric,
            color=NEUTRAL["dark"],
            size=2.2,
            alpha=0.25,
            ax=ax,
            jitter=0.18,
        )
        ax.set_xlabel("Capture round")
        ax.set_ylabel(y_label)
        ax.set_title(panel_title, fontsize=11, color=TOKENS["ink"], pad=10)
        style_axes(ax)

    fig.subplots_adjust(top=0.78, wspace=0.28, bottom=0.14)
    left = axes[0].get_position().x0
    fig.text(
        left,
        0.975,
        "Paired-frame image differences by capture round",
        ha="left",
        va="top",
        fontsize=15,
        fontweight="semibold",
        color=TOKENS["ink"],
    )
    fig.text(
        left,
        0.915,
        "Each point is one same-position frame pair. Boxplots summarize 121 pairs per round for edge gray-level difference and center displacement.",
        ha="left",
        va="top",
        fontsize=10.5,
        color=TOKENS["muted"],
    )
    filename = "chart_08_paired_frame_distribution_by_round.png"
    save_chart(fig, filename)
    write_note(
        filename,
        "Paired-frame image differences by capture round",
        "Summarizes all 363 paired-frame checks with boxplots and individual points.",
        "Use this when you want one compact slide showing that the paired-frame image layer is stable across all three capture rounds.",
        "This is still an image-layer check; the main L1 PSF coefficient comparison uses the first frame from each round.",
        PAIRED_CSV,
    )


def redraw_all() -> Path:
    if not OUTPUT_DIR.exists():
        raise FileNotFoundError(f"Output folder does not exist: {OUTPUT_DIR}")
    backup_dir = backup_existing_outputs()
    l0, l1, paired = load_inputs()
    chart_l0_noise_by_round(l0)
    chart_l1_vs_l0_by_fov(l1)
    chart_l1_abs_z_by_coefficient(l1)
    chart_l1_capture_std_heatmap(l1)
    chart_paired_frame_heatmaps(paired)
    chart_paired_distribution(paired)
    return backup_dir


if __name__ == "__main__":
    use_chart_theme()
    backup = redraw_all()
    print(f"Redrawn English slide charts in: {OUTPUT_DIR}")
    print(f"Original files backed up in: {backup}")
