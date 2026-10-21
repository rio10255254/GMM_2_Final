# R26 Validation Analysis Brief

## 快速入口

這份封包目前已有兩層外部驗證成果：

1. **單張外部影像完整分析**
   - 報告：
     `輸出結果\驗證分析\R26_external_single_bundle\R26_完整驗證分析報告.md`
   - 適合用途：
     單一代表案例的深入敘述、圖說、方法章節

2. **多張外部影像進階分析**
   - 報告：
     `輸出結果\驗證分析\R26_external_batch_bundle\R26_批次外部驗證分析報告.md`
   - 適合用途：
     成果報告中的整體觀察、彙總表格、保守結論

---

## 快速資訊表

| 項目 | 內容 |
|---|---|
| 模型 | GeoEdgeAlignSR_v1_v5_NoCoord |
| 權重 | `內部檔案\weights\r26_sm035_best_tradeoff.pth.tar` |
| 外部來源 | `C:\Users\Rio\Downloads\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output` |
| 單張驗證影像 | `VisionTop_20251029182653732.bmp` |
| 多張分析張數 | `10` 張 |
| 單張分析資料夾 | `輸出結果\驗證分析\R26_external_single_bundle` |
| 多張分析資料夾 | `輸出結果\驗證分析\R26_external_batch_bundle` |

---

## 可直接寫進報告的整體結論

- R26 權重在外部影像上可穩定完成推論，且主結構幾何位置維持穩定。
- 單張深入分析與 10 張批次分析的觀察方向一致：模型傾向抑制背景高頻與雜訊，同時提升環狀主結構的可見性。
- 在 10 張代表性外部 BMP 上，環峰值對比增益平均約為 `21.95` 灰階，環中心偏移量平均約為 `2.324` 像素。
- 因外部資料不含 paired ground truth，本成果應表述為「外部驗證下的輸入/輸出相對比較證據」，而非對真值品質的直接定量證明。
- 單張驗證已額外完成輸入完整性比對，`input_image.bmp` 與原始外部 BMP 的 SHA256 完全一致，表示輸入影像本身未被預先改動對比度。

---

## 建議引用方式

- 若你要寫**方法細節 / 專業分析**，優先引用單張完整報告。
- 若你要寫**成果總結 / 批次觀察 / 表格**，優先引用多張批次報告。
- 若你要寫**保守結論**，請同時強調：
  - 外部驗證無 GT
  - 批次分析為代表性子集，不是完整資料集 benchmark
  - 結論屬於模型行為與可用性證據
- 若要回應「輸入影像對比看起來不像原圖」的疑問，可引用：
  - `輸出結果\驗證分析\R26_external_single_bundle\input_integrity_check.json`
  - `輸出結果\驗證分析\R26_external_single_bundle\input_integrity_display_check.png`
