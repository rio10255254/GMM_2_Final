# 三形貌現代模型比較：正式結果報告

## 核心結論

本次比較已把原本的 pillar 與 line 擴充為 pillar、via、line 三種形貌。Via 使用 SEM 表中的九筆半徑，全部先乘以二再作為 CD 參考；九顆 via 的平均 SEM 直徑為 3289.0 nm，範圍為 3276.5–3303.7 nm。50× 與 20× 的樣品方向分開處理，20× 採上下反向配對。

所有方法使用同一批 Raw 預先鎖定的位移步數、同一組位置、同一個邊界規則與原生灰階。現代模型加入參數量匹配的 Compact NAFNet 與 EDSR-x1，並與 Raw、基礎 U-Net、MOSR 比較。兩個對照模型均由頭訓練，不使用外部預訓練權重；灰階輸入、輸出尺寸、資料切分、損失函數、有效批次與最佳權重規則一致。NAFNet 跑滿 30 回合，EDSR-x1 在第 15 回合驗證改善已趨緩後停止；正式推論均使用各自最低驗證誤差的權重。這項實驗比較的是架構本身，而不是以大型模型容量取得優勢。它支持的是同一樣品與同一顯微系統下的跨形貌量測轉移，不把它寫成跨樣品或跨設備的完整泛化。

20× via 是本次最清楚的新增證據：MOSR 相對 Raw 的 CD 中點 MAE 降低 65.2%，10%–90% 邊界寬度降低 79.6%。這代表原本因低倍率取樣而縮小、模糊的亮孔邊界，經重建後更接近 SEM 尺寸且更容易定位。另一方面，環狀振鈴也同步列出，避免把銳利化直接等同於量測正確。

位移方面，MOSR 相對 Raw 的 pillar MAE 改善 31.1%，via MAE 改善 7.6%；九宮格內不一致量則分別降低 63.1% 與 43.0%。不過 Base U-Net 與 EDSR 在部分位移指標更低，因此這組結果支持的是 MOSR 相對 Raw 的穩定改善，而不是所有指標全面第一。CD 也具有形貌與倍率差異：50× via 以 Base U-Net／EDSR 較接近 SEM，20× pillar 則 Raw 與 NAFNet 較接近 SEM；MOSR 的最明確優勢集中在模糊較重的 20× via。

在線寬位移的學習式方法中，邊界 MAE 最低的是 EDSR（3.29 nm），但 Raw 仍略低（3.15 nm）。基礎 U-Net 往往得到最窄的邊界，但其對比與銳化幅度也最大，因此不能只以邊界寬度判定整體方法最好；需同時看 CD、位移、局部一致性與振鈴。

## SEM 參考與 CD、銳利度

CD 不採單一 50% 門檻作為唯一答案，而是固定掃描局部對比的 35%–65%，以上下界表示門檻敏感性。表中的 CD 中點 MAE 是上下界中點相對 SEM 的誤差；CD interval width 越小，表示邊界位置對門檻越不敏感；edge width 越小表示影像越銳利；ringing ratio 越小表示額外亮暗振盪越少。

| Magnification | Morphology | Method | CD midpoint MAE (nm) | CD interval width (nm) | Edge width (nm) | Ringing ratio |
|---|---|---|---|---|---|---|
| 50x | Pillar | Raw | 46.3 | 285.7 | 613.7 | 0.013 |
| 50x | Via | Raw | 448.6 | 353.1 | 717.0 | 0.033 |
| 50x | Pillar | Base U-Net | 79.6 | 72.3 | 114.9 | 0.030 |
| 50x | Via | Base U-Net | 156.3 | 64.1 | 108.9 | 0.005 |
| 50x | Pillar | NAFNet | 63.3 | 111.4 | 168.9 | 0.010 |
| 50x | Via | NAFNet | 173.3 | 96.1 | 172.9 | 0.030 |
| 50x | Pillar | EDSR | 79.6 | 74.2 | 105.1 | 0.239 |
| 50x | Via | EDSR | 157.8 | 84.5 | 142.9 | 0.033 |
| 50x | Pillar | MOSR | 48.6 | 81.8 | 508.9 | 0.005 |
| 50x | Via | MOSR | 181.4 | 97.9 | 699.8 | 0.012 |
| 20x | Pillar | Raw | 52.6 | 415.5 | 742.8 | 0.004 |
| 20x | Via | Raw | 644.0 | 432.6 | 887.5 | 0.011 |
| 20x | Pillar | Base U-Net | 195.3 | 175.0 | 272.0 | 0.014 |
| 20x | Via | Base U-Net | 546.8 | 367.7 | 792.7 | 0.000 |
| 20x | Pillar | NAFNet | 60.3 | 247.7 | 378.0 | 0.036 |
| 20x | Via | NAFNet | 531.4 | 339.8 | 740.6 | 0.001 |
| 20x | Pillar | EDSR | 340.7 | 197.0 | 304.7 | 0.045 |
| 20x | Via | EDSR | 497.3 | 327.4 | 764.8 | 0.000 |
| 20x | Pillar | MOSR | 162.2 | 168.2 | 252.0 | 0.131 |
| 20x | Via | MOSR | 224.2 | 129.0 | 180.9 | 0.581 |

## Pillar 與 via 位移

每個倍率與步距均只使用 Raw 運動品質排序後固定選出的 30 步。表中為五種方法共同有效步數的交集，PI 命令位移作為實驗位置參考。MAE 反映與參考步距的接近程度，error SD 反映逐步穩定性，within-grid disagreement 反映同一九宮格內九個結構是否得到一致位移。

| Morphology | Method | Common steps | MAE vs PI (nm) | Error SD (nm) | Within-grid disagreement (nm) |
|---|---|---|---|---|---|
| Pillar | Raw | 118 | 9.30 | 11.64 | 17.38 |
| Pillar | Base U-Net | 118 | 5.92 | 7.68 | 4.90 |
| Pillar | NAFNet | 118 | 10.59 | 15.14 | 19.75 |
| Pillar | EDSR | 118 | 6.14 | 7.99 | 6.00 |
| Pillar | MOSR | 118 | 6.40 | 8.29 | 6.41 |
| Via | Raw | 120 | 7.31 | 9.43 | 14.34 |
| Via | Base U-Net | 120 | 6.15 | 8.31 | 4.60 |
| Via | NAFNet | 120 | 6.90 | 9.21 | 8.84 |
| Via | EDSR | 120 | 5.99 | 8.30 | 5.66 |
| Via | MOSR | 120 | 6.76 | 9.02 | 8.17 |

## Line 形貌

Line 沒有獨立 SEM CD，因此不宣稱絕對線寬正確；本區只比較原生邊界寬度、過衝與 60 個鎖定位移步的定位表現。

| Line orientation | Method | Edge width (nm) | Overshoot ratio |
|---|---|---|---|
| Horizontal Lines | Base U-Net | 181.8 | 0.009 |
| Horizontal Lines | EDSR | 178.6 | 0.007 |
| Horizontal Lines | MOSR | 587.1 | 0.037 |
| Horizontal Lines | NAFNet | 226.3 | 0.012 |
| Horizontal Lines | Raw | 683.8 | 0.035 |
| Vertical Lines | Base U-Net | 184.6 | 0.009 |
| Vertical Lines | EDSR | 193.3 | 0.005 |
| Vertical Lines | MOSR | 579.2 | 0.032 |
| Vertical Lines | NAFNet | 230.1 | 0.010 |
| Vertical Lines | Raw | 706.1 | 0.035 |

| Method | Steps | Boundary MAE (nm) | Boundary error SD (nm) | Within-edge MAD (nm) |
|---|---|---|---|---|
| Raw | 60 | 3.15 | 3.66 | 2.64 |
| Base U-Net | 60 | 4.00 | 4.93 | 6.52 |
| NAFNet | 60 | 3.30 | 3.94 | 5.25 |
| EDSR | 60 | 3.29 | 3.52 | 2.69 |
| MOSR | 60 | 3.70 | 4.22 | 6.18 |

## 原生灰階與對比

所有比較影像均保留原生 8-bit 灰階，沒有逐張自動拉伸。Base U-Net、NAFNet 與 EDSR 的原生灰階標準差明顯高於 Raw，表示其高對比來自模型輸出，而不是顯示處理；各方法的極端灰階截斷比例仍很低。目視上，EDSR 在部分 via 與 line 背景出現光暈或紋理，NAFNet／EDSR 的 20× pillar 有較明顯稜角化；MOSR 大致保留圓形，但 20× via 形成明顯環狀輪廓。因此，20× via 的 CD 改善應解讀為外側邊界位置更接近 SEM，而不是整個灰階形貌已完全忠實還原。

| Method | Median native SD | Max low clipping (%) | Max high clipping (%) |
|---|---|---|---|
| Raw | 42.93 | 0.000 | 0.000 |
| Base U-Net | 79.19 | 0.256 | 0.000 |
| NAFNet | 77.32 | 0.065 | 0.002 |
| EDSR | 72.95 | 0.000 | 0.000 |
| MOSR | 44.68 | 0.000 | 0.000 |

## 計算效能

四個學習式模型的參數量均控制在約四百萬。完整影像速度以 2048×1536 影像、相同 RTX A6000、相同自動混合精度量測；基礎 U-Net、NAFNet 與 EDSR 使用正式的重疊分塊推論，MOSR 使用正式的整張影像推論，因此數字代表實際部署路徑，而不是只比較單一網路層的理論速度。

| Method | Parameters (M) | Full-frame median (ms) | Peak GPU memory (MB) | Throughput (MP/s) |
|---|---|---|---|---|
| Base U-Net | 4.011 | 898.2 | 3396.7 | 3.50 |
| NAFNet | 4.182 | 661.8 | 1350.4 | 4.75 |
| EDSR | 4.071 | 3781.5 | 2369.3 | 0.83 |
| MOSR | 4.024 | 408.0 | 5466.5 | 7.71 |

## 對教授意見的實際補強程度

- 「形貌與量測目標過度專一」：已由單一 pillar 擴充到暗圓柱、亮孔洞與線條三種形貌，其中 pillar 與 via 均有 SEM CD，line 有位移與銳利度。這提供了跨亮暗極性與非圓形邊界的實驗證據，但仍屬同平台、同一樣品的形貌轉移。
- 「缺少現代深度學習比較」：已加入 Compact NAFNet 與 EDSR-x1。兩者重新使用相同資料與相同輸出尺寸由頭訓練，且參數量與基礎 U-Net、MOSR 接近，因此屬容量受控的架構比較。這已補上兩個代表性架構，但不宣稱已完成所有大型方法的全面排行。
- 「缺少計算效能」：已補上模型大小、256×256 延遲、完整 2048×1536 影像延遲、吞吐量與峰值 GPU 記憶體。
- 「PSF 漂移」：依本次範圍未做。
- 「不確定度」：留待後續，不在本次結果中擴張結論。

## 圖表使用建議

正文優先放：20× via CD 上下界、50× 三形貌邊界寬度、pillar/via 位移穩定性、line 位移、完整影像速度。各方法的原生灰階單張影像可放在對應結果前後；基礎 U-Net 的極端高對比與 MOSR 的 via 振鈴應保留，並用數值解釋其取捨。
