# Lab舊比較：原圖、測試輸入、模型與結果分開閱讀

這裡整理2026年7月的Base U-Net、現代模型比較、子像素平移及模型版本診斷。這些是Lab歷史，不能把表內的「MOSR」直接解讀為目前論文採用的R152，也不改COMBO正式基準或後來的研究判決。

## 126張測試圖實際來自什麼

原[輸入紀錄](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Subpixel_Translation_Equivariance_20260720/inputs/input_manifest.json)登記的是**2張完整來源影像、6個裁切區域**。50倍同一張包含pillar、via、水平線及垂直線四個區域；20倍同一張提供pillar與via兩區。每區保存一張參照及20種數學平移，共126張；其中6張是參照裁切、120張經Lanczos平移。它們不是126次重新拍攝。

完整來源是兩張2048×1536、8-bit影像，內容符合原紀錄的核對碼。衍生輸入採512×512、16-bit儲存，以保留插值後的灰階；這不代表相機新增了16-bit取像。原程式、原設計、原裁切與幾何紀錄均保留。

來源檔與數值重算的必要小型資料合計約6.5MB，見[固定原件清單](SUBPIXEL_SOURCE_FILES.json)。這份清單也保留全部126張原輸入的內容身分；126份原件已在第一批影像附件中實際取回，而本次用原生成程式完整重建，逐張檔案完全相同。新產生清單的實際磁碟位置會改變，其餘126列設計／裁切／位移欄位及六區幾何均核對一致。

## 五種方法不是五次獨立拍攝

每種方法處理同一組126張輸入。原主要讀值有五方法合計500列、每方法相同100組；線條平行方向另作側向檢查，不能把126張、600列明細與100組主要端點混為同一個數量。這些組合又共用兩張來源影像，原有重抽樣區間不能說成100次獨立實拍的不確定度。

| 表內方法 | 原推論紀錄的模型 | 應保留的差異 |
|---|---|---|
| Raw | 已知數學平移後的參照輸入 | 接近理想值是這項設計下的預期，不代表新的真實平台量測比較 |
| Base U-Net | 30輪時程中的最佳第12輪 | 不把最後第30輪當成正式輸出 |
| EDSR-x1 | 最佳第15輪 | 保留當時的固定光學前處理，不能稱為完全未用光學先驗的原版EDSR |
| Compact NAFNet | 30輪時程中的最佳第15輪 | 與其訓練總輪數分開 |
| Lab MOSR／V42 | 第120輪，PSF來自權重內部，外部錨定關閉 | 第10輪最佳權重與定位保護版本是另外的診斷，不能覆蓋這份第120輪結果 |

原[模型輸出身分](MODEL_IDENTITIES.json)保留四份模型的完整核對碼，均能對應到本次完整來源清單。小型重做不執行模型，完整模型仍由原保存附件恢復；[原推論紀錄](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Subpixel_Translation_Equivariance_20260720/results/learned_inference_manifest.json)與[MOSR原設定](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Subpixel_Translation_Equivariance_20260720/results/mosr_inference_manifest.json)才是當時實際版本。

原主要表的中位誤差依序為Raw 0.00397、Base U-Net 0.00747、EDSR 0.00402、NAFNet 0.01544、MOSR 0.00954 pixel。MOSR沒有在這個完整平移範圍領先EDSR或Base U-Net；原診斷另外列出的0.1 pixel較有利子集，不能代替預先固定的主要結果。

## 七月平台比較與九月重拍是不同證據

[現代模型的計算審查](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/Modern_Restoration_Benchmarks_20260719/evaluation/calculation_audit/MOSR_RESULT_AUDIT_20260719.md)明記：當時評估表的位移參照是名義命令，沒有逐幀數值PI回授；30步依Raw相對名義運動的偏差排序，本身對Raw較有利。較早文字寫「PI回授」不能自動升格為已取得逐幀回授。後來[9月3日30趟原拍與位置紀錄](../../../Shared_Sources/PI_Repeatability_20260903/README.md)是另一批資料，不可依相同`frame_0000`名稱回填成7月那批的回授。

同一審查也分清實際部署與網路速度：原正式表MOSR整張推論約408ms，其餘方法用重疊切片；相同輸入方式下，MOSR並不比Base U-Net快。這兩張表都保留，不能只留下較有利的速度圖。20倍via尺寸改善也要保留明顯環狀振鈴；line沒有獨立SEM尺寸，不能延伸成絕對線寬準確度。

[Base U-Net收尾報告](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/BASE_UNET_RETEST_SUMMARY_TW.md)與現代比較的CD統計及共同有效步母體不同，不能跨表混算排名。[模型／設定診斷](../../../Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/MOSR_CheckpointConfig_Diagnostic_20260724/diagnosis/DIAGNOSTIC_REPORT_zh-TW.md)的取樣相位解釋按當時診斷閱讀，不能把事後說明直接當成只改一個變因的因果證明。

## 品質預覽也不能算成相機原圖

首批12,000份影像中，掃描器依路徑標為輸入的129份，包含上述126張衍生測試圖，以及Lab R56的3張標籤修補品質預覽。後三張是來源／修補前後／參照／差異的合成檢查圖，不能因位於`Training_Data`就當成原拍。R56原本的實體角點檢查失敗仍保留，不以內部訓練分數或漂亮預覽掩蓋。

[影像用途證據](../project_completion/IMAGE_ROLE_EVIDENCE_20261021.json)以原位置及內容身分綁定131份已查明的圖：126份衍生輸入、3份品質預覽、2份完整來源。總恢復清單採用這些已查明用途，較早掃描分類照原樣留作歷史，不改原圖或原數字。

## 不需完整資料或模型即可重做

本次固定CPU環境為Python3.12.7、NumPy1.26.4、pandas2.2.2、SciPy1.13.1、OpenCV4.12.0。原生成與原統計程式沒有改寫；幾何介面從當時已保存的六區紀錄建立，不冒稱找回較早全域設定檔。

```powershell
python -m pip install numpy==1.26.4 pandas==2.2.2 scipy==1.13.1
python -m pip install --no-deps opencv-python-headless==4.12.0.88
python Tools/replay_lab_subpixel_history.py --root . --output NEW_OUTPUT_DIRECTORY
```

OpenCV採用本次已驗證的安裝組合。程式先逐份核對必要原件，再執行原生成流程、檢查全部126份檔案與原清單，最後用原統計段重算四張原表的346個數值；本機核對最大差為0。它沒有重新估計全部影像邊界、重做模型推論、訓練或平台實拍。[本機重做收據](LOCAL_REPLAY_VERIFIED.json)與後續GitHub實際取回驗證分開記錄，不以本機通過冒充遠端取回。


## 已發布、已實際取回的小包

[約4.2MB的完整小型重做包](https://github.com/rio10255254/GMM_2_Final/releases/download/research-lab-subpixel-replay-20261021/lab-subpixel-inputs-and-results-replay.zip)包含兩張完整來源、原生成與統計程式、原設計／幾何及原表。它已實際從GitHub下載並解開，21份包內檔案核對通過；在原D／H研究資料不可讀的條件下，再次完整生成126份輸入檔相同，四張原表346數值完全相同。故意改動取回的來源圖會在建立輸出前停止。[實際取回收據](GITHUB_REPLAY_PUBLISHED_VERIFIED.json)。

固定小包來源為`415ce617db99cebc7e8b72e82ad0a7ad03491748`；它沒有附四份模型權重，也沒有重新執行模型或訓練。完整權重與完整結果仍依全專案保存索引取得。小包完成不代表大型資料與總恢復索引已完成。


V41與V42的來源續查見[V41到V42完整訓練、模型及原表讀法](V42_HISTORY.md)：完整120輪確已完成；預設兩輪短測與最佳第10輪EMA分開。原表欄名錯置另存修正，不改任何原數值；原生CPU與GitHub取回範圍由各份收據分開認定。
