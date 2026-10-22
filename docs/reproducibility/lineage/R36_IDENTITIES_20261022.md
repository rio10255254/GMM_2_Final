# 兩種R36身分必須分開

2026-10-22。已找到**Lab R61內部第36次嘗試**的原訓練、模型和完整結果；它不是2026年4月主專案R35與R37之間的一份獨立實驗。主專案那個編號仍未找到足以指定的方法與結果，不能拿Lab同號補上去。

## 已找到：Lab R61內部r36

2026-06-23 07:58，從r31／r28-pos75混合的a948起點出發，給邊界修正支路增加方向輸入，使用旋轉矩形保護v10資料。原命令是6輪、每輪最多80批、batch 4、裁切256；原設定包含學習率0.000002。這是短程接續，沒有從零訓練一個主專案R36。

[原啟動與評估命令](LAB_R61_R36_ORIGINAL_COMMANDS.json)均有原成功退出紀錄；[當時啟動設定](LAB_R61_R36_ORIGINAL_LAUNCH_CONFIGURATION.json)保留真實資料與起點。原正式敘事在[Lab R61進度報告](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/R61_PROGRESS_20260623.md)。

v10是**7,496組**：800舊形狀、1,400 SEM答案錨點、1,200序列保護、4,096合成；固定分組為6,745訓練／751驗證。它不是後來v16的20,296組，也不能只把預設profile換成現在版本。分組重疊為零不等於同樣本SEM答案或反覆開發用評估已成獨立實拍證據。

## 原結果與未採用原因

使用同一組96個合成案例比較best及latest，原門檻要求各指定組別不退步。雖然整體距離略降，分組仍有退步，因此兩份都沒有採用。

| 原版本 | 平均輪廓距離（px） | 未通過分組 | 原完整表與判斷 |
|---|---|---|---|
| R8比較基準 | 0.4847606391073593 | 參考 | [完整原表](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/diverse_phantom_validation/wide_96case_r60_vs_r8best_20260623/R8_best_tradeoff/diverse_phantom_validation_20260623_040536/boundary_metrics.csv>) |
| R36 best | 0.483770348650675 | 橢圓、旋轉矩形 | [完整原表](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/diverse_phantom_validation/r36_best_from_a948_orientation_rotrect_v10_80b_wide96_matched_20260623/diverse_phantom_validation_20260623_080230/boundary_metrics.csv>)／[原分組判斷](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/diverse_phantom_validation/r36_best_from_a948_orientation_rotrect_v10_80b_wide96_matched_20260623/r36_best_vs_r8_gate.json>) |
| R36 latest | 0.48373880068377023 | 0及0.5偏移、旋轉矩形 | [完整原表](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/diverse_phantom_validation/r36_latest_from_a948_orientation_rotrect_v10_80b_wide96_matched_20260623/diverse_phantom_validation_20260623_080230/boundary_metrics.csv>)／[原分組判斷](<../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R61_BoundaryGeneralizationUniversal/reports/diverse_phantom_validation/r36_latest_from_a948_orientation_rotrect_v10_80b_wide96_matched_20260623/r36_latest_vs_r8_gate.json>) |

每份CSV含2,304列，保留每案例的輸入／重建與物件讀值；不是2,304次獨立實驗。96個案例已用於這條開發線的反覆選擇，不能改稱新的相機重拍或未知樣本驗證。

後續Lab R61內部r37改分組抽樣，r38加小偏移保持，r39再加直接位置保護；它們都不是主專案R37的頻率修正實驗。[Lab全線](LAB_SYSTEM.md)與原R61進度報告保留完整不利結果及後續。

## 重做需要哪些來源

原best／latest／平滑模型已在既有版本附件；[逐檔來源表](LAB_R61_R36_PROVIDERS.json)列出原位置、內容身分、附件和本次直接提出的原表。沒有重傳這些端點或整批影像。

原啟動需要的**a948固定起點**，此前的發布內容索引沒有提供同一份內容。不能從R36結果模型倒推起點，因此這次只另存[單一必要起始來源](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-lab-r61-r36-source-20261022)：原件17,402,302 bytes，壓縮包約15.92MB。其他混合比例、中途模型、完整v10訓練影像與重建影像不跟著整包上傳。

要重做訓練，仍須原v10生成方法、3,400組繼承來源及當時幾何、固定分組、25PSF相容處理與實際啟動設定，不能只靠seed，不能用v16生成物代替。v10的原manifest身分及已有取得位置列在來源表；可生成的大影像保持按需重建。現在能直接讀原完整表、依原程式重算分組判斷及取得固定模型；這次沒有重新訓練、推論或重製全部v10資料。

原run_meta明記`seed_deterministic=false`、`cudnn_deterministic=false`、`cudnn_benchmark=true`；有種子不等於GPU逐步重訓必然相同。原訓練時各動態程式是否都有獨立固定版本，仍需按保存清單／原修改歷史配套；本次不把找到命令和模型擴成完整訓練逐步驗收。

## 仍未辨認：主專案獨立R36

先前已查有名分支、主／Lab實驗路徑及243個可到達歷史敘述。本次另檢查原263個提交物件，以及其中不在目前D有名歷史內的86個版本樹，未找到獨立主R36路徑或提交敘述；也查原相關研究對話、修改／啟動紀錄。[本次額外查找](R36_EXTRA_HISTORY_SEARCH_20261022.json)保留實際範圍。

這不證明它從未做過。若要指定一個主R36的方法、來源、模型或結果並重跑，目前仍沒有足夠原件；不能補造或拿Lab r36代替。已取回的R34／35／37原件、這次R13算分、R94／95來源各有自己的明確身分，不靠這個未知編號才能讀取。未確認的主R36若有其他未記錄依賴，也不能反過來假定一定無影響。
