# 重要原表、來源證據與失敗的直接閱讀入口

2026-10-22。這批將原本已在正式附件保存的重要小型原件提出到一般檔案，讓讀者不用先下載大型資料包。共247份原件、14,644,206 bytes；內容照原檔保存，沒有改數字、篩掉不利列或重新推論。

## 先看哪一組

| 研究問題 | 原結果與來源 | 為何值得直接保存 |
|---|---|---|
| R128四次完整訓練為何只留第四次修正 | [四組最後全部288筆SEM讀值](../../../../Experiments/R128_SourceOnlyFullTraining/results/final_review/all_final_SEM_rows.csv)、[原選擇與未解問題](../../../../Experiments/R128_SourceOnlyFullTraining/results/final_review/selection.json)、[原完成核對](../../../../Experiments/R128_SourceOnlyFullTraining/results/final_review/execution_audit.json) | 正常亮度改善與暗曝光失敗一起留，無法讀值的物件仍在原分母內；不是只看選中模型 |
| R128整個輪廓、尺寸和完整位移是否一致改善 | [完整輪廓原表](../../../../Experiments/R128_SourceOnlyFullTraining/results/full_contour)、[各方法完整圓心與位移表](../../../../Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison) | 保留完整物件及診斷，參照讀法、邊緣保留與未通過項目一起讀 |
| R129原24次短測與新增8192次長訓練差在哪 | [短測全部864筆SEM讀值](../../../../Experiments/R129_OpticalPriorHybrid/results/sem/per_measurement.csv)、[長訓練五個時點540筆原讀值](../../../../Experiments/R129_OpticalPriorHybrid/results/long_training_review_20260913_v2/sem_measurements.csv)、[完整連續位移](../../../../Experiments/R129_OpticalPriorHybrid/results/continuous_lsc) | 短測、長訓練及完整序列不是同一母體；細形狀改善與尺寸退步不能混成全面成功 |
| R135如何在同精度下比較七組方法 | [原圖](../../../../Experiments/R135_UnifiedModelComparison/results/Raw)、[舊V42](../../../../Experiments/R135_UnifiedModelComparison/results/V42_old)、[乾淨重訓V42](../../../../Experiments/R135_UnifiedModelComparison/results/V42_clean)、[R61](../../../../Experiments/R135_UnifiedModelComparison/results/R61)、[R128](../../../../Experiments/R135_UnifiedModelComparison/results/R128)、[R129 W16](../../../../Experiments/R135_UnifiedModelComparison/results/R129_W16)、[R134 P1](../../../../Experiments/R135_UnifiedModelComparison/results/R134_P1) | 保存每張圓心、固定120對、同次拍攝194對、重新定位、SEM及速度原表，避免只留總平均 |
| R61為何不能當成未見SEM答案的獨立驗證 | [完整20,296列訓練名單](../../../../Experiments/R135_UnifiedModelComparison/results/r61_training_audit/training_roster.csv)、[答案、裁切、繼承及來源證據](../../../../Experiments/R135_UnifiedModelComparison/results/r61_training_audit)、[原SEM工作表](../../../../Shared_Sources/SEM_Originals/via_pilar.xlsx) | 35顆評估柱體的逐顆尺寸進入訓練名單，另有全體均值監督；分組交集0不等於外部樣本獨立 |
| 9月3日真正的平台讀值和時間是什麼 | [30份原始平台紀錄](../../../../Shared_Sources/PI_Repeatability_20260903/position_records/README.md) | 每趟起點加30步，共930筆原始列；不由模型重建，930張照片仍共用原始ZIP |

完整檔案身分、各原發布位置與排除理由在[本批原件清單](IMPORTANT_TABLE_RECORDS_20261022.json.gz)。CSV列數合計包含相同來源在不同分析中使用、原圖／模型及彙整表，不能當獨立樣本數。大名單在GitHub預覽可能截短，可用Raw／下載取得完整原表。

## 兩張原圖怎麼幫助判讀

![R128四組在正常及暗曝光的完整物件結果](../../../../Experiments/R128_SourceOnlyFullTraining/reports/figures/final_SEM_comparison.png)

這張圖保留每組36個物件、暗曝光退步，以及第二／三組的灰色無法量測欄。第四組正常36個改善，同時暗照片29個退步；它是當輪後續修正候選，沒有因此成為正式基準或目前論文模型。[原結果與判決](../../../../Experiments/R128_SourceOnlyFullTraining/reports/R128_RESULTS.md)。

![R135同圖同精度下的形狀、尺寸與位移取捨](../../../../Experiments/R135_UnifiedModelComparison/reports/figures/comparison.png)

原圖當時以星號標舊V42的來源重疊；**後來R61來源審查也確認SEM尺寸答案重用**，應連同本次完整名單及[原來源審查](../../../../Experiments/R135_UnifiedModelComparison/reports/R135_R61_TRAINING_AUDIT.md)閱讀。不能把R61那欄當作未見答案的獨立準確度證據。形狀、尺寸、步距與速度各有取捨，沒有用一個加權總分重選冠軍。

兩張原圖已在既有GitHub位置，本次沿用，不新增或重編碼影像。

## 避免把不同研究混起來

- R128是四組各8192次的原研究；第四組正常曝光較好，但暗曝光及清楚控制仍有問題，原決定不是正式部署採用。
- R129短測是四組各24次；長訓練是D延續新增8192次，step0已是短測後起點。長訓練36/36細形狀改善，同時31/36尺寸退步；第一次未完成審查與後來v2完成版本分開。
- R135用201張既有照片，固定120對、完整194對及3次重新定位分開。它使用名義步距；[R136的30趟重拍](../../../../Experiments/R136_PIRepeatability/reports/R136_LSC_FOUR_MODEL_RESULTS.md)及[目前R153論文交接](../../../../Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md)是其他實驗與讀法，不併成一個樣本集合。
- R61審查證明尺寸答案／來源接觸，沒有量化它造成多少分數優勢。名單上的資料也不等同完整逐樣本讀取帳，不從這個發現推斷動機。

六個R135原比較模型與R128四組最後模型的相同原件已在既有附件找到，[原端點與來源](R128_R129_R135_ENDPOINTS_20261022.json)列出完整內容身分。本批不重傳模型、不改推論設定或研究採用。

## 本批省略什麼

沒有加入整套訓練影像、重建浮點陣列或全部中途模型。3,313份重複逐張旁註或舊狀態快照沿用原正式附件／歷史，不再塞進一般閱讀樹；完整圓心、每步／每物件原表及失敗保留。原生成程式與必要固定來源由各輪方法及[生成指南](../../GENERATION_GUIDE.md)取得。

這次的檢查服務於原件是否完整收到、欄位與列數是否符合原記錄、來源是否清楚；沒有重算新實驗成績，沒有訓練、推論或重新產生整套資料。COMBO、R152／RAW論文及原D工作版本保持原身分。
