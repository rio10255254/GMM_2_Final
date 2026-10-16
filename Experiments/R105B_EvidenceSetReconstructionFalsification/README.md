# R105B Evidence-Set Reconstruction Falsification

This is a short mechanism experiment, not a production model.

It tests a variable-observation reconstruction core. The same evidence-set weights are evaluated with one observation and with four observations of the same latent scene. The four observations contain different subpixel sampling, blur, exposure, illumination and noise, then are aligned into one coordinate system.

The matched point arm has the same architecture and parameter count, but is trained to collapse its four candidate heads into one single-frame answer. The evidence arm is trained with one, two and four observations and keeps multiple locally plausible candidates. Candidate confidence comes from a local forward-imaging consistency check rather than an unconstrained confidence scalar.

Training uses only procedural shapes. Real SEM, HS100MG and external GMF images are validation-only and are not part of this mechanism probe.

Run:

    C:\Users\Rio\anaconda3\python.exe scripts\run_probe.py

## Final status

The mechanism probe is complete. On held-out procedural topologies, one, two and four observations produced monotonic contour improvements. Diverse observations beat repeated-frame and simple-average controls. A structural compatibility check and observation-jackknife uncertainty safely rejected intentionally mismatched bundles; candidate-head disagreement alone did not.

The direction is eligible for a larger real-image engineering experiment, but this small probe is not a formal model and is not a delivery candidate. It still assumes aligned observations and known synthetic nuisance parameters.

See `reports/R105B_FINAL_FINDINGS_ZH.md` for the complete Chinese interpretation.
