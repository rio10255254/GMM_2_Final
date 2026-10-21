# R74 Hard Microscopy ACM Generalization

R74 is the follow-up to the R73 ceiling-effect diagnosis. It contains 100 new images across five difficult acquisition regimes: very low contrast, uneven illumination, asymmetric blur and halo, locally missing boundary contrast, and mixed hard degradation. Five exact shape families are balanced within every regime.

The dataset is calibrated and frozen using Raw images and exact geometry only. R61 outputs are not generated until the Raw difficulty gate passes. Exact generator masks remain the primary truth, and the same truth-independent ACM initialization is used for Raw and R61.

## Run

```powershell
& 'C:\Users\Rio\anaconda3\python.exe' scripts\run_r74.py --stage all
```

Use `--force-generate` only before the Raw difficulty profile is frozen. After R61 reconstruction exists, the runner refuses forced regeneration.
