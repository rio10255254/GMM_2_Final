# L0 Repeat Fit — BADS 演算法 noise floor 量測實驗

> **目的**:量出「同一張影像、相同起點、BADS 跑多次」的 Zernike 係數標準差,
> 作為 DESIGN §9.3 Test 1 的 `noise_floor_std`,之後所有「機台是否真的變了」的 z-score 判決都用它做分母。
>
> **狀態**:已實作,未執行。
> **參考**:[`../../DESIGN_TW.md`](../../DESIGN_TW.md) §10.2 (L0 層) + §10.6.1 (校準 Test 1 的 noise floor)

---

## 1. 在做什麼(白話版)

打個比方:你買了一支體溫計,想知道「就算量同一個人也會差多少度」——這就是體溫計的精度下限。
本實驗就是在測 BADS 擬合演算法的精度下限:

- **同一張影像**(完全沒拍攝噪聲、沒機台變化)
- **同一個起點**(都從 `[0,...,0,1]` 開始,確保唯一變數是演算法本身的隨機性)
- **跑 5 次**,看 5 次解出來的 Zernike 係數差多少

這個差異就是「**演算法噪聲地板**」(noise_floor_std)。
之後評估「新機跟模板的差異」時,小於這個地板就直接判為「沒實質變化」。

## 2. 為什麼要量這個

整套快速校正方法的歸因測試有一個核心邏輯:

> 機台 A 跟模板的差異 = 機台真實變化 + 拍攝噪聲 + 演算法噪聲

如果不知道演算法噪聲多大,就分不出來「這台機真的變了」還是「只是 BADS 抖一下」。
量錯了會兩種情況都壞:

- noise floor 估太大 → 真的變了也說沒變 → 校準漏網
- noise floor 估太小 → 沒變也說有變 → 校準誤報

L0 量這個地板,L1 之後的層在它之上加拍攝噪聲、機台介入,逐層拆解差異來源。

---

## 3. 實驗設計選擇(以及為什麼)

### 3.1 跑哪些 FOV 點:9 個

選 `[1, 5, 10, 41, 45, 50, 91, 95, 100]`,對應 10×10 grid 的角落 + 中心 + 邊中。

| 為什麼不跑全部 100 點 | 100 點 × 5 次 = 500 fits ≈ 8–10 hr,等同跑 5 次完整 WholeFOV,過頭了 |
| 為什麼不只跑中心 1 點 | 不同 FOV 位置的 PSF 形狀不同,BADS 收斂難度也不同——只跑中心會錯過邊角的 noise floor |
| 為什麼正好是這 9 點 | 跟 DESIGN §7.3.1 L1 的稀疏抽樣位置對齊,L1 跑完直接拿同位置 noise floor 校準 z-score |

### 3.2 跑幾次:5 次

- 太少(< 3):std 估計不穩
- 太多(> 10):邊際效益低,時間成本翻倍
- DESIGN §10.2 寫的就是 N=5,跟它對齊

### 3.3 起點:預設 `[0,...,0,1]`,不換 x0

- 設計目的是測「演算法的隨機性」,不是「對起點的敏感度」
- 用同起點才能把 noise 來源鎖在 BADS 內部(initial design 的 random sampling、GP surrogate 的取樣)

### 3.4 確保 5 次真的有差異:`rng(trial_idx)`

- BADS 內部 initial design 是 random,但 MATLAB 預設 rng 是 deterministic
- 如果 5 次都用同 seed,可能跑出完全一樣的結果
- 每次跑前 `rng(trial_idx)` 強制換 seed,確保 5 次的 random sampling 真的不同

### 3.5 warm_start:**自動失效**(設計有照顧到)

- 底層 fitter (`HDR_fitting_2D_WholeFOV_candidate_prealign.m`) 的 warm_start 條件是 `ki > 1`
- 9 點各自跑一次,**每個 FOV 點都是 ki=1**(因為每次 trial 是獨立呼叫)
- 等於 warm_start 在 L0 自動失效——這是好事,L0 想看的是純粹從 x0 開始的隨機性

### 3.6 GPU:有就用

- `use_gpu=[]` 讓底層自動偵測 `gpuDeviceCount > 0`
- 有 GPU 速度差很多

---

## 4. 怎麼跑

### 4.1 前置

```matlab
% 在 MATLAB 中,確認 Current Folder
cd('d:/GMM_2_Final/PSF_Fitting');

% 確認 SimulatePSF 在 path
addpath(fullfile(pwd, 'SimulatePSF'));
```

### 4.2 執行

```matlab
% 切到 L0 目錄(腳本會自己處理輸出位置)
run('quick_recalibration/validation_experiments/L0_repeat_fit/run_L0_repeat_fit.m')
```

預估時間:**45–90 分鐘**(視 GPU,9 點 × 5 trials = 45 fits)。
建議晚上掛機跑。

### 4.3 分析

跑完後切到 PowerShell:

```powershell
cd d:\GMM_2_Final
python PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/analyze_L0_noise_floor.py
```

輸出 `outputs/L0_noise_floor_report.md`,內含:
- `noise_floor_std` per FOV per Zernike coef 的 std/MAD 矩陣
- 跨 FOV 的一致性檢查(std 在 9 點之間是否大致一致)
- 各 Zernike 係數的隨機性排名(哪些係數最不穩)
- 關鍵數字:**單一 noise floor 是否可用**(取決於 FOV 一致性)

---

## 5. 輸出結構

```
outputs/
├── manifest.json                         ← 本次執行的選擇(FOV indices, n_trials, git commit, 跑的時間, MATLAB version)
├── trial_01/
│   ├── batch_results.csv                 ← 9 行,每行一個 FOV 點的 fval/iterations/seconds
│   ├── PSF_fitted_2D_FOVstack.mat        ← coef_grid (15×1×9)、psf_grid (101×101×1×9), subset-order
│   ├── candidate_config.json             ← candidate_prealign 層 metadata
│   └── reasonable_config.json            ← reasonable_v1 層 metadata
├── trial_02/ ... trial_05/               ← 同上,各自獨立
└── L0_noise_floor_report.md              ← 分析腳本產出
```

> **為什麼用 `reasonable_v1` 而不是 `impl`**:
> `HDR_fitting_2D_WholeFOV_impl` 會把 N 張結果 repack 到 10x10 grid layout(其他 100-N 格填 0),
> 會污染跨 trial 的 std 計算。`reasonable_v1` 是真正的 fitter wrapper,
> 輸出 subset-order 的 stack(沒有空格子),才是 L0 要的形狀。

---

## 6. 跑完之後的判讀

`L0_noise_floor_report.md` 會直接告訴你三件事:

1. **同一個 FOV 點 5 次 fit 的 std 夠不夠小**
   - 如果跨 trial 差到跟 L1 sparse fit 結果相當,代表演算法本身就抖到沒辦法分辨機台變化——整套設計要重想
   - 預期應該很小(各 Zernike 係數 std < 0.01 量級)

2. **std 在 9 個 FOV 點之間是否一致**
   - 一致 → 可以用單一 noise floor 簡化後續分析
   - 不一致(中心 vs 角落差幾倍)→ 要 per-FOV 校準 z-score

3. **哪些 Zernike 係數的隨機性最大**
   - 預期 Z4 (defocus) 跟 Z5/Z6 (astig) 應該相對穩
   - 如果高階模態(Z11–Z15)隨機性超大,DESIGN §7.5.1「可解釋模態清單」要重新評估

---

## 7. 已知限制

- **L0 量的只是「演算法 noise floor 的下界」**,不含拍攝噪聲(那是 L1 的任務)
- **只跑 9 點**,空間覆蓋有限——如果未來 L1 結果顯示 noise floor 在 FOV 上劇烈變化,需要回頭加跑更多點
- **rng seed 1–5 是任意選的**,沒有特別意義,但確保每次重跑結果可重現
