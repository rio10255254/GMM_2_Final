# R119 formal result

Date: 2026-09-05. Formal run: `formal_B_s1195001`.
Candidate: B (same-object observation scheduling; unchanged R118 numerical
architecture). Initialization was fresh (`model_seed=1195001`); no historical
checkpoint was loaded. Training used 5,000 synthetic geometries for 42 epochs,
batch 12, four workers and 17,514 optimizer steps.

## What actually ran

The bounded probe matrix ran A/B/D with two independent model seeds (512 train
scenes, 12 epochs). A, B and D were then compared on the same locked R73/R74 ACM
sets, the same 36-pillar/12-exposure SEM set and the same Raw-locked 120-pair
LSC protocol. B was selected before the formal run because it was the only arm
that improved difficult R74 ACM, all SEM pillars and Raw LSC step variation at
the same time. Its weaker LSC fine-grid spread versus R109 was recorded, not
hidden.

The formal run completed 42/42 epochs. Fourteen E3-spaced checkpoints and real
Raw previews were written. E42 reload and halo-tiled inference are finite; the
largest direct-versus-tiled difference on the four Raw previews is
0.002614 gray levels.

## Formal E42 development results

| Readout | Raw | R109 E48 | R119 B E42 | Interpretation |
|---|---:|---:|---:|---|
| Synthetic motion step SD (px) | 0.01393 | 0.01595 | 0.01495 | R119 is slightly above Raw, below R109 |
| Synthetic static repeat SD (px) | 0.01011 | 0.01116 | 0.00965 | R119 improves this diagnostic |
| Synthetic image error (gray) | 2.036 | 1.534 | **0.714** | R119 has the clearest target agreement |
| Synthetic gradient error | 0.00902 | 0.00685 | **0.00227** | Detail/edge agreement improves strongly |
| Real LSC step SD (nm) | 9.745 | 7.003 | 7.261 | R119 improves Raw, not R109 |
| Real LSC fine-grid SD (nm) | 13.966 | **4.398** | 5.013 | R109 remains stronger on this axis |
| Real LSC cross-axis median (nm) | 6.009 | 5.313 | **4.227** | R119 has the lowest cross-axis value |

Locked ACM had zero primary and sensitivity failures in both suites. R73 mean
boundary distance changed −26.91% and R74 changed −4.25%. R74 HD95 changed
−5.79% and overlap increased by 0.00754. All five R74 families improved in mean
boundary distance; mixed-hard HD95 is the one family-level caution (+1.71%).

SEM used 36 independent pillars and 12 repeated exposures from Raw inputs. The
formal E42 median boundary gain was **−0.0846% of pitch**, with 0/36 pillars
improving under this locked development comparison. This is a real negative
transfer result and prevents a claim of universal improvement. E24 was nearly
neutral (−0.0093%, 7/36), while E36 was −0.0564% (0/36); later detail learning
helped ACM but did not transfer to this SEM readout.

## Endpoint check

E24 ACM R74 was −1.24% and its LSC was 7.596 nm step SD / 5.691 nm fine-grid
SD. E36 LSC was 7.993 / 5.696 nm and its SEM was −0.0564%. E42 gave the best
R74 ACM (−4.25%) and best R119 LSC (7.261 / 5.013 nm), so E42 is the frozen
confirmation candidate despite the SEM regression. E36 ACM was not rerun because
the endpoint sweep was stopped once E42 established the best ACM/LSC pair; this
absence is explicit rather than silently filled in.

## Scientific conclusion

R119 B E42 is a strong **shape/detail research candidate** and is materially
better than Raw on the synthetic edge/detail and locked ACM development tests.
It is not a universal replacement for R109/V42: R109 still has better fine-grid
LSC stability, and R119's formal SEM transfer is slightly negative. The change
that helped was the observation arrangement, not a new network or an output
smoothing trick. The deployment interface remains one image with tile-safe
inference; sequence observations were supervision/diagnostics only.

This report does not promote R119 to the thesis baseline or enterprise package.
The final 144-scene confirmation is still reserved for one frozen, no-tuning
evaluation. If it fails, retain the failure and do not retune on that same set.
