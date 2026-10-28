# IMPACT2026 R152 方法素材：結果尚未成立

狀態：方法與協議素材已完成；20×結果另見 `RESULTS_20X_TEXT.md`。未完成 R152 跨倍率結果海報。
圖檔為 `method_protocol_pending.png`（印刷用點陣圖）與 `method_protocol_pending.svg`（可編輯向量圖）。

## English methods text

The follow-up evaluation uses the delivered R152 reconstruction model without additional training. The original four acquisition conditions comprise 20x and 50x objectives with nominal 0.5 and 1.0 micrometer steps. The original 30 adjacent-frame pairs per condition are retained, giving 120 pairs from 166 distinct frames. All methods retain the same nine pillar identities and native image coordinates.

The original measurement backend obtains a coarse closed contour, refines the boundary at correct-polarity gradient maxima along contour normals, and estimates geometric least-squares circle centers. The absolute median horizontal shift of the nine pillars defines each array step. Pixel coordinates are converted to object space after center estimation, using 0.1725 and 0.0690 micrometers per pixel for 20x and 50x, respectively.

Step SD is the mean of the four condition-level sample standard deviations. Nominal MAE is the mean of the four condition-level mean absolute errors relative to the commanded step. Median within-grid SD is the median of the 120 pair-level sample standard deviations of the nine signed horizontal pillar shifts. These quantities describe complementary aspects of in-system displacement performance; nominal agreement is not independent absolute accuracy.

## R152 model description

R152 retains the frozen R148v2 image reconstruction path and adds a bounded, weighted Fourier PSF correction to its output. The delivered correction multiplier remains fixed at one. The optical weighting is estimated once per image across 25 calibrated kernels. This does not establish pixelwise spatial adaptation or correct identification of the physical PSF.

## 圖說

Proposed R152 follow-up under the original locked IMPACT measurement protocol. The original pair list, images, measurement code, and Wiener calibration data have been recovered. Cross-magnification R152 evaluation is pending a compatible, source-verified 50x optical bank and its established installation procedure.

## 目前不能填入的結果與主張

- 不把投稿表格的 MOSR 數值改名為 R152；投稿表格使用的是歷史 V42。
- 不把 R152 的 930 張、30 趟、平台回授比較混入本次四組、120 配對、名義步距比較。
- 未完成跨倍率比較前，不填 R152 四條件的總數值、改善百分比、配對區間或勝出結論。20×部分結果可另行呈現且須標明範圍。
- 原投稿的抗混疊對照實驗不能直接當作 R152 的元件效果證據。
- 不能宣稱 R152 已使用倍率對應的光學資料完成 20x/50x 比較。

## 中文說明

我們已固定沿用投稿時的影像配對和量測方法，20×採R152原生光學資料完成60配對。現在欠缺的是 R152 可直接使用、來源清楚的 50× 光學資料。原 Wiener 的 50× 校正仍在，但無法直接填入 R152 所需的整組資料。因此提供方法圖文與20×結果，不製作帶有四條件新結果數字的完整海報。
