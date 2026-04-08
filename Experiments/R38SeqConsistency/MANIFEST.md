# R38 — Sequence Consistency Training (Original)

| 欄位 | 值 |
|------|---|
| Round | 38 |
| Branch | `sandbox/r38` |
| Status | **部分成功** — 8px 最佳但 0.8px 弱，被 R38v2 取代 |
| Mechanism | Seq training 全 10 stages (624 pairs), no signal gate, no warmup |
| External GMF | 未送（internal 0.8px 0.159 不夠好） |
| Checkpoint | `Traing_Progress/..._20260406_122842/weights/best_tradeoff.pth.tar` |
| Key Reports | `reports/R38_RESULTS.md` |

**注意**: R38 的 edge steepness +9% vs R30 是啟發 R38v2 三重修復的關鍵線索。
R38v2 在此基礎上加入 signal gate + warmup + 8px-only 修復了 0.8px 問題。
