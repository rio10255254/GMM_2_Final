# R106A Multi-Observation Short Validation

This is the complete short gate before any full R106 training.

The model is trained from scratch and accepts one, two or four observations with one shared set of weights. Its output is always anchored to the first reference frame. Additional frames receive learned local compatibility weights before feature fusion. Signed-distance geometry is auxiliary supervision only and never directly renders the final image.

Training uses procedural latent scenes only. JunHua measurements influence shift/noise/gain ranges, not pixels or target shapes. Real JunHua images are evaluated only after the short checkpoint is locked.

Run synthetic training and validation:

    C:\Users\Rio\anaconda3\python.exe scripts\run_short.py

Then run the locked JunHua validation:

    C:\Users\Rio\anaconda3\python.exe scripts\validate_junhua.py

## Final status

All short validations are complete. The synthetic and locked JunHua gates both failed, so no full R106 training was started.

N2 improved held-out boundary distance and image error, but N4 did not continue improving contour or transition-center accuracy even on clean bundles. Soft observation weights did not fully reject bad or mismatched frames. Motion and tile behavior were safe, while exposure and leave-one-out uncertainty remained insufficient.

See `reports/R106A_FINAL_FINDINGS_ZH.md` for the complete interpretation and the specific architectural repair required before another training attempt.

The project-level follow-up decision is recorded in `Thesis_MOSR_Evidence/GPT_Context/SINGLE_IMAGE_MAINLINE_RETURN_20260824.md`: multi-observation is now an optional controlled-acquisition branch, and the research mainline has returned to single-image reconstruction through `R107A_SingleImageEdgeGeometryProbe`.
