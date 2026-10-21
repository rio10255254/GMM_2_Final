# R73 Manifest

- Model under test: frozen R61v16 best-tradeoff checkpoint.
- Test population: 100 images generated on 2026-07-30 after model training.
- Shape families: Fourier-lobed, deep notches, thin necks, crescent bodies, and rough boundaries.
- Independent unit: one generated image; twenty independently seeded images per family.
- Primary reference: exact binary geometry produced before rendering and degradation.
- Primary comparison: Raw versus R61v16 after translation-only alignment.
- Secondary comparison: fixed pixel coordinates with no alignment.
- Shape fitting exclusions: no radius fitting, no circle fitting, no scale fitting, and no rotation fitting.
- ACM extraction audit: clean truth images must reproduce the exact generator masks with IoU at least 0.97.
