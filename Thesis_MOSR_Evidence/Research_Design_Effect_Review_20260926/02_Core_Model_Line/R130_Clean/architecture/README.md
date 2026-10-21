# R130-Clean 原尺寸從零訓練

**本輪已完成：8192次scratch訓練、930張原尺寸重建、8370輪廓及全部指定比較／效率檢查。** 值得保留為快速、來源乾淨的純神經研究版本；已保留R129的主要位移穩定性，但沒有解決尺寸偏大，也不是所有形狀指標都更好。 完整數字見 [結果報告](reports/R130_CLEAN_RESULTS.md)。


本資料夾依2026-09-20使用者規格建立，與舊R130_CleanV42Comparison不同；不覆蓋R129。型態為自包含研究程式，資料為既有生成影像的原值白名單副本，非重新生成。

## 模型

從零初始化；不讀歷史神經權重、optimizer或EMA。PSF完全關閉，沒有光學核、FFT或候選選擇。64通道、四個殘差區塊，擴張率1／2／4／2，四次共享更新，全部保持原尺寸。最後Raw加受限累積殘差，無高通再注入或全圖品質校正。

殘差上限0.35；初始每步強度0.05、最大0.25，輸出頭零初始化。每步只使用一次tanh；定義與未明定數值的決斷均在config_r130_clean.yaml（JSON相容YAML）。光學feature_single／feature_field只有保留名稱，嘗試啟用會明確報錯，不會fallback。

## 訓練

512／128／128母場景；source、noiseless、target陣列與舊生成包逐項相同，不解壓PSF／latent／SDF欄位。神經訓練無真實照片、SEM或PI答案。

AdamW，最高1e-3降至1e-5，暖身128、weight decay1e-5、梯度上限5。16循環8192更新，影像＋0.2梯度＋0.2配對殘差。種子1309001／1309002／1309003。FP32，TF32關閉。最後8192預先固定；不自動延長或按實拍選中間模型。

## 使用

以START_R130.cmd啟動，或用本機Anaconda Python執行scripts/launch_r130.py。會先檢查資料與前置，再從新初值訓練，最後才跑930張原尺寸實拍、相同ACM／最大梯度／LSC／PI／SEM讀法與一次效率檢查。

正式run存在但未完成時不會默默覆寫或載入舊模型；先查runs/pipeline_failure.json。已完成訓練後可重新呼叫pipeline接續尚未完成的分析階段，但來源及模型身分必須相同。

單圖推論：infer_r130_clean.py --checkpoint runs/formal_8192/checkpoints/step08192.pth --input IMAGE --output OUTPUT.npz --mode full。tiled選項共用forward，固定512core／96halo，僅取core，不羽化、不改實際尺寸。

## 輸出與範圍

results/reconstruction是H槽活動目錄的連接，避免D槽不足。data與runs保留本輪實際資料及狀態。生成資料準備後，訓練只讀本資料夾；實拍驗證仍依evaluation/capture_plan.json定位原930張。

正式比較只有Raw、R129、R130-Clean；舊模型使用既有固定輸出，沒有載入舊checkpoint。舊R129耗時與新模型即時計時分開標記，不把含寫檔的舊耗時冒充純神經計時。

這是第一階段純神經研究模型，不代表已取代論文主模型或正式基準。現有實拍已用於歷史評估，不再叫未知holdout。SEM兩種方向與尺度限制保留。

最終結果以reports/R130_CLEAN_RESULTS.md及results/complete.json為準；程序消失或step數到頂不等於整個驗收完成。

## 版本紀錄

保留分支codex/r130-clean；原工作樹有大量未提交研究檔，因此不切換或重設使用者工作樹，以完整source hash及起點commit追溯。未作遠端發文、推送或正式基準變更。
