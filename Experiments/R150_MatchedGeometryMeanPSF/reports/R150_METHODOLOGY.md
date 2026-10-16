# R150 Methodology

R150 is the formal follow-up selected after R149's local-boundary arm failed its fixed gate. It retains only interventions supported independently by the R148v2 diagnosis: real-scale procedural circle geometry and identical mean-PSF handling in training and inference.

The architecture, global boundary objective, optimizer, 8,192-update schedule, FP32 determinism, source-referenced residual output, shifts, photometry, noise and fixed real evaluation are unchanged from R148v2. Individual measured kernels still create optical diversity in the blurred inputs; the network is not told an unavailable per-frame kernel identity.

Success is determined separately for short-step displacement, long-distance displacement, diameter repeatability, contour repeatability, same-sample SEM difference, worst-case behavior and runtime. The model is not promoted by training completion or one aggregate score.
