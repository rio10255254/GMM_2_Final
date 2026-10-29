from __future__ import annotations

import csv
import json
import math
import re
import shutil
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT / 'PSF_Fitting'))
VE = ROOT / "quick_recalibration" / "validation_experiments"
OUT = ROOT / "quick_recalibration" / "presentation_assets_20260623_L0_L1"

FOLDERS = {
    "existing_results": OUT / "01_existing_result_figures",
    "processing": OUT / "02_current_experiment_target_and_processing",
    "round_examples": OUT / "03_current_round_examples",
    "charts": OUT / "04_generated_summary_charts",
    "raw_examples": OUT / "05_raw_paired_frame_examples",
    "source_data": OUT / "06_source_data_for_upload",
}

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
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

FONT_FAMILY = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "Segoe UI",
    "DejaVu Sans",
    "Arial",
    "sans-serif",
]


records: list[dict[str, str]] = []
source_records: list[dict[str, str]] = []


def ensure_dirs() -> None:
    for path in FOLDERS.values():
        path.mkdir(parents=True, exist_ok=True)
    for round_number in (1, 2, 3):
        (FOLDERS["round_examples"] / f"Round{round_number}_selected_FOVs").mkdir(
            parents=True, exist_ok=True
        )


def write_sidecar(
    image_path: Path,
    title: str,
    description: str,
    suggested_use: str,
    caution: str,
    original_path: str | Path | None = None,
) -> Path:
    sidecar = Path(str(image_path) + ".txt")
    lines = [
        f"圖名：{title}",
        "",
        "這張圖在講什麼：",
        textwrap.fill(description, width=78),
        "",
        "簡報可以怎麼用：",
        textwrap.fill(suggested_use, width=78),
        "",
        "使用時要注意：",
        textwrap.fill(caution, width=78),
    ]
    if original_path:
        lines += ["", f"原始來源：{original_path}"]
    sidecar.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sidecar


def add_record(
    category: str,
    image_path: Path,
    title: str,
    description: str,
    suggested_use: str,
    caution: str,
    original_path: str | Path | None = None,
) -> None:
    sidecar = write_sidecar(
        image_path, title, description, suggested_use, caution, original_path
    )
    records.append(
        {
            "category": category,
            "file_name": image_path.name,
            "asset_path": str(image_path),
            "sidecar_explanation_path": str(sidecar),
            "title": title,
            "plain_explanation": description,
            "suggested_slide_use": suggested_use,
            "caution": caution,
            "original_source_path": str(original_path) if original_path else "",
        }
    )


def copy_image(
    src: Path,
    dst: Path,
    category: str,
    title: str,
    description: str,
    suggested_use: str,
    caution: str,
    convert_to_png: bool = False,
) -> Path | None:
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    if convert_to_png or src.suffix.lower() == ".bmp":
        if dst.suffix.lower() != ".png":
            dst = dst.with_suffix(".png")
        Image.open(src).save(dst)
    else:
        shutil.copy2(src, dst)
    add_record(category, dst, title, description, suggested_use, caution, src)
    return dst


def use_chart_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "grid.color": TOKENS["grid"],
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": FONT_FAMILY,
            "axes.unicode_minus": False,
        },
    )
    plt.rcParams["font.sans-serif"] = FONT_FAMILY
    plt.rcParams["axes.unicode_minus"] = False


def add_chart_header(
    fig,
    ax,
    title: str,
    subtitle: str,
    title_width: int = 52,
    subtitle_width: int = 80,
) -> None:
    title_wrapped = textwrap.fill(title, width=title_width, break_long_words=False)
    subtitle_wrapped = textwrap.fill(
        subtitle, width=subtitle_width, break_long_words=False
    )
    title_lines = title_wrapped.count("\n") + 1
    subtitle_lines = subtitle_wrapped.count("\n") + 1
    ax.set_title("")
    fig.subplots_adjust(
        top=max(0.60, 0.86 - 0.05 * (title_lines - 1) - 0.035 * (subtitle_lines - 1))
    )
    left = ax.get_position().x0
    fig.text(
        left,
        0.985,
        title_wrapped,
        ha="left",
        va="top",
        fontsize=15,
        fontweight="semibold",
        color=TOKENS["ink"],
        linespacing=1.1,
    )
    fig.text(
        left,
        0.925 - 0.045 * (title_lines - 1),
        subtitle_wrapped,
        ha="left",
        va="top",
        fontsize=10.5,
        color=TOKENS["muted"],
        linespacing=1.18,
    )
    sns.despine(ax=ax)


def save_chart(fig, path: Path) -> Path:
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)
    return path


def read_gray(path: Path) -> Image.Image:
    return Image.open(path).convert("L")


def normalize_for_display(im: Image.Image) -> Image.Image:
    arr = np.array(im).astype(np.float32)
    lo, hi = np.percentile(arr, [1, 99])
    if hi <= lo:
        hi = lo + 1
    arr = np.clip((arr - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def save_panel(
    images: list[Image.Image],
    labels: list[str],
    path: Path,
    title: str,
    subtitle: str | None = None,
    cols: int | None = None,
    figsize: tuple[float, float] | None = None,
) -> Path:
    count = len(images)
    if cols is None:
        cols = count
    rows = math.ceil(count / cols)
    if figsize is None:
        figsize = (cols * 3.2, rows * 3.2 + 1.0)
    fig, axes = plt.subplots(rows, cols, figsize=figsize)
    axes = np.array(axes).reshape(rows, cols)
    for ax in axes.flat:
        ax.axis("off")
    for index, (im, label) in enumerate(zip(images, labels)):
        ax = axes.flat[index]
        ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(label, fontsize=11, color=TOKENS["ink"], pad=8)
        ax.axis("off")
    fig.subplots_adjust(top=0.86, wspace=0.04, hspace=0.18)
    fig.text(
        0.04,
        0.98,
        title,
        fontsize=15,
        fontweight="semibold",
        color=TOKENS["ink"],
        ha="left",
        va="top",
    )
    if subtitle:
        fig.text(
            0.04,
            0.935,
            subtitle,
            fontsize=10.5,
            color=TOKENS["muted"],
            ha="left",
            va="top",
        )
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=TOKENS["surface"])
    plt.close(fig)
    return path


def collect_existing_result_figures() -> None:
    existing = [
        (
            ROOT / "Crop_circle_FreqFiltered" / "Fits" / "fitted_psf_grid_crop31.png",
            FOLDERS["existing_results"] / "01_fitted_psf_grid_crop31.png",
            "PSF 擬合後的形狀總覽",
            "這張圖把擬合後得到的 PSF 形狀排成一個總覽。它不是單張原始照片，而是擬合結果的視覺化，適合讓聽眾先看到這次到底在估一個怎樣的光學模糊形狀。",
            "放在方法或結果開頭，當作「PSF 擬合結果長相」的代表圖。",
            "這張圖來自既有 PSF 擬合輸出，不是新 L1 三輪拍攝的統計圖。",
        ),
        (
            VE
            / "archive_L0_legacy_20260616"
            / "cross_set_results"
            / "outputs"
            / "fig_4sets_basin_scatter.png",
            FOLDERS["existing_results"] / "02_legacy_l0_basin_scatter.png",
            "舊 L0 重複擬合的分群結果",
            "這張散點圖顯示舊 L0 裡多次重複擬合後，結果會落在不同穩定區域。白話來說，同一批資料反覆擬合，不一定每次都停在完全同一個解，但會聚成幾個有規律的位置。",
            "用來說明為什麼需要做 L0：先看演算法自己重跑時會有多少自然波動。",
            "這是封存的舊 L0 結果，只能當概念與歷史參考，不能直接當新 L1 的判定圖。",
        ),
        (
            VE
            / "archive_L0_legacy_20260616"
            / "cross_set_results"
            / "outputs"
            / "fig_basin_alignment.png",
            FOLDERS["existing_results"] / "03_legacy_l0_basin_alignment.png",
            "舊 L0 分群對齊示意",
            "這張圖在說明一件很重要的事：不同批次的分群編號不一定能直接對上，要看它們在參數空間裡的位置。也就是說，不能只看第 1 群、第 2 群這種名字，要看實際落點。",
            "放在解釋分析方法時，說明為什麼舊資料需要先做群的位置對齊。",
            "這張圖是舊資料的方法說明，不代表新資料仍然有完全相同的分群門檻。",
        ),
        (
            VE
            / "archive_L0_legacy_20260616"
            / "cross_set_results"
            / "outputs"
            / "fig_centroid_distance_proof_v2.png",
            FOLDERS["existing_results"] / "04_legacy_l0_centroid_distance_proof_v2.png",
            "舊 L0 群內與群間距離證據圖",
            "這張圖把同一群內的距離與不同群之間的距離放在一起比較。重點是舊資料裡群內比較近、群間比較遠，所以當時的分群不是肉眼硬切，而是有距離證據支持。",
            "用來當「舊 L0 分群真的有分開」的證據圖。",
            "這是 v2 版本，比原始版本更適合簡報；但仍是舊 L0，不是新 L0/L1 的正式門檻。",
        ),
        (
            VE
            / "archive_L0_legacy_20260616"
            / "cross_set_results"
            / "outputs"
            / "fig_centroid_distance_proof.png",
            FOLDERS["existing_results"]
            / "05_legacy_l0_centroid_distance_proof_original.png",
            "舊 L0 群距離證據圖原始版",
            "這是上一張群內與群間距離證據圖的原始版本。內容方向相同，主要是保留以免之後想比較不同版本。",
            "通常簡報用 v2 就好；這張可以當備用圖或附錄圖。",
            "與 v2 重複度高，正式簡報不一定需要兩張都放。",
        ),
    ]
    for src, dst, title, desc, use, caution in existing:
        copy_image(src, dst, "既有擬合/舊 L0 結果圖", title, desc, use, caution)


def collect_processing_images() -> None:
    gt_dir = VE / "L0_newdata_round1" / "inputs_primary" / "GT"
    processing_imgs = [
        (
            gt_dir / "GT_901_original_with_blocks.bmp",
            FOLDERS["processing"] / "01_gt_original_with_center_blocks.png",
            "原始 GT：圓形目標中間有方塊",
            "這張是同一個圓形樣本的原始目標圖。可以清楚看到中心區域有方塊結構，這也是為什麼後面不能把整個中心都拿來硬擬合，而要把真正穩定的圓形邊界當成主要目標。",
            "放在問題說明：這次影像有點歪，而且中心方塊會干擾，所以擬合目標改成圓邊界。",
            "這張是目標圖，不是實際拍攝影像，也不是擬合結果。",
        ),
        (
            gt_dir / "GT_901_with_Block_proc.bmp",
            FOLDERS["processing"] / "02_gt_processed_center_filled.png",
            "處理後 GT：中心方塊被填平",
            "這張顯示中心干擾被處理後的目標圖。它的用意是讓擬合更專注在圓形輪廓，而不是被中心方塊拖著跑。",
            "放在方法流程，接在原始 GT 後面，說明處理前後差異。",
            "它是處理後的目標圖，不是新的實驗照片。",
        ),
        (
            gt_dir / "circle_edge_mask.bmp",
            FOLDERS["processing"] / "03_circle_edge_mask.png",
            "真正拿來看的圓形邊界遮罩",
            "白色的環就是分析時真正關心的區域。簡單講，這張圖把「我要讓擬合看哪裡」標出來：看圓邊界，不看中心方塊。",
            "非常適合放在方法頁，直接說明這次不是拿整張圖硬套，而是只讓圓邊界主導擬合。",
            "遮罩本身不是影像內容，而是一張告訴分析程式該看哪裡的輔助圖。",
        ),
        (
            VE
            / "L0_newdata_round1"
            / "inputs_primary"
            / "VisionTop_Circle_Round1_001.bmp",
            FOLDERS["processing"] / "04_prepared_input_round1_pos001.png",
            "新資料處理後輸入影像範例：Round1 第 1 格",
            "這張是新資料正式進入擬合前的處理後輸入影像。可以看到圓形邊界還在，中心干擾已經被弱化或填平，符合這次的擬合策略。",
            "放在資料處理流程最後，說明原始資料最後變成什麼樣子才送進擬合。",
            "這是處理後輸入，不是原始相機大圖，也不是擬合輸出。",
        ),
    ]
    for src, dst, title, desc, use, caution in processing_imgs:
        copy_image(
            src,
            dst,
            "新資料目標與前處理",
            title,
            desc,
            use,
            caution,
            convert_to_png=True,
        )

    legacy_crop_indices = [1, 31, 61, 91, 100]
    legacy_files = sorted((ROOT / "Crop_circle_FreqFiltered").glob("VisionTop_*.bmp"))
    legacy_by_suffix = {}
    for path in legacy_files:
        match = re.search(r"_(\d+)\.bmp$", path.name)
        if match:
            legacy_by_suffix[int(match.group(1))] = path
    for index in legacy_crop_indices:
        src = legacy_by_suffix.get(index)
        if not src:
            continue
        copy_image(
            src,
            FOLDERS["processing"] / f"05_legacy_reference_crop_{index:03d}.png",
            "舊資料參考裁切影像",
            f"舊資料參考裁切影像：編號 {index}",
            f"這張是舊資料夾裡保留下來的同一圓形樣本裁切影像，編號 {index}。它可以跟新資料一起放，幫聽眾理解這次用的樣本其實和過去的 GT 是同一類圓形目標。",
            "適合放在補充頁，說明新舊資料的樣本連續性。",
            "這是舊資料的影像，不是這次 Round1/2/3 的新拍攝。",
            convert_to_png=True,
        )


def collect_round_examples() -> None:
    fov_indices = [1, 6, 11, 56, 61, 66, 111, 116, 121]
    for round_number in (1, 2, 3):
        for index in fov_indices:
            src = (
                VE
                / f"L0_newdata_round{round_number}"
                / "inputs_primary"
                / f"VisionTop_Circle_Round{round_number}_{index:03d}.bmp"
            )
            row = (index - 1) // 11 + 1
            col = (index - 1) % 11 + 1
            copy_image(
                src,
                FOLDERS["round_examples"]
                / f"Round{round_number}_selected_FOVs"
                / f"round{round_number}_fov{index:03d}.png",
                "三輪拍攝的代表視野影像",
                f"Round{round_number} 第 {index} 格處理後影像",
                f"這張是第 {round_number} 次拍攝中，第 {index} 個視野位置的處理後輸入影像；它位在 11x11 視野切分中的第 {row} 列第 {col} 欄。這類圖可以用來說明這次不是只看中心，而是用整個視野中不同位置來檢查擬合穩定性。",
                "可放在附錄或方法頁，當作 11x11 視野切分後的代表位置影像。",
                "這是送入擬合前的處理後影像，不是原始相機大圖；Round1/2/3 是三次重複拍攝。",
                convert_to_png=True,
            )


def load_data() -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with open(VE / "L1_newdata" / "L1_newdata_summary.json", "r", encoding="utf-8") as f:
        l1 = json.load(f)
    rounds_df = pd.DataFrame(l1["summary"]["rounds"])
    fov_df = pd.DataFrame(l1["summary"]["fov_rows"])
    coef_df = pd.DataFrame(l1["summary"]["coef_rows"])
    paired_df = pd.read_csv(VE / "L1_paired_frame_check" / "paired_frame_metrics.csv")
    for col in ["round_number", "position_index", "row", "col"]:
        paired_df[col] = paired_df[col].astype(int)
    return l1, rounds_df, fov_df, coef_df, paired_df


def create_summary_charts(
    l1: dict,
    rounds_df: pd.DataFrame,
    fov_df: pd.DataFrame,
    coef_df: pd.DataFrame,
    paired_df: pd.DataFrame,
) -> None:
    use_chart_theme()

    chart_path = FOLDERS["charts"] / "chart_01_key_takeaways_scorecard.png"
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    ax.axis("off")
    fig.text(
        0.05,
        0.94,
        "新資料 L0/L1 實驗重點摘要",
        fontsize=20,
        fontweight="semibold",
        color=TOKENS["ink"],
        ha="left",
    )
    fig.text(
        0.05,
        0.895,
        "重點不是追求單一數字漂亮，而是確認三次拍攝的變化是否已經小到低於 L0 自己重跑的自然波動。",
        fontsize=11.5,
        color=TOKENS["muted"],
        ha="left",
    )
    items = [
        (
            "L0 自己重跑底噪",
            f"{rounds_df.loc[0, 'l0_clean_noise_median']:.5f}",
            "Round1，同一批資料重複擬合 15 次的中位波動",
        ),
        (
            "L1 主要判讀",
            l1["summary"]["status"],
            "三輪拍攝差異落在 L0 底噪內",
        ),
        (
            "L1 中位 abs-z",
            f"{l1['summary']['metrics']['readout_abs_z']['median']:.5f}",
            "遠低於警戒值 2，代表整體變化很小",
        ),
        (
            "L1 95% abs-z",
            f"{l1['summary']['metrics']['readout_abs_z']['p95']:.3f}",
            "大多數位置與係數仍在 L0 可接受範圍內",
        ),
        (
            "拍攝間散布",
            f"{l1['summary']['metrics']['readout_capture_std']['median']:.5f}",
            "三次拍攝彼此的中位差異",
        ),
        (
            "扣掉 L0 後淨變化",
            f"{l1['summary']['metrics']['readout_net_capture_std']['median']:.1f}",
            "中位數為 0，代表拍攝差異沒有超過自身底噪",
        ),
    ]
    box_w, box_h = 0.28, 0.20
    xs = [0.06, 0.37, 0.68]
    ys = [0.59, 0.31]
    for index, (label, value, note) in enumerate(items):
        x, y = xs[index % 3], ys[index // 3]
        rect = plt.Rectangle(
            (x, y),
            box_w,
            box_h,
            transform=fig.transFigure,
            facecolor="#FFFFFF",
            edgecolor="#D7DBE7",
            linewidth=1.0,
        )
        fig.patches.append(rect)
        fig.text(x + 0.02, y + 0.145, label, fontsize=11.5, color=TOKENS["muted"])
        fig.text(
            x + 0.02,
            y + 0.085,
            str(value),
            fontsize=21,
            fontweight="semibold",
            color=COLORS["blue"]["dark"],
        )
        fig.text(
            x + 0.02,
            y + 0.035,
            textwrap.fill(note, width=30),
            fontsize=9.5,
            color=TOKENS["ink"],
            linespacing=1.15,
        )
    fig.text(
        0.05,
        0.13,
        "讀法：如果 L1 的三次拍攝差異沒有大於 L0 自己重跑的底噪，就表示目前主要限制不是三次拍攝本身，而是擬合流程自己的自然波動。",
        fontsize=11,
        color=TOKENS["ink"],
        ha="left",
    )
    save_chart(fig, chart_path)
    add_record(
        "新畫的 L0/L1 統計圖",
        chart_path,
        "新資料 L0/L1 重點摘要",
        "這是一張給簡報用的總結圖，把最重要的幾個數字集中在同一頁。核心訊息是：新資料的 L1 三次拍攝差異，整體沒有超過 L0 自己重跑造成的自然波動。",
        "可以放在結果總結頁，讓聽眾先抓到結論。",
        "這張是從 JSON 摘要檔重畫的簡報圖，不是原始程式自動輸出的舊圖。",
        VE / "L1_newdata" / "L1_newdata_summary.json",
    )

    plot_df = rounds_df[
        ["round_name", "l0_clean_noise_median", "l0_clean_noise_mean"]
    ].melt("round_name", var_name="stat", value_name="value")
    plot_df["stat"] = plot_df["stat"].map(
        {"l0_clean_noise_median": "中位數", "l0_clean_noise_mean": "平均數"}
    )
    fig, ax = plt.subplots(figsize=(10.8, 6.2))
    sns.barplot(
        data=plot_df,
        x="round_name",
        y="value",
        hue="stat",
        palette={"中位數": COLORS["blue"]["base"], "平均數": COLORS["gold"]["base"]},
        ax=ax,
        edgecolor=TOKENS["ink"],
        linewidth=0.8,
    )
    ax.set_xlabel("拍攝輪次")
    ax.set_ylabel("L0 重複擬合波動")
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        frameon=False,
        ncol=2,
    )
    for container in ax.containers:
        ax.bar_label(container, fmt="%.4f", padding=3, fontsize=9)
    add_chart_header(
        fig,
        ax,
        "L0：同一輪資料自己重跑 15 次的自然波動",
        "Round1 是正式 L0 錨點；Round2/Round3 也重跑是為了檢查三輪拍攝各自的擬合穩定性。",
    )
    fig.subplots_adjust(bottom=0.19)
    chart_path = save_chart(fig, FOLDERS["charts"] / "chart_02_l0_noise_floor_by_round.png")
    add_record(
        "新畫的 L0/L1 統計圖",
        chart_path,
        "L0 三輪各自的重複擬合底噪",
        "這張圖比較三輪資料各自重複擬合 15 次時的自然波動。可以看到三輪的中位底噪都很小，而且量級接近，代表每一輪資料自己拿去重跑時都算穩。",
        "放在 L0 結果頁，說明 L0 是「同一批資料自己重跑」得到的底噪，不是三輪拍攝互相比。",
        "正式 L0 錨點仍是 Round1；Round2/Round3 這裡只是輔助檢查。",
        VE / "L1_newdata" / "L1_newdata_summary.json",
    )

    fov_plot = fov_df.copy()
    fov_plot["short_label"] = fov_plot["fov_index"].map(lambda value: f"#{value}")
    fig, ax = plt.subplots(figsize=(12, 6.4))
    x = np.arange(len(fov_plot))
    width = 0.38
    bars1 = ax.bar(
        x - width / 2,
        fov_plot["l0_floor_median"],
        width=width,
        label="L0 自己重跑底噪",
        color=COLORS["blue"]["base"],
        edgecolor=COLORS["blue"]["dark"],
        linewidth=0.8,
    )
    bars2 = ax.bar(
        x + width / 2,
        fov_plot["capture_std_median"],
        width=width,
        label="L1 三次拍攝散布",
        color=COLORS["orange"]["base"],
        edgecolor=COLORS["orange"]["dark"],
        linewidth=0.8,
    )
    ax.set_xticks(x, fov_plot["short_label"])
    ax.set_xlabel("代表視野位置")
    ax.set_ylabel("中位散布")
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        frameon=False,
        ncol=2,
    )
    ax.bar_label(bars1, fmt="%.3f", padding=3, fontsize=8)
    ax.bar_label(bars2, fmt="%.3f", padding=3, fontsize=8)
    add_chart_header(
        fig,
        ax,
        "L1：三次拍攝的變化大多低於 L0 自身底噪",
        "每個位置比較兩件事：同一輪自己重跑會晃多少，以及 Round1/2/3 三次拍攝彼此差多少。",
    )
    fig.subplots_adjust(bottom=0.19)
    chart_path = save_chart(
        fig, FOLDERS["charts"] / "chart_03_l1_capture_vs_l0_floor_by_fov.png"
    )
    add_record(
        "新畫的 L0/L1 統計圖",
        chart_path,
        "L1 三次拍攝散布與 L0 底噪比較",
        "這張圖是新 L1 最適合放簡報的核心結果。每個視野位置都有兩根柱：藍色是 L0 自己重跑造成的波動，橘色是三次拍攝之間的波動。橘色普遍比藍色小，表示拍攝重複性沒有超過擬合自己的底噪。",
        "放在 L1 結果頁，直接回答「三次拍攝是否穩定」。",
        "這裡只畫 9 個代表 FOV，不是 121 格全部；完整資料仍在來源 JSON/CSV。",
        VE / "L1_newdata" / "L1_newdata_summary.json",
    )

    coef_plot = coef_df.copy()
    coef_plot["short_label"] = coef_plot["coef_number"].map(lambda value: f"x{value}")
    coef_plot = coef_plot.sort_values("median_abs_z", ascending=True)
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    bar_colors = [
        COLORS["blue"]["base"] if value else "#E2E5EA"
        for value in coef_plot["used_for_main_readout"]
    ]
    edge_colors = [
        COLORS["blue"]["dark"] if value else "#7A828F"
        for value in coef_plot["used_for_main_readout"]
    ]
    bars = ax.barh(
        coef_plot["short_label"],
        coef_plot["median_abs_z"],
        color=bar_colors,
        edgecolor=edge_colors,
        linewidth=0.8,
    )
    ax.axvline(2.0, color=TOKENS["ink"], linestyle=":", linewidth=1.2)
    ax.text(2.02, len(coef_plot) - 1.0, "警戒參考值 2", va="center", ha="left", fontsize=9, color=TOKENS["muted"])
    ax.set_xlabel("三次拍攝差異 / L0 底噪（abs-z，中位數）")
    ax.set_ylabel("係數")
    ax.set_xlim(0, max(2.35, coef_plot["median_abs_z"].max() * 1.25))
    for bar, value in zip(bars, coef_plot["median_abs_z"]):
        ax.text(
            value + 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            fontsize=8.5,
            color=TOKENS["ink"],
        )
    add_chart_header(
        fig,
        ax,
        "L1：主要可讀係數都遠低於警戒範圍",
        "藍色是主要讀數使用的可信係數；灰色是鎖住、貼邊或幾乎不動的係數，只作背景參考。",
    )
    chart_path = save_chart(
        fig, FOLDERS["charts"] / "chart_04_l1_abs_z_by_coefficient.png"
    )
    add_record(
        "新畫的 L0/L1 統計圖",
        chart_path,
        "L1 各係數相對 L0 底噪的變化",
        "這張圖把每個係數的三次拍攝差異換成相對於 L0 底噪的讀法。藍色可信係數都遠低於 2，代表主要可讀係數沒有出現超過自身底噪的大幅漂移。",
        "放在 L1 細節頁，補充不是只有平均穩，而是各主要係數也沒有明顯失控。",
        "灰色係數不是主要判讀依據，因為有些係數被鎖住、貼邊或幾乎不動。",
        VE / "L1_newdata" / "L1_newdata_summary.json",
    )

    trust = coef_df[coef_df["used_for_main_readout"]].copy()
    capture_std = np.array(l1["arrays"]["capture_std"], dtype=float)
    trust_indices = trust["coef_index"].astype(int).tolist()
    heat = capture_std[trust_indices, :]
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    cmap = sns.blend_palette(
        [
            TOKENS["panel"],
            COLORS["blue"]["xlight"],
            COLORS["blue"]["light"],
            COLORS["blue"]["base"],
        ],
        as_cmap=True,
    )
    sns.heatmap(
        heat,
        ax=ax,
        cmap=cmap,
        linewidths=1.0,
        linecolor="#FFFFFF",
        annot=True,
        fmt=".3f",
        cbar_kws={"label": "拍攝間散布"},
    )
    ax.set_xticklabels([f"#{value}" for value in fov_df["fov_index"]], rotation=0)
    ax.set_yticklabels([f"x{value}" for value in trust["coef_number"]], rotation=0)
    ax.set_xlabel("代表視野位置")
    ax.set_ylabel("可信係數")
    add_chart_header(
        fig,
        ax,
        "L1：可信係數在各視野位置的拍攝間散布",
        "顏色越深代表 Round1/2/3 三次拍攝彼此差異越大；整體量級仍小。",
    )
    chart_path = save_chart(
        fig, FOLDERS["charts"] / "chart_05_l1_capture_std_heatmap.png"
    )
    add_record(
        "新畫的 L0/L1 統計圖",
        chart_path,
        "L1 可信係數與視野位置熱圖",
        "這張圖把 L1 的拍攝間散布拆成「係數 × 視野位置」來看。它可以幫你說明穩定性不是只看一個總平均，而是檢查每個位置、每個主要係數。",
        "放在附錄或技術結果頁，作為比較完整的 L1 細節圖。",
        "這張圖只包含可信係數；被鎖住或貼邊的係數不適合作主要讀數。",
        VE / "L1_newdata" / "L1_newdata_summary.json",
    )

    create_paired_frame_charts(paired_df)


def create_paired_frame_charts(paired_df: pd.DataFrame) -> None:
    agg = paired_df.groupby(["row", "col"], as_index=False).agg(
        edge_mean_abs_diff=("edge_mean_abs_diff", "median"),
        center_shift_px=("center_shift_px", "median"),
    )
    heatmap_specs = [
        (
            "edge_mean_abs_diff",
            "chart_06_paired_frame_edge_diff_heatmap.png",
            "連拍兩張：圓邊界區域的影像差異",
            "每格是同一位置連拍兩張影像在圓邊界附近的中位差異；這是影像層檢查，不是 PSF 擬合結果。",
            "這張熱圖是在看每個位置連拍兩張影像的圓邊界亮度差異。白話來說，它回答「同一位置馬上拍兩張，邊界區域像不像」。數字多落在相近範圍，代表連拍差異主要是影像層的小變化。",
            "放在補充實驗頁，說明兩張連拍影像被當成額外檢查，而不是主 L1 軸。",
            "這是影像差異檢查，不是第二張也拿去做 PSF 擬合後的結果。",
        ),
        (
            "center_shift_px",
            "chart_07_paired_frame_center_shift_heatmap.png",
            "連拍兩張：估計中心位移量",
            "每格是同一位置兩張連拍影像估計中心差多少像素；這是影像層的穩定性補充。",
            "這張熱圖在看同一位置連拍兩張時，中心估計會差多少像素。大多數位置差異很小，可用來支持拍攝本身沒有劇烈跳動。",
            "放在補充實驗頁，搭配上一張邊界差異熱圖一起講。",
            "這裡的中心位移是影像層估計，不等於最終 PSF 係數漂移。",
        ),
    ]
    for metric, file_name, title, subtitle, desc, use, caution in heatmap_specs:
        matrix = agg.pivot(index="row", columns="col", values=metric).sort_index(
            ascending=True
        )
        fig, ax = plt.subplots(figsize=(9.5, 7.4))
        cmap = sns.blend_palette(
            [
                TOKENS["panel"],
                COLORS["gold"]["xlight"],
                COLORS["gold"]["light"],
                COLORS["orange"]["base"],
            ],
            as_cmap=True,
        )
        sns.heatmap(
            matrix,
            ax=ax,
            cmap=cmap,
            linewidths=0.8,
            linecolor="#FFFFFF",
            annot=True,
            fmt=".2f",
            cbar_kws={"label": "像素差異" if metric == "center_shift_px" else "亮度差異"},
        )
        ax.set_xlabel("11x11 視野欄")
        ax.set_ylabel("11x11 視野列")
        add_chart_header(fig, ax, title, subtitle, title_width=48, subtitle_width=78)
        chart_path = save_chart(fig, FOLDERS["charts"] / file_name)
        add_record(
            "新畫的連拍補充圖",
            chart_path,
            title,
            desc,
            use,
            caution,
            VE / "L1_paired_frame_check" / "paired_frame_metrics.csv",
        )

    fig, axes = plt.subplots(1, 2, figsize=(13, 6.2))
    palette_round = {
        1: COLORS["blue"]["base"],
        2: COLORS["gold"]["base"],
        3: COLORS["olive"]["base"],
    }
    sns.boxplot(
        data=paired_df,
        x="round_number",
        y="edge_mean_abs_diff",
        hue="round_number",
        palette=palette_round,
        ax=axes[0],
        legend=False,
        linewidth=0.8,
    )
    sns.stripplot(
        data=paired_df.sample(min(len(paired_df), 363), random_state=7),
        x="round_number",
        y="edge_mean_abs_diff",
        color="#464C55",
        size=2,
        alpha=0.25,
        ax=axes[0],
    )
    axes[0].set_xlabel("拍攝輪次")
    axes[0].set_ylabel("圓邊界平均絕對差")
    axes[0].set_title("圓邊界差異")
    sns.boxplot(
        data=paired_df,
        x="round_number",
        y="center_shift_px",
        hue="round_number",
        palette=palette_round,
        ax=axes[1],
        legend=False,
        linewidth=0.8,
    )
    sns.stripplot(
        data=paired_df.sample(min(len(paired_df), 363), random_state=8),
        x="round_number",
        y="center_shift_px",
        color="#464C55",
        size=2,
        alpha=0.25,
        ax=axes[1],
    )
    axes[1].set_xlabel("拍攝輪次")
    axes[1].set_ylabel("中心位移 px")
    axes[1].set_title("中心位移")
    for ax in axes:
        sns.despine(ax=ax)
    fig.subplots_adjust(top=0.78)
    fig.text(
        0.06,
        0.97,
        "連拍影像補充：三輪的影像層差異分布",
        fontsize=15,
        fontweight="semibold",
        color=TOKENS["ink"],
        ha="left",
        va="top",
    )
    fig.text(
        0.06,
        0.91,
        "每個點是一個位置的連拍兩張影像；箱型圖顯示三輪的整體分布。",
        fontsize=10.5,
        color=TOKENS["muted"],
        ha="left",
        va="top",
    )
    chart_path = save_chart(
        fig, FOLDERS["charts"] / "chart_08_paired_frame_distribution_by_round.png"
    )
    add_record(
        "新畫的連拍補充圖",
        chart_path,
        "三輪連拍影像差異分布",
        "這張圖把所有 363 組連拍影像整理成分布。左邊看圓邊界亮度差異，右邊看估計中心位移。它的價值是把連拍影像本身的穩定性用一頁講完。",
        "放在補充結果頁，回答「每個位置拍兩張到底差多少」。",
        "這仍是影像層補充檢查，不是主 L1 的 PSF 擬合比較。",
        VE / "L1_paired_frame_check" / "paired_frame_metrics.csv",
    )


def create_image_panels(paired_df: pd.DataFrame) -> None:
    gt_dir = VE / "L0_newdata_round1" / "inputs_primary" / "GT"
    paths_pipeline = [
        gt_dir / "GT_901_original_with_blocks.bmp",
        gt_dir / "GT_901_with_Block_proc.bmp",
        gt_dir / "circle_edge_mask.bmp",
        VE
        / "L0_newdata_round1"
        / "inputs_primary"
        / "VisionTop_Circle_Round1_061.bmp",
    ]
    ims = [normalize_for_display(read_gray(path)) for path in paths_pipeline]
    base = normalize_for_display(read_gray(paths_pipeline[3])).convert("RGB")
    mask = read_gray(paths_pipeline[2]).resize(base.size)
    arr = np.array(base)
    mask_arr = np.array(mask) > 0
    arr[mask_arr, 0] = 255
    arr[mask_arr, 1] = (arr[mask_arr, 1] * 0.35).astype(np.uint8)
    arr[mask_arr, 2] = (arr[mask_arr, 2] * 0.35).astype(np.uint8)
    overlay = Image.fromarray(arr)
    panel_path = FOLDERS["processing"] / "06_processing_pipeline_panel.png"
    save_panel(
        ims + [overlay],
        ["原始 GT", "中心處理後 GT", "圓邊界遮罩", "處理後輸入", "遮罩疊在輸入上"],
        panel_path,
        "新資料擬合目標的處理流程",
        "從有中心方塊的目標，轉成只讓圓邊界主導擬合的輸入。",
        cols=5,
        figsize=(16, 4.3),
    )
    add_record(
        "新資料目標與前處理",
        panel_path,
        "新資料擬合目標處理流程總覽",
        "這張把原始 GT、處理後 GT、圓邊界遮罩、處理後輸入，以及遮罩疊圖放在同一排。它非常適合用一張圖講清楚：為什麼這次不看中心方塊，而是看圓形邊界。",
        "放在方法流程頁，當作最主要的資料處理說明圖。",
        "這張是我由多張來源圖合成的簡報圖；各來源圖也有單獨放在同一資料夾。",
        "; ".join(str(path) for path in paths_pipeline),
    )

    pos61_paths = [
        VE
        / f"L0_newdata_round{round_number}"
        / "inputs_primary"
        / f"VisionTop_Circle_Round{round_number}_061.bmp"
        for round_number in (1, 2, 3)
    ]
    pos61_ims = [normalize_for_display(read_gray(path)) for path in pos61_paths]
    panel_path = FOLDERS["round_examples"] / "round1_round2_round3_fov061_panel.png"
    save_panel(
        pos61_ims,
        ["Round1 #61", "Round2 #61", "Round3 #61"],
        panel_path,
        "同一位置在三次拍攝中的樣貌",
        "#61 是 11x11 視野的中心位置；三張並排可直觀看出三次拍攝條件相近。",
        cols=3,
        figsize=(10.8, 4.1),
    )
    add_record(
        "三輪拍攝的代表視野影像",
        panel_path,
        "Round1/Round2/Round3 中心位置並排",
        "這張把三次拍攝中同一個中心位置 #61 並排。它可以用來白話說明 L1 的意義：不是同一張圖重跑，而是同條件下重新拍三次後再比較。",
        "放在 L1 實驗設計頁，解釋三個影像集就是三次同條件重複拍攝。",
        "這是處理後輸入影像並排，不是原始相機大圖。",
        "; ".join(str(path) for path in pos61_paths),
    )

    fov_indices = [1, 6, 11, 56, 61, 66, 111, 116, 121]
    for round_number in (1, 2, 3):
        ims = []
        labels = []
        srcs = []
        for index in fov_indices:
            path = (
                VE
                / f"L0_newdata_round{round_number}"
                / "inputs_primary"
                / f"VisionTop_Circle_Round{round_number}_{index:03d}.bmp"
            )
            ims.append(normalize_for_display(read_gray(path)))
            labels.append(f"#{index}")
            srcs.append(str(path))
        panel_path = (
            FOLDERS["round_examples"]
            / f"round{round_number}_selected_9_fov_contact_sheet.png"
        )
        save_panel(
            ims,
            labels,
            panel_path,
            f"Round{round_number}：9 個代表視野位置",
            "選的是 11x11 視野中的四角、邊中與中心位置，用來快速展示整個視野的代表樣貌。",
            cols=3,
            figsize=(9.2, 9.8),
        )
        add_record(
            "三輪拍攝的代表視野影像",
            panel_path,
            f"Round{round_number} 九個代表視野總覽",
            f"這張把 Round{round_number} 的九個代表位置排成 3x3：四角、邊中、中心都有。它適合快速說明這次雖然完整 FOV 是 121 格，但正式分析先選了能代表全場的 9 個位置。",
            "放在資料設計或附錄頁，讓聽眾看到取樣位置的影像樣貌。",
            "這是代表 9 格的總覽，不是 121 格全圖；完整 121 張仍在原資料夾。",
            "; ".join(srcs),
        )

    create_raw_panels(paired_df)


def create_raw_panels(paired_df: pd.DataFrame) -> None:
    pair1 = paired_df[
        (paired_df.round_number == 1) & (paired_df.position_index == 1)
    ].iloc[0]
    raw_f1 = Path(pair1["frame_1"])
    raw_f2 = Path(pair1["frame_2"])
    im1 = read_gray(raw_f1)
    im2 = read_gray(raw_f2)
    max_side = 900
    im1_small = normalize_for_display(im1.copy())
    im2_small = normalize_for_display(im2.copy())
    im1_small.thumbnail((max_side, max_side))
    im2_small.thumbnail((max_side, max_side))
    diff = Image.fromarray(
        np.clip(
            np.abs(
                np.array(im1.resize(im1_small.size)).astype(np.int16)
                - np.array(im2.resize(im1_small.size)).astype(np.int16)
            )
            * 18,
            0,
            255,
        ).astype(np.uint8)
    )
    panel_path = FOLDERS["raw_examples"] / "raw_round1_pos001_frame_pair_diff.png"
    save_panel(
        [im1_small, im2_small, diff],
        ["第一張", "第二張", "差異放大顯示"],
        panel_path,
        "原始連拍影像範例：Round1 第 1 格",
        "同一位置連拍兩張，右圖把差異加強顯示，方便看出影像層變化。",
        cols=3,
        figsize=(12, 4.5),
    )
    add_record(
        "原始連拍影像範例",
        panel_path,
        "Round1 第 1 格原始連拍差異圖",
        "這張從原始相機大圖做成簡報用縮圖：左邊是同一位置的第一張，中央是第二張，右邊把兩張差異放大顯示。它能直觀說明每個位置其實有連拍兩張，而這兩張主要拿來做影像層補充檢查。",
        "放在補充實驗頁，解釋「每個位置拍兩張」這件事。",
        "右邊差異圖為了看得清楚有放大差異，不代表實際亮度差那麼強。",
        f"{raw_f1}; {raw_f2}",
    )

    raw_pos61 = paired_df[paired_df.position_index == 61].sort_values("round_number")
    raw_imgs = []
    raw_labels = []
    raw_srcs = []
    for _, row in raw_pos61.iterrows():
        path = Path(row["frame_1"])
        im = normalize_for_display(read_gray(path))
        im.thumbnail((max_side, max_side))
        raw_imgs.append(im)
        raw_labels.append(f"Round{int(row['round_number'])} #61")
        raw_srcs.append(str(path))
    panel_path = FOLDERS["raw_examples"] / "raw_rounds_fov061_frame1_panel.png"
    save_panel(
        raw_imgs,
        raw_labels,
        panel_path,
        "原始大圖：三次拍攝的中心位置",
        "同一個 #61 中心位置，取每輪的第一張原始大圖縮成簡報用版本。",
        cols=3,
        figsize=(12, 4.5),
    )
    add_record(
        "原始連拍影像範例",
        panel_path,
        "三輪原始大圖中心位置並排",
        "這張用原始相機大圖的縮圖來看三次拍攝的中心位置。它比處理後小圖更接近實際拍攝現場，可以拿來說明這次 Round1/2/3 是同條件重新拍攝。",
        "放在實驗設計頁或補充頁，讓人看到原始拍攝資料的樣貌。",
        "這是縮小後的簡報圖；原始 BMP 很大，完整原檔仍保留在來源資料夾。",
        "; ".join(raw_srcs),
    )


def copy_source_data() -> None:
    def copy_source(src: Path, dst_name: str, description: str) -> None:
        dst = FOLDERS["source_data"] / dst_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".md":
            dst = dst.with_suffix(".txt")
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            shutil.copy2(src, dst)
        source_records.append(
            {
                "file_name": dst.name,
                "asset_path": str(dst),
                "description": description,
                "original_source_path": str(src),
            }
        )

    copy_source(
        VE / "L1_newdata" / "L1_newdata_summary.json",
        "L1_newdata_summary.json",
        "新 L1 的完整機器可讀摘要，包含三輪拍攝比較、係數表、FOV 表與主要判讀數字。",
    )
    copy_source(
        VE / "L1_newdata" / "L1_newdata_summary.md",
        "L1_newdata_summary.txt",
        "新 L1 的文字版摘要；已轉成 txt，方便上傳。",
    )
    copy_source(
        VE / "L1_paired_frame_check" / "paired_frame_metrics.csv",
        "paired_frame_metrics.csv",
        "363 組連拍影像的逐位置數據，包含邊界差異與中心位移。",
    )
    copy_source(
        VE / "L1_paired_frame_check" / "paired_frame_summary.json",
        "paired_frame_summary.json",
        "連拍影像檢查的完整摘要。",
    )
    copy_source(
        VE / "L1_paired_frame_check" / "paired_frame_summary.md",
        "paired_frame_summary.txt",
        "連拍影像檢查的文字摘要；已轉成 txt。",
    )
    for round_number in (1, 2, 3):
        copy_source(
            VE
            / f"L0_newdata_round{round_number}"
            / "outputs"
            / "L0_newdata_noise_floor.json",
            f"L0_round{round_number}_noise_floor.json",
            f"Round{round_number} 同一輪資料重複擬合 15 次的 L0 底噪完整資料。",
        )
        copy_source(
            VE
            / f"L0_newdata_round{round_number}"
            / "outputs"
            / "L0_newdata_noise_floor_report.md",
            f"L0_round{round_number}_noise_floor_report.txt",
            f"Round{round_number} L0 底噪文字摘要；已轉成 txt。",
        )
    copy_source(
        VE / "PSF_UPLOAD_FILE_MANIFEST_20260623.csv",
        "previous_upload_manifest_20260623.csv",
        "之前整理過的上傳檔案清單，可作補充索引。",
    )
    copy_source(
        VE / "PSF_UPLOAD_HANDOFF_20260623_TW.txt",
        "previous_upload_handoff_20260623_TW.txt",
        "之前寫給 GPT 分析/報告用的文字交接稿。",
    )


def write_guides() -> None:
    guide_csv = OUT / "IMAGE_GUIDE.csv"
    with open(guide_csv, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    guide_txt = OUT / "IMAGE_GUIDE.txt"
    lines = [
        "PSF L0/L1 簡報素材包圖像說明",
        f"建立時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"素材包位置：{OUT}",
        "",
        "使用方式：每張圖旁邊都有同名 .txt 說明檔；這份 IMAGE_GUIDE.txt 則是全部圖的總表。",
        "注意：舊 L0 圖只當概念與歷史參考；新 L0/L1 正式簡報建議優先使用 04_generated_summary_charts 裡的新圖。",
        "",
    ]
    for index, record in enumerate(records, 1):
        lines.extend(
            [
                f"[{index:02d}] {record['title']}",
                f"分類：{record['category']}",
                f"檔案：{record['asset_path']}",
                f"說明：{record['plain_explanation']}",
                f"簡報用法：{record['suggested_slide_use']}",
                f"注意：{record['caution']}",
            ]
        )
        if record["original_source_path"]:
            lines.append(f"原始來源：{record['original_source_path']}")
        lines.append("")
    guide_txt.write_text("\n".join(lines), encoding="utf-8")

    source_csv = OUT / "SOURCE_DATA_GUIDE.csv"
    with open(source_csv, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "file_name",
                "asset_path",
                "description",
                "original_source_path",
            ],
        )
        writer.writeheader()
        writer.writerows(source_records)

    source_txt = OUT / "SOURCE_DATA_GUIDE.txt"
    source_lines = ["PSF L0/L1 數據來源檔說明", ""]
    for record in source_records:
        source_lines.append(f"- {record['file_name']}：{record['description']}")
        source_lines.append(f"  位置：{record['asset_path']}")
        source_lines.append(f"  原始來源：{record['original_source_path']}")
    source_txt.write_text("\n".join(source_lines) + "\n", encoding="utf-8")

    readme = OUT / "00_READ_ME_FIRST.txt"
    readme.write_text(
        f"""PSF L0/L1 簡報素材包

位置：{OUT}

資料夾用途：
01_existing_result_figures：已存在的擬合結果圖與舊 L0 分群圖。
02_current_experiment_target_and_processing：這次新資料如何把中心方塊排除、只看圓邊界的流程圖。
03_current_round_examples：Round1/Round2/Round3 三次拍攝的代表視野影像。
04_generated_summary_charts：這次新 L0/L1 與連拍補充檢查新畫出的簡報用統計圖。
05_raw_paired_frame_examples：原始大圖縮成的連拍範例。
06_source_data_for_upload：產生圖表用的 JSON/CSV/TXT 數據檔。

建議簡報順序：
1. 先放 02_current_experiment_target_and_processing/06_processing_pipeline_panel.png，說明為什麼只看圓邊界。
2. 再放 03_current_round_examples/round1_round2_round3_fov061_panel.png，說明 Round1/2/3 是三次同條件拍攝。
3. 接著放 04_generated_summary_charts/chart_02_l0_noise_floor_by_round.png，說明 L0 是同一批資料自己重跑的底噪。
4. 核心結果放 04_generated_summary_charts/chart_03_l1_capture_vs_l0_floor_by_fov.png。
5. 細節補充放 chart_04、chart_05、chart_06 到 chart_08。
6. 如果要講歷史脈絡，再放 01_existing_result_figures 的舊 L0 圖。

每張圖都有同名 .txt 說明檔，也可以直接看 IMAGE_GUIDE.txt 或 IMAGE_GUIDE.csv。
""",
        encoding="utf-8",
    )


def validate_pack() -> dict:
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    asset_images = [
        path for path in OUT.rglob("*") if path.suffix.lower() in image_exts
    ]
    missing_sidecars = [
        str(path) for path in asset_images if not Path(str(path) + ".txt").exists()
    ]
    bad_images = []
    for path in asset_images:
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:  # pragma: no cover - written for runtime report.
            bad_images.append((str(path), str(exc)))
    summary = {
        "output_dir": str(OUT),
        "image_count": len(asset_images),
        "guide_rows": len(records),
        "source_data_count": len(source_records),
        "missing_sidecars": missing_sidecars,
        "bad_images": bad_images,
        "category_counts": pd.Series([r["category"] for r in records])
        .value_counts()
        .to_dict(),
    }
    (OUT / "BUILD_VALIDATION_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    ensure_dirs()
    collect_existing_result_figures()
    collect_processing_images()
    collect_round_examples()
    l1, rounds_df, fov_df, coef_df, paired_df = load_data()
    create_summary_charts(l1, rounds_df, fov_df, coef_df, paired_df)
    create_image_panels(paired_df)
    copy_source_data()
    write_guides()
    print(json.dumps(validate_pack(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
