# R26NewPSFCheck：換新 PSF 重訓為什麼退步，以及新 PSF 怎麼升為標準

[研究時間線](<../../docs/research/TIMELINE.md>)（在 R25～R29 那一列） · [PSF 政策切換說明](<../../docs/policy/PSF_POLICY_TRANSITION_R26.md>)

**一句話：** 2026-03-26 完成全視野 100 個位置的新 PSF 擬合，用它在 R26 正式交付包裡重訓模型，結果在 Demo 影像上大幅退步（例如邊緣連續性從 0.994 掉到 0.267）。這個 sandbox 同一天把原因拆開：純對照證明在相同訓練 recipe 下，換新 PSF 跟舊 PSF 的結果幾乎重合，真正的問題是那次重訓同時換掉了訓練與選模的設定（recipe 漂移）。3/27 以「物理優先」的原則，把新 PSF 加上同 recipe 的替換權重升為 current standard，舊 PSF 保留為 legacy empirical baseline。

| | |
|---|---|
| 結果 | **分析**（找出退步的真因；新 PSF 依物理優先原則升為 current standard） |
| 時間 | 2026-03-26 重訓、比較與 PSF 流程稽核；03-27 升級與政策切換 |
| 實驗條件 | A：R26 交付包的 Demo 影像，以及 NTU 三尺度外部資料（Pitch 1、0.1、0.01 µm）的外部 GMF 重建 |
| 起點 | R26 正式交付包的訓練腳本（`r26_sm035` recipe） |

## 一步一步發生了什麼

| 階段 | 結果 |
|---|---|
| 新 PSF 重訓（3/26 早上） | Demo 單張上幾乎每項都退步：弱邊界 CNR 33.34→7.79、邊緣連續性 0.994→0.267、棋盤格傾向 0.121→0.215；只有環厚度一致性改善 |
| PSF 正式擬合流程稽核 | 程式與 `formal_config.json` 一致、Python 6 項與 MATLAB 11 項測試全過，擬合流程本身沒有壞 |
| 根因調查 | 新舊 PSF 的主要差別是對齊方式（峰值從 (49,51) 到 (50,50)），不是變寬；新舊兩次訓練還差了 AMP、決定性設定、種子等執行設定；`best_tradeoff` 選到的是第 16 輪 |
| 純 PSF 對照 | 舊 recipe 加舊 PSF、舊 recipe 加新置中 PSF，在第 10／20／40 輪的單張指標幾乎重合（例如第 40 輪主邊界 CNR 15.94 對 15.89） |
| 升級（3/27） | 用同 recipe 的替換權重把新 PSF 升為 current standard；交付包的訓練、推論、煙霧測試都通過 |

## 讀這些內容要知道的事

1. **退步的真因是「PSF 變更加上 recipe 漂移」一起發生**，選模規則不匹配是共犯但不是完整解釋。不能寫成「PSF 一置中模型就崩」。
2. **升級的標準不是「全面勝過舊版」**，而是新 PSF 物理上較合理、使用面沒壞、同 recipe 下沒重現崩壞；些微的數值退步視為政策切換的代價。
3. **外部 GMF 分數沒有回填。** 三尺度重建在 3/26 已完成並建好回填位置，但這個資料夾裡沒有 `GMF_score.txt`，所以「新舊 PSF 在外部 GMF 上誰好」沒有在這裡回答。
4. **政策的權威說法在** [`docs/policy/PSF_POLICY_TRANSITION_R26.md`](<../../docs/policy/PSF_POLICY_TRANSITION_R26.md>) 與 `docs/policy/PSF_STANDARD_POLICY.json`；README 開頭也註明 3/27 之後以它們為準。

## 拿資料與重做

外部三尺度重建：`Tools/run_external_recon_newpsf.ps1`（可用 `-WeightsPath`、`-CandidateName` 指定權重）；需要原電腦上的 NTU 資料集。交付包驗證測試在 `package_repro_validation/tests/`；`package_policy_transition/tests/` 的政策守門測試依賴本機的 `_deployment_package` 中繼資料。

> 權重快照、外部重建與清理封存的位置：查 `python Tools/cloud_locator.py where Experiments/R26NewPSFCheck/<路徑>`。

## 原始報告

| 文件 | 內容 |
|---|---|
| [新 PSF 重訓比較](<reports/new_psf_retrain_compare_20260326.md>) | 先讀這份：Demo 單張的完整指標 |
| [純 PSF 對照解讀](<pure_psf_control/reports/PURE_PSF_CONTROL_INTERPRETATION_20260326.md>) | 同 recipe 下新舊 PSF 幾乎重合 |
| [根因調查](<root_cause_centering/reports/ROOT_CAUSE_CENTERING_REPORT_20260326.md>) | 對齊語意、執行設定差異、選模 |
| [正式升級比較](<formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md>) | 3/27 的升級判定 |
| [PSF 流程稽核](<psf_audit/PSF_FORMAL_AUDIT_20260326.md>) | 擬合程式的四項檢查 |
| [狀態摘要](<reports/STATUS_20260326.md>)、[README](<README.md>) | 3/26 的整體狀態與 sandbox 說明 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R26NewPSFCheck.md>)。
