# External GMF Result Drop Folder

Put the text files exported by the external GMF program in this folder.

Recommended filenames:

| Case | Suggested result filename |
|---|---|
| `gmf_cases/raw_input/` | `raw_input_GMF_score.txt` |
| `gmf_cases/lab_r39_latest/` | `lab_r39_latest_GMF_score.txt` |
| `gmf_cases/lab_r40_latest/` | `lab_r40_latest_GMF_score.txt` |
| `gmf_cases/lab_r39_best_tradeoff/` | `lab_r39_best_tradeoff_GMF_score.txt` |
| `gmf_cases/lab_r40_best_tradeoff/` | `lab_r40_best_tradeoff_GMF_score.txt` |

Keep the original GMF text output unchanged. The analysis step should parse the
exported text as-is, then record any skipped first frame, missing interval, or
warm-up behavior in the final result report.
