# External GMF 三方比較報告

**日期：** 2026-03-16
**比較對象：** round18_baseline vs round22_stepguard vs round22_hold
**目的：** 決定是否升級 current adopted model，並解決 stepguard vs hold tie-break

---

## 原始數據

### Pitch1um_Y_100（1um / 8px 大尺度）

| 模型 | mean_step | std | mean_abs_err | neg_step% | mean_score0 |
|------|-----------|-----|--------------|-----------|-------------|
| round18_baseline   | 8.0238 | 0.2507 | 0.2055 | 100.0% | 79.1540 |
| round22_stepguard  | 8.0245 | **0.2454** | **0.1991** | 100.0% | 79.1151 |
| round22_hold       | 8.0198 | 0.2887 | 0.2334 | 100.0% | 79.7062 |

### Pitch0.1um_Y_60（0.1um / 0.8px 主戰場）

| 模型 | mean_step | std | mean_abs_err | neg_step% | mean_score0 |
|------|-----------|-----|--------------|-----------|-------------|
| round18_baseline   | 0.8039 | **0.2855** | **0.2238** | 100.0% | 77.1855 |
| round22_stepguard  | 0.8019 | 0.3336 | 0.2784 | 100.0% | 77.0545 |
| round22_hold       | 0.8015 | 0.2855 | 0.2320 | 100.0% | **77.2075** |

### Pitch0.01um_Y_40（0.01um / 0.08px 次要尺度）

| 模型 | mean_step | std | mean_abs_err | neg_step% | mean_score0 |
|------|-----------|-----|--------------|-----------|-------------|
| round18_baseline   | 0.1678 | 0.1458 | 0.1149 | 69.2% | 80.1559 |
| round22_stepguard  | 0.1390 | **0.1194** | **0.1001** | 66.7% | 80.3881 |
| round22_hold       | 0.1602 | 0.1224 | 0.1061 | 66.7% | 80.2802 |

---

## 尺度別勝負判讀

| 尺度 | 勝者（std + mae 雙優） | 判讀 |
|------|----------------------|------|
| 1um (8px) | round22_stepguard（微幅） | std: 0.2454 vs 0.2507；mae: 0.1991 vs 0.2055 |
| 0.1um (0.8px) **主戰場** | round18_baseline 或 round22_hold（並列） | stepguard 明顯退步（std +0.048，mae +0.055）；hold 與 R18 持平 |
| 0.01um (0.08px) | round22_stepguard（明顯） | std: 0.1194 vs 0.1458；mae: 0.1001 vs 0.1149 |

---

## 主戰場（0.8px）細節分析

round22_stepguard 在 0.8px 尺度明顯退步：
- std：0.2855 → 0.3336（+16.8%）
- mean_abs_err：0.2238 → 0.2784（+24.4%）

round22_hold 在 0.8px 尺度與 round18 持平：
- std：0.2855 = 0.2855（相同）
- mean_abs_err：0.2238 → 0.2320（+3.7%，微幅退步）

**結論：Round22 在主戰場（0.8px）未能超越 Round18 baseline。**

---

## Internal vs External 落差分析

| 指標 | Round18 | Round22 stepguard | 落差倍數 |
|------|---------|------------------|---------|
| internal center_err (0.8px) | 0.8574 px | **0.1845 px** | 4.6× 改善 |
| external GMF std (0.8px) | 0.2855 | 0.3336 | **退步** |

Internal gate 顯示 Round22 有 4.6× 的 center_err 改善，但 external GMF 反而退步。

**這是本專案最關鍵的新發現：internal pairmix 指標與 external GMF 位置穩定性之間存在根本性脫節。**

可能原因（待後續分析）：
1. pairmix 改善的是 training-time estimator alignment，但 GMF 使用的是 annulus geometry 的整體重建質量
2. internal center_err 衡量的是估計器預測的位移誤差，不直接對應 GMF 的定位精度
3. Round22 在 0.8px 上的 step_err 訓練壓縮可能損害了 GMF 用到的某種圖像特徵

---

## 決策結論

按計畫決策規則：

> 「兩者都不優於 Round18 → 不升級；回頭分析 internal/external mismatch，不再開 generic training round」

**→ 不升級 current adopted model。Round18/r18_ec_highcenter 維持為 current adopted baseline。**

Round22 的 stepguard 與 hold 候選均未能在主戰場（0.8px GMF）超越 Round18。

---

## Tie-break 結果

本次外部驗證同時解決了 stepguard vs hold 的 tie-break：

- stepguard：在主戰場退步，但在 0.01um 表現最好
- hold：在主戰場與 R18 持平，在 0.01um 次優

由於主戰場（0.8px）是決策主軸，hold 的外部表現優於 stepguard。**但由於兩者都未能超越 Round18，這個 tie-break 在目前決策中無實際效力。**

---

## 下一步

1. 保持 Round18 為 current adopted model
2. 深度分析 internal pairmix center_err 改善 vs external GMF 定位穩定性之間的 mismatch
3. 不再開 generic training round，除非找到 internal/external gap 的根本原因
4. 需要建立一個能真正預測 external GMF 表現的 internal surrogate metric

---

**產出日期：** 2026-03-16
**製作：** Claude Code
