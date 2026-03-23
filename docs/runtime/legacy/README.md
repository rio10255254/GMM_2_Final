# Legacy Runtime 參考層 / Legacy Runtime References

這裡保存的是 **已追蹤** 的 legacy root runtime / status curated copies。  
This directory stores **tracked** curated copies of legacy root runtime and status files.

## Purpose / 用途

- 保留歷史上曾放在 repo root 的 `000_LONGRUN_*_STATUS.*` 可追溯副本。  
  Preserve traceable copies of `000_LONGRUN_*_STATUS.*` files that historically lived at the repository root.
- 讓 GitHub 上仍可看到重要 legacy bridge。  
  Keep important legacy bridge files visible on GitHub.
- 同時把 root 從 status 檔噪音中清出來。  
  Keep the repository root free of status-file noise.

## Important Rule / 重要規則

這些檔案不是當前 canonical runtime surface。  
These files are not the current canonical runtime surface.

現在真正的 process-level runtime truth 應優先看：  
The real process-level runtime truth should now be read from:

- `Experiments/R32Sandbox/runtime/R32_STATUS.md`

如果舊腳本在 repo root 再生成：  
If older scripts recreate files at the repository root such as:

- `000_LONGRUN_*_STATUS.md`
- `000_LONGRUN_*_STATUS.json`
- `000_LONGRUN_*_RUNNING.txt`

那些都視為 **本地 runtime 輸出**，不再進 Git。Git-tracked curated copies 在 `root_status/`。  
those files should be treated as **local runtime outputs** and should no longer
be committed. The Git-tracked curated copies live under `root_status/`.
