# Formal New-PSF Candidate

這個資料夾承載「以正式 `r26_sm035` recipe 為基底，只更換成 new physically justified PSF」的候選驗證資料。

它不是 generic sandbox。  
它的責任只有兩件事：

1. 在不混入 recipe drift 的前提下，測試 package 是否可切到新 PSF
2. 形成 current standard promotion 的 provenance

## 內容

- `candidate_manifest.json`
  - current/legacy hash、來源路徑與 clone/promote 記錄
- `package_clone/`
  - 用來做 candidate smoke 驗證的封包副本
- `reports/NEW_PSF_FORMAL_R26_COMPARE.md`
  - new-vs-legacy 的 promotion compare 摘要

## 判準

這裡的判準不是「一定要全面超越 legacy baseline」。  
它只需要回答：

- new PSF package 是否可正常使用
- same-recipe candidate 是否沒有 clear breakage
- 是否足以被 promote 成 current standard
