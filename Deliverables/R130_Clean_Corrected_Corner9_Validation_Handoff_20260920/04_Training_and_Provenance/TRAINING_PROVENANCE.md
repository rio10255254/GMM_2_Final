# R130-Clean 訓練來源

- 從零訓練：YES。正式run初始SHA256：0d4a4b3ed24b224df65640a3e0ec243c24b270dde6204ac5de00c40707e3a4a3。
- 載入舊神經／optimizer／EMA／step strength：NO。
- PSF：OFF，無PSF參數或檔案讀取；資料準備只保留source/noiseless/target，不解壓存放的kernel4。
- SEM／PI／實拍訓練：NO。真實影像只在8192最終模型保存後進入驗證。
- synthetic data：YES，512／128／128；母場景ID及幾何雜湊跨組交集0。
- 正式更新：8192，最後模型預先固定；32次sanity使用獨立scratch實例並丟棄。
- 最終SHA256：559afeff214ff15e92ce910d7df7ead12994074b6173dabe9a7f21a8b40372cc。
- 原始規格及未指定數值的決斷保存於config； source_lock在正式啟動前建立，未用新雜湊覆蓋歷史收據。

執行核對不能單獨證明模型效果；請讀R130_CLEAN_RESULTS.md的完整位移、尺寸、輪廓與效率數字。
