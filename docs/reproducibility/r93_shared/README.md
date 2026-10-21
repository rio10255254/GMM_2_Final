# R93 至 R98 共用來源與原始結果的 GitHub 重做入口

這條來源鏈最容易混淆的地方，是 R93 的舊說明沿用了前輪標題與亂數起點，而後面四輪又直接共用 R93 的固定資料。這裡把「查看原結果」「重算當時選擇」「取回固定模型」「準備共用訓練資料」分開，避免必須先下載所有大型資料才能理解實驗。

R93 真正使用 930041、1,250 個合成場景及 5,000 次觀測。它預計 64 輪，實際在完整第 60 輪後停止；原內部分析的綜合候選是 48 輪。COMBO 正式基準與論文採用模型均未因此改變。[完整來源審查](../../../Experiments/R93_RecoverableDetailSeparatedScratch/reports/R93_AUDIT.md)。

## 只想看懂並重算原結果

從 [R93 完整紀錄版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/r93-complete-record-20261020) 下載 `r93-result-replay.zip`，約 36 KB。它有原本 60 輪表格、原停止分析和重算程式，不需要影像、模型、Torch 或完整訓練庫。

解開後在該資料夾執行：

```powershell
python Tools/replay_r93_stopped_results.py --root . --output replayed_results
```

它會重算 32–60 輪的 15 個已觀察候選、五項最佳輪次、48 輪綜合候選與 18 個原數字。輸出同時保留「原訂 64、實際停止 60」，不會把未完成四輪補成成功。

## 查看模型與完整影像歷程

[同一版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/r93-complete-record-20261020) 的完整附件保留 600 個原位置，包含 34 個模型檔、250 張比較圖與測試影像、完整數字、smoke 小資料、四個既有實拍預覽輸入與固定資料身分。相同內容只保存一次，所有原位置仍會還原。這不是 34 次不同訓練。

完整 results 原有的 245 張圖全都保留；包括清楚輸入仍被改動、後期細節退步及差異圖。[網頁快速圖庫](GALLERY.md) 另提供 24 張未重新壓縮的原圖，並標明實拍與合成來源。

先取得本次固定程式版本：

```powershell
git clone -c core.longpaths=true --depth 1 --single-branch --branch research-preservation-20261020 https://github.com/rio10255254/GMM_2_Final.git
cd GMM_2_Final
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag r93-complete-record-20261020 --output downloads/r93-record
python Tools/research_asset_bundle.py restore --manifest downloads/r93-record/RESEARCH_ASSETS.json.gz --assets downloads/r93-record --destination . --keep-identical-existing
```

倉庫保持私人狀態，需要有讀取權限的 GitHub 帳號。原 2026-10-16 保存版本與附件仍保留；本次沒有覆寫它們。

## 取回五輪共用的完整固定資料

完整 R93 formal 資料早已在 [共用來源版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-shared-sources-20261016)，本次不再重複上傳。15 個必要附件合計約 12.6 GB，還原後為 15,004 檔、約 29.7 GB。以下只下載這份資料需要的附件，不下載其他實驗的全部來源。

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-shared-sources-20261016 --output downloads/r93-shared --prefix Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/
python Tools/research_asset_bundle.py restore --manifest downloads/r93-shared/RESEARCH_ASSETS.json.gz --assets downloads/r93-shared --destination . --prefix Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/ --keep-identical-existing
```

這裡恢復的是當時真正被使用的固定檔案，不以「相同種子應該會一樣」取代核對。R93 的生成、修復、完整核對記錄與原程式一併保留；本次沒有宣稱已把這整輪合成流程重新生成到相同內容。

## 新環境的 CPU 檢查

已使用獨立環境的 Python 3.12.7、Torch 2.3.0 CPU、NumPy 1.26.4、OpenCV 4.12.0、SciPy 1.13.1 檢查。可在新的虛擬環境安裝：

```powershell
python -m pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install --no-deps numpy==1.26.4 scipy==1.13.1 opencv-python-headless==4.12.0.88
python Tools/verify_r93_shared_recovery.py --root . --report R93_SHARED_RECOVERY_VERIFIED.json
```

第二步刻意保留原 NumPy 1.26.4；OpenCV 的較新安裝描述可能要求 NumPy 2，不能因此悄悄改掉這份已測環境。完整套件版本保存在本目錄的環境記錄中。

檢查會完整核對 15,004 個固定檔案，再實際呼叫 R93、R94、R95、R97、R98 各自原本的讀取程式。每輪涵蓋八種訓練用途和首／中／尾，共 45 個代表準備樣本，逐項比較輸入、答案、校正分支及位置等內容。R94 保留第 8 輪失敗的事實，使用當時的 512／256 準備尺寸，不假裝曾完成原訂最後階段；其他輪次使用已記錄的後期尺寸。原五輪程式沒有為通過檢查而改寫。

## 用固定模型重新產生影像

取回完整紀錄後，可只使用四個小型實拍預覽輸入，不必先下載 formal 訓練庫：

```powershell
python Experiments/R93_RecoverableDetailSeparatedScratch/inference/reconstruct.py --checkpoint Experiments/R93_RecoverableDetailSeparatedScratch/weights/formal/seed_930041/R93_scratch_seed930041_20260812_112601/weights/epoch_048.pth.tar --input Experiments/R93_RecoverableDetailSeparatedScratch/data/live_validation --output newly_replayed_R93_epoch48 --device cpu --core-size 512 --halo 192 --tile-batch 1
```

最後一輪的固定模型是同一位置下的 `epoch_060.pth.tar`，可另給新的輸出位置重做。原圖、固定模型和原推論程式都保留，重做輸出與歷史比較圖分開，不覆蓋原件。

本次比對的新 CPU 重做與舊工作區同一原版程式的 CPU 重做；不能把它寫成「重新跑完整訓練」或「重現當時所有 GPU 監看圖的每個位元」。這些實拍預覽也不是新的獨立實體準確度驗證。

## 保存範圍與限制

固定資料、原方法、完整原數字、停止原因、所有當時保存的模型和影像均可分別取得。資料讀取與固定模型重建的檢查不能代表五輪完整訓練已重跑，也不改變任何採用／未採用判決。原始相機重拍資料另由 [30 趟來源版本](https://github.com/rio10255254/GMM_2_Final/releases/tag/shared-pi-20260903-v1) 保存，不能拿這份合成訓練庫替代它。

具體實測及 GitHub 取回結果見 [本次核對收據](VERIFICATION_20261020.json)。
