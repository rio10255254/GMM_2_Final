# 逐輪精選保留與封存清單

使用者最新確認：能由程式重新產生的大型資料，以保存生成程式、設定、種子、環境與必要來源為主，不必上傳整套產物，也不要求先完整重建並逐份核對才准省略。來源依賴或重現限制如實註明；原始拍攝、原始量測、人工標記與完整實驗結果不能用生成程式取代。 此規則優先於舊完整鏡像計畫與「先完整重建才能省略」的條件；本清單的基礎來源仍按其真實用途和取得方式交代。

這份清單整理177個研究／歷史範圍的問題、判讀、來源、現有程式與數表，以及大型內容留在何處。它是較早首版的固定快照，不是新的批次上傳工作。後續已收斂373個主要圖位置、16個模型用途及完整來源界線，見[目前交付範圍](../SELECTIVE_DELIVERY.md)；不是要求每輪所有產物全部上傳。

## 後續已交付的精選更新

- [早期R33至COMBO](EARLY_RECON_SELECTION.md)：34張原重建圖、140份完整原量測，整套逐張輸出從目前閱讀版本省略。
- [R100／R103／R104完整小型結果](FAILURE_LINEAGE_READING.md)：130份原後測CSV／JSON，保留曝光、SEM、位移與共同有效範圍。
- [資料生產方法](../../GENERATION_GUIDE.md)：18條原設定確認的路線，177範圍的程式／設定及來源引用索引；只補11份約86KB原小紀錄。

以下尺寸與13個模型／8張論文圖是較早首版的固定快照，不是上述更新後的即時總量；原身分與範圍保留。

首批補兩項原有小檔：完整18,000筆位移表與模型實際使用的25顆固定光學常數。關鍵模型引用已發布的精確相同內容，現有論文代表圖直接連回原報告；沒有新增模型或大批影像。

尺寸是原檔邏輯容量，不是Git壓縮容量，也不是新增上傳量。現有文字／程式／數表只建立索引，不重新複製。原本已在GitHub的其他圖不因出現在候選池便自動成為新精選；尚需逐輪依用途收斂。

## 已有明確用途的小型交付

| 項目 | 內容 | 大小與處理 |
|---|---|---|
| R153完整原讀值 | 18,000列；10方法的相鄰步與相對起點各9,000列，共用同批掃描 | 2,620,815 bytes原CSV，補入一般來源 |
| R153正式交接數表 | 15份原CSV，含失敗、SEM、全掃描比較與150次效率原樣本 | 合計2,810,403 bytes；其餘已在一般來源 |
| R152必要光學常數 | 25顆實際使用的固定常數、原排列及SEM幾何依賴 | 731,114 bytes原NPZ；不是重建影像庫 |
| 關鍵模型 | 13個用途記錄，依正式政策或原選模收據 | 13個有已發布精確相同內容；本次新增0 bytes |
| R152／R153論文圖 | 8張原報告指定圖，包含速度代價與固定同區比較 | 合計7,888,620 bytes；已存在，不重傳 |

[模型逐項來源](KEY_MODEL_REFERENCES.json)／[R153完整小型內容](R153_LIGHTWEIGHT_CONTENT.json)／[詳細逐檔索引](CURATED_FILE_MAP.json.gz)

## 每輪去向

「現有小檔」指程式、文件、數表、設定及原執行紀錄；不把所有JSON稱為量測值。模型及影像必須依用途選取，不能只看best／last檔名。完整數表與不利結果保留，像素陣列和未選中途模型留本機/H。

| 研究範圍 | 研究問題及判讀 | 現有小檔／大小 | 必要來源及選圖用途 | 新增模型／整批影像 |
|---|---|---|---|---|
| [main/R100_CausalOperatorScratch](../../experiments/main__R100_CausalOperatorScratch.md) | 在原有形狀上加入輪廓外程序紋理；本輪40輪獨立模型與設計前測分開 | 26份／0.29 MiB | 1250場景／5000觀測、線上紋理配方與實際40輪設定；圖：輪廓／紋理及各倍率同區域對照 | 不自動新增；大型原件留封存 |
| [main/R100_DesignValidation](../../experiments/main__R100_DesignValidation.md) | 訓練前檢查幾何零點、細節及量測讀法；這是分析前測，沒有R100正式模型 | 9份／0.09 MiB | 固定程序控制、既有真實來源及原始讀值；圖：改亮暗但幾何不變的量測敏感度 | 不自動新增；大型原件留封存 |
| [main/R101_HighFrequencyCausalAblation](../../experiments/main__R101_HighFrequencyCausalAblation.md) | 相同起點逐步加入弱邊緣及連續邊界機制；A／B／C為短期機制驗證，不能冒充正式長訓練模型 | 14份／0.12 MiB | 共同生成場景、共同初值與各組完整數值；圖：相同圖像下三組邊界中心／細節差異 | 不自動新增；大型原件留封存 |
| [main/R101_HighFrequencyDesignValidation](../../experiments/main__R101_HighFrequencyDesignValidation.md) | 檢查高頻答案、邊界輸出與多目標學習為何失效；125場景500觀測的前測發現細頻答案多不相位一致，E8後實拍細節崩落且學習方向互相衝突；這是根因設計，沒有新R101模型 | 7份／0.04 MiB | R93鎖定內測來源、E1到E40模型與四張實拍、各頻帶與更新方向完整讀值；圖：高頻答案不一致、E8轉折與合成指標和實拍相反的比較 | 不自動新增；大型原件留封存 |
| [main/R102_UniversalDetailScratch](../../experiments/main__R102_UniversalDetailScratch.md) | 以局部主幹同時恢復細節與位置；實際因原樣輸出塌縮而中止，原定48輪不算完成 | 23份／0.15 MiB | 固定5000觀測、實際歷程與塌縮診斷；圖：看似穩定但沒有恢復的案例 | 不自動新增；大型原件留封存 |
| [main/R103_RecoverableDetailScratch](../../experiments/main__R103_RecoverableDetailScratch.md) | 修復不可知亮暗答案與正規化造成的細節流失；來源／答案共用曝光，低頻／輪廓／紋理分工；保留曝光轉折失敗 | 35份／0.20 MiB | 程序配方、清楚反例與固定損失設定；圖：曝光18前後、紋理收益和清楚影像代價 | 不自動新增；大型原件留封存 |
| [main/R104_PhotometricInvariantCausalGateScratch](../../experiments/main__R104_PhotometricInvariantCausalGateScratch.md) | 將形狀判斷與絕對亮度分離；設計中的幾何頭未直接形成最終邊界，需由後續R105驗證 | 22份／0.15 MiB | 程序成像與相對亮度設定、各分支實際結果；圖：亮度不變形控制、邊界與必要性閘 | 不自動新增；大型原件留封存 |
| [main/R105A_GeometryRendererFalsification](../../experiments/main__R105A_GeometryRendererFalsification.md) | 以學到的幾何直接畫出最終邊界；1800次對照改善寬度但傷中心、形狀及切片；不開正式R105 | 12份／0.08 MiB | 共同初值、4倍幾何、600／1800次及原低解析失敗；圖：變窄卻移位、光暈與切片失敗 | 不自動新增；大型原件留封存 |
| [main/R105B_EvidenceSetReconstructionFalsification](../../experiments/main__R105B_EvidenceSetReconstructionFalsification.md) | 多觀測是否持續改善輪廓並拒絕錯配；程序短測支持多觀測方向，仍假設已對齊及已知成像條件 | 12份／0.09 MiB | 獨立場景、1／2／4觀測與重複／平均控制；圖：多觀測改善及錯配觀測拒絕 | 不自動新增；大型原件留封存 |
| [main/R105C_JunHuaMultiObservationFeasibility](../../experiments/main__R105C_JunHuaMultiObservationFeasibility.md) | 均華202原圖是否適合多觀測；同位置101對可作起點；跨位置共享會影響位移獨立性 | 9份／0.05 MiB | 202原始BMP、順序與配對、對齊及環中心讀值；圖：配對偏移、平均後細節損失與跨位置誤配 | 不自動新增；大型原件留封存 |
| [main/R106A_MultiObservationShortValidation](../../experiments/main__R106A_MultiObservationShortValidation.md) | 從程序資料驗證多觀測機制能否轉到均華；生成與真實短測未過，不啟動完整R106；主線回單張 | 11份／0.11 MiB | 共同短訓練、鎖定均華配對及所有不通過項目；圖：N2／N4未持續改善、壞觀測與曝光失敗 | 不自動新增；大型原件留封存 |
| [main/R107A_SingleImageEdgeGeometryProbe](../../experiments/main__R107A_SingleImageEdgeGeometryProbe.md) | 固定局部中心只收窄邊緣是否可行；先檢查理想方向與影像估計方向，避免把取向錯誤當渲染失效 | 19份／0.08 MiB | 5000／512場景生成、解析控制及後續學習設定；圖：方向已知／估計的寬度與中心差異 | 不自動新增；大型原件留封存 |
| [main/R108A_LocalActionFalsification](../../experiments/main__R108A_LocalActionFalsification.md) | 既有模型是否互補、局部動作可否安全選擇；知道答案時的上限與真正能從原圖選擇的能力分開 | 21份／0.13 MiB | 固定舊模型、共同答案、局部動作與選擇器結果；圖：最佳可能結果及實際選擇失敗 | 不自動新增；大型原件留封存 |
| [main/R108B_StagedParallelOpticalExpertsMicroprobe](../../experiments/main__R108B_StagedParallelOpticalExpertsMicroprobe.md) | 先學提案再學採用，比共同門控是否可靠；三組全新初值的機制短測，不是可交付模型 | 6份／0.04 MiB | 同一程序場景、各組實際步數與反事實答案；圖：修正被抑制及分階段效果 | 不自動新增；大型原件留封存 |
| [main/R108C_IndependentOpticalSpecialistsMicroprobe](../../experiments/main__R108C_IndependentOpticalSpecialistsMicroprobe.md) | 分開檢查邊緣、紋理、去噪與照明專家；任一專家未通過就不訓練組合，保留停止原因 | 34份／0.14 MiB | R108B資料的精確引用及四個獨立初值；圖：各專家本身的收益與失敗 | 不自動新增；大型原件留封存 |
| [main/R108D_MultiscaleNormalGeometryMicroprobe](../../experiments/main__R108D_MultiscaleNormalGeometryMicroprobe.md) | 增加邊緣專家的尺度與法線位移能力；與R108C固定專家比較，舊權重只作訓練後對照 | 8份／0.04 MiB | 程序資料、四尺度／兩位移機制及固定對照；圖：寬度修復和幾何副作用 | 不自動新增；大型原件留封存 |
| [main/R108E_ContourConservingProfileRendererMicroprobe](../../experiments/main__R108E_ContourConservingProfileRendererMicroprobe.md) | 先定位邊界及必要性，再於局部重建；新程序困難資料；未限制輸出造成的暗圈是後續修復依據 | 4份／0.03 MiB | 新生成資料、分階段偵測與渲染記錄；圖：暗圈、重疊、中心及原樣保留 | 不自動新增；大型原件留封存 |
| [main/R108F_MonotonicProfileRendererMicroprobe](../../experiments/main__R108F_MonotonicProfileRendererMicroprobe.md) | 限制渲染範圍以避免暗圈與亮度超出；重用R108E資料但不用其模型；位移與寬度仍可能耦合 | 10份／0.04 MiB | R108E精確資料、兩階段全新模型及光學尺度設定；圖：暗圈消除與中心／寬度代價 | 不自動新增；大型原件留封存 |
| [main/R108G_MidpointWidthFactorizedProfileMicroprobe](../../experiments/main__R108G_MidpointWidthFactorizedProfileMicroprobe.md) | 將法線位移與保中點寬度修正分開；此短測成為R109依據，仍不等於完整模型驗收 | 14份／0.04 MiB | 精確R108E資料、先偵測後渲染設定；圖：中點／寬度分工及不修改案例 | 不自動新增；大型原件留封存 |
| [main/R109_StagedMidpointWidthScratch](../../experiments/main__R109_StagedMidpointWidthScratch.md) | 先固定偵測，再學受限位移與單調寬度；48輪研究模型，後來LSC與外部GMF判讀不同；保留全部量法 | 30份／0.09 MiB | 5000／512程序資料、兩階段設定及E48模型；圖：中點、寬度、實體輪廓及外部穩定性 | 不自動新增；大型原件留封存 |
| [main/R110_TimeCapacityVisibilityProbes](../../experiments/main__R110_TimeCapacityVisibilityProbes.md) | 拆開訓練時間、容量與可見性限制；延續E48與兩個從零短測不是同一種因果證據 | 7份／0.02 MiB | R109 E48、各探針來源、獨立／繼承身分及實際步數；圖：三個假說對應的同區域輸出 | 不自動新增；大型原件留封存 |
| [main/R111_R109V42ThesisReplacementQualification](../../experiments/main__R111_R109V42ThesisReplacementQualification.md) | 判斷R109能否替換論文V42；固定LSC相近但外部GMF較弱；保留量測器狀態修復與不能全面替換結論 | 21份／0.15 MiB | V42 E120、R109 E48、Raw固定名單、重設後的量測程式；圖：不同目標的優劣與反覆量測一致性 | 不自動新增；大型原件留封存 |
| [main/R112_V42R109GMFMechanismDecomposition](../../experiments/main__R112_V42R109GMFMechanismDecomposition.md) | 拆解V42與R109外部GMF差異；內部模板沒有重現外部排序，因此未用來挑反事實架構 | 11份／0.07 MiB | 同100座標／99步、原外部分數與固定模型；圖：低頻錨定、局部寬度／位移及被否決代理 | 不自動新增；大型原件留封存 |
| [main/R113_CausalStructureDissection](../../experiments/main__R113_CausalStructureDissection.md) | 拆開渲染能力、學到控制、訓練軌跡與量法；已知答案上限、元件干預與檢查器修復分開保存 | 77份／0.61 MiB | V42／R61／R109固定模型、匹配來源及每個干預設定；圖：可達上限與實際模型、元件關閉及失敗 | 不自動新增；大型原件留封存 |
| [main/R114_ConfidenceGatedRecoverableScratch](../../experiments/main__R114_ConfidenceGatedRecoverableScratch.md) | 依R113修復控制塌縮與可恢復細節；短探針與正式訓練必須分開，舊模型只能作機制檢查 | 127份／0.91 MiB | 組成感知資料清單、控制／幾何／細節各探針及正式紀錄；圖：控制是否生效、清楚輸入與最差失敗 | 不自動新增；大型原件留封存 |
| [main/R115_R109DecoupledNormalProfileScratch](../../experiments/main__R115_R109DecoupledNormalProfileScratch.md) | 以獨立法線證據決定R109動作採用量；原資料與240張替換版分開；探針載舊模型不等於正式繼承 | 27份／0.11 MiB | A／B兩版精確資料、短探針和正式身分記錄；圖：採用量、替換前後及未過門檻 | 不自動新增；大型原件留封存 |
| [main/R116_CoherentGeometryAnchorScratch](../../experiments/main__R116_CoherentGeometryAnchorScratch.md) | 沿輪廓保持位移／寬度一致並限制細節；修復BF16錯誤後重新從零；E42主要、E24備選、E48未採用，GMF仍缺回傳 | 71份／0.34 MiB | 兩段訓練、精度修復、E42／E24／E48及固定驗證資料；圖：36顆粗輪廓改善、周長／位移代價及錯誤點 | 不自動新增；大型原件留封存 |
| [main/R117_CenterLockedSubpixelScratch](../../experiments/main__R117_CenterLockedSubpixelScratch.md) | 保留必要法線位移並避免寬度造成額外中心移動；來源是8倍生成後積分，不用實體答案或舊權重 | 23份／0.15 MiB | 本輪生成、被固定的成像形成順序及正式模型；圖：中心與寬度互相影響的控制及實體失敗 | 不自動新增；大型原件留封存 |
| [main/R118_PhysicalCoordinateRepairScratch](../../experiments/main__R118_PhysicalCoordinateRepairScratch.md) | 修正符號方向、連續寬度與真實二維定位；舊R117保留；下一步設計與已完成R118訓練不能混稱 | 42份／0.20 MiB | 5000／512固定幾何、新8倍觀測及封存確認狀態；圖：亮暗方向、零修正連續性及實體幾何 | 不自動新增；大型原件留封存 |
| [main/R119_SequenceGeometryValidation](../../experiments/main__R119_SequenceGeometryValidation.md) | 檢查同物體序列訓練與邊界位置；原P00到P12完整因果完成宣稱已撤回；固定序列未實際接入及混淆證據必須保存 | 111份／0.82 MiB | 真正被讀取的訓練觀測、E42、逐筆抽樣與後續因果審查；圖：向外膨脹、跨曝光關閉位置分支及量法差別 | 不自動新增；大型原件留封存 |
| [main/R120_PhysicalSequenceRepair](../../experiments/main__R120_PhysicalSequenceRepair.md) | 修正R119序列形成與公平對照；A應逐值匹配R118；B只改排程，共用評估答案，不能用混淆控制證明因果 | 28份／0.09 MiB | R118精確來源、8倍生成物理序列、實際探針與共同測試；圖：修正前後形成順序、A／B共同答案及位置控制 | 不自動新增；大型原件留封存 |
| [main/R121_BoundaryAnchorFactorial](../../experiments/main__R121_BoundaryAnchorFactorial.md) | 將亮暗擴充與局部位置要求做四組對照；兩起點八個有效短測均未通過；C v1中止與v2有效結果分開 | 57份／0.52 MiB | R118／R120精確來源、兩套SEM參照及八組設定；圖：兩起點／兩參照下共同退步與失敗版本 | 不自動新增；大型原件留封存 |
| [main/R122_OperatorPrinciples](../../experiments/main__R122_OperatorPrinciples.md) | 驗證位置／寬度操作與V42訓練來源；插值不保證獨立操作；V42評估來源重用訓練，不能稱未知驗證 | 15份／0.07 MiB | 7776操作、360成像控制、實際V42訓練／分組清單；圖：位置寬度耦合與資料祖源對照 | 不自動新增；大型原件留封存 |
| [main/R123_RealFirstModelDesign](../../experiments/main__R123_RealFirstModelDesign.md) | 以真實量測需求制定下一代模型；是設計與既有結果核對，沒有新模型成績 | 15份／0.16 MiB | 438來源索引、實際評估名單及設計條件；圖：設計取捨、來源地圖與既有失敗 | 不自動新增；大型原件留封存 |
| [main/R124_RealFirstPrototype](../../experiments/main__R124_RealFirstPrototype.md) | 實作四步二維重建及可保存重載的原型；未訓練、未校準；執行正常不能當量測改善 | 26份／0.16 MiB | 原型程式、兩個診斷成像設定、原始初始化與測試輸入；圖：初始化原樣保留、四步紀錄與未校準提示 | 不自動新增；大型原件留封存 |
| [main/R125_DataAlignedPilot](../../experiments/main__R125_DataAlignedPilot.md) | 先對齊資料形成與模型，再實際小訓練；第一版資料失敗、第二版六組64次完成但不採用 | 47份／0.56 MiB | 兩版生成、六組共同初值、12次實拍結果；圖：第一版失敗、正常改善與暗曝光退步 | 不自動新增；大型原件留封存 |
| [main/R126_LearnabilityPhotometry](../../experiments/main__R126_LearnabilityPhotometry.md) | 先確認簡單例子能學，再匹配測試亮暗擴充；固定例子改善，但實體參照分歧、乾淨輸入改動及位移跳動仍在 | 36份／0.18 MiB | 768固定更新與512匹配更新、共同實拍／SEM面板；圖：學習前後、暗例子與乾淨輸入損失 | 不自動新增；大型原件留封存 |
| [main/R127_MeasurementPreservationRepair](../../experiments/main__R127_MeasurementPreservationRepair.md) | 修正SEM比例／取邊、位移有效性與條件原樣保留；軟體修復與物理校準分開，沒有新訓練或獨立物理準確度 | 47份／0.29 MiB | 來源SEM、72讀法測試、48完整輸出與24模型位移；圖：錯峰、有效性判斷及原樣保留控制 | 不自動新增；大型原件留封存 |
| [main/R128_SourceOnlyFullTraining](../../experiments/main__R128_SourceOnlyFullTraining.md) | 用獨立生成來源做四個完整研究訓練；四次8192完成；保留選定研究版本、暗曝光代價、細形狀與較慢速度 | 200份／3.26 MiB | 768場景原生成鏈、四組初值／設定及各個固定比較模型；圖：正常／極暗、完整輪廓／細形狀與原生影像 | 不自動新增；大型原件留封存 |
| [main/R129_OpticalPriorHybrid](../../experiments/main__R129_OpticalPriorHybrid.md) | 恢復光學融合、抗混疊與原圖參考；短測、長訓練、80／16邊緣保留及完整LSC是不同版本；尺寸代價保留 | 109份／1.40 MiB | R128來源、25PSF、初始及長訓練模型、固定輸出規則；圖：模組活動、尺寸退步與全視野邊界帶 | 不自動新增；大型原件留封存 |
| [main/R130_Clean](../../experiments/main__R130_Clean.md) | 移除光學與放大，採原尺寸純神經模型；8192與930影像完成；較快、尺寸重拍較好，尺寸偏差仍在 | 116份／2.99 MiB | 768來源的精確白名單、固定最後模型與量測設定；圖：原尺寸細節、尺寸偏差與同一30趟位移 | 不自動新增；大型原件留封存 |
| [main/R130_CleanV42Comparison](../../experiments/main__R130_CleanV42Comparison.md) | 以乾淨來源從頭訓練V42作實用比較；32輪實用比較，訓練時間與起點未做完整因果匹配 | 51份／0.49 MiB | 512生成來源、官方／專案程式身分、固定模型與201原圖；圖：尺寸／柱間位移／速度各自比較 | 不自動新增；大型原件留封存 |
| [main/R131_RecurrentStepValidation](../../experiments/main__R131_RecurrentStepValidation.md) | 同一R129模型使用0到4次修正的得失；零次仍含光學與輸出規則；這不是不同深度從零訓練比較 | 22份／0.38 MiB | 同一長訓練權重、201原圖及每個修正次數讀值；圖：四步輸出、邊界保留帶與中央完整重建 | 不自動新增；大型原件留封存 |
| [main/R132_BoundaryPolicyStudy](../../experiments/main__R132_BoundaryPolicyStudy.md) | 檢查原圖保留帶是否過寬；16像素只作研究選項，尺寸與橫向代價仍需保留 | 18份／0.23 MiB | 固定R129、五種寬度、201原圖及裁切位置；圖：同一物件靠邊與中央、各保留寬度 | 不自動新增；大型原件留封存 |
| [main/R133_SizeMechanismDiagnosis](../../experiments/main__R133_SizeMechanismDiagnosis.md) | 拆解尺寸偏大來自光學、學習還是最後輸出；沒有找到可直接套用的統一縮小公式；成像與材料參照仍需核對 | 22份／0.27 MiB | 64控制、128生成來源、固定R129及972 SEM讀值；圖：同強度干預、已知幾何與實拍膨脹 | 不自動新增；大型原件留封存 |
| [main/R134_DirectStateRepair](../../experiments/main__R134_DirectStateRepair.md) | 直接修正影像狀態並避免8bit存檔誤導；精度修正版長訓練與最後比較完成；舊8bit失敗仍保留，尚未正式採用 | 123份／2.04 MiB | P1精確模型、保存精度、兩起點短測及長訓練資料；圖：8bit／保留精度、橫向偏移與SEM得失 | 不自動新增；大型原件留封存 |
| [main/R135_UnifiedModelComparison](../../experiments/main__R135_UnifiedModelComparison.md) | 統一模型、保存精度與SEM／位移量法；R61使用35顆評估SEM答案的限制必須與分數同時呈現 | 67份／2.34 MiB | 七組固定方法、共同201原圖、SEM映射與來源審查；圖：同一精度同一物件比較及訓練來源標示 | 不自動新增；大型原件留封存 |
| [main/R136_PIRepeatability](../../experiments/main__R136_PIRepeatability.md) | 用30趟重拍檢查固定模型的位移與不確定度；區域比對與LSC兩套數字分開；四方法追加保持先前包不變 | 1033份／2.02 MiB | 930原圖及PI讀值、各固定模型、原始圓心／邊界點與比例；圖：30趟曲線、最差尾端、輪廓與SEM來源對照 | 不自動新增；大型原件留封存 |
| [main/R137_WeakPSFFeature](../../experiments/main__R137_WeakPSFFeature.md) | 以低強度光學線索輔助原尺寸模型；短步與輪廓小改善、尺寸偏大；共用GPU舊計時不能直接排名 | 175份／4.09 MiB | R130資料、精確25PSF、8192模型及共同930原圖；圖：光學開關、各倍率細節及尺寸代價 | 不自動新增；大型原件留封存 |
| [main/R138_V42PSF8](../../experiments/main__R138_V42PSF8.md) | 讓八候選光學機制反覆作用於特徵；CPU與裝置續行要保留；光學強度後期歸零不能稱選擇成功 | 230份／5.40 MiB | 精確模型、25PSF、裝置歷程及R130資料；圖：光學強度歷程與原圖／輸出差別 | 不自動新增；大型原件留封存 |
| [main/R139_UNetRecurrentPrototype](../../experiments/main__R139_UNetRecurrentPrototype.md) | 恢復U-Net並把光學放回解碼位置；後續8192訓練早期飽和、退化為原圖；首頁原型狀態已過時 | 295份／6.70 MiB | 原型與正式程式、失敗完整歷程及因果審查；圖：飽和、原樣輸出與原型正確接線 | 不自動新增；大型原件留封存 |
| [main/R140_StableUNet](../../experiments/main__R140_StableUNet.md) | 修復R139失穩並加短測限制；短測通過但正式來源檢查失敗，沒有正式更新 | 346份／8.05 MiB | 來源鎖、256次短測及正式拒絕紀錄；圖：短測改善及失敗來源核對 | 不自動新增；大型原件留封存 |
| [main/R140v2_StableUNet](../../experiments/main__R140v2_StableUNet.md) | 獨立重新封裝穩定U-Net；8192與930完成，光學仍等權；短步收益與尺寸限制分開 | 349份／8.09 MiB | 凍結程式、最後模型、PSF與R130來源；圖：位移、光學權重歷程與尺寸比較 | 不自動新增；大型原件留封存 |
| [main/R141_PSF25_AdaptiveTop4_Standalone](../../experiments/main__R141_PSF25_AdaptiveTop4_Standalone.md) | 逐張從25顆光學候選選四顆；衍生自R140v2的可推論包，非已完成新長訓練與930驗收 | 336份／7.93 MiB | 精確衍生模型、25PSF及逐影像標記需求；圖：接線／選擇受控測試與單張實拍差異 | 不自動新增；大型原件留封存 |
| [main/R142_PSF100_AdaptiveTop8_Standalone](../../experiments/main__R142_PSF100_AdaptiveTop8_Standalone.md) | 擴為100顆並逐張選八顆；指定實測100顆未安裝；推論拒絕是正確行為，合成測試不冒充實測 | 336份／7.93 MiB | 未訓練起點、安裝條件與缺件紀錄，不能放測試PSF充數；圖：機制受控測試與缺少真實來源的狀態 | 不自動新增；大型原件留封存 |
| [main/R143_PSF25_MatchedPairs](../../experiments/main__R143_PSF25_MatchedPairs.md) | 以模型同一25PSF形成訓練配對；尺寸參照差較小但位移／重拍退步；PSF選擇不成功 | 421份／9.58 MiB | 768原場景、舊25PSF、配對標記與8192模型；圖：中心偏移、尺寸波動及所有方法相同原圖 | 不自動新增；大型原件留封存 |
| [main/R144_Center9PSF25_MatchedPairs](../../experiments/main__R144_Center9PSF25_MatchedPairs.md) | 更換中心九顆擬合的25PSF；方向對應錯誤，160次中止；不能與R145修正後完整結果混用 | 462份／10.77 MiB | 舊方向MAT、160次模型與停止原因；圖：方向對應與原錯誤銀行的示意／實測 | 不自動新增；大型原件留封存 |
| [main/R145_Center9PSF25_CorrectedPairs](../../experiments/main__R145_Center9PSF25_CorrectedPairs.md) | 修正方向後完整測試新PSF；位移／輪廓較R143改善但尺寸仍偏；同九顆SEM只屬校準同樣本比較 | 477份／10.93 MiB | 正式修正MAT、768共同場景、Excel與輪廓兩套參照；圖：方向修復、光學弱作用及尺寸／穩定性取捨 | 不自動新增；大型原件留封存 |
| [main/R146_SEMCoreHaloPSF25_MatchedPairs](../../experiments/main__R146_SEMCoreHaloPSF25_MatchedPairs.md) | 把真實SEM外框形成的中心淡尾PSF用於模型；較能預測照片不等於重建量測更好；多數短步與輪廓退步 | 538份／12.44 MiB | 研究PSF、六張凍結來源、18留出圓、768配對及模型；圖：PSF擬合優勢與量測退步並列 | 不自動新增；大型原件留封存 |
| [main/R147_FullResPSFConsistency](../../experiments/main__R147_FullResPSFConsistency.md) | 修復資料與模型內PSF的尺度用法；尺寸重拍改善但短步退步；後續脈絡／邊界分工需另驗證 | 621份／14.01 MiB | 同R146場景／PSF、原尺寸光學程式及完整8192模型；圖：四步剖析、取樣位置敏感度與重拍曲線 | 不自動新增；大型原件留封存 |
| [main/R148_MeasurementStableNativePSF](../../experiments/main__R148_MeasurementStableNativePSF.md) | 把決定邊界的主幹全部留在原尺寸；正式只留下62次且無保存點；累積依賴超出訓練邊界，不續跑 | 578份／13.72 MiB | 3072視圖生成配方、64次前測與62次失敗、架構審查；圖：有效邊界範圍與位置一致性控制 | 不自動新增；大型原件留封存 |
| [main/R148v2_HybridContextNativePSF](../../experiments/main__R148v2_HybridContextNativePSF.md) | 一次多尺度脈絡加三段受控原尺寸邊界；8192與930完成；尺寸重拍佳但尺寸偏差仍在，是R152基底 | 655份／15.68 MiB | 精確8192基底、共用3072視圖生成鏈與研究PSF；圖：架構、原圖／重建、跨趟輪廓與尺寸 | 不自動新增；大型原件留封存 |
| [main/R149_MatchedGeometryLocalBoundary](../../experiments/main__R149_MatchedGeometryLocalBoundary.md) | 補接近實拍尺度的程序排列與局部邊界要求；兩版短測都未達3%門檻，不開正式長訓練 | 25份／0.20 MiB | 96新排列場景、兩版／兩起點短測及原先門檻；圖：局部邊界改善不足及配對同場景比較 | 不自動新增；大型原件留封存 |
| [main/R150_MatchedGeometryMeanPSF](../../experiments/main__R150_MatchedGeometryMeanPSF.md) | 保持架構，測新排列與訓練推論共用平均PSF；短步與去尺寸形狀小改善，直徑重拍／輪廓／SEM退步；兩因素仍未分離 | 705份／16.82 MiB | R149鎖定資料、原全局要求、8192模型及固定930驗收；圖：跨趟尺度漂移與短步收益共同展示 | 不自動新增；大型原件留封存 |
| [main/R151_R148v2_AdaptivePSFFusion](../../experiments/main__R151_R148v2_AdaptivePSFFusion.md) | 恢復可參與學習的光學加權融合；機制可運作但現有25顆不能可靠辨識，未開始正式8192 | 24份／0.08 MiB | 精確25PSF、選擇可辨識前測、受限殘差與短測模型；圖：可區分控制、現有PSF失敗及原尺寸實拍 | 不自動新增；大型原件留封存 |
| [main/R152_R148v2_SafeAdaptivePSF](../../experiments/main__R152_R148v2_SafeAdaptivePSF.md) | 保存R148v2效益並加入有作用的論文光學模組；8192擴充與930完成；位移／重拍收益保留，尺寸偏大與較慢成本不可省略 | 137份／7.51 MiB | 可獨立重建的9216影像配方、精確PSF、基底／擴充模型、930原圖與完整讀值；圖：同視野原圖／重建、實際25PSF、30趟輪廓、尺寸與不利結果 | 不自動新增；大型原件留封存 |
| [main/R153_MeanExternalBenchmark](../../experiments/main__R153_MeanExternalBenchmark.md) | 用九顆平均位移與外部架構完成論文比較；十方法930張／30趟完成，兩官方後端受阻；各自訓練目標與不等輪數如實保留 | 258份／6.36 MiB | 共同R152生成資料、七個官方來源／實際改動／模型、完整圓心／邊界／PI／效率讀值；圖：十方法同視野比較、原生影像、最差情況及全部灰階論文圖 | 不自動新增；大型原件留封存 |
| [main/R26NewPSFCheck](../../experiments/main__R26NewPSFCheck.md) | 新PSF重訓、正式光學流程與交付版本的關係；新舊PSF政策與各次審查分開保留；早期首頁的等待狀態不能代表全部子研究 | 146份／1.83 MiB | 新舊PSF、實際起始模型、原始光學來源、各子研究設定；圖：新舊PSF、同一原圖重建、頻譜及光學擬合差異 | 不自動新增；大型原件留封存 |
| [main/R32Sandbox](../../experiments/main__R32Sandbox.md) | 加入真實影像訓練是否改善R30；內部檢查通過但外部0.8px大幅退步；保留未採用結論 | 26份／0.73 MiB | R30起始模型、真實訓練影像、固定合成資料與外部GMF原始回傳；圖：內外部結果落差及相同視野比較 | 不自動新增；大型原件留封存 |
| [main/R33ContrastFix](../../experiments/main__R33ContrastFix.md) | 提高統計項能否修復R33的灰階與銳利度；目標本身變化小，增加權重未恢復細節；負結果需保留 | 3份／0.00 MiB | R33起始模型、實際訓練設定及對應來源；圖：灰階對比和邊緣寬度並列，不能以顯示拉伸代替改善 | 不自動新增；大型原件留封存 |
| [main/R33RobustLoss](../../experiments/main__R33RobustLoss.md) | 減少極端像素牽引是否改善位移穩定；p95為已核准替代；保留穩定性收益及銳利度代價，連同R34／R35／R37失敗支線 | 17份／0.10 MiB | R30模型、當時PSF及環形／序列來源，固定GMF讀法；圖：穩定性與銳利度共同展示，附不利細節案例 | 不自動新增；大型原件留封存 |
| [main/R38SeqConsistency](../../experiments/main__R38SeqConsistency.md) | 直接學習連續影像的一致性；全尺度序列受到弱訊號干擾；這是R38v2修復的前因 | 5份／0.01 MiB | 624組舊序列、當時PSF、起始模型及各候選設定；圖：大步改善與小步退步的對照 | 不自動新增；大型原件留封存 |
| [main/R38v2SeqFixed](../../experiments/main__R38v2SeqFixed.md) | 只保留有足夠訊號的序列訓練並結合R33；R38v2是視覺替代；COMBO是正式基準，兩個身分不能混用 | 15份／0.11 MiB | 兩個精確模型、8px序列、PSF、量測器與全部GMF回傳；圖：正式基準原圖／重建、三尺度位移及邊緣比較 | 不自動新增；大型原件留封存 |
| [main/R39_ShapeGeneralization](../../experiments/main__R39_ShapeGeneralization.md) | 保留環形能力並擴大非環形重建；端點與權重平均版需分開；跨R39／R40的a025是核准平衡替代 | 64份／1.03 MiB | COMBO、R39與R40端點、平均比例、形狀生成及固定分組；圖：七類形狀及三尺度量測，保留平均前後差異 | 不自動新增；大型原件留封存 |
| [main/R40_MicroscopyFeatureCoverage](../../experiments/main__R40_MicroscopyFeatureCoverage.md) | 加入格線、紋理、區域與缺陷以補顯微能力；顯微能力顯著增加，但本輪端點／a045不能全面取代COMBO | 32份／0.21 MiB | 顯微場景生成、正向PSF程序、兩個起點與固定答案；圖：各顯微家族的原圖／答案／重建與環形代價 | 不自動新增；大型原件留封存 |
| [main/R41_RingDistillation](../../experiments/main__R41_RingDistillation.md) | 用兩個固定老師同時保存環形與顯微能力；沒有共同通過點；低比例失細節，高比例失環形，不再擴大同一路線 | 24份／0.13 MiB | COMBO與R40老師、R40平均起點、1200組重播來源；圖：老師、學生及不同平均比例的成敗對照 | 不自動新增；大型原件留封存 |
| [main/R42_MicroscopyBoundaryFidelity](../../experiments/main__R42_MicroscopyBoundaryFidelity.md) | 直接提升通用顯微邊界，而非只優化環形；清楚的單張邊界未帶來穩定位移；外部三尺度退步限制使用 | 69份／0.87 MiB | R41起點、通用邊界生成、固定量測與完整外部回傳；圖：清晰度優勢和連續位移失敗同時展示 | 不自動新增；大型原件留封存 |
| [main/R43_CandidateUsabilityAudit](../../experiments/main__R43_CandidateUsabilityAudit.md) | 把既有候選放在同一決策表；只有分析與展示，沒有新訓練；保留當時資訊及之後正式政策的差別 | 5份／0.05 MiB | 各輪正式數值、候選身分與被引用代表圖；圖：同一場景不同候選的比較板 | 不自動新增；大型原件留封存 |
| [main/R44_UniversalBoundaryMotionFidelity](../../experiments/main__R44_UniversalBoundaryMotionFidelity.md) | 直接約束顯微結構隨已知位移正確移動；A到H的診斷、短訓練和蒸餾各有不同問題，必須逐支線保存得失 | 42份／0.30 MiB | 七類連續場景、R42及各老師／起點、每個支線實際設定；圖：大區塊／混合失敗、格線位移及形狀／穩定性取捨 | 不自動新增；大型原件留封存 |
| [main/R45_FamilyBoundaryAdapter](../../experiments/main__R45_FamilyBoundaryAdapter.md) | 用小修正或分族選擇承接R44分散能力；輸出小修正未改善主要形狀；有答案時可選出較好結果，不代表實際選擇器成功 | 19份／0.12 MiB | R44各候選與老師、逐張及逐族結果、固定分組；圖：可達上限與實際方法並列，保留殘差方向不利案例 | 不自動新增；大型原件留封存 |
| [main/R46_CornerAwareFineTune](../../experiments/main__R46_CornerAwareFineTune.md) | 補強角點與直角同時檢查位移；主專案與Lab同名輪次分開；實際採用與否以本輪正式報告為準 | 22份／0.13 MiB | 角點來源、前代模型、各訓練設定與完整結果；圖：直角／圓角、細節與位移共同呈現 | 不自動新增；大型原件留封存 |
| [main/R61_STEP_Generalization_20260623](../../experiments/main__R61_STEP_Generalization_20260623.md) | 追蹤R61各版在Step及論文場景的實際效益；v16是研究候選；後來SEM來源審查限制獨立準確度宣稱 | 9份／0.22 MiB | 完整v16重建包、3400組早期來源、固定模型、PSF及分組；圖：邊界、Step位移、尺寸及不利場景同時保存 | 不自動新增；大型原件留封存 |
| [main/R63_CausalBoundaryMotionAblation](../../experiments/main__R63_CausalBoundaryMotionAblation.md) | 拆開幾何、位移與安全上採樣的貢獻；共同預訓練起點的續訓對照不是全網路從零訓練的因果比較 | 878份／16.37 MiB | 共同起點、兩個種子、固定分組、各消融設定與光學來源；圖：每項移除的同區域比較及全部量測表 | 不自動新增；大型原件留封存 |
| [main/R64_IsocontourDisplacementReanalysis_20260724](../../experiments/main__R64_IsocontourDisplacementReanalysis_20260724.md) | 重新解讀等灰階輪廓位移；屬既有數據重算，保留原量法與修訂量法的差別 | 4份／0.05 MiB | 原始讀值、影格配對、座標與比例設定；圖：同一影像的輪廓與位移讀法對照 | 不自動新增；大型原件留封存 |
| [main/R65_V19_OldMethodFigurePackage_20260724](../../experiments/main__R65_V19_OldMethodFigurePackage_20260724.md) | 保存V19舊量法的論文圖表；作歷史圖表版本，不冒充目前論文主結果 | 28份／0.25 MiB | 產圖程式、完整表格、當時圖說及被引用影像；圖：舊版圖及對應數值 | 不自動新增；大型原件留封存 |
| [main/R66_V20_TraceabilityFigures_20260725](../../experiments/main__R66_V20_TraceabilityFigures_20260725.md) | 補齊論文圖與來源之間的可追查關係；保留影像、物件編號、設定與數據的對應 | 13份／0.13 MiB | 圖表索引、原始來源與產圖程式；圖：來源對照、標號及局部放大圖 | 不自動新增；大型原件留封存 |
| [main/R67_UniversalModelGeneralization](../../experiments/main__R67_UniversalModelGeneralization.md) | 在既有倍率、形狀與位移下選較穩妥模型；既有資料只能選當前領先者，不能宣稱未知樣品普遍有效 | 25份／0.37 MiB | 各固定模型、四組序列、最差情況排序及缺測記錄；圖：跨場景優劣與最差案例 | 不自動新增；大型原件留封存 |
| [main/R68_R61_RealFOVFeatureGeneralization](../../experiments/main__R68_R61_RealFOVFeatureGeneralization.md) | 檢查R61在多倍率完整視野的位移保持；301影像以六個序列為主要單位，固定Raw選區不能事後重選 | 6份／0.02 MiB | 301原圖、固定模型及24區選擇與配對；圖：各倍率選區與位移差分布，含失敗尾端 | 不自動新增；大型原件留封存 |
| [main/R69_ACMContourSEMValidation](../../experiments/main__R69_ACMContourSEMValidation.md) | R61完整外形是否更接近逐顆SEM；正常曝光粗外框改善，最暗兩張及細形狀退步，保留條件性結論 | 10份／0.08 MiB | 12曝光、36顆SEM對應、固定模型及輪廓設定；圖：正常與最暗曝光、完整輪廓及周長失敗 | 不自動新增；大型原件留封存 |
| [main/R70_V42ACMContourSEMValidation](../../experiments/main__R70_V42ACMContourSEMValidation.md) | 以相同SEM與量法檢查V42；模型與SEM訓練來源關係另標示；不能因分數高稱未知驗證 | 7份／0.04 MiB | V42 E120、R69相同原圖／SEM／參數；圖：V42／R61／Raw的同顆輪廓比較 | 不自動新增；大型原件留封存 |
| [main/R71_R61SyntheticMicroscopyDefectGeneralization](../../experiments/main__R71_R61SyntheticMicroscopyDefectGeneralization.md) | 以有乾淨答案的顯微缺陷檢查R61；100張合成測試與40張缺陷核心需分開保留 | 6份／0.06 MiB | R40保留答案、退化輸入、R61與COMBO固定模型；圖：缺角、混合缺陷和紋理的答案對照 | 不自動新增；大型原件留封存 |
| [main/R72_R61SyntheticDefectACMContourValidation](../../experiments/main__R72_R61SyntheticDefectACMContourValidation.md) | 把實拍同類輪廓量法用於已知答案的缺陷；只平移的形狀比較與固定座標比較分開；保留三套參數敏感度 | 8份／0.07 MiB | R71二十張缺陷、固定遮罩與全部參數；圖：輪廓疊圖、最差缺陷與參數敏感度 | 不自動新增；大型原件留封存 |
| [main/R73_R61ExpandedSyntheticACMGeneralization](../../experiments/main__R73_R61ExpandedSyntheticACMGeneralization.md) | 以新生成非圓形檢查完整輪廓；答案輪廓為主要參照；失敗的外圈起始與修復規則都需保留 | 10份／0.09 MiB | 精確幾何生成、固定內圈起始規則、R61及全部遮罩；圖：五類形狀、深凹形失敗與起始修復對照 | 不自動新增；大型原件留封存 |
| [main/R74_R61HardMicroscopyACMGeneralization](../../experiments/main__R74_R61HardMicroscopyACMGeneralization.md) | 避開容易測試的天花板，增加困難成像；難度先由Raw與答案鎖定，再揭露模型；不可事後換成容易資料 | 10份／0.05 MiB | 五類成像×五類形狀的固定100張與精確答案；圖：低對比、光暈、局部缺邊及混合失敗 | 不自動新增；大型原件留封存 |
| [main/R75_R61ArchitectureScratchGeneralization](../../experiments/main__R75_R61ArchitectureScratchGeneralization.md) | R61架構只用獨立純合成資料從頭訓練；首輪半精度沒有有效更新，修正版才是正式100輪；兩段記錄均保留 | 44份／0.71 MiB | 5120組生成配方、獨立初值、實際被選模型與R76驗收；圖：資料多樣性、抗鋸齒答案及實拍不利結果 | 不自動新增；大型原件留封存 |
| [main/R75v2_R61ArchitectureScratchGeneralization](../../experiments/main__R75v2_R61ArchitectureScratchGeneralization.md) | 增加密集、多物件、亮暗及不修改案例；第84與100輪角色不同；外框改善未解決細形狀，不自動替換R61 | 35份／0.76 MiB | 5120組新配方、固定分組及兩個預定比較模型；圖：密集與曝光案例，完整外框與細形狀分開 | 不自動新增；大型原件留封存 |
| [main/R76_R75ACMContourSEMValidation](../../experiments/main__R76_R75ACMContourSEMValidation.md) | R75對36顆SEM完整輪廓的實體驗證；第21與100輪是預定比較，SEM沒有選訓練輪次 | 11份／0.09 MiB | 12原光學圖、18 SEM來源、36顆映射與兩個模型；圖：正常／暗曝光及第21／100輪同顆對照 | 不自動新增；大型原件留封存 |
| [main/R77_R75v2ACMContourSEMValidation](../../experiments/main__R77_R75v2ACMContourSEMValidation.md) | 以同一實體量法檢查R75v2；84與100輪、三套輪廓參數完整保留，不能只留較好一格 | 7份／0.04 MiB | R76相同實體來源與兩個R75v2模型；圖：逐曝光輪廓、敏感度與細節不足 | 不自動新增；大型原件留封存 |
| [main/R78_R75v2_BroadRealMicroscopeGeneralization](../../experiments/main__R78_R75v2_BroadRealMicroscopeGeneralization.md) | 同時檢查SEM外形與多倍率位移；5倍512區塊丟細節；1024改善仍有損失，追加檢查另標 | 12份／0.07 MiB | 301原圖、固定配對與選區、SEM來源及模型；圖：5倍區塊失敗、1024補測和跨倍率比較 | 不自動新增；大型原件留封存 |
| [main/R79_R75v3_DenseMicroscopyScratchGeneralization](../../experiments/main__R79_R75v3_DenseMicroscopyScratchGeneralization.md) | 加強密集排列與多尺度並防止過度重建；第23輪是研究候選；後續修復確定需固定全圖推論 | 31份／0.77 MiB | 5120組新配方、第23／100輪及固定全圖程式；圖：密集細線、多尺度、全圖與分塊差異 | 不自動新增；大型原件留封存 |
| [main/R80_InflectionReferenceCircleSEMValidation](../../experiments/main__R80_InflectionReferenceCircleSEMValidation.md) | 以另一種取邊定義核對SEM與圓量測；屬量法研究，需保留與完整輪廓讀法的差別 | 9份／0.07 MiB | 固定影像／SEM對應、取邊設定及完整讀值；圖：同顆物件不同取邊位置與輪廓 | 不自動新增；大型原件留封存 |
| [main/R80_R79E23vsE100GeneralizationValidation](../../experiments/main__R80_R79E23vsE100GeneralizationValidation.md) | 比較R79訓練早期與最後模型的泛化；R73／R74已影響資料設計，屬擴大開發驗證 | 12份／0.11 MiB | 兩個模型、內部512張、301原圖及SEM固定參照；圖：23／100輪、5倍切片與困難形狀 | 不自動新增；大型原件留封存 |
| [main/R81_MultiArchitectureReferenceCircleBenchmark](../../experiments/main__R81_MultiArchitectureReferenceCircleBenchmark.md) | 擴大外部架構的受控比較；外部指架構來源，部分縮小／同尺寸改版與訓練重疊必須標示 | 134份／2.62 MiB | 各官方來源版本、實際改版、共同訓練包與固定量法；圖：同一來源影像下各架構及失敗／受阻項目 | 不自動新增；大型原件留封存 |
| [main/R82_R39R40CrossSceneGeneralizationBenchmark](../../experiments/main__R82_R39R40CrossSceneGeneralizationBenchmark.md) | 把核准替代與研究模型放到共同場景；真實GMF僅保留有回傳者，不替缺測模型補值 | 12份／0.14 MiB | 固定模型、301原圖、均華序列及SEM／合成參照；圖：跨倍率形狀／位移及最差情況 | 不自動新增；大型原件留封存 |
| [main/R83_R79SevereMicroscopyStrengthening](../../experiments/main__R83_R79SevereMicroscopyStrengthening.md) | 修復R79困難成像並測試保守輸出；新權重未超越R79；保守版只限全圖，分塊失敗仍需保留 | 66份／0.84 MiB | 原R79、兩個短訓練版本、384保留生成案例；圖：困難成像改善及切片失敗並列 | 不自動新增；大型原件留封存 |
| [main/R84_R79TileStableRootRepair](../../experiments/main__R84_R79TileStableRootRepair.md) | 移除R79對看到範圍的依賴；R84到86各修復均有代價，最後保留精確R79並固定全圖 | 31份／0.31 MiB | 原R79與三種修復設定、固定形狀／SEM／位移資料；圖：切片差異與修復後形狀損失同時展示 | 不自動新增；大型原件留封存 |
| [main/R85_R79SharedCanvasOpticalRepair](../../experiments/main__R85_R79SharedCanvasOpticalRepair.md) | 以共同光學畫布保留R79能力；切片一致但邊界超過限制，不開啟新的確認資料 | 10份／0.22 MiB | 原R79、生成配方、兩個篩選模型及未開封狀態；圖：切片成功與邊界退步對照 | 不自動新增；大型原件留封存 |
| [main/R86_R79BlockGroupNormRepair](../../experiments/main__R86_R79BlockGroupNormRepair.md) | 固定小區塊統計以消除切片差異；免訓練測試未過形狀門檻，沒有正式訓練模型 | 6份／0.06 MiB | 精確R79及區塊修正程式、原參照讀值；圖：原版／修正版與已知答案比較 | 不自動新增；大型原件留封存 |
| [main/R87_TileNativeScratchGeneralization](../../experiments/main__R87_TileNativeScratchGeneralization.md) | 純局部模型從零學習重建及切片一致性；100輪完成但新形狀／困難資料退步並出現假孔洞，不採用 | 23份／0.12 MiB | 1280場景原生成器、實際配方、固定模型、R73／R74及H完整封存；圖：假孔洞、紋理損失與切片一致性一起展示 | 不自動新增；大型原件留封存 |
| [main/R88_MeasurementFaithfulScratch](../../experiments/main__R88_MeasurementFaithfulScratch.md) | 修復R87紋理與邊界並加入實際量測約束；完成狀態以87輪停止收尾紀錄為準，不能沿用首頁的啟動狀態 | 36份／0.26 MiB | 獨立生成配方、實際87輪歷程、被保留模型與封存確認狀態；圖：紋理／暗邊／位移及未過項目 | 不自動新增；大型原件留封存 |
| [main/R89_MeasurementNativeScratch](../../experiments/main__R89_MeasurementNativeScratch.md) | 移除輸出信心閘並直接學習有界重建；獨立從零訓練；來源只有匿名成像統計，並非使用真實答案 | 30份／0.30 MiB | 本輪原生成器、匿名統計、固定初值與完整結果；圖：門控前後的紋理、輪廓與不修改案例 | 不自動新增；大型原件留封存 |
| [main/R90_ExposureCoherentScratch](../../experiments/main__R90_ExposureCoherentScratch.md) | 讓同一物體在四種曝光保持相同輪廓；實際55輪停止，不能寫成預定100輪全部完成 | 39份／0.40 MiB | 四曝光生成與獨立雜訊設定、55輪歷程與模型；圖：曝光漂移、低頻暗邊與保留細節 | 不自動新增；大型原件留封存 |
| [main/R91_DetailDecoupledScratch](../../experiments/main__R91_DetailDecoupledScratch.md) | 分開紋理恢復與輪廓／曝光約束；分開報告退化影像恢復與清楚輸入被改動的代價 | 32份／0.44 MiB | 1250場景／5000觀測的本輪配方與四曝光驗證；圖：暗邊、細節與清楚影像改動 | 不自動新增；大型原件留封存 |
| [main/R92_PhysicalTransitionBalancedScratch](../../experiments/main__R92_PhysicalTransitionBalancedScratch.md) | 補足物理邊緣過渡與平衡曝光取樣；生成修復、真實光學統計及精度差異需隨結果保留 | 38份／0.58 MiB | 本輪生成器與實際接受參數，不用後代資料替換；圖：不同過渡位置、曝光最差端點及精度比較 | 不自動新增；大型原件留封存 |
| [main/R93_RecoverableDetailSeparatedScratch](../../experiments/main__R93_RecoverableDetailSeparatedScratch.md) | 拆開可恢復細節及清楚輸入保護；實際60輪停止；此輪資料被R94到98共用，D路徑有下游相依 | 25份／0.38 MiB | 精確5000觀測生成／修復記錄、來源清單與各下游約定；圖：細節退步、清楚輸入改動及分支抵消 | 不自動新增；大型原件留封存 |
| [main/R94_EvidenceConditionalScratch](../../experiments/main__R94_EvidenceConditionalScratch.md) | 按成像順序分工並直接教何時需要修正；完整8輪；第9輪未提交即停止，所有原失敗與空啟動保留 | 30份／0.26 MiB | R93鎖定資料、初值與第8輪錯誤／梯度診斷；圖：接近原圖的輸出與未生效修正 | 不自動新增；大型原件留封存 |
| [main/R95_CounterfactualGateRepairScratch](../../experiments/main__R95_CounterfactualGateRepairScratch.md) | 修復R94修正閘與訓練動力問題；48輪完成；首度恢復重建更新狀態，49列原表及第9輪取代脈絡完整保留 | 54份／0.64 MiB | R93資料、固定反事實設定及本輪完整48輪歷程；圖：各修正分支、清楚控制與後期紋理變化 | 不自動新增；大型原件留封存 |
| [main/R96_Design_Archive](../../experiments/main__R96_Design_Archive.md) | 保存R96正式設計前的舊方案；內含仍標示R95的設定與效能讀值，屬前置設計歷史，不能當成R96正式跑過的結果 | 14份／0.08 MiB | 原R95標示設定、量測與後續R96正式設計分別保留；圖：前置方案與正式版本差異，保留原身分而不改名冒充 | 不自動新增；大型原件留封存 |
| [main/R96_LocalizedEvidenceProtectedScratch](../../experiments/main__R96_LocalizedEvidenceProtectedScratch.md) | 防止聯合訓練抵消各局部分支的目標；44輪獨立訓練，與舊設計目錄分開 | 53份／0.47 MiB | R93固定資料、44輪設定、各分支梯度與結果；圖：後期細節、局部控制及不修改案例 | 不自動新增；大型原件留封存 |
| [main/R97_DirectCausalPhaseScratch](../../experiments/main__R97_DirectCausalPhaseScratch.md) | 直接預測每分支實際施加的修正；48輪完成；固定48輪後測、兩種事故及細節／量測限制分別保存 | 35份／0.31 MiB | R93資料、線上程序週期樣本、48輪設定；圖：週期錯峰、細節與修正抵消 | 不自動新增；大型原件留封存 |
| [main/R98_AggressiveTextureScratch](../../experiments/main__R98_AggressiveTextureScratch.md) | 增加可見多尺度紋理的恢復強度；48輪完成並補正舊結果報告；SEM不利結果、驗證裁切不同及缺少整套後測明列 | 27份／0.23 MiB | 共享R93／R97來源、六頻帶及固定48輪設定；圖：紋理收益、邊界代價與不同倍率 | 不自動新增；大型原件留封存 |
| [main/R99_GeometryTextureCoherentScratch](../../experiments/main__R99_GeometryTextureCoherentScratch.md) | 把亮暗、幾何、邊緣與紋理動作依序分開；實際41輪停止；保留與計畫48輪的差別 | 19份／0.22 MiB | R92固定來源、線上增補、41輪實際記錄；圖：幾何與紋理是否同時改善，以及失敗尾端 | 不自動新增；大型原件留封存 |
| [lab/BaseUNet_Baseline_20260718](../../experiments/lab__BaseUNet_Baseline_20260718.md) | 以基礎U-Net作參數與訓練資料受控比較；不同資料量／固定光學／切片與輪次版本分開；輸出報告沿用V42欄名需核對實際方法身分 | 31份／0.15 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/Modern_Restoration_Benchmarks_20260719](../../experiments/lab__Modern_Restoration_Benchmarks_20260719.md) | 比較柱、孔、線三形貌的EDSR／NAFNet等方法；30輪NAFNet與15輪EDSR各取最低驗證模型；同系統轉移且含固定光學轉換，不宣稱所有指標第一 | 359份／8.27 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/MOSR_BestCheckpoint_Diagnostic_20260724](../../experiments/lab__MOSR_BestCheckpoint_Diagnostic_20260724.md) | 檢查最佳保存模型與最後模型對位移結果的影響；保留共同有效母體及缺測，不以較好的一個模型覆蓋另一版 | 5份／0.13 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/MOSR_CheckpointConfig_Diagnostic_20260724](../../experiments/lab__MOSR_CheckpointConfig_Diagnostic_20260724.md) | 拆解EDSR與MOSR位移差異的來源；第10輪、120輪與定位保護各有取捨；取樣相位解釋限於已測條件 | 7份／0.14 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R39_ShapeGeneralization](../../experiments/lab__R39_ShapeGeneralization.md) | Lab環境中的多形狀轉移；與主專案R39分開，Lab起點及成像條件不能互換 | 4份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R40_MicroscopyFeatureCoverage](../../experiments/lab__R40_MicroscopyFeatureCoverage.md) | Lab環境中的顯微特徵對照；作後續角點實驗的固定Lab控制，不冒充主專案正式替代 | 4份／0.04 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R46_CornerAwareFineTune](../../experiments/lab__R46_CornerAwareFineTune.md) | 以角點資料保守修正Lab模型；25輪有效但未修好實體圓角，未採用 | 13份／0.07 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R47_RealisticBoundaryGeneralization](../../experiments/lab__R47_RealisticBoundaryGeneralization.md) | 增加較真實的邊界與背景；200輪仍未修好實體角點，較多訓練不等於有效 | 15份／0.20 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R48_RealCornerTransfer](../../experiments/lab__R48_RealCornerTransfer.md) | 用實體失敗型態與幾何標記改善角點；內部改善但實體更差；200輪完整負結果保留 | 11份／0.10 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R49_CADAnchorRealGeometry](../../experiments/lab__R49_CADAnchorRealGeometry.md) | 加入可靠區域內的實體CAD答案；100輪仍使角點退步；可靠遮罩很小，不能當全圖答案 | 12份／0.07 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R50_PSFControlDiagnosis](../../experiments/lab__R50_PSFControlDiagnosis.md) | 診斷Lab光學模糊是否過強；只做診斷；完整BADS比實拍更軟，混合光學需另試 | 5份／0.03 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R51_BlurSourceProbe](../../experiments/lab__R51_BlurSourceProbe.md) | 短測高斯、弱BADS與混合光學；混合改善典型角點但大偏移比例上升，未採用 | 10份／0.06 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R52_CornerStabilityGuard](../../experiments/lab__R52_CornerStabilityGuard.md) | 續接混合光學並加入角點穩定限制；100輪後實體大偏移仍多，負結果與完整H歷史保留 | 18份／0.15 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R53_RealisticDatasetCalibration](../../experiments/lab__R53_RealisticDatasetCalibration.md) | 重新平衡環形、形狀、顯微、背景與CAD資料；6000組／100輪從零完成但實體角點失敗；已清理批次不重算回收 | 36份／0.12 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R54_GeometryRootCauseProbe](../../experiments/lab__R54_GeometryRootCauseProbe.md) | 拆解重建造成角點損害及局部CAD可學性；可靠區域內可學，但轉到實體全圖失敗；不沿此模型續訓 | 16份／0.19 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R55_SourceStyleRealisticTraining](../../experiments/lab__R55_SourceStyleRealisticTraining.md) | 保留來源亮暗風格修復假高對比答案；best通過Lab控制角點門檻，latest退步；外部回傳另記 | 12份／0.05 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R56_LabelCoreRepairTraining](../../experiments/lab__R56_LabelCoreRepairTraining.md) | 只修復弱答案核心區域；50輪內部改善但實體尾端更差，未採用；H備份與既有清理紀錄保留 | 12份／0.05 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R57_GeometryConstrainedMOSR](../../experiments/lab__R57_GeometryConstrainedMOSR.md) | 加入實體SEM半徑約束尺寸；同樣本幾何答案是訓練來源，不能當獨立SEM證據 | 11份／0.07 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R58_MeasurementClosedLoopMOSR](../../experiments/lab__R58_MeasurementClosedLoopMOSR.md) | 使用部分SEM修正答案做閉環試驗；答案故意只修一部分且缺實拍裁切，不能期待完全到SEM外框 | 8份／0.07 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R59_CDClosedLoopBoundaryLayer](../../experiments/lab__R59_CDClosedLoopBoundaryLayer.md) | 在同一影像上估計尺寸再移動邊界；屬同樣本後修正，數字變好不代表網路學會或獨立準確 | 5份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R60_SEMTruthBoundaryTraining](../../experiments/lab__R60_SEMTruthBoundaryTraining.md) | 修復實拍裁切答案、亮暗方向與真值權重；方向與取樣修正後短測改善，完整歷史及SEM訓練依賴均保留 | 25份／0.14 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R61_BoundaryGeneralizationUniversal](../../experiments/lab__R61_BoundaryGeneralizationUniversal.md) | 加入通用邊界、位移及Step保護形成v16；保留歷版；3400早期來源及舊輪廓不能單靠新推算取代 | 183份／5.35 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/R62_TargetSampleBoost](../../experiments/lab__R62_TargetSampleBoost.md) | 實體目標增補與保守原圖參考輸出；多版模型與固定後處理分開；相位位移恢復不等於所有局部圓心更準 | 157份／0.72 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/Subpixel_Translation_Equivariance_20260720](../../experiments/lab__Subpixel_Translation_Equivariance_20260720.md) | 對真實結構施加已知數學位移作壓力測試；插值位移不同於平台重新拍攝；MOSR未全面勝過EDSR，全部100配對與不利結果保留 | 18份／0.26 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/V41_Standalone](../../experiments/lab__V41_Standalone.md) | 把目標樣品探索鏈整理成兩階段訓練；起點R61v16及11254組目標樣品／老師資料都是必要來源，不可描述為完全獨立從零 | 8份／0.05 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [lab/V42_SoftLabelSNR](../../experiments/lab__V42_SoftLabelSNR.md) | 柔化邊界答案並加入影像品質閘；兩輪180組煙霧結果與後來E120論文模型分開，實際E120來源須追查完整run與模型包 | 4份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/organized_20260306](../../experiments/legacy__organized_20260306.md) | 最早整理的訓練候選、採用與拒絕歷史；保留選擇脈絡；沒有完整來源證據的舊候選只標歷史紀錄 | 11份／0.07 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/organized_20260307](../../experiments/legacy__organized_20260307.md) | 內部種子搜尋與自動參數試驗；當時精選seed不是目前基準，完整拒絕歷史另在H | 25份／0.04 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/organized_20260309](../../experiments/legacy__organized_20260309.md) | 精選seed的外部GMF與視覺比較；step8_curve_stdguard_v2屬歷史驗證對象，原始回傳不可用新讀法覆蓋 | 25份／0.07 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/organized_20260310](../../experiments/legacy__organized_20260310.md) | 多尺度、SeqVal、crossscale及uint16微步測試；中大尺度與微步結果分開，精度修復前後均保留 | 29份／0.12 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/organized_20260311](../../experiments/legacy__organized_20260311.md) | Round12長跑、Round13模型審查與Round14走廊檢查；把12到14輪各份selected報告保留，不用一個資料夾名取代各輪身分 | 34份／0.27 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/organized_20260312](../../experiments/legacy__organized_20260312.md) | Round15中心鎖定長訓練與外部驗證；centerlock_pure是歷史研究候選，代表模型與被取代原因保留 | 11份／0.08 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round16](../../experiments/legacy__round16.md) | 更換邊界估計讀法；曾為內部較好版本，後被取代 | 14份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round17](../../experiments/legacy__round17.md) | 修復步距與位移估計；內部改善不能代替後來外部比較 | 14份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round18](../../experiments/legacy__round18.md) | 中心位置約束的歷史基準；當時採用，之後與R22外部比較 | 14份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round19](../../experiments/legacy__round19.md) | 絕對位置錨定假說；已完成未採用，保留反例 | 14份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/branch_e](../../experiments/legacy__branch_e.md) | 估計器Branch E探索；後續有跟進但不是最後基準 | 14份／0.03 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/diagnostics](../../experiments/legacy__diagnostics.md) | 選擇估計器研究分支的診斷；歷史決策證據，不是新模型 | 7份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round20](../../experiments/legacy__round20.md) | 固定基準的流程前測；假說未支持，不把流程完成當效益 | 11份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/branch_e_followup](../../experiments/legacy__branch_e_followup.md) | Branch E校正後再評估；未通過升級條件，保留反例 | 15份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/estimator_formula_probe](../../experiments/legacy__estimator_formula_probe.md) | 早期估計公式探索；方法歷史不等於正式量測資格 | 9份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/pairwise_delta_probe](../../experiments/legacy__pairwise_delta_probe.md) | 兩影格位移混合方式的前測；支撐R22的設計來源，與R22正式驗證分開 | 9份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round21](../../experiments/legacy__round21.md) | 混合估計器的正式跟進；未解開主線限制 | 15份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round22](../../experiments/legacy__round22.md) | 成對混合估計器；歷史採用版本，後由外部系列比較 | 15份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round23](../../experiments/legacy__round23.md) | R22之後的歷史候選；依selected/reports保存當時結論，不能推定為目前基準 | 12份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round24](../../experiments/legacy__round24.md) | 主線與對照的歷史候選；保留實際配方與當時驗收，不補造缺失結果 | 13份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round25](../../experiments/legacy__round25.md) | 外部多尺度比較鏈的共同參照；後續各輪必須保留同一來源與讀法 | 12份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round26](../../experiments/legacy__round26.md) | 平滑強度與正式交付版本；歷史R26與新PSF沙盒的政策身分分開 | 12份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round27](../../experiments/legacy__round27.md) | 在R26基礎上的外部比較；以當時正式結果保留負面與正面讀值 | 12份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round28](../../experiments/legacy__round28.md) | 延續多尺度守門的歷史候選；保留完整外部回傳與採用判斷 | 14份／0.01 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round29](../../experiments/legacy__round29.md) | R30之前的歷史候選；不因資料夾位於selected就推定目前正式 | 14份／0.02 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round30](../../experiments/legacy__round30.md) | 方向約束的歷史前任正式模型；前任基準不是目前COMBO；保留確切模型及外部證據 | 22份／0.10 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round31](../../experiments/legacy__round31.md) | 訓練權重與等化訊號再調整；外部退步，不能只看內部通過 | 26份／0.12 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/round32](../../experiments/legacy__round32.md) | 舊批次R32輸出；正式可編輯紀錄已移到主專案R32Sandbox | 5份／0.00 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |
| [legacy/tta_experiment](../../experiments/legacy__tta_experiment.md) | 推論時多種變換與平均的影響；保存固定TTA規則與量測代價，不用單張清晰度決定採用 | 8份／0.03 MiB | 保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。；圖：共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。 | 不自動新增；大型原件留封存 |

## 四份凍結大檔草稿

以下是待決定的撤回候選，沒有取得遠端刪除指示，本次一份也未刪。先把必要的小型內容及既有來源記清，再處理整包去向；不能將混合包中的幾項必要內容當成整包都要保留。

| 草稿 | 實際附件容量 | 精選後處理方向 |
|---|---|---|
| research-model-history-additions-20261021 | 142.689 GB | 只引用明確選用的關鍵模型；整批中途模型留封存；整份草稿列為撤回候選，尚未刪除 |
| research-numeric-data-additions-20261021 | 165.455 GB | 完整量測表及必要固定常數保留，逐張影像陣列留封存；整份草稿列為撤回候選，尚未刪除 |
| research-image-data-additions-20261021 | 72.396 GB | 少量原報告代表/失敗圖及共用原拍保留，完整重建圖庫留封存；整份草稿列為撤回候選，尚未刪除 |
| research-package-additions-20261021 | 4.085 GB | 保留來源版本與必要小型交付，完整舊ZIP留封存；整份草稿列為撤回候選，尚未刪除 |

[逐份草稿及狀態](FROZEN_DRAFT_DISPOSITION_CANDIDATES.json)

930張共用原拍與30份原始紀錄、既有已發布的必要交付都不在這份草稿候選中。22份未尋回的早期來源與9項早期R13公式仍為已知缺件；已存在的完整來源清冊並不等於GitHub必須保存整份磁碟鏡像。
