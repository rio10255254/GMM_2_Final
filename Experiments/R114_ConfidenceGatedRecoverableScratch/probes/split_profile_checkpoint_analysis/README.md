# Fixed-stage checkpoint audit

This folder contains a read-only audit for the R114B split-profile probe.  It
compares only the design epochs E12, E20, E24 and E28.  If training has not
reached an epoch, that epoch is reported as pending and skipped.  The audit
never replaces it with the newest checkpoint and never chooses a delivery
model.

Example:

```powershell
C:\Users\Rio\anaconda3\python.exe .\probes\split_profile_checkpoint_analysis\analyze.py `
  --run-dir .\runs\r114b_split_profile_probe_scratch_20260830
```

Derived JSON, Markdown and CSV are written under
`results/checkpoint_stage_analysis/<run-id>`, outside the active run folder.
Use `--no-write` for a completely non-writing smoke check.
