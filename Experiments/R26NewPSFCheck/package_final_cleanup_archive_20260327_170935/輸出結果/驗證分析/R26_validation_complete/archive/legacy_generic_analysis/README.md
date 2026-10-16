# 封存說明 / Archive Notice

**封存日期：** 2026-03-27
**封存原因：** 通用影像品質指標與本專案真正目標脫節，降格至封存層

---

## 這批檔案是什麼

這個目錄收納的是 2026-03-27 重構之前的通用影像品質分析產出物，包含：

- `R26_單張影像驗證分析報告.md` — 舊版分析報告（通用品質視角）
- `scripts/generate_advanced_analysis.py` — 舊版分析腳本
- `data/advanced_metrics.json` — 舊版分析指標（SSIM/SNR/GLCM/wavelet 等）
- `figures/` — 舊版主文 8 張圖表
- `figures/appendix/` — 舊版附錄 7 張圖表

---

## 為何封存

本專案的核心目標是 **whole-annulus 幾何可定位性**，讓 external GMF 在多個位移尺度下穩定定位。

這批分析使用了以下通用影像品質指標，但這些指標對 GMF 可定位性沒有有效的預測力：

| 指標 | 封存原因 |
|------|---------|
| SSIM / PSNR | 視覺感知相似性，不預測 centroid 穩定性 |
| SNR | 背景噪訊統計，不反映 centroid bias |
| Entropy | 資訊理論密度，與 GMF localizability 無關 |
| GLCM 紋理特徵 | 紋理統計，與幾何定位無關 |
| Wavelet detail ratios | 間接的頻率描述，連結 GMF 的路徑非常迂迴 |
| Weber/Michelson local contrast | 感知對比度，不是 GMF feature |
| MTF | 為光學系統設計，本專案 GMF 不依賴此特性 |

> 核心設計原則（`PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`）：
> 「工程上真正優化的不是看起來更銳利，而是 whole-annulus geometry 是否更對 external GMF 友善。」

---

## 新報告位置

重構後的 GMF 視角分析請見：

```
../../../R26_GMF品質分析報告.md
```

（相對此目錄：`R26_validation_complete/R26_GMF品質分析報告.md`）

新分析腳本：`R26_validation_complete/scripts/generate_gmf_analysis.py`

---

## 這批資料是否完全作廢

不完全是。`basic_metrics.json`（保留在 `R26_validation_complete/data/` 未封存）仍有效用，因為它包含幾何指標（ring center, peak_radius, FWHM, gradient）這些對 GMF 有部分意義。

本目錄的 `advanced_metrics.json` 中**有效的部分**只有：
- `esf_lsf.input/output_lsf_fwhm`（邊界響應寬度）

其餘 key（ssim, snr, wavelet, glcm, local_contrast, mtf）不再作為主文 verdict 依據。
