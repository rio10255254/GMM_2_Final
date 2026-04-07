# 視覺證據 / Visual Evidence

這個資料夾只收**極少量、經過策展的 side-by-side comparison sheets**。  
This directory holds **a very small number of curated side-by-side comparison sheets**.

目的很單純：讓重要的視覺 verdict 差異能直接在 GitHub 上被 review，  
而不是把大量原始 BMP 集合塞進 repo。  
The goal is to make important visual verdict differences reviewable in GitHub  
without checking in large raw BMP collections.

## 比較的是什麼 / What Is Being Compared

每張圖板都會使用：
- 同一個檔名
- 同一個 `0.8px` 主戰場案例
- 同一組四條線

Each sheet compares:
- the same filename
- the same `0.8px` battlefield case
- the same four lines

固定四欄如下：
- `R26`
- `Round30 baseline`
- `Round31 regression`
- `Round32 fail`

這樣才能保證比較是公平的：  
This keeps the comparison fair:

- 同一案例 / same case
- 同一視角 / same view
- 同一 battlefield / same battlefield
- 同一組四條線 / same four lines

## 為什麼用 PNG 圖板，不直接收 BMP / Why PNG Sheets Instead of Raw BMPs

原始 BMP 更大，也更不適合直接在 GitHub 上閱讀。  
The original BMPs are much larger and much harder to review in GitHub.

這些 comparison sheets 刻意做成：
- 體積更小 / smaller
- 有標籤 / labeled
- 更適合在 PR 與 Markdown 中快速掃讀 / easier to scan in pull requests and markdown
- 更適合 side-by-side 視覺比較 / better for side-by-side visual comparison

## 目前檔案 / Files

- `comparison_0p8px_case_01.png`
  - 比較 `VisionTop_20251029185330879.bmp`
  - compares `VisionTop_20251029185330879.bmp`
- `comparison_0p8px_case_02.png`
  - 比較 `VisionTop_20251029185655191.bmp`
  - compares `VisionTop_20251029185655191.bmp`

## 收錄規則 / Curation Rule

不要把原始 reconstruction 全集直接放進這裡。  
Do not add raw reconstruction sets here.

只有符合以下條件的視覺證據才應該加入：
- compact
- directly comparable
- clearly labeled
- tied to an important baseline / regression / fail verdict

Only add visual evidence here when it is:
- compact
- directly comparable
- clearly labeled
- tied to an important baseline / regression / fail verdict
