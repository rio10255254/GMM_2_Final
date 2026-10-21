# Same-run interruption recovery validation — 2026-08-13

The recovery path was exercised in a disposable three-epoch sandbox copied from the finalized R97 source.

- The first trainer was forcibly terminated immediately after epoch 1 was committed.
- The latest checkpoint remained at epoch 1 and the formal registry remained a single active run.
- `--continue-formal` restored the same model, EMA, optimizer, update count, run id, and original initialization hash.
- The continued process completed epochs 2 and 3.
- The final training log contained exactly three unique rows: `1,2,3`.
- Registry status was `complete`, completed epoch was `3`, and resume count was `1`.
- The final checkpoint epoch was `3`, optimizer update count was `3`, and the initialization hash remained `9f3ab320f389d867fabc94dd8dba78439e7b0bd6d1b9c1bf039bc7ea16d81f66`.
- No failure file was produced during continuation.

This validates recovery only within the same formal run. It does not authorize importing a checkpoint from R61, R96, or another R97 run.

After the evidence above was recorded, the 153 MiB disposable sandbox was sent to the Windows Recycle Bin. No sandbox files remain in the Experiments folder.
