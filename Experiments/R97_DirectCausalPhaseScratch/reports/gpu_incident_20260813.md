# GPU incident record — 2026-08-13

This record is part of the R97 execution boundary.

- At approximately 19:29, the 512-pixel acceleration candidate with scene batch 8 reached 100% GPU load and 48,488 MiB used, leaving only 84 MiB free.
- Windows recorded an unexpected restart and bugcheck `0x00000116` (`VIDEO_TDR_FAILURE`). The third bugcheck argument was `0xC000009A`, indicating insufficient resources in the display-driver timeout path.
- After the crash reboot, `TrustedInstaller.exe` initiated two planned operating-system update restarts and Windows installed KB5121003 and KB5120708. Those later restarts were updates; the first restart was not.
- No R97 formal registry existed. Only a disposable smoke checkpoint had been written, so no formal training progress was lost.

Permanent controls:

1. Patch 512 scene batch 8 is forbidden.
2. Acceleration candidates are terminated below 6 GiB free VRAM or after 120 seconds.
3. Formal training remains unauthorized until the guarded speed benchmark and final preflight both pass.
4. A low-memory event reduces only the current stage batch; it does not abandon the experiment.

Post-incident validation:

- The guarded benchmark selected scene batches 4, 2, and 1 for patch sizes 512, 768, and 896.
- The 768-pixel batch-3 candidate was terminated safely at 4,321 MiB free without a system crash.
- Every selected candidate had finite forward loss and finite gradients.
- A separate flat-region square-root gradient defect exposed by the benchmark was corrected and covered by regression tests.
- A forced interruption after epoch 1 was resumed as the same run and completed epochs 2 and 3 without duplicate log rows.
