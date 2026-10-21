# 結果分工

preflight.json與sanity_updates.json為正式訓練前的合成資料檢查，不是正式8192步成果。

reconstruction連接到H槽保存930張原尺寸浮點NPZ與16bit顯示PNG；centers保存相同ACM／最大梯度／LSC讀值。comparison保存三方法位移、尺寸、輪廓、SEM及完整扫描配對範圍。profile.json保存原尺寸／切塊計時與GPU記憶體。

complete.json只有在訓練、生成測試、930張推論、量測、統計、profiling與報告完成後才寫入。所有歷史原檔保留，不刷新歷史證據的預期雜湊。
