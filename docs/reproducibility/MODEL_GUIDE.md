# 模型先按用途找

COMBO正式基準、核准替代、論文模型與未採用研究端點是不同身分。檔名叫`best`、`selected`、`last`或輪次比較晚，不會自動成為正式模型；以[正式政策](../../ESTIMATOR_POLICY.json)、[目前狀態](../../PROJECT_STATE.md)及各輪原選擇紀錄為準。

## 精選固定模型

下表由已保存的[精選索引](project_completion/curated/SELECTIVE_RESEARCH_INDEX.json.gz)和2026-10-22實際附件清單產生，沒有重新選模。**模型自身大小不等於整份附件大小**；同一附件含多個保存物件，先衡量需要再下載。

| 模型 | 保存用途 | 原模型大小 | 既有附件及下載大小 | 身分依據 |
|---|---|---|---|---|
| COMBO | 正式基準 | 52.64 MB | [research-fixed-models-012.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1643.17 MB） | [原選擇依據](<../../ESTIMATOR_POLICY.json>) |
| R33 | 定位取向核准替代 | 52.64 MB | [research-fixed-models-010.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1677.39 MB） | [原選擇依據](<../../ESTIMATOR_POLICY.json>) |
| R38v2 | 視覺取向核准替代 | 52.64 MB | [research-fixed-models-010.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1677.39 MB） | [原選擇依據](<../../ESTIMATOR_POLICY.json>) |
| R39R40_avg_a025 | 平衡取向核准替代 | 20.42 MB | [research-fixed-models-012.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1643.17 MB） | [原選擇依據](<../../ESTIMATOR_POLICY.json>) |
| EDSR-x1 | R153原合成驗證選出的比較模型 | 4.90 MB | [research-fixed-models-007.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1671.50 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/EDSR-x1/training_complete.json>) |
| NAFNet | R153原合成驗證選出的比較模型 | 68.66 MB | [research-fixed-models-023.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（373.42 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/NAFNet/training_complete.json>) |
| RDN-x1 | R153原合成驗證選出的比較模型 | 22.03 MB | [research-fixed-models-015.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1667.84 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/RDN-x1/training_complete.json>) |
| RCAN-x1 | R153原合成驗證選出的比較模型 | 61.71 MB | [research-fixed-models-002.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1672.65 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/RCAN-x1/training_complete.json>) |
| Restormer | R153原合成驗證選出的比較模型 | 104.57 MB | [research-fixed-models-004.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1673.30 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/Restormer/training_complete.json>) |
| USRNet-x1 | R153原合成驗證選出的比較模型 | 68.07 MB | [research-fixed-models-014.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1543.37 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/USRNet-x1/training_complete.json>) |
| SwinIR | R153原合成驗證選出的比較模型 | 122.84 MB | [research-fixed-models-005.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1593.83 MB） | [原選擇依據](<../../Experiments/R153_MeanExternalBenchmark/runs/SwinIR/training_complete.json>) |
| R152_base_reference.pth | R152原起始參照 | 5.91 MB | [research-r152-frozen-inputs-001.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-training-kits-20261016)（28.76 MB） | [原選擇依據](<../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_STANDALONE_PACKAGE_20261004.md>) |
| R152_r152_deployed.pth | R152論文實際部署模型 | 7.11 MB | [research-r152-frozen-inputs-001.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-training-kits-20261016)（28.76 MB） | [原選擇依據](<../../Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_STANDALONE_PACKAGE_20261004.md>) |
| R100_CausalOperatorScratch | 理解失敗後測的原端點；未改成正式採用 | 38.44 MB | [research-fixed-models-004.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1673.30 MB） | [原選擇依據](<../../Experiments/R100_CausalOperatorScratch/results/posttraining_validation/internal_test/summary.json>) |
| R103_RecoverableDetailScratch | 理解失敗後測的原端點；未改成正式採用 | 17.64 MB | [research-fixed-models-010.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1677.39 MB） | [原選擇依據](<../../Experiments/R103_RecoverableDetailScratch/results/posttraining_validation/candidate_selection/summary.json>) |
| R104_PhotometricInvariantCausalGateScratch | 理解失敗後測的原端點；未改成正式採用 | 18.92 MB | [research-fixed-models-011.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)（1688.74 MB） | [原選擇依據](<../../Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/candidate_selection/summary.json>) |

每份原路徑與完整內容核對值在精選索引，不能只憑檔名互換模型。下載分包時，同時依該版本的原恢復清單還原所需位置，不要把不同模型架構或光學來源混用。

## 其他研究線

| 需要理解的模型 | 入口與限制 |
|---|---|
| Lab R61 v16／V41／V42 | [Lab沿革](lineage/LAB_SYSTEM.md)、[V42原歷程](lab_comparisons/V42_HISTORY.md)。V42第10輪平滑最佳與第120輪當下模型分開，不能只留下較好的一份 |
| R93及R94／95／97／98 | [R93](r93_shared/README.md)、[四輪原紀錄](four_rounds/README.md)。早期試跑、失敗、接續和原選擇保留，模型檔案數不等於訓練次數 |
| 舊分支R34／35／37 | [原分支、報告與既有模型位置](lineage/HISTORICAL_BRANCHES.md)。原分析圖中的GMF參考沿用R26，不能當每輪各自的外部成績 |
| 原部署模型與光學檔 | [正式交付包入口](../../Deliverables/README.md)。原R61小包、COMBO、R39R40、R152用途不同；依包內當時介面使用 |

若只讀原數字或研究結論，通常不需要下載模型。大量中途模型及可生成的訓練資料留本機／H歷史，不再以完整模型鏡像作整理目標。
