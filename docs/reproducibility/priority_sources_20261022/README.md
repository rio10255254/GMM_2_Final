# 395份必要來源補件與R63查找結果

這批承接[重新核對的待補清單](../REMAINING_PRESERVATION_AUDIT_20261022.md)，原始約8.40GB，壓縮附件共5,180,624,081 bytes（約5.18GB）。[獨立發布版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-priority-sources-20261022)按用途分組，不把所有訓練／重建產物包回去。

| 內容 | 保存數量與作用 |
|---|---|
| R63原選用模型 | 31個。每個都符合原選模紀錄；原32筆中另1個仍未定位，不能稱全32組已能重新推論 |
| LabSystem原校正照片 | 25張，實際拍攝日2026-06-05，舊資料夾名稱仍保留20250605；與原裁切來源表逐張對照 |
| 原Raw邊界量測 | 30份，內含精修與粗定位座標，不是整張影像陣列；供R129／R130等共用 |
| 固定驗證輸入 | 11張原小圖，保留原凍結內容；後續相同內容共用，不另存每輪副本 |
| PSF固定小輸入 | 原光學／SEM TIFF裁切對及原單圖處理輸入，共3份，不能稱相機全幅原拍 |
| PSF100其餘原拍 | 295張；與前一發布版100張合為原395張，補完整挑圖資料，前100張未重傳 |

## 按用途下載

| 分組 | 壓縮大小 | 附件 |
|---|---:|---|
| fixed-validation-inputs | 1783130 bytes | research-fixed-validation-inputs-001.zip |
| lab-june05-camera | 34417686 bytes | research-lab-june05-camera-002.zip |
| psf-fixed-inputs | 160083 bytes | research-psf-fixed-inputs-003.zip |
| psf100-selection-context | 4611526501 bytes | research-psf100-selection-context-004.zip, research-psf100-selection-context-005.zip, research-psf100-selection-context-006.zip, research-psf100-selection-context-007.zip, research-psf100-selection-context-008.zip |
| r63-selected-models | 522254438 bytes | research-r63-selected-models-009.zip |
| raw-boundary-observations | 10456304 bytes | research-raw-boundary-observations-010.zip |

先取得新的專案副本；在新副本執行下例。Python下載器需requests與已登入的GitHub CLI。以下只下載、恢復，不啟動訓練或推論。

```powershell
gh repo clone rio10255254/GMM_2_Final research-sources -- --depth 1
cd research-sources
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-priority-sources-20261022 --output ../priority-download --prefix Experiments/R63_CausalBoundaryMotionAblation
python Tools/research_asset_bundle.py restore --manifest ../priority-download/RESEARCH_ASSETS.json.gz --assets ../priority-download --destination . --prefix Experiments/R63_CausalBoundaryMotionAblation --keep-identical-existing
```

兩行的`--prefix`須一致，依用途換成下列位置；要本批全部395份時省略`--prefix`。相同既有檔案可保留，內容不同會停止且不覆寫。

- Lab原拍：`LabSystem_MOSR/psf_calibration/raw`
- 原邊界量測：`Deliverables/Thesis_Handoffs/R129_Corrected_Corner9_Thesis_Handoff_20260920/04_Verification_and_Sources/centers/Raw`
- 固定驗證圖：`Experiments/R130_CleanV42Comparison/validation/inputs`
- PSF小輸入：`PSF_Fitting/Deconvolution`及`PSF_Fitting/SingleImage_Input`，可重複指定`--prefix`
- 其餘295張：`Shared_Sources/PSF_Camera_Acquisitions/PSF100_20250903/raw`

完整395張原拍需分別下載前版`research-psf-camera-acquisitions-20261022`的100張和本版295張，放入同一新副本；兩版使用相同PSF100原拍位置前綴，分開存放各自下載目錄與恢復清單。原100個擬合視野對照仍見[來源鏈](../../../Shared_Sources/PSF_Camera_Acquisitions/PSF100_20250903/README.md)，全批逐張身分見[395張清單](../../../Shared_Sources/PSF_Camera_Acquisitions/PSF100_20250903/COMPLETE_395_CAMERA_CATALOG.json)。保存完整原拍不表示已重跑全部分群與歷史前處理。

## 實驗如何使用這些來源

R63使用[原32筆固定名單](../../../Experiments/R63_CausalBoundaryMotionAblation/results/training_manifest.json)與[這次可取得位置](R63_ORIGINAL_SELECTION_AVAILABILITY.json)。只保存當年選用端點，不要求重傳每個中間epoch。不要在缺少全歷程時重新呼叫挑選所有epoch的程式，然後把新選擇當作原判決。共同初始模型與PSF已有舊發布來源，不重傳；仍缺的1個版本使原32模型全套重新推論不能宣稱完成，原完整結果照原紀錄閱讀。

LabSystem原拍恢復到[原準備程式](../../../LabSystem_MOSR/psf_calibration/scripts/prepare_inner_circle_roi_gt.py)實際讀取的位置；[原設定](../../../LabSystem_MOSR/psf_calibration/configs/lab_optical_setup_20250605.json)和[原25列裁切對照](../../../LabSystem_MOSR/psf_calibration/inputs/20250605_inner_circle_roi/MANIFEST.json)保留。可再產生的ROI圖及展示圖沿生成方法，不另包一套。換機時將新副本設定中的舊D槽絕對路徑指向自己的恢復位置，保留原設定作歷史對照。

原邊界資料每份有`points/coarse`兩組31×9×64×2座標；尺寸、欄位與有限數值已檢查，不把它混稱重建像素。它與原表、相機拍攝及既有結果一同使用，不補造沒有記錄的量。11張固定驗證圖則對應[原凍結設定](../../../Experiments/R130_CleanV42Comparison/config/frozen.json)。

## 尚未找到的R63版本

`no_raw_position_anchor`、種子1261217、原選中第24輪，內容身分`089192e195207a3a1631587496221746c794c03cf908f7bd8be5e9f4686c2f41`仍未找到。已查原工作區／封存、舊備份壓縮包、可讀回收筒紀錄、相關本機目錄與已連接Google Drive。可讀範圍與拒絕讀取的位置如實記錄於[查找紀錄](R63_SEARCH_AND_LIMITS.json)，不宣稱查遍所有磁碟或雲端壓縮包。後來完成60輪的版本不當作它的替代品。

本批395份補件完成與全專案所有來源完成是不同範圍。未審完的動態路徑及其他實驗來源仍待逐輪核對；原研究結論、原始資料、工作分支和正在訓練資料保留。

## 已完成的實際交付

12個附件已全部從GitHub重新下載，395份原件已在新位置完整恢復，原內容逐份相同。31個R63模型另以CPU開啟，當年選中輪次與原名單相同，模型數值可讀且有限；沒有執行模型推論或訓練。原測量資料、原拍及固定小圖也已開啟核對。遇到不同內容的既有檔案會停止且保留原檔。[交付收據](DELIVERY_VERIFIED.json)。

## 共用圖在其他套件的原位置

另外核對R129獨立包和R134的22個既有輸入位置，與這批11張固定驗證圖內容完全相同。[已核對的共用位置](KNOWN_ALIASES_VERIFIED.json)只增加位置對照，沒有新增影像附件。這批來源也讓先前引用候選中的47個位置找到可取得內容，其餘534個候選仍包含大量可再生輸出，不能全部當成必須上傳。

若要同時恢復這些共用位置，先用上述原方法下載所需附件，再改用本頁的`RESTORE_WITH_KNOWN_ALIASES.json.gz`作為恢復清單。它沿用相同的10個ZIP，不需重傳或重複下載。例如恢復R129套件的11張圖：

```powershell
python Tools/research_asset_bundle.py restore --manifest docs/reproducibility/priority_sources_20261022/RESTORE_WITH_KNOWN_ALIASES.json.gz --assets ../priority-download --destination . --prefix Deliverables/Standalone_Models/R129_OpticalHybrid_Standalone_20260912/validation/inputs --keep-identical-existing
```

若只下載了R63模型，需再取得本版`research-fixed-validation-inputs-001.zip`才能恢復上述共用圖；不用下載全部原拍。
