# Anchor Detail035 Decision 20260706

This updates the previous anchor-fusion decision. A safer detail formula was identified: keep the Raw image as the base and inject only 0.35x of the reconstruction high-frequency detail. This matches the earlier effective motionsafe_detail behavior much better than the first anchor_detail100 implementation.

## Decision

- `anchor_blend10`: safest global displacement-preserving output, especially when avoiding any local-center risk matters most.
- `anchor_detail035`: better thesis candidate for 100MG and boundary visibility, because it restores phase displacement while adding real edge/detail strength and staying very close to Raw.
- Do not promote the old `anchor_detail100`: it was too aggressive and damaged local-center GMF on 100MG 1um.

## Phase Displacement: Raw vs Blend10 vs Detail035

| group | signal | Raw median/std | Blend10 median/std | Detail035 median/std | Detail035 error |
|---|---|---:|---:|---:|---:|
| x_1um | gray_phase | 0.0081/0.0080 | 0.0084/0.2042 | 1.0082/0.0110 | 0.0082 |
| x_1um | edge_phase | 0.0297/0.4342 | 1.0055/0.0110 | 1.0020/0.0096 | 0.0020 |
| x_0p5um | gray_phase | 0.0260/0.0706 | 0.0270/0.2126 | 0.4992/0.0530 | 0.0008 |
| x_0p5um | edge_phase | 0.0518/0.4058 | 0.5000/0.0508 | 0.5053/0.0514 | 0.0053 |
| 20x_1um | gray_phase | 1.0037/0.0347 | 1.0025/0.0240 | 0.9965/0.0273 | 0.0035 |
| 20x_1um | edge_phase | 1.0053/0.0242 | 0.9999/0.0247 | 0.9959/0.0272 | 0.0041 |
| 20x_0p5um | gray_phase | 0.5093/0.1160 | 0.5065/0.0807 | 0.4974/0.0777 | 0.0026 |
| 20x_0p5um | edge_phase | 0.4987/0.0780 | 0.4952/0.0766 | 0.4854/0.0747 | 0.0146 |
| 5x_1um | gray_phase | 0.8575/0.1259 | 0.8655/0.1334 | 0.9351/0.1454 | 0.0649 |
| 5x_1um | edge_phase | 0.9073/0.1550 | 0.9160/0.1566 | 0.9209/0.1588 | 0.0791 |
| 5x_0p5um | gray_phase | 0.5181/0.0140 | 0.5274/0.0144 | 0.5239/0.0151 | 0.0239 |
| 5x_0p5um | edge_phase | 0.5111/0.0162 | 0.5095/0.0157 | 0.5038/0.0161 | 0.0038 |

## GMF Local-Center Cross-Check

| group | signal | Raw std/err | Blend10 std/err | Detail035 std/err |
|---|---|---:|---:|---:|
| x_1um | intensity | 0.0301/0.0023 | 0.0311/0.0065 | 0.0290/0.0094 |
| x_1um | edge | 0.5114/0.6219 | 0.5181/0.6201 | 0.5117/0.6194 |
| x_0p5um | intensity | 0.0571/0.0176 | 0.0563/0.0175 | 0.0578/0.0175 |
| x_0p5um | edge | 0.2080/0.0968 | 0.2100/0.0967 | 0.2093/0.0991 |
| 20x_1um | intensity | 0.0350/0.0034 | 0.0363/0.0041 | 0.0386/0.0033 |
| 20x_1um | edge | 0.4040/0.8787 | 0.3992/0.8353 | 0.4081/0.8423 |
| 20x_0p5um | intensity | 0.0805/0.0089 | 0.0808/0.0089 | 0.0787/0.0107 |
| 20x_0p5um | edge | 0.0980/0.0270 | 0.0955/0.0269 | 0.0934/0.0268 |
| 5x_1um | intensity | 0.3228/0.2041 | 0.3169/0.2104 | 0.3855/0.2208 |
| 5x_1um | edge | 0.3901/0.7738 | 0.2087/0.9058 | 0.1836/0.9551 |
| 5x_0p5um | intensity | 0.0473/0.0518 | 0.0509/0.0516 | 0.0537/0.0508 |
| 5x_0p5um | edge | 0.2743/0.0771 | 0.2551/0.0806 | 0.2281/0.2264 |

## Image Quality Sample Check

| group | case | edge strength vs Raw | detail energy vs Raw | similarity to Raw | MAE to Raw |
|---|---|---:|---:|---:|---:|
| x_1um | blend10 | 1.132 | 0.925 | 0.9994 | 1.740 |
| x_1um | detail035 | 1.281 | 1.650 | 0.9996 | 1.502 |
| x_1um | v7 | 2.451 | 5.331 | 0.9566 | 17.687 |
| x_0p5um | blend10 | 1.133 | 0.931 | 0.9994 | 1.732 |
| x_0p5um | detail035 | 1.283 | 1.665 | 0.9996 | 1.521 |
| x_0p5um | v7 | 2.498 | 5.462 | 0.9558 | 17.661 |
| 20x_1um | blend10 | 1.141 | 1.044 | 0.9968 | 2.427 |
| 20x_1um | detail035 | 1.386 | 2.934 | 0.9967 | 3.404 |
| 20x_1um | v7 | 3.131 | 15.961 | 0.8472 | 23.989 |
| 20x_0p5um | blend10 | 1.141 | 1.039 | 0.9970 | 2.373 |
| 20x_0p5um | detail035 | 1.384 | 2.886 | 0.9969 | 3.316 |
| 20x_0p5um | v7 | 3.094 | 15.485 | 0.8538 | 23.449 |
| 5x_1um | blend10 | 1.042 | 0.958 | 0.9985 | 1.459 |
| 5x_1um | detail035 | 1.234 | 1.721 | 0.9941 | 4.269 |
| 5x_1um | v7 | 1.589 | 3.855 | 0.9530 | 15.178 |
| 5x_0p5um | blend10 | 1.042 | 0.958 | 0.9985 | 1.458 |
| 5x_0p5um | detail035 | 1.235 | 1.721 | 0.9942 | 4.262 |
| 5x_0p5um | v7 | 1.588 | 3.846 | 0.9536 | 15.158 |

## Practical Thesis Use

Use `anchor_detail035` for the 100MG thesis sample when the figure/result needs visible boundary improvement and open phase displacement validation. Use `anchor_blend10` as the conservative cross-dataset displacement-preserving fallback. Both are fixed algorithms, not per-image calibration.

The next model-level direction is not another V14/V15/V16 long training run. The stronger direction is to train or infer with a native Raw-anchored residual output: Raw base plus bounded reconstruction-detail residual. The current fusion tool is the verified external version of that idea.

## Evidence

- Phase displacement: `anchor_detail035_phase_eval_20260706/detail035_phase_summary.csv`
- GMF displacement: `anchor_detail035_gmf_eval_20260706/detail035_gmf_summary.csv`
- Quality metrics: `anchor_quality_metrics_20260706/anchor_quality_summary_sample10.csv`
- Fusion tool: `Tools/Displacement_Algorithms/scripts/motion_preserving_fusion.py`
