# R113 Next Probe: Minimal Renderer Extension

This is a matched, from-scratch microprobe.  It asks one narrow question:

> Does a tile-safe, bounded, zero-local-mean detail/geometry path fix the
> hard known-truth cases that width-plus-normal-shift cannot express?

## Arms

- `width_shift`: current R109 renderer.  Its dormant detail head is computed
  but multiplied by zero so both arms have identical parameters and nearly
  identical compute.
- `bounded_detail`: the same model with a maximum 18/255 local high-pass
  correction.  No global pooling, FFT, real labels, SEM labels, teacher, or
  inherited checkpoint is allowed.
- `bounded_detail_supervised`: the identical bounded arm, trained from the same
  scratch seed with staged direct supervision toward the representable residual
  left after the width-plus-shift base output.

The R113 oracle result did not justify a coherent low-resolution-control arm:
its worst contour error was 9.17 px versus 3.24 px for dense controls.  A third
low-resolution arm is therefore deliberately excluded.  The final supervised
arm exists only because the first formal bounded branch remained underused.

## Fairness contract

- Same scratch seed, initialization, selected records, degradation sequence,
  batches, number of steps, losses, and evaluation for both arms.
- The two model instances have identical state dictionaries at initialization.
- Both arms use the same 1,024 synthetic training scenes and 128 synthetic
  validation scenes from the locked R107A/R109 package.
- Selection is worst-case-first on known contour truth; averages cannot hide a
  thin-ring, crescent, narrow-gap, identity, or tile failure.
- The fixed 24-case R113 paired-condition suite is validation only.
- Formal training is blocked unless `--confirm-formal` is explicitly passed.

## Commands

```powershell
& C:\Users\Rio\anaconda3\python.exe scripts\prepare_selection.py
& C:\Users\Rio\anaconda3\python.exe -m pytest tests -q
& C:\Users\Rio\anaconda3\python.exe scripts\run_probe.py --mode smoke --arm both
& C:\Users\Rio\anaconda3\python.exe scripts\validate_probe.py
```

The original two-arm formal result is complete and preserved in
`results/formal_comparison.json`.  After the supervised scaffold and smoke
checks passed, the parent task received authorization and launched its single
formal run.  The scaffold task did not launch a second run.
