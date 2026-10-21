from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


VALIDATION_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\20260708_v41_standalone_full_validation"
)
SOURCE_DIR = VALIDATION_ROOT / "boundary_sensitive_roi_v41_compare"
SOURCE_ALL_STEPS = SOURCE_DIR / "tables" / "boundary_sensitive_all_steps.csv"
OUT_DIR = VALIDATION_ROOT / "single_model_displacement_summary_v41_standalone"
TABLE_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"

CASE_ORDER = ["raw", "v41_standalone"]
CASE_LABEL = {"raw": "Raw", "v41_standalone": "V41-Standalone"}
CASE_COLOR = {"raw": "#8f969e", "v41_standalone": "#d95f02"}
SELECTION_ORDER = ["all_steps", "common_best30", "raw_anchor_best30"]


def ensure_dirs() -> None:
    for folder in [OUT_DIR, TABLE_DIR, FIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    for pattern in ["*.csv", "*.md", "*.json"]:
        for path in OUT_DIR.glob(pattern):
            path.unlink()
        for path in TABLE_DIR.glob(pattern):
            path.unlink()
    for path in FIG_DIR.glob("*.png"):
        path.unlink()


def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    numeric_cols = [
        "step_index",
        "x_step_um",
        "y_abs_um",
        "abs_error_um",
        "x_quality",
        "object_um_per_px",
        "nominal_step_um",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    def magnification(row: pd.Series) -> str:
        group = str(row["group"])
        if str(row["dataset"]) == "20260702_100MG":
            return "50x"
        if group.startswith("20x_"):
            return "20x"
        if group.startswith("5x_"):
            return "5x"
        return "unknown"

    def step_label(row: pd.Series) -> str:
        nominal = float(row["nominal_step_um"])
        if abs(nominal - round(nominal)) < 1e-9:
            return f"{nominal:.0f} um/step"
        return f"{nominal:.1f} um/step"

    df["magnification"] = df.apply(magnification, axis=1)
    df["step_label"] = df.apply(step_label, axis=1)
    df["dataset_label"] = df["magnification"] + " " + df["step_label"]
    df["case_label"] = df["case"].map(CASE_LABEL)
    return df


def summarize(sub: pd.DataFrame, selection: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_cols = ["magnification", "dataset", "group", "dataset_label", "step_label", "case"]
    for keys, part in sub.groupby(group_cols, sort=False):
        mag, dataset, group, dataset_label, step_label, case = keys
        rows.append(
            {
                "magnification": mag,
                "dataset": dataset,
                "group": group,
                "dataset_label": dataset_label,
                "step_label": step_label,
                "selection": selection,
                "case": case,
                "case_label": CASE_LABEL[case],
                "n_steps": int(part["step_index"].nunique()),
                "nominal_step_um": float(part["nominal_step_um"].median()),
                "object_um_per_px": float(part["object_um_per_px"].median()),
                "median_step_um": float(part["x_step_um"].median()),
                "mean_step_um": float(part["x_step_um"].mean()),
                "std_step_um": float(part["x_step_um"].std(ddof=1)),
                "median_abs_error_um": float(part["abs_error_um"].median()),
                "mean_abs_error_um": float(part["abs_error_um"].mean()),
                "p90_abs_error_um": float(part["abs_error_um"].quantile(0.90)),
                "median_y_abs_um": float(part["y_abs_um"].median()),
                "mean_y_abs_um": float(part["y_abs_um"].mean()),
                "median_x_quality": float(part["x_quality"].median()),
            }
        )
    return pd.DataFrame(rows)


def selected_common_best30(df: pd.DataFrame) -> pd.DataFrame:
    selected_frames: list[pd.DataFrame] = []
    score_rows: list[pd.DataFrame] = []
    for _, group in df.groupby(["dataset", "group"], sort=False):
        valid_steps = (
            group.groupby("step_index")["case"]
            .nunique()
            .loc[lambda s: s == len(CASE_ORDER)]
            .index
        )
        candidates = group[group["step_index"].isin(valid_steps)].copy()
        step_score = (
            candidates.groupby("step_index")
            .agg(
                mean_abs_error_um=("abs_error_um", "mean"),
                max_abs_error_um=("abs_error_um", "max"),
                mean_y_abs_um=("y_abs_um", "mean"),
                min_quality=("x_quality", "min"),
            )
            .reset_index()
        )
        step_score["score_um"] = (
            step_score["mean_abs_error_um"]
            + 0.25 * step_score["max_abs_error_um"]
            + 0.50 * step_score["mean_y_abs_um"]
            - 0.001 * step_score["min_quality"]
        )
        chosen = step_score.sort_values(["score_um", "step_index"]).head(30)["step_index"]
        chosen_set = set(int(x) for x in chosen)
        selected = candidates[candidates["step_index"].isin(chosen_set)].copy()
        selected["selection"] = "common_best30"
        selected_frames.append(selected)

        labels = candidates.iloc[0][
            ["magnification", "dataset", "group", "dataset_label", "step_label"]
        ].to_dict()
        step_score = step_score.assign(**labels)
        step_score["chosen_common_best30"] = step_score["step_index"].isin(chosen_set)
        score_rows.append(step_score)
    return pd.concat(selected_frames, ignore_index=True), pd.concat(score_rows, ignore_index=True)


def selected_raw_anchor_best30(df: pd.DataFrame) -> pd.DataFrame:
    selected_frames: list[pd.DataFrame] = []
    score_rows: list[pd.DataFrame] = []
    for _, group in df.groupby(["dataset", "group"], sort=False):
        raw = group[group["case"] == "raw"].copy()
        raw_score = raw[
            [
                "step_index",
                "abs_error_um",
                "y_abs_um",
                "x_quality",
                "magnification",
                "dataset",
                "group",
                "dataset_label",
                "step_label",
            ]
        ].copy()
        raw_score["score_um"] = (
            raw_score["abs_error_um"] + 0.50 * raw_score["y_abs_um"] - 0.001 * raw_score["x_quality"]
        )
        chosen = raw_score.sort_values(["score_um", "step_index"]).head(30)["step_index"]
        chosen_set = set(int(x) for x in chosen)
        selected = group[group["step_index"].isin(chosen_set)].copy()
        selected["selection"] = "raw_anchor_best30"
        selected_frames.append(selected)

        raw_score["chosen_raw_anchor_best30"] = raw_score["step_index"].isin(chosen_set)
        score_rows.append(raw_score)
    return pd.concat(selected_frames, ignore_index=True), pd.concat(score_rows, ignore_index=True)


def compare(summary: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["magnification", "dataset", "group", "dataset_label", "step_label", "selection"]
    raw = summary[summary["case"] == "raw"].set_index(key_cols)
    v41 = summary[summary["case"] == "v41_standalone"].set_index(key_cols)
    rows: list[dict[str, object]] = []
    common_index = raw.index.intersection(v41.index)
    for key in common_index:
        r = raw.loc[key]
        m = v41.loc[key]
        raw_std = float(r["std_step_um"])
        model_std = float(m["std_step_um"])
        raw_err = float(r["median_abs_error_um"])
        model_err = float(m["median_abs_error_um"])
        std_improvement = (raw_std - model_std) / raw_std * 100 if raw_std else np.nan
        err_improvement_nm = (raw_err - model_err) * 1000
        if std_improvement >= 5 and err_improvement_nm >= 0:
            reading = "clear stability improvement"
        elif std_improvement > 0 and err_improvement_nm >= 0:
            reading = "small but consistent improvement"
        elif std_improvement > 0:
            reading = "stability improved but median error increased"
        elif err_improvement_nm > 0:
            reading = "median error improved but stability did not"
        else:
            reading = "no improvement"
        rows.append(
            {
                "magnification": key[0],
                "dataset": key[1],
                "group": key[2],
                "dataset_label": key[3],
                "step_label": key[4],
                "selection": key[5],
                "n_steps_raw": int(r["n_steps"]),
                "n_steps_v41": int(m["n_steps"]),
                "nominal_step_um": float(r["nominal_step_um"]),
                "object_um_per_px": float(r["object_um_per_px"]),
                "raw_median_step_um": float(r["median_step_um"]),
                "v41_median_step_um": float(m["median_step_um"]),
                "raw_std_step_um": raw_std,
                "v41_std_step_um": model_std,
                "raw_std_step_nm": raw_std * 1000,
                "v41_std_step_nm": model_std * 1000,
                "std_improvement_pct": std_improvement,
                "raw_median_abs_error_um": raw_err,
                "v41_median_abs_error_um": model_err,
                "raw_median_abs_error_nm": raw_err * 1000,
                "v41_median_abs_error_nm": model_err * 1000,
                "median_error_improvement_nm": err_improvement_nm,
                "raw_p90_abs_error_nm": float(r["p90_abs_error_um"]) * 1000,
                "v41_p90_abs_error_nm": float(m["p90_abs_error_um"]) * 1000,
                "raw_median_y_abs_nm": float(r["median_y_abs_um"]) * 1000,
                "v41_median_y_abs_nm": float(m["median_y_abs_um"]) * 1000,
                "reading": reading,
            }
        )
    out = pd.DataFrame(rows)
    mag_order = {"50x": 0, "20x": 1, "5x": 2}
    out["mag_order"] = out["magnification"].map(mag_order)
    out["selection_order"] = out["selection"].map({k: i for i, k in enumerate(SELECTION_ORDER)})
    out = out.sort_values(["selection_order", "mag_order", "nominal_step_um"]).drop(
        columns=["mag_order", "selection_order"]
    )
    return out


def plot_bar(comp: pd.DataFrame, selection: str, metric: str, ylabel: str, title: str, filename: str) -> None:
    part = comp[comp["selection"] == selection].copy()
    labels = part["dataset_label"].tolist()
    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(11.5, 5.8), dpi=160)
    ax.bar(x - width / 2, part[f"raw_{metric}"], width, label="Raw", color=CASE_COLOR["raw"])
    ax.bar(
        x + width / 2,
        part[f"v41_{metric}"],
        width,
        label="V41-Standalone",
        color=CASE_COLOR["v41_standalone"],
    )
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def plot_improvement(comp: pd.DataFrame, selection: str, filename: str) -> None:
    part = comp[comp["selection"] == selection].copy()
    selection_title = selection.replace("_", " ")
    labels = part["dataset_label"].tolist()
    x = np.arange(len(labels))
    colors = ["#2ca25f" if v >= 0 else "#de2d26" for v in part["std_improvement_pct"]]
    fig, ax = plt.subplots(figsize=(11.5, 5.3), dpi=160)
    ax.bar(x, part["std_improvement_pct"], color=colors)
    ax.axhline(0, color="black", linewidth=1.0)
    ax.set_ylabel("Stability improvement vs Raw (%)")
    ax.set_title(f"V41-Standalone displacement stability advantage ({selection_title})")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    min_val = float(part["std_improvement_pct"].min())
    max_val = float(part["std_improvement_pct"].max())
    lower = min(-4.0, min_val - max(1.5, abs(min_val) * 0.50))
    upper = max(5.0, max_val + max(1.5, abs(max_val) * 0.25))
    ax.set_ylim(lower, upper)
    for xi, val in zip(x, part["std_improvement_pct"]):
        va = "bottom" if val >= 0 else "top"
        offset = 0.6 if val >= 0 else -0.6
        ax.text(xi, val + offset, f"{val:+.1f}%", ha="center", va=va, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / filename)
    plt.close(fig)


def plot_step_traces(all_steps: pd.DataFrame) -> None:
    for (dataset, group), part in all_steps.groupby(["dataset", "group"], sort=False):
        labels = part.iloc[0]
        fig, ax = plt.subplots(figsize=(11.0, 5.2), dpi=160)
        for case in CASE_ORDER:
            cpart = part[part["case"] == case].sort_values("step_index")
            ax.plot(
                cpart["step_index"],
                cpart["x_step_um"],
                marker="o",
                markersize=3,
                linewidth=1.2,
                color=CASE_COLOR[case],
                label=CASE_LABEL[case],
            )
        nominal = float(labels["nominal_step_um"])
        ax.axhline(nominal, color="black", linestyle="--", linewidth=1.0, label="Nominal")
        ax.set_title(f"Step displacement trace - {labels['dataset_label']}")
        ax.set_xlabel("Step index")
        ax.set_ylabel("Measured x displacement (um)")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, ncol=3)
        fig.tight_layout()
        safe_group = str(group).replace(".", "p")
        fig.savefig(FIG_DIR / f"step_trace_{labels['magnification']}_{safe_group}.png")
        plt.close(fig)


def plot_magnification_panels(comp: pd.DataFrame, selection: str) -> None:
    part = comp[comp["selection"] == selection].copy()
    selection_title = selection.replace("_", " ")
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5), dpi=160)
    for ax, mag in zip(axes, ["50x", "20x", "5x"]):
        mpart = part[part["magnification"] == mag].sort_values("nominal_step_um")
        x = np.arange(len(mpart))
        width = 0.34
        ax.bar(
            x - width / 2,
            mpart["raw_std_step_nm"],
            width,
            color=CASE_COLOR["raw"],
            label="Raw",
        )
        ax.bar(
            x + width / 2,
            mpart["v41_std_step_nm"],
            width,
            color=CASE_COLOR["v41_standalone"],
            label="V41-Standalone",
        )
        ax.set_title(mag)
        ax.set_xticks(x)
        ax.set_xticklabels(mpart["step_label"], rotation=15, ha="right")
        ax.set_ylabel("Std. of step displacement (nm)")
        ax.grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False)
    fig.suptitle(f"Displacement stability by magnification ({selection_title})")
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{selection}_std_nm_by_magnification_panels.png")
    plt.close(fig)


def write_report(comp: pd.DataFrame, manifest: dict[str, object]) -> None:
    all_steps = comp[comp["selection"] == "all_steps"].copy()
    best30 = comp[comp["selection"] == "common_best30"].copy()

    def md_table(part: pd.DataFrame) -> str:
        cols = [
            "dataset_label",
            "n_steps_raw",
            "raw_std_step_nm",
            "v41_std_step_nm",
            "std_improvement_pct",
            "raw_median_abs_error_nm",
            "v41_median_abs_error_nm",
            "median_error_improvement_nm",
            "reading",
        ]
        tmp = part[cols].copy()
        rename = {
            "dataset_label": "資料集",
            "n_steps_raw": "步數",
            "raw_std_step_nm": "Raw標準差(nm)",
            "v41_std_step_nm": "V41標準差(nm)",
            "std_improvement_pct": "穩定性改善(%)",
            "raw_median_abs_error_nm": "Raw中位誤差(nm)",
            "v41_median_abs_error_nm": "V41中位誤差(nm)",
            "median_error_improvement_nm": "中位誤差改善(nm)",
            "reading": "判讀",
        }
        tmp = tmp.rename(columns=rename)
        for col in tmp.columns:
            if col.endswith("(nm)"):
                tmp[col] = tmp[col].map(lambda x: f"{x:.2f}")
            elif col.endswith("(%)"):
                tmp[col] = tmp[col].map(lambda x: f"{x:+.2f}")
        return tmp.to_markdown(index=False)

    lines = [
        "# V41-Standalone 單一模型位移比較整理",
        "",
        "本資料夾只保留 Raw 與最新單一 V41-Standalone 模型的比較，方便論文第六章直接引用。",
        "主要判讀以全部步數為主；common best-30 只作為補充，表示在兩者共同較乾淨的步數上比較。",
        "",
        "## 全部步數主表",
        "",
        md_table(all_steps),
        "",
        "## 共同最佳 30 步補充表",
        "",
        md_table(best30),
        "",
        "## 圖檔",
        "",
        "- figures/all_steps_std_nm_by_dataset.png：全部步數位移標準差比較。",
        "- figures/all_steps_improvement_pct.png：全部步數穩定性改善比例。",
        "- figures/all_steps_std_nm_by_magnification_panels.png：三個倍率分開顯示的全部步數穩定性圖。",
        "- figures/common_best30_std_nm_by_dataset.png：共同最佳 30 步標準差比較。",
        "- figures/step_trace_*.png：各倍率、各位移量逐步折線圖。",
        "",
        "## 來源",
        "",
        f"- source_all_steps: {manifest['source_all_steps']}",
        f"- generated_at: {manifest['generated_at']}",
    ]
    (OUT_DIR / "V41_STANDALONE_DISPLACEMENT_COMPARISON_REPORT.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    ensure_dirs()
    raw = pd.read_csv(SOURCE_ALL_STEPS)
    df = raw[raw["case"].isin(CASE_ORDER)].copy()
    df = add_labels(df)
    df = df[df["magnification"].isin(["50x", "20x", "5x"])].copy()

    common_best30, common_scores = selected_common_best30(df)
    raw_anchor_best30, raw_anchor_scores = selected_raw_anchor_best30(df)

    all_steps = df.copy()
    all_steps["selection"] = "all_steps"
    selected = pd.concat([all_steps, common_best30, raw_anchor_best30], ignore_index=True)

    summary = pd.concat(
        [
            summarize(all_steps, "all_steps"),
            summarize(common_best30, "common_best30"),
            summarize(raw_anchor_best30, "raw_anchor_best30"),
        ],
        ignore_index=True,
    )
    comp = compare(summary)

    all_steps.sort_values(["magnification", "nominal_step_um", "case", "step_index"]).to_csv(
        TABLE_DIR / "v41_standalone_all_steps_raw_vs_model.csv", index=False, encoding="utf-8-sig"
    )
    selected.sort_values(
        ["selection", "magnification", "nominal_step_um", "case", "step_index"]
    ).to_csv(TABLE_DIR / "v41_standalone_selected_steps_long.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(TABLE_DIR / "v41_standalone_summary_by_case.csv", index=False, encoding="utf-8-sig")
    comp.to_csv(
        TABLE_DIR / "v41_standalone_displacement_comparison.csv", index=False, encoding="utf-8-sig"
    )
    comp[comp["selection"] == "all_steps"].to_csv(
        TABLE_DIR / "v41_standalone_main_all_steps.csv", index=False, encoding="utf-8-sig"
    )
    comp[comp["selection"] == "common_best30"].to_csv(
        TABLE_DIR / "v41_standalone_common_best30.csv", index=False, encoding="utf-8-sig"
    )
    common_scores.to_csv(
        TABLE_DIR / "v41_standalone_common_best30_step_scores.csv",
        index=False,
        encoding="utf-8-sig",
    )
    raw_anchor_scores.to_csv(
        TABLE_DIR / "v41_standalone_raw_anchor_best30_step_scores.csv",
        index=False,
        encoding="utf-8-sig",
    )
    with pd.ExcelWriter(TABLE_DIR / "v41_standalone_displacement_tables.xlsx") as writer:
        comp[comp["selection"] == "all_steps"].to_excel(
            writer, sheet_name="main_all_steps", index=False
        )
        comp[comp["selection"] == "common_best30"].to_excel(
            writer, sheet_name="common_best30", index=False
        )
        comp[comp["selection"] == "raw_anchor_best30"].to_excel(
            writer, sheet_name="raw_anchor_best30", index=False
        )
        summary.to_excel(writer, sheet_name="summary_by_case", index=False)
        all_steps.to_excel(writer, sheet_name="all_step_values", index=False)

    plot_bar(
        comp,
        "all_steps",
        "std_step_nm",
        "Standard deviation of step displacement (nm)",
        "Raw vs V41-Standalone displacement stability (all steps)",
        "all_steps_std_nm_by_dataset.png",
    )
    plot_bar(
        comp,
        "all_steps",
        "median_abs_error_nm",
        "Median absolute error (nm)",
        "Raw vs V41-Standalone median step error (all steps)",
        "all_steps_median_error_nm_by_dataset.png",
    )
    plot_improvement(comp, "all_steps", "all_steps_improvement_pct.png")
    plot_magnification_panels(comp, "all_steps")
    plot_bar(
        comp,
        "common_best30",
        "std_step_nm",
        "Standard deviation of step displacement (nm)",
        "Raw vs V41-Standalone displacement stability (common best 30 steps)",
        "common_best30_std_nm_by_dataset.png",
    )
    plot_bar(
        comp,
        "common_best30",
        "median_abs_error_nm",
        "Median absolute error (nm)",
        "Raw vs V41-Standalone median step error (common best 30 steps)",
        "common_best30_median_error_nm_by_dataset.png",
    )
    plot_improvement(comp, "common_best30", "common_best30_improvement_pct.png")
    plot_magnification_panels(comp, "common_best30")
    plot_step_traces(all_steps)

    manifest = {
        "title": "Raw vs V41-Standalone single-model displacement comparison",
        "source_all_steps": str(SOURCE_ALL_STEPS),
        "output_dir": str(OUT_DIR),
        "cases": CASE_LABEL,
        "selections": {
            "all_steps": "All measured steps are included. This is the main thesis table.",
            "common_best30": "The same 30 cleaner steps are selected using Raw and V41-Standalone together.",
            "raw_anchor_best30": "The 30 cleaner steps selected only from Raw, kept for audit.",
        },
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "row_counts": {
            "input_all_step_rows": int(len(df)),
            "selected_long_rows": int(len(selected)),
            "summary_rows": int(len(summary)),
            "comparison_rows": int(len(comp)),
        },
    }
    (OUT_DIR / "single_model_displacement_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(comp, manifest)

    print(json.dumps(manifest["row_counts"], indent=2))
    print(OUT_DIR)


if __name__ == "__main__":
    main()
