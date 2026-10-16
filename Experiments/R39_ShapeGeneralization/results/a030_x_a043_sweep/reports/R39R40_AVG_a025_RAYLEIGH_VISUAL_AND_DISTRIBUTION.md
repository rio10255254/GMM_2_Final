# a025 Rayleigh 診斷補充:訓練分布對齊 + 視覺驗證

本檔承接 [RAYLEIGH_DIAGNOSTIC.md](R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC.md) 跟 [VALIDATION.md](R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md),補做兩件事:

1. **訓練資料 vs 驗證資料的特徵寬度分布對齊**——R46 微調的訓練資料配比要不要重設計?
2. **視覺驗證**——指標差距是否對應到肉眼可見差異?直角圓角化、三角形變一坨這些 user 原始抱怨是否在影像上真的看到?

## 摘要

**訓練分布發現**:

- **R39 訓練集(safe / strong)完全沒有次解析尺度樣本**(sub-Rayleigh 0%),但 R39 驗證集有 0.5%(1 張)——這 1 張驗證樣本模型訓練過程中沒看過,等於完全外推。但比例極小,影響有限。
- **R40 訓練集跟驗證集分布幾乎對齊**(supra 58 vs 60%、sub 21.5 vs 18%)——R40 微調這條線**訓練覆蓋充足**,R46 不需要重新設計訓練資料配比覆蓋 sub-Rayleigh。
- R39 訓練集中位數 stroke width = 512 像素(整張畫面填滿大形狀為主);R40 訓練集中位數 = 33 像素(顯微細節為主)。兩條訓練資料線在尺度上互補,a025 微調如果繼續用 R40 train 加 R39 ring replay 的混合配方,**sub-Rayleigh 覆蓋已經夠**。

**視覺驗證發現**:

- **小三角形變一坨確認是真實現象**(sub-Rayleigh case):stroke width 6 ~ 8 像素的小三角形在所有四個模型上都重建成模糊塊狀,邊界完全消失——這是物理上限的直接視覺證據,不是模型缺陷
- **矩形直角圓角化也是真的**:雖然 a043 / a025 比 COMBO / a030 緩和,但所有模型都有一定程度的圓角化(這跟非相干 PSF 的物理事實一致——直角 step 過 PSF 後本來就會有 Rayleigh 半徑左右的圓化)
- **紋理 case(a043 PSNR +3 dB 大贏 a025)在縮圖上肉眼差異不大**——指標差距明顯但視覺感受相對溫和;需要放大單張對比才看得到細節區別
- **多邊形 case(a043 統計上贏 a025,但 paired delta 在所有指標上幾乎不顯著)在視覺上幾乎看不出差別**,證實 [VALIDATION.md](R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md) 「multi-stage mean 反例是雜訊」結論

## 訓練資料 vs 驗證資料分布

### 五個 profile 的完整分布

| Profile | n | 中位數 sw (px) | supra% | mixed% | sub% |
|---|---:|---:|---:|---:|---:|
| R39_train_safe | 1240 | 512 | 96.4 | 3.6 | **0.0** |
| R39_train_strong | 1590 | 512 | 94.3 | 5.6 | **0.06** |
| R39_val_unseen | 210 | 182 | 84.8 | 14.8 | 0.5 |
| R40_train_microscopy | 400 | 33 | 58.3 | 20.3 | 21.5 |
| R40_val_unseen | 100 | 30 | 60.0 | 22.0 | 18.0 |

(R40_train_microscopy 只計新加的 stage_29-33,不含 ring replay 跟 R39 shape replay 那兩塊)

### 兩個重要對齊事實

**R40 訓練覆蓋完美對齊驗證**:

- supra 訓 58.3% vs 驗 60.0%(差 1.7 個百分點)
- mixed 訓 20.3% vs 驗 22.0%(差 1.7 個百分點)
- sub 訓 21.5% vs 驗 18.0%(差 3.5 個百分點)

R40 訓練資料對所有三個 Rayleigh class 都有充分覆蓋,a043 看過的特徵尺度跟 R40 驗證集對齊。a025 是 a030 跟 a043 的權重平均,**a025 對 R40 顯微特徵的能力傳承自 a043** —— R46 想推 R40 顯微方向的話,訓練資料配比繼續用 R40 train 就好,不需要重做。

**R39 訓練幾乎完全不含次解析尺度**:

- R39 train safe:**0 張 sub** (n = 1240)
- R39 train strong:1 張 sub (n = 1590)
- R39 val unseen:1 張 sub (n = 210)

R39 訓練資料偏重大形狀(中位數 512 像素 = 畫面填滿)。a030(R39 形狀主訓)幾乎沒看過次解析尺度,但 R39 驗證集裡這類樣本也只佔 0.5%(1 張),所以這個訓練偏斜對 R39 線整體驗證影響極小。**a025 在 R39 驗證集上的表現不該被「R39 train 沒看過 sub」拖累**,因為 R39 驗證集本身也幾乎沒 sub。

### 分布視覺化

`distribution_overlay.png`(疊放直方圖)看到:

- R40 訓練集 / 驗證集 兩條紅色橘色線在 sub-Rayleigh 區段(< 11.7 px)分布**幾乎完全重疊**——對齊
- R39 訓練集 / 驗證集 三條藍色線在大尺度區段(> 100 px)集中,sub 區段稀疏

`class_composition_bar.png`(堆疊長條)直觀看 5 個 profile 的 supra / mixed / sub 比例,R40 訓/驗的紅色 sub 長度幾乎一樣。

### 對 R46 訓練資料配方的建議

**修正前(在 VALIDATION.md 沒看到分布前):**「R46 訓練資料偏重 stage_31(紋理)、stage_30(大區塊)、stage_33(混合場景)。」

**修正後(看到分布對齊):**

- **直接繼承 R40 train 既有配方**(550 環形 + 350 R39 形狀 + 400 R40 顯微 = 1300 對),不需要重新設計訓練覆蓋
- 如果要動,**加重 R40 顯微的 stage_31 / stage_30 / stage_33 比例**(從 80 / stage 各加到 100-120 / stage),其他保持
- **不需要刻意增加 R39 sub-Rayleigh 樣本**——R39 驗證集本身就幾乎沒這類,沒有強驗證壓力
- **不需要刻意減少 R40 sub-Rayleigh 樣本**——驗證集分布跟它一致,而且這 21.5% 訓練資料對「模型至少看過次解析尺度」是有價值的(避免模型在次解析尺度純外推)

## 視覺驗證

五組視覺對比圖位於 `rayleigh_diagnostic/visual_verification/`,每組三到四個 case,每 row 並排顯示 GT / COMBO / a030 / a043 / a025 + a043 − a025 差值摘要。

(matplotlib 字型 fallback 導致圖內中文標題顯示為方塊,但圖像本身跟英文 metadata 完整,要 polish 顯示中文可重跑加 Microsoft JhengHei 字型;不影響本報告觀察。)

### 1_top_wins_textures.png — a043 PSNR 贏 a025 最多的紋理 case

挑 3 張 stage_31_micro_textures(PSNR 贏 2.5 ~ 3.5 dB)。

**觀察**:

- GT 是密集的紋理 pattern(stippled high-frequency texture)
- 各模型都能還原大致 pattern,但細節清晰度有差:**COMBO < a030 < a025 ≈ a043**(視覺上 a043 跟 a025 接近,COMBO 最糊)
- a043 比 a025 PSNR 贏 3 dB 在縮圖縮放下肉眼不顯著,但仔細看 a043 的小亮點對比比 a025 略強
- **這驗證了一件事:R46 微調的 +0.6 ~ +1.0 dB 預期增益,視覺上會是「微小提升」而不是「天翻地覆」**——不要對 R46 視覺改善期望過高

### 2_a043_small_losses_big_shapes.png — a043 微輸的大形狀 case

挑 3 張:stage_04_ellipses 0381(輸 0.66 dB)、stage_02_circles 0184(輸 0.46 dB)、stage_05_polygons 0475(輸 0.31 dB)。

**觀察**:

- GT 都是大尺度形狀(橢圓、圓、多邊形,寬度 100+ 像素)
- 四個模型還原都很相似,**a043 跟 a025 視覺幾乎一樣**
- 沒看到「a043 過銳化導致邊緣不穩」的具體視覺證據——這跟 [VALIDATION.md](R39R40_AVG_a025_RAYLEIGH_DIAGNOSTIC_VALIDATION.md) 統計檢驗結論一致(p = 0.18,不顯著)
- 結論:a043 在這些「已經很容易」case 上的 mean 退步是雜訊,沒有真實視覺異常

### 3_rectangles_right_angles.png — 直角(user 原始抱怨)

挑 3 張 stage_03_rectangles。

**觀察**:

- GT 是矩形 + 其他形狀混合場景
- **所有模型在矩形直角處都有圓角化現象**——COMBO / a030 明顯較圓,a043 / a025 較銳但仍非完美直角
- 這個圓角化是**非相干 PSF 的物理事實**:即使是完美直角過 PSF 後,corner 也有 Rayleigh 半徑一半左右(約 5 ~ 6 像素)的曲率半徑
- **R46 fine-tune 在直角上的改善空間是有限的**——COMBO → a043 的差距已經接近物理上限,R46 從 a025 推到 a043 水準,可能就是極限
- 視覺上區分:**COMBO 直角 ≈ R = 8 ~ 10 像素;a043 / a025 ≈ R = 5 ~ 7 像素**(粗估)。物理 PSF 下限大概 R = 5 像素左右,a043 已經很接近

### 4_triangles_small.png — 小三角形(user 原始抱怨「三角形變一坨」)

挑 4 張 stage_01_triangles,按 sw_median 排序最小到中等:

| frame | sw_median | Rayleigh class |
|---|---:|---|
| 0097 | 6.0 px | **sub** |
| 0085 | 8.4 px | **sub** |
| 0079 | 10.8 px | mixed |
| 0095 | 11.2 px | mixed |

**觀察(這是最重要的視覺驗證)**:

- **次解析尺度 case(0097、0085,寬度 6 ~ 8 像素)**:GT 看得到小三角形邊界,但**四個模型重建出來都變成模糊塊狀,完全沒有三角形形狀**——「三角形變一坨」是 100% 視覺事實
- **混合區 case(0079、0095,寬度 10 ~ 11 像素)**:邊界開始可辨,但三角形仍然模糊,各模型差異小
- **這四個 case 都看不出 a043 比 a025 有意義改善**——符合物理預期(訊號被 PSF 砍掉)
- **結論:「三角形變一坨」確認是物理上限的視覺證據**,R46 微調**對 stroke width < 8 像素的三角形幾乎沒救**

### 5_polygons_corner_test.png — 多邊形(VALIDATION 結論驗證)

挑 3 張 stage_05_polygons。前一輪報告誤以為 a025 在這個 stage 贏 a043,VALIDATION 已證實為雜訊。

**觀察**:

- 視覺上 a043 跟 a025 幾乎完全一樣,看不到 a025「贏」的視覺證據
- 跟 VALIDATION 的 paired t-test p = 0.85 結論一致

## R46 設計指引綜合修正(累積這三份報告)

| 設計面向 | 第一版(RAYLEIGH_DIAGNOSTIC) | 統計驗證版(VALIDATION) | 視覺 + 分布驗證版(本檔) |
|---|---|---|---|
| 整套學 a043 方向 | 要避反例 | 沒反例,可全推 | **確認**,視覺也支持 |
| 訓練資料配比 | supra 偏重、避 stage_29 | 補強 stage_31 / 30 / 33 | **直接用 R40 train 既有配比**(58/20/22) |
| 角點加權強度 | 5 倍(避 sub 過銳化) | 5 倍(守環形守門) | 5 倍(守環形守門,sub 過銳化視覺也沒看到) |
| 次解析尺度平滑懲罰 | 必要 | 可選 | **不必要**——次解析尺度物理本來就回不來,模型已經是「猜得最像」狀態,加 penalty 邊際小 |
| 預期 PSNR 增益 | +0.64 ~ +1.02 dB | +0.63 ~ +1.01 dB | 同樣量級,**但視覺上是「微小銳化」不會天翻地覆** |
| 對「直角變圓」改善 | 訓練問題、可推 | 統計上 a043 在矩形 stage p < 10⁻¹⁵ 贏 a025 | **物理上限 ~ R = 5 像素**,a043 已接近,R46 改善幅度有限 |
| 對「三角形變一坨」改善 | sub-Rayleigh 不要期望 | 同 | **視覺確認次解析尺度三角形無解**,R46 對 stroke width < 8 像素的三角形完全幫不上忙 |

### 最關鍵的兩個新啟示

1. **R46 視覺改善期望要校準**——指標 +1 dB 對應的肉眼差別比想像中溫和。如果使用者期待 R46 後「直角變圓、三角形變一坨」消失,要先講清楚:**直角圓角化是物理上限,只能改善不能消除;三角形變一坨在次解析尺度完全無解**。
2. **R46 訓練資料配方可以直接複用 R40 train**——不需要重新設計覆蓋,因為 R40 train 對 R40 驗證集分布完美對齊。R46 launcher 可以幾乎照 R40 配方做,只調 learning rate / epoch 數 / corner-aware loss 強度。

## 限制

- 視覺驗證圖內中文標題顯示為方塊(matplotlib 字型 fallback 到 DejaVu Sans 不含中文)。要看清中文標題請重跑腳本並指定 Microsoft JhengHei 字型,或將腳本內 title 改英文。圖像跟英文 metadata 完整,不影響觀察。
- 視覺驗證每組只挑 3 ~ 4 個代表性 case,不是 exhaustive。如要看更多 case,在 `rayleigh_visual_verification.py` 的 `CASES` 字典追加即可。
- 訓練分布只看 GT label 的 stroke width,沒看 source image 的 PSF blur 後分布——但對「模型訓練看過什麼尺度的結構」這個問題,GT 分布是 ground truth。

## 產物

| 檔案 | 內容 |
|---|---|
| `../rayleigh_diagnostic/train_val_distribution/feature_width_per_profile.csv` | 五個 profile 逐影像 stroke width 跟 Rayleigh class |
| `../rayleigh_diagnostic/train_val_distribution/profile_summary.csv` | 五個 profile 的 n / 中位數 / class 比例 |
| `../rayleigh_diagnostic/train_val_distribution/distribution_overlay.png` | 疊放直方圖 |
| `../rayleigh_diagnostic/train_val_distribution/class_composition_bar.png` | Rayleigh class 堆疊長條 |
| `../rayleigh_diagnostic/visual_verification/1_top_wins_textures.png` | 紋理大贏 case |
| `../rayleigh_diagnostic/visual_verification/2_a043_small_losses_big_shapes.png` | 微輸大形狀 case |
| `../rayleigh_diagnostic/visual_verification/3_rectangles_right_angles.png` | 矩形直角 case |
| `../rayleigh_diagnostic/visual_verification/4_triangles_small.png` | 小三角形 case |
| `../rayleigh_diagnostic/visual_verification/5_polygons_corner_test.png` | 多邊形 case |
| `Experiments/R39_ShapeGeneralization/scripts/rayleigh_train_val_distribution.py` | 分布腳本 |
| `Experiments/R39_ShapeGeneralization/scripts/rayleigh_visual_verification.py` | 視覺驗證腳本 |

## 可重跑

```bash
cd D:/GMM_2_Final
python Experiments/R39_ShapeGeneralization/scripts/rayleigh_train_val_distribution.py
python Experiments/R39_ShapeGeneralization/scripts/rayleigh_visual_verification.py
```

兩個腳本都讀現成檔案,無需重跑 a025 重建。

本檔不下硬性 verdict;訓練分布跟視覺觀察是事實紀錄,R46 設計細節仍由人類拍板。
