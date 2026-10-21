# 實驗索引 / Experiment Index

Last updated: 2026-10-21（R94／R95／R97／R98 GitHub完整保存及取回重做；本輪不清D）
2026-10-21：[R94／R95／R97／R98完整方法、原模型、數據與失敗歷程](../docs/reproducibility/four_rounds/README.md)已補齊，GitHub取回1,092個原位置、32組原模型輸出相同；保留不利結果及缺件界限，沒有重新訓練或清理D。

最新論文比較已於2026-10-07完成：十方法各930張、8370讀值、30有效趟及零量測失敗，150次效率與162組完整趟次配對區間已核對。[完整交接與全部結果](R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)／[修改指南](R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/PAPER_UPDATE_GUIDE.md)。另兩官方後端受阻如實保留；監看已結束。原先七／九方法、暫停、恢復與追加SwinIR的順序見[整理前原索引](../docs/history/EXPERIMENT_INDEX_BEFORE_PROJECT_COMPLETION_20261021.md)，不再以舊「進行中」文字當目前狀態。

全專案GitHub保存續查進行中：[實際內容與完成條件](../docs/reproducibility/project_completion/README.md)。除實驗目錄外亦查共用訓練、光學校正、論文草稿／交接、原始資料和已搬到H槽的歷史；已補10條本機獨有版本歷史，18份原程式／設計取回相同。第一批851個補件位置已取回相同，含367份模型狀態、460張影像及24份分組資料；六份模型原生CPU執行及約405MB小包重做通過。第二批182471個原始紀錄、標記及論文版本位置已取回相同。全專案其他內容仍在核對，不宣稱全部完成。

來源全內容核對完成3820382個原位置；大型附件仍持續實際取回，不宣稱全專案完成。另保存光學頻譜新舊圖，並以原小型來源重算16份陣列458832數值相同；[版本與重算說明](../docs/reproducibility/optical_calibration/SPECTRA.md)。

原工具登入／工作清單備份原件留本機，已從私人草稿撤下並排除；研究原件、模型與論文不變，396份交付原件已重新從GitHub取回核對，39份原ZIP檢查與大型R61原ZIP合併檢查通過；總恢復入口仍未完成。[保留界線](../docs/reproducibility/project_completion/README.md#私人工具備份不屬於實驗保存)。

另核對目前22個H資料入口、19個實體根位置共29609份檔案，未見新增／變動／缺件；[最後交付檢查](../docs/reproducibility/project_completion/FINAL_PUBLICATION_PROTOCOL.md)仍須全部資料取回與總恢復實測，不能把單批核對當成全案完成。

Lab影像用途已按原紀錄釐清：126份數學平移輸入來自2張完整來源的6區，3份R56預覽不列為原拍；[原方法與原四表重做](../docs/reproducibility/lab_comparisons/README.md)保留不利排序、名義位移參照、分塊／整張速度及模型版本差異，不改目前研究採用。

完整數字、模型身分和外部GMF結果以 `ESTIMATOR_POLICY.json` 與各輪正式報告為準。[逐輪保存判讀](../docs/reproducibility/EXPERIMENTS.md)說明方法、來源和影像選擇；[原代表圖冊](../RECON_GALLERY.md)保留歷史順序。

保存續查另核對全新GitHub程式副本22218檔，補回兩份原文件暫存歷史及33個共用位置對照。[早期Round12–15](../docs/reproducibility/legacy_multiscale/README.md)的207分數與五次原選擇已取回重算，9個早期公式缺件明列；R88沿用未建資料／啟動中的舊文字已依原87輪停止紀錄修正並保存舊文。完整大型資料保存仍在進行，沒有重跑歷史訓練或升級模型。

續查已[補回R95兩版早期訓練程式](R95_CounterfactualGateRepairScratch/archive/recovered_training_sources_20261021/README.md)，均符合原登記並實際從GitHub取回；原更新狀態保存方式與第一次接續差異可直接追查。其他早期缺件保留，完整數值與影像仍逐批核對，不把找到兩份原程式當成全部舊訓練已重現。

[R89到R93的方法脈絡](../docs/reproducibility/scratch_lineage/README.md)已補完成狀態與來源判讀：R91／R92原結束摘要及逐輪表確認完整60／80輪，原進度active不改寫；R91只是檢查讀法對照，R92有光度／曝光修復與原件備份。原不利讀值、資料差異和未完成外部範圍保留。

**位移波動定義：**固定步數位置比較不同重拍趟次，與單趟走完30步的波動不同。[單趟完整重算與16方法比較](../Thesis_MOSR_Evidence/Model_Comparison_Reports/WithinScan_30Step_16Models_20260930/WITHIN_SCAN_30_STEP_16_MODEL_REASSESSMENT.md)保留原定義及逐趟結果。


保存續查補清[V41到V42完整來源與原表讀法](../docs/reproducibility/lab_comparisons/V42_HISTORY.md)：V41最佳第16輪是V42起點，兩輪短測、完整120輪及第10輪EMA最佳分開。原表欄名錯置另存核實讀法，原數字及原模型不改寫；約54MB固定模型小包已從GitHub實際取回，四次原生CPU完整小數及BMP相同，沒有重跑長訓練。

## Active（formal baseline + approved alternates）

| Round | 目錄 | Branch | 角色 | 關鍵報告 |
|-------|------|--------|------|---------|
| **COMBO** | `R38v2SeqFixed/` | `sandbox/r38v2` | formal production baseline | `R38v2SeqFixed/reports/COMBO_RESULTS.md` |
| **R33** | `R33RobustLoss/` | `sandbox/r33` | GMF extreme alternate | `R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md` |
| **R38v2** | `R38v2SeqFixed/` | `sandbox/r38v2` | visual priority alternate | `R38v2SeqFixed/reports/R38v2_RESULTS.md` |
| **R39R40_avg_a025** | `R39_ShapeGeneralization/results/a030_x_a043_sweep/` | (cross-round; checkpoints from `sandbox/r39` + `sandbox/r40`) | balanced full-spectrum alternate（2026-05-11 升級）| `R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md` |

## Open Research / Side Tracks

R152最新正式訓練TIFF影像版：[使用入口](../Deliverables/R152_Standalone_ImageFiles_20261004/start_here.py)／[訓練入口](../Deliverables/R152_Standalone_ImageFiles_20261004/train.py)／[完整TIFF版ZIP](../Deliverables/R152_Standalone_ImageFiles_20261004.zip)／[交付報告](R152_R148v2_SafeAdaptivePSF/reports/R152_TIFF_TRAINING_PACKAGE_20261004.md)。訓練目錄只有9216張TIFF，沒有PNG／NPZ；實際讀值、原前4次損失、續訓均精確一致，程式設定只用PY。舊NPZ版為來源快照。 已補[全部影像生成入口](../Deliverables/R152_Standalone_ImageFiles_20261004/generate_data.py)／[原始流程與核對](R152_R148v2_SafeAdaptivePSF/reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md)，無原影像可從固定種子重做全部9216 TIFF，像素與檔案完全相同。

R152獨立模型與完整訓練資料：[手動使用入口](../Deliverables/R152_Standalone_20261004/start_here.py)／[完整交付報告](R152_R148v2_SafeAdaptivePSF/reports/R152_STANDALONE_PACKAGE_20261004.md)／[完整ZIP](../Deliverables/R152_Standalone_20261004.zip)。768母場景／3072視圖、原幾何、25PSF及已訓練權重完整包內化；操作與設定一律PY。整張原生示例、全部來源輸入及短訓練前4次損失精確一致，另址與續訓已實跑，不重訓正式模型。

R152論文實際圖像補件：[25顆實際PSF、RAW／MOSR同區域與30次輪廓](R152_R148v2_SafeAdaptivePSF/reports/R152_THESIS_VISUAL_EVIDENCE_20261003/FIGURE_NOTES.md)。附第6.1／6.2.3／6.2.4節中英文圖說，實際矩陣與校正資料、原生影像、30趟64點邊界及九顆補充；共用亮度尺度、只平移對齊輪廓。[完整補件包](../Deliverables/R152_THESIS_VISUAL_EVIDENCE_20261003.zip)。

RAW／R152論文與網頁對話交接入口：[完整設計、訓練、驗證、公式與詳細結果](R152_R148v2_SafeAdaptivePSF/reports/R152_RAW_FULL_RECORD_20261002/REPORT.md)。採單趟30步波動主指標，30趟完整配對；只比較RAW與R152。灰階圖、逐筆數據、原設定及來源核對附於[完整交接包](../Deliverables/R152_RAW_COMPLETE_RESEARCH_RECORD_20261002.zip)。

| Round | 目錄 | 狀態 |
|-------|------|------|
| R152 R148v2安全PSF擴充 | [完整架構與實驗資料紀錄](R152_R148v2_SafeAdaptivePSF/reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md)／[單趟30步波動](R152_R148v2_SafeAdaptivePSF/reports/R152_SINGLE_SCAN_STEP_SD_20260930.md) | 原R148v2權重凍結，新增FFT／25 PSF／權重融合模組8192次訓練完成；930張與8370顆圓全部驗證。單趟30步波動合併標準差R152為4.865nm，RAW為10.200nm；30/30趟改善，逐趟改善36.9%～64.6%，R152與R148v2幾乎相同。最差直徑偏移微增0.000053nm；推論約慢2.2%、顯示卡峰值約多0.34GiB。權重仍近均分，SEM尺寸差仍高於RAW，不宣稱自適應成功或尺寸改善；原基準身分不變 |
| R151 R148v2＋自適應FFT PSF融合 | [設計與前測](R151_R148v2_AdaptivePSFFusion/reports/R151_DESIGN_AND_PREFLIGHT.md) | 已補回FFT、25顆PSF、特徵權重、加權融合、受限beta及殘差連接，並保留R148v2混合主幹與512/24分塊。接線、梯度、候選差異、原尺寸實拍與分塊均通過；但25選一、四群組與物理描述預測仍在隨機水準，故只保留可執行研究包，不做8192次正式訓練或效益宣告 |
| R150 實拍尺度幾何＋平均PSF | [完整結果](R150_MatchedGeometryMeanPSF/reports/R150_REAL_VALIDATION_RESULTS.md) | 8192次、930張與8370圓完成。短步3.876nm與去尺寸形狀16.483nm較R148v2改善；直徑重拍22.389nm、輪廓19.897nm及SEM差220.324nm退步。跨趟尺度更敏感，不升級 |
| R149 局部邊界失敗對照 | [失敗稽核](R149_MatchedGeometryLocalBoundary/reports/R149_AUDIT.md) | 兩版各兩起點均穩定，但共同局部邊界只改善0.75%／0.81%，未達3%門檻；無正式訓練，完整保留負結果 |
| R135 統一模型比較 | [結果](R135_UnifiedModelComparison/reports/R135_RESULTS.md)／[R61資料審查](R135_UnifiedModelComparison/reports/R135_R61_TRAINING_AUDIT.md) | 7組比較完成；R61確認使用35顆評估SEM尺寸值及均值監督，不能當乾淨替代；數值結果保留 |
| R134 直接影像狀態修正 | [保留精度驗證](R134_DirectStateRepair/reports/R134_PRECISION_REVALIDATION.md) | 保留精度版本長訓練及最終比較完成，尚未採用為正式模型；原8bit判定保留；未升級 |
| R133 尺寸機制診斷 | [已知幾何、真實SEM與底層方案](R133_SizeMechanismDiagnosis/reports/R133_RESULTS.md) | 64控制、128生成父場景、972SEM與強度對照；無統一合成膨脹，實拍學習階段向外增加。簡單換公式失敗；中性及限定幾何要求原型通過，但未訓練替代模型，先對齊成像／材料／讀法 |
| R132 邊緣保護研究 | [五種寬度、完整位移及裁切驗證](R132_BoundaryPolicyStudy/reports/R132_RESULTS.md) | 80保留過寬，16研究試用改善外圍細形狀；尺寸偏差與部分橫向結果變差。615筆SEM／9045圓心獨立核對；原模型及預設保留，無正式升級 |
| R131 R129反覆修復驗證 | [零至四次的實拍得失](R131_RecurrentStepValidation/reports/R131_RESULTS.md) | 相同權重、完整201張與正常SEM；第四次仍有細形狀收益，尺寸／位移／速度各自報告。1020張輸出、9045個圓心獨立核對；零訓練、未採用新版本，不宣稱四次架構已最佳 ；[半邊模糊原因](R131_RecurrentStepValidation/reports/R131_BOUNDARY_OUTPUT_AUDIT.md)：展示第18顆跨邊界原圖保留帶，已補中央完整重建例子 |
| R130 乾淨V42實用比較 | [32epoch訓練與真實比較](R130_CleanV42Comparison/reports/R130_RESULTS.md) | V42從頭訓練、共用乾淨合成來源；R129保持原樣。201張與SEM／LSC核對完成，尺寸偏V42、柱間一致性與橫向偏R129，細形狀相近；V42快很多。單次實用比較，非完整因果或未知資料證明，無升級 |
| R129 架構與獨立長訓練 | [201張連續LSC結果](R129_OpticalPriorHybrid/reports/R129_CONTINUOUS_LSC_RESULTS.md)・[長訓練](R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md) | 全部201張原生重建及LSC完成；固定120對R129步距波動6.991nm，R1286.873、R617.220。另報完整194對與3次重新定位。原尺寸退步仍需處理，無新訓練或升級 |
| R128 完整研究訓練 | [v34論文替換評估](R128_SourceOnlyFullTraining/reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md)・[先前R61比較](R128_SourceOnlyFullTraining/reports/R128_LSC_R61_COMPARISON.md) | 同v34名單補測：跨柱一致性改善約30%，位移波動相近；正常三張平均輪廓與尺寸較好，細部起伏相關及MZC較V42差。共同速度約慢12倍；暫不直接替換論文主模型，無重訓或正式升級 |
| R127 量測與保留修正 | [完成範圍與物理限制](R127_MeasurementPreservationRepair/reports/R127_RESULTS.md) | 原生SEM尺寸比例與取邊範圍、具有效性判斷的位移讀法、已知條件下原樣保留均完成。72個新參數測試通過；48完整視野輸出保留原小區塊，24組模型全圖位移與Raw相近。沒有新訓練或採用；材料邊界與獨立實際位置仍需對照 |
| R126 可學習性與亮暗擴充 | [完整驗證與下一步](R126_LearnabilityPhotometry/reports/R126_RESULTS.md) | 六組固定診斷768更新＋四組資料對照512更新、8次實拍评估全部完成。固定例子學習改善；暗例子Q比P誤差降低18–19%，但乾淨輸入改動加大，SEM參考結論分歧，位移讀值仍跳動。不採用或擴大訓練 |
| R125 資料修正與實際小試 | [完成範圍與不採用結論](R125_DataAlignedPilot/reports/R125_RESULTS.md) | 保留第一版失敗，修成8倍生成／4倍成像／2倍學習；64場景通過原限制。六組各64次更新共384次，12次實拍評估與來源核對完成。A正常曝光略好但暗曝光退步，B/C無可靠改善；資料亮暗與實拍仍有缺口，不擴大訓練 |
| R124 可執行模型原型 | [實作與實際運行結果](R124_RealFirstPrototype/reports/R124_RESULTS.md) | 四步完整二維模型、26項測試、兩張640px反向運算與分塊核對完成；6張實拍12份輸出、432筆SEM半對比讀值介接。未訓練、未校準、無效益或升級宣告；原始失敗及讀值敏感性保留 |
| R123 真實優先的下一代設計 | [架構、資料與實際核對](R123_RealFirstModelDesign/reports/R123_RESULTS.md) | 選定完整二維迭代重建與觀測核對、獨立幾何診斷。核對438個來源檔、364個主要真實光學檔與144個既有Raw選區；每次短測直接跑真實顯微／SEM。模型尚未實作／訓練，沒有新成績或升級 |
| R122 原理與資料來源驗證 | [實測結論與設計依據](R122_OperatorPrinciples/reports/R122_RESULTS.md) | 7,776 組操作、360 組修正後成像實測；像素插值不能當作純粹位置／寬度分離。V42 的 201 張位移評估來源、9 個尺寸答案均出現在訓練清單；1,000 組序列驗證也重用訓練影像對。下一步先做連續二維操作器，不以超越 V42 為目標；沒有新訓練或模型升級 |
| R109 / R119 固定模型量法核對 | [三種讀法與路徑比較](R119_SequenceGeometryValidation/reports/R119_R109_READOUT_COMPARISON.md) | 36 柱 ×12 曝光：R109 對 Raw 的 ACM 優勢不等於中點更準；R119 在兩者均較 R109 差。最陡點三方有效覆蓋不足，不能當一致通過。位置通道也會壓窄邊緣，R119 更明顯。無訓練、無升級；下一步先分清邊界定義與平移／寬度操作 |
| R119 模糊／亮度／位移控制與決斷 | [控制檢查與工作順序](R119_SequenceGeometryValidation/reports/R119_CONTROLLED_BOUNDARY_FACTORS.md) | 240 主條件＋100 亮度追查完成；標準模糊圓形受益於向外修正，但真實 Raw 對 SEM 已外偏約 0.661px。優先核對成像／邊界參考及亮度對比覆蓋，保留位置能力，不硬設縮小量、不啟動長訓練；物理來源尚未唯一確定 |
| R119 訓練位置分工診斷 | [已知答案與固定模型診斷](R119_SequenceGeometryValidation/reports/R119_TRAINING_POSITION_DIAGNOSIS.md) | 現有要求會罰最終影像膨脹，但無法區分相同輸出的位移／細節補償。固定 E42 關閉位置後，合成影像誤差在多數抽查場景反而增加；真實操作量則一致向外。原因範圍縮小，尚未證明單一訓練根因；無新訓練 |
| R119 跨曝光位置修正診斷 | [完整診斷結果](R119_SequenceGeometryValidation/reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md) | 固定 E42、12 曝光 × 36 柱；只關閉位置修正後 431/432 次輪廓改善、36/36 顆跨曝光中位數改善，但 282/432 次仍不如 Raw。位置路徑造成膨脹的證據跨曝光成立；細節保真與修改後位移未證實。舊證據不變，無新訓練或升級 |
| R118 / R119 Physical Coordinate Repair | [因果剖析與更正](R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md); `R118_PhysicalCoordinateRepairScratch/`; `R119_SequenceGeometryValidation/` | R119 B E42 訓練完成，但「忠實完成 P00–P12」已撤回：固定光學序列未接入訓練、對照與量測有混淆。保留實測 ACM/LSC 能力；單曝光真實 SEM 拆解指向邊界位置修正造成膨脹，並非證明必須犧牲細節。研究候選，不升級 |
| R88 Measurement Faithful Scratch | `R88_MeasurementFaithfulScratch/` | [87輪停止的失敗案例](R88_MeasurementFaithfulScratch/reports/R88_ABORTED_AT_E87.md)：原100輪計畫完成87輪，停止紀錄記最後保存第85輪。真實50倍輸出接近原圖且無驗證輪次通過；不續跑、不作下一輪初值，不改正式基準。已生成5,120正式觀察與384封存場景，不再沿用尚未建資料的舊規劃文字 |
| R87 Tile Native Scratch Generalization | `R87_TileNativeScratchGeneralization/` | 單次 100 輪從零訓練完成；分塊一致性與自身內部 ACM 通過，但 R73 新形狀與 R74 困難顯微明顯退化並產生假孔洞，因此不升級。保留為切片穩定研究模型與 R88 問題證據 |
| R83 R79 Severe Microscopy Strengthening | `R83_R79SevereMicroscopyStrengthening/` | 已完成但不升級。兩種乾淨微調都未超過 R79；保守整圖輸出在 R74 輪廓改善 23.42%，並通過 384 組保留合成影像、24 顆保留 SEM 與 6/6 真實位移，但 512 切片一致性失敗。因此預設仍為 R79，保守輸出只留作整張影像的受限選項，COMBO 正式 baseline 不變 |
| R79 R75v3 Dense Microscopy Scratch Generalization | `R79_R75v3_DenseMicroscopyScratchGeneralization/` | 第 23 輪 EMA 是目前研究線的強顯微候選，尚未取代正式 COMBO。R84-R86 已確認任何切片都會改變 R79 結果，因此來源入口與 ONNX 交付已根治為單次完整影像重建；12/12 跨場景逐像素對照通過，最大差 1 階灰階 |
| R61 STEP Generalization | `R61_STEP_Generalization_20260623/` | 近期多輪 R61 測試已收回 R 系列主線。這批不是雜散暫存，而是 Step/論文主力模型候選的研究線；最重要的是 `R61_stepguard_v16_dpv96_matched_20260623`。目前支撐 Step 樣本的位移穩定與 CD/形狀不失真證據，但尚未升級為 formal baseline，COMBO 仍是正式 baseline |
| R45 Family Boundary Adapter | `R45_FamilyBoundaryAdapter/` | R45A/R45B 完成：輸出端小校正守住位移但沒有改善大區塊/混合形狀；R45B 確認能力分散存在（逐張 oracle `0.2253` vs R44B `0.3384`，改善 `33.42%`；固定分族 oracle `0.2968`，改善 `12.30%`），但老師優勢不乾淨，多數老師在邊界像素殘差方向比 R44B 更差。研究負結果，不送外部 GMF；下一步若繼續單一入口，應做中間特徵層小分支 + 局部選擇器 |
| R44 Universal Boundary Motion Fidelity | `R44_UniversalBoundaryMotionFidelity/` | R44A-R44H Step B 皆已完成；`r44_motion_from_r42_best` 仍是最佳通用位移候選（整體位移 `0.3813 px`、格線位移 `2.2457 px`）。R44H Step A 證明家族平均可改善大區塊/混合形狀但會犧牲位移；Step B 單一老師局部蒸餾守住位移（`0.3837 px`）但形狀錯誤變差（`0.3481` vs `0.3384`）。研究成功但不可升級；不建議進 Step C 多老師全模型蒸餾，下一步應轉向 adapter / 分族小頭 / 分族選擇 |
| R43 Candidate Usability Audit | `R43_CandidateUsabilityAudit/` | analysis-only 近期候選堪用性盤點與肉眼檢查圖完成；沒有新候選可全面取代 COMBO；`R39 a030` 是最接近正式替代討論的近期候選，`R42` full endpoints 是顯微邊界重建最有價值的研究/人工檢查候選，但後補外部 GMF 確認不能作正式量測替代 |
| R42 Microscopy Boundary Fidelity | `R42_MicroscopyBoundaryFidelity/` | 訓練、本地完整分析、低比例權重平均、守門 KD 診斷與外部 GMF 補測皆已完成；R42 明顯改善未看過顯微邊界重建（最佳 PSNR 34.18、boundary F1 0.87，COMBO 為 20.55 / 0.63），但最佳外部候選 `r42_r41_best` 仍退步過大（8px +24.63%、0.8px +94.33%、0.08px +98.87%），所以 R42 僅保留研究用途，不建議作量測替代 |
| R41 Ring Distillation | `R41_RingDistillation/` | 訓練與 COMBO/R41 權重掃描已完成；direct endpoint 證明顯微能力很強（PSNR `29.4556` / HF `0.7241`），但沒有任何平均 alpha 同時通過顯微能力與本地環形守門；高 alpha 0.45/0.50 顯微通過但 0.8px/0.08px 環形失敗，所以 R41 僅作研究紀錄，不送外部 GMF。2026-08-01 完整歷史已核對封存至 H 槽，D 槽保留正式報告、摘要與恢復指引 |
| R40 Microscopy Feature Coverage | `R40_MicroscopyFeatureCoverage/` | 訓練、本地分析與外部 GMF 已完成；端點證明顯微特徵能力可被推高，但環形能力退步；`r40_combo_best_avg_a045` 改善顯微驗證，外部 8px 卻比 COMBO 退步 +22.80%，所以 R40 僅作研究紀錄，不升級 |
| R39 Shape Generalization | `R39_ShapeGeneralization/` | 訓練 endpoint 不可升級；`r39_combo_strong_avg_a030`（α=0.30 權重平均）external GMF PASS_TRADEOFF（8px −6.94%、0.08px −15.97% 專案歷史最低、0.8px +6.42% 在 alternate 容忍區內）；視覺在 sharp band（edge_steepness 比 COMBO 退 5.6%，遠優於 R33 soft band）；alternate-grade，等專案決策是否升級 |
| R26 PSF | `R26NewPSFCheck/` | pending external GMF; not active mainline |

## Closed / Falsified

| Round | 目錄 | Branch | Verdict |
|-------|------|--------|---------|
| R121 | [四組短測完整結果](R121_BoundaryAnchorFactorial/reports/R121_RESULTS.md) | `codex/r121-boundary-anchor` | 八次有效 12 輪短測完成；資料、位置與合併改動在兩種子／兩套 SEM 參考下，均 36/36 顆比對照差，細節誤差增 8.80%–17.95%。不採用、不長訓練；失敗原型與全部證據保留。本次設定的負結果，不代表所有局部位置方法均被否定 |
| R84 / R85 / R86 | `R84_R79TileStableRootRepair/`、`R85_R79SharedCanvasOpticalRepair/`、`R86_R79BlockGroupNormRepair/` | `sandbox/r84-r79-tile-stable-root-repair` | 三種結構修復都消除切片差異，但分別傷害 SEM 或邊界品質，不升級。保留精確 R79 並鎖定全圖入口；結案見 `R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md` |
| R32 | `R32Sandbox/` | `sandbox/r32` | external FAIL, 0.8px +97.7% |
| R33c | `R33ContrastFix/` | `sandbox/r33-contrast` | contrast fix did not recover |
| R34 / R35 / R37 | (sandbox only) | `sandbox/r34` / `r35` / `r37` | all failed to restore sharpness |
| R38 | `R38SeqConsistency/` | `sandbox/r38` | seq all-stages noise corrupted 0.8px |

Round31（legacy batch）亦 closed，見 `Traing_Progress/organized_20260316/round31/`。

## 完整系列報告

R33 → R38v2 → COMBO 的 12 候選 / 7 輪完整系列見 `R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`。

## 規範文件

- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 命名、模板、SOP 三合一
- `docs/operations/QUIRKS.md` — 歷史遺留事項

## R136 位移重拍比較

| 項目 | 報告 | 狀態 |
|---|---|---|
| R136 PI重拍比較 | [四組完整LSC](R136_PIRepeatability/reports/R136_LSC_FOUR_MODEL_RESULTS.md)／[原三組](R136_PIRepeatability/reports/R136_LSC_RESULTS.md) | 加入R128，各8370圓心；R128短步4.025nm、長距離15.496nm，與R129差距未明確；舊包保留 |

<!-- R136_SHAPE_SIZE -->
R136輪廓／形狀／尺寸重拍驗證：四組33480輪廓完成，R128尺寸／形狀波動13.558／13.560nm最小；實物準確度待使用者提供已確認存在的同批參考，不升級模型。 [報告](R136_PIRepeatability/reports/R136_SHAPE_SIZE_RESULTS.md)

<!-- R136_SEM_FOLLOWUP -->
R136 SEM追加核對（2026-09-19）：找回P/V各9張、三處副本18/18一致；舊配對36顆×3曝光×4方法完成，R128直徑差76.326nm、R129原80/16為96.624nm。使用者確認同片；九月九顆與舊SEM逐顆位置尚未建立，初步為不同區域；不混入30次統計。 [報告](R136_PIRepeatability/reports/R136_SEM_REFERENCE_RESULTS.md)

<!-- R136_CORNER9_COMPLETE -->
R136十字中心九顆重算完成（2026-09-19）：四組各930張／8370圓心；R128短步差3.708nm、尺寸波動9.527nm最小；SEM九顆集合均徑差R61+115.803nm、R128+222.040nm。集合22,23,24,28,29,30,34,35,36；逐顆方向保留兩候選。舊九顆有影像與PI但未配SEM，不混成尺寸真值證據。 [報告](R136_PIRepeatability/reports/R136_SEM_CORNER9_RESULTS.md)

<!-- R136_DIRECTION_INFERENCE -->
R136方向補查：已核對暗柱／亮孔；整視野較支持左右鏡像，暫用22,23,24／28,29,30／34,35,36。相同十字區域兩候選近乎同分，屬推定而非唯一證實；保留90度候選敏感度。 [方向依據](R136_PIRepeatability/reports/R136_SEM_DIRECTION_RESULTS.md)

<!-- R136_R128_CORNER9_DETAIL -->
R136最新十字九顆的R128專頁完成：位移30次曲線、60位置詳表、8370輪廓、逐顆及逐方向表、4張科學圖。短步重拍3.708nm，輪廓13.835nm；30μm終點偏差+41.966nm／重拍14.193nm，完整保留。 [R128詳表](R136_PIRepeatability/reports/R136_R128_CORNER9_DETAIL.md)

<!-- R136_RAW_R128_COMPLETE_COMPARISON -->
R136新十字九顆Raw/R128完整對照交付：10張圖（新增平均±1SD疊圖）、3600合併位移／32400逐顆位移／16740輪廓。R128短步PI差降低54.6%、短步重拍61.9%、輪廓重拍78.3%；SEM平均尺寸偏大差距185.182→222.040nm及終點偏差未改善亦完整保留。 [完整比較](R136_PIRepeatability/reports/R136_RAW_R128_CORNER9_RESULTS.md)

<!-- R128_CORNER9_THESIS_HANDOFF -->
R128修正取樣位置論文交接包（2026-09-20）：Deliverables/R128_Corrected_Corner9_Thesis_Handoff_20260920；先讀START_HERE.md與HANDOFF_FOR_THESIS.md。含Raw對照、修正後九顆、圖表、完整明細與方向推定限制；280檔約94MB，雜湊及閱讀連結檢查通過。

<!-- R129_CORNER9_REVALIDATED_20260920 -->
R129修正取樣位置再驗證完成（2026-09-20）：與Raw共16740圓擬合及720方向輪廓重算、4影像重播、60個R129不確定度分量重算通過。短步PI差4.125nm、重拍4.251nm；尺寸重拍19.231nm、輪廓18.437nm。SEM尺寸偏大224.472nm及30μm終點偏差+42.933nm保留。獨立論文交接包285檔約101MB，全部雜湊核對。 [R129報告](R136_PIRepeatability/reports/R136_RAW_R129_CORNER9_RESULTS.md)


## R130-Clean 原尺寸 scratch 新規格

2026-09-20完成：300101參數、PSF OFF、生成資料scratch8192更新及930張固定實拍驗收。位移保留R129水準、尺寸重拍改善，尺寸偏差仍在；完整影像神經推論約1.38秒。未升級正式基準。 [操作與來源](R130_Clean/README.md) · [完整結果](R130_Clean/reports/R130_CLEAN_RESULTS.md)

## R137 Weak PSF Feature 20260921

獨立8192次scratch與930影像驗證完成；短步及輪廓重拍小幅改善，尺寸偏大仍存在，不升級基準。[R137](R137_WeakPSFFeature/README.md)

## R138 V42 PSF Eight 20260923

R138：CPU訓練與驗證完成；8192次及930影像，尚無最終效果宣稱。[入口](R138_V42PSF8/README.md)

## R139 UNet Recurrent Prototype 20260923

真正三層編碼／解碼 U-Net 與跳接，融合 R130 四次共享修正、原圖參考、抗混疊上採樣；V42 八候選 PSF 在半解析度解碼位置最末次啟用。已完成8192次訓練與930張量測，但早期飽和後退化為原圖，模型不可用；請先讀 [R139因果審查](R139_UNetRecurrentPrototype/reports/R139_CAUSAL_AUDIT.md)。[設計入口](R139_UNetRecurrentPrototype/README.md)

## R140 Stable UNet 20260923

針對R139失穩，加入每像素跨通道正規化、較低學習率及早期飽和門檻。256次短測通過，但正式訓練前來源逐位元校驗失敗；無正式更新，原鎖定檔保留。[原版入口](R140_StableUNet/START_HERE.md)

## R140v2 Stable UNet 20260923

獨立重新封裝並完成8192次從零訓練、930張實拍及8370輪廓。相鄰PI平均差3.640nm、重拍3.530nm；尺寸與SEM仍有限制。PSF八候選最終全為等權，詳細原因見[因果審查](R140v2_StableUNet/reports/R140v2_PSF_GATE_CAUSAL_AUDIT.md)。原模型與完整證據保留。[結果](R140v2_StableUNet/reports/R140v2_RESULTS.md)

## R141 PSF25 Adaptive Top4 Standalone 20260923

使用現有25顆實測PSF，逐張影像從完整庫選四顆。獨立包包含訓練資料副本、程式、驗證器與衍生自R140v2主網路的可推論模型；真實原尺寸影像煙霧測試通過。選擇器尚未在這批近乎相同的實測PSF上證實有效，不繼承R140v2全930張量測結論。[操作入口](R141_PSF25_AdaptiveTop4_Standalone/README.md)

## R142 PSF100 Adaptive Top8 Standalone 20260923

完整100顆容量、逐張選八顆的網路、訓練及推論入口、資料副本和校驗已封裝。合成差異PSF的受控學習與整網路測試通過；尚未安裝指定的真實100顆PSF，正式推論與長訓練因此明確拒絕，不以測試PSF冒充。[操作入口](R142_PSF100_AdaptiveTop8_Standalone/README.md)

## R143 PSF25 Matched Pairs 20260924

沿用R141相同網路，將同一批合成場景的模糊改用既有25顆PSF均衡打散製作配對，從零完成8192次訓練、930張實拍與8370圓量測。短步PI差4.425nm，比R140v2的3.640nm高；直徑重拍波動24.161nm亦較差。既有SEM平均直徑差110.529nm，比RAW的185.182nm小74.654nm，但參照獨立性未封閉。生成測試PSF首選6/206，實拍930張全選同一顆第一名；不宣稱自適應成功或升級正式基準。[完整結果](R143_PSF25_MatchedPairs/reports/R143_RESULTS.md) · [穩定性原因診斷](R143_PSF25_MatchedPairs/reports/R143_STABILITY_DIAGNOSIS.md)

## R145 Corrected Center9 PSF25 Matched Pairs 20260924

將修正九顆圓編號後的新25顆PSF，同時用於同場景768組配對卷積與模型銀行；從零完成8192次訓練、930張實拍與8370圓量測，稽核通過。短步PI差3.990nm、直徑重拍21.013nm，較R143的4.425／24.161nm改善，仍不及R140v2的3.640／18.581nm；輪廓重拍16.001nm優於兩者。依本輪PSF擬合實際使用的SEM Excel值，平均直徑差+191.887nm，比RAW的+169.883nm更大；SEM是PSF校準輸入，沒有當神經訓練標籤，同九顆的尺寸比較不代表獨立準確度。生成測試首選6/206，實拍930張皆選同一顆第一名。後驗分析證實PSF頻域原點錯位、作用極弱和選擇訊號低於雜訊；不宣稱自適應成功或升級正式基準。方向錯誤的R144另存中止紀錄。[完整結果](R145_Center9PSF25_CorrectedPairs/reports/R145_RESULTS.md) · [穩定性追查](R145_Center9PSF25_CorrectedPairs/reports/R145_STABILITY_FOLLOWUP.md) · [PSF效益受限原因](R145_Center9PSF25_CorrectedPairs/reports/R145_PSF_LIMITING_MECHANISMS.md)

## R148v2 Hybrid Context + Native Boundary 20260926 — 訓練與930張驗證完成

8192次、930張與8370圓全部完成並通過稽核。短步PI差4.003nm，比Raw與R147好、仍落後R140v2；直徑重拍13.252nm為12方法最低，輪廓18.600nm。SEM平均直徑差204.281nm高於Raw 169.883nm，因此保留為尺寸重拍穩定候選，不宣稱尺寸更準或升級基準。[互動報告](../Thesis_MOSR_Evidence/Data_Reports/R148v2_Training_DeepDive_20260926/dist/index.html) · [門檻](R148v2_HybridContextNativePSF/reports/R148v2_VALIDATION_PLAN.md)

## R148 Measurement-Stable Native PSF 20260926 — 62次停止、架構需修正

R147診斷後的獨立版本：取消縮圖／放大主幹，以全原尺寸多距離卷積維持位置；768母場景重製3072視圖。初始門檻與64次短訓練通過，但首次正式程序停止於62次、沒有保存點。後驗核對證明四次網路與反覆PSF的累積依賴範圍超過訓練裁切中央答案的邊界，現設計不續跑。62筆及所有資料／失敗保留；無正式模型或930張結果，不取代任何既有版本。[實作紀錄](R148_MeasurementStableNativePSF/reports/R148_IMPLEMENTATION.md) · [架構核對](R148_MeasurementStableNativePSF/results/architecture_audit.json)

## R147 Full-Resolution PSF Consistency 20260926

沿用 R146 的研究25顆PSF與同768組配對，只改原尺寸PSF使用方式；8192次從零訓練、930張實拍／8370圓與最後核對完成。短步PI差4.537nm較R146的4.313nm高，直徑重拍16.336nm則較23.082nm低；輪廓19.751nm，SEM外框平均直徑差+207.067nm仍高於RAW的+185.182nm。內部四步、取樣位置、裁切、對比／模糊／雜訊、訓練梯度和768組祖源已實跑，歷史R137/R140/R145/R143及R121–R134教訓共同整理；不以單一控制排名替代實拍。H槽完整成果保留，D槽正式報告已同步，不升級正式基準。[完整結果](R147_FullResPSFConsistency/reports/R147_RESULTS.md) · [深度剖析](R147_FullResPSFConsistency/reports/R147_INTERNAL_AUDIT.md) · [改良計畫](R147_FullResPSFConsistency/reports/R147_OPTIMIZATION_PLAN.md)

## R146 SEM Core-Halo PSF25 Matched Pairs 20260925

依使用者指定的 `research_only` 真實P類SEM外框擬合25顆尖中心加淡尾PSF；預先封存的六張來源照片、18個留出圓外觀的預測優於原BADS與單一高斯。以R145同768組清晰母場景、分組、雜訊和PSF索引重新製作模糊配對，從零完成8192次訓練、930張實拍及8370顆圓量測，最終稽核通過。相對R145，短步PI平均差3.990→4.313nm、直徑重拍21.013→23.082nm、輪廓重拍16.001→20.371nm，均退步；起點相對位移重拍11.216→10.369nm改善，但其平均絕對差18.070→18.220nm未改善。與同九顆SEM外框點位參照的平均直徑差R146+218.744nm、R145+207.186nm、RAW+185.182nm。生成測試首選10/206、實拍930張全選同一顆；光學分支實際作用仍接近零，不能宣稱自適應PSF成功。SEM外框只用於PSF光學校準，未作神經清晰標籤；來源及模型保留研究身分，不升級正式基準。[完整結果](R146_SEMCoreHaloPSF25_MatchedPairs/reports/R146_RESULTS.md) · [退步原因核對](R146_SEMCoreHaloPSF25_MatchedPairs/reports/R146_CAUSAL_AUDIT.md)

## 2026-10-16 逐輪保存入口

這是後來補建的完整目錄導引，不改變當年設計、成功、失敗、中止或採用身分。最新十方法比較已於10月7日完成；前方較早的進度文字按原日期解讀。

| 實驗與歷史批次 | 研究問題 | 保存與重做說明 |
|---|---|---|
| [R100_CausalOperatorScratch/](R100_CausalOperatorScratch/) | 在原有形狀上加入輪廓外程序紋理 | [來源、結果與限制](../docs/reproducibility/experiments/main__R100_CausalOperatorScratch.md) |
| [R100_DesignValidation/](R100_DesignValidation/) | 訓練前檢查幾何零點、細節及量測讀法 | [來源、結果與限制](../docs/reproducibility/experiments/main__R100_DesignValidation.md) |
| [R101_HighFrequencyCausalAblation/](R101_HighFrequencyCausalAblation/) | 相同起點逐步加入弱邊緣及連續邊界機制 | [來源、結果與限制](../docs/reproducibility/experiments/main__R101_HighFrequencyCausalAblation.md) |
| [R101_HighFrequencyDesignValidation/](R101_HighFrequencyDesignValidation/) | 檢查高頻答案、邊界輸出與多目標學習為何失效 | [來源、結果與限制](../docs/reproducibility/experiments/main__R101_HighFrequencyDesignValidation.md) |
| [R102_UniversalDetailScratch/](R102_UniversalDetailScratch/) | 以局部主幹同時恢復細節與位置 | [來源、結果與限制](../docs/reproducibility/experiments/main__R102_UniversalDetailScratch.md) |
| [R103_RecoverableDetailScratch/](R103_RecoverableDetailScratch/) | 修復不可知亮暗答案與正規化造成的細節流失 | [來源、結果與限制](../docs/reproducibility/experiments/main__R103_RecoverableDetailScratch.md) |
| [R104_PhotometricInvariantCausalGateScratch/](R104_PhotometricInvariantCausalGateScratch/) | 將形狀判斷與絕對亮度分離 | [來源、結果與限制](../docs/reproducibility/experiments/main__R104_PhotometricInvariantCausalGateScratch.md) |
| [R105A_GeometryRendererFalsification/](R105A_GeometryRendererFalsification/) | 以學到的幾何直接畫出最終邊界 | [來源、結果與限制](../docs/reproducibility/experiments/main__R105A_GeometryRendererFalsification.md) |
| [R105B_EvidenceSetReconstructionFalsification/](R105B_EvidenceSetReconstructionFalsification/) | 多觀測是否持續改善輪廓並拒絕錯配 | [來源、結果與限制](../docs/reproducibility/experiments/main__R105B_EvidenceSetReconstructionFalsification.md) |
| [R105C_JunHuaMultiObservationFeasibility/](R105C_JunHuaMultiObservationFeasibility/) | 均華202原圖是否適合多觀測 | [來源、結果與限制](../docs/reproducibility/experiments/main__R105C_JunHuaMultiObservationFeasibility.md) |
| [R106A_MultiObservationShortValidation/](R106A_MultiObservationShortValidation/) | 從程序資料驗證多觀測機制能否轉到均華 | [來源、結果與限制](../docs/reproducibility/experiments/main__R106A_MultiObservationShortValidation.md) |
| [R107A_SingleImageEdgeGeometryProbe/](R107A_SingleImageEdgeGeometryProbe/) | 固定局部中心只收窄邊緣是否可行 | [來源、結果與限制](../docs/reproducibility/experiments/main__R107A_SingleImageEdgeGeometryProbe.md) |
| [R108A_LocalActionFalsification/](R108A_LocalActionFalsification/) | 既有模型是否互補、局部動作可否安全選擇 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108A_LocalActionFalsification.md) |
| [R108B_StagedParallelOpticalExpertsMicroprobe/](R108B_StagedParallelOpticalExpertsMicroprobe/) | 先學提案再學採用，比共同門控是否可靠 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108B_StagedParallelOpticalExpertsMicroprobe.md) |
| [R108C_IndependentOpticalSpecialistsMicroprobe/](R108C_IndependentOpticalSpecialistsMicroprobe/) | 分開檢查邊緣、紋理、去噪與照明專家 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108C_IndependentOpticalSpecialistsMicroprobe.md) |
| [R108D_MultiscaleNormalGeometryMicroprobe/](R108D_MultiscaleNormalGeometryMicroprobe/) | 增加邊緣專家的尺度與法線位移能力 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108D_MultiscaleNormalGeometryMicroprobe.md) |
| [R108E_ContourConservingProfileRendererMicroprobe/](R108E_ContourConservingProfileRendererMicroprobe/) | 先定位邊界及必要性，再於局部重建 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108E_ContourConservingProfileRendererMicroprobe.md) |
| [R108F_MonotonicProfileRendererMicroprobe/](R108F_MonotonicProfileRendererMicroprobe/) | 限制渲染範圍以避免暗圈與亮度超出 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108F_MonotonicProfileRendererMicroprobe.md) |
| [R108G_MidpointWidthFactorizedProfileMicroprobe/](R108G_MidpointWidthFactorizedProfileMicroprobe/) | 將法線位移與保中點寬度修正分開 | [來源、結果與限制](../docs/reproducibility/experiments/main__R108G_MidpointWidthFactorizedProfileMicroprobe.md) |
| [R109_StagedMidpointWidthScratch/](R109_StagedMidpointWidthScratch/) | 先固定偵測，再學受限位移與單調寬度 | [來源、結果與限制](../docs/reproducibility/experiments/main__R109_StagedMidpointWidthScratch.md) |
| [R110_TimeCapacityVisibilityProbes/](R110_TimeCapacityVisibilityProbes/) | 拆開訓練時間、容量與可見性限制 | [來源、結果與限制](../docs/reproducibility/experiments/main__R110_TimeCapacityVisibilityProbes.md) |
| [R111_R109V42ThesisReplacementQualification/](R111_R109V42ThesisReplacementQualification/) | 判斷R109能否替換論文V42 | [來源、結果與限制](../docs/reproducibility/experiments/main__R111_R109V42ThesisReplacementQualification.md) |
| [R112_V42R109GMFMechanismDecomposition/](R112_V42R109GMFMechanismDecomposition/) | 拆解V42與R109外部GMF差異 | [來源、結果與限制](../docs/reproducibility/experiments/main__R112_V42R109GMFMechanismDecomposition.md) |
| [R113_CausalStructureDissection/](R113_CausalStructureDissection/) | 拆開渲染能力、學到控制、訓練軌跡與量法 | [來源、結果與限制](../docs/reproducibility/experiments/main__R113_CausalStructureDissection.md) |
| [R114_ConfidenceGatedRecoverableScratch/](R114_ConfidenceGatedRecoverableScratch/) | 依R113修復控制塌縮與可恢復細節 | [來源、結果與限制](../docs/reproducibility/experiments/main__R114_ConfidenceGatedRecoverableScratch.md) |
| [R115_R109DecoupledNormalProfileScratch/](R115_R109DecoupledNormalProfileScratch/) | 以獨立法線證據決定R109動作採用量 | [來源、結果與限制](../docs/reproducibility/experiments/main__R115_R109DecoupledNormalProfileScratch.md) |
| [R116_CoherentGeometryAnchorScratch/](R116_CoherentGeometryAnchorScratch/) | 沿輪廓保持位移／寬度一致並限制細節 | [來源、結果與限制](../docs/reproducibility/experiments/main__R116_CoherentGeometryAnchorScratch.md) |
| [R117_CenterLockedSubpixelScratch/](R117_CenterLockedSubpixelScratch/) | 保留必要法線位移並避免寬度造成額外中心移動 | [來源、結果與限制](../docs/reproducibility/experiments/main__R117_CenterLockedSubpixelScratch.md) |
| [R118_PhysicalCoordinateRepairScratch/](R118_PhysicalCoordinateRepairScratch/) | 修正符號方向、連續寬度與真實二維定位 | [來源、結果與限制](../docs/reproducibility/experiments/main__R118_PhysicalCoordinateRepairScratch.md) |
| [R119_SequenceGeometryValidation/](R119_SequenceGeometryValidation/) | 檢查同物體序列訓練與邊界位置 | [來源、結果與限制](../docs/reproducibility/experiments/main__R119_SequenceGeometryValidation.md) |
| [R120_PhysicalSequenceRepair/](R120_PhysicalSequenceRepair/) | 修正R119序列形成與公平對照 | [來源、結果與限制](../docs/reproducibility/experiments/main__R120_PhysicalSequenceRepair.md) |
| [R121_BoundaryAnchorFactorial/](R121_BoundaryAnchorFactorial/) | 將亮暗擴充與局部位置要求做四組對照 | [來源、結果與限制](../docs/reproducibility/experiments/main__R121_BoundaryAnchorFactorial.md) |
| [R122_OperatorPrinciples/](R122_OperatorPrinciples/) | 驗證位置／寬度操作與V42訓練來源 | [來源、結果與限制](../docs/reproducibility/experiments/main__R122_OperatorPrinciples.md) |
| [R123_RealFirstModelDesign/](R123_RealFirstModelDesign/) | 以真實量測需求制定下一代模型 | [來源、結果與限制](../docs/reproducibility/experiments/main__R123_RealFirstModelDesign.md) |
| [R124_RealFirstPrototype/](R124_RealFirstPrototype/) | 實作四步二維重建及可保存重載的原型 | [來源、結果與限制](../docs/reproducibility/experiments/main__R124_RealFirstPrototype.md) |
| [R125_DataAlignedPilot/](R125_DataAlignedPilot/) | 先對齊資料形成與模型，再實際小訓練 | [來源、結果與限制](../docs/reproducibility/experiments/main__R125_DataAlignedPilot.md) |
| [R126_LearnabilityPhotometry/](R126_LearnabilityPhotometry/) | 先確認簡單例子能學，再匹配測試亮暗擴充 | [來源、結果與限制](../docs/reproducibility/experiments/main__R126_LearnabilityPhotometry.md) |
| [R127_MeasurementPreservationRepair/](R127_MeasurementPreservationRepair/) | 修正SEM比例／取邊、位移有效性與條件原樣保留 | [來源、結果與限制](../docs/reproducibility/experiments/main__R127_MeasurementPreservationRepair.md) |
| [R128_SourceOnlyFullTraining/](R128_SourceOnlyFullTraining/) | 用獨立生成來源做四個完整研究訓練 | [來源、結果與限制](../docs/reproducibility/experiments/main__R128_SourceOnlyFullTraining.md) |
| [R129_OpticalPriorHybrid/](R129_OpticalPriorHybrid/) | 恢復光學融合、抗混疊與原圖參考 | [來源、結果與限制](../docs/reproducibility/experiments/main__R129_OpticalPriorHybrid.md) |
| [R130_Clean/](R130_Clean/) | 移除光學與放大，採原尺寸純神經模型 | [來源、結果與限制](../docs/reproducibility/experiments/main__R130_Clean.md) |
| [R130_CleanV42Comparison/](R130_CleanV42Comparison/) | 以乾淨來源從頭訓練V42作實用比較 | [來源、結果與限制](../docs/reproducibility/experiments/main__R130_CleanV42Comparison.md) |
| [R131_RecurrentStepValidation/](R131_RecurrentStepValidation/) | 同一R129模型使用0到4次修正的得失 | [來源、結果與限制](../docs/reproducibility/experiments/main__R131_RecurrentStepValidation.md) |
| [R132_BoundaryPolicyStudy/](R132_BoundaryPolicyStudy/) | 檢查原圖保留帶是否過寬 | [來源、結果與限制](../docs/reproducibility/experiments/main__R132_BoundaryPolicyStudy.md) |
| [R133_SizeMechanismDiagnosis/](R133_SizeMechanismDiagnosis/) | 拆解尺寸偏大來自光學、學習還是最後輸出 | [來源、結果與限制](../docs/reproducibility/experiments/main__R133_SizeMechanismDiagnosis.md) |
| [R134_DirectStateRepair/](R134_DirectStateRepair/) | 直接修正影像狀態並避免8bit存檔誤導 | [來源、結果與限制](../docs/reproducibility/experiments/main__R134_DirectStateRepair.md) |
| [R135_UnifiedModelComparison/](R135_UnifiedModelComparison/) | 統一模型、保存精度與SEM／位移量法 | [來源、結果與限制](../docs/reproducibility/experiments/main__R135_UnifiedModelComparison.md) |
| [R136_PIRepeatability/](R136_PIRepeatability/) | 用30趟重拍檢查固定模型的位移與不確定度 | [來源、結果與限制](../docs/reproducibility/experiments/main__R136_PIRepeatability.md) |
| [R137_WeakPSFFeature/](R137_WeakPSFFeature/) | 以低強度光學線索輔助原尺寸模型 | [來源、結果與限制](../docs/reproducibility/experiments/main__R137_WeakPSFFeature.md) |
| [R138_V42PSF8/](R138_V42PSF8/) | 讓八候選光學機制反覆作用於特徵 | [來源、結果與限制](../docs/reproducibility/experiments/main__R138_V42PSF8.md) |
| [R139_UNetRecurrentPrototype/](R139_UNetRecurrentPrototype/) | 恢復U-Net並把光學放回解碼位置 | [來源、結果與限制](../docs/reproducibility/experiments/main__R139_UNetRecurrentPrototype.md) |
| [R140_StableUNet/](R140_StableUNet/) | 修復R139失穩並加短測限制 | [來源、結果與限制](../docs/reproducibility/experiments/main__R140_StableUNet.md) |
| [R140v2_StableUNet/](R140v2_StableUNet/) | 獨立重新封裝穩定U-Net | [來源、結果與限制](../docs/reproducibility/experiments/main__R140v2_StableUNet.md) |
| [R141_PSF25_AdaptiveTop4_Standalone/](R141_PSF25_AdaptiveTop4_Standalone/) | 逐張從25顆光學候選選四顆 | [來源、結果與限制](../docs/reproducibility/experiments/main__R141_PSF25_AdaptiveTop4_Standalone.md) |
| [R142_PSF100_AdaptiveTop8_Standalone/](R142_PSF100_AdaptiveTop8_Standalone/) | 擴為100顆並逐張選八顆 | [來源、結果與限制](../docs/reproducibility/experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md) |
| [R143_PSF25_MatchedPairs/](R143_PSF25_MatchedPairs/) | 以模型同一25PSF形成訓練配對 | [來源、結果與限制](../docs/reproducibility/experiments/main__R143_PSF25_MatchedPairs.md) |
| [R144_Center9PSF25_MatchedPairs/](R144_Center9PSF25_MatchedPairs/) | 更換中心九顆擬合的25PSF | [來源、結果與限制](../docs/reproducibility/experiments/main__R144_Center9PSF25_MatchedPairs.md) |
| [R145_Center9PSF25_CorrectedPairs/](R145_Center9PSF25_CorrectedPairs/) | 修正方向後完整測試新PSF | [來源、結果與限制](../docs/reproducibility/experiments/main__R145_Center9PSF25_CorrectedPairs.md) |
| [R146_SEMCoreHaloPSF25_MatchedPairs/](R146_SEMCoreHaloPSF25_MatchedPairs/) | 把真實SEM外框形成的中心淡尾PSF用於模型 | [來源、結果與限制](../docs/reproducibility/experiments/main__R146_SEMCoreHaloPSF25_MatchedPairs.md) |
| [R147_FullResPSFConsistency/](R147_FullResPSFConsistency/) | 修復資料與模型內PSF的尺度用法 | [來源、結果與限制](../docs/reproducibility/experiments/main__R147_FullResPSFConsistency.md) |
| [R148_MeasurementStableNativePSF/](R148_MeasurementStableNativePSF/) | 把決定邊界的主幹全部留在原尺寸 | [來源、結果與限制](../docs/reproducibility/experiments/main__R148_MeasurementStableNativePSF.md) |
| [R148v2_HybridContextNativePSF/](R148v2_HybridContextNativePSF/) | 一次多尺度脈絡加三段受控原尺寸邊界 | [來源、結果與限制](../docs/reproducibility/experiments/main__R148v2_HybridContextNativePSF.md) |
| [R149_MatchedGeometryLocalBoundary/](R149_MatchedGeometryLocalBoundary/) | 補接近實拍尺度的程序排列與局部邊界要求 | [來源、結果與限制](../docs/reproducibility/experiments/main__R149_MatchedGeometryLocalBoundary.md) |
| [R150_MatchedGeometryMeanPSF/](R150_MatchedGeometryMeanPSF/) | 保持架構，測新排列與訓練推論共用平均PSF | [來源、結果與限制](../docs/reproducibility/experiments/main__R150_MatchedGeometryMeanPSF.md) |
| [R151_R148v2_AdaptivePSFFusion/](R151_R148v2_AdaptivePSFFusion/) | 恢復可參與學習的光學加權融合 | [來源、結果與限制](../docs/reproducibility/experiments/main__R151_R148v2_AdaptivePSFFusion.md) |
| [R152_R148v2_SafeAdaptivePSF/](R152_R148v2_SafeAdaptivePSF/) | 保存R148v2效益並加入有作用的論文光學模組 | [來源、結果與限制](../docs/reproducibility/experiments/main__R152_R148v2_SafeAdaptivePSF.md) |
| [R153_MeanExternalBenchmark/](R153_MeanExternalBenchmark/) | 用九顆平均位移與外部架構完成論文比較 | [來源、結果與限制](../docs/reproducibility/experiments/main__R153_MeanExternalBenchmark.md) |
| [R26NewPSFCheck/](R26NewPSFCheck/) | 新PSF重訓、正式光學流程與交付版本的關係 | [來源、結果與限制](../docs/reproducibility/experiments/main__R26NewPSFCheck.md) |
| [R32Sandbox/](R32Sandbox/) | 加入真實影像訓練是否改善R30 | [來源、結果與限制](../docs/reproducibility/experiments/main__R32Sandbox.md) |
| [R33ContrastFix/](R33ContrastFix/) | 提高統計項能否修復R33的灰階與銳利度 | [來源、結果與限制](../docs/reproducibility/experiments/main__R33ContrastFix.md) |
| [R33RobustLoss/](R33RobustLoss/) | 減少極端像素牽引是否改善位移穩定 | [來源、結果與限制](../docs/reproducibility/experiments/main__R33RobustLoss.md) |
| [R38SeqConsistency/](R38SeqConsistency/) | 直接學習連續影像的一致性 | [來源、結果與限制](../docs/reproducibility/experiments/main__R38SeqConsistency.md) |
| [R38v2SeqFixed/](R38v2SeqFixed/) | 只保留有足夠訊號的序列訓練並結合R33 | [來源、結果與限制](../docs/reproducibility/experiments/main__R38v2SeqFixed.md) |
| [R39_ShapeGeneralization/](R39_ShapeGeneralization/) | 保留環形能力並擴大非環形重建 | [來源、結果與限制](../docs/reproducibility/experiments/main__R39_ShapeGeneralization.md) |
| [R40_MicroscopyFeatureCoverage/](R40_MicroscopyFeatureCoverage/) | 加入格線、紋理、區域與缺陷以補顯微能力 | [來源、結果與限制](../docs/reproducibility/experiments/main__R40_MicroscopyFeatureCoverage.md) |
| [R41_RingDistillation/](R41_RingDistillation/) | 用兩個固定老師同時保存環形與顯微能力 | [來源、結果與限制](../docs/reproducibility/experiments/main__R41_RingDistillation.md) |
| [R42_MicroscopyBoundaryFidelity/](R42_MicroscopyBoundaryFidelity/) | 直接提升通用顯微邊界，而非只優化環形 | [來源、結果與限制](../docs/reproducibility/experiments/main__R42_MicroscopyBoundaryFidelity.md) |
| [R43_CandidateUsabilityAudit/](R43_CandidateUsabilityAudit/) | 把既有候選放在同一決策表 | [來源、結果與限制](../docs/reproducibility/experiments/main__R43_CandidateUsabilityAudit.md) |
| [R44_UniversalBoundaryMotionFidelity/](R44_UniversalBoundaryMotionFidelity/) | 直接約束顯微結構隨已知位移正確移動 | [來源、結果與限制](../docs/reproducibility/experiments/main__R44_UniversalBoundaryMotionFidelity.md) |
| [R45_FamilyBoundaryAdapter/](R45_FamilyBoundaryAdapter/) | 用小修正或分族選擇承接R44分散能力 | [來源、結果與限制](../docs/reproducibility/experiments/main__R45_FamilyBoundaryAdapter.md) |
| [R46_CornerAwareFineTune/](R46_CornerAwareFineTune/) | 補強角點與直角同時檢查位移 | [來源、結果與限制](../docs/reproducibility/experiments/main__R46_CornerAwareFineTune.md) |
| [R61_STEP_Generalization_20260623/](R61_STEP_Generalization_20260623/) | 追蹤R61各版在Step及論文場景的實際效益 | [來源、結果與限制](../docs/reproducibility/experiments/main__R61_STEP_Generalization_20260623.md) |
| [R63_CausalBoundaryMotionAblation/](R63_CausalBoundaryMotionAblation/) | 拆開幾何、位移與安全上採樣的貢獻 | [來源、結果與限制](../docs/reproducibility/experiments/main__R63_CausalBoundaryMotionAblation.md) |
| [R64_IsocontourDisplacementReanalysis_20260724/](R64_IsocontourDisplacementReanalysis_20260724/) | 重新解讀等灰階輪廓位移 | [來源、結果與限制](../docs/reproducibility/experiments/main__R64_IsocontourDisplacementReanalysis_20260724.md) |
| [R65_V19_OldMethodFigurePackage_20260724/](R65_V19_OldMethodFigurePackage_20260724/) | 保存V19舊量法的論文圖表 | [來源、結果與限制](../docs/reproducibility/experiments/main__R65_V19_OldMethodFigurePackage_20260724.md) |
| [R66_V20_TraceabilityFigures_20260725/](R66_V20_TraceabilityFigures_20260725/) | 補齊論文圖與來源之間的可追查關係 | [來源、結果與限制](../docs/reproducibility/experiments/main__R66_V20_TraceabilityFigures_20260725.md) |
| [R67_UniversalModelGeneralization/](R67_UniversalModelGeneralization/) | 在既有倍率、形狀與位移下選較穩妥模型 | [來源、結果與限制](../docs/reproducibility/experiments/main__R67_UniversalModelGeneralization.md) |
| [R68_R61_RealFOVFeatureGeneralization/](R68_R61_RealFOVFeatureGeneralization/) | 檢查R61在多倍率完整視野的位移保持 | [來源、結果與限制](../docs/reproducibility/experiments/main__R68_R61_RealFOVFeatureGeneralization.md) |
| [R69_ACMContourSEMValidation/](R69_ACMContourSEMValidation/) | R61完整外形是否更接近逐顆SEM | [來源、結果與限制](../docs/reproducibility/experiments/main__R69_ACMContourSEMValidation.md) |
| [R70_V42ACMContourSEMValidation/](R70_V42ACMContourSEMValidation/) | 以相同SEM與量法檢查V42 | [來源、結果與限制](../docs/reproducibility/experiments/main__R70_V42ACMContourSEMValidation.md) |
| [R71_R61SyntheticMicroscopyDefectGeneralization/](R71_R61SyntheticMicroscopyDefectGeneralization/) | 以有乾淨答案的顯微缺陷檢查R61 | [來源、結果與限制](../docs/reproducibility/experiments/main__R71_R61SyntheticMicroscopyDefectGeneralization.md) |
| [R72_R61SyntheticDefectACMContourValidation/](R72_R61SyntheticDefectACMContourValidation/) | 把實拍同類輪廓量法用於已知答案的缺陷 | [來源、結果與限制](../docs/reproducibility/experiments/main__R72_R61SyntheticDefectACMContourValidation.md) |
| [R73_R61ExpandedSyntheticACMGeneralization/](R73_R61ExpandedSyntheticACMGeneralization/) | 以新生成非圓形檢查完整輪廓 | [來源、結果與限制](../docs/reproducibility/experiments/main__R73_R61ExpandedSyntheticACMGeneralization.md) |
| [R74_R61HardMicroscopyACMGeneralization/](R74_R61HardMicroscopyACMGeneralization/) | 避開容易測試的天花板，增加困難成像 | [來源、結果與限制](../docs/reproducibility/experiments/main__R74_R61HardMicroscopyACMGeneralization.md) |
| [R75_R61ArchitectureScratchGeneralization/](R75_R61ArchitectureScratchGeneralization/) | R61架構只用獨立純合成資料從頭訓練 | [來源、結果與限制](../docs/reproducibility/experiments/main__R75_R61ArchitectureScratchGeneralization.md) |
| [R75v2_R61ArchitectureScratchGeneralization/](R75v2_R61ArchitectureScratchGeneralization/) | 增加密集、多物件、亮暗及不修改案例 | [來源、結果與限制](../docs/reproducibility/experiments/main__R75v2_R61ArchitectureScratchGeneralization.md) |
| [R76_R75ACMContourSEMValidation/](R76_R75ACMContourSEMValidation/) | R75對36顆SEM完整輪廓的實體驗證 | [來源、結果與限制](../docs/reproducibility/experiments/main__R76_R75ACMContourSEMValidation.md) |
| [R77_R75v2ACMContourSEMValidation/](R77_R75v2ACMContourSEMValidation/) | 以同一實體量法檢查R75v2 | [來源、結果與限制](../docs/reproducibility/experiments/main__R77_R75v2ACMContourSEMValidation.md) |
| [R78_R75v2_BroadRealMicroscopeGeneralization/](R78_R75v2_BroadRealMicroscopeGeneralization/) | 同時檢查SEM外形與多倍率位移 | [來源、結果與限制](../docs/reproducibility/experiments/main__R78_R75v2_BroadRealMicroscopeGeneralization.md) |
| [R79_R75v3_DenseMicroscopyScratchGeneralization/](R79_R75v3_DenseMicroscopyScratchGeneralization/) | 加強密集排列與多尺度並防止過度重建 | [來源、結果與限制](../docs/reproducibility/experiments/main__R79_R75v3_DenseMicroscopyScratchGeneralization.md) |
| [R80_InflectionReferenceCircleSEMValidation/](R80_InflectionReferenceCircleSEMValidation/) | 以另一種取邊定義核對SEM與圓量測 | [來源、結果與限制](../docs/reproducibility/experiments/main__R80_InflectionReferenceCircleSEMValidation.md) |
| [R80_R79E23vsE100GeneralizationValidation/](R80_R79E23vsE100GeneralizationValidation/) | 比較R79訓練早期與最後模型的泛化 | [來源、結果與限制](../docs/reproducibility/experiments/main__R80_R79E23vsE100GeneralizationValidation.md) |
| [R81_MultiArchitectureReferenceCircleBenchmark/](R81_MultiArchitectureReferenceCircleBenchmark/) | 擴大外部架構的受控比較 | [來源、結果與限制](../docs/reproducibility/experiments/main__R81_MultiArchitectureReferenceCircleBenchmark.md) |
| [R82_R39R40CrossSceneGeneralizationBenchmark/](R82_R39R40CrossSceneGeneralizationBenchmark/) | 把核准替代與研究模型放到共同場景 | [來源、結果與限制](../docs/reproducibility/experiments/main__R82_R39R40CrossSceneGeneralizationBenchmark.md) |
| [R83_R79SevereMicroscopyStrengthening/](R83_R79SevereMicroscopyStrengthening/) | 修復R79困難成像並測試保守輸出 | [來源、結果與限制](../docs/reproducibility/experiments/main__R83_R79SevereMicroscopyStrengthening.md) |
| [R84_R79TileStableRootRepair/](R84_R79TileStableRootRepair/) | 移除R79對看到範圍的依賴 | [來源、結果與限制](../docs/reproducibility/experiments/main__R84_R79TileStableRootRepair.md) |
| [R85_R79SharedCanvasOpticalRepair/](R85_R79SharedCanvasOpticalRepair/) | 以共同光學畫布保留R79能力 | [來源、結果與限制](../docs/reproducibility/experiments/main__R85_R79SharedCanvasOpticalRepair.md) |
| [R86_R79BlockGroupNormRepair/](R86_R79BlockGroupNormRepair/) | 固定小區塊統計以消除切片差異 | [來源、結果與限制](../docs/reproducibility/experiments/main__R86_R79BlockGroupNormRepair.md) |
| [R87_TileNativeScratchGeneralization/](R87_TileNativeScratchGeneralization/) | 純局部模型從零學習重建及切片一致性 | [來源、結果與限制](../docs/reproducibility/experiments/main__R87_TileNativeScratchGeneralization.md) |
| [R88_MeasurementFaithfulScratch/](R88_MeasurementFaithfulScratch/) | 修復R87紋理與邊界並加入實際量測約束 | [來源、結果與限制](../docs/reproducibility/experiments/main__R88_MeasurementFaithfulScratch.md) |
| [R89_MeasurementNativeScratch/](R89_MeasurementNativeScratch/) | 移除輸出信心閘並直接學習有界重建 | [來源、結果與限制](../docs/reproducibility/experiments/main__R89_MeasurementNativeScratch.md) |
| [R90_ExposureCoherentScratch/](R90_ExposureCoherentScratch/) | 讓同一物體在四種曝光保持相同輪廓 | [來源、結果與限制](../docs/reproducibility/experiments/main__R90_ExposureCoherentScratch.md) |
| [R91_DetailDecoupledScratch/](R91_DetailDecoupledScratch/) | 分開紋理恢復與輪廓／曝光約束 | [來源、結果與限制](../docs/reproducibility/experiments/main__R91_DetailDecoupledScratch.md) |
| [R92_PhysicalTransitionBalancedScratch/](R92_PhysicalTransitionBalancedScratch/) | 補足物理邊緣過渡與平衡曝光取樣 | [來源、結果與限制](../docs/reproducibility/experiments/main__R92_PhysicalTransitionBalancedScratch.md) |
| [R93_RecoverableDetailSeparatedScratch/](R93_RecoverableDetailSeparatedScratch/) | 拆開可恢復細節及清楚輸入保護；64輪計畫、實際60輪停止，綜合候選48 | [來源、結果與限制](../docs/reproducibility/experiments/main__R93_RecoverableDetailSeparatedScratch.md)／[原始身分與GitHub重做審查](R93_RecoverableDetailSeparatedScratch/reports/R93_AUDIT.md) |
| [R94_EvidenceConditionalScratch/](R94_EvidenceConditionalScratch/) | 按成像順序分工並直接教何時需要修正 | [來源、結果與限制](../docs/reproducibility/experiments/main__R94_EvidenceConditionalScratch.md) |
| [R95_CounterfactualGateRepairScratch/](R95_CounterfactualGateRepairScratch/) | 修復R94修正閘與訓練動力問題 | [來源、結果與限制](../docs/reproducibility/experiments/main__R95_CounterfactualGateRepairScratch.md) |
| [R96_Design_Archive/](R96_Design_Archive/) | 保存R96正式設計前的舊方案 | [來源、結果與限制](../docs/reproducibility/experiments/main__R96_Design_Archive.md) |
| [R96_LocalizedEvidenceProtectedScratch/](R96_LocalizedEvidenceProtectedScratch/) | 防止聯合訓練抵消各局部分支的目標 | [來源、結果與限制](../docs/reproducibility/experiments/main__R96_LocalizedEvidenceProtectedScratch.md) |
| [R97_DirectCausalPhaseScratch/](R97_DirectCausalPhaseScratch/) | 直接預測每分支實際施加的修正 | [來源、結果與限制](../docs/reproducibility/experiments/main__R97_DirectCausalPhaseScratch.md) |
| [R98_AggressiveTextureScratch/](R98_AggressiveTextureScratch/) | 增加可見多尺度紋理的恢復強度 | [來源、結果與限制](../docs/reproducibility/experiments/main__R98_AggressiveTextureScratch.md) |
| [R99_GeometryTextureCoherentScratch/](R99_GeometryTextureCoherentScratch/) | 把亮暗、幾何、邊緣與紋理動作依序分開 | [來源、結果與限制](../docs/reproducibility/experiments/main__R99_GeometryTextureCoherentScratch.md) |

## 2026-10-16 GitHub保存收尾

[177個實驗／歷史批次的保存入口](../docs/reproducibility/EXPERIMENTS.md)與[完整下載、生成及數值重算](../docs/reproducibility/README.md)已完成。原實拍960檔、R61全部114283資料檔、R152全部9216 TIFF與十方法完整重算均由GitHub取回核對通過；各輪失敗及限制保留。D副本清理被執行工具拒絕，實際回收0，[收尾記錄](../docs/operations/GITHUB_PRESERVATION_CLOSEOUT_20261016.md)。
