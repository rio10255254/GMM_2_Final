from copy import deepcopy
from pathlib import Path
import shutil

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Emu


SOURCE = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用"
    r"\論文完整版_20260716_v22_消融圖表重整版.docx"
)
OUTPUT = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用"
    r"\論文完整版_20260716_v23_消融位移完整英文圖版.docx"
)
FIGURE_DIR = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\09_V23_ABLATION_COMPLETE_ENGLISH_20260727\figures"
)
FIGURE_WIDTH_EMU = 5_256_000


CAPTIONS = {
    "圖 6-51 ": (
        FIGURE_DIR / "01_shift_safe_step_sd_absolute.png",
        "圖 6-51 抗混疊與一般上取樣之逐步位移標準差。柱高為兩次固定初始化的平均值，"
        "誤差棒表示兩次結果的範圍；數值越低表示相鄰步驟的位移量測越穩定。",
    ),
    "圖 6-52 ": (
        FIGURE_DIR / "02_shift_safe_position_metrics_absolute.png",
        "圖 6-52 抗混疊與一般上取樣之位置量測比較。（a）同一影格九顆pillar的位移離散度；"
        "（b）相對PI平台實際回授位移的平均絕對誤差。柱高為兩次固定初始化的平均值，"
        "誤差棒表示兩次結果的範圍；兩項指標皆以數值越低為佳。",
    ),
    "圖 6-53 ": (
        FIGURE_DIR / "03_50x_x_0p5um_upsampling_step_trace.png",
        "圖 6-53 50倍、0.5 µm序列中抗混疊與一般上取樣的30步位移比較。"
        "實線為兩次固定初始化的平均值，陰影表示兩次結果的範圍，虛線為PI平台實際回授位移。",
    ),
    "圖 6-54 ": (
        FIGURE_DIR / "04_50x_x_1um_upsampling_step_trace.png",
        "圖 6-54 50倍、1.0 µm序列中抗混疊與一般上取樣的30步位移比較。"
        "實線為兩次固定初始化的平均值，陰影表示兩次結果的範圍，虛線為PI平台實際回授位移。",
    ),
    "圖 6-55 ": (
        FIGURE_DIR / "05_20x_0p5um_upsampling_step_trace.png",
        "圖 6-55 20倍、0.5 µm序列中抗混疊與一般上取樣的30步位移比較。"
        "實線為兩次固定初始化的平均值，陰影表示兩次結果的範圍，虛線為PI平台實際回授位移。",
    ),
    "圖 6-56 ": (
        FIGURE_DIR / "06_20x_1um_upsampling_step_trace.png",
        "圖 6-56 20倍、1.0 µm序列中抗混疊與一般上取樣的30步位移比較。"
        "實線為兩次固定初始化的平均值，陰影表示兩次結果的範圍，虛線為PI平台實際回授位移。",
    ),
    "圖 6-57 ": (
        FIGURE_DIR / "07_raw_anchor_displacement_three_metrics.png",
        "圖 6-57 完整模型與移除Raw位置錨定後的位移量測比較。（a）逐步位移標準差；"
        "（b）九顆pillar位移離散度；（c）相對PI平台實際回授位移的平均絕對誤差。"
        "柱高為兩次固定初始化的平均值，誤差棒表示兩次結果的範圍。",
    ),
    "圖 6-58 ": (
        FIGURE_DIR / "08_raw_anchor_per_pillar_both_magnifications.png",
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
    matches = [
        p
        for p in document.paragraphs
        if p.style.name == "Normal" and p.text.startswith(prefix)
    ]
    assert len(matches) == 1, (prefix, len(matches))
    return matches[0]


def heading_starting(document, prefix):
    matches = [
        p
        for p in document.paragraphs
        if p.text.startswith(prefix) and p.style.name.startswith("Heading")
    ]
    assert len(matches) == 1, (prefix, len(matches))
    return matches[0]


def find_ablation_table(document):
    matches = []
    for table in document.tables:
        text = "\n".join(cell.text for row in table.rows for cell in row.cells)
        if "九顆pillar位移離散度" in text and "Raw位置錨定" in text:
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
            paragraph = cell.paragraphs[0]
            set_paragraph_text(paragraph, value)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for extra in cell.paragraphs[1:]:
                extra._element.getparent().remove(extra._element)


def replace_table_header(table, values):
    assert len(table.rows[0].cells) == len(values)
    for cell, value in zip(table.rows[0].cells, values):
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        set_paragraph_text(paragraph, value)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER


def insert_normal_before(reference_paragraph, text):
    paragraph = reference_paragraph.insert_paragraph_before(text)
    paragraph.style = "Normal"
    return paragraph


def main():
    assert SOURCE.exists(), SOURCE
    shutil.copy2(SOURCE, OUTPUT)
    document = Document(OUTPUT)

    for prefix, (image_path, caption_text) in CAPTIONS.items():
        index, caption = body_caption(document, prefix)
        image_paragraph = document.paragraphs[index - 1]
        assert image_paragraph._p.xpath(".//a:blip"), prefix
        replace_picture(image_paragraph, image_path)
        set_paragraph_text(caption, caption_text)

    set_paragraph_text(
        normal_paragraph_starting(document, "消融實驗與前節位移改善結果分開呈現。"),
        "消融實驗與前節位移改善結果分開呈現。各消融條件固定起始權重、資料切分、PSF、訓練預算與評估影格，"
        "只改變待檢查的模型設計。抗混疊上取樣與Raw位置錨定均使用50倍與20倍、0.5 µm與1.0 µm四組30步序列，"
        "並同時計算逐步位移標準差、九顆pillar位移離散度，以及相對PI平台實際回授位移的平均絕對誤差。"
        "Raw位置錨定另以兩種倍率九顆pillar的CD、邊緣寬度與振鈴共同檢查邊界。圖中誤差棒或陰影來自兩次固定初始化，"
        "用來檢查效果方向是否可重現。完整模型與移除Raw位置錨定的P29同位置輸出如圖6-50所示。",
    )

    set_paragraph_text(
        normal_paragraph_starting(document, "圖6-51與圖6-52改以完整數值呈現兩種上取樣方式。"),
        "圖6-51與圖6-52分別呈現逐步穩定度與位置一致性。四序列合併後，抗混疊上取樣使逐步位移標準差"
        "由8.846 nm降至8.450 nm，降低0.395 nm（4.68%）；九顆pillar位移離散度由7.805 nm降至6.828 nm，"
        "降低0.977 nm（14.31%）；相對PI平台實際回授位移的平均絕對誤差由7.013 nm降至6.590 nm，降低"
        "0.424 nm（6.43%）。其中逐步位移標準差在四組序列中有三組的平均值較低，50倍、1.0 µm序列則小幅增加"
        "0.123 nm；另外兩項位置指標在四組序列皆較低。圖6-53至圖6-56顯示完整30步變化，因此抗混疊上取樣的"
        "主要效益是降低跨pillar的位置分歧，並在整體上改善逐步穩定度。",
    )

    insert_normal_before(
        heading_starting(document, "6.2.6.2 "),
        "為確認50倍CD結果未因量測規則而對抗混疊上取樣不利，本研究另外核對兩個版本的原始影像、九顆pillar編號、"
        "SEM參考尺寸、量測中心、35%至65%共同門檻、水平與徑向兩種剖面及兩次固定初始化。每次初始化皆有126筆"
        "一一對應且有效的50倍量測，顯示比較條件一致。抗混疊與一般上取樣的50倍CD中位絕對誤差分別為80.35 nm"
        "與77.54 nm，相差2.81 nm，僅約為50倍物體空間0.041 pixel。分別使用水平剖面、徑向剖面、50%門檻或"
        "45%至55%中央門檻時，差異方向均相同，說明結果不是由特定剖面或門檻偏置造成。兩種方法皆略為高估直徑，"
        "抗混疊固定濾波使半高邊界向外移動極小距離；相對而言，抗混疊對位移離散度的改善更大且是此設計的主要用途。",
    )

    set_paragraph_text(
        normal_paragraph_starting(document, "四組序列合併後，移除Raw位置錨定使"),
        "圖6-57顯示Raw位置錨定對三項位移指標的影響。四組序列合併後，移除該設計使逐步位移標準差由8.491 nm"
        "降至8.214 nm，差異為0.277 nm（3.26%）；九顆pillar位移離散度由6.958 nm增至7.189 nm，增加"
        "0.231 nm（3.33%）；相對PI平台實際回授位移的平均絕對誤差則由6.696 nm降至6.603 nm，差異為"
        "0.094 nm（1.40%）。三項指標的變化方向並不一致，且幅度均小於抗混疊上取樣帶來的主要改善，因此Raw位置"
        "錨定不被視為位移穩定性的主要來源；其主要作用仍是限制重建邊界偏離原始影像。",
    )

    set_paragraph_text(
        normal_paragraph_starting(document, "移除Raw位置錨定後，20倍pillar的CD中位絕對誤差"),
        "圖6-58進一步顯示逐顆pillar的CD結果。移除Raw位置錨定後，20倍pillar的CD中位絕對誤差由120.25 nm"
        "增至209.19 nm，增加88.94 nm（73.97%）；50倍則由78.54 nm降至63.45 nm，表面上減少15.09 nm"
        "（19.22%）。然而50倍的10–90%邊緣寬度同時縮減538.63 nm（90.40%），外圍振鈴能量增加246.16%；"
        "20倍外圍振鈴能量亦增加392.37%。因此50倍的單一CD誤差下降伴隨明顯邊緣壓縮與振鈴，不能單獨解讀為"
        "邊界還原較準確。綜合兩種倍率，Raw位置錨定可避免模型以過度銳化換取較低的單一CD數值，其邊界保護效果在"
        "取樣較粗的20倍影像最明顯。",
    )

    table_caption = [
        paragraph
        for paragraph in document.paragraphs
        if paragraph.style.name == "Table Caption" and paragraph.text.startswith("表 6-12 ")
    ]
    assert len(table_caption) == 1
    set_paragraph_text(
        table_caption[0],
        "表 6-12 兩項主要模型設計的配對式消融結果。變化量為以一般上取樣替換抗混疊上取樣，"
        "或移除Raw位置錨定後的結果減去參考模型；正值表示該指標增加。",
    )

    rows = [
        ("Anti-aliased upsampling", "Step-displacement standard deviation", "+0.395 nm (+4.68%)", "Improved overall step stability"),
        ("Anti-aliased upsampling", "Within-grid disagreement", "+0.977 nm (+14.31%)", "Improved cross-position consistency"),
        ("Anti-aliased upsampling", "Command-referenced MAE", "+0.424 nm (+6.43%)", "Reduced feedback-referenced error"),
        ("Anti-aliased upsampling", "50x median absolute CD error", "-2.811 nm (-3.50%)", "Difference was only 0.041 pixel"),
        ("Raw-position anchor", "Step-displacement standard deviation", "-0.277 nm (-3.26%)", "Not the primary source of step stability"),
        ("Raw-position anchor", "Within-grid disagreement", "+0.231 nm (+3.33%)", "Slightly preserved position consistency"),
        ("Raw-position anchor", "Command-referenced MAE", "-0.094 nm (-1.40%)", "Small pooled difference"),
        ("Raw-position anchor", "50x median absolute CD error", "-15.09 nm (-19.22%)", "Interpret together with ringing"),
        ("Raw-position anchor", "20x median absolute CD error", "+88.94 nm (+73.97%)", "Protected coarsely sampled boundaries"),
        ("Raw-position anchor", "50x / 20x outer ringing energy", "+246.16% / +392.37%", "Suppressed oversharpening-induced ringing"),
    ]
    ablation_table = find_ablation_table(document)
    replace_table_header(ablation_table, ("Model design", "Primary metric", "Change", "Interpretation"))
    replace_table_rows(ablation_table, rows)

    set_paragraph_text(
        normal_paragraph_starting(document, "兩項主要設計對應不同層級的量測問題。"),
        "兩項主要設計對應不同層級的量測問題。抗混疊上取樣對位移量測的作用最明確，可降低逐步位移波動、不同"
        "pillar之間的位移分歧，以及相對PI平台實際回授位移的偏差；50倍CD的小幅差異只有0.041 pixel，且在公平的"
        "共同量測規則下不影響其位移結論。Raw位置錨定對合併位移指標的影響較小，主要用來維持最終輪廓與原始影像"
        "的位置關係，避免過度銳化造成邊緣壓縮與振鈴。消融結果因此分別將兩項設計連結至位移一致性與邊界保護，並以"
        "位移標準差、CD、邊緣寬度及振鈴的共同判讀避免單一數值造成誤解。",
    )

    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
