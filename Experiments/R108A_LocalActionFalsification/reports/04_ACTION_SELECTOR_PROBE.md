# R108A Short Action-Selector Probe

- Images/families: 200 / 10.
- Leave-one-family-out exact action accuracy: 37.0%.
- Selector beats the fold-global action on 21.5% of images and is worse on 20.0%.
- Raw edge-band median: 32.884; selector: 32.018; oracle: 32.120 gray.

A useful selector should improve the global action without creating a worse tail. Failure here means the next experiment should improve local observability/action supervision before building a neural router.
