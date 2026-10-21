from __future__ import annotations

"""Create visual candidate sheets for slide-ready MOSR training-data examples.

The script reads only the two verified upstream training packages that feed the
V42 lineage: the original R55 scratch-training package and the R61 v16
boundary/motion package.  It does not alter either dataset.
"""

import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


EVIDENCE = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence")
DATA = EVIDENCE / "LabSystem_MOSR" / "Training_Data"
R55 = (
    DATA
    / "r55_source_style_rebuild"
    / "r53_realistic_dataset_calibration"
    / "r53_realistic_calibrated_train_6000"
)
R61 = (
    DATA
    / "r61_universal_boundary_generalization"
    / "hs100mg_basler"
    / "r61_universal_boundary_train_motion_texture_step_guard_v16"
)
OUTPUT = EVIDENCE / "Slide_Assets" / "Training_Data_Representatives"


def score(path: Path) -> float:
    """Prefer samples that retain both visible structure and source contrast."""
    image = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
    if image.size == 0:
        return -math.inf
    contrast = float(image.std())
    edges = float(np.mean(np.abs(np.diff(image, axis=0))) + np.mean(np.abs(np.diff(image, axis=1))))
    # Avoid near-empty or nearly saturated crops even if compression/noise raises an edge score.
    occupancy = 1.0 - abs(float(image.mean()) - 0.5) * 2.0
    return contrast * 2.0 + edges * 5.0 + occupancy * 0.25


def evenly_spaced_top(candidates: list[dict], count: int = 8) -> list[dict]:
    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    # Only retain the visually strongest third, then spread selections so they are not near duplicates.
    shortlist = ranked[: max(count * 3, len(ranked) // 3)]
    if len(shortlist) <= count:
        return shortlist
    positions = np.linspace(0, len(shortlist) - 1, count, dtype=int)
    return [shortlist[int(index)] for index in positions]


def find_r55(stage: str) -> list[dict]:
    src_dir = R55 / "src" / stage
    lbl_dir = R55 / "lbl" / stage
    result = []
    for src in src_dir.rglob("*.bmp"):
        lbl = lbl_dir / src.relative_to(src_dir)
        if lbl.exists():
            result.append(
                {
                    "source": "R55 scratch foundation",
                    "role": stage,
                    "src": src,
                    "lbl": lbl,
                    "score": score(src),
                }
            )
    return result


def find_r61(role: str, max_scan: int | None = None) -> list[dict]:
    manifest = json.loads((R61 / "manifest.json").read_text(encoding="utf-8"))
    matching = [pair for pair in manifest["pairs"] if pair.get("role") == role]
    if max_scan is not None and len(matching) > int(max_scan):
        indices = np.linspace(0, len(matching) - 1, int(max_scan), dtype=int)
        matching = [matching[int(index)] for index in indices]
    result = []
    for pair in matching:
        src = R61 / pair["package_src"]
        lbl = R61 / pair["package_lbl"]
        if src.exists() and lbl.exists():
            result.append(
                {
                    "source": "R61 precision refinement",
                    "role": role,
                    "src": src,
                    "lbl": lbl,
                    "score": score(src),
                }
            )
    return result


def draw_sheet(name: str, items: list[dict]) -> None:
    font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 17)
    small_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 13)
    tile = 220
    header = 32
    footer = 25
    gap = 12
    columns = 2
    rows = len(items)
    width = columns * tile + (columns + 1) * gap
    height = rows * (tile + header + footer) + (rows + 1) * gap
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    for row, item in enumerate(items):
        y = gap + row * (tile + header + footer + gap)
        draw.text((gap, y), f"{row + 1}. {item['role']}", fill="black", font=font)
        for col, key in enumerate(("src", "lbl")):
            image = Image.open(item[key]).convert("L")
            image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
            x = gap + col * (tile + gap) + (tile - image.width) // 2
            image_y = y + header + (tile - image.height) // 2
            canvas.paste(image.convert("RGB"), (x, image_y))
            label = "Source image" if key == "src" else "Training label"
            draw.text((gap + col * (tile + gap), y + header + tile + 3), label, fill="black", font=small_font)
    canvas.save(OUTPUT / "candidate_sheets" / f"{name}.png", optimize=True)


def copy_selection(section: str, name: str, item: dict) -> dict:
    dest = OUTPUT / "selected" / section / name
    dest.mkdir(parents=True, exist_ok=True)
    src_dest = dest / "01_source.png"
    lbl_dest = dest / "02_training_label.png"
    Image.open(item["src"]).convert("L").save(src_dest, optimize=True)
    Image.open(item["lbl"]).convert("L").save(lbl_dest, optimize=True)
    return {
        "section": section,
        "name": name,
        "training_stage": item["source"],
        "role": item["role"],
        "original_source": str(item["src"]),
        "original_label": str(item["lbl"]),
        "slide_files": {"source": str(src_dest), "label": str(lbl_dest)},
    }


def draw_slide_panel(filename: str, title: str, items: list[tuple[str, dict]]) -> None:
    """Make a clean 16:9-friendly strip: three source/label pairs in one row."""
    font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 28)
    small = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 18)
    tile = 250
    group_gap = 30
    inner_gap = 10
    margin = 28
    top = 82
    width = margin * 2 + 3 * (tile * 2 + inner_gap) + 2 * group_gap
    height = top + tile + 42 + margin
    panel = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(panel)
    draw.text((margin, 26), title, fill="black", font=font)
    for i, (caption, item) in enumerate(items):
        group_x = margin + i * (tile * 2 + inner_gap + group_gap)
        draw.text((group_x, top - 25), caption, fill="black", font=small)
        for j, key in enumerate(("src", "lbl")):
            image = Image.open(item[key]).convert("L")
            image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
            x = group_x + j * (tile + inner_gap) + (tile - image.width) // 2
            y = top + (tile - image.height) // 2
            panel.paste(image.convert("RGB"), (x, y))
            draw.text(
                (group_x + j * (tile + inner_gap), top + tile + 9),
                "Source" if key == "src" else "Label",
                fill="black",
                font=small,
            )
    panel_dir = OUTPUT / "slide_panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    panel.save(panel_dir / filename, optimize=True)


def draw_choice_sheet(filename: str, title: str, items: list[tuple[str, dict]]) -> None:
    """Create a compact six-pair review sheet for optional slide substitutions."""
    font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 28)
    small = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 18)
    tile = 220
    group_gap = 28
    row_gap = 34
    inner_gap = 10
    margin = 28
    top = 82
    columns = 3
    rows = math.ceil(len(items) / columns)
    group_width = tile * 2 + inner_gap
    group_height = tile + 46
    width = margin * 2 + columns * group_width + (columns - 1) * group_gap
    height = top + rows * group_height + (rows - 1) * row_gap + margin
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 26), title, fill="black", font=font)
    for index, (caption, item) in enumerate(items):
        row, col = divmod(index, columns)
        group_x = margin + col * (group_width + group_gap)
        y = top + row * (group_height + row_gap)
        draw.text((group_x, y - 25), caption, fill="black", font=small)
        for j, key in enumerate(("src", "lbl")):
            image = Image.open(item[key]).convert("L")
            image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
            x = group_x + j * (tile + inner_gap) + (tile - image.width) // 2
            image_y = y + (tile - image.height) // 2
            sheet.paste(image.convert("RGB"), (x, image_y))
            draw.text(
                (group_x + j * (tile + inner_gap), y + tile + 8),
                "Source" if key == "src" else "Label",
                fill="black",
                font=small,
            )
    panel_dir = OUTPUT / "slide_panels"
    panel_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(panel_dir / filename, optimize=True)


def main() -> None:
    candidate_dir = OUTPUT / "candidate_sheets"
    candidate_dir.mkdir(parents=True, exist_ok=True)

    pools = {
        "01_r55_boundary_mixed": find_r55("stage_40_boundary_mixed"),
        "02_r61_universal_shapes": find_r61("universal_synthetic"),
        "03_r61_textured_motion": find_r61("motion_texture_synthetic"),
        "04_r61_step_motion": find_r61("step_guard_motion_texture_synthetic"),
        "05_r61_sem_reference": find_r61("sem_truth_anchor"),
        "06_r61_sequence_guard": find_r61("sequence_guard"),
        "08_r61_clean_motion": find_r61("motion_synthetic", max_scan=600),
    }
    diverse_r55_stages = [
        "stage_01_triangles",
        "stage_02_circles",
        "stage_03_rectangles",
        "stage_04_ellipses",
        "stage_05_polygons",
        "stage_06_mixed_simple",
        "stage_07_mixed_complex",
        "stage_29_micro_lines_grid",
        "stage_30_micro_large_regions",
        "stage_31_micro_textures",
        "stage_32_micro_edge_defects",
        "stage_33_micro_mixed_fields",
    ]
    pools["07_r55_diverse_foundation"] = [
        evenly_spaced_top(find_r55(stage), count=1)[0]
        for stage in diverse_r55_stages
        if find_r55(stage)
    ]
    selections = {}
    for name, pool in pools.items():
        picks = pool if name == "07_r55_diverse_foundation" else evenly_spaced_top(pool)
        if not picks:
            raise RuntimeError(f"No valid pairs found for {name}")
        selections[name] = picks
        draw_sheet(name, picks)

    chosen = [
        ("foundation", "mixed_boundaries", "01_r55_boundary_mixed", 4, "Mixed boundary fields"),
        ("foundation", "universal_shapes", "02_r61_universal_shapes", 3, "Multi-shape fields"),
        ("foundation", "textured_motion", "03_r61_textured_motion", 2, "Textured motion"),
        ("precision", "step_motion", "04_r61_step_motion", 8, "Step-motion guard"),
        ("precision", "sem_reference", "05_r61_sem_reference", 8, "SEM-referenced patches"),
        ("precision", "sequence_guard", "06_r61_sequence_guard", 1, "Sequence consistency"),
    ]
    final_records = []
    panel_items: dict[str, list[tuple[str, dict]]] = {"foundation": [], "precision": []}
    for section, name, category, one_based_index, caption in chosen:
        item = selections[category][one_based_index - 1]
        final_records.append(copy_selection(section, name, item))
        panel_items[section].append((caption, item))
    draw_slide_panel(
        "01_foundation_training_examples.png",
        "Foundation training data: broad boundary and motion capability",
        panel_items["foundation"],
    )
    draw_slide_panel(
        "02_precision_refinement_examples.png",
        "Precision refinement data: controlled motion and geometry anchoring",
        panel_items["precision"],
    )

    alternatives = [
        ("foundation", "soft_checkerboard_blur", "01_r55_boundary_mixed", 1, "Soft checkerboard blur"),
        ("foundation", "real_background_boundary", "01_r55_boundary_mixed", 3, "Real background boundary"),
        ("foundation", "rotated_corner_field", "01_r55_boundary_mixed", 7, "Rotated corner field"),
        ("foundation", "annular_structure", "02_r61_universal_shapes", 7, "Annular structure"),
        ("foundation", "bright_textured_geometry", "03_r61_textured_motion", 1, "Bright textured geometry"),
        ("foundation", "dark_line_circle", "03_r61_textured_motion", 8, "Dark line-circle geometry"),
        ("precision", "bright_step_motion", "04_r61_step_motion", 1, "Bright step motion"),
        ("precision", "touching_ellipses", "04_r61_step_motion", 2, "Touching ellipses"),
        ("precision", "circle_bar_step", "04_r61_step_motion", 5, "Circle-bar step"),
        ("precision", "sem_via_anchor", "05_r61_sem_reference", 1, "SEM-referenced via"),
        ("precision", "real_pillar_field", "05_r61_sem_reference", 4, "Real pillar field"),
        ("precision", "via_sequence_variant", "06_r61_sequence_guard", 5, "Via sequence variant"),
    ]
    alternative_records = []
    alternative_items: dict[str, list[tuple[str, dict]]] = {"foundation": [], "precision": []}
    for section, name, category, one_based_index, caption in alternatives:
        item = selections[category][one_based_index - 1]
        alternative_records.append(copy_selection(f"alternatives/{section}", name, item))
        alternative_items[section].append((caption, item))
    draw_choice_sheet(
        "03_foundation_alternative_examples.png",
        "Additional foundation examples",
        alternative_items["foundation"],
    )
    draw_choice_sheet(
        "04_precision_refinement_alternative_examples.png",
        "Additional precision-refinement examples",
        alternative_items["precision"],
    )

    expanded_foundation = [
        ("triangles", "07_r55_diverse_foundation", 1, "Triangles and crossing edges"),
        ("circles", "07_r55_diverse_foundation", 2, "Multi-scale circles"),
        ("rectangles", "07_r55_diverse_foundation", 3, "Rectangles and thin lines"),
        ("ellipses", "07_r55_diverse_foundation", 4, "Multi-scale ellipses"),
        ("polygons", "07_r55_diverse_foundation", 5, "Overlapping polygons"),
        ("mixed_complex", "07_r55_diverse_foundation", 7, "Complex mixed geometry"),
        ("mixed_simple", "07_r55_diverse_foundation", 6, "Mixed rings and polygons"),
        ("micro_lines_grid", "07_r55_diverse_foundation", 8, "Fine line grid"),
        ("micro_large_region", "07_r55_diverse_foundation", 9, "Large-region boundary"),
        ("micro_texture", "07_r55_diverse_foundation", 10, "Texture preservation"),
        ("micro_edge_defect", "07_r55_diverse_foundation", 11, "Edge defects"),
        ("micro_mixed_field", "07_r55_diverse_foundation", 12, "Mixed microstructure field"),
    ]
    foundation_records = []
    foundation_panels: list[list[tuple[str, dict]]] = [[], []]
    for index, (name, category, one_based_index, caption) in enumerate(expanded_foundation):
        item = selections[category][one_based_index - 1]
        foundation_records.append(copy_selection("expanded_foundation", name, item))
        foundation_panels[index // 6].append((caption, item))
    draw_choice_sheet(
        "05_foundation_shape_choices.png",
        "Expanded foundation choices: diverse shapes",
        foundation_panels[0],
    )
    draw_choice_sheet(
        "06_foundation_microstructure_choices.png",
        "Expanded foundation choices: microstructure and boundaries",
        foundation_panels[1],
    )

    expanded_precision_synthetic = [
        ("clean_circle_bar", "08_r61_clean_motion", 1, "Clean circle-bar motion"),
        ("clean_touching_ellipses", "08_r61_clean_motion", 2, "Clean touching ellipses"),
        ("clean_dark_mixed", "08_r61_clean_motion", 3, "Clean dark mixed motion"),
        ("clean_dark_ellipse_mixed", "08_r61_clean_motion", 4, "Clean dark ellipse field"),
        ("clean_dark_line_circle", "08_r61_clean_motion", 6, "Clean dark line-circle"),
        ("clean_circle_polygon", "08_r61_clean_motion", 8, "Clean circle-polygon motion"),
        ("textured_bright_circle_bar", "03_r61_textured_motion", 1, "Textured bright circle-bar"),
        ("textured_dark_mixed", "03_r61_textured_motion", 2, "Textured dark mixed field"),
        ("textured_ellipses", "03_r61_textured_motion", 5, "Textured ellipse motion"),
        ("step_bright_polygon", "04_r61_step_motion", 1, "Step-like polygon motion"),
        ("step_touching_ellipses", "04_r61_step_motion", 2, "Step-like touching ellipses"),
        ("step_dark_annulus", "04_r61_step_motion", 8, "Step-like dark annulus"),
    ]
    precision_synthetic_records = []
    precision_synthetic_panels: list[list[tuple[str, dict]]] = [[], []]
    for index, (name, category, one_based_index, caption) in enumerate(expanded_precision_synthetic):
        item = selections[category][one_based_index - 1]
        precision_synthetic_records.append(copy_selection("expanded_precision_synthetic", name, item))
        precision_synthetic_panels[index // 6].append((caption, item))
    draw_choice_sheet(
        "07_synthetic_precision_clean_motion_choices.png",
        "Synthetic precision-refinement choices: known clean motion",
        precision_synthetic_panels[0],
    )
    draw_choice_sheet(
        "08_synthetic_precision_texture_step_choices.png",
        "Synthetic precision-refinement choices: texture and step motion",
        precision_synthetic_panels[1],
    )

    # These are placeholders that will be filled only after visual review.
    index = {
        "purpose": "Candidate sheets for manual visual selection of slide examples.",
        "candidate_categories": {
            name: [
                {
                    "source": str(item["src"]),
                    "label": str(item["lbl"]),
                    "role": item["role"],
                    "visual_score": round(item["score"], 6),
                }
                for item in items
            ]
            for name, items in selections.items()
        },
    }
    (OUTPUT / "candidate_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT / "selected_examples.json").write_text(
        json.dumps(final_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT / "alternative_examples.json").write_text(
        json.dumps(alternative_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT / "expanded_synthetic_choices.json").write_text(
        json.dumps(
            {
                "foundation": foundation_records,
                "precision_synthetic_only": precision_synthetic_records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
