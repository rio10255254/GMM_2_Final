# R113 corrected ring-measurement findings

## What was corrected

R112 first reduced each 5120 x 5120 frame by four and then assigned every
pixel to a floor-rounded radius.  That made the reported peak radius move only
on a coarse grid and could both erase real variation and inflate a one-bin
jump.  Some later interpretations also treated whole-crop texture values as
though they came only from the ring.

R113 keeps the native image resolution, aligns a 1400 x 1400 crop at the
floating-point external coordinate, samples each radius with bilinear polar
interpolation, and solves the half-maximum crossings continuously.  The
dynamic half-maximum annulus and the entire crop now have separately named
texture columns.

The brightest local radial-profile peak is not used as the primary radius.
Several real profiles have two almost equally bright maxima about 3 px apart,
so denser angular sampling can legitimately switch which one is the maximum.
The midpoint of the continuous inner and outer half-maximum crossings is the
primary ring radius; it converges under a denser sampling grid.

## Corrected 100-frame results

| Arm | Primary radius SD (px) | Ring-width SD (px) | Annulus high-frequency median (gray) | Full-crop high-frequency median (gray) |
|---|---:|---:|---:|---:|
| Raw | 0.3977 | 1.3481 | 2.5978 | 2.1156 |
| V42 E120 | 0.0783 | 0.4249 | 1.6199 | 1.0340 |
| R109 E48 | 0.2325 | 0.6201 | 3.6785 | 2.4401 |

The corrected result still places V42 first for radial and width consistency,
R109 second, and Raw third.  However, V42 is not perfectly invariant as R112
appeared to show.  R109 has the greatest high-frequency magnitude on both the
true ring annulus and the full crop; V42 has the least.  This supports the
directional description of V42 as smoother and R109 as more aggressive, but
does not prove whether R109's extra high frequency is true detail or artifact.

## Findings that do not survive correction

R112 reported width-versus-external-score correlations of about -0.228 for
Raw and -0.357 for R109.  After native-resolution continuous measurement they
are about -0.082 (p = 0.417) and -0.063 (p = 0.531); V42 is about -0.089
(p = 0.380).  Ring-width variation therefore does not currently explain the
external GMF ranking and should not be called a causal mechanism.

R112's zero peak-radius variance for all arms and zero V42 width variance are
quantization artifacts.  They are not safe thesis evidence.

## Validation status

- Exactly 300 frame rows: 100 unique frames for each of Raw, V42, and R109.
- Exactly 835,500 radial-profile rows on a 0.25 px grid.
- All numeric values are finite and all detected inner/peak/outer geometries
  are ordered correctly.
- A denser 0.125 px / 1440-angle audit on 15 representative frames changes the
  primary radius by at most 0.0648 px, width by at most 0.1913 px, and contrast
  by at most 0.137 gray levels; all prespecified limits pass.
- Five unit tests cover known subpixel radius and width, floating-point centre
  alignment, annulus scope, soft annulus area, and development-output
  isolation.
- A partial one-frame CLI run was executed after the formal run; the canonical
  CSV SHA-256 remained unchanged and retained all 300 rows.

## Interpretation boundary

These measurements use external GMF coordinates only to align corresponding
objects.  They are not physical contour truth.  Circular averaging also cannot
replace SEM/ACM validation of non-circular shape.  The results are suitable for
repairing the R112 mechanism claims, not for ranking overall reconstruction
fidelity by themselves.
