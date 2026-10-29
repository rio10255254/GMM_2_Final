# R61 到 R130：目前模型為何形成這個設計

回顧日期：2026-09-14。這是歷史文件與目前實作的交叉閱讀，不是新一輪訓練、重新認證全部舊結果，或模型升級。

## 本次完成標準與閱讀範圍

完成標準是：串起 R61 以後的主要改動、成功與失敗；遇到相互矛盾的文件追查後續更正；把每個主要設計連到 R129 的實際程式；清楚區分已實作、已作用與已證明改善；保存可查閱的來源及閱讀範圍。

實際根目錄為 `Experiments`。R61–R130 共盤點 82 個實驗／分支目錄，R62 在此根目錄下未找到。部分編號是量測重算、論文圖表整理或短探針，不是新訓練模型。本次逐份閱讀主要結果、設計與更正文件，也抽查保存的結果表、執行摘要及 R129 四個主要程式；沒有重跑數十輪訓練或所有歷史影像。

完整清冊及每份文件的「全文讀取／指定欄位／僅盤點」見 [閱讀清冊](../results/history_review_20260914/reading_ledger.csv)，各分支覆蓋見 [82 個目錄索引](../results/history_review_20260914/round_inventory.csv)，實際統計見 [範圍說明](../results/history_review_20260914/scope.json)。清冊也包含舊快照、重複量測摘要與快取說明，不能把檔案總數當作已閱讀的獨立研究數量。

## 最重要的理解

現在的設計不是每一輪都比上一輪更強的直線累積。它經過三次方向轉換：先從既有量測模型擴展場景；再嘗試把邊界位置、粗細、細節拆成可解釋動作；最後發現操作、資料與量法都有尚未成立的假設，才改成完整二維重建，並有選擇地接回光學與原圖參照。

R129 因而是「完整二維學習重建」與「有歷史依據的光學／取樣／原圖保護」的結合。保留這個研究方向合理；把它說成所有部件均已最佳、所有物理作用均已分離，則超出證據。

## 1. R61–R74：量測能力存在，但不是所有輪廓都安全

R61 是多輪沿用權重的研究成果，並非一次從零建立的普遍解答。其 [六條分支索引](../../R61_STEP_Generalization_20260623/R61_RUN_INDEX.csv) 顯示：在相同 96 個生成案例中，平均輪廓距離約從輸入 0.73557 降到 v16 的 0.48273 像素；不同 R61 分支之間差異卻很小。[v16 分組檢查](../../R61_STEP_Generalization_20260623/runs/R61_stepguard_v16_dpv96_matched_20260623/diverse_phantom_validation_20260623_220416/BOUNDARY_GATE_SUMMARY.md) 仍有個別偏移與形狀未過。因此「整體有效」不能改寫為「每項全面改善」。

[R63 的 32 次配對訓練](../../R63_CausalBoundaryMotionAblation/reports/R63_RESULTS.md) 尤其重要，不能在新設計時忘掉：

- 拿掉原圖參照，20 倍尺寸誤差增加約 73.97%，亮暗暈邊也大增；但 50 倍尺寸反而改善。它有保護作用的直接歷史證據，也有用途差異。
- 拿掉改善放大的處理，九柱位移不一致增加約 14.31%；但總步距波動與其他位移條件沒有一致改善證據。
- 其他幾何、位移及邊界分支的独立增益較小或方向混合，不能因名稱重要就視為全都已證明必要。

這些結論屬舊模型、舊訓練與舊量法，不能直接當成 R129 同一百分比的增益。

R64 重算等灰階輪廓位移；R65 整理论文第六章與圖表；R66 補來源位置與圖像身分標示。它們改善的是量測與呈現的可追查性，不能列為三個架構升級。

[R67](../../R67_UniversalModelGeneralization/reports/R67_RESULTS.md) 與 [R68](../../R68_R61_RealFOVFeatureGeneralization/reports/R68_RESULTS.md) 支持 R61 在既有多倍率影像上的廣泛可用性，但缺新樣品與獨立真實位移。接著 [R69](../../R69_ACMContourSEMValidation/reports/R69_RESULTS_TW.md)、[R70](../../R70_V42ACMContourSEMValidation/reports/R70_RESULTS_TW.md) 發現：R61、V42 能改善主要外框，細部周長與非圓起伏卻未必更接近 SEM，暗曝光也會失敗。

[R71](../../R71_R61SyntheticMicroscopyDefectGeneralization/reports/R71_RESULTS_TW.md)／[R72](../../R72_R61SyntheticDefectACMContourValidation/reports/R72_RESULTS_TW.md) 進一步分清「細邊偵測」「封閉外輪廓」與「局部凹凸」不是同一能力。[R73](../../R73_R61ExpandedSyntheticACMGeneralization/reports/R73_RESULTS_TW.md) 的清楚新形狀被改壞；[R74](../../R74_R61HardMicroscopyACMGeneralization/reports/R74_RESULTS_TW.md) 則顯示局部邊界消失、混合困難仍無可靠解答。

留下的要求：改善整體外框，同時保留本來正確的細節；量測位移不能代替量測形狀。

## 2. R75–R82：資料如何設計，往往比換網路更關鍵

[R75](../../R75_R61ArchitectureScratchGeneralization/reports/R75_DESIGN.md) 保留既有架構但從零訓練，使用一般生成形狀。[R76](../../R76_R75ACMContourSEMValidation/reports/R76_FINAL_SYNTHESIS_TW.md) 卻顯示內部選出的第 21 輪，在真實 SEM 的 36 顆全部退步；第 100 輪較好，仍非可靠接替。

[R75v2](../../R75v2_R61ArchitectureScratchGeneralization/reports/R75V2_DESIGN.md) 沒有換主幹，而是拆開前景明暗與背景亮度的錯誤關聯，補非圓、局部困難及保持原樣的例子。[完成分析](../../R75v2_R61ArchitectureScratchGeneralization/reports/COMPLETED_TRAINING_ANALYSIS_TW.md) 與 [R77](../../R77_R75v2ACMContourSEMValidation/reports/R77_RESULTS_TW.md) 顯示粗外框追回 R61 附近，但細部起伏仍差。

[R78](../../R78_R75v2_BroadRealMicroscopeGeneralization/reports/R78_RESULTS_TW.md) 揭露 5 倍密集格線被抹掉，即使位移檢查照樣通過。於是 [R79](../../R79_R75v3_DenseMicroscopyScratchGeneralization/reports/R75V3_DESIGN.md) 補密集結構，並把真實細紋的間距與模擬照明條紋尺度分開，避免同類訊號一時當結構、一時當雜訊。

[R80 的 R79 比較](../../R80_R79E23vsE100GeneralizationValidation/reports/R80_RESULTS_TW.md) 出現另一個反例：第 100 輪合成分數較好，第 23 輪真實 SEM 與困難場景反而較好；兩者對困難合成圖都仍可能比原圖差。另一個同號 R80 分支改採粗輪廓後的細部取邊與圓心量法，不能混同為相同實驗。

[R81](../../R81_MultiArchitectureReferenceCircleBenchmark/reports/R81_RESULTS.md) 的多架構比較沒有單一模型包辦全部量測第一，而且評估影像與訓練來源重合。[R82](../../R82_R39R40CrossSceneGeneralizationBenchmark/reports/R82_RESULTS_TW.md) 同樣沒有全場景贏家。這些紀錄支持分用途判斷，不能支持「更大、更新的模型自然更好」。

## 3. R83–R89：大圖處理與保守修正都必須接受實測

[R83](../../R83_R79SevereMicroscopyStrengthening/reports/R83_RESULTS.md) 的保守輸出改善困難輪廓，但整張與切圖相差數個灰階；曾有一次看似更好的訓練，實際把原光學分支逐步關掉，已作廢。問題不是接縫美化，而是每塊重新計算特徵分布會改變整個答案。

[R84–R86 結案](../../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md) 顯示三種結構修補雖能改善切圖一致性，卻傷害原本輪廓，因此保留 R79 整張處理。這不是「所有全圖運算永遠不可用」，而是必須守住同一張圖的計算意義。

[R87](../../R87_TileNativeScratchGeneralization/reports/R87_RESULTS.md) 從零做出切圖穩定版本，卻會把實心物體畫成環；資料標題雖寫紋理，答案實際未保留紋理，位移名稱也不代表真值真的進入學習。[R88 問題清單](../../R88_MeasurementFaithfulScratch/reports/R88_PROBLEM_LEDGER.md) 已明確記錄這些缺陷。

[R88](../../R88_MeasurementFaithfulScratch/reports/R88_ABORTED_AT_E87.md) 又走到過度保守、接近照抄原圖，在第 87 輪停止；[R89](../../R89_MeasurementNativeScratch/reports/final_validation/R89_FINAL_VALIDATION_TW.md) 放開修正後，雖學得動且切图一致，卻產生強暈邊及清楚結構的破壞。其第 55 輪平均 SEM 很好，某曝光仍會突然抓到外圈。

留下的要求：不能用「改得少」「切圖一致」「合成平均變好」任一項代替真正有用。

## 4. R90–R104：細節分工與控制開關的反覆失敗

這段主要調整成像資料、分支的責任、學習比例與限制方式，並非一直增加主幹容量。

| 輪次 | 當時嘗試解決什麼 | 本次查到的結果／證據範圍 |
|---|---|---|
| R90 | 同物體不同曝光一致；低頻修正不能畫窄黑邊 | 第 55 輪停止；第 45 輪保留研究，仍有曝光輪廓漂移 |
| R91 | 把細節與其他作用拆開 | 後續診斷更正舊細節分數：分母近零誇大退步；但第 60 輪曝光 18 確實嚴重失敗 |
| R92 | 平衡曝光比例、物理過渡與清楚資料保護 | 有正式完成摘要；不能由仍停在準備階段的 README 判成未訓練 |
| R93 | 可恢復細節與保留需求分離 | 執行紀錄停在完整第 60 輪；後續 R94 診斷指出共同特徵與控制開關仍有捷徑 |
| R94／R95 | 多條獨立作用路徑，按成像順序學習 | R95 記錄修正 R94 的近恆等、學習訊號與初值殘留問題；R95 有第 48 輪完成摘要，但此處沒有據此認證全部效能 |
| R96 | 各分支的學習不被總目標抵消 | R97 的根因表指出雙重控制再次壓低實際修正；光學作用能力上界並非首要瓶頸 |
| R97／R98 | 移除重複抑制，加強有來源的細節 | R97 完成 48 輪；R98 設計追查到細節稀疏、分支抵消及抽樣遺漏。R98 有正式完成摘要，結果文字頁仍過時 |
| R99／R100 | 亮度、位置、邊界與細節依序形成輸出 | R99 保存使用者停止紀錄；R100 改以可檢查的作用方式修復，後續 R101 揭露仍容易先學去噪 |
| R101 兩分支 | 分辨模型限制、訊號強弱與高頻學習失敗 | A–G 同資料短測顯示：延長步數仍大幅刪除真實細節，不能直接長訓練 |
| R102／R103 | 允許完整修正，重新設計能辨認的答案 | R103 移除會洗掉弱訊號的特徵正規化；曝光同時作用於來源與答案，避免要求單張猜不可辨認的亮度 |
| R104 | 形狀使用相對亮暗線索，需求控制能真正減弱作用 | 實際已有 E48 與完整 SEM 表，舊 README 的「未授權」是歷史狀態；粗輪廓誤差仍高於 Raw，不能把設計存在當效益 |

主要來源：[R90](../../R90_ExposureCoherentScratch/README.md)、[R91 更正](../../R91_DetailDecoupledScratch/results/capability_diagnosis_20260811/capability_summary.json)、[R94](../../R94_EvidenceConditionalScratch/README.md)、[R95](../../R95_CounterfactualGateRepairScratch/README.md)、[R96](../../R96_LocalizedEvidenceProtectedScratch/README.md)、[R97 根因表](../../R97_DirectCausalPhaseScratch/reports/root_cause_matrix.md)、[R98 方法](../../R98_AggressiveTextureScratch/reports/R98_METHODOLOGY.md)、[R101 結果](../../R101_HighFrequencyCausalAblation/EXPERIMENT_RESULTS.md)、[R103 綜合判讀](../../R103_RecoverableDetailScratch/results/posttraining_validation/final_summary.json)、[R104 實際 SEM 表](../../R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/sem_contour/summary.json)。未逐項重算這一段每輪的原始結果；執行摘要與設計文件的證據等級不同，已在清冊標示。

這段最有價值的教訓是：每個模組都要證明真的能學、能作用、作用有利。許多開關相乘和許多看似完整的目標，反而可能讓模型關閉有用能力，或讓最容易的去噪工作掩蓋形狀失敗。

## 5. R105–R110：回到單張，將位置與邊界寬度拆開

[R105A](../../R105A_GeometryRendererFalsification/reports/R105A_FINAL_FINDINGS_ZH.md) 直接用預測輪廓畫圖，邊緣寬度較準、平均影像誤差較低，卻把位置推錯；給它正確輪廓時很好，不代表模型能估出正確輪廓。

[R105B](../../R105B_EvidenceSetReconstructionFalsification/reports/R105B_FINAL_FINDINGS_ZH.md) 顯示增加真正不同觀測有潛力，但 [R105C](../../R105C_JunHuaMultiObservationFeasibility/reports/R105C_PAIR_AUDIT_ZH.md) 確認真實同位置雙張主要增加去噪資訊；[R106A](../../R106A_MultiObservationShortValidation/reports/R106A_FINAL_FINDINGS_ZH.md) 的實作沒有有效利用更細位置資訊，也不能徹底排除錯配。沒有進入完整多張模型。

回到單張的 R107／R108，逐步否決全圖挑模型、共同信心開關、固定尺度銳化與自由畫輪廓。[R108C–R109 決策鏈](../../R109_StagedMidpointWidthScratch/reports/R108C_TO_R109_DECISION_CHAIN_ZH.md) 完整保存每個分支：

- C：獨立專家能學，但固定尺度不足；舊假邊警示也曾把真實弱格線增強誤認為假邊。
- D：多尺度與自由位移仍傷害 SEM。
- E：形狀分數變好，真實影像卻出現黑環。
- F：限制亮暗範圍消除黑環，仍把 SEM 邊界推错。
- G：沿邊界方向移動與保持中點的寬度修正分開，才取得跨三套輪廓的初步共同改善。

[R109 E48](../../R109_StagedMidpointWidthScratch/reports/R109_FINAL_SELECTION_ZH.md) 成為這条路線真正有用的成果；[R110](../../R110_TimeCapacityVisibilityProbes/reports/R110_RESULTS_ZH.md) 卻顯示多訓練、擴大整個模型、再加可見度參數都没有充分好處。

這支持保留有用的幾何理解，但不支持繼續增加同類開關，也不證明任意像素上的「位移／寬度」名稱就代表純粹物理動作。

## 6. R111–R119：量測與實作稽核推翻部分機制故事

[R111](../../R111_R109V42ThesisReplacementQualification/README.md) 發現輪廓演算法內部交替狀態能使同圖重算不同，必須固定。R112 曾嘗試用環寬波動解釋外部位移差距；[R113 連續量測更正](../../R113_CausalStructureDissection/MEASUREMENT_QA_FINDINGS.md) 證明舊半徑不變部分來自粗取樣，原相關解釋不成立。

[R113 深層診斷](../../R113_CausalStructureDissection/deep_audit/DEEP_AUDIT_FINDINGS_ZH.md) 找到邊界控制未學起來、密集形狀以邊界像素數主導訓練、保持原圖與修復訊號衝突。不能以「形狀類別數平均」保證有效學習比例平均。

[R114 完整過程](../../R114_ConfidenceGatedRecoverableScratch/reports/R114_EXECUTION_LEDGER_ZH.md) 更具體：有分支的主體根本未加入更新；以正確座標訓練、以預測座標使用會錯配；補細節時共享特徵會改壞已穩定的幾何底層。分支隔離後能保住底層，但選擇何時修復仍無實質增益。[R115](../../R115_R109DecoupledNormalProfileScratch/reports/R115_DESIGN_AND_PROBE_ZH.md) 的小幅調整也未全面勝過 R109。

[R116](../../R116_CoherentGeometryAnchorScratch/reports/R116_ARCHITECTURE_DECISION_ZH.md) 因而更徹底拆開座標、寬度、位移與細節。[R117 稽核](../../R117_CenterLockedSubpixelScratch/analysis/design_audit_20260905/FINDINGS.md) 又查出：預覽竟讀到舊重建圖；暗物體法線符號錯配；位置要求未更新位置估計器；所謂中心目標對真正平移不敏感；保護投影本身能製造環。這些反例否定的是過強宣稱與具體實作，不是模型能力已到極限。

[R118 修正表](../../R118_PhysicalCoordinateRepairScratch/reports/REPAIR_MAP.md) 建立了實際資料、座標、學習與分塊契約，但 [R119 後續因果稽核](../../R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md) 證明執行並未忠實實現若干關鍵項目：訓練未消耗宣稱的新物理序列、比較組驗證資料不同、非對稱模糊夾帶位置偏移、關閉細節同時關掉寬度、確認位置重複扣位移。

所以 R119 舊完成收據、因果解釋及確認結案不能再當設計依據。訓練確實發生、部分重建與位移點估計仍可用，與「原計畫被完整且正確驗證」是兩件事。舊 144 場景確認已被使用，永遠不能再稱未見確認；本次沒有讀取其影像。

## 7. R120–R127：先把成像、資料與讀法分清楚

R120 目前保存的 [四次短測紀錄](../../R120_PhysicalSequenceRepair/results/probe_matrix.json)、[共同輸入與初始化核對](../../R120_PhysicalSequenceRepair/results/probe_audit.json) 及 [位移診斷](../../R120_PhysicalSequenceRepair/results/motion_diagnostic/summary.json) 均已存在。較早記憶中的「尚未完成」不再作現在狀態。B 的影像誤差略低，但無效定位與不同方向反應仍有取捨，未形成新模型升級證據。README 指向的 R120_RESULTS.md 目前未找到，這是文件索引缺口；不據此判定整輪未執行。

[R121](../../R121_BoundaryAnchorFactorial/reports/R121_RESULTS.md) 的兩種修正與合併方案，各兩次初始化共八次有效短訓練，全部沒有守住真實輪廓與細節。合成位置分數變好並不代表實拍改善，也不准以直接內縮 SEM 尺寸作任意訓練答案。

[R122](../../R122_OperatorPrinciples/reports/R122_RESULTS.md) 留下四個至今有效的理解：

1. 連續公式中的移動與變窄能分開，直接在像素上插值卻不一定保持相同意義。
2. 局部平均為零的細節仍可能推動邊界；不能稱它天然不影響位置。
3. 中心穩定可與尺寸偏差並存，共同偏差可在兩次位置相減時抵消。
4. V42 論文評估的 201 張影像來源與 9 個 SEM 半徑答案有直接訓練重用證據；不能把其成績当成未知樣品的優勢，也不推斷動機。

因此 [R123](../../R123_RealFirstModelDesign/reports/R123_DESIGN.md) 轉向完整二維重建：不用幾個物理名字限制所有真實結構，改讓每一步可追查，實際輸出由模型外的量法判斷。[R124](../../R124_RealFirstPrototype/reports/R124_RESULTS.md) 跑通原型；[R125](../../R125_DataAlignedPilot/reports/R125_RESULTS.md) 將內部表示由兩倍提高到四倍，但也發現亮暗範圍不符、未校準光學回饋及讀值錯配。[R126](../../R126_LearnabilityPhotometry/reports/R126_RESULTS.md) 修正學習速度與亮暗資料；[R127](../../R127_MeasurementPreservationRepair/reports/R127_RESULTS.md) 則證明先前數十像素跳值主要不能當作物體真的被移動，並拆開 SEM 尺度與取邊定義。

留下的要求：資料來源乾淨、數值正確、涵蓋實拍、有真正用途，四者都要檢查，不能互相替代。

## 8. R128–R130：目前實際保留了什麼

[R128 方法](../../R128_SourceOnlyFullTraining/reports/R128_METHODOLOGY.md) 明確移除推論時未具適用資格的光學回饋，只由影像提出四次共享修正；成像資訊可以用於合成資料及訓練要求，不能把真實模糊答案當成使用時已知輸入。四次訓練完成後只保留一條研究主線，不是要求日常部署四個模型。

[R128 與 R61 比較](../../R128_SourceOnlyFullTraining/reports/R128_LSC_R61_COMPARISON.md) 支持柱體間位移一致性與部分輪廓的改善，但 [清楚結構檢查](../../R128_SourceOnlyFullTraining/reports/R128_STRUCTURE_CHECK.md) 顯示角落、細線與清楚邊界仍會被修改。使用者其後確認正常拍攝為主，[範圍文件](../../R128_SourceOnlyFullTraining/reports/R128_APPLICATION_SCOPE.md) 因而降低極暗條件的優先度；沒有抹掉原暗圖失敗。

[對論文的同量法評估](../../R128_SourceOnlyFullTraining/reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md) 揭露 R128 並未包含原論文的全部實際部件，且計算慢、精細起伏未完全追回。使用者要求保留論文的主要創新，才形成 [R129 接入比較](../../R129_OpticalPriorHybrid/reports/R129_RESULTS.md)：實測光學融合、改善放大、原圖參照與簡化品質調整。

R129 有承接 R128 權重，並非從零訓練；新輸出頭承接與原圖參照本身就改變初始輸出，所以短測 A 組也不是原 R128，不能把 D 對 R128 的全部差異歸因於新光學與放大模組。

[R129 長訓練](../../R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md) 8192 次完成，細形狀误差從 21.352 降到 16.397 奈米，但尺寸差距從 80.679 增到 96.380 奈米。這種「細節追回、尺寸變差」已於早期保存點出現，不能期待任挑某輪就已全部解決。

[R130](R130_RESULTS.md) 以乾淨目標從零重訓 V42，保持 R129 不變。兩者使用相近資料後能力接近，舊 V42 的巨大細形狀優勢未重現；但新 V42 有較小尺寸差距及明顯速度優勢，不能說 V42 架構毫無價值。因訓練歷程、批次與起點未完全匹配，這不是單獨移除答案的因果實驗。

## 9. 對照目前實作的設計來由

本次直接閱讀 R129 整理版的 [組合入口](../../R129_OpticalPriorHybrid/model/organized/hybrid.py)、[四次重建](../../R129_OpticalPriorHybrid/model/organized/reconstruction.py)、[光學處理](../../R129_OpticalPriorHybrid/model/organized/optics.py) 與 [原圖參照](../../R129_OpticalPriorHybrid/model/organized/output_policy.py)，與 [架構紀錄](../../R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md) 交叉核對。

| 目前安排 | 歷史上的理由 | 現在能說到哪裡 |
|---|---|---|
| 一張原圖、原大小輸出 | 實際操作需求；多觀測尚未建立可靠共同收益 | 已實作；內部放大不等於新增真實解析度 |
| 完整二維表示 | 輪廓直接畫圖、單一剖面、固定頻帶對複雜形狀有失敗 | 已實作；不再要求每個像素都符合孤立單調邊界 |
| 同一小網路修正四次 | R123–R128 的可追查逐步修復 | 四步都有作用；四步最佳與成本最佳尚未證明 |
| 較細內部網格 | R117／R122 的取樣反例、R125 的表示誤差 | 四倍狀態、兩倍特徵；不是四倍真實超解析 |
| 光學處理先算一次 | 接回論文的實測資訊，同時固定全圖意義 | 確實影響輸出；並非每一步重新光學成像核對 |
| 改善放大在共享重建內 | R63 的條件性配對證據及 R129 模組接入 | 確實使用；沒有證明它單獨使目前所有量測改善 |
| 最後參照最初原圖 | R63、R112–R117 的低頻改動與外觀漂移教訓 | 限制改動；不能保證圓心、尺寸、乾淨圖都不變 |
| 光學及全圖統計保持全圖，局部網路分段 | R79–R86 曾因切圖改變答案；R129 大圖直接運算又遇限制 | 已有指定範圍的一致性驗證，不是任意切圖都等價 |
| 量測在模型之外 | 多輪內部指標與真正輸出不一致 | SEM、LSC 用實際輸出；不以模型自己的形狀預測自證 |

需要特別記住的缺口：原 V42 的獨立方向邊界分支未接入；R123 每步完整成像校正未保留；R127 特定條件下的精確原樣保留未整套移植；沒有完成可信區間的校準。光學候選自動加權雖有計算，但候選過於相似，現有實拍幾乎等同平均使用，額外效益未證實。

這些有的是刻意取捨，有的是未完成；不能全改稱「已經以另一種形式具備」。尤其「可查看過程」不等於「每個學到的特徵都有唯一物理解釋」。

## 10. 現在的證據基線與後續設計約束

以下只作同場景的實用比較，直接核對 R130 保存表與 R129 連續影像表；不混入論文另一份 120 對名單及不同輪廓演算法狀態。

| 指標 | R129 長訓練後 | R130 乾淨 V42 |
|---|---:|---:|
| 正常 SEM 尺寸差距，奈米 | 96.3803 | 91.9514 |
| 扣除平均尺寸後形狀差距，奈米 | 16.3972 | 16.4255 |
| 同一 120 對步距波動，奈米 | 6.9911 | 6.9194 |
| 同一 120 對九柱位移不一致，奈米 | 4.2037 | 4.6821 |
| 一張代表完整影像的處理時間，秒 | 9.9757 | 0.4279 |

來源：[雙模型比較表](../results/comparison.csv)、[連續影像完整解讀](../../R129_OpticalPriorHybrid/reports/R129_CONTINUOUS_LSC_RESULTS.md)。細形狀的兩個總體中位數幾乎相同，逐顆卻有 25/36 顆新 V42 較好，不能只挑對 R129 有利的小數差。完整 194 對比原選定 120 對的波動大很多，較差影格必須保留。速度只代表指定硬體、影像與方法。

之後保留 R129 主架構，但每個擬議改動都要回答：它修的是哪個已確認問題；哪一條原有能力可能被牽動；只改該因素時，在相同實拍與量法上有何結果。優先釐清目前尺寸偏移、輸出參照及放大層承接的作用，再考慮容量與加速。這是後續判斷原則，本次沒有啟動新試驗。

還有四條不能忘的界線：

1. SEM 柱體本來不圓，目標是保留真實起伏，不能強迫變成正圓。
2. 36 柱與多曝光屬同樣品的重複觀察；既有照片可供開發，不能改名成未知確認。
3. 舊 SEM 配對資料夾的 50x 名稱缺完整倍率佐證，R69／R123 已提醒；尺寸應使用該比較網格自己的尺度，不套原生相機比例。
4. 平台指令不是獨立量到的真正位移；輪廓讀法、SEM 材料邊界及光學亮暗位置也不能自動畫等號。

正式 COMBO、舊論文 V42、歷史比較 R61、目前研究主線 R129 仍是不同角色。可追溯訓練也不是 R129 專屬優點，R130 已證明 V42 同樣可以採用乾淨且可查的訓練流程。

## 本次留下的成果

這份回顧補足設計來由，不刷新任何舊驗收結論。主要閱讀清冊、目錄索引、現有表格的算術核對與本報告連結檢查，均另存於本輪 history_review_20260914。保護檔案的數值識別只用於檢查本次報告製作期間是否改動來源，不當作歷史科學结論成立的證明。
