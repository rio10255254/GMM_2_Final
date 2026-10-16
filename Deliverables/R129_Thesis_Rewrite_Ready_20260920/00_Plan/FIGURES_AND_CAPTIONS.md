# 圖表與圖說準備

正式Word編號依排版更新；F01–F10為備稿識別。四張新方法／訓練圖已備PNG與SVG，輪廓起末圖亦備向量版。

## F01 MOSR重建與共同量測流程
建議位置：4.4。 [圖檔](../05_Paper_Figures/F01_model_and_measurement.png)

單張觀測影像先經實測光學處理，再由共享參數的程序修正四次，最後將受限細節加入原圖。原圖及重建影像以相同ACM與取邊流程量測。SEM與平台讀值屬外部參照。

判讀範圍：方法示意，不是模組消融或精度證明
來源：`package-local hybrid.py, optics.py, reconstruction.py, output_policy.py`

## F02 合成訓練資料範例
建議位置：4.5／5.4。 [圖檔](../05_Paper_Figures/F02_training_examples.png)

每列為一種資料類別，依序為觀測影像A、乾淨目標A及已知平移的觀測影像B。顯示中央128×128區域；輸入依第一循環雜訊設定重建，與當時實際訓練紀錄一致。各類別選編號最小的訓練母場景。

判讀範圍：這些是生成的訓練資料，不是真實SEM答案；B圖不是A圖的重建結果
來源：`03_Dataset/example_sources.json`

## F03 接續訓練與開發資料的變化
建議位置：5.4／6.2.1。 [圖檔](../05_Paper_Figures/F03_training_and_development.png)

左圖為每128次更新的訓練目標平均，右圖為固定128個開發母場景的平均目標。橫軸從本次接續訓練開始計算，不包含先前初始化訓練。

判讀範圍：生成資料的目標下降不能直接稱真實量測改善；兩圖群體不同
來源：`02_Method_and_Training/training_curve_all_steps.csv; development_curve.csv`

## F04 ACM粗輪廓與最後量測邊界
建議位置：4.7／6.2.3。 [圖檔](../05_Paper_Figures/F04_ACM_and_final_boundary.png)

同一首掃描、首張、第一顆物件，兩欄分別為原圖與MOSR重建。黃虛線為保存的ACM粗輪廓，藍線為沿法線尋找最大灰階梯度後的量測點連線。兩欄使用相同灰階範圍與像素位置。

判讀範圍：示意取邊步驟，不是SEM真值或30次統計；未重新平滑邊界
來源：`05_Paper_Figures/example_source/provenance.json`

## F05 修正後九顆取樣位置
建議位置：5.2／6.2.2。 [圖檔](../05_Paper_Figures/F05_selected_nine.png)

選取十字交界附近固定3×3九顆，追蹤由原始影像決定；新九顆與舊中央九顆分開。

判讀範圍：位置修正不是按模型成績挑選物件
來源：`04_Results/R129_Handoff/03_Sampling_and_SEM/selected_nine.png`

## F06 位移平均差距與重拍波動
建議位置：6.2.5。 [圖檔](../05_Paper_Figures/F06_displacement_mean_sd.png)

曲線為30次掃描在固定位置的平均影像位移減PI回授值，陰影為±1樣本標準差。左圖為相鄰約1μm短步，右圖為距起點約1–30μm。主讀值由九顆圓心差分量中位數得到。

判讀範圍：陰影不是95%總不確定度；九顆合併成績不能稱每顆的絕對定位精度
來源：`04_Results/R129_Handoff/01_Raw_R129_Comparison/overlay_mean_sd_plot_data.csv`

## F07 起始位置30次輪廓疊合
建議位置：6.2.4。 [圖檔](../05_Paper_Figures/F07_contours_start.png)

九顆在位置0的30次輪廓；各次只扣除自己的圓心，保持相同尺度，不縮放或旋轉。原圖灰色，MOSR藍色。使用原始64個取邊點。

判讀範圍：輪廓集中表示讀取重複性，不等於已知真邊界
來源：`04_Results/R129_Handoff/04_Verification_and_Sources/centers`

## F08 末端位置30次輪廓疊合
建議位置：6.2.4。 [圖檔](../05_Paper_Figures/F08_contours_end.png)

與起點圖使用相同物件、尺度與畫法，展示位置30的30次重拍輪廓。

判讀範圍：起點與終點是固定展示位置，不按結果選最好案例
來源：`04_Results/R129_Handoff/04_Verification_and_Sources/centers`

## F09 尺寸平均值與重拍波動
建議位置：6.2.4。 [圖檔](../05_Paper_Figures/F09_diameter_and_SEM.png)

左圖為九顆平均直徑及SEM集合參照，右圖為各位置的尺寸重拍波動。穩定性與SEM平均差距分別呈現。

判讀範圍：平均尺寸差不是逐顆平均絕對誤差；參照尺度等不確定度未完全納入
來源：`04_Results/R129_Handoff/01_Raw_R129_Comparison/diameter_by_position_62.csv`

## F10 SEM與光學輪廓對照
建議位置：6.2.4。 [圖檔](../05_Paper_Figures/F10_SEM_contours_inferred.png)

黑線為既有SEM，灰線為原圖、藍線為MOSR。逐顆對應採目前左右鏡像工作推定，另一方向的比較數值另表保留。

判讀範圍：方向不是唯一確認；去平均半徑的形狀結果不可改稱完整輪廓準確度
來源：`04_Results/R129_Handoff/01_Raw_R129_Comparison/SEM_direction_sensitivity.csv`
