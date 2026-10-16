# Step roundness recheck

Scope: same 1 um Step validation package used for the CD recheck. Cases: raw rep0/rep1 and R61 v16 PSF-off rep0/rep1, 40 frames each. Scale: 0.125 um/px.

Method: segment bright circular regions with Otsu threshold, pick the contour whose area-equivalent diameter matches the target, fit a least-squares circle to boundary points, then report radial spread. This is an optical-image estimate, not the same metrology method as the Mitutoyo instrument.

| Target | Raw p99-p1 roundness | v16 p99-p1 roundness | Change | Raw max-min | v16 max-min | Ovality raw | Ovality v16 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 um | 0.2554 | 0.2053 | -19.6% | 0.3692 | 0.2948 | 0.0672 | 0.0561 |
| 200 um | 0.2712 | 0.2142 | -21.0% | 0.6392 | 0.7245 | 0.0723 | 0.0274 |

Negative change means v16 has smaller apparent boundary deviation. The 100 um row can be compared only as context to the report roundness value about 0.059 um; the optical contour method is noisier and should not be presented as identical to the Mitutoyo number.
