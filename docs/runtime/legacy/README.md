# Legacy Runtime References

這裡保存的是**已追蹤**的 legacy root runtime / status curated copies。

## Purpose

- 保留歷史上曾放在 repo root 的 `000_LONGRUN_*_STATUS.*` 可追溯副本
- 讓 GitHub 上仍可看到重要 legacy bridge
- 同時把 root 從 status 檔噪音中清出來

## Important Rule

這些檔案不是當前 canonical runtime surface。

現在真正的 process-level runtime truth 應優先看：

- `Experiments/R32Sandbox/runtime/R32_STATUS.md`

如果舊腳本在 repo root 再生成：

- `000_LONGRUN_*_STATUS.md`
- `000_LONGRUN_*_STATUS.json`
- `000_LONGRUN_*_RUNNING.txt`

那些都視為**本地 runtime 輸出**，不再進 Git。Git-tracked curated copies 在 `root_status/`。
