# R105C JunHua Multi-Observation Feasibility

This is a read-only audit of the 202 JunHua raw BMP images. It does not train a model and does not modify the source folder.

The first goal is an honest two-observation mode: each filename-sorted even/odd pair represents one nominal stage position and produces one future reconstruction. Neighboring positions are not shared between outputs at this stage, avoiding artificially correlated GMF displacement results.

The laboratory PI sequence is excluded from this experiment because its motion quality would confound reconstruction, registration and stage errors.

## Final status

All 101 filename-sorted even/odd pairs passed the read-only audit. The within-pair shift median is 0.091 px and the maximum is 0.276 px. These pairs are approved as the first real N=2 engineering source.

The two frames must remain separate model inputs. A direct mean lowers the estimated noise standard deviation from 0.631 to 0.446 gray levels, but also lowers the noise-suppressed structural edge energy by about 3.1%.

Cross-position N=4 is not approved for formal GMF because neighboring outputs would share source frames and the periodic sample creates ambiguous correlation peaks.

## Cross-position result

All 100 adjacent-position bundles were registered using a ring-informed initialization followed by structural ECC refinement. The median content shift is approximately X -0.083 px and Y -7.886 px; the worst aligned structural correlation is 0.99895. Fusing the aligned neighbor changes fitted ring center by 0.102 px median and 0.215 px at the 95th percentile, while median fitted radius changes by only 0.009 px.

An exploratory pass through the procedural R105B model kept N=4 center behavior comparable to N=2 and did not reduce edge energy, but N=4 changed N=2 by only 0.098 gray on median. Cross-position N=4 is therefore approved for a real-model adaptation experiment, not claimed as a proven real reconstruction or external-GMF gain.
