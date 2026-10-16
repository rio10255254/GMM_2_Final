# External GMF Selected-Step Analysis

This readout compares Raw and R61 v16 PSF-off with the same frame steps inside each selection mode. It is selected/quality-screened evidence, not the formal all-step GMF baseline.

## Data coverage

- Parsed GMF step rows: 386

- Groups with usable GMF scores: 20x_0p5um, 20x_1um, 50x_0p5um, 50x_1um

- Missing expected score files: 5x_1um Raw, 5x_1um R61 v16 PSF-off, 5x_0p5um Raw, 5x_0p5um R61 v16 PSF-off

- Note: GMF files start at frame_0001, so a selected step that needs frame_0000 cannot be recomputed here and is dropped.

## All available GMF steps

| Dataset | Raw median error | R61 median error | Raw std | R61 std | Raw within 0.05um | R61 within 0.05um | Score change |
|---|---:|---:|---:|---:|---:|---:|---:|
| 50x / 1 um | 0.0053 | 0.0049 | 0.0084 | 0.0077 | 100.0% | 100.0% | 0.978 |
| 50x / 0.5 um | 0.0053 | 0.0037 | 0.0531 | 0.0531 | 95.9% | 95.9% | 0.270 |
| 20x / 1 um | 0.0092 | 0.0083 | 0.0258 | 0.0268 | 93.8% | 91.7% | -0.215 |
| 20x / 0.5 um | 0.0108 | 0.0118 | 0.0781 | 0.0773 | 89.6% | 89.6% | -0.005 |


## Phase-selected steps transferred to GMF

| Dataset | Raw median error | R61 median error | Raw std | R61 std | Raw within 0.05um | R61 within 0.05um | Score change |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20x / 0.5 um | 0.0042 | 0.0049 | 0.0070 | 0.0089 | 100.0% | 100.0% | -0.004 |
| 20x / 1 um | 0.0058 | 0.0051 | 0.0057 | 0.0068 | 100.0% | 100.0% | -0.254 |
| 50x / 0.5 um | 0.0028 | 0.0018 | 0.0037 | 0.0029 | 100.0% | 100.0% | 0.271 |
| 50x / 1 um | 0.0027 | 0.0038 | 0.0031 | 0.0036 | 100.0% | 100.0% | 0.996 |


## GMF-selected pair-matched best 30

| Dataset | Raw median error | R61 median error | Raw std | R61 std | Raw within 0.05um | R61 within 0.05um | Score change |
|---|---:|---:|---:|---:|---:|---:|---:|
| 50x / 1 um | 0.0027 | 0.0038 | 0.0033 | 0.0037 | 100.0% | 100.0% | 0.980 |
| 50x / 0.5 um | 0.0029 | 0.0018 | 0.0036 | 0.0028 | 100.0% | 100.0% | 0.253 |
| 20x / 1 um | 0.0058 | 0.0051 | 0.0057 | 0.0064 | 100.0% | 100.0% | -0.254 |
| 20x / 0.5 um | 0.0042 | 0.0057 | 0.0074 | 0.0090 | 100.0% | 100.0% | -0.006 |


## Interpretation

- After selection, external GMF becomes extremely stable on 50x and 20x. The selected-step median errors are generally in the nanometer-to-few-nanometer range.

- Raw and R61 stay very close under GMF. This means GMF is a very strong displacement extractor here and does not strongly expose the reconstruction model advantage.

- The clearest model value should therefore be shown with boundary/CD/roundness/generalization evidence, while GMF is better used as a displacement-consistency sanity check.

- 5x cannot be included in this external-GMF selected analysis yet because no 5x GMF_score.txt files were present in the checked package.
