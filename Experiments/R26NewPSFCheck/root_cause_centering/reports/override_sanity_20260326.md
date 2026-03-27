# Post-load PSF Override Sanity

這份檢查的目的不是找最佳效果，而是證明 post-load buffer override 真的有改變輸出。

## No-override hashes

```json
{
  "old_ckpt_oldpsf_no_override": "636866bb6639e06051b1ae67a81b09f290974d363673623b946cd1dbebe80fd9",
  "old_ckpt_newpsf_no_override": "636866bb6639e06051b1ae67a81b09f290974d363673623b946cd1dbebe80fd9",
  "new_ckpt_oldpsf_no_override": "63a5771814d8e48cdb28adae3e245e098d191f1a805afbbcc4b5daa61a6c497b",
  "new_ckpt_newpsf_no_override": "63a5771814d8e48cdb28adae3e245e098d191f1a805afbbcc4b5daa61a6c497b"
}
```

## Override pairwise diffs

| pair | equal_hash | mae | rmse |
| --- | --- | --- | --- |
| old_ckpt_oldpsf_override vs old_ckpt_newpsf_override | False | 0.0018 | 0.0420 |
| new_ckpt_oldpsf_override vs new_ckpt_newpsf_override | False | 0.0044 | 0.0666 |

若同一 checkpoint 在 old/new PSF override 下不再同 hash、且出現明顯 MAE/RMSE，表示 override 工具有效。