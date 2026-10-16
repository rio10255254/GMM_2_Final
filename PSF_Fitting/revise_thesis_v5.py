from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from revise_thesis_v4 import (
    W,
    chapter6_children,
    find_unique_paragraph,
    get_style_id,
    is_paragraph,
    mark_fields_dirty,
    paragraph_text,
    replace_unique,
    set_paragraph_text,
    update_fields_setting,
    xml,
    xml_bytes,
)


SOURCE_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v4.docx"
)
OUTPUT_DOCX = Path(
    r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v5.docx"
)


def remove_unique(body, children, *, startswith: str) -> None:
    paragraph = find_unique_paragraph(children, startswith=startswith)
    body.remove(paragraph)


def build() -> dict[str, object]:
    if not SOURCE_DOCX.is_file():
        raise FileNotFoundError(SOURCE_DOCX)

    with zipfile.ZipFile(SOURCE_DOCX, "r") as source_zip:
        entries = {
            info.filename: source_zip.read(info.filename)
            for info in source_zip.infolist()
        }

    root = xml(entries["word/document.xml"])
    body = root.find(W + "body")
    if body is None:
        raise RuntimeError("Document has no body")
    all_children = list(body)

    # Contribution statement: keep the optical-prior claim at the method level.
    replace_unique(
        all_children,
        startswith="貢獻二：建立結合光學先驗與幾何穩定性的單張影像重建方法",
        replacement=(
            "貢獻二：建立結合光學先驗與幾何穩定性的單張影像重建方法。"
            "方法以局部PSF支援區域校正與傳統反卷積比較，並以多位置PSF建立融合式光學先驗；"
            "模型透過同尺寸編碼器—解碼器、位移穩定上採樣、受限邊界殘差、原圖基準與品質門控，"
            "在提升邊界可辨識性的同時限制非物理高頻與位置漂移。"
        ),
    )

    # Chapter 4: reconcile the actual program indexing with the prose.
    replace_unique(
        all_children,
        startswith="本研究使用 OSA/ANSI 單索引順序表示 Zernike 基底",
        replacement=(
            "程式內部採與OSA/ANSI模態順序一致、索引較標準編號加1的命名：Z1為piston，Z2與Z3為兩個傾斜項。"
            "Piston不影響強度PSF；傾斜項主要表現為整體平移，因此先完成亞像素幾何對位，再將Z2與Z3固定為0，"
            "使搜尋集中於會改變PSF形貌的程式內部Z4至Z15。"
        ),
    )
    replace_unique(
        all_children,
        startswith="梯度項前的",
        replacement=(
            "梯度項前的平衡係數依強度損失與梯度損失的實際數值尺度設定，使兩者在最佳化時具有相近的影響量級。"
            "此係數負責尺度對齊；若影像正規化或梯度計算方式改變，則依同一原則重新校正。"
        ),
    )
    replace_unique(
        all_children,
        startswith="需要強調的是，最低目標函數只表示",
        replacement=(
            "最終PSF由所有候選中目標函數最低者確定，並同步檢查其形貌平滑度、能量集中程度、方向性，"
            "以及預測影像與實拍影像的邊界位置和灰階剖面，使數值最佳化結果同時具備合理的光學形貌。"
        ),
    )

    # Chapter 4: explain the spatially varying PSF fusion module itself, without
    # tying this method description to the later result interpretation.
    replace_unique(
        all_children,
        startswith="4.2.4 固定融合與自適應多 PSF 修正",
        replacement="4.2.4 空間變異 PSF 融合神經網路模組",
    )
    replace_unique(
        all_children,
        startswith="等權融合的目的，是保留多個位置共有的模糊趨勢",
        replacement=(
            "固定融合分支先將多個位置的PSF對齊並正規化，再以等權方式形成共同光學核。"
            "其Wiener型修正以低權重殘差加入輸入特徵，提供一致且受控的初始光學方向。"
        ),
    )
    replace_unique(
        all_children,
        startswith="固定融合提高了輸入處理的一致性",
        replacement=(
            "自適應融合分支使用數個代表性候選PSF分別形成修正特徵，再由輸入的全域特徵估計非負且總和為1的融合權重。"
            "不同影像因而可取得不同的PSF組合，同時避免逐像素切換所造成的不連續。"
        ),
    )
    replace_unique(
        all_children,
        startswith="自適應融合以殘差形式加入主幹特徵",
        replacement=(
            "固定融合與自適應融合均以殘差形式加入主幹特徵，不直接取代原始特徵。"
            "前者描述多位置共有的模糊趨勢，後者依輸入內容調整候選PSF比例，兩者共同構成空間變異PSF融合模組。"
        ),
    )
    replace_unique(
        all_children,
        startswith="由於權重模組使用全域特徵彙整",
        replacement=(
            "自適應權重由全域特徵彙整後產生，主要反映整張輸入或目前特徵層級的整體模糊狀態，"
            "而不在相鄰像素間快速切換，以維持修正結果的空間連續性。"
        ),
    )
    replace_unique(
        all_children,
        startswith="這項分層設計的創新重點",
        replacement=(
            "此分層設計將可解釋的局部校正、穩定的共同先驗與依輸入調整的PSF權重分開處理，"
            "使光學資訊以受控的殘差方式進入神經網路，而不是直接以強反卷積取代原始影像。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="自適應多 PSF 分支與固定 25-PSF 融合並不是功能重複",
    )

    # Chapter 4: condense repeated split caveats into a direct method statement.
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="連續顯微影格之間通常只存在微小位移",
        replacement=(
            "連續顯微影格及其裁切、平移與增強版本具有共同來源，因此資料切分不以單張影格為最小單位，"
            "而以原始序列、倍率與形狀群組進行管理，使同一來源及其衍生版本固定留在同一集合。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="類似問題也可能出現在資料增強中",
    )
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="因此，本研究不是以單一影格為最小切分單位",
        replacement=(
            "完成分組後，訓練與內部驗證使用固定索引名單；來自同一連續序列及同一原始幾何的衍生配對不跨越兩個集合。"
        ),
    )
    replace_unique(
        all_children,
        startswith="分組切分的目的，是讓驗證結果反映模型是否能處理",
        replacement=(
            "固定分組驗證用於訓練期間監測未參與權重更新群組的表現，並與第六章針對指定系統與樣品的整體方法比較形成分工。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="切分後的驗證資料用來檢查模型是否能處理",
    )
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="目前資料涵蓋本研究所使用的光學系統",
        replacement=(
            "資料涵蓋本研究使用的光學系統、HS-100MG樣品、20倍與50倍影像，以及多種幾何、紋理、位移與雜訊條件，"
            "用於支援指定量測情境下的模型學習、內部監測與系統驗證；跨樣品及跨系統擴充則於第七章規劃。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="因此，本研究對適用範圍的主張保持明確界線",
    )

    all_children = list(body)
    replace_unique(
        all_children,
        startswith="這三項機制並不能從數學上保證",
        replacement=(
            "三項機制共同限制模型的輸出自由度，使邊界增強維持在受控範圍；其實際效益由逐顆CD、門檻穩健性、"
            "相鄰影格位移與九宮格內一致性共同驗證。"
        ),
    )
    replace_unique(
        all_children,
        startswith="4.6.4 統計指標與解讀界線",
        replacement="4.6.4 統計指標與解讀原則",
    )
    replace_unique(
        all_children,
        startswith="MAE 描述整體平均差距",
        replacement=(
            "MAE描述整體平均差距，MdAE代表典型單顆誤差，RMSE反映較大誤差的影響，Bias顯示整體高估或低估方向，"
            "MaxAE則檢查最大單顆偏差。多指標共同呈現，使典型表現、系統偏差與極端值具有一致的解讀基礎。"
        ),
    )
    replace_unique(
        all_children,
        startswith="平台指令是名義參考",
        replacement=(
            "平台名義指令作為三種影像方法的共同位移參考；在相同影格、相同中心與相同彙整規則下，"
            "比較指令值偏差、步間波動、跨軸變化與九宮格內一致性。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="同一序列中的相鄰步驟具有時間相關性",
    )

    # Chapter 4: turn the long mismatch warning into a concise matching rule.
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="Wiener 反卷積建立在一個重要前提上",
        replacement=(
            "Wiener反卷積使用與倍率及目標區域相符的局部擬合PSF。20倍與50倍影像分別採用對應倍率的PSF，"
            "並在相同中心九宮格與共同量測規則下比較，以維持合理的物理尺度與模糊對應。"
        ),
    )
    for prefix in (
        "例如，若使用視野中心的 PSF 處理角落影像",
        "不同倍率的 PSF 也不能互換",
        "即使使用相符的局部 PSF",
    ):
        remove_unique(body, all_children, startswith=prefix)
        all_children = list(body)
    replace_unique(
        all_children,
        startswith="Wiener 與所提模型均不得只以視覺銳利度",
        replacement=(
            "Raw、Wiener與所提模型均以同一套物理量測規則比較，依序檢查邊緣集中程度、振鈴、逐顆CD、"
            "連續位移及多pillar空間一致性；Wiener提供光學模型基準，所提模型則整合光學先驗、真實紋理與位移穩定性。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="本研究在比較設計上的核心，不是預先假設深度學習必然優於",
    )
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="光學部分以中心九宮格的逐顆參考幾何擬合局部 PSF",
        replacement=(
            "光學部分以中心九宮格的逐顆參考幾何擬合局部PSF，並以多位置PSF建立空間變異融合模組。"
            "固定分支提供共同光學方向，自適應分支依輸入特徵調整候選PSF權重。"
        ),
    )

    # Chapter 5: describe the spatially varying PSF fusion module and its place
    # in the network, without extending the discussion into Chapter 6 claims.
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="本研究所使用之深度學習模型架構如圖5-19所示",
        replacement=(
            "本研究的重建網路以Encoder–Decoder與跳接結構為主體，結合ShiftSafe Upsample、Boundary Correction"
            "與空間變異PSF融合模組。圖5-19呈現各模組在特徵提取、解析度恢復、光學修正與邊界補償流程中的相對位置。"
        ),
    )
    replace_unique(
        all_children,
        startswith="除了主要的Encoder–Decoder路徑外，本研究進一步加入Residual PSF Correction模組",
        replacement=(
            "空間變異PSF融合模組以Residual PSF Correction形式導入光學資訊。固定融合路徑提供多位置PSF的共同修正，"
            "自適應路徑則依目前輸入特徵調整候選PSF比例，兩者均以殘差方式與主幹特徵結合。"
        ),
    )
    replace_unique(
        all_children,
        startswith="Residual PSF Correction模組之內部架構如圖5-20所示",
        replacement=(
            "圖5-20呈現空間變異PSF融合模組的內部流程。輸入特徵先分為主幹與PSF修正路徑；候選PSF響應於頻域計算後"
            "回到空間域，再由Weight Block產生的權重完成融合。"
        ),
    )
    replace_unique(
        all_children,
        startswith="在PSF分支之外，Residual PSF Correction模組亦包含Weight Block",
        replacement=(
            "Weight Block由Global Pooling、卷積、SiLU、Temperature Scaling與SoftMax構成，"
            "可將輸入特徵彙整為各候選PSF的融合權重；Weight Fusion再把多個修正響應整合為單一特徵輸出。"
        ),
    )
    replace_unique(
        all_children,
        startswith="為了避免PSF先驗過度干擾主幹網路的特徵學習",
        replacement=(
            "固定融合路徑以參數α控制共同光學修正強度；自適應融合路徑則以參數β控制其殘差比例。"
            "兩者皆採殘差形式，使光學資訊以受控方式加入主幹特徵。"
        ),
    )
    replace_unique(
        all_children,
        startswith="整體而言，本研究模型以Encoder–Decoder架構作為主要重建路徑",
        replacement=(
            "整體而言，網路以Encoder–Decoder、跳接與ShiftSafe Upsample完成多尺度重建，"
            "以空間變異PSF融合模組導入光學先驗，再由Boundary Correction補償量測相關邊界。"
        ),
    )
    figure_520 = find_unique_paragraph(
        all_children,
        startswith="圖 5-20 殘差式PSF修正模組",
        style="FigureCaption",
    )
    set_paragraph_text(figure_520, "圖 5-20 空間變異PSF融合之殘差式修正模組")
    table_513 = find_unique_paragraph(
        all_children,
        startswith="表 5-13 編碼器層級參數",
        style="TableCaption",
    )
    p_pr = table_513.find(W + "pPr")
    if p_pr is None:
        p_pr = etree.Element(W + "pPr")
        table_513.insert(0, p_pr)
    page_break_before = p_pr.find(W + "pageBreakBefore")
    if page_break_before is None:
        page_break_before = etree.SubElement(p_pr, W + "pageBreakBefore")
    page_break_before.set(W + "val", "1")
    replace_unique(
        all_children,
        startswith="模型使用11,254組影像配對進行微調",
        replacement=(
            "模型使用11,254組影像配對進行微調，依資料角色、樣品來源、倍率與結構類型固定分組為9,857組訓練資料與"
            "1,397組內部驗證資料，兩集合的群組交疊為0。資料涵蓋外觀重建、SEM幾何錨點、連續位移、合成運動、"
            "真實多倍率影像與保守性樣本，分別提供外觀、邊界、運動與原圖保持等監督。"
        ),
    )

    # Chapter 6: precise modal indexing, concise interpretation, and one clear
    # statement of the formal evaluation scope.
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="本研究使用Noll編號Z4至Z15",
        replacement=(
            "本研究的擬合程式採與OSA/ANSI模態順序一致、內部索引加1的命名。完成亞像素預對位後，Z2與Z3傾斜項固定為0，"
            "BADS搜尋程式內部Z4至Z15及整體振幅。目標函數同時比較有效區域內的亮度與正規化邊緣梯度，"
            "使候選PSF兼顧灰階分布、邊界位置與過渡形貌。"
        ),
    )
    replace_unique(
        all_children,
        startswith="完成100個視野區域的參數擬合後",
        replacement=(
            "完成100個視野區域的參數擬合後，各區域的最佳Zernike參數與PSF依視野位置排列，形成全視野空間變異資料。"
            "此結果用於描繪不同位置的模糊形貌，並提供建立多位置光學先驗的候選資料。"
        ),
    )
    replace_unique(
        all_children,
        startswith="下列影像使用相同灰階範圍分開呈現",
        replacement=(
            "下列影像使用相同灰階範圍分開呈現。20×與50×的Wiener結果均可見較陡的pillar外緣；"
            "50×同時呈現較明顯的中心亮斑與外環，反映較強的高頻補償。後續以邊緣寬度、振鈴與CD共同量化其輪廓行為。"
        ),
    )
    replace_unique(
        all_children,
        startswith="20× 的平均邊緣寬度由 0.722 µm",
        replacement=(
            "20×的平均邊緣寬度由0.722 µm降至0.499 µm，縮減30.84%；50×則由0.621 µm降至0.470 µm，縮減24.35%。"
            "兩種倍率的九顆pillar均全部縮窄，顯示固定Wiener設定能一致集中灰階過渡。"
            "本節以九顆平均值摘要PSF基準；第6.2節三方法共同比較採九顆中位數，因此兩節數值代表不同彙整方式。"
        ),
    )
    replace_unique(
        all_children,
        startswith="20× 的最大振鈴比例由 3.2%",
        replacement=(
            "20×的最大振鈴比例由3.2%增至23.0%，50×則由1.6%增至25.9%，量化了較積極Wiener設定所帶來的高頻補償。"
            "兩種倍率的pillar中心均維持原有明暗方向；後續CD分析再以35–65%多門檻範圍檢查外環對邊界交點的影響。"
        ),
    )
    replace_unique(
        all_children,
        startswith="新版固定 NSR = 0.05 的 Wiener 反卷積達成本節最直接的驗證目的",
        replacement=(
            "固定NSR = 0.05的Wiener反卷積使20×與50×九顆pillar的10–90%灰階過渡一致縮窄，"
            "證明局部擬合PSF可作為有效的傳統銳化核心。最大振鈴約為23–26%，因此第6.2節以35–65%門檻上下界"
            "及120步位移一致性進一步比較輪廓的量測表現。"
        ),
    )
    remove_unique(
        body,
        all_children,
        startswith="固定NSR = 0.05的Wiener反卷積在兩種倍率均明顯縮短",
    )
    all_children = list(body)
    replace_unique(
        all_children,
        startswith="Wiener 基準的 PSF 由未納入正式 30 步結果的校正影格取得",
        replacement=(
            "Wiener基準的PSF由獨立校正影格取得，20×與50×均固定採NSR = 0.05，且不依SEM CD或位移誤差重新調整。"
            "每一倍率使用一個固定PSF處理兩種位移幅度；三種方法沿用同一影像名單與量測條件。"
        ),
    )
    replace_unique(
        all_children,
        startswith="MOSR 的完整訓練資料以 11,254 組影像配對為基礎",
        replacement=(
            "MOSR以11,254組影像配對完成微調，其中180組使用窄範圍邊界軟標籤，原始輸入影像保持不變；"
            "本節固定使用完成120回合訓練後的同一組權重。第六章部分正式評估影像與訓練資料共享拍攝序列來源，"
            "因此本節定位為既有成像條件下的系統可行性與量測一致性驗證；跨樣品與跨系統表現另於第七章規劃。"
        ),
    )
    replace_unique(
        all_children,
        startswith="兩種倍率的樣品擺放方向並不相同",
        replacement=(
            "兩種倍率的樣品擺放方向不同。50×影像的pillar區位於樣品中心交界右上方；20×影像相對呈上下翻轉，"
            "pillar區位於交界右下方。20×分析因此使用右下角最靠近交界的九顆暗色pillar；左上方亮圓形區域為via，"
            "不納入pillar量測。完成方位判定後，Raw、Wiener與MOSR沿用同一組中心、影像檔名與相鄰影格配對。"
        ),
    )
    replace_unique(
        all_children,
        startswith="方位修正後，兩倍率選到的 pillar 均為亮背景上的暗結構",
        replacement=(
            "方位確認後，兩倍率選到的pillar均為亮背景上的暗結構。九顆帶正負號Michelson對比中位數在50×的"
            "Raw、Wiener與MOSR分別為−38.3%、−55.6%與−38.5%，20×分別為−32.0%、−45.6%與−33.3%。"
            "Wiener提供最強對比增益；MOSR較接近原始亮度結構，同時保留暗pillar極性，顯示後續量測改善並非來自整體明暗翻轉。"
        ),
    )
    replace_unique(
        all_children,
        startswith="為避免顯示對比造成主觀誤判",
        replacement=(
            "50×與20×的Raw、Wiener及MOSR影像均使用相同8-bit灰階範圍0–255顯示，不對個別影像進行自動對比拉伸。"
            "以下影像與剖面圖採單張呈現；影像示例使用各倍率的代表性校正影格，位移統計則使用共同固定的120步。"
        ),
    )
    replace_unique(
        all_children,
        startswith="20× 影像的物體空間取樣較粗",
        replacement=(
            "20×影像的物體空間取樣較粗，九顆10–90%過渡寬度中位數由Raw的802.2 nm降至Wiener的493.1 nm與"
            "MOSR的246.1 nm，分別縮小38.54%與69.33%。MOSR得到最窄過渡，Wiener亦明顯優於Raw；"
            "剖面中的高頻反應再與振鈴及跨門檻CD結果共同解讀。"
        ),
    )

    sequence_replacements = {
        "50×、0.5 µm 序列共有 48 個可用候選步": (
            "50×、0.5 µm序列固定分析30步。Raw、Wiener與MOSR的步階標準差依序為7.04、4.94與3.61 nm；"
            "指令值平均絕對偏差為5.25、4.07與3.07 nm；九宮格內不一致量為13.03、6.86與4.48 nm。"
            "兩種重建均改善Raw，MOSR在三項指標上最低。"
        ),
        "50×、1.0 µm 序列亦由 48 個可用候選步固定取前 30 步": (
            "50×、1.0 µm序列固定分析30步。Raw、Wiener與MOSR的步階標準差為7.69、4.36與3.72 nm；"
            "指令值平均絕對偏差為6.98、3.89與3.36 nm；九宮格內不一致量為12.06、7.07與3.73 nm。"
            "MOSR在三項指標均為最低。"
        ),
        "20×、0.5 µm 是可用候選最少的一組": (
            "20×、0.5 µm序列固定分析30步。Raw、Wiener與MOSR的步階標準差為16.25、15.19與14.73 nm，"
            "指令值平均絕對偏差為13.13、12.78與11.74 nm，兩項均由MOSR最低；九宮格內不一致量為25.14、8.70與9.13 nm，"
            "Wiener略低於MOSR，但兩者均大幅改善Raw。"
        ),
        "20×、1.0 µm 序列共有 49 個可用候選步": (
            "20×、1.0 µm序列固定分析30步。Raw、Wiener與MOSR的步階標準差為13.52、7.46與6.94 nm；"
            "指令值平均絕對偏差為12.82、9.13與8.81 nm；九宮格內不一致量為20.28、9.03與8.53 nm。"
            "MOSR在三項指標均略優於Wiener。"
        ),
    }
    for prefix, replacement in sequence_replacements.items():
        replace_unique(all_children, startswith=prefix, replacement=replacement)

    # Chapter 7: frame extensions positively and avoid repeating the single
    # formal-evaluation scope disclosure already stated in Chapter 6.
    replace_unique(
        all_children,
        startswith="本研究已建立由光學校正、影像重建到尺寸與位移量測的完整方法鏈",
        replacement=(
            "本研究已建立由光學校正、影像重建到尺寸與位移量測的完整方法鏈，並在HS-100MG樣品上完成核心驗證。"
            "後續可將此方法延伸至更多光學條件、樣品類型與可追溯回授，進一步擴大量測導向重建的應用範圍。"
        ),
    )
    replace_unique(
        all_children,
        startswith="本研究的主要量化結果集中於同一HS-100MG樣品",
        replacement=(
            "後續可加入不同批次的標準樣品、不同尺寸的pillar與via，以及線條與方形結構，形成跨樣品測試組，"
            "量化模型對結構幾何、倍率與成像條件的適用範圍。"
        ),
    )
    replace_unique(
        all_children,
        startswith="現有位移結果以平台名義指令作為一致性參考",
        replacement=(
            "現有位移結果已以平台名義指令完成步間散佈與九顆pillar一致性比較。未來加入雷射干涉儀、外部電容式感測器"
            "或具校正證書的編碼器，可同步取得每一步的獨立回授，進一步分離平台、影像定位與重建三類變動來源。"
        ),
    )
    replace_unique(
        all_children,
        startswith="在取得獨立真值後，可建立包含重複性",
        replacement=(
            "結合獨立回授後，可建立包含重複性、系統偏差、像素尺度、SEM參考與模型變動的量測不確定度預算，"
            "並報告不同倍率與位置的擴充不確定度，使位移結果具有明確的追溯鏈與可信範圍。"
        ),
    )
    replace_unique(
        all_children,
        startswith="後續模型不應只依訓練損失或單張影像品質選擇",
        replacement=(
            "後續模型可由邊緣寬度、跨門檻CD穩健度、振鈴比例、位移重複性與多顆空間一致性共同選擇。"
            "各項資料名單與門檻在比較前固定，形成一致且可重複的模型評估準則。"
        ),
    )

    # Validation before packaging.
    all_text = "\n".join(
        paragraph_text(element) for element in body if is_paragraph(element)
    )
    forbidden = [
        "Noll編號Z4至Z15",
        "先前位於左上方",
        "可用候選最少",
        "使量測結果能由同資料域驗證",
        "自適應多 PSF 分支與固定 25-PSF",
        "固定NSR = 0.05的Wiener反卷積在兩種倍率均明顯縮短",
    ]
    remaining = [text for text in forbidden if text in all_text]
    if remaining:
        raise RuntimeError(f"Forbidden legacy wording remains: {remaining}")

    chapter6 = chapter6_children(body)
    figures = sum(
        1
        for element in chapter6
        if is_paragraph(element) and get_style_id(element) == "FigureCaption"
    )
    tables = sum(
        1
        for element in chapter6
        if is_paragraph(element) and get_style_id(element) == "TableCaption"
    )
    if figures != 42 or tables != 9:
        raise RuntimeError(
            f"Chapter 6 caption counts changed unexpectedly: figures={figures}, tables={tables}"
        )

    mark_fields_dirty(root)
    entries["word/document.xml"] = xml_bytes(root)
    settings = xml(entries["word/settings.xml"])
    update_fields_setting(settings)
    entries["word/settings.xml"] = xml_bytes(settings)

    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=OUTPUT_DOCX.stem + "_", suffix=".tmp", dir=OUTPUT_DOCX.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
            for name, data in entries.items():
                output_zip.writestr(name, data)
        with zipfile.ZipFile(temp_path, "r") as check_zip:
            corrupt = check_zip.testzip()
            if corrupt:
                raise RuntimeError(f"Corrupt ZIP member: {corrupt}")
            check_root = xml(check_zip.read("word/document.xml"))
            check_body = check_root.find(W + "body")
            if check_body is None:
                raise RuntimeError("Output has no document body")
        os.replace(temp_path, OUTPUT_DOCX)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "output": str(OUTPUT_DOCX),
        "chapter6_figures": figures,
        "chapter6_tables": tables,
    }


if __name__ == "__main__":
    result = build()
    for key, value in result.items():
        print(f"{key}: {value}")
