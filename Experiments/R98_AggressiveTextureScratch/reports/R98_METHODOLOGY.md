# R98 METHODOLOGY

## Evidence behind the change

R97 reconstructed all 301 real validation frames and preserved exact tiled parity, but its dedicated texture branch was almost inactive on real images. The sum of branch corrections was reduced by roughly one half through cancellation, and 50x fine detail remained conservative. A direct audit of the procedural labels found that valid texture corrections exist but are sparse and typically much smaller than radiometry or nuisance corrections. A sampler audit also found that a 96-batch epoch could omit several roles entirely.

## R98 intervention

1. Preserve R97's local phase-safe and canonical-tiling design.
2. Expand only the source-derived texture basis; no free image residual is introduced.
3. Give texture-bearing roles a deterministic supplemental pass every epoch.
4. Increase texture and gradient emphasis while reducing pixel-average dominance.
5. Penalize destructive cross-branch cancellation more strongly.
6. Preserve signed motion, translation and wrong-period objectives.
7. End with detail retention instead of identity-heavy consolidation.

## Claim boundary

All training pixels remain generic and procedural. Real microscopy and SEM images are validation-only. Increased visual detail is not treated as improved metrology unless displacement and contour validation also support it.
