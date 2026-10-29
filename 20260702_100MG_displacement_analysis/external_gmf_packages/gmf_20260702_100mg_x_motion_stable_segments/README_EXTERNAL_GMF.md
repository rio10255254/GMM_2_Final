# Stable-segment GMF package

Source analysis root: 20260702_100MG_displacement_analysis

This stable package splits sequences at long timing gaps. Use it for cleaner model-vs-raw displacement comparison.

Cases are listed in `paths_for_gmf_tool.tsv`. Each case has a `bmp` folder and a matching empty `_gmf_scores/<case>` folder for returned GMF scores.

Recommended workflow:
1. Open `paths_for_gmf_tool.tsv` in the external GMF tool.
2. Generate each case score into its listed score folder.
3. Keep filenames unchanged; every paired Raw/v16 case uses the same `frame_####.bmp` ordering within the same dataset/segment.

Important notes:
- `x_1um` command step is 1.0 um; expected local displacement was about 14.6 px in this capture.
- `x_0p5um` command step is 0.5 um; expected local displacement was about 7.25 px in this capture.
- These packages contain Raw and R61 v16 PSF-off reconstructions only.
