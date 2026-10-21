# R114 執行紀錄與目前決策

狀態：第二版 split-reliability + bounded-profile scratch probe 實作中；尚未建立正式交付模型。

## 1. 資料修正

- 舊 5,000 train + 512 validation target/mask/SDF 只讀重用。
- 只新增 240 張缺失形狀，替換過量 dense/easy 樣本，總量維持 5,512。
- 新增 close-pair、narrow-gap、micro-notch、rough-Fourier、ultra-thin-ring。
- 8 倍超採樣後降回 256；補充資料 SDF sign 與 mask 一致率修正至 1.0。
- 每 scene loss 先正規化；batch 16/12 的 dense 至多一筆，identity 一至兩筆。
- 原始資料 manifest SHA-256 前後不變。

## 2. Controller Probe 1

第一版從零訓練 8 epochs：

- boundary AUC median 0.99845；控制器不再死亡。
- 但 dense truth AUC 0.5229，identity boundary need 過高，正式判定 stop-and-repair。
- 診斷發現 dense raw edge detectability 只有 0.5051，但舊 recoverability target 錯給 0.4217，和一般形狀 0.4246 幾乎相同。
- identity 正確 need=0，舊模型在真實邊界卻預測 0.8807。

## 3. Controller Repair Probe

精準修正 density/visibility target、need role balance 與少量 clear counterfactual，重新從零訓練 8 epochs：

- boundary AUC median 0.99681。
- 可恢復 family 最差 AUC 0.97484。
- degraded boundary need 0.85817；identity 0.11751。
- dense geometry gate 只有一般形狀 25.0%。
- cross-degradation correlation 0.96983。
- 六項 viability 證據全部通過，才准進 geometry probe。

## 4. Geometry Probe E20

完全從零，8 epochs controller + 12 epochs geometry：

- 20 epochs、8,340 steps 完整結束；無舊權重、無非有限值。
- 完整 synthetic validation L1 由 E8 0.033189 降至 E20 0.032637。
- boundary AUC 0.99808；identity change 0.0000537。
- R73 五種未見形狀的 pixel MAE 全部改善。
- R73 locked ACM：overall boundary distance -27.50%，IoU +0.001510，五 family 全部改善，零 ACM failure。
- R74 locked ACM：IoU +0.002608，但 boundary distance +0.866%，屬混合結果，不能進 detail/formal。

R74 family boundary change（負值為改善）：

- asymmetric blur/halo -15.286%；
- uneven illumination -0.496%；
- boundary fade +1.823%；
- low contrast +0.299%；
- mixed hard +0.866%。

## 5. Geometry Causal Dissection

同一 E20 權重做介入，沒有重新訓練：

- WidthOnly overall +1.379%；ShiftOnly +5.283%；Full +0.866%。
- 現有 normal_shift 與 normal-profile oracle shift 的 Spearman rho=0.000096，代表舊 shift target 沒有可驗證關係。
- 現有 shared geometry gate 在 shift 不可靠點仍有 median 0.857。
- 新 normal-profile width/shift reliability 在 R74 五類有顯著分離；safe/unsafe shift AUC 0.885。
- 但 oracle/local gate 仍無法修復 boundary-fade/low-contrast/mixed-hard，證明現有 width/shift action library 本身缺少能力。

## 6. Bounded Boundary-Profile Oracle

新增固定、解析、局部 action 作容量上界；沒有自由 residual、沒有更新權重：

- profile = midpoint + 0.5 * signed contrast * tanh(SDF / width)。
- 10 px 內完整作用，10–14 px 平滑衰減，14 px 外精確為零。
- 單點 action delta 封頂 48 gray。
- 600 primary ACM + 135 sensitivity rows 完整、零 failure，15 項 QA 全通過。
- boundary fade -88.64%；low contrast -5.71%；mixed hard -91.82%。
- halo 與 uneven 既有改善保留。
- 此結果只授權 learned profile-head probe，不是可部署模型。

## 7. 大圖分塊根因與政策

- 三種 deployment tile grids 彼此 p99 差 0.00058 gray，max 0.0390 gray（代表 5x 測試圖）。
- direct full vs tiled 的大差異只在物理影像外邊；排除 192 px 外框後 max 0.00614 gray。
- 根因是 layered reflect padding 與 one-time outer padding 的外框語意不同，不是 tile seam。
- 正式政策：所有影像尺寸都以 tiled deployment output 為唯一 canonical output；direct forward 只供診斷。

## 8. 第二版已鎖定設計

下一版必須從零訓練，不能接續 E20：

1. `width_reliability` 與 `shift_reliability` 獨立。
2. normal-profile 10–90 width 與 two-scale centroid shift 取代 same-pixel slope/flow target。
3. shift 先作用，再由 width gate 處理 shifted base。
4. 新增 midpoint-offset / signed contrast / profile width / visibility 四參數 bounded profile action。
5. 刪除舊 free detail residual；recoverability 只作 profile evidence。
6. reliability、width、shift、render、translation、exposure、profile 分開 optimizer steps。
7. 先跑 reliability probe；通過才跑 split-profile probe；再重跑 R73/R74、真實影像與 canonical tile 驗證。

## 9. 目前禁止宣稱

- R114 尚不是正式模型或交付模型。
- Profile oracle 不是 learned reconstruction。
- E20 雖在 R73 強，但 R74 尚有 hard-family regression，不能越過第二版探針。
- 尚未執行 final SEM/LSC/real-motion/external-GMF qualification。

## 10. R114B 完整 Split-Profile Probe

- 從零訓練 28 epochs、11,676 steps，來源與初始權重證據完整。
- E20 幾何節點安全；E24 開啟 profile 後 validation MAE 由 0.0264231 退化到 0.0271575（+2.78%）。
- 實際 profile 動作方向正確率只有 34.76%。
- 根因不是單一亮暗極性寫反，而是 profile backbone 未被 optimizer 更新、true-SDF 訓練座標與 predicted-SDF 推論座標錯配、visibility 過度開啟、loss 沒有直接評估最終輸出。
- E24/E28 不升格；E20 僅保留為安全錨點。

## 11. R114C 精準修復與第二次從零訓練

完成四項修正後，由全新隨機初始化再跑 24 個完整 epochs：

1. profile optimizer 從 196 個 head 參數修正為完整 340,420 個 profile 參數；
2. visibility target 改用模型實際 predicted coordinate 的反事實改善；
3. render/guard loss 直接評估 final output 與 geometry base；
4. 移除 visibility 之外重複的 need/recoverability 抑制。

E20 幾何節點：

- validation MAE 0.02642349，重現 R114B E20。
- R73 locked ACM boundary distance -8.352%，五 family 全改善。
- R74 locked ACM boundary distance -2.109%、IoU +0.006051；halo -3.407%、boundary fade -5.134%。
- R74 仍有 low contrast +0.107%、mixed hard +0.907%、uneven illumination +0.629% 小幅退化。
- 真實 5x 三種 canonical tile grids 全通過；最大差 0.00903 gray，identity MAE 0.000273 gray。
- 真實多倍率單張 mean absolute change：5x 0.0645 gray、20x 0.9489 gray、50x 1.8631 gray；raw-edge gain 分別 1.0018、1.0687、1.1215，off-source strong edge fraction 全為 0。

E24 profile 節點：

- validation MAE 0.0274381，相對 geometry base 0.0265218 退化 3.45%，因此在 E25 early stop。
- R73 locked ACM boundary distance +83.74%，五 family 全退化，明確淘汰。
- R74 總平均受 uneven illumination -42.31% 拉高，但 boundary fade IoU -0.01737；不能用總平均掩蓋失敗。

## 12. R114C 深層失敗原因

- R114C 的 profile 參數其實明顯進步：contrast Spearman 0.696、width 0.397；R114B 分別約 0.260、-0.310。
- 但 learned action 方向正確率仍只有 44.07%；整體倍率 0–1 掃描最佳為 0，不能只縮小修好。
- 拿掉 need/recoverability 後，R114C 真實邊界的最終 gate 反而是 R114B 的 1.70 倍；有效 profile delta 為 3.60 gray，R114B 為 2.60 gray。
- 加回 need+recoverability 可消除 82.09% 退化，但仍略差於 base，只能遮錯，不能根治。
- predicted profile band 覆蓋全圖 100%，真正邊界帶只有 18.66%；visibility supervision 因而被大量背景支配。
- 若使用針對當前 learned proposal 的正確 action selection，現有 E24 profile 可把 MAE 從 0.0265218 改善到 0.0252463，證明主要瓶頸是「何時、何處、做多少」，不是 profile action 空間本身。

## 13. 下一個已授權短探針

R114D 只作因果探針，不是候選模型：

- 凍結 R114C E24 proposal 與 profile 參數；
- 將 action selection 拆成 acceptance（能不能做）與 amount（做多少）；
- 標籤按當下 learned proposal 的 signed gain 與最佳作用量即時計算，不再按 oracle profile parameters；
- 保留 boundary × need × recoverability 安全控制；
- selector 僅在真實邊界帶、clear/identity hard negatives 上校準，避免全圖背景支配。

只有短探針在 validation、R73/R74 worst-family、identity 與 tile 全部正向，才允許整合回下一個 scratch 架構。

## 14. R114D Causal Selector 短探針

- 凍結 R114C E24 全部 681,183 個 proposal 參數，只訓練 54,319 個 selector 參數。
- 全 5,000 張、6 epochs、3,750 steps 完成；proposal hash 前後完全相同。
- 固定 128 張中 E3 最好：final 相對 base 只改善 0.0002706 gray，boundary 只改善 0.001157 gray；acceptance AUC 0.543。
- E5 雖 77.5% 已選動作方向有益，但 active fraction 只有 0.247%，模型已接近全關閉；selector 能避錯，卻沒有實質釋放 profile 容量。
- E3 locked ACM：R73 overall -0.782%，crescent +0.355% 退化；R74 overall +0.925% 退化，mixed hard +0.925%。因此不升格。

R114D 另揭露共享 backbone 污染：

- R114C profile optimizer 雖已正確包含完整 profile parameter contract，但其中的 `renderer_backbone` 同時供 width/shift heads 使用。
- E21–E24 為了讓 profile features 學習，實際也改變了 width/shift 的輸入特徵；因此 E24 的 `base_output` 已不是 E20 的安全幾何基底。
- R114D 即使把 selector 幾乎全關，仍只能回到被污染的 E24 base；R73 從 E20 的 -8.352% 掉到約 -0.782%，R74 從 -2.109% 變成 +0.925%。
- 下一個架構必須讓 geometry backbone/heads 在 E20 後可完全凍結，profile 使用獨立 adapter/tower；任何 profile 學習都不得改變 base_output。

## 15. R114E Decoupled Hybrid 短探針

- E20 唯一負責 controller/width/shift/base；E24 只提供 profile renderer 與四個 profile heads。
- selector=0 時 output 與 E20 bit-identical，max abs=0；兩份來源模型全凍結。
- 固定 128 張 headroom：35.48% actionable boundary 方向可用；97% 非 identity scene 有正 gain；oracle-best gain 9.93 gray^2，允許短訓練。
- 2,048 張、6 epochs、1,536 steps 完成；兩來源 hash 前後不變。
- E6 固定 validation 最佳：整體改善只有 0.0000540 gray，boundary 改善 0.0002089 gray；acceptance AUC 0.520，仍不足以可靠選擇。
- E6 locked ACM：R73 -8.441%，R74 -2.080%，基本保留 E20，但沒有一致超越 E20；R74 mixed hard +0.932%、uneven +0.629% 仍退化。

結論：分支隔離已被證明必要且有效，但目前 2D local selector 特徵不足以判斷 learned profile proposal 的正負收益。R114E 是成功的架構因果驗證，不是新正式模型。

## 16. 本輪實際保留結果

- 目前 R114 系列真正可保留的模型權重是 R114C E20 geometry checkpoint。
- R114B E24/E28、R114C E24、R114D E3、R114E E6 都不得升為正式或交付版本。
- 下一個從零架構若繼續 profile 路線，必須同時具備：完全獨立 profile tower、沿法線取樣的 1D profile evidence、專用 metric coordinate/coordinate confidence、acceptance 與 amount 分離、full safety gate，以及 profile 訓練不得改變 geometry base。
