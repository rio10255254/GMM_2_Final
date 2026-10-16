# R97 Direct Causal Phase Scratch

R97 is a clean, independent experiment built after the R96 internal and external-GMF diagnosis. It keeps the reliable local/tiled backbone but removes the learned amplitude gates that suppressed useful corrections.

## What is different

- Each causal branch predicts the correction actually applied to the output.
- No R96/R61/V42 checkpoint, teacher or pseudo-label can be loaded.
- The same procedural scene supplies noisy, noise-free and clear counterexamples in every update.
- Texture enhancement is tied to symmetric bands already visible in the source.
- A generic on-demand periodic panel teaches the correct location to beat adjacent-repeat matches.
- Full/tiled inference remains the canonical reconstruction path.

## Data boundary

The hash-locked 5,000-observation R93 procedural package is reused without regenerating or duplicating its arrays. Labels were produced at 8x resolution and reduced with anti-aliasing. Additional periodic scenes are generated in memory from analytic primitives only. Real microscopy, SEM and HS100MG images are not training pixels.

## Safe workflow

1. Run `scripts/run_preflight.py`. It executes unit tests and a real GPU smoke update.
2. Inspect `reports/preflight_report.json`. Formal training is authorized only when every check passes.
3. Start the sole 48-epoch scratch run with `scripts/start_formal_training.ps1`.
4. Open `Open_Training_Monitor.cmd` for the compact dynamic monitor.

The formal launcher refuses to run before preflight and refuses a second formal run in this folder.
