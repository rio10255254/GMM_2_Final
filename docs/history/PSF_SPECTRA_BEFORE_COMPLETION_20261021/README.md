# GitHub較早版本的光學頻譜資料

這兩份NPZ由實際取回、完整核對過的GitHub程式副本保存，來源版本是`5d1f79bf76b61cbd362ef9fb4df33235ca9898f9`。目前本機工作版仍留在論文圖表的原位置，沒有改寫。

20倍的原拍頻譜數值相同，但反捲積與V42輸出頻譜不同；50倍的較早陣列為256×257，目前工作版為256×256。這是真正的內容／範圍差異，不能用同名或相近大小當成同一版。

此處保存較早內容供版本追查，並不裁定哪一版應被論文採用，也不重新計算或改寫原研究結論。具體來源與逐欄核對見[版本對照](../../reproducibility/project_completion/SPECTRA_VERSION_AUDIT.json)。

另在`figures/20x`及`figures/50x`保存兩張較早的反捲積頻譜圖，實際從GitHub版本`80a3aef91fb63c77def3a65f95bfae27d112d4c9`取回。兩張較早圖說均標NSR=0.08；本機現圖標NSR=0.05與background-normalized，現存MAT內的NSR也確實為0.05。不能將兩版視為只有版面大小不同；也不能把所有差異只歸因於NSR，因為V42頻譜與50倍輸入範圍另有差異。

原FFT函式已用現存相機裁切、既存V42輸出與未裁切的Wiener小數陣列重算，16份陣列、458832個數值與現存NPZ完全相同。這項核對不重做PSF擬合或V42推論，也不冒稱重現較早0.08圖的生成過程。[兩版圖與目前來源的說明](../../reproducibility/optical_calibration/SPECTRA.md)。
