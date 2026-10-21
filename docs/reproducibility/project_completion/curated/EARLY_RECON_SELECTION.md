# 早期重建影像：看得懂取捨，也不必下載整套輸出

這份整理只處理R33至COMBO形成過程的10套模型重建。它們沿用相同三尺度相機輸入，但圖中是模型輸出，不能當成相機原拍。

目前閱讀版本留下34張未改動的原BMP：每套同位置的三尺度中間影格，加上R33工具失敗的連續影格與修正後對照。完整量測、原GMF回傳和方法圖保留，未只挑成功圖。

整套2,030張約5.64GB的重建序列改由固定歷史版本查找，閱讀版只需約91.4MB的代表影像。這是目前檔案內容變輕；既有Git歷史和本機／H原件保留，不宣稱已釋放GitHub歷史容量。沒有刪除任何版本附件。

## 先看什麼

| 方法／原版本 | 為何留下 | 同位置代表圖 | 完整舊序列 |
|---|---|---|---|
| R33 contrast fix | 提高統計匹配反而壓低對比，不能當成正式R33替代。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R33ContrastFix_20260406_222404/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R33ContrastFix_20260406_222404/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R33ContrastFix_20260406_222404/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404) |
| R33 Laplacian-only p95 | 失敗支線：只截Laplacian未恢復銳度，內部步距波動反而較大。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R33RobustLoss_20260405_114824/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R33RobustLoss_20260405_114824/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R33RobustLoss_20260405_114824/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R33RobustLoss/results/lap_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_114824) |
| R33 hard p95 | 位移穩定性改善伴隨柔邊；8px兩步工具失敗保留完整原回傳。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R33RobustLoss_20260405_091941/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R33RobustLoss_20260405_091941/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R33RobustLoss_20260405_091941/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941) |
| R33 hard p95（四捨五入修復） | 位移穩定性改善伴隨柔邊；8px兩步工具失敗保留完整原回傳。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R33RobustLoss_20260405_091941_quantfix/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R33RobustLoss_20260405_091941_quantfix/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R33RobustLoss_20260405_091941_quantfix/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R33RobustLoss/results/p95_recon_quantfix/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941) |
| R33 hard p90 | 較強截尾的對照；不能借用p95的外部GMF成績。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R33RobustLoss_20260405_073906/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R33RobustLoss_20260405_073906/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R33RobustLoss_20260405_073906/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R33RobustLoss/results/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_073906) |
| R33 soft p95 | 失敗支線：柔性截尾沒有消除穩定性與銳度的取捨。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R33RobustLoss_20260405_153826/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R33RobustLoss_20260405_153826/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R33RobustLoss_20260405_153826/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R33RobustLoss/results/soft_p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_153826) |
| R38 all-stage sequence | 8px較穩但仍變柔；與R38v2修正後候選分開。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R38SeqConsistency_20260406_122842/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R38SeqConsistency_20260406_122842/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R38SeqConsistency_20260406_122842/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842) |
| R38v2 8px gate | 銳利度與位移取捨，量化修復對三尺度的影響不同。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R38v2SeqFixed_20260406_235957/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R38v2SeqFixed_20260406_235957/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R38v2SeqFixed_20260406_235957/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957) |
| R38v2 8px gate（四捨五入修復） | 銳利度與位移取捨，量化修復對三尺度的影響不同。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R38v2SeqFixed_20260406_235957_quantfix/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R38v2SeqFixed_20260406_235957_quantfix/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R38v2SeqFixed_20260406_235957_quantfix/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R38v2SeqFixed/results/8px_gate_recon_quantfix/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957) |
| COMBO | 正式基準：序列訊號篩選配合p95，仍保留所有不利尺度。 | [pitch0p01um_y_40](<../../selected_images/early_recon/R38v2SeqFixed_20260408_003525/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp>)、[pitch0p1um_y_60](<../../selected_images/early_recon/R38v2SeqFixed_20260408_003525/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp>)、[pitch1um_y_100](<../../selected_images/early_recon/R38v2SeqFixed_20260408_003525/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>) | [原203張](https://github.com/rio10255254/GMM_2_Final/tree/ff4adf9af2a1ec1bd178e6d80d864d03d34fbd94/Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525) |

## 失敗影格為什麼也保留

原R33 p95的8px結果，完整波動是0.932763px；兩次明確工具失敗剔除後才是0.153343px。失敗發生在第51→52及52→53張，不是把一般較差步伐都去掉。取整方式修正後，原報告記錄不再出現這兩個失敗，但全部步伐的波動為0.171765px。這幾個數字不能當作同一條件的單一排名。

[原計算規則與完整回傳的讀法](<../../../../Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md>)；[原量化修正報告](<../../../../Experiments/R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md>)。

下列保留原8px第51、52、53張，以及同名修正後影像；影像本身不能替代工具的完整數表。

- [修正前：VisionTop_20251029183552176.bmp](<../../selected_images/early_recon/R33RobustLoss_20260405_091941/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>)
- [修正前：VisionTop_20251029183602918.bmp](<../../selected_images/early_recon/R33RobustLoss_20260405_091941/pitch1um_y_100_odd/VisionTop_20251029183602918.bmp>)
- [修正前：VisionTop_20251029183613644.bmp](<../../selected_images/early_recon/R33RobustLoss_20260405_091941/pitch1um_y_100_odd/VisionTop_20251029183613644.bmp>)
- [修正後：VisionTop_20251029183552176.bmp](<../../selected_images/early_recon/R33RobustLoss_20260405_091941_quantfix/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp>)
- [修正後：VisionTop_20251029183602918.bmp](<../../selected_images/early_recon/R33RobustLoss_20260405_091941_quantfix/pitch1um_y_100_odd/VisionTop_20251029183602918.bmp>)
- [修正後：VisionTop_20251029183613644.bmp](<../../selected_images/early_recon/R33RobustLoss_20260405_091941_quantfix/pitch1um_y_100_odd/VisionTop_20251029183613644.bmp>)

## 完整数據與方法仍可直接閱讀

另將140份原有量測明細與摘要（約12.8MB）放進一般程式版本，包含逐張圓心、輪廓量、三尺度摘要與各分析版本；它們早已存在已發布結果附件，本次不重算、不改欄位。外部GMF原始回傳、所有既有分析圖和科學判決保持原樣。

360與720方向、IRLS與Soft-L1分析是不同量測設定，不是新增獨立訓練；原版本名稱保留。量化修復前後的GMF結果也分開。

- [R33RobustLoss原方法／結論](<../../../../Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md>)；[本輪完整量測位置](<../../../../Experiments/R33RobustLoss/results>)。
- [R33ContrastFix原方法／結論](<../../../../Experiments/R33ContrastFix/README.md>)；[本輪完整量測位置](<../../../../Experiments/R33ContrastFix/results>)。
- [R38SeqConsistency原方法／結論](<../../../../Experiments/R38SeqConsistency/reports/R38_RESULTS.md>)；[本輪完整量測位置](<../../../../Experiments/R38SeqConsistency/results>)。
- [R38v2SeqFixed原方法／結論](<../../../../Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md>)；[本輪完整量測位置](<../../../../Experiments/R38v2SeqFixed/results>)。

## 要取回全部歷史影像或重做時

表內「完整舊序列」固定在本次精簡前版本；每張原檔的大小、內容身分與原位置在EARLY_RECON_SELECTION.json.gz。歷史版本可由GitHub逐張取回，或取得該固定版本；不必先下載目前凍結的數百GB草稿。

目前代表圖集中在selected_images，不再放在原整套序列的位置，避免歷史量測程式把少數代表圖誤當完整序列。原輸出位置只留說明；要重新量測整套，須先取得完整歷史影像。

重新產生影像需要當年精確模型、同一批裁切實拍輸入、PSF及當年的取整方式。原推理程式的--weights、--input-dir、--select-mode及--recon-root須明確設定，不依賴目前預設模型或舊C槽路徑。現在程式使用四捨五入，不能冒稱直接產生修復前的每個原位元組；精確舊圖以固定歷史原件為準。

[原推理入口](<../../../../Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py>)；[R33至COMBO完整系列](<../../../../Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md>)；[已發布關鍵模型的位置](<KEY_MODEL_REFERENCES.json>)。

本次只完成這10套早期重建的精選。其他研究仍逐輪依用途整理；不把此局部成果寫成全專案完成。
