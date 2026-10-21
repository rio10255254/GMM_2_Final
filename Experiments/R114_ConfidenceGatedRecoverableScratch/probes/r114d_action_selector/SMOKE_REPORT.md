# R114D readiness report

The isolated selector probe is implemented and ready for an explicitly
launched short experiment.  No long probe has been started.

## Locked source

- proposal: R114C epoch 24
- checkpoint SHA-256:
  `909439fad61df63da628db33ed2f93974c2fdc2b18ac11da98d3058bb595e311`
- frozen proposal parameters: 681,183
- trainable proposal parameters: 0
- new selector parameters: 54,319

## Verified contracts

- initial acceptance: exact zero
- initial amount: exact zero
- initial selected action: exact zero
- initial output: bit-exact geometry base
- inference gate: exact
  `boundary * need * recoverability * acceptance * amount`
- E24 profile proposal and 48-gray bound preserved
- proposal receives no gradient and its state hash is unchanged after optimizer
  steps
- inference has no target argument
- selector has no global pooling, spatial normalization, FFT, or free residual
- all normal supervision is inside the true SDF band; the only permitted
  outside-band support is capped high-risk identity hard negatives
- full R114 plus R114D test suite: 44 passed

## Smoke results

- CPU model/gradient smoke: pass
- GPU model/gradient smoke: pass
- CPU one-step real-dataset trainer smoke: pass
- GPU one-step real-dataset trainer smoke: pass
- active-selector stitched output max difference: `5.66e-6`
- active full safety-gate max difference: `1.84e-5`
- largest diagnostic-only difference: `4.34e-4` in the sharply thresholded
  profile-band map; it changes the deployed image by only `5.66e-6`

The complete machine-readable smoke outputs are in `smoke_results`.  One-step
trainer evidence is in `runs/cpu_trainer_smoke_v2_20260831` and
`runs/gpu_trainer_smoke_v2_20260831`.

## Explicit short-probe launch

From the R114 project directory:

```powershell
& .\probes\r114d_action_selector\run_short_probe.ps1
```

The script defaults to six epochs over a stratified 2,048-scene subset.  Set
`-Limit 0` only when intentionally using the entire training set.
