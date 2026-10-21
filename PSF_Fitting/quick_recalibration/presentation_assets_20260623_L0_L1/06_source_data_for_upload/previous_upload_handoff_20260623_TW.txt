# PSF L0/L1 新資料實驗上傳交接說明

產生日期：2026-06-23

這份文件是給後續報告撰寫或另一個 GPT 分析用的交接說明。重點是：不要只看檔名，要知道每批資料在實驗裡的角色。

## 0. 最重要的檔案清單

完整檔案索引已整理成 CSV：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\PSF_UPLOAD_FILE_MANIFEST_20260623.csv`

這個 CSV 共 1700 筆，欄位包含 category、role、path、extension、size_bytes。若要讓另一個 GPT 檢查所有檔案來源，先上傳這個 CSV。

## 1. 建議上傳順序

### 第一批：讓 GPT 先理解任務與上月脈絡

1. 上個月月報 PDF  
   `C:\Users\Rio\OneDrive\學業\碩班\均華報告\GMM五月月報.pdf`

2. PSF 快速校正總設計文件  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\DESIGN_TW.md`

3. L0 雙 basin 後續修正提案  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\DESIGN_SECTION9_REVISION_PROPOSAL_TW.md`

4. 驗證實驗資料夾總說明  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\README_TW.md`

5. 舊 L1 預檢設計  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_PRECHECK_PLAN_TW.md`

### 第二批：這次正式結果

1. 正式 L0 摘要  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata\README_TW.md`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata\L0_newdata_summary.md`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata\L0_newdata_summary.json`

2. L1 三次重拍比較摘要  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_newdata\README_TW.md`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_newdata\L1_newdata_summary.md`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_newdata\L1_newdata_summary.json`

3. 同位置兩張影像的補充檢查  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_paired_frame_check\README_TW.md`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_paired_frame_check\paired_frame_summary.md`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_paired_frame_check\paired_frame_summary.json`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_paired_frame_check\paired_frame_metrics.csv`

### 第三批：每一輪的詳細擬合輸出

Round1 是正式 L0 錨點。Round2/3 是 L1 來源資料，不要再合併進正式 L0。

Round1：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round1\inputs_primary\prep_manifest.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round1\outputs\manifest.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round1\outputs\L0_newdata_noise_floor.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round1\outputs\L0_newdata_noise_floor_report.md`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round1\outputs\trial_01` 到 `trial_15`

Round2：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round2\inputs_primary\prep_manifest.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round2\outputs\manifest.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round2\outputs\L0_newdata_noise_floor.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round2\outputs\L0_newdata_noise_floor_report.md`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round2\outputs\trial_01` 到 `trial_15`

Round3：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round3\inputs_primary\prep_manifest.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round3\outputs\manifest.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round3\outputs\L0_newdata_noise_floor.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round3\outputs\L0_newdata_noise_floor_report.md`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round3\outputs\trial_01` 到 `trial_15`

每個 trial 資料夾內有四個關鍵檔：

- `PSF_fitted_2D_FOVstack.mat`：該 trial 的 PSF 係數結果。
- `batch_results.csv`：每個 FOV 的 fval、迭代次數、執行時間等。
- `candidate_config.json`：該 trial 的候選設定。
- `reasonable_config.json`：該 trial 的合理性設定。

### 第四批：原始影像

這三個資料夾是本次 L1 的三次相同條件重拍。每輪 242 張 BMP，代表 121 個位置，每個位置連續拍兩張。

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\Circle_Round1`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\Circle_Round2`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\Circle_Round3`

注意：每輪約 6.34 GB，三輪合計約 19 GB。若 GPT 上傳空間有限，不建議直接全部上傳；可先上傳結果 JSON、CSV、報告、腳本和少量代表影像，完整原始影像用雲端連結。

### 第五批：實際擬合使用的準備影像與遮罩

這三個資料夾裡的 `inputs_primary` 是將每輪原始影像整理成 901x901 的 frame-1 輸入。每輪內有 121 張準備影像、GT、圓形邊界遮罩與 prep manifest。

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round1\inputs_primary`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round2\inputs_primary`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata_round3\inputs_primary`

每輪的 GT 與遮罩在：

`...\inputs_primary\GT\GT_901_with_Block_proc.bmp`  
`...\inputs_primary\GT\GT_901_original_with_blocks.bmp`  
`...\inputs_primary\GT\circle_edge_mask.bmp`

原始 GT 來源：

`D:\GMM_2_Final\PSF_Fitting\Crop_circle_FreqFiltered\GT\GT_901_with_Block_proc.bmp`

### 第六批：舊 L0 封存結果，用來對照上月月報

舊 L0 不是這次正式 L0，但它是上月月報的基礎，也是說明「舊 basin 標準不能硬套新資料」時需要的對照。

主要對照資料：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\all_sets_comparison.md`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\all_sets_comparison.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\reference_basins.json`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\setA_vs_setB_comparison.md`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\setA_vs_setB_comparison.json`

舊 L0 圖表：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\fig_4sets_basin_scatter.png`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\fig_basin_alignment.png`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\fig_centroid_distance_proof.png`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\fig_centroid_distance_proof_v2.png`

舊四組 L0 的完整封存資料：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\L0_repeat_fit`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\L0_repeat_fit_setB`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\L0_repeat_fit_setC`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\L0_repeat_fit_setD`

### 第七批：重現分析用腳本

新資料的權威分析入口：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\l0_newdata_analysis.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\l1_newdata_analysis.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\paired_frame_analysis.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\l0_newdata_tools.py`

舊 L0 對照與畫圖：

`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\compare_all_sets.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\compare_setA_setB.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\plot_4sets_basin_scatter.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\plot_basin_alignment.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\plot_centroid_distances.py`  
`D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\plot_centroid_distances_v2.py`

測試：

`D:\GMM_2_Final\PSF_Fitting\tests\python\test_quick_recalibration_l0_newdata.py`

## 2. 實驗定義，請 GPT 分析時務必遵守

1. 正式 L0 只用 `Circle_Round1`。  
   不要把 Round1/2/3 合併成正式 L0。

2. L1 的主軸是三次相同條件重拍。  
   `Circle_Round1`、`Circle_Round2`、`Circle_Round3` 是三次 capture repeat。

3. 每個位置連拍兩張，但第二張目前只是影像層補充檢查。  
   不要把第二張當成正式 L1 的 PSF 擬合結果，除非後續真的對第二張完整跑 PSF fitting。

4. 本次原始資料是 11x11，共 121 個位置。  
   目前主擬合沿用舊標準 9 個位置：1、6、11、56、61、66、111、116、121。

5. 本次擬合目標是圓形邊界。  
   中間方塊不是擬合目標，已用填平與 circle-edge mask 避免干擾。

## 3. 主要數字摘要

### 正式 L0

正式 L0 來源：`Circle_Round1`，15 次重複擬合。

- clean repeated-fit median：0.027054842460418855
- clean repeated-fit mean：0.0653770382702862
- 使用 FOV 數量：9
- trustworthy coefficient 數量：6
- FOV clean-noise max/min：1.2114332693210326

Round2/3 只作為 L1 來源診斷：

- Round2 clean median：0.022558797385090226
- Round3 clean median：0.02729389267379506

解讀：三輪自己的 repeated-fit floor 量級接近，Round1 作為正式 L0 錨點不是孤立異常。

### L1 三次重拍比較

L1 來源：`Circle_Round1`、`Circle_Round2`、`Circle_Round3`。

- L1 status：within_L0_floor
- repeated-fit floor median：0.027054842460418855
- capture-to-capture spread median：0.004085821166184028
- net capture spread median after subtracting L0 floor：0.0
- readout abs-z median：0.04418114370662701
- readout abs-z p95：0.8218934366180716
- readout abs-z max：2.0899116827994835

直觀解讀：三次重新拍攝之間的差異，小於同一批資料自己重複擬合造成的自然波動。因此，在這批資料與這個拍攝條件下，重新拍攝本身不是主要不確定來源。

### 同位置兩張影像補充檢查

範圍：三輪全部 121 位置，每個位置 frame 1 vs frame 2，共 363 組配對。

- all positions edge mean abs diff median：2.5119731800766285 gray levels
- all positions center shift median：0.14101684089020014 px
- old nine-position subset edge mean abs diff median：2.5274830533451222 gray levels
- old nine-position subset center shift median：0.20483937727665785 px

直觀解讀：短時間同位置連拍兩張很接近，沒有看到大的影像層漂移。這可以作為拍攝穩定性的補充證據，但不能替代第二張影像的 PSF 擬合。

## 4. 舊 L0 對照重點

上月月報的舊 L0 四組結果：

- setA：primary/secondary 約 73.3 / 26.7%，noise floor 0.0286
- setB：66.7 / 33.3%，noise floor 0.0273
- setC：80.0 / 20.0%，noise floor 0.0225
- setD：80.0 / 20.0%，noise floor 0.0230

舊 L0 重要結論：BADS 在同一影像上會穩定落到兩種可解釋的解，主要差異與 defocus / spherical aberration 補償有關。這不是單純壞解，而是 loss landscape 中兩個相近的解。

## 5. 新資料和舊 basin 的關係

這次新資料不能直接套用舊 L0 的硬門檻。

新資料自己分群的結果：

- Round1：best_k = 2，比例約 13.3 / 86.7%
- Round2：best_k = 2，比例約 93.3 / 6.7%
- Round3：best_k = 3，比例約 40.0 / 53.3 / 6.7%

雖然主要差異方向仍與 defocus 相關，但比例與結構不再乾淨符合上月的 70-80 / 20-30 模式。

建議寫法：

「L1 顯示相同條件重拍的整體波動低於 L0 擬合底噪，代表拍攝重複性目前不是主要不確定來源；但舊 L0 的 reference basin 不能直接作為新資料的硬判斷門檻，新資料應建立自己的 operational standard。」

不建議寫法：

「L1 證明舊 reference basin 可直接延伸。」

## 6. 我對報告撰寫的建議

這次月報可以主打三個成果：

1. 新資料正式 L0 已重建。  
   不是沿用舊 L0，而是在新拍攝條件下重新確認 BADS repeated-fit floor。

2. L1 已完成。  
   三次相同條件重拍的 capture spread 小於 L0 repeated-fit floor，說明目前拍攝重複性良好。

3. 轉移性邊界被釐清。  
   舊雙 basin 概念仍有參考價值，但舊門檻不能硬套新資料。這是研究上的重要限制條件，不是失敗。

建議報告標題：

「PSF 快速校正 L1 重拍穩定性驗證與新資料 operational standard 修正」

建議報告結論：

「本月完成新拍攝資料下的 L0/L1 驗證。結果顯示三次相同條件重拍造成的係數差異低於同一批影像重複擬合的自然波動，代表短期拍攝重複性可接受。然而，新資料的擬合型態分布與舊 L0 reference basin 不完全一致，因此後續歸因流程應以新資料重新建立 operational threshold，而非直接套用舊門檻。」

## 7. 驗證狀態

快速回歸測試：

`python -m pytest tests\python\test_quick_recalibration_l0_newdata.py -q`

最近一次檢查結果：14 passed。

## 8. 上傳提醒

若只能上傳少量檔案，最小組合為：

1. 這份 handoff：  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\PSF_UPLOAD_HANDOFF_20260623_TW.md`

2. 完整檔案索引 CSV：  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\PSF_UPLOAD_FILE_MANIFEST_20260623.csv`

3. 上月月報 PDF：  
   `C:\Users\Rio\OneDrive\學業\碩班\均華報告\GMM五月月報.pdf`

4. 三個結果 JSON：  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L0_newdata\L0_newdata_summary.json`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_newdata\L1_newdata_summary.json`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_paired_frame_check\paired_frame_summary.json`

5. paired-frame CSV：  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\L1_paired_frame_check\paired_frame_metrics.csv`

6. 舊 L0 對照：  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\all_sets_comparison.json`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\archive_L0_legacy_20260616\cross_set_results\outputs\reference_basins.json`

7. 分析腳本：  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\l0_newdata_analysis.py`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\l1_newdata_analysis.py`  
   `D:\GMM_2_Final\PSF_Fitting\quick_recalibration\validation_experiments\paired_frame_analysis.py`

