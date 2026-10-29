from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
DATASET = (
    ROOT
    / "LabSystem_MOSR"
    / "Training_Data"
    / "r61_universal_boundary_generalization"
    / "hs100mg_basler"
    / "r61_universal_boundary_train_motion_texture_step_guard_v16"
)
RAW_100MG = ROOT / "20260618_100MG" / "Image__2026-06-18__17-10-31.bmp"
OUT = ROOT / "Experiments" / "20260626_training_data_representatives"
IMG_DIR = OUT / "images"


@dataclass
class Selected:
    key: str
    role: str
    kind: str
    source_rel: str
    boundary_rel: str
    clean_png: Path
    overlay_png: Path
    score: float
    note: str
    old_model_gap: str


def load_gray(path: Path) -> Image.Image:
    return Image.open(path).convert("L")


def normalize_for_slide(im: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(im, cutoff=0.5)


def upscale(im: Image.Image, side: int = 768) -> Image.Image:
    return im.resize((side, side), Image.Resampling.NEAREST)


def boundary_overlay(src: Image.Image, boundary: Image.Image) -> Image.Image:
    base = np.array(normalize_for_slide(src), dtype=np.float32)
    rgb = np.stack([base, base, base], axis=-1)
    raw_mask = np.array(boundary) > 0
    eroded = np.array(
        Image.fromarray((raw_mask.astype(np.uint8) * 255)).filter(ImageFilter.MinFilter(9))
    ) > 0
    mask = raw_mask & ~eroded
    mask = np.array(Image.fromarray((mask.astype(np.uint8) * 255)).filter(ImageFilter.MaxFilter(5))) > 0
    red = np.zeros_like(rgb)
    red[..., 0] = 255
    red[..., 1] = 32
    red[..., 2] = 32
    rgb[mask] = rgb[mask] * 0.25 + red[mask] * 0.75
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def score_candidate(src_path: Path, boundary_path: Path) -> float:
    src = np.array(load_gray(src_path), dtype=np.float32)
    bd = np.array(load_gray(boundary_path)) > 0
    if not bd.any():
        return -1e9
    h, w = bd.shape
    ys, xs = np.nonzero(bd)
    centroid_dist = ((xs.mean() - w / 2) ** 2 + (ys.mean() - h / 2) ** 2) ** 0.5
    border = bd[:3, :].sum() + bd[-3:, :].sum() + bd[:, :3].sum() + bd[:, -3:].sum()
    count = bd.sum()
    contrast = float(np.percentile(src, 95) - np.percentile(src, 5))
    if contrast < 8:
        return -1e9
    count_score = -abs(count - 900) / 900
    return contrast * 0.03 + count_score * 2.0 - centroid_dist * 0.04 - border * 0.01


def select_from_manifest(pairs: list[dict], role: str, kind: str) -> tuple[dict, float]:
    candidates: list[tuple[float, dict]] = []
    for item in pairs:
        rel = item.get("package_src", "")
        if item.get("role") != role or f"/{kind}/" not in rel.replace("\\", "/"):
            continue
        src_path = DATASET / rel
        boundary_path = DATASET / item["geometry_boundary"]
        if not src_path.exists() or not boundary_path.exists():
            continue
        candidates.append((score_candidate(src_path, boundary_path), item))
    if not candidates:
        raise RuntimeError(f"No candidate found for role={role}, kind={kind}")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1], candidates[0][0]


def save_pair(
    key: str,
    role: str,
    kind: str,
    item: dict,
    score: float,
    note: str,
    old_model_gap: str,
) -> Selected:
    src_path = DATASET / item["package_src"]
    boundary_path = DATASET / item["geometry_boundary"]
    clean = upscale(normalize_for_slide(load_gray(src_path)))
    overlay = upscale(boundary_overlay(load_gray(src_path), load_gray(boundary_path)))

    clean_png = IMG_DIR / f"{key}_clean.png"
    overlay_png = IMG_DIR / f"{key}_boundary_overlay.png"
    clean.save(clean_png)
    overlay.save(overlay_png)

    return Selected(
        key=key,
        role=role,
        kind=kind,
        source_rel=item["package_src"],
        boundary_rel=item["geometry_boundary"],
        clean_png=clean_png,
        overlay_png=overlay_png,
        score=score,
        note=note,
        old_model_gap=old_model_gap,
    )


def save_source_overview() -> Path:
    if not RAW_100MG.exists():
        return Path()
    im = normalize_for_slide(load_gray(RAW_100MG))
    w, h = im.size
    crop_w, crop_h = int(w * 0.74), int(h * 0.74)
    left = (w - crop_w) // 2
    top = (h - crop_h) // 2
    overview = im.crop((left, top, left + crop_w, top + crop_h))
    overview.thumbnail((1200, 900), Image.Resampling.LANCZOS)
    out = IMG_DIR / "source_100mg_basler_real_image_overview.png"
    overview.save(out)
    return out


def save_legacy_contrast(pairs: list[dict]) -> Selected:
    best_item = None
    best_score = -1e9
    for item in pairs:
        rel = item.get("package_src", "")
        if item.get("role") != "legacy_shape" or "/ring/" not in rel.replace("\\", "/"):
            continue
        if Path(rel).suffix.lower() not in {".bmp", ".png", ".jpg", ".jpeg"}:
            continue
        src_path = DATASET / rel
        boundary_path = DATASET / item["geometry_boundary"]
        if not src_path.exists() or not boundary_path.exists():
            continue
        score = score_candidate(src_path, boundary_path)
        if score > best_score:
            best_item = item
            best_score = score
    if best_item is None:
        raise RuntimeError("No legacy ring candidate found")
    return save_pair(
        "old_style_legacy_ring",
        "legacy_shape",
        "ring",
        best_item,
        best_score,
        "舊模型比較熟悉的環形/理想形狀資料，可用來對照這次不是只靠舊環形資料。",
        "舊資料對真實 100MG 顯微紋理、圓柱/圓孔極性、SEM 尺寸錨點都比較弱。",
    )


def write_index(selections: list[Selected], overview_path: Path, manifest: dict) -> None:
    csv_path = OUT / "selected_training_representatives.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "key",
                "role",
                "kind",
                "clean_png",
                "overlay_png",
                "source_in_training_package",
                "boundary_in_training_package",
                "why_selected",
                "old_model_gap",
                "score",
            ],
        )
        writer.writeheader()
        for s in selections:
            writer.writerow(
                {
                    "key": s.key,
                    "role": s.role,
                    "kind": s.kind,
                    "clean_png": str(s.clean_png),
                    "overlay_png": str(s.overlay_png),
                    "source_in_training_package": s.source_rel,
                    "boundary_in_training_package": s.boundary_rel,
                    "why_selected": s.note,
                    "old_model_gap": s.old_model_gap,
                    "score": f"{s.score:.4f}",
                }
            )

    md = OUT / "training_data_representative_index.md"
    lines = [
        "# R61 v16 training-data representative real images",
        "",
        "這包圖的用途：從訓練資料角度，展示 R61 v16 相比舊模型多了哪些真實資料，以及這些資料補強了什麼。",
        "",
        "## Dataset check",
        "",
        f"- Dataset: `{DATASET}`",
        f"- Target: `{manifest.get('target')}`",
        f"- Total pairs: `{manifest.get('total_pairs')}`",
        f"- Role counts: `{manifest.get('role_counts')}`",
        f"- Anti-answer-leakage design: `{manifest.get('anti_answer_leakage_design')}`",
        "",
    ]
    if overview_path:
        lines += [
            "## Source overview",
            "",
            f"- `source_100mg_basler_real_image_overview.png`: 100MG Basler 原始影像的中心區域，可當作真實資料來源的總覽圖。",
            "",
        ]
    lines += ["## Selected images", ""]
    for s in selections:
        lines += [
            f"### {s.key}",
            "",
            f"- Training role: `{s.role}`",
            f"- Shape/type: `{s.kind}`",
            f"- Clean image: `{s.clean_png}`",
            f"- Boundary overlay: `{s.overlay_png}`",
            f"- Why this matters: {s.note}",
            f"- Compared with old model: {s.old_model_gap}",
            "",
        ]
    lines += [
        "## Plain-language slide message",
        "",
        "- 以前模型比較像是在學會把常見形狀變清楚，尤其環形/理想形狀比較強。",
        "- R61 v16 多了 100MG 的真實顯微 crop，並且有 SEM 邊界錨點，所以它不只是把邊緣銳化，而是被拉向較接近真實尺寸的位置。",
        "- R61 v16 同時放入圓柱與圓孔，避免模型只熟一種亮暗極性。",
        "- sequence guard 的資料是為了讓模型不要每張圖各自亂修邊界，對連續位移量測的穩定性比較重要。",
        "- 位移合成資料也很重要，但它不是現場真實影像；簡報若要講真實資料來源，建議主圖用本資料夾的 real crop，位移資料另外用結果曲線說明。",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]

    overview_path = save_source_overview()
    specs = [
        (
            "new_sem_truth_pillar_real_crop",
            "sem_truth_anchor",
            "pillar",
            "100MG 圓柱真實 crop，邊界答案來自 SEM 錨點，是這次邊界尺寸準度提升最直接的資料。",
            "舊模型較缺少同一套光學條件下的真實尺寸錨點，容易只把邊緣變銳但尺寸偏掉。",
        ),
        (
            "new_sem_truth_via_real_crop",
            "sem_truth_anchor",
            "via",
            "100MG 圓孔真實 crop，補上與圓柱相反的亮暗/內外邊界情況。",
            "舊模型若偏向單一形狀或單一極性，碰到圓孔時容易把邊界方向修錯。",
        ),
        (
            "new_sequence_guard_pillar_real_crop",
            "sequence_guard",
            "pillar",
            "圓柱 sequence guard 真實 crop，用較保守的邊界答案約束模型，避免連續影像重建後位置抖動。",
            "舊模型常把單張圖修得銳利，但連續影像之間不一定穩定。",
        ),
        (
            "new_sequence_guard_via_real_crop",
            "sequence_guard",
            "via",
            "圓孔 sequence guard 真實 crop，用來讓孔洞邊界在連續影像中也不要亂漂。",
            "舊模型對孔洞與圓柱的穩定性不一定一致，容易造成位移讀值不對稱。",
        ),
    ]

    selections = []
    for key, role, kind, note, old_gap in specs:
        item, score = select_from_manifest(pairs, role, kind)
        selections.append(save_pair(key, role, kind, item, score, note, old_gap))
    selections.append(save_legacy_contrast(pairs))
    write_index(selections, overview_path, manifest)
    print(f"wrote {len(selections)} representative selections")
    print(f"image_dir={IMG_DIR}")
    print(f"index={OUT / 'training_data_representative_index.md'}")
    print(f"csv={OUT / 'selected_training_representatives.csv'}")


if __name__ == "__main__":
    main()
