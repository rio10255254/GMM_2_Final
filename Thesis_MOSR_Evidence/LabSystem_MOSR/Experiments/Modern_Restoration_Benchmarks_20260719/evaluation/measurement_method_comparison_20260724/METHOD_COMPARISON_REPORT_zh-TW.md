# 位移邊界量測方法比較

## 資料完整性

- 舊法原始列數：960；新法原始列數：960。
- 四方法共同有效的舊法資料為 952 列；新法為 960 列。
- 新舊方法可逐步配對的資料為 952 列。
- 重複主鍵：舊法 0，新法 0。

## 方法判讀

- 舊法以左右邊緣最大灰階斜率的中點定位，對單一而平滑的邊緣很直接，但較容易受到振鈴或多重斜率峰影響。
- 新法以30%、40%、50%、60%與70%局部對比交點的中位數定位，與CD的跨閾值邊界定義一致，也能直接檢查閾值敏感度。
- 是否採用新法不能只看MOSR排名；本資料包同時保留實拍結果、合成已知位移測試與新舊方法配對差異。

## 新法的實拍結果

- 50x pillar：MOSR 2.775 nm < EDSR 2.985 nm < Raw 3.015 nm < NAFNet 3.925 nm。
- 20x pillar：EDSR 10.414 nm < MOSR 10.859 nm < Raw 11.133 nm < NAFNet 15.798 nm。
- 50x via：Raw 3.000 nm < MOSR 3.146 nm < EDSR 3.169 nm < NAFNet 3.422 nm。
- 20x via：EDSR 8.938 nm < Raw 9.167 nm < NAFNet 9.902 nm < MOSR 10.269 nm。

## EDSR與MOSR配對比較

- original_gradient／50x pillar：EDSR較低，差值 0.342 nm，95%區間 [-0.763, 0.079] nm。
- original_gradient／20x pillar：EDSR較低，差值 0.181 nm，95%區間 [-1.556, 1.211] nm。
- original_gradient／50x via：EDSR較低，差值 0.049 nm，95%區間 [-0.407, 0.329] nm。
- original_gradient／20x via：EDSR較低，差值 1.494 nm，95%區間 [-2.560, -0.417] nm。
- new_isocontour／50x pillar：MOSR較低，差值 0.210 nm，95%區間 [-0.135, 0.558] nm。
- new_isocontour／20x pillar：EDSR較低，差值 0.445 nm，95%區間 [-1.697, 0.797] nm。
- new_isocontour／50x via：MOSR較低，差值 0.023 nm，95%區間 [-0.311, 0.365] nm。
- new_isocontour／20x via：EDSR較低，差值 1.331 nm，95%區間 [-2.455, -0.225] nm。

## 合成已知位移檢查

- original_gradient，振鈴強度 0.0：有效率 100.0%，MAE 0.0270 px，P95 0.1207 px。
- new_isocontour，振鈴強度 0.0：有效率 100.0%，MAE 0.0073 px，P95 0.0241 px。
- original_gradient，振鈴強度 0.8：有效率 100.0%，MAE 0.0228 px，P95 0.1124 px。
- new_isocontour，振鈴強度 0.8：有效率 100.0%，MAE 0.0079 px，P95 0.0264 px。
- original_gradient，振鈴強度 1.6：有效率 100.0%，MAE 0.0199 px，P95 0.0772 px。
- new_isocontour，振鈴強度 1.6：有效率 100.0%，MAE 0.0096 px，P95 0.0338 px。

## 初步結論

- 新法在量測定義上較容易說明與稽核，建議作為邊界位置的主要候選；舊法保留為獨立敏感度檢查。
- 新法讓MOSR在50倍pillar成為最低平均絕對誤差，但沒有讓MOSR在所有倍率與形貌都領先。
- 因此，若後續寫入論文，應把選法理由建立在邊界定義與合成驗證，而不是建立在單一模型排名。

## 舊法摘要（核對用）

- 50x pillar：EDSR 2.868 nm < MOSR 3.210 nm < NAFNet 3.491 nm < Raw 6.116 nm。
- 20x pillar：EDSR 9.526 nm < MOSR 9.707 nm < Raw 12.588 nm < NAFNet 17.928 nm。
- 50x via：EDSR 3.068 nm < MOSR 3.117 nm < NAFNet 3.522 nm < Raw 5.531 nm。
- 20x via：EDSR 8.913 nm < Raw 9.098 nm < NAFNet 10.271 nm < MOSR 10.408 nm。
