# 四組位移實驗 Raw 鎖定、V42 盲化稽核

## 方法

四組資料固定追蹤同一組具有 SEM 尺寸的中心九顆圓柱。入選名單只使用原始拍攝時間與 Raw 二維運動建立；名單寫入並計算雜湊後才加入 V42。候選主表固定採用 25% 命令容差，代表 Raw 篩選後與平台命令一致的步數，沒有依 V42 結果挑選母體。

## 候選主表

| 資料組 | Raw有效/總步 | 配對步 | Raw SD (nm) | V42 SD (nm) | 穩定性 | Raw九圓柱 (nm) | V42九圓柱 (nm) | 局部一致性 |
|---|---:|---:|---:|---:|---|---:|---:|---|
| 50x_x_0p5um | 48/50 | 48 | 8.15 | 6.03 | improved | 12.86 | 4.31 | improved |
| 50x_x_1um | 48/49 | 48 | 11.08 | 7.84 | improved | 12.13 | 3.82 | improved |
| 20x_0p5um | 40/49 | 32 | 24.84 | 22.83 | improved | 25.31 | 10.88 | improved |
| 20x_1um | 49/49 | 49 | 26.74 | 24.17 | improved | 21.54 | 8.62 | improved |


## 解讀原則

完整批次內母體、25% Raw 篩選平台一致母體與正常拍攝節奏母體均保留在表格中。只有固定的25% Raw 篩選平台一致母體是候選主表；其他母體不得因結果較漂亮而取代它。20%、25%、30%三個門檻的方向若不一致，報告會標記為不穩健。

平台命令是名義參考，不是獨立位置真值。本稽核只能支持重複性、平台運動合理性與九圓柱局部一致性比較。

## 固定規則排除明細

- `50x_x_0p5um`：27 (cross_acquisition_session), 31 (cross_acquisition_session)。
- `50x_x_1um`：1 (cross_acquisition_session)。
- `20x_0p5um`：15 (raw_x_command_incomplete;raw_y_cross_axis_excess), 41 (not_all_nine_raw_boundary), 42 (not_all_nine_raw_boundary), 43 (not_all_nine_raw_boundary), 45 (not_all_nine_raw_boundary;raw_x_command_incomplete;raw_y_cross_axis_excess), 46 (not_all_nine_raw_boundary;raw_x_command_incomplete;raw_y_cross_axis_excess), 47 (not_all_nine_raw_boundary), 48 (raw_boundary_invalid;not_all_nine_raw_boundary), 49 (not_all_nine_raw_boundary)。
- `20x_1um`：無排除步，全部保留。

## 門檻穩健性

- `50x_x_0p5um`：20/25/30% 分別保留 48/48/48 步；位移穩定性方向為 improved, improved, improved；九圓柱一致性方向為 improved, improved, improved。
- `50x_x_1um`：20/25/30% 分別保留 48/48/48 步；位移穩定性方向為 improved, improved, improved；九圓柱一致性方向為 improved, improved, improved。
- `20x_0p5um`：20/25/30% 分別保留 38/40/40 步；位移穩定性方向為 improved, improved, improved；九圓柱一致性方向為 improved, improved, improved。
- `20x_1um`：20/25/30% 分別保留 49/49/49 步；位移穩定性方向為 improved, improved, improved；九圓柱一致性方向為 improved, improved, improved。
