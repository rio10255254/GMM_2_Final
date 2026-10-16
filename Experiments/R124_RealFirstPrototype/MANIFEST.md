# R124 identity and scope

- Run ID: `r124_prototype_20260908`.
- Profile: self-contained prototype implementation.
- Branch: `codex/r124-real-first-prototype`.
- Design source: immutable R123 architecture/data/validation reports; prior sources not rewritten.
- Implementation: 301,212 trainable parameters, shared four-step local 2D prior, explicit fixed observation gradients, logged intensity projection, image-independent geometry diagnostics.
- Training status: untrained; all tests perform zero optimizer updates. Artificial nonzero weights in stress tests are unsaved test models, not learned checkpoints.
- Checkpoints: `results/cli_initial/initialization.pth` and reloaded copy are explicitly untrained initializations; no production or thesis-model status.
- Observation qualifications: arithmetic identity and assumed Gaussian profiles only. No independent instrument admission exists; metadata cannot make a profile qualified.
- Verification: unit behavior, explicit adjoint/gradient, full-size paired backward, tile support, real smoke output, SEM-linked readout adapter. See `reports/R124_RESULTS.md` and `results/final_verification.json` for exact completed scope.
- No sealed confirmation image access, no old expected hash updates, no teacher or SEM input to reconstruction.
- Retention: keep the full small prototype within2GiB on D, no original raw duplication or deletion.
