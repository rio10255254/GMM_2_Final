# R95 data policy

No formal array payload is created or copied during architecture design.

The locked source is the audited R93 procedural package with content
fingerprint `6494719ad21665723ba32cdcb3871a40691753ca03791f181416349f02fd31a5`.
R95 reads these arrays in place. Only compact replay metadata, R95 logs and R95
checkpoints belong under this experiment folder, so the approximately 27 GB
source payload is not duplicated.

The loader assembles same-scene clear T, noise-free B and noisy S views and
uses recorded seeds to replay hidden P and O stages on demand. No unaffected
array is regenerated. Any future source repair is outside R95 scope and would
require a new upstream audit and content fingerprint.

Real 5x, 20x, 50x, HS100MG and SEM imagery remains validation-only and is never
used as a training input, label, pseudo-label, geometry hint or teacher output.

`live_validation` contains four fixed preview copies only. They are never read
by the optimizer and are used solely for scheduled 5x/20x/50x visual checks.

