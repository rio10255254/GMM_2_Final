# 主線起點至R38：正式基準的形成

[全部分區](../EXPERIMENTS.md) · [研究沿革](../lineage/README.md) · [目前保存狀態](../STATUS.md)

光學檢查、R32失敗與R33至COMBO；R34／35／37另由歷史分支取得。

以下是閱讀順序，不表示相鄰兩輪必然繼承同一模型或資料。原正式報告優先於卡片的早期摘要。

| 實驗 | 研究問題 | 判讀與限制 |
|---|---|---|
| [main/R26NewPSFCheck](../experiments/main__R26NewPSFCheck.md) | 新PSF重訓、正式光學流程與交付版本的關係 | 新舊PSF政策與各次審查分開保留；早期首頁的等待狀態不能代表全部子研究 |
| [main/R32Sandbox](../experiments/main__R32Sandbox.md) | 加入真實影像訓練是否改善R30 | 內部檢查通過但外部0.8px大幅退步；保留未採用結論 |
| [main/R33ContrastFix](../experiments/main__R33ContrastFix.md) | 提高統計項能否修復R33的灰階與銳利度 | 目標本身變化小，增加權重未恢復細節；負結果需保留 |
| [main/R33RobustLoss](../experiments/main__R33RobustLoss.md) | 減少極端像素牽引是否改善位移穩定 | p95為已核准替代；保留穩定性收益及銳利度代價，連同R34／R35／R37失敗支線 |
| [main/R38SeqConsistency](../experiments/main__R38SeqConsistency.md) | 直接學習連續影像的一致性 | 全尺度序列受到弱訊號干擾；這是R38v2修復的前因 |
| [main/R38v2SeqFixed](../experiments/main__R38v2SeqFixed.md) | 只保留有足夠訊號的序列訓練並結合R33 | R38v2是視覺替代；COMBO是正式基準，兩個身分不能混用 |
