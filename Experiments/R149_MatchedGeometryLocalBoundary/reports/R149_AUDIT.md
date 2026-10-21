# R149 Audit

## Verdict

The local-boundary arm did not pass its predeclared gate and was not released to formal training.

## Evidence

- Pilot 1: boundary weight 0.20, 75% local mix. Common matched-circle local-boundary score improved 0.75%; matched image error improved 0.70%.
- Pilot 2: boundary weight 0.35, 100% local. Common matched-circle local-boundary score improved 0.81%; matched image error improved 0.87%.
- Both pilots preserved translation consistency below 0.00002 px and trained stably at two fresh initializations.
- The required local-boundary improvement was at least 3% with image degradation below 5%.

Increasing the boundary strength did not materially increase the common local benefit. The gate was retained and the arm was stopped. The matched-geometry data and fixed-mean PSF intervention remain eligible for a separate formal experiment because the two global-boundary controls learned stably on that exact data.
