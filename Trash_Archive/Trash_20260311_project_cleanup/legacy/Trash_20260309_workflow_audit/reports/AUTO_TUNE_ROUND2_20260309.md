# 0307 Round2 自動化調整

## 狀態

- 狀態：執行中
- 日期：2026-03-09
- 目標：
  - 以 `8 px` 已知步長穩定度為第一優先
  - 嘗試保住 round1 早期穩定點，不再讓後段 stage 轉換把 KPI 拉垮

## round1 給出的直接訊號

- round1 最佳點幾乎都出現在很早的 epoch
- `SWP_stdg` 在早期最穩，但 `final 18 epoch` 明顯退化
- 問題不是 seed 完全錯，而是後段：
  - weak-PSF
  - physics
  - 幾何 ramp
  的介入時機太早或太重

## round2 策略

核心思路：

- 不再從頭訓練
- 直接用 round1 保留下來的內部最佳 seed：
  - `selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`
- 測試四個 warm-start 候選：
  - `step8_seed_stage0_hold`
  - `step8_seed_stage0_sharp`
  - `step8_seed_no_weakpsf`
  - `step8_seed_hold_general`

共同方向：

- 延長 stage0 / early freeze
- 延後 weak-PSF 啟動
- 延後 physics 介入
- 延後 eq ramp
- 避免再跑進 round1 後段崩壞區

## 本輪命令

```powershell
python -u Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py --sweep-epochs 6 --final-epochs 14 --deterministic
```

## 本輪 log

- `pending/logs/auto_tune_console_20260309_105107_round2.out.log`
- `pending/logs/auto_tune_console_20260309_105107_round2.err.log`
- `pending/logs/auto_tune_console_20260309_105107_round2.meta.txt`

## 備註

- `20260306` 正式基準版不變
- `20260307 selected/` 目前代表 round2 的續訓 seed
- round2 跑完後，仍需你用外部 GMF 流程做最終驗證
