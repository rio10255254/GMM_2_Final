# 按用途選附件

PSF100與0615的重要原拍新增獨立版本，完整下載約12.73GB，按輪次可分開取得；[用途、精確大小與恢復方法](../../Shared_Sources/PSF_Camera_Acquisitions/RESTORE.md)。這是不可再生相機資料，未重新啟動舊生成影像全量方案。

先選研究目的，再下載具體附件。**不需要下載全部版本，也不要執行舊全量保存排程。** 本頁大小取自2026-10-22 GitHub實際附件清單，是壓縮下載大小；解開後另需空間。

## 常用小型包

只看必要原始數字，可直接取得[30份原平台紀錄](../../Shared_Sources/PI_Repeatability_20260903/position_records/README.md)、[原SEM工作表](../../Shared_Sources/SEM_Originals/README.md)與[本批重要完整原表](project_completion/curated/IMPORTANT_TABLES_20261022.md)，不需先下載大附件。

| 用途 | 到對應版本選這個檔案 | 下載大小 |
|---|---|---|
| R93原60輪表、停止及候選選擇；純數字 | [r93-result-replay.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/r93-complete-record-20261020) | 36,022 bytes |
| R94／95／97／98原完整數字與停止／接續讀法 | [four-round-result-replay.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-preservation-20261021) | 3.67 MB |
| Lab數學平移來源與原表；不能改稱相機重拍 | [lab-subpixel-inputs-and-results-replay.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-lab-subpixel-replay-20261021) | 4.24 MB |
| 原R61部署模型、光學與示例；不是整套訓練資料 | [R61-original-ONNX-delivery-verified.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-r61-onnx-delivery-20261021) | 15.08 MB |
| R152原固定模型、必要光學及設定來源 | [research-r152-frozen-inputs-001.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-training-kits-20261016) | 28.76 MB |
| 既存光學結果讀取與重算；不是重新做全部MATLAB擬合 | [psf-saved-results-replay.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-optical-calibration-replay-20261021) | 39.50 MB |
| V42原120輪表讀法、固定第10／120輪與原紀錄 | [v42-original-log-and-fixed-models-replay.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-v42-history-replay-20261021) | 54.05 MB |
| 十方法原觀察及全部270數值、18,000筆位移與162組區間 | [ten-method-result-replay.zip](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) | 77.32 MB |

這些是已有交付，本次沒有重新訓練或另包整套來源。原實際核對見各包與所屬研究導讀；包內固定來源不因main文件更新而改寫。

選一個附件的方式如下，`ASSET_NAME`與`RELEASE_TAG`用上表的檔名與對應版本取代：

```powershell
gh release download RELEASE_TAG --repo rio10255254/GMM_2_Final --pattern ASSET_NAME --dir downloads/selected
```

版本頁內還有其他大檔時，只選列出的檔名；不要把整個版本全部下載當成必要步驟。一般結果包解壓後讀包內說明；研究來源分包則需對應的原恢復清單，不能把ZIP中的儲存物件隨意改名當原路徑。

## Lab R61內部r36的單一必要起點

本次只新增一份[固定a948起點](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-lab-r61-r36-source-20261022)，原17,402,302 bytes，附件`research-lab-r61-r36-initializer-001.zip`為15,923,528 bytes。搭配同版`RESEARCH_ASSETS.json.gz`恢復一個原位置即可；已實際從GitHub取回、還原及核對相同。原best／latest模型已有既有附件，不重傳；整套v10影像和其他中途模型不在新包。

[原訓練、96案例結果及兩種R36身分](lineage/R36_IDENTITIES_20261022.md)另列；這是Lab R61內部來源，不是把主專案未知R36補成已完成。

## 原始來源與較大交付

| 需要什麼 | 取得位置與界線 |
|---|---|
| 9月3日930張原拍、30份原始位置紀錄 | [共用原拍與恢復](../../Shared_Sources/PI_Repeatability_20260903/README.md)。原始拍攝ZIP約2.03GB，只保留這一次共用來源 |
| R61 v16繼承來源 | [原生成包](../../Deliverables/R61_TrainingData_Regenerator_20261004/README_TW.md)、[固定來源版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-training-kits-20261016)。不是只靠種子可重算的3,400組歷史來源／幾何必須保留 |
| R93／R94至98基礎 | [R93來源導讀](r93_shared/README.md)及[本機固定資料位置](../../Experiments/R93_RecoverableDetailSeparatedScratch/data/ARCHIVE_POINTER_20261022.md)。可先讀方法，不必先下載約12.6GB共用formal來源；生成器與原修正另在[生成方法](GENERATION_GUIDE.md) |
| 四輪選用模型、原表及失敗影像 | [R94／95／97／98導讀](four_rounds/README.md)。先選輪次和用途，完整歷程包不是每次閱讀的必需品 |
| Step、多倍率原拍、SEM與原工作表 | [共用來源與影像取捨](SOURCE_AND_IMAGE_DECISIONS.md)。原拍、SEM、合成及模型輸出各有不同角色 |
| 早期模型與R153外部比較模型 | [模型用途與具體附件](MODEL_GUIDE.md)。同一分包可能包含多個模型，表中分清模型自身大小與附件下載大小 |
| 原論文草稿、可編輯原圖與必要部署版本 | [精選歷史交付](project_completion/curated/draft_cleanup_20261022/README.md)。約237MB精選原件已保存，不需取回舊數百GB草稿 |

## 不要把保存索引當新上傳清單

歷史大附件仍有存在理由，但這次不增加全量影像、完整訓練庫或每個中途模型。可生成資料先保留生成器、設定和必要來源。原始相機、量測、人工標記與完整研究結果則不能只靠程式代替。

六份超量草稿已撤回；舊JSON仍保留當時狀態。現在正式附件的用途以上述入口及[保存紀錄](project_completion/README.md)為準；遇到舊草稿網址不要改跑全量上傳來補齊它。
