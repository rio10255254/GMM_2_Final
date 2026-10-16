# main/R101_HighFrequencyDesignValidation 研究與重做紀錄

檢查高頻答案、邊界輸出與多目標學習為何失效

125場景500觀測的前測發現細頻答案多不相位一致，E8後實拍細節崩落且學習方向互相衝突；這是根因設計，沒有新R101模型

## 必要來源

R93鎖定內測來源、E1到E40模型與四張實拍、各頻帶與更新方向完整讀值

## 影像保存理由

高頻答案不一致、E8轉折與合成指標和實拍相反的比較

## 原始方法與結果

下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。

- [MANIFEST.md](../../../Experiments/R101_HighFrequencyDesignValidation/MANIFEST.md)
- [R101_DESIGN.md](../../../Experiments/R101_HighFrequencyDesignValidation/R101_DESIGN.md)
- [README.md](../../../Experiments/R101_HighFrequencyDesignValidation/README.md)

## 重做與驗證範圍

程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。
本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。
任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。
