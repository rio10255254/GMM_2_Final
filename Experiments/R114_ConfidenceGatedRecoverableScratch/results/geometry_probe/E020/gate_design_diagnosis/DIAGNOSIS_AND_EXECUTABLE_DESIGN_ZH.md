# R114 E20 幾何閘門診斷與可執行修正設計

## 結論先行

E20 目前不是「修正量不夠」，而是**同一個閘門同時決定銳化與位移**。這讓模型在看得出邊緣寬度、但無法可靠定位邊緣中心時，仍然可能啟動位移。R74 的拆解實驗已經直接顯示：位移在非對稱模糊與照明不均時有用，卻在邊界淡化、低對比和混合困難情境造成退步。

下一版應做精準而局部的架構修正：保留既有局部控制器、SDF、法向量、修正需求、寬度與位移渲染器，新增兩張互相獨立的空間判斷圖：

1. `width_reliability`：此處的邊緣寬度是否足以可靠估計。
2. `shift_reliability`：此處的邊緣中心是否唯一、穩定、可精準定位，而且所需修正落在 ±1.5 px 能力內。

兩者必須分別控制銳化與位移，不能再共用一張 `geometry_gate`。這項修正需要新的 scratch probe；不應接續 E20 權重。

## 本次實際驗證範圍

- 凍結的 R74 五類資料，共 100 張、每類 20 張。
- 每張最多取 1,200 個已知真實邊界點，共 120,000 點。
- 每點沿已知 SDF 法向讀取 -12 到 +12 px 的 source/target 剖面。
- 對照 R114 E20 的 `geometry_gate`、`normal_shift` 與 `width_gain` 內部圖。
- 對照已完成的 R74 Full、WidthOnly、ShiftOnly ACM 拆解結果。
- 沒有啟動訓練，沒有改動 model、training 或 config 主檔。

## 已確認的根因

### 1. 現有共用閘門幾乎在所有已知邊界上打開

五類 R74 的 E20 邊界閘門中位數為：

| R74 類別 | E20 共用閘門中位數 |
|---|---:|
| 非對稱模糊與光暈 | 0.911 |
| 局部邊界消失 | 0.964 |
| 極低對比 | 0.933 |
| 混合困難 | 0.959 |
| 照明不均 | 0.965 |

這不是依照「位置是否可靠」做判斷，而是只要被視為邊界就大多放行。即使在新真值判定為位移不可靠的點，現有共用閘門的每張中位數仍達 0.857；可靠點為 0.960。差異太小，且兩者都過高。

### 2. 現有位移輸出與可由 source/target 推得的正確局部位移沒有關係

120,000 個已知邊界點上，E20 `normal_shift` 與剖面真值的 Spearman 相關係數為 0.000096，p=0.973。也就是目前位移頭在此資料上的方向與大小幾乎沒有可驗證關係。

### 3. WidthOnly 與 ShiftOnly 的效果證明兩種操作不能共用可靠度

R74 鎖定 ACM 結果相對 Raw：

| 操作 | 整體平均邊界距離變化 | 非對稱模糊 | 邊界淡化 | 低對比 | 混合困難 | 照明不均 |
|---|---:|---:|---:|---:|---:|---:|
| Full | +0.866% | -15.286% | +1.823% | +0.299% | +0.866% | -0.496% |
| WidthOnly | +1.379% | -12.095% | +0.269% | +0.052% | +1.379% | +0.164% |
| ShiftOnly | +5.283% | -5.381% | +0.325% | +0.459% | +1.510% | -0.446% |

負值代表改善。位移確實能保留非對稱模糊和照明不均的優勢，但不能在所有邊界啟動。邊界淡化的 ShiftOnly IoU 更下降 0.00869，是最清楚的錯誤證據。

## 新空間真值如何產生

這些真值只能由已知 synthetic source、target、mask/SDF 產生；真實顯微影像不會被當成訓練答案。

### 共同前處理

1. 用 SDF 固定正負方向並取得邊界法向。
2. 對每個邊界點沿法向擷取 -12 到 +12 px 剖面。
3. source 與 target 各自用左右兩側平台值做局部正規化，因此亮暗極性、局部曝光增益、偏移與緩慢照明坡度不會直接變成假位移。
4. 以兩個輕微平滑尺度（本次為 0.85、1.45 px）估計正向梯度的中心與分散程度。
5. 真值只在 SDF 邊界帶內有效；正式實作時把邊界點可靠度沿 SDF 法線延伸到渲染所需的窄帶，而不是讓遠離邊界的背景參與。

### Width 真值

- `width_gain_target` = source 邊緣 10–90 寬度 / target 邊緣 10–90 寬度，限制在 1.0–3.5。
- `width_reliability` 由下列證據連續組合，不做硬式開關：
  - source/target 極性一致；
  - source 邊緣對平台雜訊的訊噪比；
  - 剖面是否大致單調；
  - 兩個平滑尺度估出的寬度是否穩定；
  - source 邊緣對比是否仍可見。
- 低可靠度時讓寬度真值平滑退回 1.0，而不是留下不可信的激進增益。

### Shift 真值

- `normal_shift_target` = source 正向梯度中心 − target 正向梯度中心，限制在 -1.5–+1.5 px。這個符號與目前 `grid_sample` 的 flow 方向相符。
- `shift_reliability` 比 width 更嚴格，另外要求：
  - 邊緣中心在兩個平滑尺度下位置一致；
  - 梯度集中在單一轉折，而不是多個雜訊峰或消失邊緣；
  - 依 source 邊緣寬度與訊噪比推得的定位不確定度足夠小；
  - 未截斷位移落在渲染器可表示範圍附近。
- 多個置信因子採幾何平均校準，避免長串相乘後整張圖幾乎全為零，導致可靠度頭再次塌縮。
- 真值位移與可靠度分開保存；不可靠的偏移不是偷偷改成「強力的零位移答案」。

## 五類 R74 的真值分離結果

| R74 類別 | Width 可靠度中位數 | Shift 可靠度中位數 | Shift 保留比例 | Shift 抑制比例 | 可靠度加權位移量 |
|---|---:|---:|---:|---:|---:|
| 非對稱模糊與光暈 | 0.561 | 0.337 | 47.5% | 22.6% | 0.199 px |
| 局部邊界消失 | 0.469 | 0.284 | 40.7% | 28.6% | 0.166 px |
| 極低對比 | 0.229 | 0.054 | 2.0% | 82.0% | 0.057 px |
| 混合困難 | 0.467 | 0.267 | 37.7% | 32.1% | 0.168 px |
| 照明不均 | 0.509 | 0.424 | 62.5% | 12.4% | 0.216 px |

這個結果符合預期：

- 低對比的估計位移絕對值反而最大（0.914 px 中位數），但 82% 會被標成不可靠，因此不會把雜訊偏移交給渲染器。
- 照明不均經局部平台正規化後仍保留最高 shift 可靠度，而不是因整體亮度坡度被關閉。
- 非對稱模糊仍保留中等 shift 與高 width 可靠度，不會為了防低對比而連原本有效的修正一起取消。
- 邊界淡化只有受破壞的局部片段降低，不應把整張影像一刀切掉；這正是空間可靠度而非影像分類的理由。
- 五類 `shift_reliability` 的 Kruskal–Wallis p=3.14e-11，效果量 0.538。
- 以非對稱模糊/照明不均為應保留組，低對比/邊界淡化為應抑制組，sample-level AUC 為 0.885；使用抑制比例時 AUC 為 0.895。
- Width 與 Shift 可靠度相關係數為 0.779，不是同一訊號；全體邊界仍有 4.80% 屬於 width 足夠可靠但 shift 應明顯降低的點。

## 下一版最小且完整的架構修正

### ControllerOutput 新增

- `width_reliability`
- `shift_reliability`

現有 `recoverability` 保留給細節恢復，不能改名冒充上述兩者，因為「可補紋理」、「可估寬度」、「可移位置」是三種不同問題。

### 分離執行路徑

```text
width_gate = boundary_confidence × correction_need × width_reliability
shift_gate = boundary_confidence × correction_need × shift_reliability

flow = predicted_shift × normal × shift_gate
shifted_base = warp(raw, flow)
width_proposal = width_transform(shifted_base, predicted_width)
base_output = shifted_base + width_gate × (width_proposal − shifted_base)
```

重點是最後一行必須以 `shifted_base` 為基準。若仍使用目前的 `raw + geometry_gate × (proposal − raw)`，位移效果會再次被 width gate 間接綁住。

舊 `geometry_gate` 可保留為相容的診斷圖，例如 `max(width_gate, shift_gate)`，但不能再實際控制兩種操作。驗證輸出必須新增 `width_gate` 與 `shift_gate`。

### Identity 與 flat 的語意

- 清晰邊緣可以有高可靠度，但 `correction_need=0`，因此實際 gate 必須為零；這能分清楚「看得準」與「需要改」。
- flat 沒有邊界，兩種可靠度皆為零。
- 這比把清晰影像的可靠度強制設零更乾淨，因為強制設零會讓模型誤以為清楚邊界不可定位。

## Loss 與訓練順序修正

### 必須拆掉的現況

- 不再共用 `geometry_weight`。
- 不再於同一步直接相加 `width loss + shift loss`。
- 不再使用同像素的一階 optical-flow 式 shift 真值；它在低梯度、曝光差及邊緣消失時不穩定。
- 不再只用相同位置的 source/target slope ratio 當 width 真值；邊緣位置稍有偏差就會污染寬度估計。

### 新的四組幾何 loss

1. `width_fit`：只以 oracle `width_reliability` 加權可靠區域的寬度誤差。
2. `width_neutral`：在不可靠區域把 width head 緩和拉回 1，而不是任其漂移。
3. `shift_fit`：只以 oracle `shift_reliability` 加權可靠區域的位移誤差。
4. `shift_neutral`：在不可靠區域把 shift head 拉回 0。

兩個 reliability head 本身需各自接受連續真值監督，並在每張影像內平衡高、低可靠度區域，避免大面積低值讓模型學成全零。可加入每張平均值校準與成對排序，要求同一張圖中清楚片段高於消失片段。

### 建議的 scratch probe 階段

1. **Reliability-only**：先只訓練兩個可靠度頭與既有 boundary/need 維護；確認不是常數圖，且五類排序接近 oracle。
2. **Parameter fit with oracle gates**：訓練 width/shift 參數頭，但渲染暫用 oracle gate，先證明數值真值可學。
3. **Predicted split gates**：換成模型預測 gate，先讓 render loss 不回推破壞可靠度頭，再以低學習率共同微調。
4. **Matched ablation**：相同 scratch seed 與資料，至少比較 width-only、shift-only、split-full；不要拿接續 E20 的結果混入。

每個循環將 width、shift、render、平移一致、曝光一致分開抽樣；尤其 width 與 shift 不在同一步求和。連續 gate 取代部署硬門檻，不需要設定「低於某值完全不能動」的死規則。

## 下一輪必須新增的驗證

- 每四輪輸出 `width_reliability`、`shift_reliability`、`width_gate`、`shift_gate`。
- 逐 family 報告 oracle 與 predicted 的相關、校準誤差和高低區排序，不只看全圖平均。
- R74 重跑 Full、WidthOnly、ShiftOnly；確認低對比 shift actuation 明顯降低，同時照明不均與非對稱模糊仍有動作。
- 對邊界淡化顯示空間圖，確認只關閉局部消失段，不是整張抑制。
- 清晰 identity 必須由 `need≈0` 保持不動，而不是靠 reliability 偽裝成看不懂邊界。
- 分塊驗證新增四張 gate 圖的 grid-origin 與 shifted-origin 一致性。
- 最終仍用 ACM、位移穩定、系統偏差、真實 5/20/50x 與分塊一致性判定；GMF 最後檢查相容性。

## 不應採用的替代方案

- 只把現有 `geometry_gate` 整體乘小：會一併失去 halo/uneven 的有效修正。
- 只縮小 `maximum_normal_shift_px`：雜訊方向仍錯，只是錯得較小。
- 讓 `recoverability` 同時控制紋理、width、shift：會重新製造共用閘門問題。
- 用 family 名稱或影像級分類決定是否移動：邊界淡化是局部問題，同一張圖中同時有可靠與不可靠片段。
- 在真實影像上製造偽 shift label：本設計的幾何真值只來自已知 synthetic pair。
- 直接接續 E20：輸出欄位、gate 路徑與 target 語意都已改變，必須從頭訓練才能保持實驗獨立。

## 本資料夾內容

- `analyze_gate_targets.py`：可重跑的唯讀 R74 真值診斷。
- `sample_statistics.csv`：100 張逐張統計。
- `family_statistics.csv`：五類統計。
- `diagnosis_summary.json`：完整數據、分離與相關性摘要。
- `representative_target_maps.png`：五類 source、target、mask、width/shift 可靠度與 shift 真值視覺檢查。
- `implementation_contract.json`：供下一版實作逐項核對的契約。
- `validation.json`：本診斷交付的完整性與唯讀範圍檢查。

