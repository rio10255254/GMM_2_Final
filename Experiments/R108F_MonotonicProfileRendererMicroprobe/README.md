# R108F Monotonic Profile Renderer Microprobe

R108F is an independent scratch-weight causal experiment. It keeps R108E's
successful staged boundary/necessity concept but replaces the unconstrained
pixel renderer that produced dark rings.

The renderer may only (1) shift the existing image locally and smoothly and
(2) apply a positive mixture of four local optical scales. Its proposal is
clamped to the observed local intensity range, so it cannot create a darker
or brighter overshoot than the nearby source. Detector and renderer are
trained sequentially from random initialization.

The verified R108E procedural dataset is reused byte-for-byte. No R108E model
weight, real microscope pixel, SEM pixel, teacher output, or pseudo-label is
used in training.

