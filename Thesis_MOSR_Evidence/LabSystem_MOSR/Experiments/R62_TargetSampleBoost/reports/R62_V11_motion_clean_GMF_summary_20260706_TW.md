# R62 V11 motion-clean GMF summary (2026-07-06)

## 這輪想驗證什麼

這輪不是再盲目長訓練，而是先檢查一件很具體的事：

「R62 訓練資料裡的真實連續位移 pair，是否混入了平台本身跳動的壞步，導致模型被錯誤位移標籤教壞？」

如果這是真的，合理策略是先建立一份乾淨資料包，再用同一個 V7 訓練策略做短訓練，觀察 GMF 位移穩定性是否明顯改善。

## 發現的資料問題

使用 100MG 的 Raw GMF pairwise 結果回查訓練 manifest 後，確認 x_0p5um 序列有兩個壞步：

| sequence | bad step | dx um | dy um | reason |
|---|---:|---:|---:|---|
| 20260702_100MG / x_0p5um | 27 | 0.865540 | 0.788527 | dx 過大 + y 方向大飄 |
| 20260702_100MG / x_0p5um | 31 | 0.577166 | 0.123953 | y 方向大飄 |

把壞步前後各一幀也排除後，訓練資料中受影響的幀是：

`26, 27, 28, 30, 31, 32`

受影響訓練 pair：

| risk type | count | 白話意思 |
|---|---:|---|
| direct_label_conflict | 24 | 真實連續位移 pair 仍被標成固定 0.5um，這是最可疑的錯標籤 |
| source_texture_only | 12 | self-shift 用到壞步附近影像當底圖，但位移是人工 shift，風險較低 |
| affected_context | 30 | 同幀偽邊界資料，沒有直接錯位移，但為了乾淨先移除 |
| total | 66 | 從 7760 筆中移除 |

稽核工具輸出：

`D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R62_TargetSampleBoost\reports\r62_motion_training_data_audit_20260706`

## 建立的乾淨資料包

新資料包：

`D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Training_Data\r62_target_sample_boost\hs100mg_basler\r62_target_sample_boost_v4_motion_clean`

資料數量：

| item | count |
|---|---:|
| original pairs | 7760 |
| kept pairs | 7694 |
| removed pairs | 66 |

已驗證：

1. manifest 總數是 7694。
2. src / lbl / geom 三種主檔案也都是 7694。
3. 66 筆被標記的 source 影像，在新包裡都不存在。
4. group split overlap = 0。

## V11 訓練設計

V11 的目的不是發明新策略，而是做公平測試：

「沿用 V7 訓練策略，只把資料包從 v3 換成 v4 motion-clean。」

V11 candidate：

`r62_target_selfshift_motion_clean_v11`

短訓練起點：

V7 best checkpoint

短訓練設定：

1 epoch，最多 300 train batches，batch size 8。

訓練輸出：

`D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_motion_clean_v11_v11_motion_clean_from_v7_probe_e1_mtb300_b8_20260706_20260706_031435`

重要注意：

`best_tradeoff.pth.tar` 是 epoch 0 baseline，不是訓練後權重。真正短訓練後的權重是 `latest.pth.tar`。

## 一般亮度型 GMF 結果

這是用原本的 GMF-like pairwise，直接在亮暗結構上做擬合。

### 100MG 主資料

| group | Raw std um | V7 std um | V11 latest std um | V11 vs Raw | 判斷 |
|---|---:|---:|---:|---:|---|
| x_1um | 0.009536 | 0.009362 | 0.009441 | +0.995% | V11 有小改善，但不如 V7 |
| x_0p5um | 0.052563 | 0.052373 | 0.052428 | +0.257% | V11 有小改善，但不如 V7 |

### 20x / 5x guardrail

| group | Raw std um | V7 std um | V11 latest std um | V11 vs Raw | 判斷 |
|---|---:|---:|---:|---:|---|
| 20x_1um | 0.025065 | 0.025344 | 0.025738 | -2.685% | 變差 |
| 20x_0p5um | 0.076356 | 0.077201 | 0.077314 | -1.254% | 變差 |
| 5x_1um | 0.160710 | 0.158132 | 0.160442 | +0.167% | 幾乎沒差 |
| 5x_0p5um | 0.012163 | 0.025546 | 0.021534 | -77.049% | 比 Raw 差很多，但比 V7 稍微好 |

結論：

V11 motion-clean 不能作為長訓練主線。它沒有超過 V7，而且 guardrail 不穩。

## 邊界型 GMF 結果

這輪另外把 GMF-like 演算法加上 edge signal mode。意思是不用亮暗面積當中心，而是用邊界梯度當擬合訊號，較貼近「邊界重建是否有助於定位」。

### 100MG 主資料

| group | Raw std um | V7 std um | V11 latest std um | best | 判斷 |
|---|---:|---:|---:|---|---|
| x_1um | 0.009449 | 0.009017 | 0.009385 | V7 | 邊界型 GMF 下 V7 明顯最好 |
| x_0p5um | 0.052380 | 0.052086 | 0.052226 | R61 | V11 仍不是最好 |

### 20x / 5x guardrail

| group | Raw std um | V7 std um | V11 latest std um | V11 vs Raw | 判斷 |
|---|---:|---:|---:|---:|---|
| 20x_1um | 0.025650 | 0.028575 | 0.028659 | -11.732% | 變差 |
| 20x_0p5um | 0.077762 | 0.077134 | 0.077738 | +0.030% | 幾乎沒差 |
| 5x_1um | 0.162830 | 0.170495 | 0.166962 | -2.538% | 變差 |
| 5x_0p5um | 0.021653 | 0.042002 | 0.024358 | -12.496% | 仍差於 Raw |

結論：

邊界型 GMF 確實比較能看到 V7 在 100MG x_1um 的優勢，但 V11 沒有帶來突破。

## 目前判斷

1. 訓練資料確實有小規模污染，且污染剛好在 0.5um 這種關鍵位移資料上。
2. 但是只清掉壞步並沿用 V7 策略，沒有讓模型大幅變強。
3. V11 不值得直接長訓練。
4. 若要繼續追「論文好結果」，下一步比較有料的是：
   - 以 V7 為目前主力模型。
   - 保留乾淨資料包作為基礎。
   - 訓練目標要改成更直接的定位穩定目標，而不是只靠重建圖像外觀。
   - GMF 驗證要同時報亮度型與邊界型，因為邊界型更貼近論文主張。

