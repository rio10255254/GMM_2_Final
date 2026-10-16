# R108C Independent Optical Specialists Microprobe

R108C tests four isolated specialists before any combined image model is
allowed: edge profile, source-phase texture, paired-noise denoising, and
zero-mean illumination.  Every specialist starts from random initialization
and receives a direct action target.  Existing R108B procedural targets are
used by verified read-only reference; no R108B weight, real image, teacher, or
pseudo-label enters training.

Combination is conditional.  If any specialist suppresses its own action or
fails its isolated held-out task, the script records the failure and does not
train or validate a combined candidate.

