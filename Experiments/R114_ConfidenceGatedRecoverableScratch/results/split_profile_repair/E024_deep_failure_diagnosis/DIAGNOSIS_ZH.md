# R114C E24 深層失敗診斷

## 一句話結論

R114C 並不是把 R114B 的修復「全部做錯」。它確實讓 contrast、width 與 visibility 的學習明顯進步，但同時拿掉了原本 `need × recoverability` 的雙重煞車；尚未學準的 profile 動作因此被放大。真正的核心問題已縮小成：**visibility 並沒有判斷「目前這個已學到的 proposal 是否真的朝 target 變好」，而 boundary confidence 只知道哪裡像邊界，不知道動作方向是否正確。**

因此 R114C E24 不應續訓或升為候選模型；E20 geometry 仍是安全錨點。下一次修正也不應只是把整體動作縮小，因為 0 到 1 的倍率掃描顯示整體最佳倍率就是 0。

## 固定條件與重放確認

- 兩個 checkpoint 都以相同的固定 validation：epoch 0、128 張、256×256 重新推論。
- R114B 以舊控制式重放後，MAE 為 0.0271575291，與原紀錄差 8.8e-8。
- R114C 以新控制式重放後，MAE 為 0.0274378917，與原紀錄差 1.8e-7。
- 兩個總輸出變化量也都能重現原 training validation 紀錄。
- 所以這不是重新評估方式改變造成的假差異，可以直接做因果比較。

## R114C 實際做錯了什麼

### 1. Profile 動作方向仍低於可用標準

- geometry base MAE：0.0265218472。
- 開啟 R114C profile 後 MAE：0.0274378917，退化 0.000916045，約 3.45%。
- 真正有動作的像素中，依動作幅度加權的方向正確率只有 44.07%；R114B 是 34.76%，雖然進步，仍低於 50%。
- 真實邊界帶內有 58.97% 的位置被動作弄得更差。
- 真實邊界帶平均 gain 為 -0.007615，明確為負。
- asymmetric blur/halo、band-limited noise、nonuniform PSF 的 gain 分別約 -0.01498、-0.01271、-0.01199；只有 five_x_dense 出現很小的正 gain（約 +0.000091）。

這表示問題不只是幅度太大，而是動作選擇仍常常放錯方向。

### 2. 單純縮小動作無法挽救

把 E24 已產生的 profile delta 乘上 0、0.025、0.05，一直到 1.0：

- 全域 MAE 最佳倍率：0。
- 真實邊界帶 MAE 最佳倍率：0。
- 倍率 0.025 時 MAE 已從 0.0265218470 增至 0.0265314890。
- 倍率 1.0 時是 0.0274378911。

雖然少數單張影像可從非零倍率受益，但各 role 的逐張最佳倍率中位數都是 0。這代表下一輪不能只加一個固定縮放係數；需要逐位置判斷「這次動作是否安全」。

### 3. Boundary-only gate 是本次退化被放大的直接原因

R114B 的 profile gate 使用 boundary × need × recoverability × visibility × band。R114C 改成 boundary × visibility × band。用同一個 R114C checkpoint 做反事實：

| R114C gate 版本 | MAE |
|---|---:|
| 不做 profile（geometry base） | 0.0265218472 |
| 現行 boundary-only controller gate | 0.0274378917 |
| 加回 need | 0.0271790077 |
| 加回 recoverability | 0.0267966643 |
| 加回 need 與 recoverability | 0.0266858944 |

舊的雙重煞車可消除現行退化的 82.09%，但仍比 base 差，所以它只能「掩蓋錯誤」，不能根治方向錯誤。另一方面，過去 oracle 已證明 recoverability 也會抑制正確動作，因此不能把舊 gate 原封不動當最終答案。

### 4. 為何 visibility 明明下降，profile delta 反而更大

原 training log 的 `delta_abs` 是「最後 output 相對 raw」的總變化，不是純 profile delta。本次把 geometry 與 profile 拆開後仍可確認 profile 本身確實變大：

- 全圖 visibility：R114C 只有 R114B 的 18.30%。
- 真實邊界帶 visibility：R114C 是 R114B 的 48.96%。
- 兩者尚未乘 gate 的 proposal 幅度幾乎相同；R114C 是 R114B 的 92.75%。
- 但 R114C 現行 gate 在真實邊界帶平均 0.18738；R114B 舊 runtime gate 只有 0.11016，R114C 反而是 1.70 倍。
- 最終有效 profile delta 在真實邊界帶：R114C 3.6009 gray，R114B 2.5982 gray，R114C 是 1.386 倍。
- R114C 若套回自己的舊式三因子 gate，gate 會從 0.18738 降到 0.04682。
- 最後 output 對 raw 的平均變化由 R114B 的 0.1796 gray 增至 R114C 的 0.4170 gray，正好對應 log 中 0.000704 與 0.001635 的差別。

所以「visibility 低但 delta 大」並不矛盾：visibility 下降了，但原本更強的兩層抑制同時被移除，乘積最後反而更大。

## R114C 修復其實成功的部分

R114C 開放 profile 專用特徵層、改用部署座標並直接評分最終輸出後，參數學習比 R114B 好很多：

| 項目 | R114B Spearman | R114C Spearman | R114C 幅度斜率 |
|---|---:|---:|---:|
| midpoint offset | -0.0201 | 0.1911 | 0.0384 |
| signed contrast | 0.2740 | 0.6956 | 0.6727 |
| profile width | -0.3341 | 0.3969 | 0.0812 |

- contrast sign agreement 已達 87.72%，是明顯進步。
- visibility 對新 counterfactual target 的 Spearman 為 0.5765，weighted MAE 0.1078；R114B 對同一個新 target 的 weighted MAE 是 0.4397。
- 因此 C 不是重演 B 的「四個頭完全學不到」；contrast 已相當可用，width 與 midpoint 則有排序但幅度仍嚴重壓縮。

這些成功部分應保留，不應把 C 的所有改動全部回退。

## Visibility 仍失敗的深層原因

### 1. 新 target 與預測在平均值接近，但關鍵位置仍錯

- 依 supervision weight 計算，target 平均 0.08213，prediction 平均 0.09954，看起來很接近。
- 但真實邊界帶 target 平均 0.23696，prediction 平均 0.32278，仍明顯過開。
- target ≤ 0.05 時 prediction 仍平均 0.05864，且有約 4.99% 的權重被開到至少 0.5。
- identity target 明確為 0，但 identity 真實邊界帶 prediction 仍約 0.2273。
- 嚴格 identity challenge 的 base MAE 約 0.0000163，開啟 profile 後升到約 0.0005965，約 36.7 倍。這是不能忽略的 hard failure。

### 2. Predicted SDF 並不是可直接拿來當 profile 距離的可靠座標

- 真實邊界帶內 predicted SDF 符號一致率：61.59%。
- 與真實 SDF 的 Spearman：0.1381。
- 真實邊界帶內平均絕對座標誤差：5.22 px。
- 真實零邊界上的預測偏移：2.07 px。
- 更關鍵的是 predicted profile band 在整張 validation 影像的支援率是 100%，而真正的 true profile band 只佔 18.66%。

因為 predicted band 幾乎覆蓋全圖，visibility supervision 也覆蓋了 100% 像素；真正 target visibility > 0.05 的位置卻只有 9.73%。模型於是主要在學大量容易的背景零值，造成全圖 visibility 很低，但真正邊界帶的校準仍不夠準。這正是「平均很低、關鍵邊界仍過開」的來源。

### 3. Visibility target 仍假設 profile parameters 是正確的

目前 counterfactual visibility target 是用 clean target 推出的 oracle midpoint、contrast、width，再問這個理想 proposal 是否能改善影像；部署時 visibility 實際控制的卻是模型當下學到的 proposal。只要 parameters 尚有誤差，target 認為安全的位置，對目前 proposal 不一定安全。

反事實結果清楚分離出這個問題：

- 現行 predicted visibility + learned parameters：MAE 0.0274379，退化。
- 換成新的 counterfactual target visibility、仍保留 learned parameters：0.0263301，已優於 base。
- 直接對「目前 learned proposal」求逐像素最佳 visibility：0.0252463，還能再大幅改善。

因此新 target 有用，但還不是最貼近部署動作的 target；visibility 應針對目前 proposal 的實際 signed gain，而不是只針對理想 proposal。

## Oracle 反事實：Profile 概念沒有失效

| 反事實 | MAE |
|---|---:|
| geometry base | 0.0265218 |
| target visibility + learned parameters + predicted coordinate | 0.0263301 |
| target parameters + target visibility + predicted coordinate | 0.0256462 |
| target parameters + target visibility + true coordinate | 0.0249963 |
| learned parameters + predicted coordinate + 逐像素最佳 visibility | 0.0252463 |
| target parameters + predicted coordinate + 逐像素最佳 visibility | 0.0246671 |
| target parameters + true coordinate + 逐像素最佳 visibility | 0.0245847 |

Profile action space 仍有明顯上限，而且即使保留 predicted coordinate，只要 action selection 正確，也能從 0.0265218 降到 0.0246671。這表示下一個首要問題不是再增加動作種類，而是把「當前 proposal 的方向與幅度是否安全」學準；coordinate 校準是第二個可再取得的增益。

## 精確修正建議

1. 保留 R114C 已成功的 profile adapter/backbone、final-output loss 與 predicted-coordinate 路徑；不要整體回退成 R114B。
2. Visibility target 改成以當前 learned proposal 的 stop-gradient 版本計算逐像素 signed gain 與最佳 0–1 作用量。可拆成「能不能做」與「做多少」兩個輸出，避免一張 soft visibility 同時承擔方向、可靠度和幅度。
3. Visibility loss 不要再讓 predicted band 的全圖支援帶來大量容易的背景負樣本。訓練時應在 true/deployment boundary 聯集附近做平衡抽樣，另外明確加重 identity、錯方向與低 target visibility 的 hard negatives。
4. Boundary confidence 只負責定位邊界，不可再被當作動作正確性的充分條件。在新 gain gate 尚未驗證前，可保留 recoverability/need 作為安全上限或旁路保護，但不應永遠以三項連乘壓住正確 oracle 動作。
5. Predicted SDF 必須另外校準成可用的局部距離，或讓 profile coordinate 從局部零交叉重新生成。現在 band 100% 覆蓋全圖，已證明它不能直接充當距離支援範圍。
6. 下一個短 probe 先固定 E20 geometry，只訓練 profile selection；以實際 final output 的 gain、identity 零動作、R74 五類最差案例與 tile 一致性判斷。不要直接續訓 R114C E24。

## 可重跑與自洽驗證

- `probes/profile_failure/diagnose_r114c_e24.py`：重放 B/C E24、執行倍率掃描、參數校準、gate 分解與 oracle 反事實。
- `probes/profile_failure/validate_r114c_e24_diagnosis.py`：核對 checkpoint 雜湊、固定 128 張、原始 validation 重放、倍率端點、反事實方向及分析來源未被改動。
- `diagnosis.json`：完整機器可讀結果。
- `scene_metrics.csv`：每張影像與每個 challenge 的逐項結果。
- `validation_report.json`：29/29 項通過。

本次分析只讀取 checkpoint 與資料，沒有修改模型、訓練程式或訓練資料，也沒有啟動任何訓練。
