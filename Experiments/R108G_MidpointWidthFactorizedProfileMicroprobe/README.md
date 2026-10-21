# R108G Midpoint-Width Factorized Profile Microprobe

R108G is an independent scratch-weight experiment derived from the SEM signed-
profile diagnosis. It factorizes edge restoration into two operations:

1. a scalar displacement strictly along the observed edge normal, and
2. a monotonic local contrast curve that narrows edge width while preserving
   its midpoint and never exceeding the observed local intensity range.

Boundary/necessity detection is trained first and frozen. The renderer is then
trained separately. The verified procedural R108E dataset is reused by hash;
no old weight, real microscope pixel, SEM pixel, teacher, or pseudo-label is
used for training.

