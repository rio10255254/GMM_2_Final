# 共用原拍、量測與固定來源

[專案首頁](../README.md) · [按用途取得檔案](../docs/reproducibility/ASSET_GUIDE.md) · [目前保存狀態](../docs/reproducibility/STATUS.md)

共用內容保存一次，各輪引用同一來源。這裡先按「資料是怎麼來的」區分，再連到原說明與取得方法。

## 相機原拍與儀器紀錄

| 來源 | 內容及用途 | 取得入口 |
|---|---|---|
| 2026-09-03位移重拍 | 30趟，每趟起點加30步，共930張相機照片及30份平台位置紀錄 | [原拍與順序](PI_Repeatability_20260903/README.md)、[位置原表](PI_Repeatability_20260903/position_records/README.md) |
| PSF100原拍及完整挑圖來源 | 2025-09-03原395張，其中100視野用於原擬合；與2026年位移重拍不同 | [逐張來源與原擬合對照](PSF_Camera_Acquisitions/PSF100_20250903/README.md) |
| 0615三輪PSF取像 | 三輪各242張，共726張原拍；同位置兩張及原擬合使用方式有記錄 | [三輪原拍、處理輸入與恢復方法](PSF_Camera_Acquisitions/README.md) |
| Lab 25位置校正 | 原25張，實拍日2026-06-05；舊路徑名稱20250605保留為歷史身分 | [原校正補件及按用途取得](../docs/reproducibility/priority_sources_20261022/README.md) |
| Step、多倍率及其他實拍 | 既有來源與保存理由各有身分，避免和模型輸出混用 | [原來源與影像用途](../docs/reproducibility/SOURCE_AND_IMAGE_DECISIONS.md) |

## 量測、人工參照與固定比較輸入

| 來源 | 為什麼保存 | 入口 |
|---|---|---|
| SEM原工作表與參照 | 尺寸／輪廓的原參照；同樣本及答案依賴須隨結果閱讀 | [SEM原件](SEM_Originals/README.md) |
| 30份Raw邊界點 | 原量測座標，供R129／R130等比較；不是整張重建影像 | [原邊界與固定小圖](../docs/reproducibility/priority_sources_20261022/README.md) |
| 歷史幾何與固定裁切 | 不可用今天重新裁切的結果冒充當年輸入 | [歷史固定輸入](Legacy_Frozen_QA_Inputs/README.md) |
| 跨輪固定參照與診斷 | R32、R113／R116、R131／R132及SEM方向候選；部分來自模型輸出而非相機 | [逐項用途與取得](../docs/reproducibility/round_source_followthrough_20261022/README.md) |

## 早期固定環形來源

[R33／COMBO／R39／R40共用輸入](Baseline_Ring_Inputs/README.md)把1,000組生成來源未明的原件與100組既有PSF處理輸入分開保存及恢復；不把整套可生成訓練庫一起上傳。

## 可生成的大資料

訓練影像與整批重建先找[原生成程式、設定與必要來源](../docs/reproducibility/GENERATION_GUIDE.md)。R108兩套資料已有從取回程式生成相同檔案的紀錄；R61的3,400組繼承來源與歷史幾何仍需原件，不能只留亂數種子。

照片、處理輸入、合成資料、模型輸出與量測座標不能互稱。各輪是否用過相關答案、是否獨立驗證，仍以原正式報告為準。
