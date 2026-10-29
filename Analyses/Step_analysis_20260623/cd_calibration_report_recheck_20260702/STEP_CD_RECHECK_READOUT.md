# Step CD vs calibration-report recheck

Scale: 2.5 um camera pixel / 20x objective = 0.125 um/px.

Calibration-report interpretation: the Mitutoyo circle page is a form-deviation / roundness page, not a certified per-circle CD table. The newly supplied page 3 is different: it is an EUV Pattern measured-size correction table where calibration value = measured value - nominal value, in mm. This run still compares the measured concentric-circle CD to nominal circle diameters because the 100 um and 200 um circles measured here are not directly listed on that EUV Pattern page.

| Target | Raw mean | Raw error | v16 mean | v16 error | v16 absolute-error change | Raw sensitivity | v16 sensitivity |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 um | 99.2879 | -0.7121 | 99.4614 | -0.5386 | -0.1735 | 0.3293 | 0.0258 |
| 200 um | 199.5190 | -0.4810 | 199.6922 | -0.3078 | -0.1732 | 0.3367 | 0.0262 |

Negative error means measured CD is smaller than the nominal report size. Negative absolute-error change means v16 is closer to nominal; positive means farther from nominal.

Circle report context: 100 um row roundness is about 0.059 um; 300 um row roundness is about 0.057 um. These are not CD offsets. The line-width value 399.63 um is readable but not measured here because this field is the concentric-circle region.

## Page 3 EUV Pattern correction note

The page 3 photo supplied on 2026-07-02 is real measured-size evidence for the EUV Pattern region. The formula on the sheet means:

actual size = nominal size + calibration value.

The unit is mm, so 0.00001 mm = 0.01 um. For example, a 0.30000 mm row value of +0.00002 mm means 300.02 um; a value of -0.00004 mm means 299.96 um.

Important boundary: this page should be used for the EUV Pattern features labeled No.00 to No.17, not automatically for the concentric-circle CD values measured above. To use it as ground truth, we must measure the matching EUV Pattern feature in the optical image and know which No. column it corresponds to.

## Circle_Round1 feasibility check

Circle_Round1 was inspected as raw-image feasibility only. This folder does not currently contain an R61 v16 reconstruction package, so it is not used as a latest-model CD validation result.

| Target | Full-circle frames | Raw mean | Raw error | Frame std | Note |
|---:|---:|---:|---:|---:|---|
| 100 um | 242 / 242 | 99.1422 | -0.8578 | 0.1024 | all frames have a complete fitted 100 um circle |
| 200 um | 162 / 242 | 199.3502 | -0.6498 | 0.1206 | many frames lose the full 200 um circle because the pattern is off-center |
