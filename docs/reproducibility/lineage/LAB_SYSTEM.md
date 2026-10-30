# LabSystem完整研究線：先有校正與資料，再有各輪模型

2026-10-22。LabSystem永久屬於本專案論文工作區，是與原工業資料分開的成像條件與研究歷史。本頁補它的閱讀脈絡，沒有搬動、重新訓練或改變目前正式模型。

## Lab實驗資料夾之外的五個共用階段

原26個Lab實驗入口沒有把這五階段單列，不能因此略過它們。

| 階段 | 實際做了甚麼 | 原件與重要限制 |
|---|---|---|
| 光學校正 | 同一組25位置Lab ROI，用主專案的Whole-FOV Zernike／BADS流程；細預對齊改0.10px與385px裁切 | [粗細對齊比較](../../../LabSystem_MOSR/psf_calibration/reports/FINE_PREALIGN_COMPARISON_20250608.md)。中心更穩不代表全面勝過高斯，原高斯控制保留 |
| stage01至33資料基礎 | 2,968組乾淨答案、Lab BADS輸入與高斯控制；1100環形配對；R39 safe1240／strong1590／保留210，R40訓練1300／保留100 | [完整資料基礎](../../../LabSystem_MOSR/Training_Data/reports/LAB_TRAINING_DATA_STAGE01_33_20250608.md)。stage是資料類型，不是33次訓練；第一批沒有R41／42／44資料 |
| 相容起點與25輪短跑 | 沿用COMBO網路權重，去掉舊PSF緩衝並以Lab25位置重建；Lab R39及R40各25輪 | [原bootstrap](../../../LabSystem_MOSR/Experiments/reports/LAB_TRAINING_BOOTSTRAP_20250608.md)。PSF緩衝不同不表示整個模型從零；略過驗證的輪次不能當品質比較 |
| 首次100輪正式訓練 | R39 safe及R40 combo各100輪，沒有開force_fast_eval；原log仍只有50個偶數輪填正式驗證 | [完整100輪報告](../../../LabSystem_MOSR/Experiments/reports/LAB_FORMAL_TRAINING_100E_20260609.md)。品質最佳第100輪與內部best第21／44輪都保留，之後按實拍量測另判 |
| 首次實拍GMF與角點失敗 | 51張棋盤照片，外部只有50列／49步；重建對整段步長波動只有小幅改善，同時角點受損 | [原五種GMF結果](../../../LabSystem_MOSR/Experiments/reports/LAB_CHECKBOARD_EXTERNAL_GMF_20260611.md)、[根因拆解](../../../LabSystem_MOSR/Experiments/reports/LAB_GMF_ROOT_CAUSE_DEEP_PROBE_20260611.md)。共同異常步留在主結果，移除只作診斷 |

資料原生成器是[Lab乾淨資料](../../../LabSystem_MOSR/Training_Data/Data_Simulaion.py)與[Lab光學卷積](../../../LabSystem_MOSR/Training_Data/PSF_Convolution.py)，並由各輪原資料組合器建配對。它們和主專案同名程式有Lab路徑及控制差異，不能混用。

## 為甚麼R46一路做到R62

R46加入角點，R47增加更真實邊界，R48加入實體失敗形態與幾何標記，R49加入可信區域CAD；較長訓練與較低內部誤差仍未修好實拍角點。因此R50先診斷模糊來源，R51混合光學短測，再到R52加入穩定限制。

R53重配資料，過程中的OOM、Windows記憶體、PSF-forward過慢及最後可跑設定都是研究脈絡。R54則證明可信遮罩若只有平坦內部，損失降低不表示學到邊緣；補上CAD邊帶後局部能學，實拍仍失敗。R55修答案亮暗風格後best通過Lab角點門檻，但latest退步；R56只修答案核心並未解決尾端偏移。

R57至60轉到SEM與尺寸答案：同樣本錨點、半量修正、同影像後修正，以及實拍標記方向和權重逐一釐清。R61擴大通用邊界與位移保護，R62延續目標樣品、老師與原圖保護。這條路不能被壓縮成「模型越後面越好」或「SEM分數就是獨立準確度」。

## V41與V42接在哪裡

V41的原設計從R61v16起步，用R62 v13老師配對11,254組，不是從探索期某個V41檔案隨意續訓。V42原180組兩輪短測再加入軟答案邊帶與品質閘；後來完整120輪及平滑best第10輪另有完整來源。[原V41設計](../../../LabSystem_MOSR/Experiments/V41_Standalone/V41_STANDALONE_DESIGN.md)、[原V42短測](../../../LabSystem_MOSR/Experiments/V42_SoftLabelSNR/V42_SOFTLABEL_SNR_SMOKE_RESULT.md)、[已釐清的完整V42歷史](../lab_comparisons/V42_HISTORY.md)必須一起閱讀。

主專案R41是環形蒸餾，R42是顯微邊界；它們與Lab V41／V42不是同一實驗。主專案R61的STEP／論文驗證入口也不是另一份獨立從零R61模型。

## 平行研究

Base U-Net與EDSR／NAFNet有各自的資料、光學及訓練條件；兩個MOSR診斷則拆開最佳／末輪與推論設定。它們都不應因沒有R號就從沿革中消失。

[模型最佳點診斷的原數表讀法](LAB_BEST_CHECKPOINT_READING.md)本次補上原本缺少的文字入口，分清118／120步的共同有效母體與缺測。數學平移測試另使用兩張原來源、六區及126份衍生輸入，不等於平台30趟重拍。

## 保留與重做的界線

R61 v16的3,400組繼承來源、歷史幾何與16,896組新合成配方均有各自身分，見[生產方法](../GENERATION_GUIDE.md)與[原檔對照](../r61_regeneration_example/README.md)。後續V41／V42的目標樣品和老師來源也不能僅以一個種子代替。

目前論文採用仍回到R152／RAW及R153交接；本頁呈現Lab研究歷史，不把舊稿「final」字樣改成現在正式採用。各輪完整數表、不利結果、未採用與已移到H的原歷程均保留原角色；大型生成產物按目前精選原則留本機／H。

[2026-10-23逐輪必要來源與模型核對](../round_source_reviews/LAB_SYSTEM_20261023.md)已將26輪代表模型、原拍／SEM／PSF、資料清單及R62兩個固定輸出模型接回深層目錄；不重傳既有附件。

## 各研究的實際來源與結果

下列26項逐一回到自己的原報告；相近名稱不合併成同一模型。

| 研究 | 本輪必要來源與身分 | 原結果及限制 |
|---|---|---|
| [BaseUNet_Baseline_20260718](../experiments/lab__BaseUNet_Baseline_20260718.md) | 分清縮小資料、完整資料、固定PSF與分塊30輪各版；保留各自資料清單、Base U-Net權重、原推論設定及五方法原表。舊輸出沿用V42欄名，方法身分必須回到實際模型與設定。 | 不同資料量／固定光學／切片與輪次版本分開；輸出報告沿用V42欄名需核對實際方法身分 |
| [Modern_Restoration_Benchmarks_20260719](../experiments/lab__Modern_Restoration_Benchmarks_20260719.md) | 保留EDSR十五輪、NAFNet三十輪的原分組與最低驗證模型、固定光學前後處理、柱／孔／線三類來源與完整表；與R153後來的十方法比較分開。 | 30輪NAFNet與15輪EDSR各取最低驗證模型；同系統轉移且含固定光學轉換，不宣稱所有指標第一 |
| [MOSR_BestCheckpoint_Diagnostic_20260724](../experiments/lab__MOSR_BestCheckpoint_Diagnostic_20260724.md) | 唯一改動是以訓練選中第10輪替換MOSR第120輪；保留原manifest、Raw鎖定每序列30相鄰步、九顆參照設定、可用性與共同有效母體四張CSV。柱的共同母體118、孔120；不能把缺兩步默默補值。 | 保留共同有效母體及缺測，不以較好的一個模型覆蓋另一版 |
| [MOSR_CheckpointConfig_Diagnostic_20260724](../experiments/lab__MOSR_CheckpointConfig_Diagnostic_20260724.md) | 保留第10／120輪、定位保護與取樣相位的原對照設定、相同Raw選擇及原診斷數表；比較目的是拆解差異，不能只留下最好的模型。 | 第10輪、120輪與定位保護各有取捨；取樣相位解釋限於已測條件 |
| [R39_ShapeGeneralization](../experiments/lab__R39_ShapeGeneralization.md) | Lab微調繼承COMBO的網路權重，但重建25位置Lab PSF緩衝；使用Lab生成的1240組safe形狀資料，保留25輪短跑與100輪正式run的各自紀錄。最佳檔與第100輪不能互換。 | 與主專案R39分開，Lab起點及成像條件不能互換 |
| [R40_MicroscopyFeatureCoverage](../experiments/lab__R40_MicroscopyFeatureCoverage.md) | 使用Lab專屬1300組micro資料、Lab 25位置PSF與相容起點；保留25／100輪、內部best第44輪與第100輪、51張實拍和50列外部GMF。不能以主專案R40或資料stage29至33替代這次訓練。 | 作後續角點實驗的固定Lab控制，不冒充主專案正式替代 |
| [R46_CornerAwareFineTune](../experiments/lab__R46_CornerAwareFineTune.md) | 從Lab R39 latest起步；1550組由550環形、350形狀、250顯微、400角點構成，另100組保留驗證。固定Lab PSF、25輪原表及51張棋盤角點失敗一起讀；主專案同名R46另列。 | 25輪有效但未修好實體圓角，未採用 |
| [R47_RealisticBoundaryGeneralization](../experiments/lab__R47_RealisticBoundaryGeneralization.md) | 保留Lab R39相容起點、4000訓練／800驗證組、較真實邊界及原Lab光學；第33輪best與第200輪末檔均須對照實拍角點，不能把內部重建改善當成轉移成功。 | 200輪仍未修好實體角點，較多訓練不等於有效 |
| [R48_RealCornerTransfer](../experiments/lab__R48_RealCornerTransfer.md) | 6000訓練／1200驗證組含幾何sidecars；保留120輪後續到200輪的兩段、Lab R39起點，以及第32／86／200輪三種讀法。實體角點更差是本輪完整結果。 | 內部改善但實體更差；200輪完整負結果保留 |
| [R49_CADAnchorRealGeometry](../experiments/lab__R49_CADAnchorRealGeometry.md) | 從Lab R40 best起步，用4000組訓練與120組保留CAD錨點；必須保留可信遮罩、遮罩外原樣答案、100輪與三種原模型的角點表。局部CAD不能冒充全圖真值。 | 100輪仍使角點退步；可靠遮罩很小，不能當全圖答案 |
| [R50_PSFControlDiagnosis](../experiments/lab__R50_PSFControlDiagnosis.md) | 同一stage48角點比較實拍、正式BADS、高斯及弱BADS alpha0.50／0.75；保留原邊寬、梯度表和控制生成設定。這是模糊來源診斷，沒有新的正式訓練模型。 | 只做診斷；完整BADS比實拍更軟，混合光學需另試 |
| [R51_BlurSourceProbe](../experiments/lab__R51_BlurSourceProbe.md) | 三組各1550配對共用Lab R40 best起點，只比較高斯、弱BADS與混合PSF角點；各12輪／80批次。固定51張實拍、358角點，同時保留中位改善與大位移比例退步。 | 混合改善典型角點但大偏移比例上升，未採用 |
| [R52_CornerStabilityGuard](../experiments/lab__R52_CornerStabilityGuard.md) | 續接R51混合PSF best，4000訓練／700驗證組均有幾何檔；100輪內部best第23輪及末檔分開。原門檻同時要求中位改善與大偏移不增加，兩者不可只報一個。 | 100輪後實體大偏移仍多，負結果與完整H歷史保留 |
| [R53_RealisticDatasetCalibration](../experiments/lab__R53_RealisticDatasetCalibration.md) | 6000組重新平衡環、形狀、顯微、角點、背景與CAD，1740組驗證；保留R49可信遮罩與三種角點光學。從零100輪的batch16／workers4／關閉PSF-forward設定，以及OOM、Windows工作程序失敗和過慢嘗試都屬必要脈絡。 | 6000組／100輪從零完成但實體角點失敗；已清理批次不重算回收 |
| [R54_GeometryRootCauseProbe](../experiments/lab__R54_GeometryRootCauseProbe.md) | 先保留無效的平坦可信遮罩，再讀修正後72組含CAD邊緣的遮罩小測；Lab R40控制、遮罩內答案與遮罩外漂移均需保存。局部能擬合仍未轉移到51張棋盤，不據此續成可用模型。 | 可靠區域內可學，但轉到實體全圖失敗；不沿此模型續訓 |
| [R55_SourceStyleRealisticTraining](../experiments/lab__R55_SourceStyleRealisticTraining.md) | 使用修復來源亮暗風格的6000組R53式資料與1740組驗證，重新準備幾何；從零50輪沿batch16／workers4／關閉PSF-forward。best通過Lab角點門檻、latest失敗，外部GMF與正式採用另判。 | best通過Lab控制角點門檻，latest退步；外部回傳另記 |
| [R56_LabelCoreRepairTraining](../experiments/lab__R56_LabelCoreRepairTraining.md) | 沿R55配方僅修弱答案核心，保留6000組來源、原修復程式及保留驗證池；50輪best和latest均須對照R55。尾端角點退步不能因中位相同而省略。 | 50輪內部改善但實體尾端更差，未採用；H備份與既有清理紀錄保留 |
| [R57_GeometryConstrainedMOSR](../experiments/lab__R57_GeometryConstrainedMOSR.md) | 以R55的6000組加入2048組同樣本SEM／Basler錨點，共8048組及三種幾何sidecar；R57.1中心修復前後分開。SEM同時用於答案和比較，不能宣稱獨立SEM驗證。 | 同樣本幾何答案是訓練來源，不能當獨立SEM證據 |
| [R58_MeasurementClosedLoopMOSR](../experiments/lab__R58_MeasurementClosedLoopMOSR.md) | 保留原半量SEM半徑修正公式、各次512／4096理想圓錨點版本及幾何產生方式；frac050答案只修一半，且不是實拍裁切。第2輪best與後來30輪不得混成同一訓練證據。 | 答案故意只修一部分且缺實拍裁切，不能期待完全到SEM外框 |
| [R59_CDClosedLoopBoundaryLayer](../experiments/lab__R59_CDClosedLoopBoundaryLayer.md) | 來源是同一R58輸出與同樣本SEM尺寸；保存逐影像量測、估計尺寸偏移、邊界移動及R58版本。這是同樣本後修正，不是網路已學會正確輪廓或新獨立量測。 | 屬同樣本後修正，數字變好不代表網路學會或獨立準確 |
| [R60_SEMTruthBoundaryTraining](../experiments/lab__R60_SEMTruthBoundaryTraining.md) | 保留同樣本SEM表、71個實拍裁切、來源亮暗方向修正、重複12次成852配對及1024合成錨點；錯方向／過低實拍權重舊版與修正版分開，並保留CD門檻與PSF-forward停用理由。 | 方向與取樣修正後短測改善，完整歷史及SEM訓練依賴均保留 |
| [R61_BoundaryGeneralizationUniversal](../experiments/lab__R61_BoundaryGeneralizationUniversal.md) | 保留v1至v16的來源／失敗及固定起點；v16由3400組繼承來源與16896組新程序配對組成，合計20296組。繼承幾何必須凍結匯入，另保存seed6116、原step_guard_v16配方和實際分組；主專案R61是使用／驗證入口。 | 保留歷版；3400早期來源及舊輪廓不能單靠新推算取代 |
| [R62_TargetSampleBoost](../experiments/lab__R62_TargetSampleBoost.md) | 以R61v16及目標樣品來源作多版增補；保存各版真實裁切、數學位移、老師答案、SEM及原圖參考混合設定。anchor_detail035等後處理與各版網路分開，不能把較好相位位移等同全部局部圓心更準。 | 多版模型與固定後處理分開；相位位移恢復不等於所有局部圓心更準 |
| [Subpixel_Translation_Equivariance_20260720](../experiments/lab__Subpixel_Translation_Equivariance_20260720.md) | 保留兩張完整實拍來源、六個區域、126份數學平移輸入及原插值／量測程式；同來源的位移測試不是平台重新拍攝，也不是新的獨立樣本。完整配對表與不利EDSR比較一起留存。 | 插值位移不同於平台重新拍攝；MOSR未全面勝過EDSR，全部100配對與不利結果保留 |
| [V41_Standalone](../experiments/lab__V41_Standalone.md) | 從R61v16起步，使用11254組v13_measurement_view_safe_teacher配對；其中SEM錨點、目標樣品、位移與老師來源都必須記錄。原設計的兩段訓練敘事不等於全部從零或不含探索期答案。 | 起點R61v16及11254組目標樣品／老師資料都是必要來源，不可描述為完全獨立從零 |
| [V42_SoftLabelSNR](../experiments/lab__V42_SoftLabelSNR.md) | 原兩輪短測使用180組／15角色，以V41 best起步，只柔化答案邊帶並加入品質閘；後來完整120輪、平滑best第10輪與末檔是另一組完整來源。保留V41／R61、老師與同樣本SEM依賴，不將V42當主專案R42。 | 兩輪180組煙霧結果與後來E120論文模型分開，實際E120來源須追查完整run與模型包 |


2026-10-22補查：[Lab R61內部r36](R36_IDENTITIES_20261022.md)有原6輪命令、v10的7,496組、原96案例完整表與未採用原因；內部r36／r37／r39不能與主專案同號實驗合併。
