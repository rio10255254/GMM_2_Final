# 完整結果先於漂亮影像：早期失敗如何接到後續設計

這份入口整理既有實驗，不開新訓練、不重新推論。完整數表直接進一般倉庫，三張圖引用原已存在內容；中途模型只記必要的原選用版本，不再整批上傳。

## 這幾輪各自想修什麼

| 輪次 | 改了什麼、實際做到哪裡 | 仍須保留的失敗／限制 |
|---|---|---|
| R88 | 從零訓練，想同時守住紋理、輪廓、位移與大圖分塊；完成87輪後停止，最後保存85輪。 | 沒有驗證輪次通過原條件，真實50倍輸出近原圖；兩張舊煙霧資料預覽不是正式實拍成果，不用它們補造成功圖。 |
| R91 | 將低頻、細節與邊界分工，四種曝光一起學；原結束摘要與完整原表是60輪。 | 原進度仍active只是舊快照；清楚輸入改動、拓樸與位移尾端診斷保留，完成訓練不等於驗收通過。 |
| R92 | 修正物理邊緣過渡、平衡曝光取樣，移除不穩定的自適應細節控制；原表80輪。 | 生成／曝光修復與來源統計保留；不能拿不同資料組別比例直接排名，也不把匿名光學統計當成無來源關係。 |
| R100 | 在原程序場景上加入不接觸輪廓的程序材質；原固定主要終點為40輪。 | 真實圖看起來接近原圖不等於乾淨答案準確；完整逐步位移、尺寸與原圖改動一併看。 |
| R103 | 來源與答案共享曝光，移除會消掉細節訊號的特徵正規化，分開低頻／輪廓／紋理；原內部測試選48輪。 | 曝光18有明確輪廓失敗，照明問題及清楚輸入不必要改動仍在；不能把一般紋理改善當成SEM輪廓全面勝出。 |
| R104 | 用局部相對亮度判斷形狀與修正需要；原內部測試選48輪，已完成實拍與SEM後測。 | 早期README仍寫未授權啟動，那是設計時狀態；現有完成原件不代表當時所有構想都成真。形狀頭未直接形成最終邊界，SEM整體結果也較Raw差。 |

R88、R91、R92本次不新增重建圖，直接讀原停止／完成紀錄、全輪表與不利診斷；不為填滿圖冊重新產生輸出。

## 可直接閱讀的完整數據

以下保留原始檔案，包含逐張、逐步、逐物件與每個曝光的表、原選模、共同有效範圍、敏感度、失敗與來源清單；不只留下較好的平均分數。

| 輪次 | 原結果檔數 | 大小 | 直接閱讀位置 |
|---|---:|---:|---|
| R100 | 28 | 5.71 MB | [完整後測表與原摘要](<../../../../Experiments/R100_CausalOperatorScratch/results/posttraining_validation>) |
| R103 | 52 | 4.87 MB | [完整後測表與原摘要](<../../../../Experiments/R103_RecoverableDetailScratch/results/posttraining_validation>) |
| R104 | 50 | 5.12 MB | [完整後測表與原摘要](<../../../../Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation>) |

R100有6,672筆鎖定位移，跨方法共同有效範圍為5,860筆。R103／R104的6,672筆讀值來自同一批301張實拍，並非重新獨立拍攝。SEM比較為36個實體柱體、12種曝光反覆觀察，不能把曝光筆數當成更多獨立柱體。SEM不提供光學亮度或紋理的真實答案。

## 三張圖的用途

- [R100同物件SEM外形對照：必須連同完整七方法表看](<../../../../Experiments/R100_CausalOperatorScratch/results/posttraining_validation/sem_contour/figures/r100_sem_contour_overlay.png>)
- [R103固定真實序列示例：不能替代曝光失敗的原數表](<../../../../Experiments/R103_RecoverableDetailScratch/results/posttraining_validation/real_sequences/figures/20x_0p5um_comparison.png>)
- [R104曝光相關的輪廓對照：保留較差結果](<../../../../Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/sem_contour/figures/exposure_comparison.png>)

這三張圖原已在GitHub，不新增影像。R103曝光18的判讀以原final_summary及per_exposure_summary為準，沒有借用R104圖片冒充R103失敗圖。

## 原模型與重做界線

本入口記錄R100原第40輪及R103／R104原第48輪的精確身分與既有已發布位置，沒有新增模型。R100是原預先固定終點，R103／R104是當年內部測試的選擇；都不是目前論文改採用。逐個檔案及模型對應見FAILURE_LINEAGE_RECORDS.json.gz。

重新訓練仍需要各輪實際資料配方、固定輸入與環境；完整生成影像、逐張重建像素和其他中途權重留本機／H或由既有必要來源取得。原D/C/H絕對位置是歷史來源紀錄，不保證直接在另一台電腦執行。沒有宣稱這次重跑全部歷史GPU訓練。

## 原判讀與後續設計入口

- [R88原停止判決](<../../../../Experiments/R88_MeasurementFaithfulScratch/reports/R88_ABORTED_AT_E87.md>)
- [R91原完成、資料與不利讀值](<../../../../Experiments/R91_DetailDecoupledScratch/reports/R91_PRESERVATION_AUDIT_20261021.md>)
- [R92原完成、生成修復與不利讀值](<../../../../Experiments/R92_PhysicalTransitionBalancedScratch/reports/R92_PRESERVATION_AUDIT_20261021.md>)
- [R103原完整總結與曝光18限制](<../../../../Experiments/R103_RecoverableDetailScratch/results/posttraining_validation/final_summary.json>)
- [R104原SEM整體及每曝光結果](<../../../../Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/sem_contour/summary.json>)
- [R105A為何否決直接用預測輪廓重畫影像](<../../../../Experiments/R105A_GeometryRendererFalsification/reports/R105A_FINAL_FINDINGS_ZH.md>)

原22份早期程式與9項早期R13公式缺件依舊保留；本頁不以這批完整小表冒稱全專案精選已完成。
