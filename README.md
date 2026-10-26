# MOSR：用 AI 還原顯微影像，讓位移與尺寸量得更穩

**一句話：** 顯微鏡拍出來的邊緣會糊，糊會讓「圓在哪裡」的量測抖動。本研究訓練神經網路把影像還原，目的不是讓圖好看，而是讓**奈米等級的位移、尺寸、輪廓量測更穩定**。

## 結論（論文採用版）

論文用的模型叫 **MOSR**（就是 R152），拿 930 張實拍（30 趟 × 31 位置，每步約 1 µm）和不處理的原圖 **RAW** 比：

| 指標（nm，越小越穩） | RAW | MOSR（R152） |
|---|---:|---:|
| 單趟 30 步合併波動（主要指標） | 8.781 | 4.273（−51.3%，30 趟全部變好） |
| 相鄰步相對 PI 平均絕對差 | 6.969 | 3.598（−48.4%） |
| 直徑重拍波動 | 32.750 | 13.252 |
| 輪廓重拍波動 | 63.758 | 18.600 |
| 與 SEM 直徑的平均差 | 169.883 | **204.281（變差）** |

位移是九顆柱體位移向量的**算術平均**，這是回應口試委員建議後的論文口徑（[平均與中位數比較](Experiments/R153_MeanExternalBenchmark/reports/MEAN_MEDIAN_RESULTS.md)）。R152 原紀錄用的是中位數（RAW 10.200 → 4.865，−52.3%），論文不再沿用，兩種口徑不可混用；直徑、輪廓與 SEM 的數字兩者相同。

三個要記住的限制：**更穩不等於更準**（對 SEM 的尺寸差反而變大）；論文裡的多 PSF 融合模組實際作用極小，效果主要來自底座 R148v2；SEM 與樣品曾用於光學校準，不是完全獨立的驗證。
另有十種方法的完整比較（EDSR、NAFNet、SwinIR…）。數字與限制見 [PROJECT_STATE.md](PROJECT_STATE.md)。

## 兩條線、兩個「目前模型」，不要搞混

這個專案同時服務兩個用途，所以有兩個「目前」的答案：

| 用途 | 目前模型 | 怎麼評分 |
|---|---|---|
| **公司端量測部署** | **COMBO**（正式基準，2026-04-08 起；歷史前任 baseline 是 R30） | 環形影像交給固定的外部定位工具（GmmVisionTool 的 GMF），看 1／0.1／0.01 µm 三個位移尺度的穩定度。COMBO 交付為 ONNX 包（`_deployment_package/`）；之後的 ONNX 交付（`Deliverables/MOSR_ONNX/`、`MOSR_R61_ONNX/`）以均華 202 張等實拍驗證（`Validations/MOSR_ONNX_JunHua/`） |
| **論文** | **R152 / MOSR**，對照 RAW | 2026-09-03 拍攝的 930 張 PI 位移重拍，看位移、尺寸、輪廓 |

兩者考的是不同的試，並不衝突。R152 沒有取代 COMBO 的正式身分。機器可讀的版本在 [ESTIMATOR_POLICY.json](ESTIMATOR_POLICY.json)。

## 你想做什麼，就讀哪裡

| 想… | 讀 |
|---|---|
| 理解整個系統怎麼設計、怎麼判斷好壞 | [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) |
| 知道**現在**的結果、限制、缺件 | [PROJECT_STATE.md](PROJECT_STATE.md) |
| 看研究怎麼一路走到這裡、某一輪做了什麼 | [docs/reproducibility/EXPERIMENTS.md](docs/reproducibility/EXPERIMENTS.md) |
| 看不懂縮寫（PSF、GMF、PI、RAW…） | [docs/README.md](docs/README.md) 的名詞表 |
| 找資料夾、原始照片、模型在哪 | [docs/navigation/PROJECT_MAP.md](docs/navigation/PROJECT_MAP.md) |
| 改論文 | [R153 論文交接](Experiments/R153_MeanExternalBenchmark/reports/FINAL_BENCHMARK_THESIS_HANDOFF/REPORT.md) |
| 開新實驗或維護 repo | [docs/operations/README.md](docs/operations/README.md) |

## 研究怎麼進行（概念圖）

```text
光學校正 → PSF ─┬─► 把乾淨合成場景弄糊 → 訓練配對 → 訓練模型
                └─► 放進模型的物理模組
真實照片 → 模型重建 → 獨立量測程式找圓心／輪廓 → 對照平台回授（PI）與電子顯微鏡（SEM）
```

## 資料夾角色（常用的）

| 資料夾 | 內容 |
|---|---|
| `Experiments/` | 主專案各輪（R26–R153）：程式、設定、報告、結果 |
| `Model/` | 第一代共用模型與訓練、推論、自動調參 |
| `PSF_Fitting/` | 光學校正（MATLAB） |
| `Shared_Sources/` | 不可替代的原始照片與量測入口 |
| `Thesis_MOSR_Evidence/` | 論文證據與 LabSystem（實驗室顯微鏡）整條研究線 |
| `Deliverables/` | 可獨立使用的交付包（R152 獨立版等） |
| `Tools/`、`docs/` | 工具與文件 |

其餘日期型分析與封存區見 [專案地圖](docs/navigation/PROJECT_MAP.md)。

## 保存狀態

大型原拍、模型與資料以 GitHub 發布附件保存，按需下載，不必整套取回。**逐輪必要來源的查核仍在進行**；已知缺一個 R63 原模型、主專案 R36 無法辨認。詳見 [PROJECT_STATE.md](PROJECT_STATE.md) 與 [docs/reproducibility/README.md](docs/reproducibility/README.md)。

> 2026-10-24 改寫前的舊首頁原文在 [docs/history/BEFORE_PLAIN_REWRITE_20261024/](docs/history/BEFORE_PLAIN_REWRITE_20261024/README.md)。 較早的程序狀態在 `docs/archive/legacy_runtime_status/`。
