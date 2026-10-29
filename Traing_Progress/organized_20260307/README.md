# 20260307 測試區總說明

## 這個資料夾的定位

`Traing_Progress/organized_20260307/` 是從 2026-03-07 開始的新測試區。

> 2026-08-01 storage note：封存前完整批次已逐檔核對保存到 H 槽。D 槽保留 `selected/` 代表模型、種子與原始說明；大型 `rejected/` 歷史由 H 槽保存。完整位置及恢復方法見 `ARCHIVE_POINTER.md`。這項存放變更不改寫當時結論。

用途：
- 收納後續新的訓練測試
- 收納對應的重建輸出
- 收納外部 GMF 定位程式產生的 `GMF_score.txt`
- 收納我根據 `GMF_score.txt` 做出的步長統計與評估報告

這樣做的目的是把：
- `20260306`：已採用、已凍結的基準版
- `20260307`：後續持續測試與比較

明確分開，避免新舊結果混在一起。

## 目前外部驗證入口

`0307` 這邊現在主要保留的是「內部 seed 搜索與 autotune 歷史」。

從 `2026-03-09` 開始，外部驗證入口已切到：

- `Traing_Progress/organized_20260309/external_validation/current_seed/`

目前外部驗證說明：

- [external_validation/current_seed/README.md](../organized_20260309/external_validation/current_seed/README.md)
- [external_validation/current_seed/CURRENT_TARGET.json](../organized_20260309/external_validation/current_seed/CURRENT_TARGET.json)

## 目前的基準版是什麼

目前的基準版仍然是 `20260306` 採用的 `step8_curve_sharp`。

- 基準 run：
  - `Traing_Progress/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332`
- 基準權重：
  - `Traing_Progress/organized_20260306/selected/runs/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_AUTO_FINAL_step8_curve_sharp_20260306_200332/weights/best_tradeoff.pth.tar`

後續在 `20260307` 的所有新測試，都是拿這一版當比較基準。

## 0307 目前的內部續訓種子

`20260307` round1 已完成整理。

目前保留作為「後續續訓 seed」的版本是：

- `selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625`
- 權重：
  - `selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`

這個版本的定位是：
- 它是 0307 round1 內部 autotune 的最佳 sweep 候選
- 用來作為後續 round2/round3 的續訓起點
- 它不是目前手動推理的正式採用版

也就是說：
- 手動重建 / 外部 GMF 比較基準，仍然看 `20260306`
- `20260307 selected/` 目前代表「繼續優化時優先延伸的 seed」

## 你和我的分工

### 我負責
- 修改訓練 / 推理 / autotune 程式
- 進行新一輪訓練或重建
- 整理每一輪的輸出與報告
- 讀取你提供的 `GMF_score.txt` 後，計算位移步長統計
- 根據統計結果判斷該版本是保留、拒絕或歸檔

### 你負責
- 在我重建完成後，使用外部 GMF 程式跑定位
- 把外部程式產生的 `GMF_score.txt` 提供給我

原因很直接：
- 我可以處理重建、訓練、整理、統計
- 但你目前的外部 GMF 定位程式是在我的工作區之外執行，所以這一步仍然需要你操作

## 評估主目標

主目標不是只有影像變銳利，而是：

1. `POSY` 位移步長的平均值要接近 `8 px`
2. `POSY` 位移步長的標準差要盡量小
3. `P05-P95 span` 要盡量收斂
4. 同時畫面邊界仍要看起來真實、不要糊、不要假銳化

換句話說：
- 第一優先是定位穩定度，尤其是步長標準差
- 第二優先才是視覺上的銳利與真實感

## 你目前提供的實際測試流程

目前你實際使用的流程是：

1. 用推理程式重建：
   - `C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output`
2. 資料集共有 `200` 張
3. 你只重建奇數張，因為奇數張對應到有位移的影像
4. 重建結果再丟到外部 GMF 程式
5. 外部程式輸出：
   - `E:\GMM_Software\GmmVisionToolExe_20260107\GMF_score.txt`
6. 我再根據這個檔案去計算 `POSY` 的步長統計

如果後續流程不變，這就是 `20260307` 的標準評估方式。

## 目錄結構

### `pending/`
放「正在測、還沒有做最終判定」的東西。

子目錄用途：
- `runs/`
  - 新訓練 run 或候選 run
- `reconstructions/`
  - 某一版權重對某個資料集的重建輸出
- `gmf_results/`
  - 外部程式輸出的 `GMF_score.txt`
  - 以及我後續整理的統計結果
- `reports/`
  - 針對該輪測試寫的 md / json 報告
- `logs/`
  - autotune / train / infer 的 console log

### `selected/`
放目前值得保留的重點結果。

在 `20260307` 這一區，`selected/` 不等於「已取代 20260306 正式採用版」。

目前它代表：
- 已完成內部整理
- 值得拿來做後續續訓或深入比較
- 但尚未經過你外部 GMF 流程驗證到足以正式升級

### `rejected/`
放已經確認不採用的結果，但仍保留作比較依據。

### `archive/`
放更早期的歷史測試資料，避免工作區太亂。

## 建議命名規則

為了讓之後每一輪都能直接比對，建議採用以下命名：

### 重建輸出資料夾
格式：

```text
recon_<候選名>_<資料集名>_<YYYYMMDD_HHMMSS>
```

例如：

```text
recon_step8_curve_sharp_Pitch1um_Y_100_20260307_143000
```

### GMF 結果資料夾
格式：

```text
gmf_<候選名>_<資料集名>_<YYYYMMDD_HHMMSS>
```

內部至少保留：
- `GMF_score.txt`
- `GMF_POSY_stats.md`
- `GMF_POSY_stats.json`

### 評估報告
格式：

```text
eval_<YYYYMMDD>_<候選名>_<資料集名>.md
```

## 你之後怎麼用這個結構

### 情境 1：我先重建，你再跑外部 GMF
- 我先把重建輸出放到：
  - `pending/reconstructions/`
- 你跑完外部 GMF 後，把 `GMF_score.txt` 對應放到：
  - `pending/gmf_results/`
- 我再根據統計決定：
  - 如果更好，移到 `selected/`
  - 如果退步，移到 `rejected/`

### 情境 2：我先做新一輪訓練
- 新 run 先放：
  - `pending/runs/`
- 該輪說明與結果先放：
  - `pending/reports/`
- 等你提供外部 GMF 評估後，再決定升級或淘汰

## 補充說明

- `organized_20260306/` 不再拿來塞新測試，只保留作基準版與歷史比較。
- 如果後面 `20260307` 測試很多，我會再幫你把其中已完成的部分分批歸檔，不會讓資料夾無限制膨脹。
