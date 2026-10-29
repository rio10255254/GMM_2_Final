# 20x Perfect-Step External GMF Readout

## Calibration Used

- Camera pixel size: 3.45 um
- Objective magnification: 20.0x
- Object-plane pixel size: 0.1725 um/px
- Expected 1.0 um step: 5.7971 px
- Expected 0.5 um step: 2.8986 px

## Main Gate

- A physical step is counted only if the same frame interval passes in both Raw and R61.
- Main perfect-step gate: abs(dx error) <= 0.15 px and abs(dy) <= 0.25 px.

## Main Result, Common Perfect Physical Steps

| Group | Variant | Selected steps | Expected px | Median abs(dx) px | Error nm | Std nm | Median abs(dy) nm |
|---|---|---:|---:|---:|---:|---:|---:|
| 20x_0p5um | raw | 36/48 | 2.8986 | 2.9065 | 1.37 | 10.29 | 13.89 |
| 20x_0p5um | v16 | 36/48 | 2.8986 | 2.9040 | 0.94 | 10.99 | 14.75 |
| 20x_1um | raw | 39/48 | 5.7971 | 5.8330 | 6.19 | 7.88 | 11.04 |
| 20x_1um | v16 | 39/48 | 5.7971 | 5.8340 | 6.37 | 8.65 | 10.70 |

## Common Step Indices

- 20x_0p5um: 36 common steps
  1->2, 2->3, 3->4, 4->5, 5->6, 6->7, 7->8, 8->9, 9->10, 10->11, 13->14, 15->16, 20->21, 21->22, 22->23, 23->24, 24->25, 25->26, 26->27, 28->29, 29->30, 30->31, 31->32, 32->33, 34->35, 35->36, 36->37, 37->38, 38->39, 39->40, 40->41, 42->43, 43->44, 46->47, 47->48, 48->49
- 20x_1um: 39 common steps
  1->2, 4->5, 5->6, 6->7, 9->10, 10->11, 11->12, 12->13, 13->14, 14->15, 15->16, 16->17, 17->18, 18->19, 19->20, 20->21, 21->22, 22->23, 23->24, 24->25, 25->26, 26->27, 27->28, 28->29, 29->30, 30->31, 31->32, 32->33, 34->35, 35->36, 36->37, 37->38, 38->39, 39->40, 43->44, 44->45, 45->46, 47->48, 48->49

## Sensitivity Gates

The CSV includes stricter and looser gates so this diagnostic is not tied to one arbitrary threshold.

## Output Files

- external_gmf_perfect_step_summary.csv
- external_gmf_perfect_common_steps.csv
- external_gmf_20x_perfect_steps_summary.png