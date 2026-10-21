# R114E decoupled hybrid causal probe

Status: implementation and pre-training evidence complete. A short selector
probe is authorized by the fixed-128 headroom gate, but no multi-epoch short
probe and no long/formal training have been launched.

The model always uses sealed R114C E20 for geometry/controller/base and sealed
R114C E24 only for its renderer backbone plus four profile heads. A new local
selector decides whether and how much of the E24 profile proposal to apply.

## Verified evidence

- Fixed 128 validation records: selector-zero output is exactly E20, maximum
  absolute difference 0.
- Learned hybrid direction is useful on 35.48% of actionable boundary pixels.
- Pixelwise oracle-best boundary squared-error gain is 9.93 gray-level squared.
- 97% of non-identity scenes have positive oracle headroom.
- All five frozen thresholds passed. This is an upper-bound direction test,
  not evidence that the untrained selector already realizes the gain.
- Eight unit/adapter tests passed.
- GPU contract smoke passed; E20/E24 had no gradients and unchanged hashes.
- One-step trainer smoke completed with only the selector in the optimizer.
- Read-only evaluator smoke completed.
- Locked R73 and R74 preparation smoke reconstructed all required smoke inputs
  and preserved both locked ACM scripts/contracts.

## Explicit short-probe launch

From the R114 project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\probes\r114e_decoupled_hybrid\run_short_probe.ps1 `
  -RunId r114e_selector_short_probe_20260831 `
  -Epochs 6 -BatchSize 8 -Workers 4 -Limit 2048 -Device cuda
```

This command launches only the isolated six-epoch selector probe. It cannot
update either sealed source model. It does not launch a long/formal run.

After a short run, evaluate each checkpoint with:

```powershell
C:\Users\Rio\anaconda3\python.exe -m probes.r114e_decoupled_hybrid.evaluate `
  --checkpoint <selector-checkpoint> --output <fresh-output-folder> `
  --device cuda:0 --limit 128 --batch-size 8 --workers 4
```

The unchanged locked R73/R74 pipeline is available through:

```powershell
C:\Users\Rio\anaconda3\python.exe -m probes.r114e_decoupled_hybrid.run_locked_acm `
  --checkpoint <selector-checkpoint> --output <fresh-output-folder> `
  --method-name R114EHybrid --suite R73 R74 --device cuda:0
```

