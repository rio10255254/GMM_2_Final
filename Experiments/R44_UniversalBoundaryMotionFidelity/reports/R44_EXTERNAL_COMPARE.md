# R44 外部 GMF 紀錄

目前尚未送外部 GMF。

R44 是研究優先路線；外部 GMF 在這一輪只作舊能力紀錄，不作通用顯微邊界位移忠實度研究價值的淘汰條件。

本輪已先補 `r44_motion_from_r42_best` 的本地三尺度環形代理紀錄，結果相對 COMBO 退步明顯：

| 尺度 | R44B internal step std y | COMBO internal step std y | 相對 COMBO |
|---|---:|---:|---:|
| 8px | 0.2015 | 0.1389 | +45.1% |
| 0.8px | 0.2214 | 0.1509 | +46.7% |
| 0.08px | 0.1568 | 0.1185 | +32.3% |

因此 R44 第一版暫不主動送外部 GMF 作升級判定；若未來需要補外部紀錄，仍可依下列流程放入九份外部 GMF 結果後產生正式比較表。

外部結果放入 `results/external_gmf/` 後，使用：

```powershell
python Experiments\R44_UniversalBoundaryMotionFidelity\scripts\r44_external_compare.py --candidate-name <candidate>
```

產生本報告的正式比較表。
