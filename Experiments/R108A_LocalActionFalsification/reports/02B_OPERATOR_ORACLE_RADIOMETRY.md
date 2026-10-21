# R108A Constrained Optical Action Oracle

Evaluated 56 actions on 200 truth-backed images.

## R73

- Non-identity selected: 78.0%.
- Simultaneous edge/center/width improvement: 74.0%.
- Edge-band median: Raw 27.285 gray, selected 24.123 gray.
- Transition-center median: Raw 0.500 px, selected 0.000 px.
- Transition-width median: Raw 8.000 px, selected 5.500 px.
- Selected action families: {"wiener": 45, "identity": 22, "fixed_center_radiometry": 18, "combined": 7, "combined_radiometry": 5, "denoise": 3}.

## R74

- Non-identity selected: 94.0%.
- Simultaneous edge/center/width improvement: 80.0%.
- Edge-band median: Raw 43.372 gray, selected 42.780 gray.
- Transition-center median: Raw 1.000 px, selected 0.500 px.
- Transition-width median: Raw 11.000 px, selected 10.000 px.
- Selected action families: {"denoise": 46, "combined_radiometry": 25, "wiener": 14, "identity": 6, "local_contrast": 4, "illumination": 3, "symmetric_unsharp": 1, "fixed_center_edge": 1}.

## Interpretation

If the truth-selected action library materially improves edge profile, center and width together on both suites, the local-action mechanism has enough representational headroom for a learned selector.  If gains occur only on R73 or require unstable inverse filters, the proposed bank is not ready for a selector probe.
