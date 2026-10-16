# R126 learning and readout diagnosis

## Controlled learnability

Four initial128-update runs give native reference MAE3.10051→2.79529(A image),3.10051→2.79557(A full),2.96973→2.78698(B image),2.96973→2.75558(B full). None reaches the pre-fixed20percent learning signal. The image-only B also worsens latent reference error3.82315→3.90204, illustrating why a lower native image error alone is insufficient.

The separately frozen learning-rate intervention leaves architecture, data, initial weights, loss terms, optimizer type, clip and update count unchanged; only1e-4→1e-3. Final A native MAE1.91836(38.13percent decrease),B1.15305(61.17percent decrease); latent errors also decline to2.81794/2.43854. This establishes learnability on this single fixed geometry/noise pair and a causal update-scale effect under these conditions. It does not prove the same rate is universally best, fully explain R125's64-scene result, or establish unseen real performance.

The gradient path is checked numerically, not just for existence. Very small FP32 finite-difference steps1e-4 show about6percent relative disagreement and are retained. A scale sweep gives multiple agreeing scales: at1e-2 relative errors0.000213(A),0.000000204(B), at3e-3 about0.000408/0.001014. This supports cancellation/roundoff sensitivity in the very small-step numerical check, without altering any original result. Most weighted gradients point toward the native objective at initialization; some individual terms disagree, but full vs image-only fixed runs do not implicate destructive objective conflict as the main observed bottleneck.

## Real matching failure anatomy

The untrained, assumed-optics B output already shifts the reported match relative to Raw. The exact OpenCV4.12.0 phase surface and its signed5x5 readout were independently reconstructed on all six original Raw/output pairs, reproducing the positions exactly in the recorded run. The algorithm uses a maximum and a local signed weighted centroid; see the [version-matched primary implementation](https://github.com/opencv/opencv/blob/4.12.0/modules/imgproc/src/phasecorr.cpp).

For20x_1um, the integer maximum changes from(-6,-6) to(-6,-19); the candidate's local signed response is negative. For50x_0p5um it changes from(-8,2) to(-7,-3). Thus the large differences are already present in peak selection. The alternative hypothesis of local centroid extrapolation is **not supported in these initial cases**: all12 centroids remain within their local window. Negative and weak responses remain visible in the primary comparison; no substituted maximum becomes a new success score.

This explains the numerical origin of those large reported jumps. It does not establish whether real physical displacement is preserved, whether the optical assumption is correct, or whether another readout can be treated as independent truth. The failure remains a reliability concern and cannot be erased to admit a candidate.

The trained expanded-photometry seed2 output has a new50x_0p5um jump: Raw(-7.4424,1.5760) vs candidate(29.4884,2.2698), about36.94px apart. The independent surface reproduces it exactly and locates the candidate maximum at(29,2); the centroid still lies within its5x5window. A separate raw horizontal autocorrelation probe has its strongest tested nonlocal response near29px, not37px; this does **not** justify labelling the observed discrepancy as exactly one physical lattice period. No positive-response or alternative-peak reading is substituted as ground truth.

On a known already-correct generated identity image, the broad-data Q models introduce about0.391gray average error in the original-brightness condition, versus0.129for P. Both begin at exact zero for this known identity reference. This is a real counterexample to an automatic "do nothing when already correct" claim: including identity examples in the loss does not enforce exact preservation after learning. Q improves noisy flat examples, so this is a tradeoff requiring a separately designed and tested preservation rule, not a reason to erase either result.
