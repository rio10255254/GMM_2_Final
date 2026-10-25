# Lab R61：通用邊界與位移保護，以及後來被廣泛沿用的 v16

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R60](<../R60_SEMTruthBoundaryTraining/FILE_GUIDE.md>) · [下一輪 Lab R62](<../R62_TargetSampleBoost/FILE_GUIDE.md>) · [由此起步的 V41](<../V41_Standalone/FILE_GUIDE.md>)、[V42](<../V42_SoftLabelSNR/FILE_GUIDE.md>) · [主專案的 R61 STEP 驗證](<../../../../Experiments/R61_STEP_Generalization_20260623/README.md>)

**一句話：** Lab R60 確認邊界問題主要出在訓練資料，R61 就從資料著手：保留舊資料當錨點，修正合成答案的亮暗方向，再一版一版加入位移、相機紋理和類似 Step 的合成資料，在 2026-06-23 一天內跑到 v16。v16 在自己的三道門檻（模擬邊界、真實位移、Step 樣品）都沒有過，但它保住了 Step 的尺度、改善了部分邊界，後來成為 R62、V41、V42 和 R61 ONNX 應急交付的共同起點。

| | |
|---|---|
| 結果 | **研究候選**（v16 未通過自己的三道門檻，不能升為論文結果；但被當成後續研究與應急交付的起點） |
| 時間 | 2026-06-23（v1～v16 與內部各輪都在這一天） |
| 實驗條件 | C：實驗室顯微系統的資料與 PSF；另用 6/3 的真實位移序列與 Step 樣品驗證 |
| v16 最佳權重 | `training_progress_..._r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_200020` |

主專案另有一個 [R61 STEP 驗證資料夾](<../../../../Experiments/R61_STEP_Generalization_20260623/README.md>)，那是用這個模型家族做 Step 樣品驗證的入口，不是另一份從零訓練的模型。報告裡提到的「R36」是 R61 內部的一次試跑，跟主專案找不到的 R36 不是同一個（見[兩種 R36](<../../../../docs/reproducibility/lineage/R36_IDENTITIES_20261022.md>)）。

## 在研究裡的位置

LabSystem 從 6 月初開始修實拍棋盤的角點，Lab R46～R56 一直修不好；R57～R60 改用 SEM 尺寸當答案，R60 的稽核結論是：主要失敗原因是訓練資料沒有正確表示真實邊界，不是模型本身沒用。R61 就是直接處理資料面的一輪。

## 這輪在問什麼

保留舊資料當錨點、修正合成資料的設計，能不能讓模型學到「通用的邊界修正」，在不同亮暗、不同偏移量、加上位移之後都穩定？

## 怎麼做

**第一個發現：原本的合成答案設計錯了。** R61 第一版把暗的輸入和亮的輸入都教成重建出同一個亮的答案，造成亮暗方向互相干擾，暗邊界特別不穩。修正後，暗的輸入重建暗的銳利答案、亮的輸入重建亮的；同一個幾何可以分別畫成暗和亮，但只共用邊界位置。幾何資訊直接從已知遮罩寫出，不再從畫出來的影像回推；驗證集按幾何分組，同一個幾何不會同時出現在訓練和驗證。

**一版一版加資料：** 偏移混合、次像素混合、小偏移守門、老師保留、尾端重播、失敗平衡重播、邊界轉接層、邊界位置損失、亮暗分流、位移合成、相機紋理位移……每一步的數字都在[進度報告](<reports/R61_PROGRESS_20260623.md>)裡。

**v16 的資料**（共 20,296 列）：

| 角色 | 列數 |
|---|---:|
| 舊形狀 | 800 |
| SEM 答案錨點 | 1,400 |
| 序列守門 | 1,200 |
| 通用合成 | 4,096 |
| 乾淨位移合成 | 4,800 |
| 相機紋理位移合成 | 4,800 |
| 類似 Step 的相機紋理守門合成 | 3,200 |

新加的 3,200 列「類似 Step」的資料完全是合成的，逐列確認沒有用到真實 Step 的像素或答案。v16 從 v14 的最佳權重起步，用 R39 a970 當區域老師，訓練 8 輪。

## 結果

**早期版本的邊界誤差**（模擬幻影，平均邊界誤差 px，越小越好）：

| 模型 | 1 px 偏移（全部／亮／暗） | 2 px 偏移（全部／亮／暗） |
|---|---|---|
| Lab R60 | 0.32／0.46／0.17 | 0.89／1.27／0.51 |
| R61 亮暗修正 | 0.61／0.32／0.91 | 0.25／0.17／0.33 |
| R61 偏移混合 | 0.30／0.14／0.46 | 0.28／0.36／0.20 |
| R61 次像素混合（續訓） | 0.15／0.14／0.16 | 0.59／0.60／0.58 |

偏移混合版最平衡，次像素混合版是小偏移專家，但都還不能稱為通用。

**v16 的三道門檻**：

| 門檻 | 結果 | 說明 |
|---|---|---|
| 模擬邊界（96 個案例） | 未過 | 整體平均略好於 R39、R8、v14（0.4827 px），修好了 v14 的亮邊、環形、橢圓失敗；但 0.0 px 與 0.5 px 小偏移組仍比 R39 差 |
| 6/3 真實位移序列 | 未過 | 尾段 dy 標準差 0.2765 px，比 R39 好，但比 v14 差一點，也比原圖（0.2688 px）差 |
| Step 樣品（位置 10 的中心裁切序列） | 未過 | Step 尺度保持在約 8 px；穩定度比 R39、v14 略差 |

報告第一句就寫：「v16 不能升為論文結果」；但也寫「它不是沒用」，下一步應該針對小偏移的邊界不變性與位移穩定度，而不是再加銳利度壓力。

## 讀這些數字要知道的事

1. **v16 在不同文件裡的定位不一樣，三份都是原始紀錄：**
   - [v16 驗證報告](<reports/next_round_20260623_v17_post_v16_training_handoff/V16_VALIDATION_RESULTS.md>)（6/23）：三道門檻全部未過，不能升為論文結果。
   - [主專案 R61 STEP 資料夾](<../../../../Experiments/R61_STEP_Generalization_20260623/README.md>)（6/23～24）：把 v16 的驗證稱為「目前的論文／主模型候選」，Step 樣品上的證據支持 CD 保留與位移穩定，但不能證明跨樣品通用。
   - [R61 ONNX 交付包](<../../../../Deliverables/MOSR_R61_ONNX/README.md>)：「為已驗證量測影像準備的應急交付版」，適用均華、HS100MG 這類亮環或位移影像；遇到不同材料、極低對比或完全不同形狀時，應同時保留原圖確認。
2. **一個量測方法的修正。** Step 序列原圖一開始量到約 0.74 px，後來發現那是亮度相位相關的響應太弱造成的；改用邊緣為基礎的量法，原圖也量到約 8 px，跟 1 µm 的預期尺度一致。
3. **不能說成完全獨立。** v16 的 3,400 組繼承來源（舊形狀、SEM 錨點、序列守門）與歷史幾何必須凍結匯入，不能只靠新的生成程式取代；SEM 錨點也來自同一批樣品。
4. **之後的 SEM 來源審查**限制了 R61 的獨立準確度宣稱（見主專案 R135 等輪次）。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 進度報告、v15～v17 交接、模擬幻影驗證 | 本資料夾 [reports/](<reports/README.md>)，已在 GitHub |
| v16 最佳權重與訓練紀錄（約 71 MB） | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，目前要下載約 8 GB |
| R61 ONNX 交付包（模型、光學常數、示例） | Release [`research-r61-onnx-delivery-20261021`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-r61-onnx-delivery-20261021)，約 15 MB；包內 `model.onnx` 與原電腦上的交付檔逐位元組相同 |
| v16 訓練資料的重建 | [R61 完整訓練資料重建包](<../../../../Deliverables/R61_TrainingData_Regenerator_20261004/README_TW.md>)；生成方法與 3,400 組繼承來源見[生成方法](<../../../../docs/reproducibility/GENERATION_GUIDE.md>)與 [R61 原檔對照](<../../../../docs/reproducibility/r61_regeneration_example/README.md>) |
| 程式與測試 | 本資料夾 [scripts/](<scripts>)（資料建置、啟動、驗證）、[tests/](<tests>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** R61 各版本的訓練資料在原電腦上約 117 GB、93 萬個檔案，依保存原則不上傳；雲端保存的是生成程式、必要的繼承來源與資料清單。

## 原始報告

| 報告 | 什麼時候讀 |
|---|---|
| [R61 進度報告](<reports/R61_PROGRESS_20260623.md>) | 6/23 一整天的逐版紀錄：資料、每一輪的改動與數字、真實樣品包、v16 實作 |
| [v16 驗證結果](<reports/next_round_20260623_v17_post_v16_training_handoff/V16_VALIDATION_RESULTS.md>) | 三道門檻的完整結果與下一步方向 |
| [v16 完整訓練狀態](<reports/next_round_20260623_v17_post_v16_training_handoff/V16_FULL_TRAINING_STATUS.md>) | v16 的 8 輪訓練 |
| [v15 目標](<reports/next_round_20260623_v15_step_guard/NEXT_ROUND_TARGET_PROMPT.md>)、[v16 交接](<reports/next_round_20260623_v16_handoff/V16_IMPLEMENTATION_STATUS.md>) | 當時規劃下一輪的文件，原樣保留 |
| [模擬幻影驗證](<reports/diverse_phantom_validation>) | 各候選的邊界驗證結果 |
| [GitHub 重建稽核](<reports/R61_GITHUB_REGENERATION_AUDIT_20261016.md>) | 2026-10-16 的資料重建保存核對 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R61_BoundaryGeneralizationUniversal.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
