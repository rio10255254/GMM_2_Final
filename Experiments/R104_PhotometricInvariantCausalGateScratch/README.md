# R104 Photometric-Invariant Causal-Gate Scratch

R104 is the proposed successor to R103.  It keeps R103's proven local,
anti-aliased, tile-safe backbone and changes only the mechanisms implicated by
the completed causal diagnosis.

The formal R104 run is intentionally not authorized yet.  No R103 or other
checkpoint may be loaded.  Real optical/SEM images remain validation-only.

## Why this round exists

- R103 confidence cannot suppress a correction; its minimum effective scale is
  0.75.
- The R103 SEM response flips around exposure 18 even though physical geometry
  is unchanged.
- R103 preserves shared illumination instead of learning illumination-invariant
  shape evidence.
- A single image-wide intensity midpoint is not a reliable boundary definition
  under local shading, low contrast, or halos.
- Some R103 online innovation texture is added at native resolution instead of
  being rendered large and downsampled.

## R104 intervention

1. Preserve the raw-amplitude backbone for radiometry and proposal amplitude,
   but make shape and restoration-need decisions use only local relative cues.
2. Predict arbitrary shape as a signed distance field; no circle or radius
   assumption is introduced.
3. Separate each radiometry, illumination, contour, and texture proposal from a
   true 0-to-1 correction-need gate.  Proposals and gates receive separate
   procedural supervision, and gate targets are reduced continuously when the
   missing detail has weak observable evidence.
4. Learn broad spatial-illumination correction from zero-mean fields while
   preserving global exposure, avoiding an unobservable request to guess the
   absolute brightness.
5. Train same geometry under several exposure/illumination conditions and make
   shape and gate decisions agree across them.
6. Retain R103 motion and tile objectives, but construct tile pairs from one
   coherent larger observation so their overlap is physically identical.
7. Render new texture at four times resolution before area downsampling, and
   read only the required signed-distance window instead of resizing a full
   canvas for every sample.

The core model, data path, objectives, and structural preflight are implemented.
`reports/design_preflight.json` records the passing audit.  Formal training is
still disabled and no earlier checkpoint may be loaded.

The large procedural base package is not duplicated.  Its verified location,
content hash, and isolation rules are recorded in
`data/TRAINING_DATA_REFERENCE.json`; R104 generates its 5,000 epoch observations
online from that immutable base.
