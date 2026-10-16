# v19 圖表索引與建議圖說

## 一、位移改善實驗

| 檔名 | 建議圖說 | 建議用途 |
|---|---|---|
| `01_50x_x_0p5um_step_trace` | 50 倍、0.5 µm 位移序列之 Raw、Wiener 與 MOSR 逐步量測結果。虛線為 PI 平台實際回授位移，各方法皆使用相同的 30 個相鄰影格。 | 主要結果 |
| `02_50x_x_1um_step_trace` | 50 倍、1.0 µm 位移序列之 Raw、Wiener 與 MOSR 逐步量測結果。各點代表九顆 pillar 邊界位移的穩健集中值。 | 主要結果 |
| `03_20x_0p5um_step_trace` | 20 倍、0.5 µm 位移序列之 Raw、Wiener 與 MOSR 逐步量測結果。橫軸為實際納入分析的 30 步。 | 主要結果 |
| `04_20x_1um_step_trace` | 20 倍、1.0 µm 位移序列之 Raw、Wiener 與 MOSR 逐步量測結果。虛線為 PI 平台實際回授位移。 | 主要結果 |
| `05_sequence_displacement_mae` | 四組位移序列相對於 PI 平台實際回授位移的平均絕對誤差。較低數值表示量測結果較接近平台回授值。 | 整體準確度摘要 |
| `06_sequence_step_sd` | 四組位移序列的逐步位移標準差。較低數值表示連續影格間的量測波動較小。 | 穩定度摘要 |
| `07_sequence_within_grid` | 四組位移序列中九顆 pillar 的位移離散度。較低數值表示同一影格內各 pillar 的邊界定位較一致。 | 九宮格一致性摘要 |

## 二、消融實驗

| 檔名 | 建議圖說 | 建議用途 |
|---|---|---|
| `01_shift_safe_within_grid_effect` | 以一般上採樣取代抗混疊上採樣後，九顆 pillar 位移離散度的變化。正值代表移除抗混疊設計後一致性變差；誤差棒為兩次獨立訓練結果所估得的 95% 區間。 | 支持抗混疊上採樣 |
| `02_shift_safe_mae_effect` | 以一般上採樣取代抗混疊上採樣後，位移平均絕對誤差的變化。正值代表移除該設計後，量測結果偏離平台回授值。 | 支持抗混疊上採樣 |
| `03_50x_x_0p5um_upsampling_step_trace` | 50 倍、0.5 µm 序列中抗混疊上採樣與一般上採樣的逐步位移比較。陰影表示兩次獨立訓練結果的範圍。 | 代表序列 |
| `04_50x_x_1um_upsampling_step_trace` | 50 倍、1.0 µm 序列中抗混疊上採樣與一般上採樣的逐步位移比較。 | 補充結果 |
| `05_20x_0p5um_upsampling_step_trace` | 20 倍、0.5 µm 序列中抗混疊上採樣與一般上採樣的逐步位移比較。 | 補充結果 |
| `06_20x_1um_upsampling_step_trace` | 20 倍、1.0 µm 序列中抗混疊上採樣與一般上採樣的逐步位移比較。 | 補充結果 |
| `07_raw_position_anchor_20x_cd_effect` | 移除原始影像位置錨定後，20 倍 pillar CD 中位絕對誤差的增加量。圓點與誤差棒表示平均效果及 95% 區間，藍點為兩次獨立訓練結果。 | 支持位置錨定 |
| `08_raw_position_anchor_20x_per_pillar_cd` | 完整模型與移除原始影像位置錨定後，各 pillar 的 CD 絕對誤差比較。誤差棒表示兩次獨立訓練結果之間的差異。 | 顯示各結構的一致效果 |

## 三、多模型比較實驗

| 檔名 | 建議圖說 | 建議用途 |
|---|---|---|
| `01_pillar_50x_x_0p5um_model_step_trace` | 50 倍、0.5 µm pillar 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | pillar 主要結果 |
| `02_pillar_50x_x_1um_model_step_trace` | 50 倍、1.0 µm pillar 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | pillar 主要結果 |
| `03_pillar_20x_0p5um_model_step_trace` | 20 倍、0.5 µm pillar 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | pillar 主要結果 |
| `04_pillar_20x_1um_model_step_trace` | 20 倍、1.0 µm pillar 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | pillar 主要結果 |
| `05_via_50x_x_0p5um_model_step_trace` | 50 倍、0.5 µm via 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | via 泛化結果 |
| `06_via_50x_x_1um_model_step_trace` | 50 倍、1.0 µm via 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | via 泛化結果 |
| `07_via_20x_0p5um_model_step_trace` | 20 倍、0.5 µm via 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | via 泛化結果 |
| `08_via_20x_1um_model_step_trace` | 20 倍、1.0 µm via 序列之 Raw、NAFNet、EDSR-x1 與 MOSR 逐步位移比較。 | via 泛化結果 |
| `09_model_displacement_mae` | 不同形貌與倍率下，各模型相對於 PI 平台實際回授位移的平均絕對誤差。 | 準確度總覽 |
| `10_model_within_grid` | 不同形貌與倍率下，各模型對九顆結構量得之位移離散度。 | 穩定度總覽 |
| `11_model_edge_width` | 不同形貌與倍率下，各方法的平均邊界過渡寬度。較低數值表示邊界灰階轉換較集中。 | 銳利度比較 |
| `12_model_full_frame_runtime` | NAFNet、EDSR-x1 與 MOSR 對單張完整影像的推論時間。 | 運算速度 |
| `13_model_gpu_memory` | NAFNet、EDSR-x1 與 MOSR 處理完整影像時的峰值 GPU 記憶體需求。 | 硬體需求 |
| `14_model_parameter_count` | NAFNet、EDSR-x1 與 MOSR 的模型參數量。 | 模型規模 |
| `15_model_cd_median_abs_error` | 50 倍與 20 倍之 pillar、via 在統一量測規則下的 CD 中位絕對誤差。各方法共用 Raw 影像固定的九顆結構中心，並合併 35% 至 65% 門檻與兩種剖面量測結果。 | CD 主要摘要 |
| `16_model_cd_mean_abs_error` | 50 倍與 20 倍之 pillar、via 在統一量測規則下的 CD 平均絕對誤差。 | CD 補充摘要 |
| `17_50x_pillar_cd_range` | 50 倍九顆 pillar 的 SEM 參考直徑與各方法量測結果。符號為多門檻結果的中位數，誤差棒為同一結構於全部門檻與剖面方向所得範圍。 | 50 倍 pillar 細節 |
| `18_20x_pillar_cd_range` | 20 倍九顆 pillar 的 SEM 參考直徑與各方法量測結果。 | 20 倍 pillar 細節 |
| `19_50x_via_cd_range` | 50 倍九顆 via 的 SEM 參考直徑與各方法量測結果。 | 50 倍 via 細節 |
| `20_20x_via_cd_range` | 20 倍九顆 via 的 SEM 參考直徑與各方法量測結果。 | 20 倍 via 細節 |

## 四、保留既有圖

| 檔名 | 內容 | v19 建議 |
|---|---|---|
| `00a_50x_full_fov_pillar_locator.png` | 50 倍視野及 pillar 九宮格位置 | 保留，用於說明取樣位置 |
| `00b_20x_full_fov_pillar_locator.png` | 20 倍視野及 pillar 九宮格位置 | 保留，用於說明取樣位置 |
| `00c_signed_pillar_contrast.png` | 兩倍率下 pillar 明暗極性檢查 | 可移至補充說明 |
| `01_50x_raw_center9.png` | 50 倍 Raw pillar 九宮格 | 保留 |
| `02_50x_v42_center9.png` | 50 倍 MOSR pillar 九宮格 | 保留 |
| `02a_50x_wiener_center9.png` | 50 倍 Wiener pillar 九宮格 | 保留 |
| `03_50x_pillar_edge_profile.png` | 50 倍 pillar 徑向邊界剖面 | 保留，圖說改為中文 |
| `04_20x_raw_center9.png` | 20 倍 Raw pillar 九宮格 | 保留 |
| `05_20x_v42_center9.png` | 20 倍 MOSR pillar 九宮格 | 保留 |
| `05a_20x_wiener_center9.png` | 20 倍 Wiener pillar 九宮格 | 保留 |
| `06_20x_pillar_edge_profile.png` | 20 倍 pillar 徑向邊界剖面 | 保留，圖說改為中文 |
| `07_center9_cd_per_pillar.png` | 九顆 pillar 在不同門檻下的 CD 範圍 | 可作 CD 靈敏度說明 |
| `08_center9_cd_error_summary.png` | CD 穩健中位絕對誤差摘要 | 保留 |
| `09a_cd_threshold_sensitivity_horizontal.png` | 水平剖面 CD 對門檻的敏感度 | 補充圖 |
| `09b_cd_threshold_sensitivity_radial.png` | 徑向平均 CD 對門檻的敏感度 | 補充圖 |
| `18a_50x_wiener_psf_distance_robustness.png` | 50 倍 PSF 校正距離對位移誤差的影響 | 保留 |
| `18b_20x_wiener_psf_distance_robustness.png` | 20 倍 PSF 校正距離對位移誤差的影響 | 保留 |
| `23_20x_noncalibration_cd_range.png` | 20 倍非校正影格的 CD 範圍 | 泛化補充 |
| `23_training_loss_components.png` | MOSR 訓練期間各損失項變化 | 方法訓練補充 |
| `24_20x_noncalibration_cd_error_summary.png` | 20 倍非校正影格的 CD 誤差摘要 | 泛化補充 |

## 五、建議放入 v19 的精簡組合

為避免第六章圖數過多，正文優先選擇：

1. 位移改善：四張逐步位移圖、平均絕對誤差圖與九宮格離散度圖。
2. 消融：抗混疊上採樣的整體效果圖、代表性逐步位移圖、原始影像位置錨定的 CD 效果圖。
3. 多模型比較：pillar 與 via 各選一張代表性逐步位移圖，再放位移平均絕對誤差、九宮格離散度、CD 中位絕對誤差、邊界過渡寬度及推論時間；各結構 CD 範圍圖可放在後段或附錄。
4. 其餘倍率、步距及硬體需求圖移至該節後段或附錄，正文以文字引用即可。
