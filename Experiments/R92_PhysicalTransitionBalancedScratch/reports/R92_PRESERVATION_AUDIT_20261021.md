# R92 完成狀態、來源與GitHub保存審查

本文件是2026-10-21事後保存審查，沒有重新訓練、改原數字或升級模型。

## 真正的完成狀態

原結束摘要記`status=complete`、完成80輪，時間2026-08-12T05:53:24.736385。原CSV恰有80列、輪次從1連續到80，沒有重複或缺輪；最後20個已記錄驗證量與結束摘要逐值相符，診斷旗標也相同。

原run_progress.json仍保留active，屬最後一次進度快照，不能取代結束摘要；本次沒有改寫這份歷史原件。

- [原結束摘要](../runs/training_R92_scratch_seed920041_20260812_015138/run_summary.json)
- [原完整逐輪表](../runs/training_R92_scratch_seed920041_20260812_015138/training_log.csv)
- [未改寫的舊進度](../runs/training_R92_scratch_seed920041_20260812_015138/run_progress.json)
- [來源身分與核對收據](../../../docs/reproducibility/scratch_lineage/COMPLETION_RECORDS_VERIFIED.json)

## 方法與必要來源

保留局部且分塊穩定的主幹，改以受控更新比例抽曝光組、記錄非對稱物理邊緣過渡、分開退化細節恢復與原圖保護，移除不穩定的自適應細節控制；正式種子920041、1250場景／5000觀測、無舊權重或教師初始化。

原實際資料身分為`260ccc5b4e31727e7fc97082b831717aa4c06d9f429ef98a5ce1210cb49bf5d5`。原生成器、匿名光學統計、資料檢查／修復、實際陣列、當時初值、保存模型、原表與既存影像分開保留，不能用R93或其他後代配方替換。原紀錄說明沒有把SEM／HS100MG像素或模型輸出直接當作訓練答案；匿名成像統計仍帶有來源關係，不據此宣稱後續SEM評估獨立。

## 必須一起保留的不利讀值

原資料中identity_and_detail_guard一組，最後pixel相對Raw比值為2.959113，texture相對Raw比值為7.678571。這是原資料組別的彙整，不把它改稱逐張完全無退化的恆等輸入測試，也不拿不同輪的組別比例直接排名。

原診斷：identity_mean_abs_gray, clear_texture_change_gray, physical_transition_profile_error, raw_clear_added_topology_failures, motion_mae_px, motion_p95_px, cross_observation_contour_gray, signed_motion_bias。完成訓練不等於所有清楚輸入、尾端位移、結構或曝光問題都已解決。

| 原最後驗證量 | 原值 |
| --- | ---: |
| val_identity_gray | 2.6888752587139608 |
| val_added_topology_failures | 7 |
| val_motion_mae | 0.2865655081612723 |
| val_motion_p95 | 1.1064659118652338 |
| val_motion_bias_x | -0.040957132975260414 |
| val_motion_bias_y | -0.095575968424479171 |
| val_tile_gray | 0 |

## 保存與實測界線

完整來源清單中已找到最後第80輪兩個模型位置，內容已核對並列入模型保存；相同內容的別名不算獨立訓練。最後epoch不是本次重新選出的冠軍。完整模型、必要原資料與完整結果由[全專案入口](../../../docs/reproducibility/project_completion/README.md)逐批取回核對。這份審查沒有重跑當年GPU訓練，也沒有以狀態校正冒稱完整外部驗證已通過。

COMBO與目前論文採用身分不變；原論文、訓練工作區與所有D槽研究原件保留。
