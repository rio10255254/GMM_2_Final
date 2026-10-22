# 逐輪必要來源接續核對

這輪按當年真正選用的模型、程式讀取的資料與原完整結果追查。一般閱讀入口齊全不代表來源已閉合；[177組逐輪進度](ROUND_SOURCE_LEDGER.json)分開記錄本次查到的項目與仍待核對部分，不以列數宣稱全部完成。

## 這批補了甚麼

- R32：補當年內部選中、但外部位移比較失敗的原模型；原失敗判決保留。另凍結原設定指定的100張901×901 EQ輸入，供等變性訓練項讀取。這些是原路徑現存的處理輸入，未找到完整的原拍到該處理版本對照，不能冒稱100張全幅原拍或已逐字證實當年輸入版本。100份重複GT已共享同一既有內容，不重傳。
- R147：補實際完成8192次訓練的最後模型。原已有2944次備份和短測模型，不能拿它們替代最後結果；PSF與父來源沿既有保存，不改其研究版身分。
- R108B／C：15個缺少的小型最終測試模型直接放在原`weights`位置，共5.43MB；包含B的兩組比較，以及C的專家、採用器與六組各訓練300步的校準端點。後續探索與最初條件式計畫分開閱讀，不宣稱升級為正式模型。[逐個原件身分](R108_FROZEN_MODELS_REVIEW.json)。
- R113／R116：保存明確被後續程式讀取的少量歷史比較輸入。R116四張檔名含raw的圖實際是R109重建結果；R113含五張重建參照與六張固定合成例圖，均不當新相機資料。
- R129／R130／R137／R138：保留原方向、亮暗與鏡像候選以及選圖核對圖，不只留最後選中的方向。R66的三張原比較圖來源也留，便於原論文圖追查。
- R131／R132：保留三份已鎖定的raw、pre_guard、guarded、weight診斷記錄，供邊界保留範圍研究使用。這是少量具體比較來源，不是全部930張重建陣列。

附件共130個原檔、原始242,959,491 bytes，壓縮約161.37MB；另15個小模型與舊封存清單直接收錄一般程式版本。[版本附件](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-round-source-followthrough-20261022)／[逐份恢復清單](RESEARCH_ASSETS.json.gz)。

## 哪些不重傳

13輪的17筆原完成／部署模型紀錄已比對當前原件，內容均符合原紀錄。[核對明細](FIXED_COMPLETION_MODEL_REVIEW.json)。R147缺最後模型已在本批補上；R152的已發布便攜檔與原部署檔有209組相同模型數值，保留身分差異，不因整檔封裝不同就再稱模型缺件。

R42四個低比例混合模型可由兩個已發布原模型和[原混合方法](../../../Experiments/R42_MicroscopyBoundaryFidelity/scripts/r42_weight_sweep.py)重新生成；保留父來源、比例、原失敗結果，不重傳四個派生權重。[判斷依據](R42_GENERATED_MODEL_DECISION.json)。R89被拒絕的早期資料與短測模型，與正式來源分清，未把全部失敗陣列包回去。

先前剩餘534個具體引用已逐項分類：[完整處置表](REFERENCE_DISPOSITIONS.json.gz)／[分類統計](REFERENCE_DISPOSITION_SUMMARY.json)。R100與R128清單裡大量影像及`output/neural_output`陣列是可再生輸出；原數表、選用模型及來源沿既有保存。這份舊候選清單已判讀，不代表全部動態、相對路徑與所有歷史版本已查完。

## R108資料只生成、不訓練

原整支實驗入口會訓練，所以另提供只取原生成函式的入口。它核對兩支來源原碼，只執行資料生成、不匯入Torch、不載入模型、不呼叫推論，且只接受專案外的新資料夾。

```powershell
python Tools/rebuild_microprobe_inputs_only.py --output ../microprobe-inputs
```

需NumPy1.26.4、OpenCV4.12.0。實測R108B的384／96／96資料以108801／108802／108803種子重生，R108E各加倍並採109020至109022的條件種子；兩個NPZ完整內容符合原固定雜湊。既有輸出會拒絕，不覆寫。原B、E生成程式及這份小入口保存即可，不重傳兩套可再生訓練庫。[本機初驗](GENERATION_LOCAL_VERIFIED.json)。

需要讓C/D或F/G使用時，在新的研究副本將它們的來源位置指向生成的B/E資料；保留原雜湊檢查，不改舊紀錄假裝路徑一樣。平台或套件版本造成不同時會停止，不能直接放寬原來源限制。

## 按輪取得本批原件

在新的專案副本、使用已登入的GitHub CLI：

```powershell
python Tools/download_research_assets.py --repo rio10255254/GMM_2_Final --tag research-round-source-followthrough-20261022 --output ../round-source-download --prefix Experiments/R147_FullResPSFConsistency
python Tools/research_asset_bundle.py restore --manifest ../round-source-download/RESEARCH_ASSETS.json.gz --assets ../round-source-download --destination . --prefix Experiments/R147_FullResPSFConsistency --keep-identical-existing
```

兩行前綴一致；完整取得本批130份則省略`--prefix`。R32模型與原EQ輸入分別用`Experiments/R32Sandbox`及`Training_Data/generated_convolved/Real_Image`；其他輪依清單原路徑選取。文件中的舊D/H絕對位置用於追溯，在新的副本依實際恢復位置調整設定，原紀錄保留不改。

## R63缺件原因的新證據

找到[2026-08-13原清理紀錄](../../../Experiments/R63_CausalBoundaryMotionAblation/results/cleanup_archive_20260813/cleanup_manifest.json)：它記載保留32個`completion_run_dir`，刪除其他56個目錄。其中包含原第24輪選中模型的`074102`目錄，而保留的是後來完成60輪的`113034`。該清理所依據名單的原內容雜湊與現存名單一致；選中模型位置與完成續訓位置不是同一件事。[逐條衝突核對](R63_MISSING_MODEL_CAUSE.json)。

紀錄記載刪除，且該原檔目前仍未找到；本次沒有刪研究資料，也沒有用後來版本代替。新查找應針對8月13日前的備份／交付，而不是重複找9月後相同封存。若將來清理，必須同時保護當年實際選中模型與完成目錄，不能只看complete=true。原完整表與31個已保存模型仍保留，原32模型全套重跑仍有這一缺口。

這是本輪指定來源項目的交付，並非全專案全部來源已完成。正在訓練、論文與原始研究資料保留。

## 這批實際交付核對

本版10個附件已全部從GitHub取回，130個原件完整恢復且內容相同；50個一般程式／文件／小模型及3個固定恢復工具也實際下載。兩個附件模型與15個小型測試模型共17個均以CPU開啟，模型數值可讀且有限；未執行推論或訓練。原R32拆分紀錄的570／30項與600個原索引對上，這不等於新的獨立實拍驗證。

從GitHub取回的資料生成入口和兩支原碼，另外在新位置重新產生兩套NPZ，完整內容仍符合原雜湊；既有輸出拒絕覆寫。[實際生成收據](GENERATION_FROM_GITHUB_VERIFIED.json)／[完整交付收據](DELIVERY_VERIFIED.json)。

逐輪帳本目前31個範圍已有本次指定面向核對，並非31輪的全部來源已閉合。後續以帳本的未查項目接續；先前534個引用候選分類完成，也不代表所有動態、相對路徑或新加入檔案已審完。
