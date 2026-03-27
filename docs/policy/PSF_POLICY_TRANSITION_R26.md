# R26 PSF 政策切換說明

日期：2026-03-27

## 政策結論

自本次切換起，`R26` 研究與封包的**目前標準（current standard）**改為使用新的、物理上較合理的 PSF 擬合結果；舊 PSF 不再作為正式預設，但必須保留為**legacy empirical baseline**。

這個切換不是單純把 `.mat` 檔換掉。  
因為 `R26` package 預設推論會吃 checkpoint 內的 PSF buffer，所以若要讓 package 正式代表新的物理標準，就必須同時 promote：

- 新的正式 PSF
- 在相同 `r26_sm035` recipe 下得到的 replacement checkpoint

## 為什麼可以切換

目前已確認：

- 新 PSF 的差異主要是對齊語意，而不是明顯變寬。
- 先前那次「新 PSF 重訓版崩壞」不是純 PSF 因子，而是 `PSF 變更 + recipe drift` 共同造成。
- 在 `pure_psf_control` 的 same-recipe 對照下，`old_recipe + new_psf` 至少到 `epoch 40` 沒有重現先前那種明顯崩壞。

因此，若研究原則是 physics-first，而不是 purely performance-first，則新的 PSF 應成為目前標準。

## 切換後的語意

- `current standard`
  - 代表目前研究採用、物理上較合理的標準 PSF 與相應 formal checkpoint
- `legacy empirical baseline`
  - 代表歷史上曾取得較好經驗數值、但物理合理性較弱的舊 PSF 線

## 保留舊 baseline 的原因

舊 PSF 不應刪除，原因如下：

- 歷史報告、舊 compare 與封包演進仍需引用它
- 後續若要解釋差異，必須能回到 legacy baseline 對照
- 若新 PSF 後續在下游流程仍需再校準，legacy baseline 是必要對照，不是雜訊

## 目前可安全採用的說法

- 新 PSF 是目前研究上較合理的物理標準
- 舊 PSF 轉為 legacy empirical baseline
- slight regression 若未構成 clear breakage，可視為政策切換成本，而不是自動回退理由

## 不應誤寫的說法

- 不應再把舊 PSF 寫成唯一正式標準
- 不應寫成新 PSF 已經證明在所有 downstream 指標都更好
- 不應把舊 baseline 直接刪除或視為錯誤資料

## 對 package 的要求

切換完成後，package 應改成：

- 預設使用新 PSF
- 預設使用與新 PSF 對應的 same-recipe replacement checkpoint
- 文件明確說明 old/new 的 current-vs-legacy 身份

並且保留一份 legacy baseline manifest，避免之後再次混淆正式標準與歷史 baseline。
