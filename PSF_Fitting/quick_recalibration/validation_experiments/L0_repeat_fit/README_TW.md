# L0 Repeat Fit — Set A

對 FOV `[1, 5, 10, 41, 45, 50, 91, 95, 100]`(grid row 1/5/10 × col 1/5/10)跑 BADS 15 次,量演算法 noise floor。

- **設計脈絡**:[DESIGN_TW.md](../../DESIGN_TW.md) §10.2(L0 層)+ §10.6.1(校準 Test 1 的 noise floor)
- **進度與結論**:[../README_TW.md](../README_TW.md)
- **跑法**:
  1. MATLAB Current Folder = `d:\GMM_2_Final\PSF_Fitting\`,跑 `run_L0_repeat_fit.m`
  2. PowerShell 在 `d:\GMM_2_Final\` 跑 `python analyze_L0_noise_floor.py` 跟 `python deep_analyze_L0.py`
- **產出**:`outputs/trial_XX/`(15 個)+ `outputs/manifest.json` + `outputs/noise_floor.json` + `outputs/deep_analysis.json` + 兩份 `outputs/L0_*_report.md`
