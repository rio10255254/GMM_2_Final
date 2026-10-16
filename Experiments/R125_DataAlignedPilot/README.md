# R125 — 資料相容性修正與第一輪實際小試跑

本輪執行 R124 後的下一步：獨立建立訓練資料，檢查資料與模型是否相容，接上真正的訓練及固定實拍／SEM 檢查。

**已完成六組各64次更新與全部12次實拍評估；沒有可採用模型，不進入長訓練。** 數值相容性修正後成立，但實拍亮暗範圍與成像假設仍不充分。見 [完成結果](reports/R125_RESULTS.md) 與 [可離線閱讀的完整報告](reports/R125_REPORT.html)。

**第一版資料未通過，並沒有直接拿來訓練。** 三個細密／尖角場景暴露2倍表示的格內資訊流失，另一個場景暴露Float32形狀判斷問題。原檔與失敗保留；第二版用8倍Float64生成、4倍成像狀態與2倍學習網路，保留全部原來的形狀／模糊／雜訊／位移條件。64場景全部通過原先相容性限制，僅准做已知模擬条件的小試跑，沒有儀器或真實效益認證。

## 實際範圍

- 64個新場景、各2張觀測；原生640px及中央128px監督。
- 三組A/B/C、兩個共同初始化起點，各64次更新，合計384次。
- 每組自己的初始／64次結果都跑固定實拍面板；全部六個初始結果在更新參數前量完。
- 實拍面板為六張固定完整影像，加六組位移序列各前兩張的固定區域。SEM對照為兩種曝光、36柱、兩套參考；不是完整364張面板或全301幀位移驗證。
- 本輪不是R123原先規劃的512場景／1024更新大比較；實際校準與正式應用門檻仍未具備。

進度讀 `runs/matrix_state.json`、各run的`state.json`和`sample_ledger.jsonl`，不要把程序停止當成完成。執行結束後以`reports/R125_RESULTS.md`和`results/final_verification.json`為準。

## 入口

- `data/generator.py`、`data/package/`：失敗第一版，保留且不准訓練。
- `data/generator_v2.py`、`data/package_v2/`：獨立8倍生成的第二版；64個物理條件與第一版相同。
- `results/data_audit_v1.json`／`data_audit_v2.json`：同門檻的獨立審查，第二版准入綁定精確清單指紋。
- `prototype/network.py`：四倍成像、兩倍學習的模型修正；舊R124不改。
- `prototype/factorized_observation.py`：保留原光學核的有界數值加速；不是重新擬合PSF。
- `training/train_pilot.py`：真實讀取、損失、更新、來源紀錄及權重保存。
- `scripts/evaluate_real_pilot_v2.py`：固定實拍評估，明確替換為同一個未校準的實拍成像假設；不沿用最後一筆訓練PSF。
- `scripts/run_matrix.py`：依序執行全部初始評估、六次訓練／評估及共同人口彙整。

## 重現

使用 `C:\Users\Rio\anaconda3\python.exe`，在本資料夾執行。既有輸出不能覆寫；重跑須另立輸出版本與來源紀錄。

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' -m unittest discover -s tests -v
```

原本的執行命令已保存於`runs/launcher_logs/matrix_execution.log`與各階段紀錄；不要直接重跑已存在的矩陣，程式會拒絕覆寫。

已訓練checkpoint是R125格式，不能用R124的「只接受未訓練初始化」載入器。實拍推論請走R125評估入口；它核對所有學習參數，另綁固定的實拍觀測設定並保留未校準標記。

自包含型態，分支`codex/r125-data-aligned-pilot`，容量預算12GiB。保留兩版資料、所有初始／最終權重、每筆抽樣紀錄、失敗、實拍輸出及比較；不删除舊資料、不重設舊確認、不改舊模型／收據。
