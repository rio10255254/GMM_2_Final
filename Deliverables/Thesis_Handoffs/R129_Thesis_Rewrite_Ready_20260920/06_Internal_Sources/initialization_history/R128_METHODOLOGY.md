# R128 — 完整訓練前固定的方法

使用者已授權補齊必要前置並開始完整訓練。本輪把可實作的研究訓練與最後的物理精度認證分開；不再以欠缺独立儀器位置讀數作為研究訓練的阻礙。

## Architecture decision

The new model is a source-only four-step shared recurrent image restorer. Its input is the observed image only; it does not receive the true simulation PSF, noise, geometry, motion, scene identity, SEM data or answers. Seven internal feature maps are all derived from the image/current reconstruction. The4xstate/2xlearned grid retains R125's tested representation capacity, while removing the unqualified optical feedback at deployment. No geometry/confidence output is advertised without a completed training/calibration design.

Both arms have exactly the same architecture and initialization within each seed. ArmI uses native-image,4xlatent, image-gradient and paired-reference-residual supervision. ArmP adds true-simulator consistency only after forward. True rendering information is legitimate supervision, not a privileged model input. This single training-objective difference is the declared comparison.

## Data and information boundary

New independently seeded parents are assigned to train/dev/final-generated-test before augmentation. There are512/128/128parents; old real images, old SEM outlines and old teacher/checkpoints are never read by generation or training. Geometry, photometry, texture/illumination, blur and motion/noise are controlled separately. Flat controls are not counted as evidence of unseen geometry.

The new source-only model has a smaller finite dependency region than R125's optical-correction model. New384native-pixel fields retain128pixels of actual context around the128core; this must be verified by full-context/cropped forward and gradient comparisons. Existing640data are not resized or padded to fake context. Independent8xFloat64 formation provides4xlatent/native references. Pair formation remains continuous shift, fixed within-pair optics, sensor integration, independent noise and quantization. Fresh training noise is drawn deterministically per presentation, identically across arms/seeds.

Actual data-fit, saturation, category content, parent/source isolation and minimum required context are checked before training. Every generated attempt is retained. A failed representation check triggers a separately recorded correction, never silent parent replacement, new expected hashes or relaxed conditions to obtain a green result.

## Training strategy

Two arms times two fresh starts,8192updates each:32768planned optimizer updates. Each run sees the512training parents16times in deterministic per-epoch permutations. AdamW uses128update linear warmup, peak0.001then cosine decay to0.00001, weight decay0.00001and gradient clipping5. Settings are frozen before full training. Intermediate checkpoints are diagnostics; final8192is the primary comparison. No automatic extension or best-step selection.

Development runs only on the128held-out development parents. The final generated test is first evaluated by learned models at the fixed final step, after all corresponding training decisions are frozen; data integrity/formation checks do not make it a new real confirmation set. Real checks remain primary evidence of practical behavior, with source-scope limitations visible. SEM sizes are compared under fixed operational definitions, not claimed as certified physical material boundaries.

## Readiness and execution

Before the coordinator is allowed to launch training: source protection, complete manifests/splits, data formation/admission, operator and gradient correctness, identity/translation/context behavior, learning smoke test, actual GPU backward, checkpoint save/reload and resume behavior, and real evaluator integration must pass. Failures and fixes are retained. Training records actual input hashes, parent identity, noise seed, losses, parameter updates, checkpoints and scheduled evaluations. A running process or a receipt alone cannot establish scientific completion.

## Frozen implementation details before full training

Training uses the actual native320crop32:352 of each generated384field, with the central128core at96:224. The source-only dependency halo is64; the additional true-PSF supervision radius is at most16. Full384 versus cropped320 was tested using a nonneutral network for core output, complete objective and every parameter gradient. Saturated sensor bins use tail probabilities at0.5/254.5gray; interior bins use a Gaussian approximation with quantization variance1/12gray-squared and the predeclared0.5gray noise floor.

All four runs use deterministic algorithms, strictFP32 withTF32off, and the same fresh per-epoch sensor-noise realizations. The first nondeterministic resume attempt remains recorded; the fixed-translation implementation and deterministic runtime are validated by exact next-update equality after checkpoint restoration. Checkpoints are saved every128updates in addition to all scheduled evaluation steps.

Real application output retains Raw through global boundary distance64 and blends over the next16pixels, once per complete image. Unguarded neural outputs are saved separately. SEM sampling uses source/SEM-only fixed ray populations; candidate-invalid fixed rays yield unmeasurable objects instead of candidate-dependent exclusion. All36objects/exposure are reported with a predeclared context stratum. The30/50/70percent profile definitions are reported together. Motion uses the same80pixel global-border exclusion for Raw and candidate, with uncropped full-field readouts retained separately. These definitions are fixed before any full-training candidate output.
