# R115 完整設計與執行結論

## 架構

- 影像動作完全沿用 R109：法線中點位移與單調寬度修正。
- 新增獨立法線剖面線，沿法線擷取 -12 到 +12 px 的九點剖面。
- 新分支不共享 detector/renderer 參數，梯度不能進入幾何主體。
- 初始輸出精確等於 R109；新分支只能把兩種作用量調成 0.85–1.15 倍。
- 無自由殘差、無新輪廓 renderer、無全域 pooling/FFT/空間正規化。

## 資料

- R115 內含 R114 平衡版 5,000 train / 512 validation 的硬連結資料包。
- 200 張新增訓練資料與 40 張新增驗證資料均完整保留。
- 已建立 A/B/C/D 四組同種子短測：
  - A：R109 原始 2,048。
  - B：R114 替換版 2,048，含 200 新資料。
  - C：A 加全部 200 新資料。
  - D：A 加 100 新資料。

最佳固定驗證結果（gray，越大越好）：

| Arm | Best epoch | Common gain | Supplemental gain | Clear change |
|---|---:|---:|---:|---:|
| A | 5 | 0.032255 | 0.055676 | 0.000539 |
| B | 6 | 0.031296 | 0.053411 | 0.000707 |
| C | 5 | 0.029100 | 0.048302 | 0.000362 |
| D | 3 | 0.027270 | 0.045011 | 0.000477 |

結論：新資料能加速早期學習，但沒有提高六輪最佳上限。正式幾何與法線證據若未來重開，應使用 R109 原始資料；40 張新增驗證保留為封閉 hard holdout。

## 失敗後的精準修正

第一版讓新分支重新決定 0–100% 採用率，負例代價使模型全部關閉並退回 Raw，已停止並保留失敗紀錄。

第二版降低負例權重後仍有不穩定全域採用率，已停止。

第三版改成以 R109=1.0 為中心、最多 ±15% 的殘差作用量，成功穩定改善內部 common/supplemental validation，且清晰影像改動低於 0.001 gray。

## Locked ACM

R115 A E2：

- R73 mean boundary distance 0.165173，略優於 R109 E48 約 0.1658。
- R74 mean boundary distance 2.513892，略差於 R109 E48 2.4989。
- R74 translation-only family 對齊：只有 uneven illumination 略優；asymmetric halo、boundary fade、low contrast、mixed hard 四類略差。

R115 A E5：

- R73 0.170987。
- R74 2.514944。

因此內部最佳 E5 不是外部最佳；E2 也未通過 R74 worst-family 保護。正式 48 epoch scratch 訓練不授權啟動。

## 已完成工程

- 資料準備、硬連結與 A/B/C/D 清單。
- 完整模型、兩條獨立參數路徑與 canonical tiled inference。
- 四階段 scratch trainer：detector、geometry、profile evidence、joint。
- 動態退化、清晰配對、固定驗證、預覽、checkpoint、CSV/JSON 紀錄。
- 11 項模型/資料/梯度測試全通過。
- 四階段 GPU smoke 全通過；峰值 reserved 約 4.14 GiB。
- R73/R74 locked ACM 各 100 張、primary/sensitivity 零 failure。

## 下一步

不要直接跑 R115 48 epoch。若要再次推進，應先找出低對比 family 的作用方向錯誤，或把法線剖面只作 training-time dense midpoint/width supervision，而不是 inference-time action adjustment。

