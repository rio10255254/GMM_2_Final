# R108A Constrained Optical Action Oracle

Evaluated 33 actions on 200 truth-backed images.

## R73

- Non-identity selected: 99.0%.
- Simultaneous edge/center/width improvement: 75.0%.
- Edge-band median: Raw 27.285 gray, selected 24.271 gray.
- Transition-center median: Raw 0.500 px, selected 0.000 px.
- Transition-width median: Raw 8.000 px, selected 5.500 px.
- Selected action families: {"wiener": 62, "denoise": 24, "combined": 11, "fixed_center_edge": 2, "identity": 1}.

## R74

- Non-identity selected: 95.0%.
- Simultaneous edge/center/width improvement: 76.0%.
- Edge-band median: Raw 43.372 gray, selected 42.829 gray.
- Transition-center median: Raw 1.000 px, selected 0.500 px.
- Transition-width median: Raw 11.000 px, selected 10.000 px.
- Selected action families: {"denoise": 69, "wiener": 16, "combined": 6, "identity": 5, "illumination": 4}.

## Interpretation

If the truth-selected action library materially improves edge profile, center and width together on both suites, the local-action mechanism has enough representational headroom for a learned selector.  If gains occur only on R73 or require unstable inverse filters, the proposed bank is not ready for a selector probe.
