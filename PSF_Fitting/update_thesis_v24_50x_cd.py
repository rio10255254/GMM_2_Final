from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import shutil

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu, Pt
PROJECT_ROOT = Path(__file__).resolve().parents[1]


SOURCE = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用"
    r"\論文完整版_20260716_v23_消融位移完整英文圖版.docx"
)
OUTPUT = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用"
    r"\論文完整版_20260716_v24_50倍CD校正驗證版.docx"
)
FIGURE_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/10_V23_50X_CD_PRESENTATION_CANDIDATES_20260727/figures')
)
FIGURE_WIDTH_EMU = 5_256_000


def clone_first_run_format(paragraph):
    if paragraph.runs and paragraph.runs[0]._r.rPr is not None:
        return deepcopy(paragraph.runs[0]._r.rPr)
    return None


def set_paragraph_text(paragraph, text):
    first_rpr = clone_first_run_format(paragraph)
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)
    run = paragraph.add_run(text)
    if first_rpr is not None:
        if run._r.rPr is not None:
            run._r.remove(run._r.rPr)
        run._r.insert(0, first_rpr)


def find_one_paragraph(document, prefix, style_name=None):
    matches = []
    for paragraph in document.paragraphs:
        if paragraph.text.startswith(prefix) and (
            style_name is None or paragraph.style.name == style_name
        ):
            matches.append(paragraph)
    assert len(matches) == 1, (prefix, style_name, len(matches))
    return matches[0]


def find_one_heading(document, prefix):
    matches = [
        paragraph
        for paragraph in document.paragraphs
        if paragraph.text.startswith(prefix)
        and paragraph.style.name.startswith("Heading")
    ]
    assert len(matches) == 1, (prefix, len(matches))
    return matches[0]


def renumber_existing_figures(document, start_number=57, increment=2):
    pattern = re.compile(r"(圖\s*6-)(\d+)")
    english_pattern = re.compile(r"((?:Figure|Fig\.)\s*6-)(\d+)", re.IGNORECASE)

    def replace(match):
        number = int(match.group(2))
        if number >= start_number:
            return f"{match.group(1)}{number + increment}"
        return match.group(0)

    # Cross-references are sometimes split across several Word runs (for
    # example, one run contains "圖 6-" and the next contains the number).
    # Work on the complete paragraph text in the chapter body so those cases
    # are renumbered as well.  The list of figures is updated later by Word.
    chapter_start = next(
        index
        for index, paragraph in enumerate(document.paragraphs)
        if paragraph.text.strip().startswith("6.1")
        and paragraph.style.name.startswith("Heading")
    )
    for paragraph in document.paragraphs[chapter_start:]:
        updated = pattern.sub(replace, paragraph.text)
        updated = english_pattern.sub(replace, updated)
        if updated != paragraph.text:
            set_paragraph_text(paragraph, updated)

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        updated = pattern.sub(replace, run.text)
                        updated = english_pattern.sub(replace, updated)
                        if updated != run.text:
                            run.text = updated


def insert_normal_before(reference, text):
    paragraph = reference.insert_paragraph_before(text)
    paragraph.style = "Normal"
    return paragraph


def insert_picture_before(reference, image_path):
    assert image_path.exists(), image_path
    paragraph = reference.insert_paragraph_before()
    paragraph.style = "Normal"
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run().add_picture(str(image_path), width=Emu(FIGURE_WIDTH_EMU))
    return paragraph


def insert_caption_before(reference, text):
    paragraph = reference.insert_paragraph_before(text)
    paragraph.style = "Figure Caption"
    return paragraph


def find_ablation_table(document):
    matches = []
    for table in document.tables:
        text = "\n".join(cell.text for row in table.rows for cell in row.cells)
        if "Anti-aliased upsampling" in text and "Raw-position anchor" in text:
            matches.append(table)
    assert len(matches) == 1, len(matches)
    return matches[0]


def set_cell_text(cell, text):
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    paragraph = cell.paragraphs[0]
    set_paragraph_text(paragraph, text)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)


def replace_table(table, header, rows):
    assert len(table.rows[0].cells) == len(header)
    for cell, value in zip(table.rows[0].cells, header):
        set_cell_text(cell, value)

    template = deepcopy(table.rows[-1]._tr)
    for row in list(table.rows)[1:]:
        table._tbl.remove(row._tr)
    for values in rows:
        table._tbl.append(deepcopy(template))
        for cell, value in zip(table.rows[-1].cells, values):
            set_cell_text(cell, value)


def format_compact_table(table):
    """Keep a long summary table readable without orphaning its caption."""
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = False
                paragraph.paragraph_format.line_spacing = 1.0
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    run.font.size = Pt(10.5 if row_index == 0 else 10)
                    if row_index == 0:
                        run.bold = True


def main():
    assert SOURCE.exists(), SOURCE
    shutil.copy2(SOURCE, OUTPUT)
    document = Document(OUTPUT)

    # Make room for two new 50x-CD figures without creating duplicate figure numbers.
    renumber_existing_figures(document, start_number=57, increment=2)

    locked_paragraph = find_one_paragraph(
        document,
        "為確認50倍CD結果未因量測規則而對抗混疊上取樣不利",
        "Normal",
    )
    set_paragraph_text(
        locked_paragraph,
        "前述位移結果顯示抗混疊上取樣可改善跨pillar的一致性，但固定門檻CD仍需分辨整體偏差與局部邊界誤差。"
        "在原先鎖定的35%至65%共同門檻與兩種剖面下，Raw、抗混疊上取樣與一般上取樣的50倍CD中位絕對誤差"
        "分別為96.34、80.35與77.54 nm，如圖6-57所示。兩種重建皆較Raw低，但抗混疊較一般上取樣高2.81 nm；"
        "此差距僅相當於50倍物體空間的0.041 pixel。兩個版本使用相同原圖、九顆pillar、SEM尺寸、量測中心、門檻、"
        "剖面與兩次固定初始化，因此該差距不是由比較條件不一致造成，而是抗混疊濾波使半高邊界產生微小且近似共同的外移。",
    )

    heading = find_one_heading(document, "6.2.6.2 ")
    insert_picture_before(
        heading, FIGURE_ROOT / "01_50x_cd_locked_protocol_with_raw.png"
    )
    insert_caption_before(
        heading,
        "圖 6-57 50倍Raw、抗混疊上取樣與一般上取樣在鎖定共同門檻下的CD中位絕對誤差。"
        "三種方法使用相同九顆pillar、SEM參考尺寸、量測中心、35%至65%門檻及水平與徑向剖面；數值越低越好。",
    )
    insert_normal_before(
        heading,
        "為評估移除共同偏差後的邊界定位能力，本研究另採徑向最大梯度法。首先將每顆pillar的徑向平均灰階剖面"
        "平滑1 pixel，再以灰階下降最快的位置定義外緣。量測第i顆pillar時，以其餘八顆pillar之光學量測值減去"
        "SEM參考值所得的中位數作為單一系統偏差，並從第i顆的光學CD扣除；被驗證pillar本身的SEM數值不參與"
        "該次校正。此留一顆驗證方式可避免直接使用待測答案修正自身，同時將共同尺寸偏移與逐顆邊界殘餘誤差分開。",
    )
    insert_picture_before(
        heading, FIGURE_ROOT / "02_50x_cd_bias_corrected_metrics.png"
    )
    insert_caption_before(
        heading,
        "圖 6-58 50倍最大梯度CD經留一顆驗證之單一偏差校正後的誤差比較。AE為絕對誤差，RMSE為均方根誤差；"
        "每次量測僅以其餘八顆pillar估計共同偏差，三項指標皆以數值越低為佳。",
    )
    insert_normal_before(
        heading,
        "校正後，抗混疊上取樣與一般上取樣的中位絕對誤差分別為15.24與15.74 nm，RMSE分別為26.63與"
        "27.05 nm，最大絕對誤差分別為61.89與63.28 nm，如圖6-58所示。抗混疊版本分別降低0.50、0.42與"
        "1.39 nm。為確認結果不是特定平滑參數造成，本研究另將平滑尺度設為0.75、1.0與1.5 pixel；抗混疊版本"
        "的RMSE依序為26.69、26.63與26.65 nm，一般上取樣則為27.13、27.05與26.98 nm，三種設定下方向一致。"
        "因此，抗混疊上取樣在未校正CD中呈現0.041 pixel的共同外移，但經單一系統偏差校正後，其逐顆邊界殘餘誤差較低。",
    )

    set_paragraph_text(
        find_one_paragraph(document, "兩項主要設計對應不同層級的量測問題。", "Normal"),
        "兩項主要設計對應不同層級的量測問題。抗混疊上取樣可降低逐步位移波動、不同pillar之間的位移分歧，"
        "以及相對PI平台實際回授位移的偏差。50倍未校正CD雖較一般上取樣高2.81 nm，但差距僅0.041 pixel，且"
        "兩種重建皆優於Raw；利用其餘八顆估計單一偏差後，抗混疊版本的中位絕對誤差、RMSE與最大絕對誤差均較低。"
        "這表示其主要影響是可校正的共同尺寸偏移，而非逐顆邊界關係遭到破壞。Raw位置錨定對合併位移指標的影響較小，"
        "主要用來維持最終輪廓與原始影像的位置關係，避免過度銳化造成邊緣壓縮與振鈴。消融結果因此分別將兩項設計"
        "連結至位移一致性與邊界保護，並以未校正CD、留一顆偏差校正、邊緣寬度及振鈴共同判讀。",
    )

    table_caption = find_one_paragraph(document, "表 6-12 ", "Table Caption")
    set_paragraph_text(
        table_caption,
        "表 6-12 兩項主要模型設計的配對式消融結果。抗混疊上取樣列依序比較抗混疊與一般上取樣；"
        "Raw位置錨定列則比較完整模型與移除該設計後的結果。",
    )
    rows = [
        ("Anti-aliased upsampling", "Step-displacement standard deviation", "8.450 vs 8.846 nm (-4.68%)", "Improved overall step stability"),
        ("Anti-aliased upsampling", "Within-grid disagreement", "6.828 vs 7.805 nm (-14.31%)", "Improved cross-position consistency"),
        ("Anti-aliased upsampling", "Command-referenced MAE", "6.590 vs 7.013 nm (-6.43%)", "Reduced feedback-referenced error"),
        ("Anti-aliased upsampling", "Uncorrected 50x median absolute CD error", "80.35 vs 77.54 nm (+2.81 nm; 0.041 px)", "Small common outward offset"),
        ("Anti-aliased upsampling", "Bias-corrected 50x CD", "Median AE: 15.24 vs 15.74 nm; RMSE: 26.63 vs 27.05 nm", "Lower residual error after scalar calibration"),
        ("Raw-position anchor", "Step-displacement standard deviation", "8.491 vs 8.214 nm (+3.26%)", "Not the primary source of step stability"),
        ("Raw-position anchor", "Within-grid disagreement", "6.958 vs 7.189 nm (-3.33%)", "Slightly preserved position consistency"),
        ("Raw-position anchor", "Command-referenced MAE", "6.696 vs 6.603 nm (+1.40%)", "Small pooled difference"),
        ("Raw-position anchor", "50x median absolute CD error", "78.54 vs 63.45 nm", "Interpret together with ringing"),
        ("Raw-position anchor", "20x median absolute CD error", "120.25 vs 209.19 nm", "Protected coarsely sampled boundaries"),
        ("Raw-position anchor", "50x / 20x outer ringing energy", "+246.16% / +392.37% after removal", "Suppressed oversharpening-induced ringing"),
    ]
    ablation_table = find_ablation_table(document)
    replace_table(
        ablation_table,
        ("Model design", "Primary metric", "Result", "Interpretation"),
        rows,
    )
    format_compact_table(ablation_table)

    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
