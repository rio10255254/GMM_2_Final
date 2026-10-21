# R89到R93：為什麼後面的設計不只是把模型訓練更久

這幾輪是各自隨機初始化的研究，不把前輪模型當成後輪起始權重；設計會參考前輪暴露的問題。資料、曝光抽樣和驗證讀法並不相同，因此下面是研究脈絡，不能依最後一個內部分數直接排模型高低。

| 輪次 | 想解決什麼 | 實際完成與保留理由 |
| --- | --- | --- |
| R89 | 移除輸出信心閘，讓模型真正恢復細節，克服接近原圖照抄 | 100輪完成，但安全條件未全過。第100輪強烈細節伴隨輪廓退步；第55輪跨曝光中間值較佳，最差曝光仍抓到外圈。兩者都保留，不能只挑中位數或最銳利的一張圖 |
| R90 | 把低頻分支確實限制為低頻，四種相干曝光回到共同輪廓位置 | 實際55輪停止。20至55輪事後比較保留45輪作研究與ONNX可行性候選；50輪起清楚5倍出現黑邊退步，45輪也仍有真實SEM曝光條件向外偏，沒有升級 |
| R91 | 把亮度、細節與邊界分開，四曝光組合、持續紋理與獨立雜訊分開學習 | 60輪完成。原進度仍寫active，但結束摘要和完整60列原表相符；接近清楚／原圖保護組的代價、位移尾端和曝光診斷保留，沒有因正常跑完就宣稱問題解決 |
| R92 | 修正曝光組更新佔比、物理邊緣過渡，分開退化細節恢復與原圖保護 | 80輪完成。保留資料的修復前後版本與身分，分清訓練bfloat16、主要驗證／部署float32；其清楚組與位移等不利診斷仍保留 |
| R93 | 進一步拆開可恢復細節與清楚輸入保護 | 原64輪計畫實際60輪停止，既存候選的原規則重算選出48輪；本輪固定資料之後被R94／95／97／98共用。不能把後代共用資料關係改稱獨立來源 |

## 兩種很不同的「資料檢查修正」

R91的原紀錄將四曝光由舊固定窗口檢查改為連續路徑契約，指出300組中有3組未落在舊窗口；原陣列與manifest沒有改動，內容身分仍是`bcce2a7b...`。這是檢查讀法的對照，不能說因此重新生成了一套資料。

R92真的改過生成觀測。原紀錄保存69張來源影像的整體光度投影、4組／16張曝光跨度修復及另外1張整體投影；封存組另有1張在同退化家族內重抽光學與雜訊參數。幾何、答案、分組與角色不改，沒有把答案像素混入來源。修復前備份、每步資料身分及後來完整檢查一併保留；正式實際使用的內容身分是`260ccc5b...`，不能只留初始種子或套用後代生成器。

## 如何閱讀完成與失敗

R91／R92原結束摘要分別寫complete，舊進度快照仍寫active。2026-10-21逐輪表核對確認60／80輪完整連續，最後14／20個記錄量與摘要吻合；原進度檔保持原樣。[實際核對](COMPLETION_RECORDS_VERIFIED.json)。這是保存判讀，沒有重新訓練、重算原始輪廓或宣稱通過外部實體驗收。

要看結果時，先同時讀恢復較差影像的收益、原本清楚影像被改動的代價、最差曝光、位移偏差與尾端，以及實際耗時。正常完成、分塊相同、內部平均改善和能否正式採用，各自有不同證據。

- [R89正式最後驗證](../../../Experiments/R89_MeasurementNativeScratch/reports/final_validation/R89_FINAL_VALIDATION_TW.md)／[55與100輪的平均及最差曝光](../../../Experiments/R89_MeasurementNativeScratch/reports/final_validation/stage_weight_analysis/R89_STAGE_WEIGHT_FINDINGS_TW.md)
- [R90原方法與55輪停止後結果](../../../Experiments/R90_ExposureCoherentScratch/README.md)
- [R91完成與來源審查](../../../Experiments/R91_DetailDecoupledScratch/reports/R91_PRESERVATION_AUDIT_20261021.md)／[原曝光檢查對照](../../../Experiments/R91_DetailDecoupledScratch/reports/formal_continuous_exposure_audit_reconciliation.json)
- [R92完成與來源審查](../../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/R92_PRESERVATION_AUDIT_20261021.md)／[原光度修復](../../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/formal_recoverability_projection.json)／[原曝光跨度修復](../../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/formal_exposure_span_repair.json)
- [R93完整方法與小型原結果重算](../r93_shared/README.md)

完整數據、原模型與影像仍依[全專案保存入口](../project_completion/README.md)逐批處理；D槽原件、論文與活動訓練保留。
