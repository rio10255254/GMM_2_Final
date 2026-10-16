from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO = Path(r"D:\GMM_2_Final")
EXPERIMENT_ROOT = REPO / "Experiments" / "R39_ShapeGeneralization"
SWEEP_ROOT = EXPERIMENT_ROOT / "results" / "a030_x_a043_sweep"
MOVED_OUTPUT_ROOT = (
    SWEEP_ROOT
    / "delivery_audit"
    / "a025_onnx_internal_eval_20260513"
    / "moved_from_delivery_package_outputs"
)
COMPARE_ROOT = MOVED_OUTPUT_ROOT / "a025_vs_combo_onnx_microscopy_compare_20260513"
CSV_PATH = COMPARE_ROOT / "metrics" / "a025_vs_combo_per_image.csv"
SUMMARY_JSON = COMPARE_ROOT / "metrics" / "a025_vs_combo_summary.json"
OLD_PACKAGE_OUTPUT_ROOT = (
    REPO
    / "_deployment_package"
    / "GeoEdge_R39R40_a025_ONNX_Company_Package_20260511"
    / "outputs"
)
OUT_ROOT = SWEEP_ROOT / "presentation_microscopy_selected_20260513"
PPT_READY = OUT_ROOT / "ppt_ready"
INTERNAL_QA = OUT_ROOT / "internal_qc"

FONT_PATHS = [
    Path(r"C:\Windows\Fonts\msjh.ttc"),
    Path(r"C:\Windows\Fonts\msjhl.ttc"),
    Path(r"C:\Windows\Fonts\mingliu.ttc"),
]


@dataclass(frozen=True)
class CaseSpec:
    slug: str
    title: str
    focus: str
    dataset: str | None
    family: str | None
    pick: str
    folder: str


CASES = [
    CaseSpec(
        "01_defects_scratch_points",
        "Defect and Scratch Preservation",
        "a025 preserves dark spots, bright particles, and scratch-like structures with higher fidelity to the ground truth.",
        "r42_boundary_val_unseen",
        "defects",
        "best_delta",
        "ppt",
    ),
    CaseSpec(
        "02_large_region_boundary",
        "Large-Area Boundary Reconstruction",
        "a025 produces sharper large-region boundaries with reduced boundary swelling and fewer edge residuals.",
        "r42_boundary_val_unseen",
        "large_regions",
        "best_delta",
        "ppt",
    ),
    CaseSpec(
        "03_mixed_micro_scene",
        "Mixed Microscopy Field",
        "a025 better preserves both coarse structures and fine local features in the same scene.",
        "r44_motion_val_unseen_subset",
        "mixed_fields",
        "best_delta",
        "ppt",
    ),
    CaseSpec(
        "04_curved_boundaries",
        "Curvilinear Boundary Localization",
        "a025 yields more localized curved boundaries with reduced background residuals and boundary drift.",
        "r44_motion_val_unseen_subset",
        "curves",
        "best_delta",
        "ppt",
    ),
    CaseSpec(
        "05_thin_lines_junctions",
        "Thin-Line and Junction Recovery",
        "a025 improves line continuity and junction reconstruction while reducing line breakage.",
        "r42_boundary_val_unseen",
        "junctions",
        "best_delta",
        "ppt",
    ),
    CaseSpec(
        "06_texture_retention",
        "Local Texture Retention",
        "a025 retains more granular and rough-surface texture detail after reconstruction.",
        "r40_micro_val_unseen",
        "textures",
        "best_delta",
        "ppt",
    ),
    CaseSpec(
        "07_grid_remaining_challenge",
        "Grid and Periodic Structures",
        "a025 shows measurable improvement, but dense periodic grids remain an important limitation.",
        None,
        "grids",
        "smallest_positive_delta",
        "ppt",
    ),
    CaseSpec(
        "08_internal_combo_better_edge_case",
        "Minority Counterexample",
        "A small subset remains closer to the ground truth with COMBO; this case is retained for internal risk discussion.",
        None,
        None,
        "worst_delta",
        "internal",
    ),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS:
        if path.exists():
            return ImageFont.truetype(str(path), size=size, index=0)
    return ImageFont.load_default(size=size)


F_TITLE = font(46, bold=True)
F_SUBTITLE = font(28)
F_PANEL = font(24)
F_SMALL = font(21)
F_TINY = font(18)


def read_rows() -> list[dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def remap_path(value: str) -> Path:
    s = value.strip()
    p = Path(s)
    if p.exists():
        return p
    old = str(OLD_PACKAGE_OUTPUT_ROOT)
    if s.lower().startswith(old.lower()):
        rel = s[len(old) :].lstrip("\\/")
        moved = MOVED_OUTPUT_ROOT / rel
        if moved.exists():
            return moved
    return p


def fnum(row: dict[str, str], key: str) -> float:
    return float(row[key])


def choose_row(rows: list[dict[str, str]], spec: CaseSpec) -> dict[str, str]:
    pool = rows
    if spec.dataset:
        pool = [r for r in pool if r["dataset"] == spec.dataset]
    if spec.family:
        pool = [r for r in pool if r["family"] == spec.family]
    if not pool:
        raise RuntimeError(f"No rows for {spec}")

    if spec.pick == "best_delta":
        return max(pool, key=lambda r: fnum(r, "delta_psnr_a025_minus_combo"))
    if spec.pick == "smallest_positive_delta":
        positive = [r for r in pool if fnum(r, "delta_psnr_a025_minus_combo") >= 0]
        return min(positive or pool, key=lambda r: abs(fnum(r, "delta_psnr_a025_minus_combo")))
    if spec.pick == "worst_delta":
        return min(pool, key=lambda r: fnum(r, "delta_psnr_a025_minus_combo"))
    raise ValueError(spec.pick)


def load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Cannot read image: {path}")
    return img


def to_pil_gray(img: np.ndarray) -> Image.Image:
    return Image.fromarray(img).convert("RGB")


def locate_roi(combo: np.ndarray, a025: np.ndarray, gt: np.ndarray, mode: str) -> tuple[int, int, int, int]:
    combo_f = combo.astype(np.float32)
    a025_f = a025.astype(np.float32)
    gt_f = gt.astype(np.float32)
    if mode == "worst_delta":
        score = np.abs(a025_f - gt_f) - np.abs(combo_f - gt_f)
    elif mode == "smallest_positive_delta":
        score = np.abs(a025_f - gt_f) + np.abs(combo_f - gt_f)
    else:
        score = np.abs(combo_f - gt_f) - np.abs(a025_f - gt_f)
    score = cv2.blur(score, (61, 61))
    y, x = np.unravel_index(int(np.argmax(score)), score.shape)
    side = min(112, combo.shape[0], combo.shape[1])
    half = side // 2
    x0 = max(0, min(combo.shape[1] - side, x - half))
    y0 = max(0, min(combo.shape[0] - side, y - half))
    return x0, y0, side, side


def fit_image(img: Image.Image, box: tuple[int, int, int, int], bg=(255, 255, 255)) -> tuple[Image.Image, tuple[int, int, float]]:
    x, y, w, h = box
    canvas = Image.new("RGB", (w, h), bg)
    scale = min(w / img.width, h / img.height)
    nw = int(round(img.width * scale))
    nh = int(round(img.height * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = x + (w - nw) // 2
    oy = y + (h - nh) // 2
    canvas.paste(resized, (ox - x, oy - y))
    return canvas, (ox, oy, scale)


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill, font_obj, max_width: int, line_gap: int = 6) -> int:
    x, y = xy
    if " " in text:
        words = text.split()
        line = ""
        for word in words:
            test = word if not line else f"{line} {word}"
            if draw.textlength(test, font=font_obj) <= max_width or not line:
                line = test
            else:
                draw.text((x, y), line, fill=fill, font=font_obj)
                y += font_obj.size + line_gap
                line = word
        if line:
            draw.text((x, y), line, fill=fill, font=font_obj)
            y += font_obj.size + line_gap
    else:
        line = ""
        for ch in text:
            test = line + ch
            if draw.textlength(test, font=font_obj) <= max_width or not line:
                line = test
            else:
                draw.text((x, y), line, fill=fill, font=font_obj)
                y += font_obj.size + line_gap
                line = ch
        if line:
            draw.text((x, y), line, fill=fill, font=font_obj)
            y += font_obj.size + line_gap
    return y


def paste_panel(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    img: np.ndarray,
    label: str,
    box: tuple[int, int, int, int],
    roi: tuple[int, int, int, int] | None = None,
    metric: str | None = None,
) -> None:
    x, y, w, h = box
    panel, (ox, oy, scale) = fit_image(to_pil_gray(img), box)
    canvas.paste(panel, (x, y))
    draw.rounded_rectangle((x - 2, y - 2, x + w + 2, y + h + 2), radius=10, outline=(210, 214, 222), width=2)
    draw.text((x, y - 34), label, fill=(31, 41, 55), font=F_PANEL)
    if metric:
        draw.text((x + w - 150, y - 32), metric, fill=(76, 89, 107), font=F_TINY)
    if roi is not None:
        rx, ry, rw, rh = roi
        draw.rectangle(
            (
                ox + rx * scale,
                oy + ry * scale,
                ox + (rx + rw) * scale,
                oy + (ry + rh) * scale,
            ),
            outline=(255, 193, 7),
            width=4,
        )


def paste_crop(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    img: np.ndarray,
    label: str,
    box: tuple[int, int, int, int],
    roi: tuple[int, int, int, int],
    outline,
) -> None:
    x, y, w, h = box
    rx, ry, rw, rh = roi
    pad = max(12, rw // 5)
    x0 = max(0, rx - pad)
    y0 = max(0, ry - pad)
    x1 = min(img.shape[1], rx + rw + pad)
    y1 = min(img.shape[0], ry + rh + pad)
    crop = img[y0:y1, x0:x1]
    panel, _ = fit_image(to_pil_gray(crop), box, bg=(248, 250, 252))
    canvas.paste(panel, (x, y))
    draw.rounded_rectangle((x - 3, y - 3, x + w + 3, y + h + 3), radius=10, outline=outline, width=4)
    draw.text((x, y + h + 8), label, fill=(31, 41, 55), font=F_SMALL)


def render_case(spec: CaseSpec, row: dict[str, str], out_dir: Path) -> Path:
    src = load_gray(remap_path(row["src"]))
    gt = load_gray(remap_path(row["lbl"]))
    combo = load_gray(remap_path(row["combo_recon"]))
    a025 = load_gray(remap_path(row["a025_recon"]))
    roi = locate_roi(combo, a025, gt, spec.pick)

    canvas = Image.new("RGB", (1920, 1080), (246, 248, 251))
    draw = ImageDraw.Draw(canvas)

    accent = (17, 122, 101) if spec.folder == "ppt" else (180, 83, 9)
    draw.rectangle((0, 0, 1920, 14), fill=accent)
    draw.text((70, 38), spec.title, fill=(17, 24, 39), font=F_TITLE)
    draw.text((72, 93), f"{row['dataset']} / {row['family']} / {row['file']}", fill=(92, 107, 125), font=F_SMALL)

    delta = fnum(row, "delta_psnr_a025_minus_combo")
    ssim_delta = fnum(row, "delta_ssim_a025_minus_combo")
    pill = f"a025 vs COMBO: PSNR {delta:+.2f} dB / SSIM {ssim_delta:+.3f}"
    pw = int(draw.textlength(pill, font=F_SMALL)) + 36
    draw.rounded_rectangle((1920 - pw - 70, 50, 1850, 92), radius=18, fill=(232, 245, 241), outline=accent, width=2)
    draw.text((1920 - pw - 52, 60), pill, fill=(20, 83, 45), font=F_SMALL)

    panel_boxes = [(70, 164, 390, 390), (530, 164, 390, 390), (990, 164, 390, 390), (1450, 164, 390, 390)]
    paste_panel(canvas, draw, src, "Input", panel_boxes[0], roi)
    paste_panel(canvas, draw, combo, "COMBO", panel_boxes[1], roi, f"{fnum(row, 'combo_psnr'):.2f} dB")
    paste_panel(canvas, draw, a025, "a025", panel_boxes[2], roi, f"{fnum(row, 'a025_psnr'):.2f} dB")
    paste_panel(canvas, draw, gt, "Ground Truth", panel_boxes[3], roi)

    draw.text((70, 594), "Magnified Region of Interest", fill=(31, 41, 55), font=F_SUBTITLE)
    crop_boxes = [(70, 648, 390, 260), (530, 648, 390, 260), (990, 648, 390, 260), (1450, 648, 390, 260)]
    paste_crop(canvas, draw, src, "Input ROI", crop_boxes[0], roi, (148, 163, 184))
    paste_crop(canvas, draw, combo, "COMBO ROI", crop_boxes[1], roi, (220, 38, 38))
    paste_crop(canvas, draw, a025, "a025 ROI", crop_boxes[2], roi, (22, 163, 74))
    paste_crop(canvas, draw, gt, "Ground Truth ROI", crop_boxes[3], roi, (37, 99, 235))

    draw.rounded_rectangle((70, 962, 1850, 1034), radius=18, fill=(255, 255, 255), outline=(218, 224, 232), width=2)
    draw.text((100, 982), "Key observation:", fill=accent, font=F_SMALL)
    draw_wrapped(draw, (330, 982), spec.focus, fill=(31, 41, 55), font_obj=F_SMALL, max_width=1460)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec.slug}.png"
    canvas.save(out_path)
    return out_path


def render_summary(rows: list[dict[str, str]]) -> Path:
    with SUMMARY_JSON.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    canvas = Image.new("RGB", (1920, 1080), (246, 248, 251))
    draw = ImageDraw.Draw(canvas)
    accent = (17, 122, 101)
    draw.rectangle((0, 0, 1920, 14), fill=accent)
    draw.text((70, 48), "a025 vs COMBO Microscopy Reconstruction", fill=(17, 24, 39), font=F_TITLE)
    draw.text((72, 106), "Curated internal presentation set from 387 microscopy, boundary, and motion validation images", fill=(92, 107, 125), font=F_SUBTITLE)

    cards = [
        ("Images Evaluated", f"{summary['overall']['count']}"),
        ("a025 Win Rate", f"{summary['overall']['a025_win_rate'] * 100:.1f}%"),
        ("Mean PSNR Gain", f"{summary['overall']['delta_psnr']:+.2f} dB"),
        ("Mean SSIM Gain", f"{summary['overall']['delta_ssim']:+.3f}"),
    ]
    for i, (k, v) in enumerate(cards):
        x = 70 + i * 455
        draw.rounded_rectangle((x, 190, x + 405, 330), radius=20, fill=(255, 255, 255), outline=(218, 224, 232), width=2)
        draw.text((x + 28, 218), k, fill=(92, 107, 125), font=F_SMALL)
        draw.text((x + 28, 258), v, fill=accent, font=font(42, bold=True))

    family_best = {}
    for row in rows:
        key = f"{row['dataset']} / {row['family']}"
        family_best.setdefault(key, []).append(row)
    family_delta = []
    for key, vals in family_best.items():
        family_delta.append((key, sum(fnum(v, "delta_psnr_a025_minus_combo") for v in vals) / len(vals)))
    family_delta.sort(key=lambda x: x[1], reverse=True)

    draw.text((70, 400), "Feature Families with the Largest Reconstruction Gains", fill=(31, 41, 55), font=F_SUBTITLE)
    top = family_delta[:8]
    max_delta = max(v for _, v in top)
    for i, (name, val) in enumerate(top):
        y = 462 + i * 54
        draw.text((92, y + 6), name.replace("r40_micro_val_unseen / ", "R40 ").replace("r42_boundary_val_unseen / ", "R42 ").replace("r44_motion_val_unseen_subset / ", "R44 "), fill=(31, 41, 55), font=F_TINY)
        bx = 640
        bw = int(780 * val / max_delta)
        draw.rounded_rectangle((bx, y, bx + 780, y + 28), radius=12, fill=(229, 231, 235))
        draw.rounded_rectangle((bx, y, bx + bw, y + 28), radius=12, fill=accent)
        draw.text((bx + 805, y - 1), f"{val:+.2f} dB", fill=(31, 41, 55), font=F_TINY)

    note = "Recommended framing: emphasize defects, large regions, curved boundaries, mixed fields, and textures. Treat dense grids as a remaining challenge rather than a solved capability."
    draw.rounded_rectangle((70, 930, 1850, 1015), radius=20, fill=(255, 255, 255), outline=(218, 224, 232), width=2)
    draw_wrapped(draw, (104, 954), note, fill=(31, 41, 55), font_obj=F_SMALL, max_width=1700)

    PPT_READY.mkdir(parents=True, exist_ok=True)
    out_path = PPT_READY / "00_summary_a025_vs_combo.png"
    canvas.save(out_path)
    return out_path


def write_index(selected: list[tuple[CaseSpec, dict[str, str], Path]], summary_path: Path) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# a025 vs COMBO 顯微重建簡報素材",
        "",
        "日期：2026-05-13",
        "",
        "## 用途",
        "",
        "這個資料夾保存 a025 ONNX 與 COMBO ONNX 顯微重建比較的簡報素材。這些是內部展示/簡報素材，不放入公司 ONNX 交付包。",
        "",
        "## 主簡報素材",
        "",
        f"- `{summary_path.relative_to(OUT_ROOT)}`：整體比較摘要。",
    ]
    for spec, row, path in selected:
        rel = path.relative_to(OUT_ROOT)
        delta = fnum(row, "delta_psnr_a025_minus_combo")
        target = "主簡報" if spec.folder == "ppt" else "內部備用"
        lines.append(f"- `{rel}`：{target}，{spec.title}，PSNR 差異 {delta:+.2f} dB。")
    lines += [
        "",
        "## 建議使用方式",
        "",
        "- 對外或正式簡報：優先使用 `ppt_ready/00` 到 `ppt_ready/06`，展示 a025 在缺陷、大區塊、曲線、混合場景與紋理上的改善。",
        "- 需要誠實說明限制時：使用 `ppt_ready/07_grid_remaining_challenge.png`，說明格線/週期結構仍是後續強化方向。",
        "- 內部問答或風險討論：使用 `internal_qc/08_internal_combo_better_edge_case.png`，說明 a025 不是每張都勝過 COMBO。",
    ]
    (OUT_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    csv_path = OUT_ROOT / "selected_cases.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["slide", "folder", "dataset", "family", "file", "delta_psnr", "combo_psnr", "a025_psnr", "output"])
        for spec, row, path in selected:
            writer.writerow(
                [
                    spec.slug,
                    spec.folder,
                    row["dataset"],
                    row["family"],
                    row["file"],
                    f"{fnum(row, 'delta_psnr_a025_minus_combo'):.4f}",
                    f"{fnum(row, 'combo_psnr'):.4f}",
                    f"{fnum(row, 'a025_psnr'):.4f}",
                    str(path),
                ]
            )


def make_contact_sheet(paths: Iterable[Path]) -> Path:
    imgs = [Image.open(p).convert("RGB") for p in paths]
    thumbs = []
    for img in imgs:
        t = img.copy()
        t.thumbnail((580, 326), Image.Resampling.LANCZOS)
        thumbs.append(t)
    cols = 2
    rows = int(np.ceil(len(thumbs) / cols))
    canvas = Image.new("RGB", (1280, 80 + rows * 390), (246, 248, 251))
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 24), "a025 vs COMBO Presentation Figure Overview", fill=(17, 24, 39), font=F_SUBTITLE)
    for i, (thumb, path) in enumerate(zip(thumbs, paths)):
        c = i % cols
        r = i // cols
        x = 40 + c * 620
        y = 90 + r * 390
        draw.rounded_rectangle((x - 8, y - 8, x + 588, y + 338), radius=14, fill=(255, 255, 255), outline=(218, 224, 232), width=2)
        canvas.paste(thumb, (x, y))
        draw.text((x, y + 336), path.stem, fill=(76, 89, 107), font=F_TINY)
    out = OUT_ROOT / "contact_sheet_all_selected.png"
    canvas.save(out)
    return out


def main() -> None:
    rows = read_rows()
    PPT_READY.mkdir(parents=True, exist_ok=True)
    INTERNAL_QA.mkdir(parents=True, exist_ok=True)
    summary_path = render_summary(rows)

    selected: list[tuple[CaseSpec, dict[str, str], Path]] = []
    for spec in CASES:
        row = choose_row(rows, spec)
        target = PPT_READY if spec.folder == "ppt" else INTERNAL_QA
        out = render_case(spec, row, target)
        selected.append((spec, row, out))

    write_index(selected, summary_path)
    contact = make_contact_sheet([summary_path] + [p for _, _, p in selected])
    print(json.dumps({
        "output_root": str(OUT_ROOT),
        "ppt_ready": str(PPT_READY),
        "internal_qc": str(INTERNAL_QA),
        "summary": str(summary_path),
        "contact_sheet": str(contact),
        "slides": [str(p) for _, _, p in selected],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
