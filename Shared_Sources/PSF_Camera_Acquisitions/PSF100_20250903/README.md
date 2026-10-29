# 正式100視野的真正上游

2026-10-22後續：原先留本機的295張已另行保存，完整395張的來源見[全批清單](COMPLETE_395_CAMERA_CATALOG.json)與[下載方法](../../../docs/reproducibility/priority_sources_20261022/README.md)。下文描述的是前一輪100張交付的範圍；歷史前處理完整重做仍未宣稱完成。

這批原拍的檔名日期是**2025年9月3日**。從原擬合結果的100個檔名反查，完整原圖找到於舊光學專案的`TestImage/ConcentricCircle`；100張在`Representative_Clusters_Output`中的副本逐張內容相同，尺寸均為5120×5120。原資料夾共有395張，本批只挑實際進入100視野擬合的100張，其餘295張留原處，並未判定可刪。

## 原拍如何走到結果

1. 原圖先按圓心位置分組，選取代表照片。原[分組程式](upstream/Other/find_and_group_circles.m)以DBSCAN分組、複製相機原檔；保留其舊路徑與參數。
2. [找圓心](upstream/Preprocessing_CircleSample/find_circle_multi_v1.m)與[原圓心紀錄](upstream/Preprocessing_CircleSample/circle_results.mat)接到[1201裁切](upstream/Preprocessing_CircleSample/crop_image_multi_v1.m)。
3. [901處理程式v1](upstream/Preprocessing_CircleSample/preprocess_v1.m)、[v2](upstream/Preprocessing_CircleSample/preprocess_v2.m)涉及置中、中心黑塊與角落處理；[頻率濾波](upstream/Denoise_Observed_Frequency.m)的現存版本只直接指定一張影像，不能冒稱已找回全部100張當年的完整批次操作。
4. 實際擬合使用的100張901×901歷史輸入原樣保存，與原拍分開；[逐張對照](SOURCE_TO_FIT.csv)連到[原100筆結果](../../../PSF_Fitting/PSF_Fitting_ValidationLab/outputs/final_candidate_full100/batch_results.csv)。
5. [正式入口](../../../PSF_Fitting/run_psf_fitting_manual.m)與[原設定](../../../PSF_Fitting/Crop_circle_FreqFiltered/Fits/formal_config.json)說明後來採用的對齊／固定傾斜版本；舊版與修正版不能混稱。

實際原拍全幅均已完整讀取。檔名日期、原圖與代表副本一致、原擬合表的檔名及來源位置是這次確認的證據；沒有因此宣稱前處理已完整重跑或原始設備紀錄完整。此處程式為現存來源快照，不能保證每一行就是當日執行版本。

額外依原圓心紀錄及原1201裁切規則讀取像素，**100張原拍都能對回保存的1201裁切，全部像素相同**，沒有寫出新影像或重跑擬合。[逐張來源核對](SAVED_CROP_TRACE.json)。兩個已找到的901處理資料夾則都沒有任何一張與正式擬合輸入逐檔相同；因此仍保留正式100張輸入，不能只憑這兩版程式便宣稱完整前處理已復原。

原MAT的1×100是儲存順序，10×10位置要依原`source_row/source_col`讀取，不能把儲存中間當作物理中心。[原位置核對](../../../docs/reproducibility/optical_calibration/SOURCE_POSITION_MAP_VERIFIED.json)。本次保留100張實際處理輸入，正是為了不讓早期前處理的版本限制阻斷後續擬合來源。

返回：[原拍總入口](../README.md)。

若要重做395張全體影像的分群挑圖，仍需本機另外295張未納入本次附件的原拍；已固定的100張及後續擬合來源不受此限制。

## 後續研究的使用界線

這100個視野連到[2026-03-27的正式PSF政策](../../../docs/policy/PSF_STANDARD_POLICY.json)：其中修正版PSF與早期經驗版保留不同身分。保存原拍讓人可以回查這個共同光學來源，並不改變各輪當年採用的模型或PSF。

[R142的100顆自適應選八顆包](../../../Experiments/R142_PSF100_AdaptiveTop8_Standalone/README.md)仍明確要求先完成尺度、樣本及SEM來源核對；它沒有因本次找到舊原拍就自動變成已安裝、已訓練的100顆版本。[R137原主實驗](../../../Experiments/R137_WeakPSFFeature/README.md)則使用原25顆平均，不能把名稱相近的後續100顆包倒套成它的原始訓練來源。

## 同日棋盤原拍（2026-10-28 補）

同一天（2025-09-03）、同一台相機另外拍了 393 張棋盤影像，原本只放在本機 `Shared_Sources/PSF_Camera_Acquisitions/PSF100_20250903/chessboard_same_session`，專案裡沒有程式或報告引用。電腦要交出去之前補進發布附件 [research-psf100-chessboard-20261028](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-psf100-chessboard-20261028)，恢復後在 `chessboard_same_session/`，檔名不變（`VisionTop_20250903171148.bmp` 這類）。

這批照片當時拿來做什麼沒有留下紀錄；推測和那次拍攝的尺度或畸變校正有關，但沒有證據，這裡不替它補用途。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-psf100-chessboard-20261028 --output ../chess-download
python Tools/research_asset_bundle.py restore --manifest ../chess-download/RESEARCH_ASSETS.json.gz --assets ../chess-download --destination . --keep-identical-existing
```
