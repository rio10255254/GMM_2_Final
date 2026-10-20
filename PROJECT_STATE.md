# PROJECT STATE / 專案狀態

Last updated: 2026-10-21（GitHub優先：R94／R95／R97／R98完整紀錄與另址重做核對）

專案控制與整體巡檢請使用 `python Tools/project_control_center.py`。
機器真相：`ESTIMATOR_POLICY.json`。

<!-- QUICK_HANDOFF_START -->
## Quick Handoff
### 正式身分
- 正式基準仍為 **COMBO / r38v2_8px_gate_p95**；容量整理及可攜包不改變任何研究判決。
- Approved Alternates：R33、R38v2、R39R40_avg_a025；正式基準分支`sandbox/r38v2`。
- 論文目前研究採用R152／RAW，R153保存十方法完整比較。原論文、採用模型與量測資料保護。
### 已完成研究
- 十方法各930張、8370讀值、30有效趟及150次效率已核對；兩官方後端受阻如實保留。
- [完整論文交接](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)。
- R152資料重建與模型獨立包已完成；尺寸偏差、速度代價與SEM參照限制保留。
### 共用原始資料與GitHub整理 20261016
- 20261021全專案續查進行中：補回10條本機獨有版本歷史，18份原程式／設計從GitHub取回相同；其餘本機及H歷史逐項核對。[範圍與完成條件](docs/reproducibility/project_completion/README.md)。尚未宣稱全專案完成。
- 全新GitHub程式副本當次22218檔逐份相同；另補兩份暫存文件歷史，33個共用位置已列對照。[早期多尺度判讀](docs/reproducibility/legacy_multiscale/README.md)重算207分數／五次選擇，9個早期公式缺件保留。
- 20261021 R94／R95／R97／R98完整紀錄1,092位置、107模型檔、663影像從GitHub取回；32組原模型輸出相同，原數字與四輪共用輸入核對通過。[四輪方法與重做入口](docs/reproducibility/four_rounds/README.md)。本輪不清D、不使用訓練顯卡。
- 20261020續整以GitHub為主：補R93全部既存模型／影像歷程及36KB原數字重算包，修正舊模板的輪次／種子；[五輪共用來源新入口](docs/reproducibility/r93_shared/README.md)。沒有重跑歷史訓練或改科學判決。
- 30趟實拍原始ZIP已從Google Drive取回；930相機BMP與30原始位置CSV全部符合歷史原檔核對碼，PI／時間／影格／曝光逐筆相同。
- D槽保護工作副本：[共用原始資料](Shared_Sources/PI_Repeatability_20260903/README.md)；H槽保留原始ZIP及核對紀錄。
- 先前R139恢復副本與原始ZIP全部相同；正式來源使用直接從原始ZIP取出的檔案。
- 177個實驗或歷史批次的保存判讀已建立；[逐輪入口](docs/reproducibility/EXPERIMENTS.md)。檔案整理與完整重跑訓練分別標示。
- 本次R61在另一位置完整重建114283檔全部相同；R152完整重建9216 TIFF全部相同，均禁止讀取舊研究資料。
- 五組來源／模型／結果版本已發布GitHub；原件960檔、R61完整114283資料檔、R152全部9216 TIFF及十方法完整數值取回重做均通過。
- 20261020 R87 維持原模式、不改人工核准，三份5,152檔重核後單次原生刪除成功；D實測增加11.3398 GiB，舊位置讀取H工作副本通過。[最新R87封存入口](Experiments/R87_TileNativeScratchGeneralization/ARCHIVE_POINTER_R87_20260926.md)。20x/5x仍保留D原件。
### 容量與保護
- 20261016完整盤點3592327檔、零讀取錯誤；不追蹤31個外部資料入口，不把H資料重算成D負擔。
- 20261020 H槽R152 v8獨立訓練持續保護；原C槽獨立包與論文來源保留，沒有啟動另一個GPU訓練。
- 既有R53／R56清理與H完整備份已結案，不能重算本次回收量。
- 20x／5x及其他舊資料仍須另行核對備份、相依與保留清單；R87本次完成範圍只有兩個舊合成陣列副本。
### 閱讀順序
- [機器真相](ESTIMATOR_POLICY.json)、[完整現況](#full-current-state--完整現況)、[實驗索引](Experiments/INDEX.md)。
- [封存與恢復索引](docs/operations/PROJECT_ARCHIVE_INDEX.md)、[來源政策](docs/operations/SOURCE_OF_TRUTH_POLICY.md)。
- [整理前的完整交接原文](docs/history/PROJECT_STATE_HANDOFF_BEFORE_RECOVERY_20261016.md)。
- [早期執行狀態快照](docs/archive/legacy_runtime_status/)只供歷史查找，原實驗報告優先。
<!-- QUICK_HANDOFF_END -->

---

## Full Current State / 完整現況

### 全專案GitHub保存續查（2026-10-21，進行中）

本輪以實際本機內容核對，不以177個閱讀範圍或既有附件清單推定完整。範圍包括共用訓練、光學校正、論文草稿／交接、早期分析、獨立包及先前搬到H槽的歷史。本機79個有名稱分支的歷史已可從GitHub取得：其中10條原本獨有歷史補上保存入口，18份獨有程式／設計均實際從GitHub取回相同。

第一批28次舊訓練的851個補件位置已從GitHub取回相同：367份模型狀態、460張影像及24份實際分組資料；六個固定端點原生CPU輸出相同。另有約405MB小包實際下載重做通過。第二批182471個研究紀錄／標記／文件位置已實際從GitHub取回相同，原Word及資料格式核對通過。其他模型、輸入與結果仍在全內容核對，不宣稱全專案完成。發現R33舊報告將20260405_073230列為啟動失敗，但原表及原模型保留100輪，已另記來源矛盾，沒有自動指派為接受候選。原文、科學判決、論文及活動訓練保留；本輪不清D、不使用GPU。[全專案核對](docs/reproducibility/project_completion/README.md)／[R33來源審查](Experiments/R33RobustLoss/reports/R33_HISTORY_PRESERVATION_AUDIT_20261021.md)。

後續已實際下載全新GitHub程式副本，當次22218檔／6679152130 bytes逐份相同，禁止讀取舊研究來源。另補回20260324的兩份暫存文件版本，原暫存不變；33個共用位置的11個專案內引用與22個H目標逐一記錄。Round12–15入口分清方法組初排、固定模型再審與同分規則；207個分數及五次原選擇從GitHub取回重做，9個較早R13總分的舊公式未找回而保留原值。R88首頁／索引按未改動的87輪停止原報告修正，最後保存85輪，舊文字保留。

光學區另分清早期L0、後來三次拍攝L1、正式MATLAB擬合及僅作流程預覽的Python教學。45份既存擬合的L1摘要／陣列2016數字欄位與100位置48摘要欄位本機重算通過；原1×100儲存按原位置資訊另排10×10，原值不變。約39.5MB光學小包已實際從GitHub重新下載，在禁止讀取舊研究來源的環境中重算通過，並已發布。[光學保存審查](PSF_Fitting/docs/PSF_GITHUB_PRESERVATION_AUDIT_20261021.md)。全專案大型資料仍在執行中。

### GitHub優先：R94／R95／R97／R98完整歷程（2026-10-21）

四輪逐一理解原方法、模型、原表與失敗後，補齊1,092個現存原位置、107個模型檔及663張影像；相同內容只存一次。R94完整8輪、第9輪未提交；R95首度由第8輪接續曾重建更新狀態、原表第9輪重複列保留；R97開跑前顯示驅動事故與正式第1輪檔案存取失敗分開；R98完整48輪但舊報告仍停在預檢文字，本次補正且保存舊文。

固定四視野另追到完整相機來源；5倍、20倍、50倍與九宮格四份原件另存小型GitHub版本，包含先前漏存的2026-06-18相機原圖。四輪16份預覽均能由取回的相機原件裁切成完全相同的檔案，沒有用模型輸出代替原拍攝。

原模型定義／最後訓練程式／原設計12項均符合當時紀錄。GitHub完整附件實際下載另址還原，全部內容核對；663張影像可解碼，107個模型檔內數值有限。四輪各兩個正式端點×四個固定實拍輸入共32組，在新CPU環境、舊D／H研究位置不可讀的條件下，以原推論路徑重做；完整小數陣列與BMP均與原程式CPU參照相同。小型數字包119個原摘要量、共用15,004檔、四輪36個原生準備樣本、8批程序週期樣本與3個R98補抽排程核對通過。

R97／R98內部驗證裁切種子不同，不能單靠最後分數排名；R98缺少的整套實拍／位移後測及較早測試程式版本缺件明列，未冒稱完整歷史GPU訓練重跑。COMBO、論文、正在H槽執行的R152獨立訓練與D原件保留。[完整入口](docs/reproducibility/four_rounds/README.md)／[驗證收據](docs/reproducibility/four_rounds/VERIFICATION_20261021.json)。

### GitHub優先續整：R93完整歷程及五輪共用資料（2026-10-20）

使用者再次指定首要目標為從GitHub理解及重做各輪實驗。本次新的D清理全部暫緩：20x／5x只重核，R93原資料也沒有刪除。R87前一批已完成的清理不重算成本次成果。

R93真正固定來源為種子930041、1250場景／5000觀測，原設計64輪、使用者在完整60輪後停止；32至60輪的15個已觀察候選重算選出48輪，與原分析一致。舊README／MANIFEST沿用前輪標題及種子的問題已更正，舊文原封保留歷史。GitHub附件原來缺少該48輪模型和245張results圖，本次完整紀錄補齊所有34個模型檔及250張比較／測試圖、完整原表與必要小輸入；另有36KB包可不下載大資料便重算當時選擇與18個數字。

R93 formal的15004檔已從GitHub取回逐份相同；在新CPU環境及原D／H不可讀條件下，核對R93／R94／R95／R97／R98原生資料準備。R93固定48與60輪模型、四個實拍預覽輸入和原推論程式從GitHub取回後另址重做；與原程式CPU參照比較，不把原GPU監看圖冒稱已逐位元重現。詳細範圍及收據見[新入口](docs/reproducibility/r93_shared/README.md)和[R93正式審查](Experiments/R93_RecoverableDetailSeparatedScratch/reports/R93_AUDIT.md)。

### R87 原模式單次刪除與保留核對（2026-10-20）

依使用者要求不切換人工核准，先完整重核兩個 R87 陣列目錄的 D 原件、H 不可變封存與 H 獨立工作副本，5,152 檔全部相同。原生刪除只嘗試一次並成功，移除 D 邏輯檔案 12,155,752,448 bytes；同期間 D 可用空間實測增加 12,176,003,072 bytes（11.3398 GiB），不可混為相同數字。

原 D 資料入口現讀取獨立 H 工作副本，正式／smoke 原生讀取程式首、中、尾全部相同；原保留 438 檔內容核對通過後只更新封存說明。R87 模型／科學報告、原始照片、R152/R153 論文來源及正在 H 槽執行的 R152 v8 均保留。20x/5x 與其他批次未清理。先前 blocked by policy 為歷史拒絕；本次成功不作內部拒絕成因已查明的主張。[精確範圍與完成收據](Experiments/R87_TileNativeScratchGeneralization/ARCHIVE_POINTER_R87_20260926.md)。

### GitHub研究保存與原始來源追回（2026-10-16）

[原始相機資料](https://github.com/rio10255254/GMM_2_Final/releases/tag/shared-pi-20260903-v1)已發布：原ZIP直接取自Google Drive；930相機BMP與30原始CSV與歷史凍結清單完全相同。已從GitHub下載原ZIP、清單與恢復程式另址重做，阻擋原D/H讀取仍通過。D保護工作來源為Shared_Sources/PI_Repeatability_20260903；不是由模型重建圖取代原件。先前R139恢復的副本亦與實際原ZIP一致，取得方式分別記錄。

本次逐輪判讀177個範圍，補建缺失的導引而不補造原登錄。R61完整114283檔與R152完整9216 TIFF另址生成完全一致；十方法完整270指標、18000位移、162完整趟次配對區間及平均／中位數36區間另址重算通過。沒有重跑全部歷史訓練、輪廓重新擬合或改動正式基準。

必要原始照片、SEM、固定來源、完整結果與模型附件已發布五個GitHub版本；208123個附件原位置與一般倉庫合併核對225848個原位置，全部內容一致且無衝突。GitHub取回R61／R152完整資料重建與十方法完整重算通過。原分支與既有工作狀態保留，保存快照使用codex/research-recovery-20261016。R87與20x／5x兩批54個D目錄三方核對通過，但原生R87刪除指令在程序啟動前被自動審查拒絕；本次D原件未清理、實際回收0。C槽正在訓練的獨立包持續保護。[總入口](docs/reproducibility/README.md)。


### Committee-response mean aggregation and external benchmark (2026-10-05)

2026-10-07 14:34：十種可執行方法完整比較已核對，每方法930張／8370讀值／30有效趟，零失敗；150次效率、162組配對區間、完整模型架構／訓練設定／合成及SEM數據／灰階圖／原生影像／修改指南齊全。SwinIR8輪／選第8輪，1800筆位移與18組區間獨立重算通過。九方法舊包與135次效率保持原樣；原論文、模型、既有量測與尺度／方向／PI不變。U-Net／MambaIRv2官方後端受阻不列為已驗證；可執行範圍已完成，監看結束，正式基準未改。[最新完整論文交接](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)／[全部圖表與數據](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF.zip)。

2026-10-07 08:06：SwinIR已完成8輪／4096次更新，合成驗證選第8輪EMA及128場景完整測試已核對；同條件15次效率完成。七個可訓練外部模型全部完成，現只新增SwinIR原生整張930張重建及8370固定讀值（巡檢已成功230張、失敗0），再彙整十方法結果。九方法原完整論文包／135次效率保留；不改原論文、MOSR、RAW/MOSR保存量測、尺度／PI／方向。完整比較尚未完成，下一次預估檢查 2026-10-07T14:15:00+08:00（含20分鐘緩衝、非保證）。[訓練完成核對](Experiments/R153_MeanExternalBenchmark/runs/launcher_logs/SwinIR_training_complete_verified_20261007.json)。

2026-10-06 16:45：九方法完整論文包已核對交付並保留原樣。使用者直接授權續訓SwinIR，已從保存step256恢復原佇列並確認進至step272，總上限仍8輪；相同來源與設定已核對。完成後只新增SwinIR效率15次及930張／8370讀值，再重用九方法資料彙整十方法。原論文／MOSR／比例／方向／PI不變；監看恢復，下一次估計檢查 2026-10-07T08:00:00+08:00（非保證）。[九方法論文交接](Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_THESIS_HANDOFF/REPORT.md)／[續訓紀錄](Experiments/R153_MeanExternalBenchmark/config/USER_RESUME_20261006.json)。

2026-10-06 14:58：使用者指定的九方法完整論文交付已完成並核對。六外部模型＋RAW／Wiener／MOSR，每方法930張／8370讀值／30有效趟，零失敗；144組配對區間、135次效率、全部模型設定／合成測試／SEM／灰階圖／同區域影像與修改指南齊全。獨立重算主要位移與16組區間通過，原檔未改。SwinIR保存step256、未完成且不列入比較；保持暫停不自動續訓，監看已停止。[完整論文交接](Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_THESIS_HANDOFF/REPORT.md)／[附件包](Experiments/R153_MeanExternalBenchmark/reports/COMPLETED_MODELS_THESIS_HANDOFF.zip)。

2026-10-06：使用者要求暫停SwinIR並先交付已完成模型的完整論文紀錄。SwinIR保存step256且不自動續訓；六外部模型加RAW/Wiener/MOSR共九方法，只補Restormer／USRNet的930張驗證，原七結果重用。九方法135次效率已完成；USRNet曾驅動退出，原生檢查及相同設定重測通過，錯誤保留。完整九方法實拍／圖表／論文包仍執行中，預估15:00檢查。

2026-10-06 03:27：七方法完整實拍與效率比較完成並核對，全部30趟有效、無量測失敗；4650份新重建、41850筆新讀值，RAW/MOSR保存量測重用，108組配對區間與105次效率實測。MOSR位移波動與相鄰PI差最低，輪廓與EDSR差異未確定；形狀NAF/EDSR較好、SEM尺寸RAW較好，均完整保留。Restormer已自動續訓，完整benchmark仍待後續模型完成。[完整階段交接](Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_STAGE_COMPLETE/REPORT.md)／[附件包](Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_STAGE_COMPLETE.zip)。

2026-10-05晚間：使用者授權先暫停訓練釋放GPU，Restormer保存step896。七方法同GPU／FP32／batch1共105次效率實測完成；Wiener930張／8370量測已完成且無失敗，EDSR等四個外部模型實拍驗證依序執行。完成本階段核對後自動續訓，完整benchmark仍未完成。[效率報告](Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_EFFICIENCY.md)／[階段論文資料](Experiments/R153_MeanExternalBenchmark/reports/AVAILABLE_MODELS_STAGE_PROGRESS/REPORT.md)。

User-confirmed ordinary external training supersedes the initial common-five-loss training request. Same fixed TIFF bank and synthetic validation, from scratch, adaptive epoch stopping; all five task terms remain synthetic evaluation diagnostics. Sequential queue is EDSR-x1 → NAFNet → RDN-x1 → RCAN-x1 → Restormer → USRNet-x1 → SwinIR. Official U-Net/MambaIRv2 backend failures remain recorded. Verified live manager/worker and duplicate prevention; heartbeat automation `mosr` checks near estimated active-model completion plus buffer in the original chat and continues the remaining authorized benchmark work. Mean aggregation is primary: RAW/MOSR SD8.780826/4.272773nm, adjacent PI MAE6.969175/3.598341nm; long-distance mean-MAE interval crosses zero. No source circle refits, scale/PI/direction changes, or thesis/model edits. Mean-only thesis handoff and THESIS_UPDATE_MAP.md are complete; full real930 comparison and fresh runtime remain incomplete. User caps unstarted external models at8 epochs; completed32-epoch EDSR/NAFNet and14-full-epoch RDN results are retained with actual durations reported. See [monitor](Experiments/R153_MeanExternalBenchmark/reports/TRAINING_MONITOR.md).

### R152 formal TIFF-image training package (2026-10-04)

同日新增generate_data.py及generation/五份當初原始程式，從固定種子重新生成全部768母場景／9216 TIFF，阻擋舊實驗及現成影像讀取仍通過；所有像素、TIFF內容、完整實際輸入及前四次CUDA更新均相同。另址無訓練影像時可生成，--data-dir可直接正式訓練新資料。最新包35個PY、9257檔約476.5MB，ZIP約457.5MB，outputs空白。[完整生成與驗證紀錄](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_DATA_GENERATION_REPRODUCTION_20261004.md)。

最新交付為Deliverables/R152_Standalone_ImageFiles_20261004，正式Bank.read從TIFF直接讀取，不依賴NPZ訓練容器。3072清楚／3072無噪模糊／3072幾何標記，原float16轉訓練FP32的數值完整保存於TIFF32，索引及向量標記為PY。全905969664影像值的PNG16測試有144073個還原差，故選浮點TIFF；使用者指定不附PNG。全部3072實際輸入／目標／幾何／算子均與原版完全相同，CUDA前4次損失、停2次接續至4次與連續4次亦完全相同。35個PY、9257檔約476.5MB，ZIP約457.5MB；模型／權重／PSF未改，沒有新的正式訓練。[報告](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_TIFF_TRAINING_PACKAGE_20261004.md)。

### R152 clean Python standalone package (2026-10-04)

Deliverables/R152_Standalone_20261004包含完整3072視圖和768組幾何資料，原FP16儲存保持逐陣列完全相同，讀取後FP32與在線加噪／分組／算子選擇忠於原配方。只有PY控制檔，NPZ/PTH/BMP保留必要資料；無外部連結、快取及驗證試跑結果。訓練預設載入包內已訓練主體做8192次擴充，可用--from-scratch完整兩階段各8192；續訓支持正常中斷及完成更新後的評估接續。所有3072輸入、209張量、原前4次損失和原生整張示例均精確一致；兩階段短測、異址拒絕來源讀取、CPU／CUDA、8／16位元讀取及ZIP逐檔核對均通過。原來源只有已授權報告更新的封存雜湊過期，本次僅更新該文件來源鎖，其他33檔保持一致。新包裝不是重新正式訓練或模型升級。[交付與驗證](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_STANDALONE_PACKAGE_20261004.md)。

### R152 actual thesis visual evidence (2026-10-03)

完成第6.1節／圖6-3實際25核響應、第6.2.3節同區域RAW與MOSR原生輸出、第6.2.4節同物件30條實測輪廓。PSF原MAT101×101×5×5逐行堆疊與實際銀行逐元素相同，部署float32核轉型後亦完全相同；25個CSV原矩陣逐檔精確回讀。影像固定第16趟起點004246_XY_0/1.bmp、共同亮度範圍與相同129×129裁切，5／50µm比例尺；輪廓固定物件5、起點、全部30趟64原始邊界點，只減已保存LSC圓心，不改尺寸或方向。另列九顆起點共34560個兩方法邊界點；中心物件局部輪廓重拍RAW62.750035／R15217.987640nm，不替代全資料63.758／18.600nm。五頁PDF逐頁渲染查看通過，六個PDF、PNG、SVG、中英文圖說、原MAT／校正紀錄與原生影像資料完整封存；70個壓縮檔成員均核對。[補件說明](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_THESIS_VISUAL_EVIDENCE_20261003/FIGURE_NOTES.md)；[資料包](Deliverables/R152_THESIS_VISUAL_EVIDENCE_20261003.zip)。沒有新訓練或重建後校正。

### R152 RAW complete research record and within-scan recalculation (2026-10-02)

使用者指定論文只比較RAW與R152，以單趟30步波動為主，30趟用於改善範圍。由兩方法各30份中心CSV和64點輪廓NPZ完整重算3600筆位移、16740個圓及720方向插值輪廓。34份封存來源、930張RAW、930份R152原生浮點輸出及保存點逐檔重驗通過。單趟波動合併10.199758→4.864821nm，降低52.3045%，30/30趟改善；20000次整趟配對、種子20261002，改善率95%區間49.6679%～55.0380%。直徑／輪廓／去尺寸重拍降低59.5%／70.8%／71.8%；SEM表直徑差增加34.397279nm，終點有號偏差及終點SD的配對區間跨零，無全面準度改善主張。主文件涵蓋兩階段訓練、一次U-Net脈絡與三個獨立原尺寸階段、受限25PSF支路、完整定義及逐趟／逐位置表；資料附件只含RAW／R152。這是既有實拍的重新計算，沒有新拍攝、重新訓練或基準升級。[主文件](Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_RAW_FULL_RECORD_20261002/REPORT.md)；[完整附件包](Deliverables/R152_RAW_COMPLETE_RESEARCH_RECORD_20261002.zip)。

### R147 native-image PSF consistency and internal audit (2026-09-26)

第8192次固定模型、930張實拍與8370圓全部核對；單張入口重播與批次浮點輸出差0。短步MAE／重拍4.537／4.720nm，直徑／輪廓重拍16.336／19.751nm，起點相對MAE／重拍18.120／10.279nm，SEM外框平均直徑差+207.067nm；尺寸重拍改善而短步退步，不全面採用。內部診斷完成4320筆階段圓、1134筆位移控制、810筆裁切、1134筆成像擾動、108筆R137格點控制、14組實際訓練梯度及768組資料核對。原尺寸對齊裁切影響極小；1像素平移R147平均額外圓心差0.865nm，8像素0.000305nm，R137接近數值精度；該弱點在R140v2也存在，不能當作全部退步原因。R147對比提高20%時圓心平均變化3.897nm，R146為1.632nm；添加0.5像素模糊的直徑變化R1473.543nm，R1466.579nm。第四次在30張中的18張使再成像差增加，仍改變邊界；合成配對最多1.233像素，实拍每步约5.8像素，每母場景模糊與亮暗固定。改良計畫分開檢驗取樣穩定路徑、跨成像狀態資料與量測要求，未新訓練或依診斷提前停步採用。D/H成果與狀態已對齊，原資料／權重／正式基準保留。[完整診斷](Experiments/R147_FullResPSFConsistency/reports/R147_INTERNAL_AUDIT.md)

### R146 actual-SEM core-halo PSF matched pairs (2026-09-25)

研究版MAT標記`research_only=1`，九顆SEM外框校準，25張PSF來源驗證通過；預先封存六視角、18個留出圓外觀中，新模型平方差0.001791，較原BADS0.002997及單一高斯0.002105低。與R145固定相同768母場景、分組、雜訊、逐場景PSF索引、模型及8192次更新，只換銀行與模糊配對；固定930張及8370圓完整量測、單張入口逐值重播及最終稽核通過。R146短步PI平均差／重拍4.313／4.459nm，較R145的3.990／4.016nm退步；直徑／輪廓重拍23.082／20.371nm，較R145的21.013／16.001nm退步；起點相對位移重拍10.369nm較R145的11.216nm低，但平均絕對差18.220nm未優於18.070nm。同九顆SEM外框參照平均直徑差R146+218.744、R145+207.186、RAW+185.182nm；Excel表版本分開保存。逐圓固定步進重拍8.837nm，比R145的7.933nm高；270組中203組較差。生成測試PSF首選10/206，實拍全930張首選第8顆；有效光學混入僅0.93%，12張實拍關閉分支的逐顆直徑最大差0.360nm，量測改變主要來自重新訓練的主網路。SEM外框不是神經清晰答案，研究版來源不能自動晉升正式PSF，正式基準不變。[完整結果](Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/reports/R146_RESULTS.md) · [原因核對](Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/reports/R146_CAUSAL_AUDIT.md)

追加來源與穩定性核對：768組清晰目標全與R145逐值相同；692組新PSF卷積及76組清晰對照的1536張影像、雜訊與8192筆訓練順序獨立重播完全相同，並抽查21個實際訓練批次。R146實拍邊緣平均較窄，但固定位置／圓的邊寬重拍起伏0.090像素，R145為0.025；279/279組R146較不穩。原圖跨趟模糊變化與R146輸出邊寬相關0.968，R145為0.476。這是輪廓退步的影像機制線索，仍不能獨自指認焦距或照明。[資料鏈稽核](Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/results/data_training_chain_audit.json) · [邊緣圖與數值](Experiments/R146_SEMCoreHaloPSF25_MatchedPairs/reports/figures/edge_width_repeatability.png)

### R145 corrected center-nine PSF matched pairs (2026-09-24)

修正後來源MAT通過28份照片與九顆SEM身分來源核對，R145以同768個清楚母場景、分組及逐場景PSF索引更換25顆銀行與卷積模糊，完整完成8192次、930張及8370圓；`results/final_audit.json` 通過。短步PI差3.990nm、重拍4.016nm，較R143的4.425／4.290nm改善，仍比R140v2的3.640／3.530nm高。逐顆固定步進重拍標準差7.933nm，介於R143的8.413與R140v2的6.829nm。直徑重拍21.013nm也介於兩者；輪廓重拍16.001nm及去尺寸形狀12.153nm較兩者低。新銀行減少R143的大幅平均圓心修正，未消除逐圓位置波動。依新PSF校準所用SEM Excel值，平均直徑差R145+191.887nm、RAW+169.883nm、R143+95.230nm；校準值均值2629.737nm，舊輪廓參照均值2614.439nm，不混用。SEM尺寸是PSF校準輸入而非神經清楚標籤，同九顆比較不作獨立尺寸準確度宣稱。選擇器測試6/206首選，實拍930張全首選第24顆。新增的後驗檢查以模型實際運算重現PSF頻域錯位、約1.59%光學混入及只剩3.23%的零頻反推；12張實拍開關分支的平均直徑差僅0.35–0.50nm；206組保留場景的PSF差異全部低於各自雜訊。PSF來源與驗證照片的亮度／對比亦有差異，來源單次擬合不可直接保證逐張量測。自適應效益未證實，正式基準不變。[完整報告](Experiments/R145_Center9PSF25_CorrectedPairs/reports/R145_RESULTS.md) · [原因分析](Experiments/R145_Center9PSF25_CorrectedPairs/reports/R145_PSF_LIMITING_MECHANISMS.md)

### R136 十字中心九顆

R129修正取樣位置再驗證完成（2026-09-20）：與Raw共16740圓擬合及720方向輪廓重算、4影像重播、60個R129不確定度分量重算通過。短步PI差4.125nm、重拍4.251nm；尺寸重拍19.231nm、輪廓18.437nm。SEM尺寸偏大224.472nm及30μm終點偏差+42.933nm保留。獨立論文交接包285檔約101MB，全部雜湊核對。 [R129交接入口](Deliverables/R129_Corrected_Corner9_Thesis_Handoff_20260920/START_HERE.md)

R128修正取樣位置論文交接包（2026-09-20）：Deliverables/R128_Corrected_Corner9_Thesis_Handoff_20260920；先讀START_HERE.md與HANDOFF_FOR_THESIS.md。含Raw對照、修正後九顆、圖表、完整明細與方向推定限制；280檔約94MB，雜湊及閱讀連結檢查通過。

R136新十字九顆Raw/R128完整對照交付：10張圖（新增平均±1SD疊圖）、3600合併位移／32400逐顆位移／16740輪廓。R128短步PI差降低54.6%、短步重拍61.9%、輪廓重拍78.3%；SEM平均尺寸偏大差距185.182→222.040nm及終點偏差未改善亦完整保留。 [Raw/R128完整比較](Experiments/R136_PIRepeatability/reports/R136_RAW_R128_CORNER9_RESULTS.md)

R136最新十字九顆的R128專頁完成：位移30次曲線、60位置詳表、8370輪廓、逐顆及逐方向表、4張科學圖。短步重拍3.708nm，輪廓13.835nm；30μm終點偏差+41.966nm／重拍14.193nm，完整保留。 [R128詳表與圖](Experiments/R136_PIRepeatability/reports/R136_R128_CORNER9_DETAIL.md)

R136方向補查：已核對暗柱／亮孔；整視野較支持左右鏡像，暫用22,23,24／28,29,30／34,35,36。相同十字區域兩候選近乎同分，屬推定而非唯一證實；保留90度候選敏感度。 [方向依據](Experiments/R136_PIRepeatability/reports/R136_SEM_DIRECTION_RESULTS.md)

R136十字中心九顆重算完成（2026-09-19）：四組各930張／8370圓心；R128短步差3.708nm、尺寸波動9.527nm最小；SEM九顆集合均徑差R61+115.803nm、R128+222.040nm。集合22,23,24,28,29,30,34,35,36；逐顆方向保留兩候選。舊九顆有影像與PI但未配SEM，不混成尺寸真值證據。 [新九顆報告](Experiments/R136_PIRepeatability/reports/R136_SEM_CORNER9_RESULTS.md)

### R136 SEM追加對照

R136 SEM追加核對（2026-09-19）：找回P/V各9張、三處副本18/18一致；舊配對36顆×3曝光×4方法完成，R128直徑差76.326nm、R129原80/16為96.624nm。使用者確認同片；九月九顆與舊SEM逐顆位置尚未建立，初步為不同區域；不混入30次統計。 [SEM核對報告](Experiments/R136_PIRepeatability/reports/R136_SEM_REFERENCE_RESULTS.md)

### R136 輪廓與尺寸重拍驗證

R136輪廓／形狀／尺寸重拍驗證：四組33480輪廓完成，R128尺寸／形狀波動13.558／13.560nm最小；實物準確度待使用者提供已確認存在的同批參考，不升級模型。 [驗證報告](Experiments/R136_PIRepeatability/reports/R136_SHAPE_SIZE_RESULTS.md)

### R136 R128追加完成

**R136四組LSC完成（2026-09-18）：** 新增固定R128，全四組各930張／8370圓心。短步MAE原圖／R61／R129／R128=8.667／5.160／4.092／4.025nm；長距離17.738／15.267／15.712／15.496nm。R128與R129差距未明確，最差短步R129較低；不作全面升級。新影像放H槽，舊三組資料及PDF/ZIP保持不變。[四組報告](Experiments/R136_PIRepeatability/reports/R136_LSC_FOUR_MODEL_RESULTS.md)

### R136 LSC圓心位移比較

R129不確定度補充：已完成60個固定位置的資料內重拍分量與時間模型平均值評估；1μm步距s=3.115–5.475nm，30μm終點s=15.810nm、平均PI差值+15.560nm。PI／尺度校正缺項保留未知，完整總不確定度未定，不以MAE代替。[計算報告](Experiments/R136_PIRepeatability/reports/R136_R129_UNCERTAINTY_RESULTS.md)

**R136 LSC完整結果（2026-09-17）：** 原圖／R61／R129各930張、8370圓心完成；短步平均絕對PI差距8.667／5.160／4.092nm，起點相對17.738／15.267／15.712nm。R129短步優於R61；長距離兩模型差距未明確，不能全面排名。全部25110圓心獨立重算、5400合併位移與PI對應核對。R61既有PDF包保留。無模型升級。[三組LSC結果](Experiments/R136_PIRepeatability/reports/R136_LSC_RESULTS.md)

<!-- R135_START -->
**R135：** R135：六個固定模型加原圖的同精度比較，完成7/7組；舊V42含資料重疊標記，無訓練或升級。 [結果](Experiments/R135_UnifiedModelComparison/reports/R135_RESULTS.md)
**R61資料審查（2026-09-16）：** 已確認目前36顆SEM尺寸表中35顆數值用於R61訓練目標，另有全體平均尺寸監督；1284筆SEM答案相關資料在末階段訓練名單，852裁切／目標逐像素重現。R61不可視為排除評估答案後的乾淨替代品；原分數不改，未證明目前201張位移照片全部直接進訓練，完整祖譜未封閉。[審查](Experiments/R135_UnifiedModelComparison/reports/R135_R61_TRAINING_AUDIT.md)
<!-- R135_END -->

### R134 complete full201 screening, not admitted (2026-09-15)

<!-- R134P1_START -->
**R134 P1：** 保留精度版本長訓練及最終比較完成，尚未採用為正式模型。[保留精度驗證](Experiments/R134_DirectStateRepair/reports/R134_PRECISION_REVALIDATION.md)。原8bit未通過判定保留，新版本需全部合格並單獨打包實測才長訓練。
<!-- R134P1_END -->

Follow-up diagnosis: [R134_CROSS_AXIS_DIAGNOSIS.md](Experiments/R134_DirectStateRepair/reports/R134_CROSS_AXIS_DIAGNOSIS.md). Same C checkpoint/image/reader: Raw43.240395nm, model float44.019181nm, exported8bit48.665763nm. Quantization adds4.646583of5.425369nm (85.65%for this case only). Actual16bitPNGreadback44.039084nm. Both Cseeds show pattern; sixfullframePNG replays and702independentcircle refits pass. Neighbor18to19 and19to20 retain7.331/6.418nm extra side displacement at float. No independent realYtruth; rigid image registrationRaw/Cfloat53.697/53.896nm, so a Raw-relative gate cannot identify true model error. Original8bitnegative admission preserved; full201highprecision requalification has NOT run. No optical removal, step-count reduction, newtraining or promotion.

All201 images were computed; closeout failed because a NumPy boolean could not be serialized. The original partial JSON and every output remain unchanged. Independent recovery refit1809centers and recomputed634candidate/Raw pair rows, using unchanged prospective thresholds.19/20checks pass; locked120maximum cross-axis48.665763nm vsRaw43.240395nm (same20x_0p5umframes16to17), ratio1.125470 exceeds1.10. No long package or long training, no alternate-seed substitution or promotion. Canonical report: Experiments/R134_DirectStateRepair/reports/R134_RESULTS.md. Correct recovery is results/full_motion_recovery_v2/complete.json, referenced by long_admission.json; do not parse the retained incomplete original as a completion. Original A/C short results remain valid within their scope. B/D unexecuted pending independent calibration.

### R133 size-mechanism diagnosis and repair design complete (2026-09-14)

Canonical results: [Experiments/R133_SizeMechanismDiagnosis/reports/R133_RESULTS.md](Experiments/R133_SizeMechanismDiagnosis/reports/R133_RESULTS.md); repair design: [Experiments/R133_SizeMechanismDiagnosis/reports/R133_REPAIR_DESIGN.md](Experiments/R133_SizeMechanismDiagnosis/reports/R133_REPAIR_DESIGN.md). FrozenR129long8192, ninearms:Raw,Optics,Neural,Final,NoOptics,ResidualHP,DirectResidual andtwoRMSmatchedFinalcontrols. All128generatedparents/256views,64area-renderedcircleconditions/640readouts,normal3SEMfields/972rows complete. FinalreproducesR132W16. ControlFinalabsdiametermedian.03952px vsRaw.05088;41improve23worsen,worst.70739. CleanTargetreaderitselfranges−.03217to+.04708;8vs16formationmaxdiameterdifference.000442. Idealbluroftenmakesmeasuredcircletoosmall andmodelmovesoutward, unlike already-large realSEMopticalreadout. This supports imaging/reference mismatch, not an identified allocation among material response, scale and reader definitions.

Realstage diameter medians:Raw88.204,Optics81.083,Neural101.492,Final102.232nm. Within-exposurepairedFinal-Raw median12.122nm all36increase;Neural-Optics18.905,Final-Neural.687nm. Head/opticsinterventionsremain101–102nm; nofrozenreplacementadopted. RMSmatchingbeforeFOV~.99857–1,actualafterFOV~.98896–1.01257:approximate, notexact; wordingcorrectionandinitialdraftretained. GeneratedFinalMAE1.831vsResidualHP2.682/DirectResidual4.377;Neural29.329,mean-aligned16.509. Internalimagescannotbeclaimedcleanphysicalreconstructionswithoutdirectsupervision; geometryinformationmaystillbeuseful.

Neutraloutputcontractandnonzero/finite-differencegradients verified; oldobjectivehascorrectradiusgradient, whileconsistent2pxdiameterbiasgiveszeropairloss. Qualifiedtwo-levelcoverageobjectiveisprototype-only,notvalidforunknownrealmaterialmapping. Initialneutralroundofffailureandtwoorchestrationwaitfailurespreserved; intendedstrictneutralcontractfixedbeforemainruns,originalweights/sourcesunchanged. Independent972SEM/640controlfitsand2304image metrics pass. No training, oldconfirmationaccess ordefaultchange. Proposednextwork: qualify reference/forward-data relationship, retainfoursharedupdates/AA/measuredopticalinformation whilemakingimage/outputsemanticsneutralanddirect, thenmatcheddata×interfaceprobes, followedbyseparatequalifiedgeometrylosscomparison. No new trainedreplacementexists.

### R132 boundary-policy research complete (2026-09-14)

Canonical report: [Experiments/R132_BoundaryPolicyStudy/reports/R132_RESULTS.md](Experiments/R132_BoundaryPolicyStudy/reports/R132_RESULTS.md). SameR129long8192checkpoint/foursteps, vary only finalRawretention widths80/64/32/16/0; nonzero16transition,zero means no retention. Reuse verifiedpre-guard fields,201x5PNGs andall9045LSCcenters;540primarynormalSEM reads+75samepillar contextreads. Currentfullforward verifies storedpre-guard semantics;80float/PNG/SEM/centers reproduce. All615SEM valid,independent615SEM/9045circle fits and1585paircalculations passed. Outer20 shape/correlation/MZC allimprove at16,diameter allworsen;central16 unchanged. All36shape16.397→8.411nm,MZC62.651→9.268,diameter96.380→102.232. Locked120SD6.991→6.929,within4.204→3.808;full194cross7.974→8.069worsens andlockedmaxcross59.088→60.292. Not uniform superiority.

Real context: centralpillar16 at3exposures,measurement-window leftmargins0/16/32/64/96,15currentforwards; actualopticalcontourclosest14.5–15.4pxinside edge. Crop changesglobaloptical/qualitycontexttoo. Pre-guard errorvsfullfield fallsfrommaxwindowmean.188gray/maxpixel14.90 atmargin0 to.00495/.01953 atmargin16;80blending substantiallychanges same-object shape. Existing-normal-field evidence supports16researchtrial,not universalpixel-edge safety. PublicSEM/fullfieldreplay exact; fractionmap isnotconfidence. No training/defaultmodelchange/oldhashrebaseline/confirmationaccess. Sizebias remains a separate model/reference problem; do not compare new16numbers directly toold80counterparts without matching policy.

### R131 frozen recurrent-step validation complete (2026-09-14)

Display follow-up: [Experiments/R131_RecurrentStepValidation/reports/R131_BOUNDARY_OUTPUT_AUDIT.md](Experiments/R131_RecurrentStepValidation/reports/R131_BOUNDARY_OUTPUT_AUDIT.md). Three-exposure exact replay and independent spatial blending confirm gallerypillar18 is partially replaced by Raw at the final80/16FOV guard, not a missing neural forward. Central16measurementwindows are fullymodel, outer20partiallyretained. Added labeled full-field map and centralpillar16 example; oldfigures/results preserved. Pre-guard reconstructions are diagnostic only; no defaultchange. Inner16four-vs-three improves shape/diameter/radial16/16, but cannot replace the36-pillar primary population.

Canonical report: [Experiments/R131_RecurrentStepValidation/reports/R131_RESULTS.md](Experiments/R131_RecurrentStepValidation/reports/R131_RESULTS.md). User requested checking four repeated refinements. The frozen R129 long-training8192 checkpoint is evaluated at0–4learned updates, always retaining the same global optical conditioning, final original-image anchor and80/16FOV guard. Zero is not Raw; intermediate final outputs never feed the next iteration. All201nativeframes plus3normalSEM fields at5prefixes yield1020PNGs,540SEM rows and9045LSC centers. Existingfour-stepoutputreproducedonall201frames, oldLSCcenters reproduced. Fourthversusthird: centeredshape33/36better,diameter30/36better, butMZC20/36worse despite loweroverallmedian. Fullsame120pair and194within-session results,3recordedrepositionings andworstcases remain separate. Standaloneprefix timing excludes intermediate exports and matches savedPNGs onSEM/full-fieldcases.

Independent540SEMmetric recomputations and9045circle refits,1585pair-arithmetic checks andaggregate recomputations complete. Initial random-inputpreflight mistakenly askedbitidentityacrossdifferentconvolutionshapes; failedsource/logpreserved, actual1.19e-7difference iswithinoriginal1e-6protocol. No historicalexpectedhashreset. Allreadsource/protectedbindings preserved. This isfrozencheckpointusagediagnostic,notfromscratcharchitecturecomparisonorproofthatfourisoptimal. No training,default replacement,promotionoroldconfirmationaccess. See canonical tables for model,shape,motion andruntime tradeoffs.

### R130 clean V42 practical comparison complete (2026-09-14)

Canonical report: [Experiments/R130_CleanV42Comparison/reports/R130_RESULTS.md](Experiments/R130_CleanV42Comparison/reports/R130_RESULTS.md). User explicitly requested keeping R129 unchanged and training only a fresh pure V42 for tens of epochs on similar clean data. Preserved V42 encoder-decoder/AA/directional boundary/Raw-anchor/quality architecture, fresh seed1309001, no legacy neural weights or teacher. Fixed legacy PSF buffers are shared with R129; new V42 constructor weak scale is active(.35effective), unlike old saved0. Deterministic pad/bilinear backward adaptation preserves original forward. Same512/128/128 source-only split,32epochs,4parents/update,4096updates,16384parents. R129 lineage has16408parents but different batch/optimizer/objectives and prior selection; not a fully balanced architecture causal experiment.

All33dev,5realSEM panels andfinalgeneratedtest complete;all201nativefields and1809LSCcenters,locked120andall194within-sessionpairs measured with matching reader/FOV rule. FinalV42/R129 radial46.392/49.523nm,diameter91.951/96.380,correlation.7473/.6919,centeredshape16.425/16.397,MZCerror66.351/62.651. Paired V42 improves diameter29/36,centeredshape25/36,MZC24/36,despite slightly worse overall shape/MZCmedians. Locked120stepSD6.919/6.991,nominal6.200/6.302,within4.682/4.204,cross5.237/4.798nm. Full194SD29.308/29.098. Sameimage FP32 one-warmup/three-repeat timing.428sV42/9.976sR129. OldV42shape6.810nm advantage not reproduced, but differences cannot solely be assigned to answer removal because data/initialization/training/inference differ.

WinError5 status-file lock afterstep1538: checkpoint1536 intact. Preserve allfailurefiles andoriginalfrozen sources; process-local IOretry wrapper resumed unchanged computations, actualreadlock testpassed. Steps1537/1538 replay exactly;4098calls but4096uniqueupdates. Freshinit reproduced,256parent inputs independently rebuilt,108finalSEM contours and1809LSCcircles independently refitted,publicSEM14replay exact. R129files andmetadata entry unchanged;no model promotion or oldconfirmation access. Both models remain research references; independent calibration/new physical samples and sizebias remain open.

### R129 V42-design integration: completed bounded pilot, retained prototype (2026-09-12)

2026-09-13 continuous sequence completion: [Experiments/R129_OpticalPriorHybrid/reports/R129_CONTINUOUS_LSC_RESULTS.md](Experiments/R129_OpticalPriorHybrid/reports/R129_CONTINUOUS_LSC_RESULTS.md). Fixedlong-trainedD8192 reconstructsall201sources in4sequences,with201RawandR129LSCreads/1809centers each. Primarysame120Raw-selectedpairs yieldR129stepSD6.991056nm,R1286.872913,R617.220139;nominal6.302470,within4.203669,cross4.798278. Secondary194allwithin-sessionpairs vsRaw only,3pre-existingrecordedrepositioningpairs separatelykept. No model-based frame rejection. Source-definedcommonFOV-context subset reported asdiagnosticbecauseR129uses80/16guardversusR12864/16. DirectfullNNdepthwiseoperationfailed32bitindexlimit; originalfailure preserved. Separateglobaloptics/features/state/quality andlocalpriorcore512/halo16executionverified onreal fields/random input anddifferentcores,alltested8bitpixels equal,smallfloatdifferencesrecorded. All3618circles independentlyrefitted,634pair-table calculations(394unique method/adjacentpairs)recomputed,Raw1431oldcenters reproduce,andworstR129-vsR128pairpublicentry/LSCreplayed. Newportableaddon addedwithouteditingfrozenpackage files. No training/promotion oroldconfirmationaccess; priorSEMsizeissueisnotresolvedbyLSCresults.

2026-09-13 completed long-run audit: [Experiments/R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md](Experiments/R129_OpticalPriorHybrid/reports/R129_LONG_TRAINING_RESULTS.md). One8192-update continuation finished2026-09-12T14:20:12UTC. All8192rowsunique/inorder,all512parents per16epochs;64actualinputs independently rebuilt.24completion records and1603package resources unchanged; checkpoint/optimizer at8192. Full17dev,5real andfinaltest present. Native dev4.87358→2.68142, but SEM radius41.579→49.523nm anddiameter80.679→96.380nm worsen. Centeredshape21.352→16.397nm improvesall36;MZCerror86.605→62.651 improves31/36, diameter worsens31/36. Four-pairwithin-grid8.828→7.434, nominal6.746→6.970,cross6.933→7.721nm;no temporalSD. Independent540-rowcircle-refit/20pairarithmetic andpublicfinalSEM14replay pass. First inference invocation returnedexit1withoutdiagnostics; initialreviewstoppedonmissingimage; separate retry/v2passedunchangedtests, failures retained. No endpoint adoption, auto-default replacement, oldexpectedhashrefresh or confirmationaccess. KeepR129design; address sizebias with bounded causal checks instead of more epochs by default.

2026-09-12 standalone training follow-up: [Experiments/R129_OpticalPriorHybrid/reports/R129_STANDALONE_TRAINING.md](Experiments/R129_OpticalPriorHybrid/reports/R129_STANDALONE_TRAINING.md). User requested a manually operated independent package and start of full training. All768source parents copied with hashes; hostPython/CUDA andMATLAB remain external software dependencies. SingleD continuation,16epochs/8192new updates,128-update saves,128devcases every512,real3SEM/4motionpairs at0/512/2048/4096/8192; native image+gradient+pair loss matches pilot. All inputs/code/weights local, full audit,16discarded probe updates, exact optimizer resume and original real-reader parity pass. Package physically relocated for public dry-run/inference/menu checks, then restored. Real training paused/saved at4 and resumed; observed44/8192 at2026-09-12T09:40:14.834275+00:00, PID5596. Current status file is inside package results/training/r129_long_01. This is a verified start, not training completion, superiority or production promotion. Default inference remains originalD; old records and confirmation remain untouched.

2026-09-12 organization follow-up: [Experiments/R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md](Experiments/R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md). User retains R129 as the next architecture; do not switch back to the old V42 backbone by default. Split optics/shared reconstruction/original-image output into an organized package without changing arithmetic, registered parameter names, checkpoint or active modules. All8 saved states have exact forward/input-gradient/parameter-gradient agreement; D three full SEM fields and eight fixed motion ROIs match old float outputs and historical PNGs exactly. Four observed intermediate states match independently reconstructed old states, and mutation of observation copies does not affect output. Existing source/weights remain unchanged. A new tested image entry uses the same D checkpoint. This does not implement the missing direction-specific branch, per-step full physical correction or uncertainty estimate, and does not establish speedup or new scientific efficacy. Zero new training; previous mixed-result verdict and qualification limits remain.

Canonical report: [Experiments/R129_OpticalPriorHybrid/reports/R129_RESULTS.md](Experiments/R129_OpticalPriorHybrid/reports/R129_RESULTS.md). User requested preserving measured optical fusion and improved upsampling as thesis design requirements. New isolated D checkpoint retains both; A/B/C are experimental controls only. Four matched 24-update runs completed 96 updates, with actual initial tensors and all 24 consumed inputs independently rebuilt. V42 E120 calibration buffers alone are imported: 25 measured 101x101 kernels plus 4 very similar candidates; saved legacy adaptive beta_scale=0, so its default-loaded branch was inactive. New input-stage optics correct centroid origin/DC gain and remain active; V42-style AA matches the legacy operator. This is an adaptation, not a complete exact V42 transplant or new novelty proof.

Normal SEM 13-15: 36 pillars, 864 valid reads across all four arms before/after training. D24 radial/shape-correlation/CD/centered-shape/MZC-error medians = 41.579nm/0.668942/80.679nm/21.352nm/86.605nm; A24 = 41.869/0.643638/80.607/22.304/82.747. D improves centered shape on 27/36 but radial on only 16/36 and diameter on 15/36. D remains weaker than original R128/V42 on fine shape. All arms share a converted decoder and new Raw anchor: A is already weaker than original R128 at initialization, so total differences cannot be causally assigned to added optics/AA. Four ROI motion pairs only: D nominal/within-grid/cross-axis 6.746/8.828/6.933nm vs A 6.942/8.434/7.245; no temporal SD or complete thesis120-pair claim.

Full D SEM14 replay exact; disabling optics or AA changes output. Learned versus uniform optical weights changes that image by at most 1.1921e-7 (0-1 scale), so adaptive selection's independent benefit is not established. 864 contour rows refitted by independent two-parameter circle method, all 36 motion pairs recomputed, and 51 recorded source paths unchanged. Original deterministic-backward failure and original plan/source are retained; separate v2 preserves forward/criteria. Keep D as the user's requested architecture prototype; first repair conversion/output retention and verify meaningful instrument-specific optical variation before a justified larger training study. No model promotion, old-confirmation reuse, old evidence rebaselining or thesis edit.

### R128 completed four-run study, one follow-up candidate, no production adoption (2026-09-09)

2026-09-12 full annotated-v34thesis review and replacement assessment: Experiments/R128_SourceOnlyFullTraining/reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md. Read7chapters,111referenceentries,252livecommentsandannotationindex,viewed60embeddedfigures andkeyrenderedpages. Source13,121,560bytes/SHA256d85a7987bbea8f5f58585334104f9d0425f3a42a92e51bbbb187cca2c5a9fc12capturedread-only;originalDOCXnotedited. Thev34modelisV42E120anditsclaimchainincludesmeasuredPSFfusion,AAupsampling,raw-anchoroutput,refinedSEMshape/MZC,LSC/MZCchoice,eight-modelcomparisonandruntime. R128hasdifferentimage-only4sharedupdatesandsimulationobservationsupervision,notalloldmodules. Traceabilityisnotcompletephysicalinterpretability.

Actualv34bridge uses166frames/120pairs,only87pairscommonwithSep10R128study.22newfullR128images+144verifiedreuses;Raw/V42all2988centersreproducev34to4.55e-13px. NewR128LSC7.250296nmstepSD,5.767442nominalMAE,3.416135within-grid,6.764177crossaxis;V427.292303/5.742972/4.885544/6.551281. ReplacingV42inold7baselinecomparison yieldsranks3/1/3,notpurearchitecturecomparison. Oldv34readerprocessing-orderstate isexplicit;do notmixwithSep10per-pillar-resetreader.

FineSEMnormal3exposure bridge usesexactlegacyper-cellnormalizationandmaxgradientcontours,180SEM/144opticalpointsand720radialsignature. Initialnativecellparityfailureisretained;separatev2restoresdocumentedim2uint8(mat2gray(cell))andall108Rawcellsreproduce. All216Raw/V42metricrowsreproduce;324rowsretained. R128vsV42radialMAE38.705044vs43.324390nm,CD76.646764vs86.295184nm;correlation.767368vs.942754(all36worse),MZCerror50.989858vs5.816055nm(33/36worse). CenteredshapeMAEdiagnostic16.118916vs6.809732nm;R128reducessizebiasbutdoesnotpreserveirregularshapeaswellintheseexistingreferences. SEMnonroundnessisnotperfect-circlepreference. Only13–15testedhere,notwhole12exposurepaperclaim.

FreshA6000strictFP32pairedcommonrecipe(tile256,overlap128,batch8,2warmups/8runs):V422341.82msvsR12828066.46ms,about11.98times. R128validatedfullFOVcore256/halo64/Rawguardpipeline16834.22msmedian(1warmup/3runs),outputbitwiseequaltoexisting. Differentrecipeoutputqualitynotpromoted;donotmixnewtimeswitholdpaper1102.3ms/oldsevenmodelranks. Modelparametercountsmallerdoesnotimplyfaster. Decision:retainR128researchdirectionbutdonotimmediatelyreplacev34;prioritizeirregularshapeandcostbeforeadaptingclaims. PreserveoriginalPSF/systemworkasactualcharacterizationandWienerreference;do notclaimcurrentR128ingestsmeasuredPSFbank. No training,checkpointchange,sourceDOCXedit,oldexpectedhashreplacementorproductionpromotion.

2026-09-10 same-protocol LSC completion: Experiments/R128_SourceOnlyFullTraining/reports/R128_LSC_R61_COMPARISON.md. This supersedes the earlier pending-LSC status below, while preserving those time-stamped reports. 159nativeframes (150newR128forwards+9verifiedreused),120fixedRaw-selectedpairs,4sequencesand9pillars. HistoricalR61v16PSF-offcheckpoint verified andonefullframepersequence reproduces saved8bitoutputs exactly. Raw159frames/1431centers reproduce historicalreader values to about4.55e-13px. R128andR61each add1431centersand120pair measurements;withRawreplayandfinalFOVguarddiagnostic,5724saved-boundarycircles independently refitted,all pair arithmetic independently recomputed. All7primarymethods use identicalpairs;nofailed/missingrowsorposthocframechoice. WorstpairvsR61replayed through the publictrialentry with exactfloat/neural/PNGoutputs andmatchingLSC.

完整同條件比較已完成。R128 相對 R61 的整體位移波動由 7.220 降至 6.873 奈米，改善約 4.8%；不同柱體量出位移的不一致由 5.823 降至 3.416 奈米，改善約 41%。結合較好的配對 SEM 輪廓、周長與圓度表現，R128 是更值得保留的單一綜合研究候選，但橫向偏移、個別影格及圓度相對原圖仍有退步或不確定性，沒有正式精密量測升級。

PrimarymeansequenceSDnm:Raw9.745101,Wiener7.391651,R617.220139,R1097.002564,R1197.260884,R1286.872913. R128medianwithin-gridSD3.415735nm;nominalMAE6.162762nm;cross-axis5.152931nm. Preserve per-sequence andworst-case findings in report. Source-definedFOVcontext:all50xwindowsfullyneural;20x0.5um180/306fullyneuraland27fullyRaw,20x1um333/360and3fullyRaw. Both-frameall-nine-neural diagnostic subset95pairs, neverreplacesmain120. Guard-off is sameforwarddiagnostic,notanothertrainedmodeloradoptedoutput. SEMpairedspecimen is separatefrommotionimages;no same-pillarSEMtruthclaimforLSC. V42trainingoverlap andR119causalauditcorrection remain authoritative. No training/modelchanges,oldhashreplacement,productionpromotionoroldconfirmationaccess.

2026-09-10 matched competitive review: Experiments/R128_SourceOnlyFullTraining/reports/R128_COMPETITIVE_REVIEW.md. Reused identical Raw/SEMmask sources for36pillars xnormal13/14/15 xRaw,R61v16,R109E48,R119E42,R128PNG x2references. No per-model alignment fitting. All1080rows independently recomputed;432previousRaw/R128rows reproduce. After median per-pillar across3exposures, R128historical/global boundary medians0.585814/0.375708px vsRaw0.769901/0.508201 andR1090.690251/0.442433. R128boundary beatsR109on33/36pillars with bothreferences and remains strongest aggregateboundary/area/perimeter among listedmethods in the16fully-neuralinterior. Circularity medianerrorsRaw0.016188toR1280.012494historical,but0.011769to0.015056global. Predictedcircularity is identicalacrossrefs;SEMreference per-object absolute difference median0.014586shows referenceconstruction sensitivity. Worstlocalerror canincrease. These are one reuseddevelopment specimen,notfreshconfirmation or universal geometry certification.

LSC summaries independently recomputed from the same120Raw-lockedpairs: mean per-sequence stepSDRaw9.745101,Wiener7.391651,V42E1206.922744,R109E487.002564,R119E427.260884nm. R128was notrun through this protocol; its0.013190pxfull-fieldRaw-relative registrationdifference is notformalLSC improvement. V42specifictrainingdataoverlap andR119causalauditcorrection remain authoritative. Nextdecision: same120-pairLSCevaluation of the singleP_s1285002model with Raw,Wiener,R109references and worst-case inspection,then resolve reference-sensitivecircularity before precisionadoption. No newinference/training,promotionor oldconfirmationaccess in thisreview.

2026-09-10 full-contour follow-up: Experiments/R128_SourceOnlyFullTraining/reports/R128_FULL_CONTOUR_SEM.md. Prior36/36claims were diameter/pitch readouts, not completeContour; this distinct supplemental test now extracts all36outer contours on normal13/14/15with unchanged historical ACMhelpers. PrimaryRaw200iterations/smooth1masks match all108oldRaw masks bitwise. Same Raw-derived integer shifts are applied to Raw,PNGandfloat outputs; fixed historical and R121global-pitch SEMreferences are unchanged. No per-candidate scale/rotation/translation fit. All1944rows valid across3predefined extraction presets,3image representations and2references; independent boundary/HD95/IoU/area checks agree within1e-6,zero support contacts.

PrimaryPNGfull-contour mean-distance/IoU improvements:historical36/36for each exposure;global-pitch36/36,35/36,36/36. Global-reference mean-distance mediansRaw0.514/0.513/0.508toR1280.363/0.382/0.365px. All16fully-neural interior objects improve for all3exposures/bothreferences. The worst mean-distance case,pillar12/exposure14/globalreference,worsens0.527834to0.539109px and is displayed. Perimeter/circularity and maximum local distance do not improve universally (globalexposure13worst2.236to2.828px). This establishes tested coarse pillar outer-contour benefit, not all local geometry or absolute material-edge truth. Existing structure-risk evidence and sole trial candidate remain unchanged.

2026-09-10 structure check complete: Experiments/R128_SourceOnlyFullTraining/reports/R128_STRUCTURE_CHECK.md. Raw-only feature/source plan preceded analysis;15new full-image inferences plus12verified reused outputs cover27real frames. Six motion suites at first/last adjacent pairs all12remain source-consistent,max0.0131902847px.12profile strips at3levels/two normalizations show12count flags, all resolved as original-domain endpoint crossings using actual context.12true checker junctions have max0.4679pxfixed-aperture readout change, strongly aperture-sensitive;32automatic square-region responses are diagnostic features, not all physical corners, and the2.237pxmaximum is a smallspot.

Known-reference controls:6clean,26corners/junctions,26dense. Exact nearest-line-segment contour distances with32pixels of actual surrounding context replace the imprecise sampled-point comparison in the final interpretation; all original values retained. Six clean cases have mean0.0328413pxunnecessary contour error,max0.535591px; contrast106-174cases have mean0.009894-0.015052px,max0.178328-0.258026px. Blurred corner mean improves0.173932to0.144400pxbut11/26worsen. Dense common25cases improve0.248982to0.157972pxbut9worsen; one low-contrast case has no candidate half-level contours and remains explicit. No claim of38pxobject displacement from periodic ordered matching. A new1pixel component at cropped boundary belongs to an existing243pixelneighbor in expanded context. No training/model changes. Continue soleP_s1285002research trial; prioritize clear boundary/corner protection and stable local readouts before precision adoption.

2026-09-10 normal-scope follow-up: source-only prospective development check names13/14/15before new outputs; P_s1285002improves36/36objects and16/16interior objects in all3. These are36physical objects repeated, not108independent cases or a qualified normal operating range. Single-candidate trial/restore.py was executed on full optical image14:float/PNGoutput matches the independent result exactly; source preserved, overwriting and unsupported input types rejected. Input brightness rejection is not implemented; clean controls and noncircular-detail preservation remain to be assessed. No new training or scientific-protocol rewrite.

Application scope clarified after final review: the user can fix camera/lighting and retake dark images. Prioritize normal controlled acquisition and realistic nearby variation; extreme-dark images define a retake/out-of-scope boundary. Do not retroactively relabel R128 failures as passing or pick normal inputs by candidate scores. Actual operating limits, input-quality rejection, normal-scene preservation and metrological qualification remain to be verified. The only follow-up candidate stays P_s1285002; final deployment remains one model. See Experiments/R128_SourceOnlyFullTraining/reports/R128_APPLICATION_SCOPE.md and config/application_scope.json.

Final review: all4runs completed at2026-09-09T13:55:38UTC. Execution audit confirms32768unique steps,224exact duplicated recovery calls, original frozen identities, all768data parents and5403historical protected files. All arms/seeds consumed identical recorded photos/order,64independent consumed-input replays cover16passes, and all12trained real evaluations were verified. Final288SEM rows were recomputed; complete dark-image inference and worst source-relative motion for P_s1285002were rerun and reproduce saved results.

Retain only P_s1285002step8192as the engineering follow-up candidate, not an adopted application model:43/72SEM comparisons improve,29worsen,0unmeasurable; normal36/36improve and dark29/36worsen. All4candidates worsen all16fully-neural dark objects. All24final motion pairs remain Raw-consistent (max0.005946px), which is not stage accuracy. Generated-test mean improves but all6clean controls are modified. Reference definitions and physical calibration remain unqualified. Production selection is null; no extra training was launched. Full result and audit supersede stale running-only status below while retaining interruption history.

The new301,832parameter model reads only images through four shared updates. I/P use identical initializations, scenes/noise/order, optimizer and validation; their only difference is0.02weighted true-simulator observation supervision after forward. The complete768parent procedural bank passes the unchanged data screens, with512training/128development/128final-generated-test parents. Four fresh runs each use8192updates/16passes,32768planned updates total. No real/SEM/teacher answers enter training.

The initial nondeterministic resume failure remains retained. The repaired constant-translation/deterministic runtime passes exact next-update resume, actual128update learning, complete physical-context output/loss/gradient checks and the full6image/6motion-pair/two-exposure36objectSEM evaluation for Raw and a nonneutral model. All5403protected files remain unchanged. Candidate failures and global-boundary coverage are explicit.

The background runner has produced actual training updates. Current progress: Experiments/R128_SourceOnlyFullTraining/reports/TRAINING_PROGRESS.md; canonical preparation: Experiments/R128_SourceOnlyFullTraining/reports/R128_RESULTS.md. Training is running, not complete or adopted. Existing real data remain reused development, the old144confirmation is not reused or relabeled, and independent physical qualification remains open. COMBO and historicalV42roles are unchanged.

2026-09-09 follow-up: the original first run executed1393updates but its last status recorded1392; a Windows sharing violation replacing status.json stopped it at01:18Taipei. No run completed. A separately versioned operational adapter now retries transient metadata reads/writes; a real Windows lock reproduces the original failure,200concurrent writes/readers preserve whole documents, and replay1281-1284matches original learning fields exactly. Original frozen source and expected hashes are retained; recovery identity is additional, not substituted. The same four-run study resumed from checkpoint1280 at05:58Taipei. Prior failure, old progress snapshots and ledgers remain preserved; replayed calls are not new unique steps. See the canonical recovery report and live process-backed progress.

2026-09-09 17:12Taipei follow-up: first2runs are fully reconciled through8192updates, final optimizer states, all scheduled real evaluations and128final-generated-test parents/run. The third run stopped after5359updates at14:21:39with both processes absent and no new exception record. System events show the start of a Codex update and an NVIDIA event at the same second; this is temporal evidence, not unique causal proof. Original checkpoint5248 and135third-runfiles were retained. A one-off Windows-service-parented launch, outside the application job, reproduces5249-5252exactly and resumes the same unchanged frozen coordinator/trainer. It introduces no recurring schedule or model/data/loss/evaluation change. Fourth run remains queued; no final single-model selection is made yet.

### R127 completed software repairs with explicit physical limits (2026-09-08)

Experiments/R127_MeasurementPreservationRepair provides a tested image-pair CLI for8/16bit images and explicit ROI/context scope, a native SEM relative-size diagnostic and a conditional preservation controller around the unchanged R126weights. It does not introduce a newly trained model. The3GiB budget is respected; all earlier failures and historical source identities remain retained.

The native SEM audit uses original9images and36objects, obtaining optical pitch134.4284px/nativeSEM pitch431.0545px and a relative transfer factor0.3118594(+0.7306% from historical1/3.23). LegacyP pairing declares an unused3.2507variable but applies1/3.230. Resizing plus re-segmentation adds differences beyond scale; native ratio/rim-band comparisons avoid mixing those operations. The720-ray statistic and inner/rim/outer definition band are explicitly operational, not qualified material-edge truth. Under this native size definition, both Qdark models enlarge the optical size statistic on36/36objects; no model is adopted.

The motion reader keeps invalid local estimates unavailable and adds actual spatial information. A third new-parameter72case check passes with max0.015998px error and all unobservable/unrelated negatives rejected; earlier failed validation informed development and is not re-labelled unseen. Actual local128and saved-context checks support10/30and20/30pairs. Full-fieldRaw supports6/6, so all4R126final models are reconstructed on all12original full frames. All48original cores are bitwise identical. The24full-field model translations differ from corresponding full-fieldRaw estimates by at most0.000511px. This is dominant-image-translation consistency, not independently measured stage error, individual-ROI accuracy or complete301frame validation. R126's old local phase numbers remain historical outputs; their large jumps no longer support a claim of a comparable whole-image movement.

The preservation controller returns exact native input only for known procedural unit-identity optics, gain1,bias0 and actual sensor noise0.6identity parents and100arbitrary inputs pass exactly; noisy identity and noiseless blur still execute unchanged reconstruction and improve the tested errors. Unknown real inputs remain unqualified. An identical-observation counterexample establishes why image-only universal clean detection cannot be asserted from this evidence. No weights were updated. A profile-definition probe also shows Qdark30%crossings move outward while70%crossings move inward: transition-shape changes must not be mistaken for a unique material-edge improvement.

Independent audit recomputes correlation algebra, native scale/band arithmetic,24full-field differences and all48old-core parities, and verifies5,242older files unchanged. The canonical execution notes preserve failures; the acquisition plan identifies the missing physical correspondence/actual-position evidence. Availability of existing independent position records has been requested from the user. Baseline/alternates and V42's historical thesis role remain unchanged.

### R126 completed learnability repair and matched photometry experiment (2026-09-08)

The latest learned research checkpoints are the four `Experiments/R126_LearnabilityPhotometry/runs/photo_{P|Q}_s{1265001|1265002}/step0128.pth` artifacts. None is adopted. Six fixed-example controls establish a causal update-scale effect under a single known generated geometry: changing only1e-4 to1e-3 improves native error reductions from9.84/7.21percent(A/B full) to38.13/61.17percent. The numerical derivative sweep, original inadequate runs and first launcher failure are retained. This does not establish an optimal general learning rate or unseen performance.

The separately frozen P/Q study compares original and expanded photometry on the same64 procedural parents, two presentations each, with identical geometry/optics/motion and matched sensor-noise draws. Both use the unchanged R125 B architecture, fixed geometry parameters, same full non-geometry objectives and two matched starts. All256 treatment conditions(512views) pass unchanged data-fit screens; independent8x replay agrees within0.00000844gray. Q reduces common dark simulation-reference MAE18–19percent relative to P, but introduces about0.391gray error on an originally exact clean input versus0.129for P. Data coverage helps, but does not ensure preservation or real physical applicability.

All four initial real evaluations precede photometry training, and all four final checkpoints use the same reused real panel. The1152common-population SEM rows show improvement under globally pitch-matched references, while historical dark-reference comparisons reverse the Q/P conclusion. The48motion records preserve weak/negative responses and new Q Raw-relative jumps36.83–36.94px. Independent phase-surface reconstruction identifies maximum-selection changes; neither the old12px nor new37px differences are treated as known stage movement. Qualified SEM/optical correspondence, reliable displacement readouts and preservation mechanisms remain next requirements. No fullACM, full301-frame evaluation, new physical confirmation or model promotion.

Execution audit verifies1280updates(768fixed plus512photometry),256independent actual-input rebuilds,144real float outputs and3431unchanged older files including132original R119 controls. Learned strict-FP32 tile tests pass on two real windows. The initial learned real trace fails a cross-runtime comparison and is preserved; a four-setting diagnosis identifies the evaluator's deterministic/default-TF32 setup, and a separate same-runtime trace reproduces the saved image exactly without changing weights, images, expectations or tolerance. This distinction is explicit in `reports/R126_EXECUTION_NOTES.md`. Detailed scientific outcome and final verification remain separate.

### R125 completed data repair and bounded exploratory learning (2026-09-08)

R125's learned research artifacts are under `Experiments/R125_DataAlignedPilot/runs/{A|B|C}_s{1235001|1235002}/checkpoints/step0064.pth`. These are six exploratory checkpoints, not adopted models. The first generated package remains rejected:2xwithin-cell information loss exceeded predefined model-fit screens in three cases, and one Float32geometry cell was inconsistent with independent precision replay. The repaired package preserves all64physical conditions, uses8xFloat64 observations and4xlatent targets, and passes all128cores under the same limits. The network preserves4xoptical degrees of freedom while its neural prior remains2x. Exact original kernels are retained beside bounded factorized computation; context reduction is independently checked against full640input with the same128supervised core.

The full actual matrix is64updates x3arms x2starts, not the proposed512-scene/1024-update R123 comparison. Per-step source/profile/target-use ledgers and checkpoints were independently reconciled:384updates,64identical inputs/orders perrun,21/22/26changedparameter tensors forA/B/C, intended fixed modules unchanged. All12initial/final real evaluations are complete. The fixed SEM half-readout shows A normal-exposure improvement but dark-exposure regression; B/C do not show reliable benefit. Real phase-matching discrepancies/low responses are preserved and not called true stage motion. Existing real sources remain reused development; no fullACM, full301-frame evaluation, qualified physical mapping or new confirmation claim was made.

Post-pilot source diagnostics show training target levels/contrast do not cover either SEM exposure's Raw plateau envelope; dark real contrast is20gray versus training94–163gray. This is not proof that photometry alone caused failure. A fixed-six training-reference check also lacks clear image-error reduction. Decision: no adopted model or long training; next work addresses learnability and real coverage/calibration. See `reports/R125_DATA_FIT.md`, executed notebook `reports/R125_DATA_FIT.ipynb`, reader `reports/R125_REPORT.html` and `results/final_verification.json` within R125. Original failures, old protected evidence and the consumed confirmation state remain unchanged.

### R124 implemented prototype and completed mechanical verification (2026-09-08)

The current executable prototype is `Experiments/R124_RealFirstPrototype`, implementing R123's full2D iterative direction. `README.md` documents single-file/folder CLI and Python usage. Only diagnostic identity/assumed Gaussian observations are admitted; a qualified-calibration string is rejected because instrument admission is not implemented. Geometry cannot overwrite the image, and scale proxies are not calibrated uncertainty. There is no trained model or optimizer update; nonzero-prior test states are unsaved stress fixtures.

All26 behavior/operator/artifact tests pass. Actual paired640-native-pixel forward/backward fits on the A6000 at22.57GiB allocated peak; tile parity is established for the exact tested computation, not arbitrary future support or nonlinear optics. Untrained actual outputs were passed through fixed SEM-linked half-contrast readings for exposures13/24, all36 pillars under two references. Raw replay is exact; Gaussian assumptions slightly increase observed distance. Original denominator-floor sensitivity and an unjustified monotonic sampling assertion were preserved and diagnosed without editing old expectations. The prototype's half-readout connection is not complete ACM or full301-frame motion evaluation. Next work is the source-independent scientific data/loss/ledger pipeline, qualified observation/readout semantics and bounded learning with immediate real-first evaluation; R124 mechanical completion does not promote that work to done.

### R123 real-first model and data design (2026-09-08)

The user's updated priority is real microscopy and SEM comparison from the first short candidate, including real full-field motion, corners, lines, gaps and defects. R73/R74 are synthetic diagnostics, not real-acquisition primary evidence. The selected architecture proposal uses a full 2D optical-intensity state, four shared learned updates and explicit qualified observation corrections, with no unchecked final detail patch. Geometry and uncertainty remain externally audited; internal geometry cannot substitute for measurements from the actual output image. The prototype is not implemented. Design verification includes source/ROI inventory, historical real-score replay and limited observation-operator arithmetic, not new model performance.

Read `Experiments/R123_RealFirstModelDesign/reports/R123_RESULTS.md` for completed scope. Training data initially mean new independent generated scenes, not the current real development sources or their SEM answers. New real training acquisitions are an extension not yet admitted. All short model variants use the same visible real development panel; the proposed final 1024-update point is the main comparison. Unset application tolerances allow exploration only, not automatic long training. Qualified calibration and image/SEM correspondence are needed before physical accuracy claims; 364 existing optical files and 144 full-field ROIs are not independent new samples. R123's 144 ROIs are unrelated to the consumed old 144-scene confirmation.

### R122 verified principles and corrected V42 evidence scope (2026-09-08)

Read `Experiments/R122_OperatorPrinciples/reports/R122_RESULTS.md` for executed diagnostics and `reports/MODEL_DESIGN.md` in that experiment for the next design contract. V42 retains its identity as the model used for historical thesis results; those reused motion/static samples must not be described as independent unseen evidence. Normal supervised labels are legitimate; source reuse across an independence claim is the issue. The audit binds current E120, its actual split, original loader construction and source pixel/SEM-answer lineage. It does not reconstruct every historical batch or every ancestor teacher run.

R122 preserves the negative sampled-renderer results and initial binary-raster failure. Area-integrating v2 resolves the simulator's artificial motion error, but the simple straight-edge estimator still fails 119 absolute-position and 47 motion cases of 360. This is evidence about assumptions and limits, not an adopted model. Continuous 1D oracle operation is verified; predicting the parameters, handling 2D geometry/texture/tiles, calibrating optics and demonstrating independent real usefulness remain work to do. Raw and independently generated known truth are the primary next references. No further neural training or confirmation evaluation happened in R122. The 144-scene confirmation remains consumed.

### R109/R119 readout and operator comparison (2026-09-07)

The new frozen comparison under R119 `analysis/R109_comparison_20260907` uses the same Raw-derived integer alignment for ACM, half-contrast and steepest-edge readouts, retaining legacy alignment separately for parity. Under both SEM references, R109 wins against Raw on ACM for all 36 pillar medians but loses on half-contrast for all 36; this is not an alignment or single-scale artifact. R119 loses to R109 on both reliable comparisons. Primary steepest-edge Raw coverage is inadequate; a predeclared smoother sensitivity and separately labeled model-only population do not substitute for the three-way comparison.

Within each frozen model, removing the R119 position path improves ACM and midpoint error in every exposure median, while removing R109 position generally worsens them. These path effects are not pure translation: real and clean synthetic tests show position fields also compress edge transitions, with a larger effect in R119. This invalidates interpreting a position-path switch as a pure displacement experiment, not the stored numerical observations. R109 is a comparison model, not physical ground truth. The next operation design must separate profile translation from width compression and keep readout definitions explicit before additional training. All 132 protected inputs are unchanged. Existing R119 causal corrections, consumed confirmation and R121 negative outcome remain in force.

### R121 complete bounded comparison, not adopted (2026-09-06)

The four-arm experiment is `Experiments/R121_BoundaryAnchorFactorial`; valid results use `config/protocol_v2.json` and `results/matrix_finished_v2.json`. Eight valid runs completed 12 epochs and 768 updates each, with 24 checked checkpoints and one common validation bank. C v1 was interrupted after an independent fixture showed pure-width/position confounding; it is excluded, its records retained, and its unaffected A/B controls were reused only after exact loss/gradient parity checks. Valid C/D use symmetric reference-centered profiles.

SEM reference replay recovered all 36 original masks exactly. Fixed historical scaling leaves SEM pitch 0.623%-1.099% below optical pitch; a separate global factor 1.009233335 was determined from center spacing before evaluating new candidates. It explains part of the shared size bias but does not rescue B/C/D: all three lose to A for every pillar's across-exposure median under both references and both seeds. All 7,776 shape measurements were independently recomputed. The new position factor improves simple synthetic boundary scores but degrades true-reference texture error and real SEM contours in this twelve-epoch budget. No intervention meets the predeclared combined gate, so conditional real LSC and long training are not triggered. The underlying universal-model goal is not claimed solved; COMBO, V42 and existing research roles are unchanged. The canonical report is `reports/R121_RESULTS.md` within R121.

### R119 controlled blur, radiometry and motion decision (2026-09-06)

The controlled study under `Experiments/R119_SequenceGeometryValidation/analysis/controlled_boundary_factors_20260906` separates blur, gain and true object translation before sensor integration. The three simple geometries pass the declared readout calibration; all 340 synthetic cases retain 720 common-valid profiles for seven output paths. Standard blurred circles benefit from outward correction, whereas existing real Raw profiles already lie outward relative to the current SEM digital reference. This is a data/reference discrepancy to resolve, not proof that a fixed inward offset or new loss weight is correct. The independent-level follow-up exposes brightness/contrast dependence but does not fully reproduce real expansion. The chosen priority is the optical/SEM reference contract and independently varied intensity/contrast coverage; no architecture change, training, confirmation access or promotion occurred. See `reports/R119_CONTROLLED_BOUNDARY_FACTORS.md` within R119 for preserved initial calibration failures, revised geometry-only readout calibration, invalid-profile counts and the distinction from locked ACM/LSC metrics.

### R119 training-position diagnostic extension (2026-09-06)

See `Experiments/R119_SequenceGeometryValidation/reports/R119_TRAINING_POSITION_DIAGNOSIS.md` and its `analysis/training_position_diagnosis_20260906` data. Four known-answer cases show that center/pair consistency misses common dilation while local image/edge losses penalize it; equal-output position/detail compensation is not identified by the current objective. These are operator counterexamples, not proof of learned historical compensation. Fixed synthetic tests and real SEM operator-field measurements further narrow the question to necessary versus unnecessary displacement under different imaging conditions. No complete training root cause, new model, or universal solution is claimed. Earlier cross-exposure and causal-audit corrections remain valid.

### R119 cross-exposure diagnostic extension (2026-09-06)

The fixed-E42 position-path diagnosis now covers 36 pillars in all 12 existing SEM-linked exposures. See `Experiments/R119_SequenceGeometryValidation/reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md` and `analysis/sem_position_audit_20260906` within that experiment. Full / position-off / Raw pooled median contour errors are 0.66176 / 0.58756 / 0.57419 percent of pitch. The within-pillar paired median effect is -0.07691 pitch-percentage-points; a pillar-level bootstrap gives [-0.07976, -0.07112] within this sample only. There is one adverse full-vs-position-off observation (exposure 22, pillar 6). The exact additive detail is retained but output texture changes, so no lossless-detail claim is made. This diagnoses a harmful contribution of the existing position path; it does not justify globally disabling position correction or starting a long training run. Earlier causal corrections and consumed-confirmation status remain in force. All old scientific evidence and receipts are preserved.

### R119 research correction (2026-09-06)

The canonical causal review is `Experiments/R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md`, with reproducible diagnostics under that experiment's `analysis/causal_audit_20260905`. It supersedes the earlier coherent-sequence success explanation and the approximately 0.9-pixel confirmation position error. The actual checkpoint and locked ACM/SEM/LSC observations are retained; training/data/weights were not changed by the review. Further design should first restore the intended physical observation and fair-control contracts, then verify local boundary motion independently of width/detail. COMBO production roles are unchanged.

## 1. Current Formal Baseline / 目前正式 baseline

目前正式 baseline：**COMBO / `r38v2_8px_gate_p95`**
The formal production baseline is now **COMBO / `r38v2_8px_gate_p95`**.

升級生效日期 / Promotion effective date：**2026-04-08**

| 指標 | COMBO |
|------|-------|
| external `8px step std` | `0.154515` |
| external `0.8px step std` | `0.131560` |
| external `0.08px step std` | `0.099891` |
| `0.8px` lag-1 autocorr | `-0.5176` |
| edge steepness vs R30 | `+89.4%` |
| contrast std vs R30 | `-6.6%` |
| gradient magnitude vs R30 | `-19.7%` |
| residual std (`0.8px` inner) | `2.044` |

正式入口 / Formal entry points：

- checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\weights\best_tradeoff.pth.tar`
- promoted baseline report:
  `D:\GMM_2_Final\Experiments\R38v2SeqFixed\reports\COMBO_RESULTS.md`
- complete series context:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`
- machine-readable truth:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`

COMBO 之所以被升級，不是因為它在單一 GMF 指標上最極端，而是因為它在 `0.8px` 主戰場、`8px` 宏觀守門、視覺 steepness、以及 residual_std 四個面向同時最均衡。
COMBO was promoted not because it is the most extreme on any single metric, but because it best balances the `0.8px` battlefield, the `8px` guard, visual steepness, and residual quality.

### Former Baseline / 前任 baseline

前任正式 baseline：**Round30 / `r30_b1_dironly`**
Former formal baseline: **Round30 / `r30_b1_dironly`**.

| 指標 | R30 former baseline |
|------|---------------------|
| external `8px step std` | `0.205193` |
| external `0.8px step std` | `0.167862` |
| external `0.08px step std` | `0.157720` |
| `0.8px` lag-1 autocorr | `0.267027` |

## 2. Approved Alternates / 已核准特化候選

### R33 / r33_robust_p95 — GMF Extreme Alternate

一句話定位：**GMF 極致型特化候選；不是正式 baseline。**
One-line role: **GMF-extreme approved alternate; not the formal baseline.**

| 指標 | R33 |
|------|-----|
| external `8px step std` | `0.153343` |
| external `0.8px step std` | `0.119049` |
| external `0.08px step std` | `0.086274` |
| `0.8px` lag-1 autocorr | `-0.5549` |
| edge steepness vs R30 | `-22%` |

適用場景 / Recommended use：
- 以 GMF 幾何精度為唯一主目標
- 可以接受視覺邊界更柔

正式入口 / Formal entry points：
- report:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\R33_EXPERIMENT_SUMMARY.md`
- checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260405_091941\weights\best_tradeoff.pth.tar`

### R38v2 / r38v2_8px_gate — Visual Priority Alternate

一句話定位：**視覺優先型特化候選；不是正式 baseline。**
One-line role: **visual-priority approved alternate; not the formal baseline.**

| 指標 | R38v2 |
|------|-------|
| external `8px step std` | `0.143988` |
| external `0.8px step std` | `0.134205` |
| external `0.08px step std` | `0.106457` |
| `0.8px` lag-1 autocorr | `-0.5459` |
| edge steepness vs R30 | `+89.4%` |

適用場景 / Recommended use：
- 需要外部 GMF 改善，同時維持接近 R30 的視覺銳度
- 視覺品質比極致 GMF 更重要

正式入口 / Formal entry points：
- report:
  `D:\GMM_2_Final\Experiments\R38v2SeqFixed\reports\R38v2_RESULTS.md`
- checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260406_235957\weights\best_tradeoff.pth.tar`

### R39R40_avg_a025 / r39r40_complementary_avg_a025 — Balanced Full-Spectrum Alternate

一句話定位：**全方位平衡替代候選；外部 GMF 三尺度都在 3% 內，顯微/形狀能力全勝 COMBO 與 a030；不是正式 baseline。**

升級生效日期 / Promotion effective date：**2026-05-11**

| 指標 | R39R40_avg_a025 |
|------|-----------------|
| external `8px step std` | `0.146505` |
| external `0.8px step std` | `0.133546` |
| external `0.08px step std` | `0.100400` |
| external 8px Δ vs COMBO | `−5.18%` |
| external 0.8px Δ vs COMBO | `+1.51%` |
| external 0.08px Δ vs COMBO | `+0.51%` |
| external verdict | **`PASS_UPGRADE_GUARD`**（三尺度都過 3% 升級上限）|
| R40 micro 整體 PSNR | `25.4091`（+2.68 dB vs COMBO，5 類全勝）|
| R39 shape 整體 PSNR | `25.5098`（+2.67 dB vs COMBO，7 類全勝）|
| edge steepness vs R30（推算） | `+78.1%`（sharp band）|

導生方式 / Derivation：

R39 a030（COMBO ↔ R39_strong α=0.30 權重平均）與 R40 a043（COMBO ↔ R40 micro_capacity_combo α=0.43 權重平均）兩個 checkpoint，在 α=0.25 做跨輪線性插值（75% a030 + 25% a043）。

適用場景 / Recommended use：
- 需要外部 GMF 三尺度都接近 COMBO，又要比 COMBO 更強的形狀泛化與顯微特徵能力的部署
- 不需要單一尺度極致優化（用 R33）也不需要極致視覺銳度（用 R38v2）時的預設替代
- 為「balanced full-spectrum」這個之前空缺的特化位置

升級依據 / Promotion basis（四項驗證 2026-05-11 通過）：
1. 外部 GMF 三尺度都過 3% 升級上限（首個專案候選做到）
2. R40 micro_val_unseen 5 類顯微結構 PSNR 全勝 COMBO 與 a030（+0.20 到 +0.47 dB vs a030）
3. R39 shape_val_unseen 7 類純幾何形狀 PSNR 全勝 COMBO 與 a030（+0.37 到 +0.61 dB vs a030）
4. 視覺 edge_steepness vs R30 約 +78.1%，與 a030（+78.8%）跟 a043（+79.2%）幾乎一致，落在 COMBO/R38v2 同一個 sharp band，遠優於 R33 soft band（−22%）

正式入口 / Formal entry points：
- promotion report:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\reports\R39R40_AVG_a025_CAPABILITY_EVAL.md`
- sweep results:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\reports\R39R40_COMPLEMENTARY_AVG_RESULTS.md`
- external GMF compare:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\reports\R39R40_AVG_a025_EXTERNAL_COMPARE.md`
- checkpoint:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\checkpoints\a025\best_tradeoff.pth.tar`
- 視覺對比 sheet（R40 micro 5 聯 / R39 shape 5 聯）:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\visuals\contact_sheet_a025_micro_five_panel.png`
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\visuals\contact_sheet_a025_shape_five_panel.png`

## 3. Current Promoted State / 目前正式狀態

目前 mainline 狀態是 / The current mainline state is：

- **formal production baseline 已升級為 COMBO**
- `R33`、`R38v2` 與 `R39R40_avg_a025`（2026-05-11 升）為 approved alternates；前兩者是特化位置（GMF 極致 / 視覺優先），a025 是 balanced full-spectrum 位置
- **目前沒有開放中的 baseline challenger**
- `R39_ShapeGeneralization` 的 `r39_combo_strong_avg_a030` 仍為 alternate-grade pending（用作 a025 sweep 端點，本身未獨立升級）
- `R40_MicroscopyFeatureCoverage` 已完成訓練、本地評估、外部 GMF：顯微特徵重建變好，但 8px 外部守門退步；不升級
- `R41_RingDistillation` 已完成設施、訓練、本地評估與權重混合掃描：顯微特徵能力成立，但沒有任何混合點同時守住 microscopy 與 local ring guard；不送外部 GMF
- `R42_MicroscopyBoundaryFidelity` 已完成正式訓練、本地分析、低比例權重平均、守門 KD 診斷與外部 GMF 補測：通用顯微邊界能力明顯提升，但外部補測確認退步過大；不升級，也不建議作量測替代
- `R43_CandidateUsabilityAudit` 已完成 analysis-only 盤點：沒有新候選可全面取代 COMBO；`R39 a030` 最接近正式替代討論，`R42` full endpoints 可作顯微邊界研究/人工檢查候選
- `R44_UniversalBoundaryMotionFidelity` 已完成 R44A 診斷、R44B 三候選訓練、R44C 三個短探針、R44D 分族診斷、R44E 專項探針、R44F 錯誤解剖、R44G 邊界形狀體檢、R44H Step A 家族平均探測與 Step B 局部老師蒸餾：通用位移忠實度有進展，但仍未找到可直接堪用或可升級的平衡模型；研究成功但不可升級
- `R45_FamilyBoundaryAdapter` 已完成 R45A 單一入口小模組驗證與 R45B 老師殘差診斷：輸出端小校正可守住位移但沒有改善大區塊/混合場景；能力分散有 oracle 上限，但老師優勢不乾淨，不能直接拿來輸出端蒸餾
- `LabSystem_MOSR / R51_BlurSourceProbe` 是論文 Lab-system blur-source 小訓練探針：Gaussian、weak-BADS alpha `0.50`、mixed-PSF 三組短訓練與 real `20250605_checkboard` 重建/角點驗證皆完成。最佳 R51 是 mixed-PSF `best_tradeoff`，median corner shift `2.828 px`，優於 Lab R40 control `4.243 px`，但 large-shift corner rate `36.872%` 仍差於 R40 的 `24.581%`；方向有幫助但不可升級，下一步需加入真實角點穩定守門
- `LabSystem_MOSR / R52_CornerStabilityGuard` 是論文 Lab-system formal long run：R52 以 R51 mixed-PSF `best_tradeoff` 為起點，加入 4000-pair corner-stability training data 與 geometry sidecars，完成 100 epochs、真實 `20250605_checkboard` 重建與角點驗證。最佳 R52 是 epoch-100 `latest`，median corner shift `3.606 px` 優於 Lab R40 control `4.243 px`，但 large-shift corner rate `30.447%` 仍差於 R40 的 `24.581%`；R52 failed real-corner gate，不升級，不當 Lab baseline
- `LabSystem_MOSR / R53_RealisticDatasetCalibration` 是論文 Lab-system realistic-data formal round：R53 以 6000-pair main-project-like Lab training mix 從頭訓練 100 epochs，內部驗證到 epoch 100 仍改善（`PSNR 26.39` / `SSIM 0.9353`），但真實 `20250605_checkboard` 重建與角點驗證失敗。R53 `best_tradeoff` median corner shift `3.606 px`，但 large-shift corner rate `40.782%` 差於 Lab R40 的 `24.581%`；R53 `latest` 更退到 median `9.220 px` / `58.939%` large-shift corners。R53 不升級，不當 Lab baseline
- `LabSystem_MOSR / R54_GeometryRootCauseProbe` 是論文 Lab-system root-cause diagnostic + masked small-overfit probe：R54 先確認重建本身正在傷害真實角點（raw input >5 px 角點 `1.676%`，Lab R40 `24.581%`，R53 latest `58.939%`），再用 20260613 strict-rectangle CAD GT 做 edge-band masked small-overfit。小探針能成功貼近 CAD 監督（inside MAE input `61.145` -> R54 epoch20 `9.268`），但套到真實 `20250605_checkboard` 失敗：R54 epoch20 median corner shift `9.220 px`、>5 px `60.056%`，比 Lab R40 `4.243 px` / `24.581%` 更差。R54 證明問題不是「模型完全學不動 CAD 邊」，而是小範圍 CAD 適應會造成真實影像輸出漂移；不可作 Lab baseline
- `LabSystem_MOSR / R56_LabelCoreRepairTraining` 是論文 Lab-system label-core repair follow-up：R56 使用 R53/R55 source-style 6000-pair package 的 label-core 修復版本，完成 50 epoch scratch training，內部驗證到 epoch 50 仍改善（`PSNR 26.40` / `SSIM 0.9333`），但真實 `20250605_checkboard` 角點驗證失敗。R56 `best_tradeoff` median corner shift `2.828 px` 與 R55 best 相同，但 tail shift `9.899 px` 與 >5 px corners `26.816%` 都比 R55 best 的 `3.606 px` / `21.788%` 更差；R56 `latest` 更退到 median `9.899 px` / `59.777%` >5 px corners。R56 不採用，不送外部 GMF；R55 best 仍是目前較好的 Lab 候選
- `LabSystem_MOSR / R50_PSFControlDiagnosis` 是論文 Lab-system PSF/degradation 診斷：real Lab checkboard edge-width proxy 是 `7.0 px`，formal BADS 是 `11.0 px`，Gaussian 是 `9.0 px`，weak-BADS alpha `0.50` 是 `7.0 px`；結論是 BADS PSF 可用但不適合作為唯一 checkboard-corner blur truth，並已導向 R51 Gaussian / weak-BADS / mixed-PSF 小訓練探針
- `LabSystem_MOSR / R49_CADAnchorRealGeometry` 是論文 Lab-system replication side track：R49 CAD-anchor data/geometry packages, formal 100-epoch training, real Lab checkboard reconstruction, and real-corner validation are complete; validation failed (best R49 median corner shift `9.000 px` vs Lab R40 control `4.243 px`), so it remains negative method-transfer evidence and not a main-project baseline challenger. Full history is hash-verified on H; D keeps canonical context and restore instructions
- `LabSystem_MOSR / R48_RealCornerTransfer` 是論文 Lab-system replication side track：R48 data/geometry packages, formal 200-epoch training, real Lab checkboard reconstruction, and real-corner validation are complete; validation failed, so it remains negative method-transfer evidence and not a main-project baseline challenger
- `Round31` 已關閉，`Round32` 已關閉
- `R26NewPSFCheck` 仍保留為 **open side track**，但不是 active mainline

### R39 Shape Generalization

一句話 verdict：**訓練端點不升級；`r39_combo_strong_avg_a030`（COMBO ↔ R39_strong 權重平均，alpha=0.30）external GMF 通過 PASS_TRADEOFF（兩個尺度改善、0.8px 退 6.42% 在 R38v2 alternate 退步幅度內），達 alternate-grade，等專案決策是否正式升級為 approved alternate。**
One-line verdict: **trained endpoints not promotable; `r39_combo_strong_avg_a030` (COMBO ↔ R39_strong weight average at alpha=0.30) cleared external GMF as PASS_TRADEOFF (two scales improved, 0.8px regressed within the R38v2 alternate band). Alternate-grade; awaiting project-owner promotion decision.**

核心數字 / Core numbers（local + external GMF / Local + external GMF）：

| candidate | held-out shape PSNR | local 8px | local 0.8px | local 0.08px | external 8px | external 0.8px | external 0.08px |
|------|---:|---:|---:|---:|---:|---:|---:|
| COMBO | `22.8411` | `0.1389` | `0.1509` | `0.1185` | `0.154515` | `0.131560` | `0.099891` |
| `r39_shape_mix_safe` | `26.6799` | `0.3693` | `0.1811` | `0.1338` | — | — | — |
| `r39_shape_mix_strong` | `30.0722` | `0.2004` | `0.1691` | `0.1750` | — | — | — |
| **`r39_combo_strong_avg_a030`** | **`25.0326`** | **`0.1384`** | **`0.1507`** | **`0.1114`** | **`0.143794`** | **`0.140008`** | **`0.083941`** |

External GMF verdict（a030 vs COMBO，方法論：raw step_std，0 outliers removed）：

| scale | a030 | COMBO | delta % | 狀態 |
|---|---:|---:|---:|:---:|
| 8px | `0.143794` | `0.154515` | **−6.94%** | IMPROVED |
| 0.8px | `0.140008` | `0.131560` | +6.42% | TRADEOFF_OK（< 7% alternate cap） |
| 0.08px | `0.083941` | `0.099891` | **−15.97%** | IMPROVED（**專案歷史最低**） |

跨 alternate ranking：
- 8px:`a030 (0.1438)` ≈ `R38v2 (0.1440)` < R33 < COMBO（a030 與 R38v2 統計上並列頭部）
- 0.8px:R33 < COMBO < R38v2 < `a030`（a030 是最差,但仍優於 former baseline R30 0.168）
- 0.08px:`a030 (0.0839)` < R33 (0.0863) < COMBO < R38v2(**a030 為專案歷史最低**)

Visual profile（a030 vs COMBO,frame-wise mean over 203 ring BMP）：
- gradient_magnitude_mean −2.97%
- **edge_steepness_p95 −5.64%**(主指標)
- contrast_std −2.00%
- edge_contrast_p99_minus_p1 −2.64%

a030 屬 sharp band（接近 COMBO / R38v2,推算對 R30 約 +78.8% edge_steepness）,**不在 R33 的 soft band（R33 對 R30 −22% edge_steepness）**。視覺沒有崩壞,只輕微妥協。

正式入口 / Formal entry points：

- experiment results:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\reports\R39_RESULTS.md`
- external GMF compare:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\reports\R39_EXTERNAL_COMPARE.md`
- weight sweep summary + plot:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\weight_sweep\sweep_summary.md`
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\weight_sweep\sweep_tradeoff.png`
- representative visual sheet:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\shape_recon\r39_representative_shape_sheet.png`
- averaged checkpoint:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\weight_sweep\checkpoints\a030\best_tradeoff.pth.tar`
- external GMF score files:
  `D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\external_gmf_a030\pitch{8px,0p8px,0p08px}\GMF_score.txt`

a030 在 ESTIMATOR_POLICY.json 的位置：`open_side_tracks[].candidate_id = "R39_a030"`，狀態 `external_gmf_complete_alternate_grade_pending_promotion`。
未升級進 `approved_alternates` 之前，COMBO 仍是唯一正式 baseline，R33 / R38v2 仍是現有 approved alternates；a030 是 alternate-grade 但等專案決策。

R39 收尾 finding：a030 在訓練分布內(ring + 簡單幾何形狀)是 alternate-grade，但合成的「IC + grid + 紋理」這類訓練分布外顯微內容,a030 跟 COMBO 都重建不好(grid 完全消失、紋理被當雜訊濾掉)。雜訊調輕後重建幾乎沒變,證實限制是訓練分布而非雜訊或 PSF。詳見 `Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md` 的 "Synthetic Microscopy Demo" 段落。R40 已沿著這個 finding 擴大顯微特徵訓練覆蓋，證明能力可被推高，但外部 8px 守門未守住。

### R43 Candidate Usability Audit

一句話 verdict：**R43A 是 analysis-only 堪用性盤點，不是訓練輪次；結論是沒有近期候選可全面取代 COMBO，但 R39 a030 是最值得進入正式替代討論的候選，R42 full endpoints 是最值得保留的顯微邊界研究/人工檢查候選。**

核心產物：

- 報告：`D:\GMM_2_Final\Experiments\R43_CandidateUsabilityAudit\reports\R43A_USABILITY_AUDIT.md`
- 分數表：`D:\GMM_2_Final\Experiments\R43_CandidateUsabilityAudit\results\candidate_usability\usability_scorecard.json`
- CSV：`D:\GMM_2_Final\Experiments\R43_CandidateUsabilityAudit\results\candidate_usability\usability_scorecard.csv`
- 肉眼檢查圖：
  - `D:\GMM_2_Final\Experiments\R43_CandidateUsabilityAudit\results\visual_review\micro_feature_visual_sheet.png`
  - `D:\GMM_2_Final\Experiments\R43_CandidateUsabilityAudit\results\visual_review\boundary_feature_visual_sheet.png`
  - `D:\GMM_2_Final\Experiments\R43_CandidateUsabilityAudit\results\visual_review\boundary_zoom_visual_sheet.png`

重點結論：
- `R39 a030`：外部 GMF PASS_TRADEOFF，形狀泛化明顯改善，是近期最接近「堪用替代候選」的結果。
- `R42` full endpoints：顯微邊界、格線、缺陷重建能力強，但本地環形守門與後補外部 GMF 都失敗，不適合正式量測替代。
- R40/R41：證明顯微細節能力可被學到，但更適合作為能力來源，不適合部署。
- R42 low-alpha：守住舊能力時，新能力幾乎沒有帶回來，暫時不值得使用。

### R45 Family Boundary Adapter

一句話 verdict：**R45A 輸出端小校正沒有比 R44B from R42 更好；R45B 確認能力分散存在，但老師優勢不乾淨，不能直接拿來輸出端蒸餾。**

R45 的目標不是啟動多個完整模型，而是測試「單一入口 + 內部小校正模組」是否能把 R44 後分散的能力收回來。

本輪設計：

- 主模型：R44B from R42，保持凍結。
- 小模組：只在 `large_regions` 與 `mixed_fields` 啟動。
- 訓練資料：R44 motion train 的 stage 45/47，共 960 對。
- 驗證資料：R44 motion_val_unseen 七類全部，共 980 張、840 對位移比較。

R44B from R42 基準：

| 指標 | R44B from R42 |
|---|---:|
| 大區塊/混合合併形狀錯誤 | `0.338390` |
| 整體位移誤差 | `0.381330 px` |

R45 縮放掃描：

| 版本 | 校正強度 | 目標形狀錯誤 | 相對 R44B 形狀變化 | 整體位移誤差 | 判定 |
|---|---:|---:|---:|---:|---|
| `r45_oracle_adapter_large_mixed_s04` | 0.04 | `0.341758` | `-0.995%` | `0.381437` | FAIL |
| `r45_oracle_adapter_large_mixed_s08` | 0.08 | `0.340286` | `-0.560%` | `0.381685` | FAIL |
| `r45_oracle_adapter_large_mixed_s12` | 0.12 | `0.344523` | `-1.813%` | `0.381704` | FAIL |
| `r45_oracle_adapter_large_mixed` | 0.18 | `0.349675` | `-3.335%` | `0.382155` | FAIL |

關鍵解讀：

- 小模組沒有破壞非目標類型，位移也幾乎守住。
- 但目標形狀沒有變好；最佳 s08 只讓大區塊微幅改善，卻讓混合場景變差，合併後仍輸給 R44B。
- 因此問題不是「多模型入口」本身，而是輸出端小校正太晚、太弱，修不到模型內部形成邊界的能力。

正式入口 / Canonical files：

- 實驗根目錄：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter`
- 主結果報告：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\reports\R45_RESULTS.md`
- 縮放掃描總表：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\results\diagnostics\r45_adapter_scale_sweep_summary.csv`
- 代表圖：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\results\visual_samples\r45_s08_vs_r44b_target_compare.png`

下一步判斷：

- 不建議繼續調輸出端小校正。
- 不建議用全圖蒸餾或直接老師輸出當答案。
- 若仍要維持單一入口，下一步應改成中間特徵層小分支，並且加入局部選擇器，只在老師確實優於 R44B 的區域啟動。

R45B 診斷結果：

| 診斷 | 形狀錯誤 | 相對 R44B 改善 |
|---|---:|---:|
| R44B from R42 | `0.3384` | `0.00%` |
| 固定分族 oracle | `0.2968` | `12.30%` |
| 逐張 oracle | `0.2253` | `33.42%` |

固定分族 oracle：

| 結構類型 | 最佳固定模型 | 平均形狀錯誤 |
|---|---|---:|
| large_regions | R44B from COMBO | `0.3755` |
| mixed_fields | R44C static heavy | `0.2181` |

老師可轉移性判斷：

- `R44B from R40` 與 `R41 direct` 形狀分數好，但位移退步過大，且邊界像素殘差方向不穩。
- `R44B from COMBO` 與 `R44C static heavy` 有局部參考價值，但不適合直接全圖或輸出端蒸餾。
- `R44H StepB region KD` 的殘差方向最接近穩定，但形狀能力不足。

R45B 正式入口：

- 診斷報告：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\reports\R45B_TEACHER_DIAGNOSTICS.md`
- oracle 總結：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\results\r45b_teacher_diagnostics\r45b_oracle_summary.json`
- 老師殘差表：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\results\r45b_teacher_diagnostics\r45b_residual_summary.csv`
- 代表圖：`D:\GMM_2_Final\Experiments\R45_FamilyBoundaryAdapter\results\visual_samples\r45b_teacher_diagnostics_sheet.png`

### R44 Universal Boundary Motion Fidelity

一句話 verdict：**R44A-R44H Step B 已完成；R44B from R42 仍是最佳通用位移候選。R44H Step A 的全域平均會犧牲位移，Step B 的局部老師蒸餾雖守住位移但沒有救回形狀，因此不建議進 Step C 多老師全模型蒸餾。**

核心設計：

| 項目 | 內容 |
|------|------|
| R44A | 已完成診斷：COMBO、R39 a030、R40 a045、R41、R42 主要候選在已知位移顯微結構上的漂移程度 |
| R44B | 已完成訓練：三個候選各 24 epoch，分別從 R42、R40 a045、COMBO 出發 |
| R44C | 已完成短探針：三個候選各 21 epoch，檢查降低 motion、排除部分結構、加強靜態邊界是否能取得平衡 |
| R44D | 已完成診斷：不訓練，只按結構類型、位移段與模型來源拆解既有結果 |
| R44E | 已完成短探針：三個候選各 14 epoch，只針對大區塊與混合場景做修補 |
| R44F | 已完成診斷：不訓練，檢查大區塊/混合場景錯誤是否來自指標誤判或真邊界形狀問題 |
| R44G | 已完成診斷：不訓練，量化邊界厚度、破碎、直邊與角點保留 |
| R44H Step A | 已完成診斷：不訓練，檢查 R44C 老師乾淨度，並測試 R44B 家族權重平均是否能匯聚能力 |
| R44H Step B | 已完成短訓練：從 R44B from R42 出發，只在大區塊邊界帶向 R44B from COMBO 做局部老師蒸餾 |
| 位移資料 | `0 / 0.08 / 0.16 / 0.4 / 0.8 / 2 / 8 px` 的細線、格線、交叉線、曲線、大區塊、缺陷、混合場景序列 |
| 主候選 | `r44_motion_from_r42_best`、`r44_motion_from_r40_a045`、`r44_motion_from_combo`；R44C/R44E 是內部短探針，不是升級候選 |

主要結果：
- `R44B from R42` 是目前最佳通用位移候選：整體位移誤差 `0.3813 px`，優於 R42 `0.4609 px` 與 COMBO `0.8253 px`
- 格線位移誤差 `2.2457 px`，優於 R42 `2.7911 px` 與 COMBO `5.3567 px`
- 整體邊界距離沒有同步變好：R44B from R42 `3.7276 px`，略差於 R42 `3.6726 px`
- 本地三尺度環形代理退步：8px +45.1%、0.8px +46.7%、0.08px +32.3% vs COMBO
- R44C 最佳探針 `r44c_static_heavy_all_motion`：整體位移 `0.4011 px`、整體邊界 `3.7198 px`、格線位移 `2.3820 px`；比 R44B 稍微平衡，但位移優勢被拉回，大區塊仍未改善
- R44C 本地環形代理仍退步：8px +36.6%、0.8px +47.2%、0.08px +33.8% vs COMBO
- R44D 分族診斷：最佳單一邊界模型仍是 R42 best（平均 `3.6726 px`），分族上限為 `3.2038 px`，仍有 `12.77%` 空間
- R44D 確認大區塊最佳邊界來源是 R41 direct，混合場景最佳邊界來源是 R44B from R40；單一模型目前很難同時吃下所有結構
- R44D 也確認現有 `grid_phase_motion_error_px` 對所有模型幾乎相同，不能拿來排名模型
- R44E 最接近可用的 `r44e_region_mix_repair_from_r44b_r42` 幾乎保住 R44B 位移（`0.3820 px`），但大區塊退到 `7.7581 px`；另外兩個探針會讓格線與整體位移大幅退步
- R44F 壓力測試：大區塊 1px/5px 人工偏移為 `0.5335 / 2.5477`，混合場景為 `0.5673 / 2.6217`，代表指標能抓到偏移；但邊界變厚也會明顯變差
- R44G 形狀體檢：大區塊與混合場景合併最低形狀錯誤是 `R44B from R40`（`0.3110`），`R41 direct` 幾乎並列（`0.3119`）；大區塊單項最好是 `R44B from COMBO`（`0.3755`），混合場景單項最好是 `R44C static heavy`（`0.2181`）
- R44H Step 0：`R44C static heavy` 可暫作混合場景局部老師，混合場景形狀錯誤 `0.2181` 優於 R44B from R42 的 `0.2230`，相關位移最大退步 `6.07%`
- R44H Step A：四個 R44B 家族平均候選都能改善大區塊/混合形狀，最佳 `r44h_b42_bcombo_a050` 形狀錯誤 `0.2955`；但整體位移退到 `0.5298 px`，其他平均候選也退到 `0.4843-0.6277 px`
- R44H Step B：`r44h_stepb_region_kd_main` 整體位移 `0.3837 px`，幾乎守住 R44B from R42 的 `0.3813 px`；但大區塊/混合形狀錯誤從 `0.3384` 變差到 `0.3481`
- 結論：R44 證明 motion 資料能推動位移忠實度，也證明單純調權重、排除分族、大區塊/混合場景短訓練修補、把問題歸咎於指標誤判、R44B 家族全域平均、或單一老師局部蒸餾都不足；現成候選能力分散，下一步應轉向 adapter / 分族小頭 / 推論時分族選擇

正式入口：
- 實驗根目錄：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity`
- 主結果報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44_RESULTS.md`
- 資料產生器：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\scripts\r44_motion_data.py`
- 訓練啟動器：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\scripts\launch_r44.py`
- 代表圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\visual_samples\r44_motion_r42_vs_r44_contact_sheet.png`
- R44C 代表圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\visual_samples\r44c_probe_r42_r44b_r44c_sheet.png`
- 總表：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\summary\r44_motion_summary_all.csv`
- R44C 探針總表：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\summary\r44c_probe_summary.csv`
- R44D 診斷報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44D_FAMILY_DIAGNOSTIC.md`
- R44D 邊界熱圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_boundary_heatmap.png`
- R44D 位移熱圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_motion_heatmap.png`
- R44E 專項報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44E_TARGETED_PROBE.md`
- R44E 探針總表：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\summary\r44e_probe_summary.csv`
- R44E 代表圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\visual_samples\r44e_region_mixed_probe_sheet.png`
- R44F 錯誤解剖報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44F_ERROR_DIAGNOSTIC.md`
- R44F 指標壓力測試：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44f_metric_stress.csv`
- R44F 代表圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\visual_samples\r44f_error_dissection_sheet.png`
- R44G 邊界形狀報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44G_BOUNDARY_SHAPE_METRICS.md`
- R44G 邊界形狀分數表：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44g_boundary_shape_scorecard.csv`
- R44G 邊界形狀熱圖：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\visual_samples\r44g_boundary_shape_heatmap.png`
- R44H Step A 報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44H_STEPA_FAMILY_AVERAGE.md`
- R44H Step A 總表：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\r44h_family_average\r44h_stepa_summary.csv`
- R44H Step B 報告：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\reports\R44H_STEPB_REGION_KD.md`
- R44H Step B 位移摘要：`D:\GMM_2_Final\Experiments\R44_UniversalBoundaryMotionFidelity\results\r44h_stepb_region_kd\r44h_stepb_motion_summary.json`

### R40 Microscopy Feature Coverage

一句話 verdict：**R40 成功證明顯微特徵訓練資料能提高格線、紋理、缺陷等重建能力；但最佳折衷 `r40_combo_best_avg_a045` 外部 8px GMF 退步 +22.80%，所以只能列為研究結果，不升級。**
One-line verdict: **R40 proves the capacity gain from microscopy-feature coverage, but `r40_combo_best_avg_a045` regressed the 8px external GMF guard by +22.80%, so it is research-only and not promotable.**

核心數字 / Core numbers：

| candidate | held-out micro PSNR | held-out micro SSIM | high-frequency retention | local 8px | local 0.8px | local 0.08px | external 8px | external 0.8px | external 0.08px |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBO | `22.7326` | `0.8588` | `0.2234` | `0.1389` | `0.1509` | `0.1185` | `0.154515` | `0.131560` | `0.099891` |
| `r40_combo_best_avg_a045` | `26.8911` | `0.9199` | `0.3414` | `0.1510` | `0.1379` | `0.1199` | `0.189750` | `0.133314` | `0.097048` |

External GMF verdict（a045 vs COMBO，方法論：raw step_std，0 outliers removed）：

| scale | a045 | COMBO | delta % | 狀態 |
|---|---:|---:|---:|:---:|
| 8px | `0.189750` | `0.154515` | **+22.80%** | REGRESSED |
| 0.8px | `0.133314` | `0.131560` | +1.33% | TRADEOFF_OK |
| 0.08px | `0.097048` | `0.099891` | **-2.85%** | IMPROVED |

Step audit：8px `99` steps、0.8px `59` steps、0.08px `39` steps 全部納入；三個尺度 `z>5` 移除數都是 `0`。

正式入口 / Formal entry points：

- experiment results:
  `D:\GMM_2_Final\Experiments\R40_MicroscopyFeatureCoverage\reports\R40_RESULTS.md`
- external GMF compare:
  `D:\GMM_2_Final\Experiments\R40_MicroscopyFeatureCoverage\reports\R40_EXTERNAL_COMPARE.md`
- external step audit:
  `D:\GMM_2_Final\Experiments\R40_MicroscopyFeatureCoverage\results\external_gmf\step_audit\step_audit_summary.json`
- representative visual sheet:
  `D:\GMM_2_Final\Experiments\R40_MicroscopyFeatureCoverage\results\weight_sweep\combo_best_low_alpha\r40_a045_micro_comparison_sheet.png`
- averaged checkpoint:
  `D:\GMM_2_Final\Experiments\R40_MicroscopyFeatureCoverage\results\weight_sweep\combo_best_low_alpha\checkpoints\a045\best_tradeoff.pth.tar`

R40 在 ESTIMATOR_POLICY.json 的位置：`open_side_tracks[].candidate_id = "R40_a045"`，狀態 `external_gmf_complete_research_capacity_only_not_promotable`。COMBO 仍是唯一正式 baseline；R40 不進 approved alternates。

R40 收尾 finding：合成顯微特徵覆蓋有效，代表模型確實有能力學更清楚的格線、紋理、小缺陷；問題不是能力不存在，而是目前資料/訓練策略把顯微能力推高時仍會拉動既有環形能力。下一輪應保留 R40 顯微特徵資料，但用更溫和的保留策略守住 COMBO。

### R41 Ring Distillation

一句話 verdict：**R41 訓練與權重混合掃描已完成；顯微特徵能力確實保住，但沒有任何混合點同時通過 microscopy 與 local ring guard，所以 R41 是 research-only，不送外部 GMF。**
One-line verdict: **R41 training and weight sweep are complete; microscopy-feature capacity is preserved, but no averaged checkpoint passes both microscopy capacity and local ring guard, so R41 is research-only and no external GMF candidate is sent.**

核心數字 / Core numbers：

| candidate | held-out micro PSNR | held-out micro SSIM | high-frequency retention | local 8px | local 0.8px | local 0.08px | external 8px | external 0.8px | external 0.08px |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBO local reference | — | — | — | `0.1389` | `0.1509` | `0.1185` | `0.154515` | `0.131560` | `0.099891` |
| `r41_kd_from_a045` direct best | `29.4556` | `0.9513` | `0.7241` | `0.1628` | `0.1652` | `0.1543` | not sent | not sent | not sent |
| `r41_combo_avg_a045` diagnostic | `26.1840` | — | `0.3012` | `0.1577` | `0.1515` | `0.1322` | not sent | not sent | not sent |
| `r41_combo_avg_a050` diagnostic | `26.6662` | — | `0.3358` | `0.1534` | `0.1595` | `0.1475` | not sent | not sent | not sent |

R41 在 ESTIMATOR_POLICY.json 的位置：`open_side_tracks[].candidate_id = "R41_direct_best"`，狀態 `weight_sweep_complete_no_guarded_tradeoff`。COMBO 仍是正式 baseline；R41 不是 approved alternate。

R41 當前 finding：知識蒸餾加強了顯微能力保留，沒有把 R40 的顯微能力洗掉，甚至在 unseen micro validation 上高於 R40 a045。但這條路線沒有產生 ring/micro 共同通過點。低 alpha 守環形較好但顯微不夠；0.45/0.50 顯微過線但 0.8px / 0.08px 環形不過。下一輪若要繼續，應改機制，不要只沿 R41 的 teacher anchoring + weight averaging 加測。

Storage note (2026-08-01)：R41 封存前完整快照、正式訓練與專用資料共 6,075 個檔案，已透過三份 SHA-256 清單核對後保存到 `H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history`。D 槽的 `Experiments/R41_RingDistillation/ARCHIVE_POINTER.md` 保留完整恢復方式；此存放變更不改變上述研究 verdict。

### R42 Microscopy Boundary Fidelity

一句話判定：**R42 研究成功但不可升級：通用顯微邊界能力被明顯推起來，但本地三尺度環形守門與後續外部 GMF 補測都明顯退步；即使允許環形有限退步，也不建議作量測替代。**

核心結果：

| 模型 | 邊界 PSNR | 高頻保留 | 邊界距離 | 邊界 F1@1px |
|------|---:|---:|---:|---:|
| COMBO | `20.55` | `0.20` | `7.82` | `0.63` |
| R40 a045 | `23.35` | `0.51` | `6.77` | `0.72` |
| R41 直接端點 | `22.73` | `0.92` | `5.04` | `0.73` |
| `r42_combo_best` | `31.81` | `0.70` | **`3.35`** | **`0.87`** |
| `r42_combo_latest` | `34.09` | `0.75` | `3.48` | `0.87` |
| `r42_r41_best` | `32.89` | `0.75` | `3.48` | `0.87` |
| `r42_r41_latest` | **`34.18`** | **`0.80`** | `3.60` | `0.87` |

本地環形守門：

| 候選 | 8px | 0.8px | 0.08px | 判讀 |
|------|---:|---:|---:|---|
| COMBO 本地參考 | `0.1389` | `0.1509` | `0.1185` | 正式基準參考 |
| `r42_combo_best` | `9.5592` | `0.3621` | `0.6579` | 明顯崩壞 |
| `r42_combo_latest` | `0.1807` | `0.2158` | `0.2132` | 失敗 |
| `r42_r41_best` | `0.1715` | `0.2121` | `0.1673` | R42 中最好但仍失敗 |
| `r42_r41_latest` | `0.2442` | `0.2513` | `0.2154` | 失敗 |

外部 GMF 補測（2026-05-06）：

| 候選 | 8px 外部 | vs COMBO | 0.8px 外部 | vs COMBO | 0.08px 外部 | vs COMBO | 判讀 |
|------|---:|---:|---:|---:|---:|---:|------|
| `r42_r41_best` | `0.192577` | `+24.63%` | `0.255665` | `+94.33%` | `0.198651` | `+98.87%` | R42 中最好但仍退步過大 |
| `r42_combo_latest` | `0.286248` | `+85.26%` | `0.274479` | `+108.63%` | `0.251685` | `+151.96%` | 不建議使用 |
| `r42_r41_latest` | `0.279891` | `+81.14%` | `0.208713` | `+58.64%` | `0.225730` | `+125.98%` | 能力上限參考 |

深度補測：

| 補測 | 邊界 PSNR | 高頻保留 | 邊界 F1@1px | 環形 8px | 環形 0.8px | 環形 0.08px | 判讀 |
|------|---:|---:|---:|---:|---:|---:|---|
| 低 alpha 權重平均，邊界最佳 `a005` | `21.0094` | `0.2214` | `0.6518` | `0.1483` | `0.1555` | `0.1291` | 沒有共同通過；邊界改善太小且環形已退步 |
| 低 alpha 權重平均，守門較穩 `a003` | `20.8252` | `0.2127` | `0.6420` | `0.1399` | `0.1487` | `0.1232` | 環形較接近，但邊界仍接近 COMBO |
| `r42_guarded_kd_probe_latest` | `32.6607` | `0.7591` | `0.8705` | `0.2108` | `0.4257` | `0.1986` | 邊界仍強，但環形守門更差 |

已完成：
- 合成邊界資料 stages 34–40：細線、格線、交叉線、曲線、大區塊、缺陷、混合場景
- 每張 R42 圖的邊界遮罩、中心線遮罩、距離圖與 metadata
- 訓練資料包 `r42_boundary_research_train`：1660 pairs（環形 500 / 形狀 250 / 顯微特徵 350 / 邊界 560）
- 診斷資料包 `r42_guarded_kd_probe_train`：1530 pairs（環形 700 / 形狀 300 / 顯微特徵 250 / 邊界 280）
- 測試資料包 `boundary_val_unseen`：140 pairs（7 類邊界資料階段各 20）
- 訓練器可開關的邊界幾何損失
- `r42_boundary_from_combo` 1 epoch / 1 batch CPU 快速接線測試
- `r42_boundary_from_combo` 與 `r42_boundary_from_r41` 各 50 epoch 正式訓練
- COMBO / R39 / R40 / R41 / R42 共 8 組顯微邊界重建與分項評估
- R42 四個權重的本地三尺度環形守門
- COMBO ↔ `r42_r41_best` 低 alpha 權重平均補測（0.01 / 0.02 / 0.03 / 0.05）
- `r42_guarded_kd_probe` 1 epoch 快速接線測試、8 epoch 短訓練、顯微邊界驗證與本地三尺度環形守門
- `r42_r41_best`、`r42_combo_latest`、`r42_r41_latest` 外部 GMF 補測完成；三者皆不堪作量測替代

正式入口：
- 實驗主報告：`D:\GMM_2_Final\Experiments\R42_MicroscopyBoundaryFidelity\reports\R42_RESULTS.md`
- 外部比較報告：`D:\GMM_2_Final\Experiments\R42_MicroscopyBoundaryFidelity\reports\R42_EXTERNAL_COMPARE.md`
- 訓練啟動器：`D:\GMM_2_Final\Experiments\R42_MicroscopyBoundaryFidelity\scripts\launch_r42.py`
- 資料包根目錄：`D:\GMM_2_Final\Training_Data\r42_microscopy_boundary_fidelity\`
- 代表圖：`D:\GMM_2_Final\Experiments\R42_MicroscopyBoundaryFidelity\results\boundary_recon\r42_representative_boundary_sheet.png`

R42 當前發現：資料與幾何目標可以推起通用顯微邊界忠實度；問題不在「模型完全學不會」，而在「推高通用邊界能力後，連續位移下的位置穩定性會退步」。低 alpha 權重平均證明能力不是小幅混合就能安全帶回；守門 KD 診斷證明單張影像老師牽引也不夠；外部 GMF 補測進一步確認這不是本地分析假象。下一輪應改做通用邊界位置一致性：對線條、格線、曲線、缺陷與大區塊建立已知位移 / phase / pitch 的序列約束，讓所有顯微結構的邊界位置穩定，不只是補環形。

### Closed Follow-up: Round31

一句話 verdict：**measured B1 hyperparam candidates external 全部退步；沒有形成升級。**
One-line verdict: **all measured Round31 B1 hyperparameter candidates regressed externally; no upgrade was produced.**

正式入口 / Formal entry points：

- decision:
  `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
- external compare:
  `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_EXTERNAL_COMPARE.md`

measured candidates / 已量測候選：

| candidate | external `0.8px step std` | vs former baseline `R30` |
|------|-----------|-----------|
| `r31_eq_prob_up` | `0.184867` | `+10.1%` |
| `r31_eq_weight_up` | `0.185458` | `+10.5%` |
| `r31_edge_ratio_low` | `0.179347` | `+6.8%` |

artifact caveat / artifact 注意事項：
- `r31_eq_combo` 缺 `GMF_score.txt`
- 判定：**artifact missing**，不是 measured regression

### Closed Sandbox: Round32

一句話 verdict：**`R32Sandbox` internal winner external FAIL；sandbox 已關閉。**
One-line verdict: **the `R32Sandbox` internal winner failed the final external gate; the sandbox is closed.**

正式入口 / Formal entry points：

- sandbox README:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- decision memo:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
- final external compare:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`

核心數字 / Core numbers：

| scale | former baseline `R30` | `r32_real_eq_finetune` | delta |
|------|-----------|-----------|-----------|
| `8px` | `0.205193` | `0.319667` | `+0.114475` |
| `0.8px` | `0.167862` | `0.331821` | `+0.163960` |
| `0.08px` | `0.157720` | `0.230119` | `+0.072399` |

## 4. Open Side Track / 開放中的 side track

### R26NewPSFCheck

一句話定位：**PSF 驗證 side track；pending external GMF；不是 active mainline。**
One-line role: **PSF-validation side track; pending external GMF; not the active mainline.**

| 項目 | 狀態 |
|------|------|
| 新 Whole-FOV PSF 擬合 | ✓ 完成（2026-03-26） |
| 新 PSF 重訓模型 checkpoint | ✓ 已建立 |
| 外部三尺度重建（external recon） | ✓ 已完成 |
| PSF 正式流程審核 | ✓ 已完成 |
| pure_psf_control 對照實驗 | ✓ 已完成 |
| formal_newpsf_candidate promote | ✓ 已完成，verdict：PROMOTE |
| 外部 GMF 結果 | ⏳ 等待中 |

正式入口 / Formal entry points：

- sandbox README:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\README.md`
- status:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\reports\STATUS_20260326.md`
- PSF audit:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\psf_audit\PSF_FORMAL_AUDIT_20260326.md`
- promote compare:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\formal_newpsf_candidate\reports\NEW_PSF_FORMAL_R26_COMPARE.md`

## 5. Measurement Policy Status / 量測政策狀態

目前穩定結論 / Current stable conclusion：

- **external GMF remains the final gate**
- internal step_std **不再適合作為硬門檻**，尤其在 residual_std 進入低噪聲區後
- 720-angle unweighted circle fit 已驗證能降低 internal/external gap
- weighted fit 可用，但不是統一預設

正式入口 / Formal entry points：

- divergence analysis:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`
- machine-readable policy:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`

量化修復狀態 / Quantization policy：

- canonical inference now uses `np.rint`
- R33 修復後 `0.8px` 改善，R38v2 修復後 `8px` 改善但 `0.8px` 退步
- 這個差異被視為 **model-dependent quantization sensitivity**，不推翻 COMBO promotion

## 6. PSF Policy Status / PSF 政策狀態（2026-03-27）

R26 研究線的 PSF 已於 2026-03-27 正式完成政策切換。

| 身份 | PSF | 說明 |
|------|-----|------|
| **current standard** | 新 Whole-FOV PSF（2026-03-26 完成） | 物理上較合理；same-recipe 對照確認不引發崩壞；為目前研究採用的正式 PSF |
| **legacy empirical baseline** | 舊 PSF | 歷史上取得較好經驗數值；保留用於引用與對照，不刪除，不再作為正式預設 |

機器可讀 PSF 政策 / Machine-readable PSF policy：
`D:\GMM_2_Final\docs\policy\PSF_STANDARD_POLICY.json`

詳細說明 / Full details：
`D:\GMM_2_Final\docs\policy\PSF_POLICY_TRANSITION_R26.md`

## 7. Next Decision Boundary / 下一個決策邊界

下一個決策邊界已經不再是「三候選誰升級」，因為這件事已完成。
The next decision boundary is no longer "which of the three candidates gets promoted," because that decision is now closed.

接下來只在以下情況才值得立新 round：

1. 有明確新機制，不是 R33/R38v2/COMBO 的微幅重掃
2. 有 deployment-specific 需求，足以合理地偏向某個 alternate 或新線
3. 能同時說清楚 external GMF 目標、`8px` guard、與視覺取捨

不再合理的下一步 / What is no longer a sensible next step：

- 把 `R26NewPSFCheck` 寫成 active mainline
- 把 `R33` 或 `R38v2` 繼續寫成 pending promotion
- 把 720-angle 當成未完成 action item

目前真正的決策邊界是：
**若要再開新 round，必須是新的機制或新的 deployment 條件，而不是重複討論已完成的 baseline promotion。**
