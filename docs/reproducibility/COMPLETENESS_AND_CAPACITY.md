# 保存完整度與容量

[目前完整度與缺件](STATUS.md) · [按用途取得資料](ASSET_GUIDE.md) · [歷次保存](project_completion/README.md)

## 目前完整度

主要研究閱讀與結果已有入口，必要來源仍逐輪補查；不能說全專案已確認無遺漏。已完成的補件與仍未解的影響統一見[目前狀態](STATUS.md)，本頁不再重複疊放舊的待補清單。

## 最近一次容量紀錄

核對範圍：早期共用環形來源補件完成後；實際取回範圍見[交付收據](../../Shared_Sources/Baseline_Ring_Inputs/DELIVERY_VERIFIED.json)。

| 類型 | 當次用量 | 怎麼讀 |
|---|---:|---|
| 正式版本附件 | 27個版本、253個附件，共142,964,380,401 bytes，約142.96GB | 不等於一般程式倉庫大小；只需按用途取回 |
| 未發布草稿 | 0個 | 六份舊超量草稿已處理，舊收據中的draft不是現在待辦 |
| 程式倉庫與歷史 | 較早API快照約1.66GB | 是較早概略值，不冒充本次重新測量，也不拿它推算剩餘配額 |

附件數與容量依[最新來源交付收據](../../Shared_Sources/Baseline_Ring_Inputs/DELIVERY_VERIFIED.json)；較早倉庫數字見[原容量快照](project_completion/curated/GITHUB_CAPACITY_SNAPSHOT_20261022.json)。使用者已明確同意這次約234MB早期固定配對補件；其餘可生成大資料仍不整套上傳。

## 如何決定是否繼續放

依來源是否不可替代、實驗是否需要及是否已有相同內容決定，不以把空間放滿為目標。原拍、人工與儀器紀錄、關鍵模型、完整量測值得保存；可生成的大訓練庫與整批模型輸出優先留生成方法、設定及必要來源。

GitHub的程式倉庫限制與發布附件規則分開；沒有由以上用量得出一個保證的「還剩XGB」。需要新增大附件時，依當時[大型檔案說明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)、[倉庫限制](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)與[發布版本規則](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)核對。

## 舊紀錄如何保留

[整理前本頁的固定版本](https://github.com/rio10255254/GMM_2_Final/blob/c1102e92c9eb48f322196f7aac34908de53ea0fe/docs/reproducibility/COMPLETENESS_AND_CAPACITY.md)保留各批當時數字、曾經缺件與補件時間；不能把較早「尚未上傳」當作現在狀態，也不能把後來成功回填成早先已完成。
