# External GMF package: Pitch1um_Y_100 / R103 E48 / R104 E48

This package contains 202 frames from:

`Shared_Sources/NTU_Originals/Pitch1um_Y_100/Cropped_Output`

The three arms use the same normalized names and order:

- `pitch1um_y100_raw\bmp`: byte-preserved Raw control
- `pitch1um_y100_r103_e48\bmp`: R103 epoch 48 reconstruction
- `pitch1um_y100_r104_e48\bmp`: R104 epoch 48 reconstruction

Run the external GMF program on every `image_folder` listed in
`paths_for_gmf_tool.tsv`. Put each returned `GMF_score.txt` into the matching
folder under `_gmf_scores`. Do not rename or reorder frames. The original
filename mapping and SHA-256 hashes are in `source_mapping.csv`.

The score folders are intentionally empty until the external program returns.
