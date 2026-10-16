# L0 Repeat Fit — Set B

對 FOV `[12, 16, 19, 52, 56, 59, 82, 86, 89]`(grid row 2/6/9 × col 2/6/9,跟 setA 完全不重疊)跑 BADS 15 次。
目的:驗證 setA 偵測到的「2 個收斂域」是 BADS 對這類問題的常態,還是那組 FOV 的特例。

- **設計脈絡**:同 setA,參數設定也同步(同 GT、同 fitter、同搜尋範圍、同 lock_tilt、同 rng 策略)
- **進度與結論**:[../README_TW.md](../README_TW.md);跨組對比 → [../setA_vs_setB_comparison.md](../setA_vs_setB_comparison.md)
- **跑法**:同 setA,把腳本名換成 `_setB`(`run_L0_repeat_fit_setB.m` + 兩支同名 Python)
- **產出**:同 setA 的結構,寫在本目錄的 `outputs/`
