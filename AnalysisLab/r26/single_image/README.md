# R26 Single-Image Analysis

這條分析線聚焦於 `R26` demo input 的單張 reconstruction 幾何品質。

內容分工：
- `scripts/`
  - `run_single_image_analysis.py`：主分析入口
- `tests/`
  - `test_single_image_analysis.py`：幾何偵測、circle fit 與 fixture regression 測試
- `inputs/`
  - tracked demo input fixture 與 preview
- `recon/`
  - tracked reconstruction fixture 與 preview
- `results/`
  - 圖表與 `analysis_summary.json`
- `reports/`
  - 人類可讀分析報告

這條線現在是自含 fixture，可在不依賴 `_deployment_package` 的情況下重跑分析與測試。
