# R114 E24 profile 階段退化診斷

## 結論

E24 的問題不是模型「做得太多」這麼簡單，而是 profile 分支學到的動作方向本身大多不正確。E20 的 geometry base 在固定 128 張驗證集 MAE 為 0.0264231；E24 開啟 profile 後變成 0.0271575，退化 2.78%。

最主要的原因依證據排序如下：

1. Profile 的四個輸出頭沒有學會其監督目標。profile 階段只允許四個 1x1 輸出頭更新，提供特徵的 renderer backbone 被凍結；但那個 backbone 先前只為寬度與位移動作訓練，沒有為 midpoint、contrast、profile width 與 visibility 學習可分辨特徵。結果 midpoint Spearman 為 -0.0245、contrast 為 0.2598 且幅度斜率只有 0.0269、width 甚至為 -0.3097。
2. 訓練與實際輸出的邊界座標不一致。profile loss 用真實 SDF 形成輪廓，但部署輸出用模型預測的 SDF。E24 的預測 SDF 在真實邊界帶內符號一致率只有 60.38%，與真實 SDF 的 Spearman 只有 0.1169，真實零邊界上的預測偏離平均 2.16 px。即使換成正確 profile 參數，放在預測 SDF 上仍比 base 差；同一組正確參數改用真實 SDF 才開始優於 base。
3. Visibility 開得過度。真實 profile band 中預測平均 0.6592，標籤平均只有 0.3712；當標籤不超過 0.05 時，預測仍平均 0.4671，而且 48.60% 的像素被開到至少 0.5。這使錯誤方向的動作被大量放行。
4. 目前的 profile loss 評分的是「真實 SDF 上、尚未經最後 gate 的理想 proposal」，不是部署時真正輸出的影像；物理 guard 也用 source 作為差值基準，而實際 profile 是疊加在 geometry base 上。因此訓練分數下降，不保證最後輸出變好。

## 方向與極性檢查

- 真正產生動作的像素中，profile_delta 指向 target 的比例只有 34.76%，低於隨機的 50%。
- 實際動作在邊界帶造成 -0.006295 的平均 gain；保留相同動作幅度、只把方向改正，可得到 +0.004063；再限制不超過真實誤差，可得到 +0.006960。問題主要是方向，而不是「動作一定不能太大」。
- 全部翻轉 contrast 並沒有改善，MAE 由 0.0271575 變成 0.0271731。因此不是單一全域極性寫反，而是參數、邊界座標和可見度三者共同錯配。
- 改用 base 或 raw 計算 midpoint cue 都沒有改善，代表 shift-first、width-second、profile-last 的作用順序本身不是這次主要根因。

## Gate 與樣本分解

- Identity 的 profile gate 平均只有 0.000312，flat 為 0，clear/identity 保護有作用，不是主要退化來源。
- 一般 edge 的 visibility 預測 0.883、標籤 0.578；textured edge 預測 0.853、標籤 0.396，退化主要集中在真正需要重建的影像。
- asymmetric halo 最嚴重：方向一致率 21.71%，visibility 預測 0.971、標籤 0.259，邊界 gain 為 -0.01651。
- 唯一稍微正向的是 five_x_dense；其方向一致率 55.86%，邊界 gain 約 +0.000094。

## Oracle 拆解

- E24 實際 MAE：0.0271575。
- 只把 visibility 換成標籤：0.0265603，雖仍略差於 base，但已收回大部分損失。
- 正確參數 + 預測 SDF：0.0269799，仍然退化，證明預測 SDF 座標是獨立問題。
- 正確參數 + 真實 SDF + 現有控制因素：0.0261256，開始優於 base。
- 再移除 recoverability 的重複抑制：0.0254595。
- 僅保留 boundary confidence 與 oracle visibility：0.0251959。
- 完整 oracle gate：0.0240857。這證明 profile 這個動作空間仍有能力，失敗的是學習與 gate 對接，不是 profile 概念本身無效。

## 精確修復方向

1. Profile 階段必須讓 profile 專用特徵層一起學習；可保留 geometry 主幹凍結，但要新增/開放 profile adapter，不能只訓練四個 1x1 頭。
2. 最終影像損失必須直接作用在實際 `output`，包含預測 SDF、實際 band、完整 gate 和 geometry base。真實 SDF 只保留作為 supervision，不再拿它代替部署座標形成 render loss。
3. Profile 先做 predicted-SDF coordinate warmup：固定 controller/geometry，讓參數頭在部署座標上學會產生正向 gain；若 SDF 品質達不到門檻，profile gate 必須依座標可信度下降。
4. Visibility 改成以「最終動作是否降低 base-to-target error」為標籤，並加入低標籤像素的明確負樣本校準；不要再單獨追逐目前的 soft Dice，使整張 degraded edge 快速飽和。
5. Recoverability 不應在 profile visibility 已經包含可用性後再重複相乘。下一個短 probe 應分別測試完整控制、移除 recoverability、boundary+visibility 三種 gate，並以 sealed MAE/ACM 和 identity/tile guard 共同選擇。
6. 在修正前，不應把 E24/E28 profile checkpoint 升為正式模型；E20 geometry checkpoint 仍是本輪安全錨點。

完整逐樣本與家族結果見 `diagnosis.json` 與 `scene_metrics.csv`；`validate_diagnosis.py` 會核對 checkpoint、訓練驗證數字與主要因果反事實是否一致。
