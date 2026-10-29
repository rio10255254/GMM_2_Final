# R152獨立模型與完整訓練資料包

日期：2026-10-04。用途：將最新已完成訓練與實拍驗證的R152，整理成可以獨立搬動、直接手動訓練與推論的整齊資料夾。來源實驗、原始權重與訓練資料不移動。這是交付與重現性工作，沒有新的8192次正式訓練或新模型性能結論。

## 1 交付位置

- [獨立包使用入口](../../../Deliverables/R152_Standalone_20261004/start_here.py)
- [完整壓縮包](../../../Deliverables/R152_Standalone_20261004.zip)
- [訓練入口](../../../Deliverables/R152_Standalone_20261004/train.py)
- [推論入口](../../../Deliverables/R152_Standalone_20261004/infer.py)
- [設定與預設路徑](../../../Deliverables/R152_Standalone_20261004/settings.py)
- [完整性檢查](../../../Deliverables/R152_Standalone_20261004/check_package.py)

獨立資料夾為`Deliverables/R152_Standalone_20261004`。約350.5 MB，包含794個檔案，其中20個Python檔案、768個母場景資料檔；ZIP約338.1 MB。所有控制、設定、說明、索引及檢查清單都是`.py`，包內沒有JSON、BAT、PS1、TXT或Markdown。實際數據與權重保留NPZ、PTH、BMP必要格式。

## 2 整齊的功能分組

```text
R152_Standalone_20261004/
  start_here.py       使用說明與目前機器上的實際執行路徑
  train.py            訓練、續訓、可選的從零兩階段重做
  infer.py            原生R152推論
  settings.py         所有模型、訓練與預設路徑設定
  check_package.py    全部檔案／數據／模型完整性檢查
  data_index.py       固定分組、母場景、逐陣列來源身分
  manifest.py         包內不可變檔案的SHA-256
  reference_info.py   原R152保存點及資料數量
  verification_info.py 本次交付檢查的結果
  models/             R152主體、原U-Net／原尺寸階段、兩個PSF模組
  core/               資料讀取、兩階段損失、訓練及保存工具
  data/train/         512個母場景
  data/dev/           128個母場景
  data/test/          128個母場景
  calibration/        25顆實際PSF銀行
  weights/            凍結主體、R152訓練完成及部署保存點
  input/              待重建影像，附一張真實示例
  reference/          示例的原版已驗證浮點輸出
  outputs/training/   新手動訓練結果（交付時空白）
  outputs/inference/  新推論結果（交付時空白）
```

沒有連結到原實驗的junction或symlink。包內以`settings.py`自身位置定位資料與權重；預設不依賴執行當下的工作目錄。

## 3 完整訓練資料

768個母場景，訓練512、開發128、合成最後測試128。每母場景四個視圖，共3072個視圖，其中2048訓練、512開發、512測試。

原payload目標／無噪模糊資料與幾何檔，合併成每母場景一個NPZ。保留原始float16儲存精度，沒有重新卷積、縮圖或修改像素。每個檔案包含：

| 陣列 | 形狀及用途 |
|---|---|
| target | 4×384×384，原清晰目標 |
| noiseless | 4×384×384，原PSF卷積後的無噪觀測 |
| sdf | 4×96×96，中央監督區的幾何signed distance |
| valid | 4，是否有可用幾何邊界 |
| noise_sigma_gray | 4，原加噪設定 |
| psf_index | 4，原卷積PSF索引 |
| shifts_xy | 4×2，原已知位移 |
| contrast、brightness_gray | 4，各視圖已保存的光度設定 |

讀取後仍按原配方轉FP32，使用原種子、原epoch與四視圖順序加噪及八位元四捨五入。全部768母場景、3072視圖的第一輪輸入、清晰目標、幾何、位移及觀測算子索引均與原版逐項完全相同；另核對第八輪三個訓練母場景，噪聲与算子選擇亦相同。

## 4 手動執行

目前可直接使用已驗證的Anaconda Python：

```powershell
& "C:\Users\Rio\anaconda3\python.exe" "Deliverables/R152_Standalone_20261004/start_here.py"
& "C:\Users\Rio\anaconda3\python.exe" "Deliverables/R152_Standalone_20261004/check_package.py" --full-data --model
& "C:\Users\Rio\anaconda3\python.exe" "Deliverables/R152_Standalone_20261004/train.py"
& "C:\Users\Rio\anaconda3\python.exe" "Deliverables/R152_Standalone_20261004/infer.py"
```

也可以在具備numpy、PyTorch及Pillow的Python IDE中直接執行train.py或infer.py。搬到其他機器後，start_here.py會依當前資料夾與Python顯示新的路徑，程式內不需要修改舊機器地址。

預設train.py完全沿用最新R152配方：載入包內已訓練主體，凍結1194406個參數，訓練12699個新增參數8192次，完整使用128個開發母場景選部署倍率，最後評估128個合成測試母場景。

要從零完整重做兩階段，使用`train.py --from-scratch`：先以原主體種子及損失訓練8192次，再以R152種子訓練擴充8192次。三個獨立原尺寸階段、一次U-Net、抗混疊、全部25PSF與原生輸出策略不改。

續訓用`train.py --resume 某次訓練/extension/last.pth`。若原要求的更新數已全部完成，只剩最後評估，續跑last.pth可完成評估；已完成的正式保存點要繼續增加訓練時，`--updates`必須指定更大的累計更新總數。Ctrl+C在完成目前更新後保存，避免將半次更新當成完整保存點。

`--max-updates`和`--assessment-limit`用於短暫功能檢查；正式使用不限制開發／測試母場景。短測的完成權重標示`completed_short_test`，不冒稱正式模型。所有新結果寫入outputs，不覆寫交付權重。

推論預設讀input中的8／16位元灰階影像，以既定512核心／24周圍範圍分塊。輸出原生FP32 NPZ和十六位元PNG顯示圖；沒有另加銳化、位移或尺寸校正。

## 5 實際完成的檢查

| 檢查 | 結果 |
|---|---|
| 全部3072視圖第一輪訓練／開發／測試輸入及標記 | 與原資料讀法逐項完全相同 |
| 209個交付R152權重及緩衝張量 | 與原部署保存點完全相同 |
| 原版前四次正式更新的父場景及八個損失項 | 逐項完全相同，最大差0 |
| 停在第二步後續到第四步，對照連續四步 | 全部模型張量完全相同 |
| 擴充短訓練中的原主體 | 全部凍結張量未變 |
| 從零兩階段、部署倍率選擇及合成測試 | 各兩次更新的功能流程完整跑通 |
| 已完成最後更新、但評估未完成的續跑 | 跑通，不額外訓練 |
| 真實1544×2064示例，CUDA推論 | 與原驗證浮點影像逐像素完全相同，最大差0 |
| 異址、不同工作目錄、拒絕讀取原R152／R148v2資料夾 | 新址訓練兩次及CPU推論成功 |
| 新址與交付位置的CPU推論 | 完全相同 |
| 8位元與16位元PNG讀取 | 依規定比例轉換，核對相同 |
| 原程式／權重／資料地址留在包內執行程式或保存點中 | 0個 |
| 包內快取、捷徑、試跑輸出或非PY操作／設定檔 | 0個 |
| 所有檔案與完整ZIP內成員 | SHA-256逐檔核對通過 |

短測均寫在來源實驗的results/STANDALONE_PACKAGING_20261004，沒有塞進交付包。異址檢查只複製短測所需四個母場景；交付包本身含完整768個母場景，並已另外逐一開啟及核對全部陣列。

## 6 權重、環境與原始來源

已驗證環境為PyTorch 2.3.0+cu121、NumPy 1.26.4、Pillow 10.4.0，RTX A6000。程式為一般Python/PyTorch程式，外部Python套件仍需安裝；此包不冒稱自帶Python或CUDA執行環境。

來源部署權重SHA-256為`17bf7c63f070520a5ef8d4428010340686f465bf1fa03ef8225c0a2eadad4a61`。權重容器已移除舊機器地址，故新檔案的SHA-256不同；逐項張量完全相同及整張原生輸出完全相同，已分別核對。原PSF銀行檔案以原件複製，SHA-256仍為`efc9d70d6427d82ba84f1371f71b6423f1491a815956412f8d6a627b72b1f843`。

來源封存表中的完整報告先前因已授權的定義／導航更新而有不同雜湊；本次只更新該報告的封存值，其他33份封存程式與設定完全吻合。詳細紀錄位於results/STANDALONE_PACKAGING_20261004/documentation_lock_refresh.json，沒有據此修改任何模型張量或訓練資料。

此交付不重新跑正式8192次訓練，不改變既有完整實拍結果或專案正式基準。最新論文R152模型、完整資料與可手動執行入口均已獨立可用。
