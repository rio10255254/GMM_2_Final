# R114 split-profile action contract

## Scope

This candidate turns the E020 oracle profile-action result into a fresh,
trainable, inference-time architecture.  It does not load a checkpoint and it
does not authorize training by itself.

The action is attached only after the independent normal-shift and width
actions have produced `base_output`.

## Allowed learned fields

The renderer backbone feeds four one-channel local heads:

1. `midpoint_offset`, bounded to +/-24 gray levels;
2. `signed_plateau_contrast`, bounded to +/-72 gray levels;
3. `profile_width`, bounded to 0.8--3.5 pixels;
4. `profile_visibility`, bounded to 0--1 and initialized to exact zero.

The local midpoint cue is the midpoint of local low/high plateaus from the
shifted raw-derived base.  The learned midpoint head may only offset that cue.
The proposal is analytic:

`midpoint + 0.5 * signed_contrast * tanh(predicted_sdf_px / profile_width)`

There is no target argument, target copy, raw anchor, free pixel residual, or
detail-action head in this candidate.

## Actuation gate and bounds

The profile action gate is exactly:

`boundary_confidence * profile_visibility * profile_band`

`profile_band` is one through an absolute predicted distance of 10 pixels,
falls with a C1 smoothstep from 10 to 14 pixels, and is exactly zero at and
beyond 14 pixels.  The proposal delta is hard-clipped to +/-48 gray levels
before the gate is applied.

The zero-initialized visibility head maps a zero logit to an exact zero action
while retaining a positive one-sided gradient for positive training targets.
Consequently a freshly initialized profile action is bit-exact neutral with
respect to the completed split width+shift base.

## Locality and tiling

All cues are fixed local filters, local convolutions, local pooling, or
pointwise analytic operations.  There is no global pooling, FFT, patch-wide
normalization, or patch statistic.  `minimum_halo_px` includes the controller,
split geometry action, shift sampling margin, and the extra local plateau
midpoint radius.  Tiled inference refuses a smaller halo.

## Staged optimization groups

The four profile heads have separate atomic parameter groups.  The
`profile_parameters()` convenience method contains the shared renderer
backbone and exactly those four heads.  The recoverability head remains a
controller evidence head; it is not an image residual branch.

## Executable checks

`test_r114_split_profile_model.py` verifies:

- exact neutral initialization;
- all physical parameter and 48-gray delta bounds;
- smooth 10/14-pixel band and exact zero action outside it;
- signed polarity behavior;
- isolation of boundary, visibility, and band gates, with an explicit check
  that need/recoverability are not multiplied twice after visibility already
  represents counterfactual usefulness;
- active full-image versus tiled-interior parity;
- input and head gradients;
- disjoint, exhaustive parameter groups;
- absence of a detail or free image-residual head.
