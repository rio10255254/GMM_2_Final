# R152正式訓練改讀TIFF影像檔

日期：2026-10-04。使用者要求正式訓練以影像檔案提供，並明確選擇只放TIFF、不附PNG。本交付是最新獨立模型包的影像檔版本；原NPZ版保留作為來源快照，不作此版本的執行依賴。

## 使用位置

- [TIFF版使用說明](../../../Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/start_here.py)
- [正式訓練入口](../../../Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/train.py)
- [推論入口](../../../Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/infer.py)
- [完整TIFF版獨立包](../../../Deliverables/R152_Standalone_ImageFiles_20261004.zip)

包內程式、設定、說明、索引、檢查清單仍一律PY。全部路徑由包位置定位，模型、PSF和已驗證權重與上一版相同。

## 正式訓練影像

```text
data/train/clear/      2048張清楚TIFF
data/train/blur/       2048張無噪模糊TIFF
data/train/geometry/   2048張邊界距離TIFF
data/dev/clear/        512張
data/dev/blur/         512張
data/dev/geometry/     512張
data/test/clear/       512張
data/test/blur/        512張
data/test/geometry/    512張
```

總計3072組清楚／模糊視圖（6144張影像），另有3072張幾何標記。相同檔名如`0000_v0.tif`在clear、blur、geometry之間對應同一視圖。清楚和模糊尺寸384×384，幾何標記中央96×96；有效性、位移、PSF索引、噪聲與光度設定放在data_index.py。

訓練資料夾只有TIFF，沒有NPZ或PNG。正式Bank.read使用Pillow直接打開TIFF，不是提供影像預覽後繼續讀NPZ。PSF銀行、模型權重、推論原生輸出及訓練紀錄保留必要的NPZ／PTH資料格式，與訓練影像分開。

TIFF為32位元浮點灰階，完整保存原訓練數值；清楚／模糊的亮度範圍為0～1，幾何檔保留正負距離。查看時應使用能處理浮點TIFF、可自動顯示亮度範圍的影像工具。沒有為了顯示而改變正式訓練像素，也沒有附PNG。

原資料以float16保存，原讀法在訓練前轉FP32；轉換後TIFF直接保存這些完全相同的FP32值。測過全905969664個清楚／模糊像素；若改存一般16位PNG，即使再還原float16，仍有144073個值不同。因此此次採TIFF，避免格式轉換改變訓練資料。這是數值保存方式的選擇，不是重新製作模糊。

## 訓練和驗證

直接執行train.py仍使用最新R152原配方：包內已訓練主體保持凍結，擴充訓練8192次。--from-scratch可完整重做兩階段各8192次。讀入模糊TIFF後，仍按原種子和輪次加入噪聲、八位元四捨五入；模型、損失、PSF、分組和觀測算子策略不變。

已核對完整768母場景／3072視圖：實際訓練輸入、清楚目標、幾何、位移、PSF及算子索引均與原始R152讀法完全相同；第八輪的代表場景加噪與算子索引也一致。CUDA實際訓練前四次更新的八個損失項與原版紀錄完全相同，最大差0。第二次保存後續到第四次，所有模型張量與連續四次更新完全相同。所有模型程式、25PSF銀行和交付權重都與上一獨立版逐檔相同。

完整包目前9257個檔案，其中35個PY、9216個TIFF，約476.5 MB；ZIP約457.5 MB。沒有快取、外部連結或短測結果。全部壓縮檔內容已逐檔核對；完整影像檢查與模型載入檢查也已實際執行。沒有重新開始正式8192次訓練。

## 同日補齊完整影像生成來源

已加入五份未修改的原始生成程式，以及獨立generate_data.py入口。全部768母場景／3072視圖／9216 TIFF已從固定種子重新製作，阻擋舊來源及現成TIFF讀取仍通過；全部像素及檔案內容相同。新資料透過--data-dir正式入口的全部實際輸入及前四次CUDA更新亦精確相同。完整來源、固定參數與實跑紀錄見[R152重新生成核對](R152_DATA_GENERATION_REPRODUCTION_20261004.md)。
