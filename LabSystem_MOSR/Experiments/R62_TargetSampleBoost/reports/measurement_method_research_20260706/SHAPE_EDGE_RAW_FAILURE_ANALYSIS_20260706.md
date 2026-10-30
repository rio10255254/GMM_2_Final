# Shape-Edge Raw Failure Analysis 20260706

## Method Principle

The shape-edge anchor method does not measure whole-image texture motion.

For each selected ROI, it does the following:

1. Convert the image into an edge map.
2. Keep the stronger boundary-like edge points as the local shape.
3. Estimate subpixel motion from the edge maps.
4. Check whether the shifted edge shape actually lands on the next frame's edge shape.
5. Keep both values:
   - all attempted displacement for fair all-step statistics,
   - high-confidence status for readability/measurement confidence.

This means a bad Raw result should be read as:

Raw boundary information is hard for this boundary-based measurement to read consistently.

It should not be read as:

the physical stage moved less.

## Why Raw Looks Bad In 100MG x_1um

The all-step result:

| case | all steps | high-confidence steps | all-step mean um | all-step std um |
|---|---:|---:|---:|---:|
| Raw | 49 | 16 | 0.886481 | 0.092068 |
| V31 | 49 | 49 | 1.005682 | 0.010178 |

Raw has two different behaviors.

| Raw group | steps | mean dx px | std dx px | mean dy px | meaning |
|---|---:|---:|---:|---:|---|
| edge-phase accepted | 16 | -14.5519 | 0.1139 | 0.0094 | clean boundary motion, near expected 1 um |
| edge-phase rejected | 33 | -12.0212 | 0.7127 | 1.9273 | ambiguous shape match, not reliable |

Expected 1 um motion is about `-14.492754 px`.

So Raw is not uniformly bad. When Raw's boundary signal is readable, it gives the correct answer. The problem is that most Raw steps do not produce a stable edge-only subpixel motion candidate.

## What The Edge-Phase Check Shows

For Raw, many consecutive frame pairs have edge-phase candidates near zero motion:

```text
frame 1: dx about -0.07 px
frame 2: dx about -0.04 px
frame 3: dx about -0.02 px
...
```

For V31, the same check is near the expected motion on every step:

```text
frame 1: dx about -15.05 px
frame 2: dx about -14.07 px
frame 3: dx about -14.79 px
...
mean dx about -14.575 px
```

This is the central reason Raw loses:

Raw's edge map often does not behave like a clean translated boundary image, while the reconstruction does.

## Why This Can Happen

Likely causes in the Raw image:

1. The true sample boundary is blurred and low contrast.
2. Raw contains local texture, illumination variation, and edge-like noise that do not move like the sample boundary.
3. The ROI contains repeated pillar/boundary structures, so a shape-only match has several similar answers.
4. When the edge-phase cue fails, the fallback shape match can choose a nearby but wrong alignment, often around `-11.5 px` with a false y shift.

Likely effect of reconstruction:

1. It suppresses raw texture that is not useful for boundary localization.
2. It makes the sample boundary more coherent.
3. It turns the same physical motion into a clearer edge-map translation.
4. Therefore the edge-phase step is accepted on all 49 steps.

## Important Caveat

The current result is evidence of better boundary readability, not by itself proof that every physical Raw step was wrong.

The fair thesis wording should be:

Under the same boundary-based measurement rule, reconstructed images make the 1 um displacement much more consistently measurable than Raw.

Avoid wording like:

Raw physically moved only 0.886 um.

## Why Counting All Steps Was Necessary

If only high-confidence steps are counted, Raw gets an unfair advantage because its difficult steps disappear.

The corrected rule is:

- all attempted steps are used for the main stability and accuracy comparison,
- high-confidence coverage is reported separately,
- failure reasons explain whether the measurement is trustworthy.

This is why the final table is stronger and fairer:

Raw is not punished by deletion, and reconstruction is not rewarded by filtering. Every frame interval is included.

