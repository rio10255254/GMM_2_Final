# R26 Sequence Analysis

這條分析線聚焦於 `R26` 三尺度 odd-frame sequence 的幾何穩定性。

內容分工：
- `scripts/`
  - `run_sequence_analysis.py`：主分析入口
- `tests/`
  - `test_sequence_analysis.py`：pairing、step stability、circular stats、hotspot persistence 等測試
- `configs/`
  - `dataset_config.py`：外部 raw input / baseline recon / GMF score 的依賴宣告
- `results/`
  - 各尺度圖表、JSON 摘要與 cross-dataset comparison
- `reports/`
  - 人類可讀分析報告

注意：
- 這條線追蹤的是 analysis outputs、測試與設定，不追蹤外部原始 sequence dataset 本體
- 若日後新增 `r30` 或 `r32` sequence 分析，沿用同一層級即可
