# R89 Lock Timeline

- Two pre-formal data attempts were rejected before training: one exposed a
  Windows progress-file reader lock, and one exposed target-shaped pixelwise
  clipping leakage. Both payloads were moved intact under failure evidence and
  are not reused.
- The final data generator replaces pixelwise repair with one image-wide
  degradation scale and a tightly limited outlier clip.
- 00:57:38: the final model, trainer, inference, data generator, design, gates,
  authorization, and optical-statistics summary were frozen after 17 tests,
  the learnability check, and all GPU/tile checks passed.
- The clean formal and holdout generators start only after this final lock.
- Formal training starts only after both final packages pass full hash and
  source-isolation audits. No formal run was registered before that point.

The final generator hash is
`63c406724349295bbaa0a15c0c5001a7ced43e5a8eff701a3ebe927aeb1db3e7`.
The final model hash is
`b3f6f22563cb49c227143aba2376d7b35a14f78d8f12a618a0c19db4592ff8cc`.

