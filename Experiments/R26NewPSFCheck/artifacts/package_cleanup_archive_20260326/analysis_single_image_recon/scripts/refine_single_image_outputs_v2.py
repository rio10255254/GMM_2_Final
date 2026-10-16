from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.patches as patches
import numpy as np

import analysis_core


ROOT = Path(__file__).resolve().parents[2]

ROI_LABELS = [
    ("main_edge", "A", "主要邊界"),
    ("defect", "B", "缺陷區"),
    ("weak_edge", "C", "弱邊界"),
    ("background", "D", "背景區"),
]

ROI_COLORS = {
    "A": "#2F5597",
    "B": "#C55A11",
    "C": "#548235",
    "D": "#7F6000",
}


def load_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).with_name("analysis_config.json")
    return json.loads(config_path.read_text(encoding="utf-8"))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_metrics_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    parsed: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {"image": row["image"]}
        for key, value in row.items():
            if key == "image":
                continue
            item[key] = float(value)
        parsed.append(item)
    return parsed


def _prepare_reference(source_selection: dict[str, Any]) -> dict[str, Any]:
    ref = source_selection["reference_summary"]
    return {
        "cx": float(ref["cx"]),
        "cy": float(ref["cy"]),
        "inner_edge_r": float(ref["inner_edge_r"]),
        "outer_edge_r": float(ref["outer_edge_r"]),
        "peak_r": float(ref["peak_r"]),
    }


def _prepare_rois(roi_selection: dict[str, Any]) -> dict[str, tuple[int, int, int, int]]:
    return {
        key: tuple(int(v) for v in value)
        for key, value in roi_selection["rois"].items()
    }


def _rows_by_image(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["image"]: row for row in rows}


def _title_case_metric_name(name: str) -> str:
    mapping = {
        "HF_ratio": "HF_ratio",
        "checkerboard_ratio": "checkerboard_ratio",
        "edge_continuity_ratio": "edge_continuity_ratio",
        "ring_thickness_std_px": "ring_thickness_std_px",
    }
    return mapping.get(name, name)


def render_overall_compare_v2(
    raw: np.ndarray,
    recon: np.ndarray,
    rois: dict[str, tuple[int, int, int, int]],
    config: dict[str, Any],
    out_path: Path,
) -> None:
    vmin, vmax = config["gray_display"]
    fig, axes = analysis_core.plt.subplots(1, 2, figsize=(12.2, 7.2))
    for ax, title, image in zip(axes, ["RAW", "R26"], [raw, recon]):
        ax.imshow(image, cmap="gray", vmin=vmin, vmax=vmax)
        ax.set_title(title, fontweight="bold")
        for key, letter, label in ROI_LABELS:
            x, y, w, h = rois[key]
            color = ROI_COLORS[letter]
            ax.add_patch(
                patches.Rectangle(
                    (x, y),
                    w,
                    h,
                    linewidth=2.0,
                    edgecolor=color,
                    facecolor="none",
                )
            )
            ax.text(
                x + 8,
                y + 18,
                f"{letter}",
                color="white",
                fontsize=12,
                fontweight="bold",
                bbox={
                    "boxstyle": "round,pad=0.18",
                    "facecolor": color,
                    "edgecolor": color,
                    "alpha": 0.95,
                },
            )
        ax.axis("off")
    fig.suptitle("圖 1 單張影像整體比較與 ROI 對應位置", fontsize=16, fontweight="bold")
    fig.text(0.5, 0.015, "ROI A-D 與圖 2 完整對應；所有影像均使用相同灰階範圍與顯示尺度。", ha="center", fontsize=11)
    fig.savefig(out_path)
    analysis_core.plt.close(fig)


def render_roi_compare_v2(
    raw: np.ndarray,
    recon: np.ndarray,
    rois: dict[str, tuple[int, int, int, int]],
    config: dict[str, Any],
    out_path: Path,
) -> None:
    vmin, vmax = config["gray_display"]
    fig, axes = analysis_core.plt.subplots(len(ROI_LABELS), 2, figsize=(7.8, 13.8))
    for row, (key, letter, label) in enumerate(ROI_LABELS):
        color = ROI_COLORS[letter]
        raw_crop = analysis_core._crop(raw, rois[key])
        recon_crop = analysis_core._crop(recon, rois[key])
        for col, (image_label, crop) in enumerate([("RAW", raw_crop), ("R26", recon_crop)]):
            ax = axes[row, col]
            ax.imshow(crop, cmap="gray", vmin=vmin, vmax=vmax)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(image_label, fontweight="bold")
            ax.text(
                0.02,
                0.96,
                f"{letter} {label}" if col == 0 else label,
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=12,
                fontweight="bold",
                color="white",
                bbox={
                    "boxstyle": "round,pad=0.22",
                    "facecolor": color,
                    "edgecolor": color,
                    "alpha": 0.92,
                },
            )
    fig.suptitle("圖 2 代表性 ROI 放大比較（RAW vs R26）", fontsize=16, fontweight="bold")
    fig.text(0.5, 0.015, "A 主要邊界、B 缺陷區、C 弱邊界、D 背景區；各 ROI 使用相同裁切座標與灰階範圍。", ha="center", fontsize=11)
    fig.savefig(out_path)
    analysis_core.plt.close(fig)


def render_edge_profiles_v2(plot_data: dict[str, Any], rows_by_image: dict[str, dict[str, Any]], out_path: Path) -> None:
    fig, axes = analysis_core.plt.subplots(1, 2, figsize=(13.6, 5.3), sharey=False)
    panel_defs = [
        ("main_edge", "A 主要邊界法線剖面", "edge_width_main_px", "max_slope_main"),
        ("weak_edge", "C 弱邊界法線剖面", "edge_width_weak_px", "max_slope_weak"),
    ]
    for ax, (key, title, width_key, slope_key) in zip(axes, panel_defs):
        entry = plot_data[key]
        ax.plot(entry["positions"], entry["raw_profile"], color="#4C78A8", lw=2.2, label="RAW")
        ax.plot(entry["positions"], entry["r26_profile"], color="#F58518", lw=2.2, label="R26")
        ax.set_title(title, fontweight="bold")
        ax.set_xlabel("相對邊界法線位置 (px)")
        ax.set_ylabel("平均灰階值")
        ax.grid(alpha=0.25)
        ax.legend(loc="upper right")
        text = "\n".join(
            [
                f"10–90 轉換寬度: {rows_by_image['RAW'][width_key]:.2f} -> {rows_by_image['R26'][width_key]:.2f} px",
                f"最大斜率: {rows_by_image['RAW'][slope_key]:.2f} -> {rows_by_image['R26'][slope_key]:.2f}",
            ]
        )
        ax.text(
            0.02,
            0.04,
            text,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=9.8,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.88},
        )
    fig.suptitle("圖 3 邊界灰階剖面與 10–90 轉換寬度", fontsize=16, fontweight="bold")
    fig.savefig(out_path)
    analysis_core.plt.close(fig)


def render_frequency_validation_v2(
    fft_plot_data: dict[str, Any],
    rows_by_image: dict[str, dict[str, Any]],
    config: dict[str, Any],
    out_path: Path,
) -> None:
    raw = fft_plot_data["RAW"]
    recon = fft_plot_data["R26"]
    vmax = max(float(np.percentile(raw["log_magnitude"], 99)), float(np.percentile(recon["log_magnitude"], 99)))
    fig, axes = analysis_core.plt.subplots(2, 2, figsize=(12.0, 9.0))

    im0 = axes[0, 0].imshow(raw["log_magnitude"], cmap="magma", vmin=0, vmax=vmax)
    axes[0, 0].set_title("RAW 二維頻譜幅值（FFT log magnitude）", fontweight="bold")
    axes[0, 0].axis("off")
    fig.colorbar(im0, ax=axes[0, 0], fraction=0.046, pad=0.04)

    im1 = axes[0, 1].imshow(recon["log_magnitude"], cmap="magma", vmin=0, vmax=vmax)
    axes[0, 1].set_title("R26 二維頻譜幅值（FFT log magnitude）", fontweight="bold")
    axes[0, 1].axis("off")
    fig.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)

    raw_x = raw["radial_x"][1:] if len(raw["radial_x"]) > 1 else raw["radial_x"]
    raw_y = raw["radial_curve"][1:] if len(raw["radial_curve"]) > 1 else raw["radial_curve"]
    recon_x = recon["radial_x"][1:] if len(recon["radial_x"]) > 1 else recon["radial_x"]
    recon_y = recon["radial_curve"][1:] if len(recon["radial_curve"]) > 1 else recon["radial_curve"]
    hf_lo, hf_hi = config["fft"]["radial_hf_band"]
    axes[1, 0].axvspan(hf_lo, hf_hi, color="#D9D9D9", alpha=0.35, lw=0)
    axes[1, 0].semilogy(raw_x, raw_y + 1e-6, color="#4C78A8", lw=2.2, label="RAW")
    axes[1, 0].semilogy(recon_x, recon_y + 1e-6, color="#F58518", lw=2.2, label="R26")
    axes[1, 0].set_title("徑向平均頻譜（radial average spectrum）", fontweight="bold")
    axes[1, 0].set_xlabel("正規化徑向頻率")
    axes[1, 0].set_ylabel("正規化功率（log）")
    axes[1, 0].set_xlim(0.0, 0.7)
    axes[1, 0].grid(alpha=0.25)
    axes[1, 0].legend(loc="upper right")

    axes[1, 1].axis("off")
    text = "\n".join(
        [
            f"HF_ratio（固定高頻帶能量比，r={hf_lo:.2f}–{hf_hi:.2f}）: {rows_by_image['RAW']['HF_ratio']:.4f} -> {rows_by_image['R26']['HF_ratio']:.4f}",
            f"checkerboard_ratio（corner energy 指標）: {rows_by_image['RAW']['checkerboard_ratio']:.4f} -> {rows_by_image['R26']['checkerboard_ratio']:.4f}",
            "",
            "本圖的定位：",
            "- 用來檢查是否出現不自然 checkerboard / 假高頻副作用。",
            "- 用來說明頻帶重分配，以及背景高頻與噪聲成分受抑。",
            "",
            "解讀重點：",
            "- checkerboard ratio 未上升，未見明顯棋盤格型假高頻污染。",
            "- HF_ratio 顯著下降，較適合解讀為固定高頻帶能量受抑與頻帶更集中，",
            "  不宜直接延伸成整體細節同步增強的結論。",
            "- 因此頻域結果屬於輔助證據，用來支持改善可信，而非作為細節強化程度的直接證明。",
        ]
    )
    axes[1, 1].text(
        0.02,
        0.98,
        text,
        ha="left",
        va="top",
        fontsize=10.4,
        bbox={"boxstyle": "round,pad=0.42", "facecolor": "white", "alpha": 0.92},
    )
    fig.suptitle("圖 4 頻域驗證：假高頻排除與頻帶重分配", fontsize=16, fontweight="bold")
    fig.savefig(out_path)
    analysis_core.plt.close(fig)


def build_metrics_report_v2(rows: list[dict[str, Any]], config: dict[str, Any]) -> str:
    headers = list(rows[0].keys())
    lines = ["# 單張重建總表 v2", "", "|" + "|".join(headers) + "|", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        values = []
        for header in headers:
            value = row[header]
            if isinstance(value, (float, np.floating)):
                if math.isnan(float(value)):
                    values.append("not reliable")
                else:
                    values.append(f"{float(value):.4f}")
            else:
                values.append(str(value))
        lines.append("|" + "|".join(values) + "|")

    hf_lo, hf_hi = config["fft"]["radial_hf_band"]
    lines.extend(
        [
            "",
            "## 結果解讀重點",
            "1. 邊界集中化是主證據。`edge_width_main_px`、`edge_width_weak_px` 明顯下降，且 `max_slope_main`、`max_slope_weak` 明顯上升，這是本報告最核心、最穩定的主結論。",
            "2. CNR 提升需結合背景抑噪一起解讀。`CNR_main` 與 `CNR_weak` 的上升，不應單獨寫成結構訊號變強；更合理的解讀是邊界集中化，加上 `background_std` 與 `background_grad_p95` 顯著下降，表示局部對比改善來自邊界集中與背景抑噪的共同作用。",
            f"3. 頻域主要用來排除假高頻與說明頻帶集中。`HF_ratio` 在本流程中定義為固定頻帶 `r={hf_lo:.2f}–{hf_hi:.2f}` 的能量比，較接近固定高頻帶/噪聲帶能量佔比，不宜直接解讀成有效細節量；`checkerboard_ratio` 未上升，因此頻域結果主要作為未見明顯假高頻副作用的輔助證據。",
            "4. 幾何 proxy 僅保守支持應用價值。`ring_thickness_std_px` 應作為較穩健的主幾何 proxy；`edge_continuity_ratio` 受 threshold 與 edge rule 影響較大，應降為輔助支持，不宜作為 headline 指標。",
        ]
    )
    return "\n".join(lines)


def build_result_draft_v2(rows_by_image: dict[str, dict[str, Any]], config: dict[str, Any], geo_log: dict[str, Any]) -> str:
    raw = rows_by_image["RAW"]
    r26 = rows_by_image["R26"]
    hf_lo, hf_hi = config["fft"]["radial_hf_band"]
    cb = float(config["fft"]["checkerboard_corner_threshold"])
    return "\n".join(
        [
            "# 單張影像重建分析結果草稿 v2",
            "",
            "## 主結果分析正文",
            (
                f"以 RAW 與 R26 的單張比較結果來看，最強的主證據來自邊界剖面量化。主邊界的 `edge_width_main_px` 由 `{raw['edge_width_main_px']:.2f}` px "
                f"下降至 `{r26['edge_width_main_px']:.2f}` px，弱邊界的 `edge_width_weak_px` 由 `{raw['edge_width_weak_px']:.2f}` px 下降至 `{r26['edge_width_weak_px']:.2f}` px；"
                f"同時，主邊界 `max_slope_main` 由 `{raw['max_slope_main']:.2f}` 上升至 `{r26['max_slope_main']:.2f}`，弱邊界 `max_slope_weak` 由 `{raw['max_slope_weak']:.2f}` 上升至 `{r26['max_slope_weak']:.2f}`。"
                "這組結果可較安全地解讀為：R26 使原本較擴散的灰階轉換變得更集中、邊界轉換更陡，且此現象同時出現在主要邊界與弱邊界。"
            ),
            (
                f"局部對比指標方面，`CNR_main` 由 `{raw['CNR_main']:.2f}` 提升至 `{r26['CNR_main']:.2f}`，`CNR_weak` 由 `{raw['CNR_weak']:.2f}` 提升至 `{r26['CNR_weak']:.2f}`。"
                f"這個提升不能只解讀成結構訊號本身變強，而應結合背景抑噪一起理解：`background_std` 由 `{raw['background_std']:.4f}` 降至 `{r26['background_std']:.4f}`，"
                f"`background_grad_p95` 由 `{raw['background_grad_p95']:.4f}` 降至 `{r26['background_grad_p95']:.4f}`。因此，本研究較合理的寫法應是：局部對比改善來自邊界集中化與背景抑噪的共同作用，"
                "而不是靠背景惡化或單純銳化所換得的視覺效果。"
            ),
            "",
            "## 頻域圖的保守解讀正文",
            (
                f"頻域分析的角色應定位為輔助驗證，而不是主證據。`HF_ratio` 在本流程中的定義為固定頻帶能量比 `E(r={hf_lo:.2f}–{hf_hi:.2f}) / E(r=0.05–0.60)`，"
                f"其數值由 `{raw['HF_ratio']:.4f}` 降至 `{r26['HF_ratio']:.4f}`；`checkerboard_ratio` 的定義為 `|fx|, |fy| >= {cb:.2f}` 的 corner energy 比值，"
                f"其數值由 `{raw['checkerboard_ratio']:.4f}` 降至 `{r26['checkerboard_ratio']:.4f}`。依此結果，較保守且較合適的解讀是：未見明顯 checkerboard 或不自然高頻污染，"
                "且伴隨背景高頻與噪聲成分受抑、頻帶更集中。換言之，頻域結果主要是用來排除明顯副作用與支持改善可信，"
                "不宜直接延伸成整體細節同步增強的主結論，也不能把頻域當成細節強化程度的直接證明。"
            ),
            "",
            "## 幾何 proxy 的保守解讀正文",
            (
                f"幾何 proxy 層面中，較穩健的主指標應為 `ring_thickness_std_px`。其數值由 `{raw['ring_thickness_std_px']:.4f}` 下降至 `{r26['ring_thickness_std_px']:.4f}`，"
                "表示在固定 RAW 幾何參考下，R26 所對應的環狀厚度分布更一致，較適合用來支持邊界結構完整性提升。相較之下，`edge_continuity_ratio` 雖由 "
                f"`{raw['edge_continuity_ratio']:.4f}` 提升至 `{r26['edge_continuity_ratio']:.4f}`，但此指標明顯受 threshold、edge rule 與 valid angle 判定影響。"
                f"本次 valid angle 計數由 `{geo_log['valid_angle_counts']['RAW']}` 提升至 `{geo_log['valid_angle_counts']['R26']}`，方向雖正向，但較適合當作輔助支持，而非 headline 指標。"
                "因此，幾何層的建議寫法應是：geometry proxy 保守支持重建後的結構完整性較佳，顯示其對後續辨識或量測較有利；但本分析尚未直接證明實際量測精度提升。"
            ),
            "",
            "## 圖說建議",
            "圖 1：RAW 與 R26 的單張整體比較，並標示後續 ROI 分析所使用之 A–D 區域。整體觀察顯示，R26 在主要結構邊界與背景平坦區的表現與 RAW 存在一致方向的差異。",
            "圖 2：四類代表性 ROI 放大比較。A 為主要邊界、B 為缺陷區、C 為弱邊界、D 為背景區；所有 ROI 均使用相同座標、相同灰階範圍與相同裁切邏輯，以避免顯示尺度造成誤判。",
            "圖 3：主要邊界與弱邊界之灰階剖面比較，並以 10–90 轉換寬度與最大斜率量化邊界轉換。R26 在兩類邊界上皆呈現較窄的轉換寬度與較陡的灰階變化。",
            "圖 4：頻域驗證圖。此圖主要用來檢查是否出現明顯 checkerboard 或不自然高頻污染，並輔助說明頻帶重分配與背景高頻噪聲受抑，不宜直接作為細節強化程度的證明。",
            "",
            "## 最終結論建議寫法",
            (
                "綜合本單張分析結果，R26 相較於 RAW 在主要邊界與弱邊界上皆呈現更集中的灰階轉換與更陡的邊界剖面，這是本研究最強的主證據。"
                "局部對比指標的改善需結合背景波動與背景高梯度雜訊的同步下降一起解讀，因此較支持 R26 的改善並非單純銳化或放大雜訊所致。"
                "頻域結果未見明顯 checkerboard 或不自然高頻污染，且顯示背景高頻與噪聲成分受抑、頻帶更集中，可作為改善可信的輔助證據。"
                "此外，`ring_thickness_std_px` 的下降與 `edge_continuity_ratio` 的正向變化，亦保守支持重建後的結構完整性較佳，顯示其對後續辨識或量測較有利；"
                "但本分析仍不宜直接宣稱真實解析度提升，也不宜寫成量測精度已獲直接證明。"
            ),
        ]
    )


def build_revision_notes_v2(rows_by_image: dict[str, dict[str, Any]], config: dict[str, Any], geo_log: dict[str, Any]) -> str:
    raw = rows_by_image["RAW"]
    r26 = rows_by_image["R26"]
    hf_lo, hf_hi = config["fft"]["radial_hf_band"]
    cb = float(config["fft"]["checkerboard_corner_threshold"])
    inner_thr = geo_log["thresholds"]["inner_gradient_threshold"]
    outer_thr = geo_log["thresholds"]["outer_gradient_threshold"]
    return "\n".join(
        [
            "# revision_notes_v2",
            "",
            "## 本輪改了哪些圖",
            "- 新增 `01_overall_compare_raw_vs_r26_v2.png`：在全圖上補上 A/B/C/D ROI 框與標號，讓圖 1 和圖 2 能一一對應。",
            "- 新增 `02_roi_compare_raw_vs_r26_v2.png`：改成固定 A–D 四列、RAW/R26 兩欄的報告版布局，提升閱讀順序與對照性。",
            "- 新增 `03_edge_profiles_raw_vs_r26_v2.png`：保留主/弱邊界雙圖架構，但將標題與註解改為正式報告口徑，明寫 10–90 transition width。",
            "- 新增 `04_frequency_validation_raw_vs_r26_v2.png`：保留 2D FFT 與 radial spectrum 主體，但改寫整張圖的定位與註解方向，移除任何暗示「高頻整體提升」的表述。",
            "",
            "## 本輪改了哪些文字",
            "- 新增 `single_image_metrics_report_v2.md`：在表格後加入『結果解讀重點』，固定以邊界集中化、背景抑噪、頻域輔助驗證、幾何 proxy 保守支持的順序解讀。",
            "- 新增 `single_image_recon_result_draft_zh_v2.md`：重寫為可直接貼入報告的中文草稿，補上頻域與幾何 proxy 的保守解讀段落與圖說建議。",
            "- 新增 `revision_notes_v2.md`：明列本輪降權與保留的證據，避免圖、表、正文之間口徑漂移。",
            "",
            "## 指標定義與 ROI 是否更動",
            "- 本輪未更改任何 metric definition，未重選 ROI，未重新設計 band 或 threshold。",
            "- HF_ratio 仍使用固定頻帶 `r={:.2f}–{:.2f}`；checkerboard_ratio 仍使用 `|fx|, |fy| >= {:.2f}` 的 corner energy 定義。".format(hf_lo, hf_hi, cb),
            "- edge_continuity_ratio 仍使用 RAW 量測出的梯度 quantile threshold 作為 valid rule，實際門檻為 inner `{:.4f}`、outer `{:.4f}`。".format(inner_thr, outer_thr),
            "- 可在不改資料與不重挑 ROI 的前提下完成本輪修正；本輪只調整圖面、命名與解讀權重。",
            "",
            "## 哪些解讀被刻意弱化，為什麼",
            "- 弱化『高頻提升』『有效高頻增加』這類說法，因為目前 `HF_ratio` 由 `{:.4f}` 降至 `{:.4f}`，不支持把頻域寫成高頻全面增強。".format(raw["HF_ratio"], r26["HF_ratio"]),
            "- 弱化 `edge_continuity_ratio` 的 headline 地位，因為它依賴 threshold、valid angle 規則與 edge rule，語意上比 `ring_thickness_std_px` 更容易被挑毛病。",
            "- 弱化『背景未明顯惡化』這種保守但不準確的說法，改寫為背景波動與背景高梯度雜訊明顯下降，因為 `background_std` 與 `background_grad_p95` 的數值改善非常明確。",
            "",
            "## 哪些解讀被保留為主證據，為什麼",
            "- 保留 `edge_width_main_px`、`edge_width_weak_px`、`max_slope_main`、`max_slope_weak` 為最核心主證據，因為它們最直接對應『邊界變窄、變陡、變集中』這個研究主問題。",
            "- 保留 `CNR_main`、`CNR_weak`，但要求與 `background_std`、`background_grad_p95` 綁定解讀，因為對比改善明顯來自邊界集中化與背景抑噪的共同作用。",
            "- 保留 `ring_thickness_std_px` 作為較穩健的主幾何 proxy，因為它直接反映有效角度上環厚度的一致性，較不容易被單一門檻規則主導。",
            "",
            "## HF_ratio 在本報告中最終應被如何定位",
            "- `HF_ratio` 應被定位為固定高頻帶能量比或高頻/噪聲帶能量佔比的輔助指標，不應直接等同於有效細節量。",
            "- 在本報告中，`HF_ratio` 的用途是幫助說明頻帶重分配、背景高頻與噪聲成分受抑，以及避免把結果誤寫成『全面高頻增強』。",
            "",
            "## edge_continuity_ratio 在本報告中最終應被如何定位",
            "- `edge_continuity_ratio` 應被定位為幾何層的輔助支持指標，而非 headline 指標。",
            "- 正文若要提及，應同步註明其對 threshold / edge rule / annulus valid rule 較敏感，避免把它寫成已直接證明幾何量測能力提升。",
            "",
            "## 最終建議正文應主打哪些指標，避免主打哪些指標",
            "- 建議主打：`edge_width_main_px`、`edge_width_weak_px`、`max_slope_main`、`max_slope_weak`、`background_std`、`background_grad_p95`、`CNR_main`、`CNR_weak`、`ring_thickness_std_px`。",
            "- 建議降權：`HF_ratio`、`checkerboard_ratio`、`edge_continuity_ratio`；其中前兩者屬於排除副作用與支持改善可信的輔助證據，後者則是較敏感的幾何輔助支持。",
            "- 建議避免主打：『高頻提升』『細節全面增強』『已直接證明量測精度提升』。這些說法在目前資料下都過滿。",
            "",
            "## 是否重算數值",
            "- 本輪未發現需要修正的實作 bug，因此未重算官方表格數值，也未修改 CSV。",
            "- v2 圖面僅以相同輸入、相同 ROI、相同指標定義重繪，v2 文字則直接對齊既有 CSV 與 log 的數值與語意。",
        ]
    )


def generate_v2_artifacts(out_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    figures_dir = out_dir / "figures"
    tables_dir = out_dir / "tables"
    draft_dir = out_dir / "draft"
    logs_dir = out_dir / "logs"

    for path in [figures_dir, tables_dir, draft_dir, logs_dir]:
        analysis_core.ensure_dir(path)

    source_selection = _read_json(logs_dir / "source_selection.json")
    roi_selection = _read_json(logs_dir / "roi_selection.json")
    run_summary = _read_json(logs_dir / "run_summary.json")
    rows = _read_metrics_csv(tables_dir / "single_image_metrics.csv")
    rows_by_image = _rows_by_image(rows)

    raw_path = Path(source_selection["raw_path"])
    r26_path = Path(source_selection["r26_path"])
    raw = analysis_core.load_grayscale_image(raw_path)
    r26 = analysis_core.load_grayscale_image(r26_path)
    ref = _prepare_reference(source_selection)
    rois = _prepare_rois(roi_selection)

    _, plot_data, _ = analysis_core.compute_spatial_metrics(raw, r26, ref, rois, config)
    _, fft_plot_data = analysis_core.compute_fft_metrics(raw, r26, ref, config)

    overall_v2 = figures_dir / "01_overall_compare_raw_vs_r26_v2.png"
    roi_v2 = figures_dir / "02_roi_compare_raw_vs_r26_v2.png"
    profiles_v2 = figures_dir / "03_edge_profiles_raw_vs_r26_v2.png"
    frequency_v2 = figures_dir / "04_frequency_validation_raw_vs_r26_v2.png"
    report_v2 = tables_dir / "single_image_metrics_report_v2.md"
    draft_v2 = draft_dir / "single_image_recon_result_draft_zh_v2.md"
    revision_notes = out_dir / "revision_notes_v2.md"

    render_overall_compare_v2(raw, r26, rois, config, overall_v2)
    render_roi_compare_v2(raw, r26, rois, config, roi_v2)
    render_edge_profiles_v2(plot_data, rows_by_image, profiles_v2)
    render_frequency_validation_v2(fft_plot_data, rows_by_image, config, frequency_v2)

    report_v2.write_text(build_metrics_report_v2(rows, config), encoding="utf-8")
    draft_v2.write_text(build_result_draft_v2(rows_by_image, config, run_summary["geometry"]), encoding="utf-8")
    revision_notes.write_text(build_revision_notes_v2(rows_by_image, config, run_summary["geometry"]), encoding="utf-8")

    return {
        "figures": {
            "overall_v2": overall_v2,
            "roi_v2": roi_v2,
            "profiles_v2": profiles_v2,
            "frequency_v2": frequency_v2,
        },
        "report_v2": report_v2,
        "draft_v2": draft_v2,
        "revision_notes": revision_notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate second-round refined v2 outputs for RAW vs R26 analysis.")
    parser.add_argument("--out-dir", dest="out_dir", type=Path, default=ROOT / "analysis_single_image_recon")
    parser.add_argument("--config", dest="config_path", type=Path, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config_path)
    generate_v2_artifacts(args.out_dir, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
