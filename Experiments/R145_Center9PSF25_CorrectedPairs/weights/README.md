# 權重身分

本輪從零完成 8192 次訓練，沒有載入 R143、R140v2 或 V42 的神經權重。正式 R145 保存點在 `../runs/formal_8192/checkpoints/step08192.pth`，SHA-256 為 `c112d59e1d3efbb281059ca443bebf26c1ce7202e9b586740bca7b86d001ab41`。預設單張推論入口使用此保存點；套件完整性和同張實拍的批次重播均已通過。完整效能和選 PSF 的限制見 `../reports/R145_RESULTS.md`。
