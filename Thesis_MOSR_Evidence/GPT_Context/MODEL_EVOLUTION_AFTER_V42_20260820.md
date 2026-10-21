# V42 口試模型之後的 MOSR 模型演進、策略調整與失敗脈絡

更新日期：2026-08-20  
用途：提供另一個 GPT、共同研究者或未參與過專案的人，理解 V42 之後的模型實驗到底在解什麼問題、每次調整為什麼出現、哪些結論已被真實資料支持，以及哪些仍只是研究假說。

時間閱讀注意：本文件以「V42 是口試／論文參考模型」作概念起點，而不是假裝每個資料夾建立日期都晚於 V42。部分 R61 訓練與驗證 artifact 的日期早於 V42 的論文封裝，但它在口試後的比較、SEM／GMF 驗證與交付決策中仍是第一個主要替代候選；以下排序以問題與決策演進為主，並在需要時附實際完成狀態。

---

## 先給下一個 GPT 的核心結論

這不是一條「模型版本一路變強」的直線故事，而是一系列把四個互相干擾的目標拆開、再嘗試重新整合的研究：

1. 真實輪廓是否更接近 SEM，而不是只看圓半徑或 CD。
2. 重建後是否讓固定的外部 GMF 定位軟體更穩定。
3. 大圖切塊後是否與整張重建一致，不能靠拼接羽化掩蓋差異。
4. 真實顯微影像是否能更清晰，但不產生假邊、暗邊、光暈、假孔洞或位移偏差。

最重要的歷程性結論是：

- R61 證明「量測導向的重建」可以真實提高外部 GMF 的定位穩定度，但它在極暗曝光、細微不規則輪廓與困難顯微情境並不全面成功。
- R75 到 R79 證明只靠更乾淨、更廣的程式形狀資料，能顯著提升密集結構與 SEM 輪廓，但仍無法自然得到任意場景的泛化；R79 還暴露出舊架構對切圖範圍敏感的根本問題。
- R84 到 R87 證明「切塊一致」不是後處理問題，而是架構問題：只要模型含有依賴整張影像統計的運算，切法一變，結果就會變。後來的模型因此改成局部、相位對齊、固定 halo 的原生切塊架構。
- R89 證明過度銳化可以讓合成資料與視覺看起來更好，卻會在真實 SEM 輪廓上更差；因此「更清楚」不能被等同於「更準」。
- R90 到 R104 把問題從一般影像重建，改寫成一個受物理、幾何、位移、曝光、噪聲、紋理證據與切塊一致性共同約束的因果分解問題。
- R101 的短驗證非常關鍵：它證明後期模型保守、平滑，不是因為訓練不夠久，而是因為舊資料與舊損失本身多數時候在教模型「把高頻刪掉」；要恢復真實細節，必須改真值形成方式、可恢復性定義、輸出方式與多目標更新關係。
- 到目前為止，沒有單一模型同時在外部 GMF、SEM 真實輪廓、困難顯微、低倍密集結構、真實細節、絕對座標與切塊一致性全部勝出。

因此，不能把目前所有模型壓成一個「最終唯一模型」。較正確的角色分工是：

| 角色 | 目前最有證據的模型或版本 | 為什麼 |
|---|---|---|
| 專案正式 baseline | COMBO | 正式 policy 仍指定它，因外部 GMF 三尺度與視覺的平衡最完整。 |
| 口試／論文結果模型 | V42 E120 | 目前論文正式圖表與中心九顆 CD、位移結果使用它。 |
| 外部 GMF 實用候選 | R61 v16，含 R61 ONNX v1.1 | 在真實 Pitch1um 序列與固定 GmmVisionTool 上有最強、最直接的定位穩定度證據。 |
| SEM 中央 36 柱的強輪廓候選 | R79 E23，但只適合整張處理 | 在該固定 SEM 對照上很強，但原始架構切圖不一致，困難顯微也不是全面勝出。 |
| 原生切塊、真實細節與位移的研究候選 | R103 E48 | 大圖切塊、真實位移與較自然細節都很有潛力，但 SEM／曝光泛化仍弱於 R61。 |
| 最新光照不變性假說的結果 | R104 E48 | 新形狀合成測試與切塊、位移表現不錯，但真實 SEM 與困難顯微大多退回接近 Raw，尚非交付候選。 |

---

## 0. 起點：V42 口試模型真正解決了什麼，又留下什麼問題

### V42 在口試中的定位

V42 E120 是當時論文正式採用的模型。它在中心九顆 100MG pillar 的 CD 與固定位移序列上提供了論文所需的結果：

- 中心九顆的平均絕對 CD 誤差由 Raw 的 92.99 nm 降到 V42 的 78.18 nm。
- 在預先按 Raw 拍攝狀況鎖定的幾段 20x、50x 位移序列中，V42 的位移波動通常低於 Raw。
- 但它不是獨立絕對位置真值驗證，也不能宣稱平台本身變穩。

### 口試後真正改變的問題定義

教授指出樣品不是完美圓形，因此不能只用半徑或 CD 判斷重建是否正確。這使研究重心由「圓柱直徑有沒有較接近」改成：

1. 整個不規則外框是否接近 SEM。
2. 輪廓位置、面積、周長、圓整程度、局部粗糙度是否同時合理。
3. 重建影像放進企業既定的 GmmVisionTool 之後，定位是否更穩定。

這是後續所有策略改動的第一個根源。CD 沒有被廢除，而是降回「尺寸」的指標；ACM 完整輪廓與 SEM 對照成為「形狀」的補充真值。

### V42 後來的完整輪廓驗證

R70 把 V42 放到與 R61 相同的 36 顆實體 pillar、12 段曝光、SEM 對照與 translation-only ACM 框架下：

- V42 相對 Raw 的主要外框有改善：平均邊界距離由 0.570% pillar pitch 降到 0.523%，36/36 pillar 改善。
- 但 V42 在曝光 20 之後開始失去改善，最暗的曝光 23、24 沒有通過。
- V42 的細部形狀指標並沒有通過；周長與圓整程度仍不夠好。
- R61 在同一個一般曝光 SEM 框架下更強，但 R61 也會在最暗曝光失效。

這個結果讓後續研究不再追求「把 V42 調得更好」，而是轉向：能否在不偷用真實 SEM 形狀的前提下，建立一個更能跨形狀、跨曝光、跨位移且能被外部量測工具接受的模型。

---

## 1. R61：先建立一個真正面向量測與位移的候選

### R61 的核心想法

R61 不是乾淨從零訓練的 scratch 模型，而是既有 MOSR 架構的一系列多輪演化。它的目的不是只讓圖看起來銳利，而是同時把「真實幾何、相鄰影格位移、已知合成位移、紋理與步進序列」放入訓練。

R61 最終採用的 v16 Step-guard 方向，大致加入了七類資料：

- 舊有一般形狀資料：保留既有基本成像能力。
- sequence guard：以保守方式拉回 SEM 方向，避免每張影像被過度修正而使時間序列抖動。
- SEM truth anchor：用已對應的 SEM 型態作幾何錨點，但禁止把同一測試樣品做事後校正。
- universal synthetic：增加圓、橢圓、矩形、環、細條、polygon、混合形狀等泛化。
- motion synthetic：成對影格具已知 dx、dy。
- motion texture synthetic：同一幾何在帶紋理的成像條件下移動。
- step-guard motion texture：把連續步進與紋理一起學，防止模型為了單張漂亮而破壞步距。

其資料設計有兩個重要原則：

1. 不讓真實 HS100MG 或 SEM 測試結構回流成訓練答案。
2. 同一個潛在形狀／序列不能同時分到 train 與 validation，避免模型只是看過同一外框。

### R61 的成功

R61 最強的不是「所有影像都最漂亮」，而是固定外部 GMF 的實測效果。

在 Pitch1um_Y_100 真實序列的歷史外部 GMF 測試中：

- Raw 的 Y step 標準差為 4.335 px。
- R61 v16 PSF-off 的 Y step 標準差為 0.342 px。
- GMF 平均分數由 73.619 提升到 89.659。
- 同一 stage position 的重複定位散布由 8.335 px 降到 0.526 px。

後來為了企業交付而做的 R61 ONNX v1.1，又把大圖分塊方式升級成相位固定、反射 halo、只保留核心區的推論。新版使用真實 5120×5120 序列，仍用同一套 GmmVisionTool 直接驗證：

- Raw 的 Y step 標準差：8.194 px。
- R61 v1.1 分塊輸出的 Y step 標準差：0.413 px。
- GMF 平均分數：77.798 -> 89.501。
- 100 個有效 R61 點全部高於對應 Raw 分數。
- 方向正確比例：86% -> 100%。

這是到目前為止最直接的「模型输出确实更适合企业既定 GMF」證據。

### R61 的限制

R61 同時暴露了後續研究最重要的弱點：

1. SEM 一般曝光下的主要外框較準，但極暗曝光 23、24 反而惡化。
2. 主要外框 IoU、平均邊界距離改善，但周長與圓整程度較差，表示細微不規則邊緣可能被平滑或重畫。
3. R71、R72、R73、R74 的合成壓力測試顯示，R61 對低對比、局部邊界消失、混合困難、淡邊與複雜紋理並非全面成功。
4. R61 的舊架構含 GroupNorm 與 FFT 光學處理，原生上依賴可見影像範圍；即使後來 ONNX runner 已改善拼接，它也無法像後續局部架構那樣達到數學上的全圖／切圖逐位元一致。

### R61 留下的概念遺產

R61 把後續研究的成功標準拉高：新模型不能只在合成資料變好，也不能只在 SEM 變好；至少必須同時面對真實位移、外部 GMF、真實輪廓、曝光與泛化。

---

## 2. R63 到 R74：先修正「怎麼判斷模型好不好」

這一段多數不是新模型，而是驗證觀念與量測方法的重建。它非常重要，因為後續所有新模型都在這些檢驗框架下被淘汰或保留。

### R63：把 V42/MOSR 的方法元件拆開

R63 對 V42 類 MOSR 做了匹配的機制拆解：幾何錨定、相對位移一致性、shift-safe upsampling、Raw position anchor、boundary residual adapter、quality gate 等。

它的價值不是產生新交付模型，而是確認：

- Raw-position anchor 是守住邊界安全的重要機制。
- shift-safe upsampling 有助降低跨 pillar 的位移不一致。
- 靜態幾何與相對位移的一起存在，支持完整 MOSR pipeline。
- 但在兩個 seed 的 matched fine-tuning 下，很多單一 loss 的因果效應沒有強到可以單獨寫成絕對真理。

這使後續設計不再迷信「只加一個 loss 就會根治」，而改成從資料、輸出、架構與驗證一起設計。

### R67、R68：把「泛化」改成 worst-case-first

R67 建立一個重要原則：不是只看平均，而是先要求每個候選都沒有明顯的最差場景失敗，再比較最差情況的 regret。

R68 對 R61 在 5x、20x、50x 共 301 張真實影像上做 sequence-level 檢查，而不是把大量小 tile 當成獨立樣本。它要求方向、尺度、相關性與局部 alignment 全部過關，才稱作在該拍攝組合上有泛化證據。

### R69、R70：從 CD 走向 ACM 完整輪廓

R69 用 SEM 真實輪廓驗證 R61；R70 用同一框架驗證 V42。重要方法原則：

- 每顆 pillar 的完整外框比較。
- 只允許 translation alignment；不允許 scale 或 rotation fitting。
- 36 顆實體 pillar 才是獨立樣本；12 段曝光只是重複觀察。
- 三種 ACM 平滑設定都要看，避免把單一參數當真理。

這讓研究從「半徑是否靠近」升級成「真實不圓形狀是否靠近」。

### R71 到 R74：刻意建立讓模型失敗的壓力測試

R71 的 100 張未見合成顯微缺陷影像發現：R61 的 PSNR/SSIM 常改善，但弱邊與混合缺陷輪廓會退步。也就是說，像素平均改善不代表輪廓完整性改善。

R72 用 ACM 對封閉缺陷外框再驗，發現 R61 的主要外框常改善，但周長與細鋸齒誤差增加。

R73 用五種未見形狀測試，R74 再刻意加入極低對比、照明不均、非對稱 blur/halo、局部邊界消失與混合困難。R74 的結論是：R61 對低對比、照明不均與某些 halo 有改善，但局部邊界消失與混合困難未能全面通過。

這段的概念結論是：

> 一個模型可以同時「讓主要外框更好」與「讓細邊、淡邊、周長或粗糙度更差」。因此後續模型必須分開判斷位置、過渡寬度、細節、位移、identity 與拼接，而不能再用單一 PSNR、IoU 或 CD 選模型。

---

## 3. R75、R75-v2、R79：用乾淨 scratch 訓練測試「問題是不是資料與權重歷史造成」

### R75：把 R61 架構完全從零開始

R75 的問題是：R61 看起來很強，是否只是因為它沿用許多輪權重與舊資料，無法知道真正有效的是架構、資料，還是歷史路徑？

因此 R75 做了很嚴格的獨立 scratch：

- 保留 R61 的 encoder-decoder 骨架與小幅邊界校正。
- 所有可學權重從隨機值開始。
- 不使用舊權重、teacher、真實 SEM、HS100MG、舊模型輸出或量測 PSF。
- 只用 5,120 張程式資料，16 類基礎形狀。
- 標籤先在 1024 或更高解析度畫好，再 area-average 降到 256，避免鋸齒標籤。
- 多瓣、深凹口、細頸、月牙、粗糙邊界刻意留作外部未見測試。

R75 的概念意義是把「新模型」與「歷史權重延續」切開。它證明同一類骨架可從零學到基本光學與邊界，但也暴露一般形狀資料不足以面對真實密集顯微場景。

### R75-v2：先修資料分布，不急著換架構

R75-v2 的判斷是：R75 把亮物體／暗背景、暗物體／亮背景綁得太死，而且所有輸入都被要求變清楚，會逼模型形成「一定要修」的偏見。

因此只改資料，不改架構：

- 加入非圓、窄頸、新月、星形、孔洞、斷環、不對稱輪廓。
- 加入多物件、多尺度、邊界裁切。
- 用完整五段曝光，讓亮暗極性不再綁定。
- 加入局部 fade、shadow、halo、照明不均與混合困難。
- 960 張不修改／近乎不修改案例，直接教模型清楚輸入要保留。
- 形狀先在 2048 解析度畫出，再降到 256。

R75-v2 在內部合成資料非常強，且 SEM 主外框接近 R61；但 R78 的真實 301 張測試顯示，5x 密集小格與細線仍被錯當背景或雜訊。512 patch 時，100 張 5x 影像大量丟失細節；改 1024 patch 有改善但仍不完整。

概念結論：

> 資料分布改善可以修正「一定銳化」與極性偏見，但低倍密集結構不是單物件形狀資料的自然延伸；必須明確把密度、間距、週期與多尺度同時放進訓練。

### R79：把密集週期與多尺度場景當成主要資料族

R79（原稱 R75-v3）沿用 R75-v2 骨架，但重新分配 5,120 張資料：

- 1,600 張密集週期排列，間距 5 到 24 像素。
- 800 張多尺度混合場。
- 960 張不修改／近乎不修改的細結構。
- 其餘保留非圓、局部 fade、基本幾何。
- 真實結構與模擬條紋的頻率刻意不重疊，避免模型把相同頻率有時當真結構、有時當噪聲。

R80 對 R79 E23 與 E100 做完整擴大比較後，選 E23：

- E100 在內部合成 MAE 較好。
- E23 在 SEM 中央 36 pillar 的平均邊界距離明顯較好，且在 R74 困難顯微較少受傷。
- 兩者真實位移都通過 6/6。

但 R80 同時說明 R79 的根本限制：在 R74 困難顯微下，E23 與 E100 都比 Raw 差，E23 只是較不差。

因此 R79 的真正定位是：

- 它證明密集／多尺度資料可以處理低倍密集結構。
- 它在固定 SEM 對照上很強。
- 它不是「任何顯微場景」的候選，也不是因為 E100 loss 更低就該選 E100。

---

### 同期但不是新模型的驗證與比較輪

這些 round 不一定產生新權重，但它們塑造了後續決策，因此不能略過：

| Round | 角色 | 對後續策略的影響 |
|---|---|---|
| R76 | R75 的 SEM–ACM 完整輪廓驗收 | 將 scratch 模型放回 36 顆真實 pillar，而不是只看內部合成資料。 |
| R77 | R75-v2 的 SEM–ACM 驗收 | 比較內部最佳 epoch 與 E100，避免把訓練選出的權重與 SEM 後選混在一起。 |
| R78 | R75-v2 的 301 張真實顯微泛化 | 發現 5x 密集細節在 512 patch 被大量抹掉，是 R79 資料重分配的直接原因。 |
| R80 | R79 E23 vs E100 的完整驗證 | 證明 loss 更低的 E100 不等於真實 SEM／困難顯微更好，因而選 E23。 |
| R81 | 多架構 reference-circle benchmark | 把比較擴到外部 CNN、attention、transformer 與 MOSR，但明確標示為相同資料包上的控制比較，不是假泛化。 |
| R82 | R39、R40、COMBO、R61、R79 的跨場景比較 | 用同一組 301 張真實影像、R73/R74、SEM 與既有外部 GMF 記錄比較各模型；提醒研究不能把沒有外部 GMF 的候選補成假分數。 |
| R64、R65、R66 | 位移讀值重算、論文圖與可追溯性 | 沒有新模型；它們將舊圖、舊量測流程與來源追溯重新整理，使後來的模型比較可重跑。 |

這些驗證 round 的共同作用是：把「訓練結果」和「真實可用性」拆開。後續模型即使內部 validation 很漂亮，也必須再過真實位移、SEM、難顯微、切圖與外部 GMF。

## 4. R83 到 R87：發現切塊一致性是架構根問題

### R83：先嘗試用 R79 資料與保守輸出補強困難顯微

R83 想在 R79 基礎上處理嚴重低對比、光暈、模糊與邊界消失。

它先做乾淨短訓練，結果沒有超過 R79。還發現早期看似改善的一次訓練，實際上是 PSF 強度被悄悄降到近零，不是資料真的讓模型學得更好；這條結果被正式判為無效。

R83 最終保留一個「保守輸出」選項：同一套 R79 權重，只在低品質輸入時縮小修正幅度。它對 R74 困難顯微有明顯改善，且真實位移不退化，但 512 切片一致性不通過。

這告訴研究者：

> 在同一個舊架構上，改資料或縮小輸出可以減少傷害，但不能根治不同切法得到不同答案的問題。

### R84、R85、R86：直接修 R79 的切圖根因

R79 會依當前影像範圍重算特徵統計。切成小圖時，GroupNorm 或類似全區塊統計改變，結果不是單純接縫，而是整個影像的重建行為改變。

三條修復線：

- R84：改成局部、切塊穩定的根架構。
- R85：保留一次全畫布 optical preconditioner，再用 R79 行為作受限保存。
- R86：把 image-wide GroupNorm 改成 phase-aligned feature block。

三者都可以讓全圖與切圖一致，但都傷害 R79 原有的 SEM、邊界或合成品質。結論不是「沒有修好」，而是：

> 若硬把 R79 變成 tile-safe，等於改掉它依賴的表徵方式；那個表徵雖然造成不一致，也同時參與了原本的形狀能力。

因此 R79 的工程解法是鎖定「整張影像一次推論」，不再把它當成可普遍分塊交付的模型。

### R87：從架構一開始就 tile-native

R87 是第一個真正從零開始、把切塊一致性放進訓練資料的模型：

- 大型 1536 場景用兩種重疊視角一起學。
- 每個輸入保留 192 pixel halo，只輸出中央 core。
- 同一成像的重疊區直接比較，要求不同切法得到同結果。
- 禁止舊權重、teacher、真實資料答案。

R87 完成 100 epochs，內部 tile 一致與自身合成 ACM 都通過。但在 R73 新形狀與 R74 困難顯微出現假孔洞、明顯退化。

這個失敗的意義很重要：

> 原生切塊一致不等於真實形狀泛化；模型可以非常一致地輸出錯誤的局部形狀。

---

## 5. R88 到 R92：從「能切」改成「量測忠實、曝光一致、但不要過度銳化」

### R88：把需求正式整理成 measurement-faithful contract

R88 把前面所有需求一次寫成正式規格：

- 8x 抗鋸齒標籤。
- 正／反／零位移的相同成像條件。
- clear / near-identity case。
- 192 pixel halo、核心輸出，不做羽化式拼接。
- 合成資料、封存盲測、真實 SEM、真實位移、切圖一致性完全分工。

R88 更像一份方法契約與資料／流程藍圖。現有 run registry 主要保留 smoke 記錄，不能把它當成已完成且成功的 100-epoch 交付模型。

### R89：移除 confidence gate，直接學受限重建

R89 認為 R88／早期模型太容易接近 Raw，因此保留 tile-safe local backbone，但移除輸出 confidence gate，讓一個直接 bounded reconstruction 同時負責輪廓、texture、位移與 tile。

R89 的結果非常有教育意義：

- 合成困難輪廓與位移平均改善。
- 全圖與不同切法完全一致。
- 真實 50x 邊緣變強，肉眼看起來更清楚。
- 但真實清楚輸入被明顯改動，新增大量假結構。
- 真實 SEM–ACM 幾乎全面退步，35/36 pillar 較 Raw 差。

R89 證明「過度銳化／強對比」可以讓合成輪廓好看、甚至讓某些位移讀值不壞，但把真實模糊帶壓成強內外暈邊後，ACM 會收斂到錯誤位置。

核心教訓：

> 真實邊界的模糊帶本身含有位置資訊；把它硬壓窄不等於還原真實邊界。

### R90：把 dark outline 與曝光漂移當成物理問題

R90 的策略是：

- 低頻分支必須真的是低通，不能畫出窄黑邊。
- 同一程序幾何以四個曝光共同訓練到同一 contour position。
- 同時訓練 tile pair、cross-observation pair、signed-motion pair。
- loss 強度平滑上升，checkpoint 用連續多軸分數，而非單一硬門檻。

R90 E45 是重要的中間成功：

- 6 組真實位移都通過。
- 分塊結果與整張結果 exact。
- 比 R61 顯著減少 dark outline。
- SEM 12 曝光中有 10 個曝光改善。

但 R90 在 exposure 18 仍讓輪廓外擴；E50 後 5x dark outline 又明顯回來，因此在 E55 停止，E45 被保留作研究與 ONNX 可行性候選，而非交付。

它留下的概念是：

> 模型不該只對單張亮度做修正；同一幾何在不同曝光下必須被迫維持同一位置。但 exposure consistency 還不等於所有曝光都能正確。

### R91：細節與暗邊分離

R91 想保留 R90 的自然邊界與 tile-safe 性，同時更清楚地恢復微觀紋理，且不把 dark outline 當捷徑。

它的概念包括：

- 四個曝光觀測共同訓練。
- 噪聲彼此獨立。
- 多軸選模：contour、detail、identity、motion、tile。
- 讓 detail 不必透過低頻分支或黑邊達成。

R91 的中期 checkpoint 在 SEM 上有改善，但 E60 在 exposure 18 有嚴重失敗，且較晚期 broad correction 變大。這告訴研究者：

> 平均 exposure 表現好，仍可能藏住一個特定曝光點的輪廓崩壞；之後必須用最差曝光，而不是 bundle 平均，決定模型能否保留。

### R92：物理邊界過渡、資料平衡與 clear-input 非劣化

R92 針對 R91 的問題改資料與驗證，而非盲目加 detail loss：

- 邊界不是固定亮度中點，而是非對稱、可記錄位置的物理 transition profile。
- 低對比範圍參考真實儀器 aggregate statistics，但不放任何真實像素或形狀進訓練。
- degraded texture 與 clear-input preservation 分開評估。
- 對本來 geometry 已準的 Raw，加入連續 non-inferiority 約束。
- 四個曝光位置各自報告，最差曝光會進入整體 exposure axis。
- FP32 / tile batch 1 是正式驗證基準，BF16 只作速度敏感度。

R92 的結果是穩定、無 dark halo、FP32 切塊幾乎無縫、困難合成顯微相對 Raw 有改善；但真實高頻仍被壓低，尤其 50x，且 SEM 仍落後 R61/R90/R91。

它推進了「穩定而保守」的方向，卻仍沒有解決真實細節恢復。

---

## 6. R93 到 R97：把重建拆成可解釋的因果分支

### R93：先分清什麼是噪聲，什麼是可恢復細節

R93 的出發點是：舊模型把「去掉隨機 noise」與「恢復被光學退化的真實 texture」混在一個 detail loss 裡，因此最容易學到的解就是平滑。

R93 引入三層同場景真值：

- T：乾淨 latent truth。
- B：沒有隨機噪聲、但仍有光學退化的影像。
- S：含隨機噪聲的輸入。

於是 nuisance target 是 B-S，restoration target 是 T-B。這是一個重要概念轉折：模型不再被允許把所有高頻都叫作 noise。

R93 也採用了：

- normalization-free、local convolution、no global FFT/pooling。
- canonical reflect padding、phase-aligned tile origins、192 halo。
- low-frequency、contour、texture 的非重疊 residual decomposition。

但 R93 的共享表示仍要同時滿足 detail、geometry、identity、motion。後續診斷發現 detail 變差、clear input 改動偏大；它更像設計與診斷節點，不應被當成完整成功模型。

### R94：設計出「按因果形成順序」的私有分支

R94 的邏輯是：

1. 先移除 sensor nuisance。
2. 再修 radiometry。
3. 再修 local contrast fade。
4. 再修 phase-safe structural boundary。
5. 最後才修 material texture。

每個 tower 私有，只共享固定局部量測；need 與 recoverability 分開，且直接由程序真值監督。R94 是為了防止控制圖被拿來當 shortcut。

R94 的原始設計與 smoke 通過，但正式 run artifact 不足，不能被說成已完成大規模成功。

### R95：修正 R94 的「接近 identity」機制

R95 preflight 發現 R94 的 gate 幾乎學不動，原因包括：

- epsilon floor 讓理論零 need 仍非零。
- need bias 飽和。
- image-space L1 對 gate 幾乎沒有梯度。
- EMA 太黏在初始化。

R95 因此改為：

- exact-zero target。
- T/B/S 的 joint logit supervision。
- gradual intervention handoff。
- early EMA adjustment。
- 不允許不同目標彼此反向破壞的更新。

R95 完成 48 epochs，但 internal analysis 仍顯示 clear input 被改動遠多於理想值，且不同 branch 的最佳強度依角色不同，說明單一全域 gate 仍不足以適配所有情境。

### R96：保護每一條分支，不讓總 loss 偷偷犧牲某一條

R96 的修正是把每個 branch 目標在 joint training 期間逐一保護：

- radiometry、nuisance、local contrast、boundary、texture 各自不允許被總 loss 反向犧牲。
- 每八個 batch 加入 clear counterfactual，增強 identity。
- 不再 late-stage 把 detail weight 推高。

R96 的成果：

- 全圖／分塊 exact。
- 六組真實位移很穩，尺度接近命令。
- 不會產生 R89 式 dark edge。
- 小幅對稱局部 detail gain 的後驗測試顯示，增加一些清晰度不一定傷害位移。

但 R96 也有根本問題：need high/low separation 幾乎為零，gate 沒有真正分辨什麼該修、什麼不該修，因此模型仍偏保守。它的 SEM 主外框也明顯落後 R61。

### R97：拿掉抑制有用修正的 gate，直接讓分支輸出實際修正

R97 把設計往更直接的因果方式推：

- 每個 branch 直接預測最終會套用的修正。
- 不再讓 learned amplitude gate 壓掉有用修正。
- 同一程序場景同時提供 noisy、noise-free、clear counterfactual。
- texture 僅能依靠來源中可見、相位對齊的對稱頻帶。
- 加入周期 panel，逼模型分辨真正週期與 adjacent-repeat 的錯誤匹配。

R97 的結果比 R96 更接近使用者想要的視覺：

- 真實 edge gain 與細節能量相對 R96 上升。
- 沒有 off-source dark edge。
- 全圖與分塊 exact。
- 真實位移略優於 R96，且六組序列都穩定。

但 R97 的 SEM 外框仍遠落後 R61，表示「讓細節活回來」不等於「真實 SEM 主外框更準」。

---

## 7. R98 到 R104：深入找出高頻為何總被模型當噪聲

### R98：更激進的 texture 嘗試

R98 的假說是 R97 的紋理目標太稀、頻帶太少、分支互相抵消，所以把三個頻帶擴成六個，增加 texture supervision 與對分支抵消的懲罰，並取消最後回到保守直通的階段。

它確實完成 48 epoch formal run，但目前 R98 的完整 post-training documentation 不如 R89、R92、R103 完整，README 與結果檔也有過時狀態。它應被視為「激進 texture 的探索與後續 R99/R101 的問題來源」，不應被放進可靠的交付候選排名。

### R99：讓 geometry transport 在 texture 前真正可作用

R99 的概念是：如果 contour 位置不對，texture restoration 建立在錯位邊界上沒有意義。因此設計了：

- radiometry -> signed subpixel contour transport -> edge profile -> texture 的固定順序。
- geometry transport 在全訓練期間可動，不只當輔助頭。
- local、normalization-free、192 halo、tile-exact backbone。

R99 只有 smoke artifact，沒有可視為完整 formal result 的 evidence。它的想法被 R100 的更受限因果 operator 接續。

### R100：把自由殘差縮成受物理限制的 operator

R100 的設計比 R99 更保守：

- output 以 Raw 為基底。
- 沒有自由 image residual。
- 不允許 geometry transport。
- 一次只做有上限的 radiometry、flat-region denoise、symmetric edge profile、boundary-excluded material texture。
- 不用 normalization、global pooling 或 global FFT。
- 明確要求 full/tile 共享同一路徑與 exact parity。

R100 完成 40 epoch，確實保住 tile exact、identity 比早期模型好、合成邊界和 motion 有改善；但它的真實影像輸出仍偏去噪與平滑。

這一點不是直覺判斷，而是 R101 對 R100 做的短 A/B/C/D/E/F/G mechanism experiments 所證實。

### R101：最重要的根因實驗，不是新交付模型

R101 沒有直接再燒完整訓練，而是用相同資料與 400 step 對照實驗問：

「模型為何總先學會去噪，卻學不會真實微觀細節？」

結果：

1. edge path 的原始梯度比 radiometry 小約 70 到 160 倍。
2. 細節目標與像素／identity／位移等目標常方向相反。
3. R100 類資料中，最細邊界頻帶真正相位一致且值得增強的比例只有約 2.2%；大量案例的正確答案反而更平滑。
4. serial 設計先刪高頻、再試圖恢復 texture，本身就會衝突。
5. 就算加入 high-frequency innovation，模型仍學到近乎全域的 finest-band suppression。

R101 的重大結論：

> 保守平滑不是訓練不夠久，而是資料、真值、表示能力與梯度關係一起把「刪除高頻」變成最容易、最能降 loss 的策略。

因此 R101 提出下一代必要條件：

- source 與 target 必須由同一連續 latent scene 成像，保留可恢復 texture 的相位。
- boundary、recoverable material、noise、不可恢復頻率要分開。
- 模型要有能重畫次像素邊界或生成有證據的 innovation 的輸出形式。
- detail 不能再與所有目標直接相加後被淹沒。

### R102：parallel innovation 的嘗試

R102 設計了 radiometry、contour、generative texture innovation 的平行路徑，保留 tile safe 與 exact identity initialization。現有 artifact 只有 smoke run，沒有正式 48 epoch 結果，因此不應把它列為已驗證模型。

### R103：把「可恢復性」真正寫入生成資料與殘差分解

R103 是這條 clean-scratch 線目前最完整、最有價值的結果之一。它的關鍵改動：

- observation 由可恢復的 local optical forward model 從程序真值生成。
- exposure、contrast、gamma、illumination 同時作用於 source 與 label；模型不再被要求猜一個不可觀察的 source-only 曝光修正。
- 每個 degraded crop 都配同一位置 clear crop，清楚圖直接監督零修正。
- 移除 feature normalization，保留微弱 local amplitude 與 texture cue。
- low-frequency、contour、texture 分成非重疊 residual。
- loss 權重固定，不再用訓練 scalar loss 動態調整。

R103 E48 的成果：

- 全圖與分塊在三張大圖上幾乎一致。
- 六組 5x/20x/50x 真實位移穩定，至少不差於 R61。
- 相比 R96，真實細節與 edge gain 回升，沒有 broad dark outline。
- 在 R73 新形狀、R74 困難顯微的一些子類有改善。

但它仍不適合作為 R61 的全面替代：

- SEM aggregate contour 仍落後 R61。
- exposure 18 是明顯失敗點。
- uneven illumination 仍沒有可靠修好。
- 已清楚圖仍會有小幅不必要修正。

所以 R103 是「原生 tile、安全、較自然 texture、位移良好」的研究候選，不是 SEM／外部 GMF 已全面勝出的最終模型。

### R104：試圖讓 shape 判斷與亮度、曝光、gate 真正分離

R104 是對 R103 做的最直接根因修復。R103 的問題是：

- gate 最小修正強度仍大於零，不能真正關掉。
- contour / texture confidence 對 clean 與 hard 的分離很差。
- shape 過度依賴絕對亮度，曝光 18 會跨過非線性捷徑。
- 單一 image-wide brightness midpoint 對局部 shading、halo、low contrast 不穩。

R104 的設計：

- shape 與 need gate 只讀 local relative cue；Raw amplitude 留給修正 proposal。
- 任意形狀用 signed distance field，不假設圓或半徑。
- radiometry、illumination、contour、texture 各自有 proposal 和真正可到零的 gate。
- 同一 geometry 在多個曝光／illumination 下要求 shape decision 一致。
- texture 先在 4x 解析度畫，再降採樣。

R104 的 formal run 實際上已完成 48 epoch，儘管 README 與 root-cause file 仍保留「尚未正式訓練」的過時文字。結果很有代表性：

- 新形狀 R73 上的 contour 變好。
- 六組真實位移都通過。
- 大圖切塊幾乎一致。
- 但 R74 困難顯微大多退回 Raw，表示模型太常選擇不修正。
- 真實 SEM 中央 36 pillar 甚至比 Raw 與 R61 差。

這說明 R104 解掉了一部分「亂修」問題，卻把模型推向過度保守／近似 identity；它還沒有學到在困難真實成像中何時該安全地啟用修正。

---

## 8. 這一路真正學到的，不應再被遺忘的規則

### 8.1 視覺、SEM、位移、GMF 不是同一件事

- R89 證明視覺更銳利可使真實 SEM 更差。
- R61 證明 GMF 可大幅更穩，但細周長與極暗曝光仍失敗。
- R79 E23 的 SEM 很強，但不能安全做任意切塊。
- R103 的 tile／motion／texture很平衡，但 SEM 主外框仍弱於 R61。

未來不能再用單張 demo、PSNR 或單一 ACM 分數宣布模型更強。

### 8.2 切塊一致性必須原生設計

R79 的案例證明，若模型內部依賴 image-wide normalization 或全域 FFT，切圖大小改變就會改變模型答案。羽化拼接只能遮住接縫，不能讓模型本身一致。

後續 local models 的共同原則：

- no global pooling。
- no image-wide spatial normalization。
- canonical reflect padding once。
- phase-aligned tile origins。
- halo context。
- core-only output。
- full/tiled 同一路徑。

R61 ONNX v1.1 只能在 runner 層改善這件事，因為 R61 權重本身仍有 GroupNorm 與 FFT；R103/R104 才是結構上原生 tile-safe。

### 8.3 不該再把真實影像偷混入訓練

R75 後的 scratch 主線刻意固定：

- 只用程序形狀。
- 8x 或更高解析度標籤再一次性降採樣。
- 真實 SEM、HS100MG 不進訓練 pair。
- 最多只用匿名 aggregate optical statistics 塑造 noise、illumination、PSF 分布。
- 真實影像僅在 checkpoint 鎖定後做 validation。

這是為了讓泛化宣稱可被檢驗，而不是讓模型背下手上的柱子。

### 8.4 不要把「細節」當成單一 loss

R101 已經證明，高頻可能是：

1. 真實可恢復邊界；
2. 真實可恢復材質；
3. 隨機 sensor noise；
4. 原本就不可從單張觀察回推的資訊；
5. halo、ringing 或模型新造的假細節。

因此後續模型需把它們分開，尤其要透過同一 latent scene 的多個觀測、相位一致性、clear counterfactual 與可恢復性，讓模型知道什麼可以修、什麼應保留、什麼不能猜。

### 8.5 過度保守與過度激進都不是答案

- R89：太激進，假邊／SEM 退步。
- R92、R96：太保守，真實高頻被壓低。
- R97：較好地回收 detail，但 SEM 不足。
- R104：gate 可關掉後，在困難真實影像又太常退回 identity。

真正要追求的不是抽象的「平衡」，而是能依局部可觀察證據正確決定修正幅度與種類。

---

## 9. 目前可用的研究判斷

### 可以相對有信心說的

1. R61 是目前外部 GMF 定位最有直接實測支撐的模型。
2. R61 ONNX v1.1 的新分塊 runner 沒有破壞這個 GMF 優勢。
3. R79 E23 在固定 SEM 中央 36 pillar 的完整輪廓上很強，但其原始網路不應作一般切塊交付。
4. 後續 scratch 線已成功建立 exact tile-safe inference 與穩定真實位移的能力。
5. R103 是目前最接近「真實細節、tile-safe、motion-safe」三者兼顧的 clean-scratch 候選。

### 不能說的

1. 不能說任何模型已經對所有顯微場景泛化。
2. 不能說細節變強必然讓 GMF 或 SEM 更好。
3. 不能說 R103、R104 已取代 R61。
4. 不能把 R79 的整張結果直接當成切塊部署結果。
5. 不能把內部合成 metric 的提升直接外推成真實 SEM 提升。
6. 不能把仍只有 smoke 或設計 artifact 的 R88、R93、R94、R99、R102 當成完整訓練模型。

### 目前最值得 GPT 協助分析的問題

1. R61 的外部 GMF 優勢究竟來自真實幾何改善、模板匹配偏好，還是兩者兼有？
2. R79 E23 為何在固定 SEM 很強，但在 R74 困難顯微與切圖上失敗？這能否用局部統計／GroupNorm 的機制解釋？
3. 後續 tile-safe models 為何普遍保守，且 SEM 主外框弱於 R61？是 training target、PSF model、real-domain shift、還是 lack of global context？
4. R103 的 recoverable-data 方向已有效改善真實細節與位移，下一步要如何修 exposure 18 與 SEM coarse contour，而不重回 R89 的假銳化？
5. R104 的 true-zero gate 為何在新形狀有效、在困難顯微近 identity、在 SEM 反而變差？gate calibration、observable evidence、或 train/test degradation gap 哪一項最可能是主因？
6. 是否應把未來模型改為兩個有明確接口的模式：單張安全模式與短序列證據融合模式？前者不猜不可觀察細節，後者在多個觀測一致時才允許更強恢復。

---

## 10. 給另一個 GPT 的建議分析任務

請用以下立場分析：

1. 不要推薦單純增加 epoch、增加 detail loss、或把真實 SEM 影像放進訓練。
2. 不要假設「平滑與位移穩定」必然互相衝突；R96 的後驗 detail gain 與 R97 的結果已顯示兩者可部分相容。
3. 將問題拆成：資料可識別性、真值定義、網路架構、局部／全域 context、gate 校準、損失梯度衝突、實際量測工具偏好。
4. 對每一個新建議，必須說明它會如何同時被以下項目反證：SEM full contour、R73/R74 合成形狀、5x/20x/50x 位移、full/tiled parity、外部 GMF。
5. 明確區分「能改善外觀」、「能改善真實形狀」、「能改善相對位移」、「能改善固定 GMF」四種主張。

---

## 11. 關鍵來源與可信度優先順序

讀取資料時應遵守這個優先順序：

1. run_summary、final summary、locked validation JSON、external GMF score log。
2. PROJECT_STATE.md、ESTIMATOR_POLICY.json。
3. 實驗 README、design 文件與結果報告。
4. 舊 handoff 或 memory 摘要。

有幾個文件狀態已知較舊：

- R93 README 內容與 R92 高度重複，請以 R93 config 與後續 R94 diagnosis 為準。
- R98 有 formal run，但 R98_RESULTS.md 仍保留早期「結果待補」文字。
- R104 README 與 root_cause_and_design.json 說正式訓練尚未開始，但 run registry 與 posttraining validation 已證明 formal E48 已完成；應以 run registry 和 validation 結果為準。
- R88 README 描述過正式啟動，但目前可直接核對的 registry 主要是 smoke 記錄，因此不可把它當成已驗證成功的正式 100 epoch 結果。

最重要的實體來源：

- 論文 V42：D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\README_CURRENT_THESIS_RESULTS.md
- V42 與 R61 SEM 完整輪廓：D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation 和 R70_V42ACMContourSEMValidation
- R61 角色與資料：D:\GMM_2_Final\Experiments\R61_STEP_Generalization_20260623
- R75 / R75v2 / R79：D:\GMM_2_Final\Experiments\R75_R61ArchitectureScratchGeneralization、R75v2_R61ArchitectureScratchGeneralization、R79_R75v3_DenseMicroscopyScratchGeneralization
- R79 E23/E100 對照：D:\GMM_2_Final\Experiments\R80_R79E23vsE100GeneralizationValidation\reports\R80_RESULTS_TW.md
- Tile root-cause：D:\GMM_2_Final\Experiments\R84_R79TileStableRootRepair
- Measurement-native 線：D:\GMM_2_Final\Experiments\R89_MeasurementNativeScratch 到 R104_PhotometricInvariantCausalGateScratch
- 新版 R61 ONNX + 外部 GMF：D:\GMM_2_Final\Thesis_MOSR_Evidence\External_GMF_Packages\GmmVisionTool_FixedFlow_Benchmark\analysis\r61v11_gmf_analysis.json

---

## 12. R105A 到 R106A：多觀測支線與回歸單張主線

R105A 首次完整測試「預測 SDF 後直接生成最終邊界」。理想輪廓交給生成器時幾乎完美，但模型估計未見形狀輪廓時，直接生成會把錯誤零集合硬寫進影像。延長訓練、來源混合與殘差混合都沒有形成全面優勢，因此正式 R105 未啟動。

R105B 改測多觀測證據集合。在程序資料的理想觀測組合中，N=1、N=2、N=4 呈現逐步改善，證明多次觀測在資訊充分時可以突破單張歧義；候選分支差異本身不能作可信度，需改用結構相容與逐張留一分歧。

R105C 將均華 202 張真實影像整理成 101 個同位置雙張與 100 個跨位置組。所有同位置組穩定，跨位置約 X -0.083／Y -7.886 px 且可精細對齊。但同位置雙張位移中位數只有 0.091 px，跨位置最近整數相位差中位數約 0.161 px，主要提供降噪而非充分分散的超解析取樣。

R106A 用更接近應用的單一權重、參考幀錨定與均華統計重新短訓練。N=2 改善輪廓距離與影像誤差；N=4 繼續改善影像誤差和位移尾端，卻不再改善輪廓與邊界中心，曝光穩定性也變差。鎖定後均華 N=4 幾何安全，但沒有獨立真值證明更準，錯配退回也不完整。程序與真實閘門均失敗，完整 R106 未啟動。

2026-08-24 的正式研究優先決策：多觀測不再作為通用主線，只保留同位置 N=2 選配與未來刻意微位移拍攝研究。主線回到單張模型。下一個 `R107A_SingleImageEdgeGeometryProbe` 改以局部法線座標明確分離邊界中心與過渡寬度：第一階段固定中心、只驗證寬度修正，避免全局 SDF 與自由影像殘差再次用銳化換位置漂移。

完整決策記錄：`GPT_Context/SINGLE_IMAGE_MAINLINE_RETURN_20260824.md`。
