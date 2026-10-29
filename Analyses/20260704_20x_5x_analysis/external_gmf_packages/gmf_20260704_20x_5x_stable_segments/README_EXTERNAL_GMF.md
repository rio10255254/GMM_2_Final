# 20260704 20x/5x external GMF package (stable_segments)

Use `paths_for_gmf_tool.tsv` as the case list for the external GMF tool.
Each case has a `bmp` image folder and a matching empty `_gmf_scores/<case>` folder.
Please save each returned score as `GMF_score.txt` in that matching score folder.

Cases use identical frame ordering between Raw and R61 v16 inside the same group/segment.
The image filenames are normalized to `frame_####.bmp` for stable parsing.

Expected displacement uses camera pixel size 3.45 um divided by the folder magnification label.
20x / 1um is expected to be about 5.797101 px; 20x / 0.5um about 2.898551 px.
5x / 1um is expected to be about 1.449275 px; 5x / 0.5um about 0.724638 px.

Raw and R61 v16 PSF-off cases are both included.
