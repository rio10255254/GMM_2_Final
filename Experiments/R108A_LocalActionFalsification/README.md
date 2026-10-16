# R108A Local-Action Falsification

R108A is an evidence-gathering experiment, not a formal model round.  It tests
three questions before any full R108 scratch training is authorized:

1. Are the existing Raw/R61/R79/R103/R104 results complementary on the same
   truth-backed images, and is the winning behavior predictable from Raw alone?
2. Can a local, phase-safe optical action library improve boundaries without
   relying on a free image residual or a global shape renderer?
3. If the first two mechanisms work, can a short selector learn the oracle
   action without collapsing to identity?

All existing experiment folders are read-only inputs.  R108A writes only below
this folder.  Existing checkpoints are diagnostic probes only and are never
loaded into an R108 model or used as training teachers.

