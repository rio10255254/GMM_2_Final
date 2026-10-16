from copy import deepcopy
from pathlib import Path
import shutil

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu


SOURCE = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v21_位移標準差表格版.docx")
OUTPUT = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v22_消融圖表重整版.docx")
FIGURE_DIR = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\08_V22_ABLATION_REDESIGN_20260727\figures")
FIGURE_WIDTH_EMU = 5_256_000


CAPTIONS = {
    "圖 6-51 ": (
        FIGURE_DIR / "01_shift_safe_within_grid_absolute.png",
        "圖 6-51 抗混疊與一般上取樣之九顆pillar位移離散度。柱高為兩次固定初始化的平均值，"
        "誤差棒表示兩次結果的範圍；數值越低表示同一影格內九顆pillar的位移估測越一致。",
    ),
    "圖 6-52 ": (
        FIGURE_DIR / "02_shift_safe_command_mae_absolute.png",
        "圖 6-52 抗混疊與一般上取樣相對PI平台回授的位移平均絕對偏差。柱高與誤差棒分別表示"
        "兩次固定初始化的平均值及結果範圍；數值越低越好。",
    ),
    "圖 6-57 ": (
        FIGURE_DIR / "03_raw_anchor_displacement_both_metrics.png",
        "圖 6-57 完整模型與移除Raw位置錨定後的位移量測比較。（a）九顆pillar位移離散度；"
        "（b）相對PI平台回授的平均絕對偏差。柱高為兩次固定初始化的平均值，誤差棒表示兩次結果的範圍；數值越低越好。",
    ),
    "圖 6-58 ": (
        FIGURE_DIR / "05_raw_anchor_per_pillar_both_magnifications.png",
        "圖 6-58 完整模型與移除Raw位置錨定後的逐顆pillar CD絕對誤差中位數。"
        "（a）50倍；（b）20倍。線條為兩次固定初始化的平均值，誤差棒表示兩次結果的範圍。",
    ),
}


def set_paragraph_text(paragraph, text):
    first_rpr = None
    if paragraph.runs and paragraph.runs[0]._r.rPr is not None:
        first_rpr = deepcopy(paragraph.runs[0]._r.rPr)
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)
    run = paragraph.add_run(text)
    if first_rpr is not None:
        if run._r.rPr is not None:
            run._r.remove(run._r.rPr)
        run._r.insert(0, first_rpr)


def replace_picture(paragraph, image_path):
    assert image_path.exists(), image_path
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)
    run = paragraph.add_run()
    run.add_picture(str(image_path), width=Emu(FIGURE_WIDTH_EMU))
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def body_caption(document, prefix):
    matches = [
        (i, p)
        for i, p in enumerate(document.paragraphs)
        if p.style.name == "Figure Caption" and p.text.startswith(prefix)
    ]
    assert len(matches) == 1, (prefix, len(matches))
    return matches[0]


def normal_paragraph_starting(document, prefix):
    matches = [p for p in document.paragraphs if p.style.name == "Normal" and p.text.startswith(prefix)]
    assert len(matches) == 1, (prefix, len(matches))
    return matches[0]


def heading_starting(document, prefix):
    matches = [p for p in document.paragraphs if p.text.startswith(prefix) and p.style.name.startswith("Heading")]
    assert len(matches) == 1, (prefix, len(matches))
    return matches[0]


def find_ablation_table(document):
    matches = []
    for table in document.tables:
        text = "\n".join(cell.text for row in table.rows for cell in row.cells)
        if "九顆pillar位移離散度" in text and "原始影像位置基準" in text:
            matches.append(table)
    assert len(matches) == 1, len(matches)
    return matches[0]


def replace_table_rows(table, rows):
    template = deepcopy(table.rows[-1]._tr)
    for row in list(table.rows)[1:]:
        table._tbl.remove(row._tr)
    for values in rows:
        table._tbl.append(deepcopy(template))
        row = table.rows[-1]
        for cell, value in zip(row.cells, values):
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            set_paragraph_text(p, value)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for extra in cell.paragraphs[1:]:
                extra._element.getparent().remove(extra._element)


def insert_normal_before(reference_paragraph, text):
    p = reference_paragraph.insert_paragraph_before(text)
    p.style = "Normal"
    return p


def main():
    assert SOURCE.exists(), SOURCE
    shutil.copy2(SOURCE, OUTPUT)
    document = Document(OUTPUT)

    # Replace each figure while preserving the original caption/image width and document style.
    for prefix, (image_path, caption_text) in CAPTIONS.items():
        index, caption = body_caption(document, prefix)
        image_paragraph = document.paragraphs[index - 1]
        assert image_paragraph._p.xpath(".//a:blip"), prefix
        replace_picture(image_paragraph, image_path)
        set_paragraph_text(caption, caption_text)

    set_paragraph_text(
        normal_paragraph_starting(document, "消融實驗與前節位移改善結果分開呈現。"),
        "消融實驗與前節位移改善結果分開呈現。各消融條件固定起始權重、資料切分、PSF、訓練預算與評估影格，"
        "只改變待檢查的模型設計。抗混疊上取樣與Raw位置錨定均使用50倍與20倍、0.5 µm與1.0 µm四組30步序列"
        "評估位移量測；Raw位置錨定另以兩種倍率九顆pillar的CD、邊緣寬度與振鈴共同檢查邊界。圖中的範圍來自"
        "兩次固定初始化，用來判斷效果方向是否可重現。完整模型與移除Raw位置錨定的P29同位置輸出如圖6-50所示。",
    )

    set_paragraph_text(
        normal_paragraph_starting(document, "四組序列合併後，一般上取樣使"),
        "圖6-51與圖6-52改以完整數值呈現兩種上取樣方式。抗混疊上取樣在四組序列皆得到較低的九顆pillar位移離散度；"
        "四組合併值由一般上取樣的7.81 nm降至6.83 nm，降低0.977 nm（14.31%）。相對PI平台回授的平均絕對偏差"
        "則由7.01 nm降至6.59 nm，降低0.424 nm（6.43%）。兩次固定初始化的合併結果方向一致，逐步位移曲線如"
        "圖6-53至圖6-56所示，支持抗混疊上取樣主要改善跨pillar的相對位置一致性。",
    )

    set_paragraph_text(
        heading_starting(document, "6.2.6.2 "),
        "6.2.6.2 原始影像位置錨定與邊界保護",
    )

    # Add a direct explanation between the new displacement chart and the per-pillar CD chart.
    fig58_index, fig58_caption = body_caption(document, "圖 6-58 ")
    fig58_image_paragraph = document.paragraphs[fig58_index - 1]
    insert_normal_before(
        fig58_image_paragraph,
        "四組序列合併後，移除Raw位置錨定使九顆pillar位移離散度由6.96 nm增至7.19 nm，增加0.231 nm（3.33%）；"
        "相對PI平台回授的平均絕對偏差則由6.70 nm降至6.60 nm，差異為0.094 nm（1.40%）。各序列的變化方向並不完全一致，"
        "因此Raw位置錨定不是位移穩定性的主要來源；其主要功能仍是限制重建邊界偏離原始影像。",
    )

    set_paragraph_text(
        normal_paragraph_starting(document, "移除以原始影像為基準的殘差輸出後，"),
        "移除Raw位置錨定後，20倍pillar的CD中位絕對誤差由120.25 nm增至209.19 nm，增加88.94 nm（73.97%）；"
        "50倍則由78.54 nm降至63.45 nm，表面上減少15.09 nm（19.22%）。但50倍的10–90%邊緣寬度同時縮減"
        "538.63 nm（90.40%），外圍振鈴能量增加246.16%；20倍的外圍振鈴能量亦增加392.37%。因此50倍的CD誤差下降"
        "不能單獨視為邊界還原更準確，而是伴隨明顯的邊緣壓縮與振鈴。綜合兩種倍率可知，Raw位置錨定可避免模型以過度銳化"
        "換取較低的單一CD數值，其CD精度效益在取樣較粗的20倍影像最明顯。",
    )

    table_caption = [
        p for p in document.paragraphs
        if p.style.name == "Table Caption" and p.text.startswith("表 6-12 ")
    ]
    assert len(table_caption) == 1
    set_paragraph_text(
        table_caption[0],
        "表 6-12 兩項主要模型設計的配對式消融結果。變化量為替換或移除設計後減去完整模型；正值表示該指標增加。",
    )

    rows = [
        ("抗混疊上取樣", "九顆pillar位移離散度", "+0.977 nm（+14.31%）", "改善跨位置一致性"),
        ("抗混疊上取樣", "位移平均絕對偏差", "+0.424 nm（+6.43%）", "降低平台回授偏差"),
        ("Raw位置錨定", "九顆pillar位移離散度", "+0.231 nm（+3.33%）", "小幅維持位置一致性"),
        ("Raw位置錨定", "位移平均絕對偏差", "−0.094 nm（−1.40%）", "合併差異較小"),
        ("Raw位置錨定", "50倍CD中位絕對誤差", "−15.09 nm（−19.22%）", "須與振鈴共同判讀"),
        ("Raw位置錨定", "20倍CD中位絕對誤差", "+88.94 nm（+73.97%）", "保護粗取樣邊界"),
        ("Raw位置錨定", "50倍／20倍外圍振鈴能量", "+246.16%／+392.37%", "抑制過度銳化振鈴"),
    ]
    replace_table_rows(find_ablation_table(document), rows)

    set_paragraph_text(
        normal_paragraph_starting(document, "兩項主要設計對應不同層級的量測問題："),
        "兩項主要設計對應不同層級的量測問題。抗混疊上取樣對位移量測的作用最明確，可降低不同pillar之間的位移分歧，"
        "並減少相對PI平台回授的偏差；Raw位置錨定對合併位移指標的影響較小，主要用來維持最終輪廓與原始影像的位置關係，"
        "避免過度銳化造成邊緣壓縮與振鈴。消融結果因此分別將兩項設計連結至位移一致性與邊界保護，並以CD、邊緣寬度及振鈴"
        "的共同判讀避免單一數值造成誤解。",
    )

    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
