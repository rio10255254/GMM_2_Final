# R114 Confidence-Gated Recoverable MOSR：完整總計畫

狀態：**只完成規劃，尚未建立正式模型、尚未開始任何新訓練。**

## 一、目標與不變條件

R114 的目標不是單純得到更銳利的影像，而是在單張輸入下，同時改善：

- 真實邊界位置與完整輪廓；
- 非圓形細節、細環、月牙、窄間隙與粗糙邊界；
- 5×、20×、50×真實顯微影像的紋理泛化；
- LSC／輪廓定位與位移穩定；
- 大圖切塊後的一致性；
- 清楚影像、空白區域與不可恢復區域的安全性。

不變條件：

- 單張推論，不要求特殊拍攝序列；
- 模型與每個對照實驗全部從零開始，不繼承R109、R61或V42權重；
- 不使用真實SEM、HS100MG或JunHua影像作為訓練答案；
- 只使用局部、可切塊的運算，不加入全圖統計、全圖FFT或空間GroupNorm；
- ACM、LSC、真實影像、位移與最差案例優先；CD僅為次要資料；
- 外部GMF只能在物理驗證完成後作相容性測試，不可反向決定核心模型。

## 二、證據對應修正

| 已確認問題 | 關鍵證據 | R114修正 | 驗證方式 |
|---|---|---|---|
| Boundary/controller死亡 | Boundary固定0.508、AUC 0.496、對輸入梯度為零；同樣LocalCues的線性分類器AUC 0.870 | 以SDF、法向量、boundary confidence、need與recoverability聯合控制器取代目前boundary head；移除末端tanh飽和 | 控制器microprobe逐family、逐退化檢查；不可只看總平均 |
| Necessity從未訓練 | target有計算，但所有necessity loss固定為零；推論necessity固定1 | 真正建立need target與loss，控制器可開啟也可拒絕修正 | clear、flat、degraded三組輸出需明顯分離且保持跨場景一致 |
| Dense array支配loss | 只佔7.6%記錄，卻佔67.7% edge weight、75.3% perimeter；其boundary probe AUC僅0.42 | 每張影像先正規化edge loss再跨影像平均；dense array獨立配額，不靠邊界像素數取得更大權重 | 保存每family實際梯度占比，確認不再由單一family支配 |
| Clear資料過多 | 展開後54.7%為clear/identity；clear在shift上的總梯度為degraded的5.92倍且方向相反 | 取消每筆資料固定附一張clear；改為獨立identity bucket，每批只配置少量clear樣本 | 每輪記錄clear/degraded的梯度方向與大小 |
| Width target錯誤主導 | 單一Gaussian width target在renderer backbone約佔91%總梯度、width head約99%；未描述halo、motion、ghost與局部fade | 從已知source/target沿真實法向量計算局部transition width與50% crossing shift，產生空間化target | 對每個退化family檢查target有效率與renderer實際誤差 |
| Loss互相打架 | width上的contour vs gradient cosine -0.982；shift上的area vs centroid -0.997 | 不再把所有loss永久加總；改採分階段與交替更新，必要時使用gradient conflict projection | 每個microprobe重跑gradient audit |
| Mixed-hard資訊不足 | 已知真實midpoint/polarity後IoU中位仍只有0.337；真實對齊高頻只剩6.8%；近來源歧義5.8% | 預測recoverability／uncertainty；不可恢復區域降低精確高頻監督，不強迫模型猜唯一答案 | recoverable與unrecoverable區域分開報告，不讓平均掩蓋幻覺 |
| 合成紋理不符真實 | 真實5×距合成域8.81倍，20× 3.75倍，50× 3.63倍；合成噪聲頻譜過白 | 加入有空間相關性的colored noise、多尺度照明、固定列／行雜訊、5×規則密集結構與真實風格但純合成的紋理 | 重新執行domain-gap audit，只比較統計覆蓋，不複製真實影像作label |
| Detail支路學不起來 | Oracle證明有容量，但正式直接監督僅使用目標約5.1% | Geometry先訓練；detail階段凍結或大幅降低geometry LR，detail使用獨立optimizer與recoverability-weighted target | matched scratch detail/no-detail microprobe |
| Patch不是根因 | 90% ERF約42px、99%約56px、最大約90px | 正式訓練仍以256 patch為主；較大patch只用於資料組合或驗證，不宣稱增加模型理解力 | 256／完整／切塊輸出一致性 |

## 三、資料設計

### 3.1 Target資料

現有5,000 train＋512 validation的target/mask/SDF品質良好，不整批重做：

- 原始array只讀重用；
- 新建R114 data manifest與sampler，不複製既有大檔；
- 保留8倍超採樣軟標籤；
- 僅新增少量缺失的target families：close-pair/narrow-gap、micro-notch、rough-Fourier、極薄亮暗環；
- 新增資料時，以替換過多或重複功能的easy/dense樣本為主，使總量維持約5k級別。

### 3.2 Batch組成

不再將一筆record自動展開成degraded＋clear兩張。每個batch由獨立bucket組成：

- 一般幾何：circle、ellipse、polygon、rectangle、lobed、irregular；
- 困難幾何：ring、crescent、thin-bar、thin-neck、narrow-gap、micro-notch；
- textured/multiscale；
- dense-array：每batch至多一筆，且loss仍按每張影像正規化；
- flat negative；
- clear/identity：每batch約一至兩筆，實際比例可依梯度audit微調，不再固定54.7%。

### 3.3 Loss聚合

所有pixel/boundary loss都先在單張影像內正規化，再對batch取平均：

`loss = mean_i(sum(weight_i * error_i) / sum(weight_i))`

因此dense-array即使有大量邊界像素，也不能取得數十倍發言權。

### 3.4 動態成像

保留現有blur、anisotropy、motion、halo、ghost、illumination、fade，再加入：

- 1/f與band-limited colored noise；
- 多尺度低頻背景與固定pattern noise；
- 不同倍率的結構頻譜與5×密集網格；
- 亮暗兩極、局部對比反轉風險與非均勻PSF；
- 由已知forward degradation產生的local recoverability map。

真實影像只能用來決定合成統計範圍與作封閉驗證，不能成為target。

## 四、新模型架構

### 4.1 保留部分

- R109的LocalCues概念；
- 48-channel局部骨幹量級；
- analytic width＋normal-shift renderer；
- bounded output與tile-safe推論；
- 不使用全圖pooling與FFT。

### 4.2 Geometry／Confidence Controller

新的controller不再只輸出一張boundary map，而是聯合輸出：

1. normalized SDF／局部boundary coordinate；
2. normal-x、normal-y；
3. boundary confidence；
4. correction need；
5. recoverability／uncertainty。

Controller骨幹使用channel-only normalization或穩定的normalization-free residual scaling；禁止使用依賴整張patch空間統計的GroupNorm，也移除目前造成約58%飽和的末端tanh。

### 4.3 Gate

原本：`support = max(raw_gradient_support, learned_floor)`。

新設計：

- `geometry_gate = boundary_confidence × correction_need`
- `detail_gate = geometry_gate × recoverability`

原圖gradient只是輸入特徵，不能強迫成support下限。這讓模型能拒絕雜訊、5×正常細紋與假halo，也能在弱但可信的邊界啟動修正。

### 4.4 Width／Shift

- 保持width gain 1.0–3.5與normal shift ±1.5px的安全範圍；
- 使用沿真實／預測法向量得到的空間target；
- 使用沿boundary tangent方向的coherence loss，不做固定二維Gaussian平滑；
- 不同pillar或不同物件不互相平均。

### 4.5 Detail

- 保留最多18 gray-level的bounded、zero-local-mean候選支路；
- detail只在recoverable區域接受target；
- 不可恢復區域只允許保守幾何修正，不要求猜出紋理；
- detail支路與geometry分開optimizer與訓練階段。

### 4.6 Uncertainty輸出

訓練與研究版保存confidence/uncertainty map，最終交付影像仍可保持單輸出。這張map用於：

- 判斷mixed-hard是否超出單張資訊上限；
- 避免把幻覺當成恢復；
- 分開計算recoverable與unrecoverable的驗證結果。

## 五、分階段、完全獨立的實驗

所有probe與formal arm都使用相同資料規則但**各自從零初始化**，不接續前一個probe權重。

### Probe 1：Controller Viability

只訓練SDF／normal／confidence／need／recoverability controller，不接renderer。

目的：證明controller不再是常數、能跨family與退化辨認邊界，而且dense-array不再拖垮其他形狀。

結果判斷採完整分布：

- 與固定LocalCues線性probe比較；
- standard、fade、mixed、dense、thin、ring各自呈現；
- clear／flat／degraded的need分離；
- 同一latent跨退化的一致性；
- 不以單一平均分數或任意硬門檻決定。

若controller仍常數化或只在dense/general其中一邊有效，停止，不進Probe 2。

### Probe 2：Geometry Renderer

完整模型從零開始，但只使用controller＋width／shift，不含detail。

- Controller持續以較低LR更新，不再凍結42 epochs；
- Geometry target step與render/contour step交替進行；
- clear／identity使用獨立step；
- Translation/exposure按幾何單位或gradient尺度正規化；
- tile只做驗證，因local model本身應完全一致。

若R73/R74、中心36 SEM與LSC顯示只交換誤差類型而沒有跨域改善，停止並回到target/gate設計。

### Probe 3：Recoverable Detail

兩個matched scratch arms：

- Geometry-only；
- Geometry＋bounded detail。

兩臂相同seed、參數量級、batch順序與更新步數。Detail階段凍結或減慢geometry，使用獨立LR與recoverability-weighted residual target。

若detail只提升合成高頻、卻傷害SEM輪廓、LSC、identity或tile，正式R114不帶detail。

### Formal R114

只有三個probe的因果結果都明確後才建立正式run。正式run依然從零開始，暫定約40 epochs：

- Controller：前段；
- Geometry：主段；
- Detail：獨立段（僅在Probe 3支持時）；
- Joint refinement：短段。

實際epoch分配依probe收斂位置決定，不預先把E100當成目標，也不因最後epoch較新就自動選它。

## 六、Batch、patch、顯存與速度

- Patch以256為主，因現有ERF已被完整覆蓋；
- Batch先測12與16，選擇可穩定留下至少7GiB顯存且吞吐最高者；
- 若batch composition需要，使用gradient accumulation，不靠無限制擴大patch；
- FP32為正式基準；BF16只有在output、控制圖與梯度方向都通過對照後才使用；
- DataLoader採persistent workers、pinned memory與預先生成的degradation參數；
- 每個run唯一lock、可恢復checkpoint、動態ETA與前景監控；
- 不允許同時存在兩個正式trainer。

## 七、即時驗證與選模

每2 epochs保存checkpoint，每4 epochs執行固定驗證：

1. 9-grid pillar視覺對照；
2. R73 novel shapes固定subset；
3. R74五種hard families固定subset；
4. 5×、20×、50×代表影像；
5. clear、flat與identity安全性；
6. 兩種tile grid一致性；
7. controller、gate、width、shift、detail、uncertainty內部圖；
8. gradient方向與各family實際edge-weight占比。

正式訓練完成後依序執行：

- 全R73/R74 ACM；
- SEM 36 pillars × 12 exposures ACM；
- deterministic LSC current-top30；
- 5×／20×／50×共301張真實序列；
- line pattern sharpness與位移；
- large-image多種tile origin/core/halo；
- 封閉未見樣品與獨立位移真值（若可取得）；
- 最後才做外部GMF相容性。

選模不使用單一加總分。先看是否存在災難性family／曝光／倍率失敗，再看ACM、LSC、identity、tile與真實紋理的整體證據。GMF不能推翻前面的物理判定。

## 八、資料夾與可手動執行性

正式建立時使用單一根目錄：

```text
R114_ConfidenceGatedRecoverableScratch/
  README.md
  config/
    data.json
    model.json
    training.json
    validation.json
  data/
    manifest.json
    references/
    supplemental_targets/
  model/
  training/
  inference/
  validation/
  probes/
    controller/
    geometry/
    detail/
  scripts/
    prepare_data.ps1
    run_probe.ps1
    train.ps1
    infer.ps1
    monitor.ps1
    validate.ps1
  runs/
  weights/selected/
  results/
  reports/
```

`training/train.py`與`inference/infer.py`都能直接開啟修改參數並按執行；PowerShell只是乾淨入口，不把核心設定藏在命令列。

## 九、明確禁止帶入R114的舊做法

- 不接續任何舊權重；
- 不使用V42 Raw anchor迎合GMF；
- 不保留常數0.5 boundary解；
- 不把need固定為1；
- 不讓raw gradient成為無法拒絕的support floor；
- 不每筆自動附clear影像；
- 不按整個batch的邊界像素總量計算loss；
- 不使用整張圖共用的scalar width target；
- 不固定二維平滑所有控制圖；
- 不把不可恢復區域當成可精確還原；
- 不靠加大patch、batch、epoch或backbone掩蓋控制器失效；
- 不在物理驗證前以GMF或視覺銳利度選模。

## 十、目前決策

現在只批准下一步建立 **Controller Viability Probe**。尚未批准正式R114訓練，也尚未批准完整資料生成。Controller probe完成後，根據實際空間分離、跨退化穩定與逐family結果，再決定是否進Geometry Probe。

