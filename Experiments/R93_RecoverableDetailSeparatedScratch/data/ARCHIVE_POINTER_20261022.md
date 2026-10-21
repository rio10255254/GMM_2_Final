# R93 共用訓練資料的保存與恢復（2026-10-22）

本輪已核對 D 與 H 的 formal／locked_holdout 共18,072份大陣列完全相同；同時按原生成器的陣列內容核對碼核對，不把 .npy 檔案外層誤當成陣列內容。這是儲存核對，不是重新訓練、重新評估或開啟封存測試。

這份合成資料不是9月3日的相機原拍。正式共用資料的身分仍是6494719a…、主種子930041；封存組身分2f726d80…、種子939927，不能和R92共用基礎互換。

清理只處理兩個 arrays 目錄的 D 重複副本；小型 manifest／audit／build_progress／SEALED、預覽與 smoke、所有模型、原始數表、原報告、修復紀錄及生成程式保留。完整固定資料仍在 H 的20260925_full_history，formal 另有既有GitHub共用版本。實際執行狀態見同目錄 ARCHIVE_SCOPE_20261022.json。

## 舊訓練入口前先恢復

R94／R95／R96／R97／R98共用這份R93基礎。未來需要完整重訓或重做以這份資料為輸入的舊內部驗證時，先恢復同一份資料；不要直接把R92或新產生但不同身分的資料換進去。目前沒有使用這些D陣列的訓練程序，現有H獨立訓練套件不在本輪範圍。

若 arrays 仍存在，請先核對，不要覆寫任何既有不同檔案。以下在專案根目錄執行，只補回缺少的原目錄：

```powershell
if (Test-Path -LiteralPath 'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal/arrays') { throw '原位置已有資料，請先核對身分。' }
robocopy 'H:\GMM_2_Final_Archive\experiments\R93_RecoverableDetailSeparatedScratch\20260925_full_history\data\r93_formal\arrays' 'D:\GMM_2_Final\Experiments\R93_RecoverableDetailSeparatedScratch\data\r93_formal\arrays' /E /COPY:DAT /DCOPY:DAT /XJ /R:1 /W:1
```

需要原封存組時，同樣從 H 的 data/r93_locked_holdout/arrays 複製回同名新目錄。恢復它不代表取得使用封存組調整模型或宣稱獨立驗證的資格；原封存規則與 SEALED.json 保持。

## 沒有H槽時

正式共用資料可按 docs/reproducibility/r93_shared/README.md，從已發布的 research-shared-sources-20261016 只下載R93 prefix，使用 keep-identical-existing恢復缺少內容；不能覆寫不同的既有資料。當年生成程式、光學設定、11場景／44觀測的修復與原完整結果亦已保存；沒有把資料生成方法寫成已重跑所有歷史GPU訓練。

完整逐檔SHA清單與本次實測在 H:\GMM_2_Final_Archive\reproducibility\20261021_d_cleanup_continued；其中正式資料的三份原陣列已實際由H另取回並開啟。封存組僅做完整性核對，沒有模型評估。
