# R108E Contour-Conserving Profile Renderer Microprobe

R108E is a bounded scratch experiment prompted by the locked failure of R108D.
It does not ask a sharpening loss to discover contour geometry indirectly.
Instead it predicts a boundary band, reconstructs only near that band, and is
directly supervised on soft contour overlap, area, centroid, edge profile, and
identity preservation.

The training inputs are newly generated generic shapes with low contrast,
uneven illumination, asymmetric blur/halo, local boundary fade, and mixed
degradation. Real microscope, SEM, R73, and R74 pixels are evaluation-only.

