# R50 PSF Control Diagnosis

R50 checks whether the Lab-system BADS PSF is too strong for the real
checkboard-corner task.

This is a diagnostic experiment, not a model-training round. It compares the
real `20250605_checkboard` edge appearance against four synthetic blur controls:
clean, Gaussian, weakened BADS, and formal BADS.

## Completion Criteria

- Measure the real Lab checkboard edge-width proxy.
- Measure the matching synthetic checkboard-corner controls.
- Generate weakened-BADS controls for direct comparison.
- Compare the selected BADS PSF against the Gaussian validation model.
- Record a clear verdict before starting another long Lab training run.

## Verdict

The selected BADS PSF is usable, but it is too strong to be the only blur truth
for Lab checkboard-corner training. The real checkboard edge-width proxy is
`7.0 px`; formal BADS is `11.0 px`; weakened BADS at alpha `0.50` is `7.0 px`;
Gaussian is `9.0 px` and gives the best combined width/edge-strength compromise.

Next Lab training should compare Gaussian, weakened-BADS, and mixed-PSF data in
a small probe before committing to another long run.

