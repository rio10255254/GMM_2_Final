from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageChops
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
PROJECT_ROOT = Path(__file__).resolve().parents[8]


SOURCE = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v17_修訂版.docx")
OUTPUT = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v18_圖表整理版.docx")
WORK = Path(str(PROJECT_ROOT / 'PSF_Fitting/.codex_docx_work/v18'))
FIG = WORK / "figures"
EARLY = FIG / "early"
WIENER = FIG / "wiener" / "figures"
R63 = FIG / "r63"
CROSS = FIG / "cross_morphology"
PREPARED = WORK / "prepared_media"
MANIFEST = WORK / "chapter6_figure_redraw_manifest.json"


FIGURE_CAPTIONS = {
    1: "圖 6-1 50倍物鏡拍攝影像與空間頻譜。左圖為用於PSF校正的中心3×3 pillar原始影像；右圖為其二維傅立葉幅值頻譜，統一以−80至0 dBFS色階顯示。",
    2: "圖 6-2 20倍物鏡拍攝影像與空間頻譜。左圖為用於PSF校正的中心3×3 pillar原始影像；右圖為其二維傅立葉幅值頻譜，統一以−80至0 dBFS色階顯示。",
    3: "圖 6-3 全視野點擴散函數排列。每一點對應全視野取樣位置的局部擬合PSF，用以呈現視野內模糊形狀的空間變化。",
    4: "圖 6-4 50倍物鏡之局部擬合點擴散函數。PSF以總能量正規化後呈現，色階表示相對強度。",
    5: "圖 6-5 20倍物鏡之局部擬合點擴散函數。PSF以總能量正規化後呈現，色階表示相對強度。",
    6: "圖 6-6 CD、10–90%邊緣寬度與徑向剖面之量測方式。左圖以50%局部對比邊界定義相對方向直徑；右圖由360個徑向剖面中位數讀取10%、50%與90%交點，其中CD以相對方向的兩個50%半徑相加，邊緣寬度為90%與10%半徑之差。",
    7: "圖 6-7 20倍原始影像之中心九顆pillar。此影像為20倍PSF校正與後續Raw、Wiener及MOSR比較所共用的中心3×3區域。",
    8: "圖 6-8 20倍固定PSF之Wiener反卷積結果。輸入影像與圖6-7相同，固定雜訊功率比NSR為0.05。",
    9: "圖 6-9 50倍原始影像之中心九顆pillar。此影像為50倍PSF校正與後續Raw、Wiener及MOSR比較所共用的中心3×3區域。",
    10: "圖 6-10 50倍固定PSF之Wiener反卷積結果。輸入影像與圖6-9相同，固定雜訊功率比NSR為0.05。",
    11: "圖 6-11 20倍Raw與Wiener之九顆pillar徑向邊緣剖面中位數。各pillar以360個方向取樣，圖中為九顆pillar彙整後的徑向灰階過渡比較。",
    12: "圖 6-12 50倍Raw與Wiener之九顆pillar徑向邊緣剖面中位數。各pillar以360個方向取樣，圖中為九顆pillar彙整後的徑向灰階過渡比較。",
    13: "圖 6-13 兩種倍率反卷積前後之平均10–90%邊緣寬度。數值越低表示由背景到pillar的灰階過渡越集中。",
    14: "圖 6-14 預先指定50%邊界下之Raw與Wiener平均絕對CD誤差。各pillar以對應SEM直徑為參考，縱軸為九顆pillar的平均絕對誤差。",
    15: "圖 6-15 20倍Raw與Wiener之CD閾值敏感度。每個閾值使用相同影像、中心位置及SEM pillar身分；曲線較低且較平坦代表量測對邊界閾值較穩健。",
    16: "圖 6-16 50倍Raw與Wiener之CD閾值敏感度。每個閾值使用相同影像、中心位置及SEM pillar身分；曲線較低且較平坦代表量測對邊界閾值較穩健。",
    17: "圖 6-17 兩種倍率反卷積前後之最大局部振鈴比例。此比例以pillar周圍反向徑向變化相對於向外邊緣上升量計算。",
    18: "圖 6-18 20倍Wiener反卷積影像之二維傅立葉幅值頻譜。由未截幅的反卷積結果計算，固定NSR為0.05，並與原始影像共用−80至0 dBFS色階。",
    19: "圖 6-19 50倍Wiener反卷積影像之二維傅立葉幅值頻譜。由未截幅的反卷積結果計算，固定NSR為0.05，並與原始影像共用−80至0 dBFS色階。",
    20: "圖 6-20 MOSR第1至第120訓練週期的未平滑損失變化。各項損失以第1週期值正規化為100%，用以比較重建、梯度幅值及邊緣方向項目的收斂趨勢。",
    21: "圖 6-21 50倍完整視野的樣品中心、pillar、via與中心3×3 pillar陣列定位。圖例標示各區域與選取範圍；尺度線為20 µm。",
    22: "圖 6-22 20倍完整視野的樣品方位與中心3×3 pillar陣列定位。相對於50倍影像，本圖採上下翻轉後的實際拍攝方位；圖例標示各區域與選取範圍，尺度線為50 µm。",
    23: "圖 6-23 50倍與20倍中心九顆pillar的帶正負號Michelson對比度。每根柱為九顆pillar的中位數；負值表示pillar較背景暗。",
    24: "圖 6-24 50倍原始影像之中心九顆pillar。此裁切區域與50倍Wiener及MOSR結果共用相同影格、中心位置與顯示尺度；尺度線為5 µm。",
    25: "圖 6-25 50倍固定擬合PSF之Wiener反卷積結果。裁切範圍、影格與圖6-24完全相同；尺度線為5 µm。",
    26: "圖 6-26 50倍MOSR重建之中心九顆pillar。裁切範圍、影格與圖6-24完全相同；尺度線為5 µm。",
    27: "圖 6-27 50倍Raw、Wiener與MOSR的徑向邊緣剖面及過渡寬度。曲線為中心pillar 360個方向的中位數，點與誤差範圍則彙整九顆pillar的10–90%過渡寬度。",
    28: "圖 6-28 20倍原始影像之中心九顆pillar。此裁切區域與20倍Wiener及MOSR結果共用相同影格、中心位置與顯示尺度；尺度線為5 µm。",
    29: "圖 6-29 20倍固定擬合PSF之Wiener反卷積結果。裁切範圍、影格與圖6-28完全相同；尺度線為5 µm。",
    30: "圖 6-30 20倍MOSR重建之中心九顆pillar。裁切範圍、影格與圖6-28完全相同；尺度線為5 µm。",
    31: "圖 6-31 20倍Raw、Wiener與MOSR的徑向邊緣剖面及過渡寬度。曲線為中心pillar 360個方向的中位數，點與誤差範圍則彙整九顆pillar的10–90%過渡寬度。",
    32: "圖 6-32 35–65%閾值與兩種剖面下的中心九顆pillar CD範圍。虛線為逐顆SEM參考直徑；各方法的上下界由七個閾值及水平、徑向兩種剖面共同取得。",
    33: "圖 6-33 中心九顆pillar的跨閾值CD絕對誤差中位數。每種方法統計兩種剖面、七個閾值與九顆具有SEM參考尺寸的pillar。",
    34: "圖 6-34 水平七列剖面的CD閾值敏感度。比較Raw、Wiener與MOSR在共同pillar身分、中心與SEM參考下的平均CD絕對誤差。",
    35: "圖 6-35 360度平均徑向剖面的CD閾值敏感度。比較Raw、Wiener與MOSR在共同pillar身分、中心與SEM參考下的平均CD絕對誤差。",
    36: "圖 6-36 20倍非PSF校正影格的Raw、Wiener與MOSR跨閾值CD絕對誤差中位數。每種方法均包含九顆pillar、七個閾值及兩種剖面，共126筆量測。",
    37: "圖 6-37 50倍、0.5 µm序列的Raw、Wiener與MOSR逐次位移量。橫軸為共同固定的30個配對步次，縱軸為各方法從中心九顆pillar量得的位移幅度。",
    38: "圖 6-38 50倍、1.0 µm序列的Raw、Wiener與MOSR逐次位移量。橫軸為共同固定的30個配對步次，縱軸為各方法從中心九顆pillar量得的位移幅度。",
    39: "圖 6-39 20倍、0.5 µm序列的Raw、Wiener與MOSR逐次位移量。橫軸為共同固定的30個配對步次，縱軸為各方法從中心九顆pillar量得的位移幅度。",
    40: "圖 6-40 20倍、1.0 µm序列的Raw、Wiener與MOSR逐次位移量。橫軸為共同固定的30個配對步次，縱軸為各方法從中心九顆pillar量得的位移幅度。",
    41: "圖 6-41 四組位移序列的逐次位移量標準差。每組使用由Raw影像共同選出的30個配對步次，數值越低表示步與步之間的量測波動越小。",
    42: "圖 6-42 四組位移序列中九顆pillar的內部位移離散度。每組使用由Raw影像共同選出的30個配對步次，數值越低表示同一影格中九顆pillar的位移更一致。",
    43: "圖 6-43 Raw、Wiener與MOSR相對平台實際回授位移的平均絕對偏差。每組使用共同固定的30個配對步次，縱軸越低表示影像量測位移與平台實際回授位置越一致。",
    44: "圖 6-44 Wiener與MOSR逐步降低中心九顆pillar位移離散度的比例。只比較三種方法皆有效的相同配對步次；與Raw相同的步次不計入改善。",
    45: "圖 6-45 50倍固定PSF相對校正位置距離的位移誤差。橫軸為各距離分組的平均物體空間距離，每個分組固定20步，兩種位移幅度共用同一PSF。",
    46: "圖 6-46 20倍固定PSF相對校正位置距離的位移誤差。橫軸為各距離分組的平均物體空間距離，每個分組固定20步，兩種位移幅度共用同一PSF。",
    47: "圖 6-47 完整MOSR模型相對Raw的兩倍率SEM對照CD誤差。柱狀值為兩次配對訓練的平均，點標示各次訓練結果。",
    48: "圖 6-48 完整MOSR模型相對Raw的四組實拍位移序列步間穩定性。縱軸為逐次位移量標準差，柱狀值為兩次配對訓練的平均。",
    49: "圖 6-49 完整MOSR模型相對Raw的九顆pillar位移一致性。縱軸為同一影格內九顆pillar的位移離散度，柱狀值為兩次配對訓練的平均。",
    50: "圖 6-50 以輸入影像為基準的殘差輸出對兩倍率SEM對照CD誤差的影響。正值表示保留輸入參考時的CD誤差較低。",
    51: "圖 6-51 抗混疊與一般上取樣的九顆pillar位移一致性。兩種模型的參數量相同，點標示兩次配對訓練結果。",
    52: "圖 6-52 完整MOSR模型相對Raw的外圍振鈴比較。縱軸為以pillar周圍灰階變化計算的外圍振鈴能量。",
    53: "圖 6-53 20倍via在35–65%固定局部對比閾值下的表觀CD範圍。虛線為逐顆via的SEM參考直徑，誤差棒表示各方法在共同閾值範圍內的CD上下界。",
    54: "圖 6-54 Raw與MOSR於水平及垂直線條上的10–90%邊緣過渡寬度。重建前後維持相同影像取樣尺寸，數值越低表示邊緣過渡越集中。",
}


TABLE_CAPTIONS = {
    1: "表 6-1 兩種倍率之邊緣銳化與最大振鈴摘要。邊緣寬度以九顆pillar的10–90%徑向過渡寬度計算；振鈴比例由局部反向灰階變化評估。",
    2: "表 6-2 預先指定50%邊界下之SEM對照CD結果。各方法使用相同九顆pillar、中心位置及SEM逐顆參考直徑。",
    3: "表 6-3 40%、50%與60%相對對比閾值之CD敏感度。兩種倍率均使用相同影像、pillar身分與SEM參考。",
    4: "表 6-4 MOSR訓練損失摘要。各項損失以第1週期值為基準，以呈現訓練期間的相對收斂幅度。",
    5: "表 6-5 四組位移序列之取樣條件與主分析步數。每組以共同固定的30個有效配對步次進行Raw、Wiener與MOSR比較。",
    6: "表 6-6 35–65%閾值與兩種剖面下中心九顆pillar的CD上下界。上下界涵蓋七個閾值及水平、徑向兩種剖面。",
    7: "表 6-7 跨兩種剖面與七個閾值之CD誤差穩健性。各方法以九顆具有SEM參考尺寸的pillar共同統計。",
    8: "表 6-8 20倍非PSF校正影格之跨閾值CD一致性。每種方法共包含九顆pillar、七個閾值與兩種剖面。",
    9: "表 6-9 四組序列之逐次位移量標準差與平台實際回授位移一致性。所有方法共用每組固定的30個配對步次。",
    10: "表 6-10 四組序列之中心九顆pillar內部一致性。離散度以同一影格內九顆pillar量得的位移差異表示。",
    11: "表 6-11 全部配對步與分倍率之位移結果。平均絕對偏差以平台實際回授位置為位移參考。",
    12: "表 6-12 四組序列之第90百分位誤差。用以補充平均結果之外的較大誤差範圍。",
    13: "表 6-13 模組與損失函數消融實驗之比較條件。各條件維持共同資料、量測規則與配對訓練設定。",
    14: "表 6-14 主要模組、量測導向損失函數與輔助模組之消融結果。正負比較依各指標的較佳方向判讀。",
    15: "表 6-15 20倍via在共同量測規則下的結果。CD區間涵蓋35–65%局部對比閾值，SEM直徑作為逐顆參考。",
    16: "表 6-16 不同影格選取規則下的位移平均絕對偏差。除改善率外，單位皆為nm；比較以平台實際回授位置為參考。",
    17: "表 6-17 相同顯示卡下的全解析度直接推論效能。時間為兩次暖機後六次推論的中位數與第95百分位。",
}


MEDIA_REPLACEMENTS = {
    "word/media/image45.png": EARLY / "fig6-01_zh.png",
    "word/media/image47.png": EARLY / "fig6-02_zh.png",
    "word/media/image49.png": EARLY / "fig6-04_zh.png",
    "word/media/image50.png": EARLY / "fig6-05_zh.png",
    "word/media/image51.png": EARLY / "fig6-06_zh.png",
    "word/media/image56.png": EARLY / "fig6-11_zh.png",
    "word/media/image57.png": EARLY / "fig6-12_zh.png",
    "word/media/image58.png": EARLY / "fig6-13_zh.png",
    "word/media/image59.png": EARLY / "fig6-14_zh.png",
    "word/media/image60.png": EARLY / "fig6-15_zh.png",
    "word/media/image61.png": EARLY / "fig6-16_zh.png",
    "word/media/image62.png": EARLY / "fig6-17_zh.png",
    "word/media/image63.png": EARLY / "fig6-18_zh.png",
    "word/media/image64.png": EARLY / "fig6-19_zh.png",
    "word/media/image65.png": EARLY / "fig6-20_zh.png",
    "word/media/image66.png": EARLY / "fig6-21_zh.png",
    "word/media/image67.png": EARLY / "fig6-22_zh.png",
    "word/media/image68.png": WIENER / "00c_signed_pillar_contrast.png",
    "word/media/image69.png": WIENER / "01_50x_raw_center9.png",
    "word/media/image70.png": WIENER / "02a_50x_wiener_center9.png",
    "word/media/image71.png": WIENER / "02_50x_v42_center9.png",
    "word/media/image72.png": WIENER / "03_50x_pillar_edge_profile.png",
    "word/media/image73.png": WIENER / "04_20x_raw_center9.png",
    "word/media/image74.png": WIENER / "05a_20x_wiener_center9.png",
    "word/media/image75.png": WIENER / "05_20x_v42_center9.png",
    "word/media/image76.png": WIENER / "06_20x_pillar_edge_profile.png",
    "word/media/image77.png": WIENER / "07_center9_cd_per_pillar.png",
    "word/media/image78.png": WIENER / "08_center9_cd_error_summary.png",
    "word/media/image79.png": WIENER / "09a_cd_threshold_sensitivity_horizontal.png",
    "word/media/image80.png": WIENER / "09b_cd_threshold_sensitivity_radial.png",
    "word/media/image81.png": WIENER / "19_20x_noncalibration_cd_error_summary.png",
    "word/media/image82.png": WIENER / "10_50x_0p5um_step_trace.png",
    "word/media/image83.png": WIENER / "11_50x_1um_step_trace.png",
    "word/media/image84.png": WIENER / "12_20x_0p5um_step_trace.png",
    "word/media/image85.png": WIENER / "13_20x_1um_step_trace.png",
    "word/media/image86.png": WIENER / "14_step_stability_summary.png",
    "word/media/image87.png": WIENER / "15_nine_pillar_consistency_summary.png",
    "word/media/image88.png": WIENER / "16_nominal_command_consistency.png",
    "word/media/image89.png": WIENER / "17_stepwise_local_improvement_rate.png",
    "word/media/image90.png": WIENER / "18a_50x_wiener_psf_distance_robustness.png",
    "word/media/image91.png": WIENER / "18b_20x_wiener_psf_distance_robustness.png",
    "word/media/image92.png": R63 / "15_full_vs_raw_cd_error.png",
    "word/media/image93.png": R63 / "16_full_vs_raw_step_stability.png",
    "word/media/image94.png": R63 / "17_full_vs_raw_grid_agreement.png",
    "word/media/image95.png": R63 / "18_raw_position_anchor_cd_error.png",
    "word/media/image96.png": R63 / "19_upsampling_grid_agreement.png",
    "word/media/image97.png": R63 / "20_full_vs_raw_ringing_tradeoff.png",
    "word/media/image98.png": CROSS / "fig6-53_zh.png",
    "word/media/image99.png": CROSS / "fig6-54_zh.png",
}


LINEAGE = {
    "6-1, 6-2, 6-18, 6-19": {
        "data": "中心3×3 pillar原始BMP與Wiener反卷積MAT檔；以FFT計算二維幅值頻譜。",
        "source": r"Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\center9_pillar_fit_20x_50x，source_data\center9_pillar_fit_20x_50x\psf_deconvolution_cd",
        "script": "generate_v18_ch6_early_figures_clean.m",
    },
    "6-3, 6-4, 6-5": {
        "data": "全視野與局部PSF擬合結果；局部PSF由PSF_fitted_2D_FOVstack.mat讀取。",
        "source": r"PSF_Fitting\output\deconvolution_baseline_psf_20260715",
        "script": "generate_v18_ch6_early_figures_clean.m（圖6-3保留原始無文字排列圖）",
    },
    "6-6, 6-11至6-17": {
        "data": "九顆pillar的徑向量測資料、SEM對照CD表與閾值敏感度表。",
        "source": r"Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\source_data\center9_pillar_fit_20x_50x\sharpness_validation 及 tables\center9_pillar_fit_20x_50x",
        "script": "generate_v18_ch6_early_figures_clean.m",
    },
    "6-7至6-10": {
        "data": "20倍及50倍中心3×3 pillar的原始與固定PSF Wiener反卷積影像。",
        "source": r"Final_Data_Figures\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit\figures\center9_pillar_fit_20x_50x",
        "script": "原始無文字影像，保留不重繪。",
    },
    "6-20至6-46": {
        "data": "MOSR訓練記錄、共同影格選取、Raw/Wiener/MOSR逐顆CD與120個配對位移步次資料。",
        "source": r"Final_Data_Figures\04_V42_NEURAL_NETWORK_RESULTS\source_validation\wiener_baseline_20260715\tables，以及V42訓練記錄與共同輸入影像",
        "script": "generate_v18_ch6_early_figures_clean.m、build_wiener_three_way_chapter62_figures_clean.m、generate_v18_fig36_clean.m",
    },
    "6-47至6-52": {
        "data": "兩次配對訓練的模組與損失函數消融彙整結果。",
        "source": r"Experiments\R63_CausalBoundaryMotionAblation\results\evaluation\aggregate",
        "script": "build_r63_figures_clean.m",
    },
    "6-53, 6-54": {
        "data": "20倍via的SEM對照CD區間與水平、垂直線條的邊緣過渡寬度。",
        "source": r"LabSystem_MOSR\Experiments\Modern_Restoration_Benchmarks_20260719\evaluation\circular_cd_sharpness 及 line\tables",
        "script": "generate_v18_via_line_clean.m",
    },
}


def replace_paragraph_text(paragraph, text: str) -> None:
    rpr = None
    for run in paragraph.runs:
        if run._r.rPr is not None:
            rpr = deepcopy(run._r.rPr)
            break
    for child in list(paragraph._p):
        if child.tag != qn("w:pPr"):
            paragraph._p.remove(child)
    run = OxmlElement("w:r")
    if rpr is not None:
        run.append(rpr)
    node = OxmlElement("w:t")
    node.text = text
    run.append(node)
    paragraph._p.append(run)


def figure_number(text: str, kind: str) -> int | None:
    match = re.match(rf"{kind} 6-(\d+)", text)
    return int(match.group(1)) if match else None


def fit_to_existing_frame(path: Path, target_size: tuple[int, int]) -> bytes:
    image = Image.open(path).convert("RGB")
    bg = Image.new("RGB", image.size, "white")
    diff = ImageChops.difference(image, bg).convert("L")
    box = diff.point(lambda p: 255 if p > 7 else 0).getbbox()
    if box:
        margin = max(12, round(min(image.size) * 0.008))
        box = (
            max(0, box[0] - margin),
            max(0, box[1] - margin),
            min(image.width, box[2] + margin),
            min(image.height, box[3] + margin),
        )
        image = image.crop(box)
    canvas = Image.new("RGB", target_size, "white")
    scale = min(target_size[0] / image.width, target_size[1] / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas.paste(resized, ((target_size[0] - resized.width) // 2, (target_size[1] - resized.height) // 2))
    stream = io.BytesIO()
    canvas.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def patch_media(docx_path: Path) -> None:
    PREPARED.mkdir(parents=True, exist_ok=True)
    temp = docx_path.with_suffix(".patched.docx")
    with zipfile.ZipFile(docx_path, "r") as source, zipfile.ZipFile(temp, "w") as target:
        names = set(source.namelist())
        missing = sorted(set(MEDIA_REPLACEMENTS) - names)
        if missing:
            raise RuntimeError(f"Missing media parts: {missing}")
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename in MEDIA_REPLACEMENTS:
                replacement = MEDIA_REPLACEMENTS[item.filename]
                if not replacement.is_file():
                    raise FileNotFoundError(replacement)
                with Image.open(io.BytesIO(data)) as current:
                    target_size = current.size
                if item.filename == "word/media/image98.png":
                    target_size = (1530, 977)
                data = fit_to_existing_frame(replacement, target_size)
                (PREPARED / Path(item.filename).name).write_bytes(data)
            target.writestr(item, data)
    temp.replace(docx_path)


def build_manifest() -> None:
    manifest = {
        "source_document": str(SOURCE),
        "output_document": str(OUTPUT),
        "figure_count": len(FIGURE_CAPTIONS),
        "table_count": len(TABLE_CAPTIONS),
        "replacement_media_count": len(MEDIA_REPLACEMENTS),
        "lineage": LINEAGE,
        "caption_policy": "圖內只保留圖例、座標軸、刻度與必要視覺符號；量測規則、資料範圍與判讀方式置於圖說。",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    for p in MEDIA_REPLACEMENTS.values():
        if not p.is_file():
            raise FileNotFoundError(p)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, OUTPUT)
    doc = Document(OUTPUT)
    figures_done: set[int] = set()
    tables_done: set[int] = set()
    for paragraph in doc.paragraphs:
        content = "".join(run.text for run in paragraph.runs).strip()
        if paragraph.style.name == "Figure Caption":
            n = figure_number(content, "圖")
            if n in FIGURE_CAPTIONS:
                replace_paragraph_text(paragraph, FIGURE_CAPTIONS[n])
                figures_done.add(n)
        elif paragraph.style.name == "Table Caption":
            n = figure_number(content, "表")
            if n in TABLE_CAPTIONS:
                replace_paragraph_text(paragraph, TABLE_CAPTIONS[n])
                tables_done.add(n)
    if figures_done != set(FIGURE_CAPTIONS):
        raise RuntimeError(f"Figure captions not replaced: {sorted(set(FIGURE_CAPTIONS) - figures_done)}")
    if tables_done != set(TABLE_CAPTIONS):
        raise RuntimeError(f"Table captions not replaced: {sorted(set(TABLE_CAPTIONS) - tables_done)}")
    settings = doc.settings._element
    field_update = settings.find(qn("w:updateFields"))
    if field_update is None:
        field_update = OxmlElement("w:updateFields")
        settings.append(field_update)
    field_update.set(qn("w:val"), "true")
    doc.save(OUTPUT)
    patch_media(OUTPUT)
    build_manifest()
    print(OUTPUT)
    print(f"figure_captions={len(figures_done)} table_captions={len(tables_done)} media_replaced={len(MEDIA_REPLACEMENTS)}")


if __name__ == "__main__":
    main()
