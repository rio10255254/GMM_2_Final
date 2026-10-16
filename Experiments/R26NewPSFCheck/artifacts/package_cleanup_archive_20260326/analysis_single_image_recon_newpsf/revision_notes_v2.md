# revision_notes_v2

## 本輪改了哪些圖
- 新增 `01_overall_compare_raw_vs_r26_v2.png`：在全圖上補上 A/B/C/D ROI 框與標號，讓圖 1 和圖 2 能一一對應。
- 新增 `02_roi_compare_raw_vs_r26_v2.png`：改成固定 A–D 四列、RAW/R26 兩欄的報告版布局，提升閱讀順序與對照性。
- 新增 `03_edge_profiles_raw_vs_r26_v2.png`：保留主/弱邊界雙圖架構，但將標題與註解改為正式報告口徑，明寫 10–90 transition width。
- 新增 `04_frequency_validation_raw_vs_r26_v2.png`：保留 2D FFT 與 radial spectrum 主體，但改寫整張圖的定位與註解方向，移除任何暗示「高頻整體提升」的表述。

## 本輪改了哪些文字
- 新增 `single_image_metrics_report_v2.md`：在表格後加入『結果解讀重點』，固定以邊界集中化、背景抑噪、頻域輔助驗證、幾何 proxy 保守支持的順序解讀。
- 新增 `single_image_recon_result_draft_zh_v2.md`：重寫為可直接貼入報告的中文草稿，補上頻域與幾何 proxy 的保守解讀段落與圖說建議。
- 新增 `revision_notes_v2.md`：明列本輪降權與保留的證據，避免圖、表、正文之間口徑漂移。

## 指標定義與 ROI 是否更動
- 本輪未更改任何 metric definition，未重選 ROI，未重新設計 band 或 threshold。
- HF_ratio 仍使用固定頻帶 `r=0.35–0.60`；checkerboard_ratio 仍使用 `|fx|, |fy| >= 0.80` 的 corner energy 定義。
- edge_continuity_ratio 仍使用 RAW 量測出的梯度 quantile threshold 作為 valid rule，實際門檻為 inner `2.7414`、outer `2.7422`。
- 可在不改資料與不重挑 ROI 的前提下完成本輪修正；本輪只調整圖面、命名與解讀權重。

## 哪些解讀被刻意弱化，為什麼
- 弱化『高頻提升』『有效高頻增加』這類說法，因為目前 `HF_ratio` 由 `0.6185` 降至 `0.0164`，不支持把頻域寫成高頻全面增強。
- 弱化 `edge_continuity_ratio` 的 headline 地位，因為它依賴 threshold、valid angle 規則與 edge rule，語意上比 `ring_thickness_std_px` 更容易被挑毛病。
- 弱化『背景未明顯惡化』這種保守但不準確的說法，改寫為背景波動與背景高梯度雜訊明顯下降，因為 `background_std` 與 `background_grad_p95` 的數值改善非常明確。

## 哪些解讀被保留為主證據，為什麼
- 保留 `edge_width_main_px`、`edge_width_weak_px`、`max_slope_main`、`max_slope_weak` 為最核心主證據，因為它們最直接對應『邊界變窄、變陡、變集中』這個研究主問題。
- 保留 `CNR_main`、`CNR_weak`，但要求與 `background_std`、`background_grad_p95` 綁定解讀，因為對比改善明顯來自邊界集中化與背景抑噪的共同作用。
- 保留 `ring_thickness_std_px` 作為較穩健的主幾何 proxy，因為它直接反映有效角度上環厚度的一致性，較不容易被單一門檻規則主導。

## HF_ratio 在本報告中最終應被如何定位
- `HF_ratio` 應被定位為固定高頻帶能量比或高頻/噪聲帶能量佔比的輔助指標，不應直接等同於有效細節量。
- 在本報告中，`HF_ratio` 的用途是幫助說明頻帶重分配、背景高頻與噪聲成分受抑，以及避免把結果誤寫成『全面高頻增強』。

## edge_continuity_ratio 在本報告中最終應被如何定位
- `edge_continuity_ratio` 應被定位為幾何層的輔助支持指標，而非 headline 指標。
- 正文若要提及，應同步註明其對 threshold / edge rule / annulus valid rule 較敏感，避免把它寫成已直接證明幾何量測能力提升。

## 最終建議正文應主打哪些指標，避免主打哪些指標
- 建議主打：`edge_width_main_px`、`edge_width_weak_px`、`max_slope_main`、`max_slope_weak`、`background_std`、`background_grad_p95`、`CNR_main`、`CNR_weak`、`ring_thickness_std_px`。
- 建議降權：`HF_ratio`、`checkerboard_ratio`、`edge_continuity_ratio`；其中前兩者屬於排除副作用與支持改善可信的輔助證據，後者則是較敏感的幾何輔助支持。
- 建議避免主打：『高頻提升』『細節全面增強』『已直接證明量測精度提升』。這些說法在目前資料下都過滿。

## 是否重算數值
- 本輪未發現需要修正的實作 bug，因此未重算官方表格數值，也未修改 CSV。
- v2 圖面僅以相同輸入、相同 ROI、相同指標定義重繪，v2 文字則直接對齊既有 CSV 與 log 的數值與語意。