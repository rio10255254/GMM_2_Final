from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from scipy.io import loadmat


@dataclass
class AnalysisResult:
    inventory_path: Path
    summary_report_path: Path
    report_draft_path: Path
    selected_mat_path: Path
    selected_csv_path: Path


@dataclass
class DataSelection:
    mat_path: Path
    csv_path: Path
    reason: str
    candidates: list[dict[str, Any]]


def configure_matplotlib_fonts() -> None:
    candidates = [
        "Microsoft JhengHei",
        "PingFang TC",
        "Noto Sans CJK TC",
        "Source Han Sans TW",
        "SimHei",
        "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    helper_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="PSF 報告輔助分析")
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--helper-root", type=Path, default=helper_root)
    parser.add_argument("--output-root", type=Path, default=helper_root / "outputs")
    parser.add_argument("--mat-path", type=Path, default=None)
    parser.add_argument("--csv-path", type=Path, default=None)
    return parser.parse_args()


def run_analysis(
    repo_root: Path,
    helper_root: Path,
    output_root: Path,
    preferred_mat: Path | None = None,
    preferred_csv: Path | None = None,
) -> AnalysisResult:
    configure_matplotlib_fonts()
    output_root = output_root.resolve()
    figures_dir = output_root / "figures"
    tables_dir = output_root / "tables"
    reports_dir = output_root / "reports"
    for path in (figures_dir, tables_dir, reports_dir):
        path.mkdir(parents=True, exist_ok=True)

    selection = select_data_sources(repo_root, preferred_mat, preferred_csv)
    psf_grid, coef_grid, fval_map, iterations_map = load_core_arrays(selection.mat_path)
    batch_df = pd.read_csv(selection.csv_path)
    validate_dataset_consistency(psf_grid, fval_map, iterations_map, batch_df)

    montage_path = figures_dir / "psf_montage.png"
    montage_log_path = figures_dir / "psf_montage_log_normalized.png"
    rep_path = figures_dir / "psf_representative_comparison.png"
    heatmap_path = figures_dir / "fval_heatmap.png"
    stats_path = tables_dir / "summary_stats.csv"
    inventory_path = reports_dir / "data_inventory_tw.md"
    summary_path = reports_dir / "analysis_summary_tw.md"
    draft_path = reports_dir / "report_text_draft_tw.md"

    render_montage(psf_grid, montage_path, normalize_each=False, log_scale=False)
    render_montage(psf_grid, montage_log_path, normalize_each=True, log_scale=True)
    representatives = render_representative_comparison(psf_grid, rep_path)
    render_heatmap(fval_map, heatmap_path)
    stats_df = build_summary_stats(fval_map, iterations_map, psf_grid, representatives, batch_df)
    stats_df.to_csv(stats_path, index=False, encoding="utf-8-sig")

    inventory_path.write_text(
        build_inventory_markdown(selection, batch_df, psf_grid),
        encoding="utf-8",
    )
    summary_path.write_text(
        build_analysis_summary(selection, stats_df, representatives, batch_df, psf_grid),
        encoding="utf-8",
    )
    draft_path.write_text(
        build_report_draft(stats_df, representatives, psf_grid),
        encoding="utf-8",
    )
    return AnalysisResult(
        inventory_path=inventory_path,
        summary_report_path=summary_path,
        report_draft_path=draft_path,
        selected_mat_path=selection.mat_path,
        selected_csv_path=selection.csv_path,
    )


def select_data_sources(
    repo_root: Path, preferred_mat: Path | None, preferred_csv: Path | None
) -> DataSelection:
    if preferred_mat and preferred_csv:
        return DataSelection(
            mat_path=preferred_mat.resolve(),
            csv_path=preferred_csv.resolve(),
            reason="使用明確指定的資料路徑。",
            candidates=[],
        )
    if preferred_mat:
        mat_path = preferred_mat.resolve()
        csv_path = mat_path.with_name("batch_results.csv")
        if not csv_path.exists():
            raise FileNotFoundError(
                f"只指定 MAT 時，找不到同目錄對應的 CSV：{csv_path}"
            )
        return DataSelection(
            mat_path=mat_path,
            csv_path=csv_path.resolve(),
            reason="使用指定 MAT，並自動配對同目錄的 CSV。",
            candidates=[],
        )
    if preferred_csv:
        csv_path = preferred_csv.resolve()
        mat_path = csv_path.with_name("PSF_fitted_2D_FOVstack.mat")
        if not mat_path.exists():
            raise FileNotFoundError(
                f"只指定 CSV 時，找不到同目錄對應的 MAT：{mat_path}"
            )
        return DataSelection(
            mat_path=mat_path.resolve(),
            csv_path=csv_path,
            reason="使用指定 CSV，並自動配對同目錄的 MAT。",
            candidates=[],
        )

    mats = list(repo_root.rglob("PSF_fitted_2D_FOVstack.mat"))
    csvs = list(repo_root.rglob("batch_results.csv"))
    if not mats or not csvs:
        raise FileNotFoundError("找不到 Whole-FOV 所需的 .mat 或 .csv 輸出。")

    candidate_rows: list[dict[str, Any]] = []
    best: tuple[float, Path, Path] | None = None
    for mat_path in mats:
        sibling_csv = mat_path.with_name("batch_results.csv")
        if sibling_csv.exists():
            csv_path = sibling_csv
        else:
            csv_path = min(csvs, key=lambda p: abs(p.stat().st_mtime - mat_path.stat().st_mtime))

        mat_mtime = mat_path.stat().st_mtime
        csv_mtime = csv_path.stat().st_mtime
        score = 0.0
        if csv_path.parent == mat_path.parent:
            score += 1000
        score += min(mat_path.stat().st_size / 1024.0, 2000)
        score += min(csv_path.stat().st_size / 256.0, 500)
        score += (mat_mtime + csv_mtime) / 1e7
        candidate_rows.append(
            {
                "mat_path": str(mat_path),
                "csv_path": str(csv_path),
                "score": round(score, 2),
                "mat_mtime": pd.Timestamp.fromtimestamp(mat_mtime),
                "csv_mtime": pd.Timestamp.fromtimestamp(csv_mtime),
            }
        )
        if best is None or score > best[0]:
            best = (score, mat_path, csv_path)

    assert best is not None
    reason = "優先選擇同目錄成對輸出，其次考慮檔案完整度與更新時間。"
    return DataSelection(
        mat_path=best[1].resolve(),
        csv_path=best[2].resolve(),
        reason=reason,
        candidates=candidate_rows,
    )


def load_core_arrays(mat_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    data = loadmat(mat_path)

    def _read(name: str) -> np.ndarray:
        if name not in data:
            raise KeyError(f"{mat_path} 缺少欄位: {name}")
        return np.asarray(data[name], dtype=float)

    psf_grid = _read("psf_grid")
    coef_grid = _read("coef_grid")
    fval_map = _read("fval_map")
    iterations_map = _read("iterations_map")
    return psf_grid, coef_grid, fval_map, iterations_map


def validate_dataset_consistency(
    psf_grid: np.ndarray,
    fval_map: np.ndarray,
    iterations_map: np.ndarray,
    batch_df: pd.DataFrame,
) -> None:
    errors: list[str] = []
    if psf_grid.ndim != 4:
        errors.append(f"`psf_grid` 必須是 4D，目前為 {psf_grid.ndim}D。")
    else:
        expected_shape = (psf_grid.shape[2], psf_grid.shape[3])
        if fval_map.shape != expected_shape:
            errors.append(
                f"`fval_map.shape` 應為 {expected_shape}，目前為 {fval_map.shape}。"
            )
        if iterations_map.shape != expected_shape:
            errors.append(
                f"`iterations_map.shape` 應為 {expected_shape}，目前為 {iterations_map.shape}。"
            )
        expected_rows = expected_shape[0] * expected_shape[1]
        if len(batch_df) != expected_rows:
            errors.append(
                f"`batch_results.csv` 筆數應為 {expected_rows}，目前為 {len(batch_df)}。"
            )
    if errors:
        joined = " ".join(errors)
        raise ValueError(f"資料一致性檢查失敗：{joined}")


def normalize_axes_grid(axes: Any, rows: int, cols: int) -> np.ndarray:
    if rows == 1 and cols == 1:
        return np.asarray([[axes]], dtype=object)
    if rows == 1:
        return np.asarray([axes], dtype=object)
    if cols == 1:
        return np.asarray([[ax] for ax in np.ravel(axes)], dtype=object)
    return np.asarray(axes, dtype=object)


def render_montage(psf_grid: np.ndarray, output_path: Path, normalize_each: bool, log_scale: bool) -> None:
    rows, cols = psf_grid.shape[2], psf_grid.shape[3]
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 1.3, rows * 1.3), constrained_layout=True)
    axes = normalize_axes_grid(axes, rows, cols)
    vmax = None if normalize_each else float(np.max(psf_grid))
    for row in range(rows):
        for col in range(cols):
            ax = axes[row, col]
            tile = np.asarray(psf_grid[:, :, row, col], dtype=float)
            if normalize_each and tile.max() > 0:
                tile = tile / tile.max()
            if log_scale:
                tile = np.log1p(tile)
            ax.imshow(tile, cmap="magma", origin="lower", vmin=0, vmax=vmax)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(f"R{row+1}C{col+1}", fontsize=7)
    title = "Whole-FOV PSF montage"
    if log_scale:
        title += " (normalized/log)"
    fig.suptitle(title, fontsize=14)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def render_representative_comparison(psf_grid: np.ndarray, output_path: Path) -> list[dict[str, Any]]:
    rows, cols = psf_grid.shape[2], psf_grid.shape[3]
    positions = [
        ("中心位置", (rows // 2, cols // 2)),
        ("邊緣位置", (rows // 2, 0 if cols == 1 else cols - 1)),
        ("角落位置", (0, 0)),
    ]

    fig, axes = plt.subplots(len(positions), 2, figsize=(10, 10), constrained_layout=True)
    representatives: list[dict[str, Any]] = []
    for idx, (label, (row, col)) in enumerate(positions):
        psf = np.asarray(psf_grid[:, :, row, col], dtype=float)
        peak = float(psf.max())
        norm = psf / peak if peak > 0 else psf
        center_y, center_x = np.array(norm.shape) // 2
        x_profile = norm[center_y, :]
        y_profile = norm[:, center_x]
        width_x, width_y = second_moment_width(norm)

        ax_img, ax_line = axes[idx]
        im = ax_img.imshow(norm, cmap="magma", origin="lower")
        ax_img.set_title(f"{label} (R{row+1}, C{col+1})")
        ax_img.set_xticks([])
        ax_img.set_yticks([])
        fig.colorbar(im, ax=ax_img, fraction=0.046, pad=0.04)

        ax_line.plot(x_profile, label="X 剖面", color="#c44e52", linewidth=2)
        ax_line.plot(y_profile, label="Y 剖面", color="#4c72b0", linewidth=2)
        ax_line.set_ylim(0, 1.05)
        ax_line.set_title(f"{label} 剖面")
        ax_line.set_xlabel("像素")
        ax_line.set_ylabel("正規化強度")
        ax_line.grid(alpha=0.25)
        ax_line.legend(frameon=False)

        representatives.append(
            {
                "label": label,
                "row": row + 1,
                "col": col + 1,
                "peak": peak,
                "width_x": width_x,
                "width_y": width_y,
            }
        )

    fig.suptitle("代表位置 PSF 比較", fontsize=15)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return representatives


def render_heatmap(fval_map: np.ndarray, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 5.4), constrained_layout=True)
    im = ax.imshow(fval_map, cmap="viridis", origin="upper")
    for row in range(fval_map.shape[0]):
        for col in range(fval_map.shape[1]):
            ax.text(col, row, f"{fval_map[row, col]:.0f}", ha="center", va="center", color="white", fontsize=6)
    ax.set_title("Whole-FOV fval heatmap")
    ax.set_xlabel("FOV column")
    ax.set_ylabel("FOV row")
    fig.colorbar(im, ax=ax, label="fval")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def second_moment_width(psf: np.ndarray) -> tuple[float, float]:
    y_idx, x_idx = np.indices(psf.shape)
    total = float(psf.sum())
    if total <= 0:
        return 0.0, 0.0
    x_mean = float((psf * x_idx).sum() / total)
    y_mean = float((psf * y_idx).sum() / total)
    width_x = math.sqrt(max(float((psf * (x_idx - x_mean) ** 2).sum() / total), 0.0))
    width_y = math.sqrt(max(float((psf * (y_idx - y_mean) ** 2).sum() / total), 0.0))
    return width_x, width_y


def build_summary_stats(
    fval_map: np.ndarray,
    iterations_map: np.ndarray,
    psf_grid: np.ndarray,
    representatives: list[dict[str, Any]],
    batch_df: pd.DataFrame,
) -> pd.DataFrame:
    peaks = np.max(psf_grid, axis=(0, 1))
    widths = np.zeros((psf_grid.shape[2], psf_grid.shape[3], 2), dtype=float)
    for row in range(psf_grid.shape[2]):
        for col in range(psf_grid.shape[3]):
            width_x, width_y = second_moment_width(psf_grid[:, :, row, col])
            widths[row, col, 0] = width_x
            widths[row, col, 1] = width_y

    rows = []
    for name, values in [
        ("fval", fval_map.ravel()),
        ("iterations_map", iterations_map.ravel()),
        ("peak", peaks.ravel()),
        ("width_x", widths[:, :, 0].ravel()),
        ("width_y", widths[:, :, 1].ravel()),
    ]:
        rows.append(summary_row(name, values))

    if "seconds" in batch_df.columns:
        rows.append(summary_row("seconds", batch_df["seconds"].to_numpy(dtype=float)))

    rep_df = pd.DataFrame(representatives)
    for _, rep in rep_df.iterrows():
        rows.append(
            {
                "metric": f"{rep['label']}_peak",
                "mean": rep["peak"],
                "std": 0.0,
                "min": rep["peak"],
                "max": rep["peak"],
            }
        )
        rows.append(
            {
                "metric": f"{rep['label']}_width_xy_mean",
                "mean": float((rep["width_x"] + rep["width_y"]) / 2.0),
                "std": 0.0,
                "min": float(min(rep["width_x"], rep["width_y"])),
                "max": float(max(rep["width_x"], rep["width_y"])),
            }
        )
    return pd.DataFrame(rows)


def summary_row(metric: str, values: np.ndarray) -> dict[str, float | str]:
    arr = np.asarray(values, dtype=float)
    return {
        "metric": metric,
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def build_inventory_markdown(selection: DataSelection, batch_df: pd.DataFrame, psf_grid: np.ndarray) -> str:
    lines = [
        "# 資料盤點",
        "",
        "## 採用資料",
        "",
        f"- PSF stack：`{selection.mat_path}`",
        f"- 批次摘要：`{selection.csv_path}`",
        f"- 選擇原則：{selection.reason}",
        "",
        "## 資料完整性",
        "",
        f"- `psf_grid` 尺寸：`{tuple(psf_grid.shape)}`",
        f"- FOV 格點數：`{psf_grid.shape[2]} x {psf_grid.shape[3]}`",
        f"- `batch_results.csv` 筆數：`{len(batch_df)}`",
    ]
    if selection.candidates:
        lines.extend(
            [
                "",
                "## 掃描候選",
                "",
                "| MAT | CSV | score |",
                "|---|---|---:|",
            ]
        )
        for item in selection.candidates:
            lines.append(
                f"| `{item['mat_path']}` | `{item['csv_path']}` | {item['score']} |"
            )
    lines.extend(
        [
            "",
            "## 判讀",
            "",
            "- 目前掃描到的 Whole-FOV 結果為成對 `.mat` 與 `.csv`，足以產出 montage、代表位置比較、fval heatmap 與簡表。",
            "- 若後續出現更新的 Whole-FOV 結果，可直接重新執行此腳本，會再次依同目錄配對、完整度與時間排序重新挑選。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_analysis_summary(
    selection: DataSelection,
    stats_df: pd.DataFrame,
    representatives: list[dict[str, Any]],
    batch_df: pd.DataFrame,
    psf_grid: np.ndarray,
) -> str:
    fval_row = stats_df.loc[stats_df["metric"] == "fval"].iloc[0]
    iter_row = stats_df.loc[stats_df["metric"] == "iterations_map"].iloc[0]
    seconds_row = stats_df.loc[stats_df["metric"] == "seconds"].iloc[0] if "seconds" in stats_df["metric"].values else None
    center = next(rep for rep in representatives if rep["label"] == "中心位置")
    edge = next(rep for rep in representatives if rep["label"] == "邊緣位置")
    corner = next(rep for rep in representatives if rep["label"] == "角落位置")

    lines = [
        "# Whole-FOV PSF 分析摘要",
        "",
        "## 分析範圍",
        "",
        f"- 本次分析採用 `{selection.mat_path.name}` 與 `{selection.csv_path.name}`，針對 `psf_grid`、`fval_map` 與 `iterations_map` 生成報告型圖表。",
        f"- FOV 版圖為 `{psf_grid.shape[2]} x {psf_grid.shape[3]}`，可直接反映全視野擬合後的 PSF 形貌分布。",
        "",
        "## 主要觀察",
        "",
        f"- `fval` 平均為 `{fval_row['mean']:.2f}`，標準差 `{fval_row['std']:.2f}`，範圍 `{fval_row['min']:.2f}` 到 `{fval_row['max']:.2f}`，表示全視野擬合品質存在可觀的空間差異。",
        f"- `iterations` 平均為 `{iter_row['mean']:.1f}` 次；"
        + (f"單張計算時間平均 `{seconds_row['mean']:.2f}` 秒。" if seconds_row is not None else "本次未提供逐張耗時資訊。"),
        f"- 中心位置 (R{center['row']}, C{center['col']}) 的二階矩寬度約為 `X={center['width_x']:.2f}`, `Y={center['width_y']:.2f}`；"
        f"邊緣位置與角落位置分別為 `({edge['width_x']:.2f}, {edge['width_y']:.2f})` 與 `({corner['width_x']:.2f}, {corner['width_y']:.2f})`。",
        "- 代表位置比較圖提供 2D PSF 與中心 X/Y 剖面，可快速判讀是否有視野邊界變寬、拉伸或非對稱現象。",
        "",
        "## 建議放入報告的圖表",
        "",
        "- `figures/psf_montage.png`：呈現全視野 PSF 整體分布。",
        "- `figures/psf_montage_log_normalized.png`：壓縮動態範圍後更容易比較側瓣與外圍擴散。",
        "- `figures/psf_representative_comparison.png`：用中心、邊緣、角落三個代表點說明視野位置差異。",
        "- `figures/fval_heatmap.png`：對應擬合誤差在視野上的空間變化。",
        "",
        "## 備註",
        "",
        f"- `batch_results.csv` 共 `{len(batch_df)}` 筆，與 MAT 內 `fval_map` / `iterations_map` 可互相對照。",
        "- 目前資料已足以形成 1 到 2 頁研究成果報告的核心圖文；若需要更完整因果解釋，仍需回到光學與 Zernike 係數層級做補充。",
    ]
    return "\n".join(lines) + "\n"


def build_report_draft(
    stats_df: pd.DataFrame,
    representatives: list[dict[str, Any]],
    psf_grid: np.ndarray,
) -> str:
    fval_row = stats_df.loc[stats_df["metric"] == "fval"].iloc[0]
    iter_row = stats_df.loc[stats_df["metric"] == "iterations_map"].iloc[0]
    center = next(rep for rep in representatives if rep["label"] == "中心位置")
    edge = next(rep for rep in representatives if rep["label"] == "邊緣位置")
    corner = next(rep for rep in representatives if rep["label"] == "角落位置")

    paragraphs = [
        (
            "本研究以 Whole-FOV PSF 擬合結果為基礎，針對 "
            f"{psf_grid.shape[2]} x {psf_grid.shape[3]} 視野格點建立全視野 PSF 分布圖與擬合品質摘要。"
            "由 montage 圖可見，各位置的 PSF 主峰與外圍擴散並非完全一致，顯示系統在視野範圍內存在可量測的空間變異。"
            "此結果可作為後續報告中說明視野均勻性與像差分布的直接證據。"
        ),
        (
            f"就整體擬合品質而言，fval 平均為 {fval_row['mean']:.2f}，標準差為 {fval_row['std']:.2f}，"
            f"最低與最高分別為 {fval_row['min']:.2f} 與 {fval_row['max']:.2f}。"
            f"迭代次數平均約為 {iter_row['mean']:.1f} 次，表示大多數格點皆能在相近的優化步數內完成收斂，"
            "但不同區域之間仍可觀察到誤差分布起伏，適合以 heatmap 呈現其空間位置關係。"
        ),
        (
            f"代表位置比較方面，中心位置的二階矩寬度約為 X={center['width_x']:.2f}、Y={center['width_y']:.2f}；"
            f"邊緣位置為 X={edge['width_x']:.2f}、Y={edge['width_y']:.2f}；角落位置則為 X={corner['width_x']:.2f}、Y={corner['width_y']:.2f}。"
            "配合正規化 X/Y 剖面可進一步看出，視野外圍是否出現展寬、方向性拉伸或側瓣差異，"
            "因此能用少量圖幅清楚支撐『中心與非中心位置 PSF 形貌不同』的觀察結論。"
        ),
        (
            "綜合而言，本次分析已建立一組可直接放入研究成果報告的最小圖文組合，包含全視野 PSF montage、"
            "代表位置比較圖、fval heatmap 與簡要統計表。這些輸出足以支撐對擬合穩定度與視野位置差異的描述，"
            "並可作為後續連接反捲積表現或光學像差討論的前導證據。"
        ),
    ]
    return "\n\n".join(paragraphs) + "\n"


def ensure_readmes(helper_root: Path) -> None:
    readme_tw = helper_root / "README_TW.md"
    if not readme_tw.exists():
        readme_tw.write_text("", encoding="utf-8")


def main() -> None:
    args = parse_args()
    configure_matplotlib_fonts()
    ensure_readmes(args.helper_root)
    result = run_analysis(
        repo_root=args.repo_root,
        helper_root=args.helper_root,
        output_root=args.output_root,
        preferred_mat=args.mat_path,
        preferred_csv=args.csv_path,
    )
    print(f"完成分析: {result.selected_mat_path}")
    print(f"完成分析: {result.selected_csv_path}")
    print(f"輸出摘要: {result.summary_report_path}")
    print(f"輸出草稿: {result.report_draft_path}")


if __name__ == "__main__":
    main()
