# R106A Synthetic Short Gate

```json
{
  "metrics": {
    "n1": {
      "iou": 0.9452373133049661,
      "boundary_distance_px": 0.32053637004078017,
      "centroid_error_px": 0.16620128487013044,
      "transition_center_error_px": 0.3806201219558716,
      "transition_width_error_px": 0.5154141441869813,
      "mean_abs_error_gray": 6.8886095099151134,
      "images": 144
    },
    "n2": {
      "iou": 0.9518203375645138,
      "boundary_distance_px": 0.2946120819877336,
      "centroid_error_px": 0.12953515196639687,
      "transition_center_error_px": 0.3874908536672592,
      "transition_width_error_px": 0.5103412694854864,
      "mean_abs_error_gray": 5.802539438009262,
      "images": 144
    },
    "n4": {
      "iou": 0.952694701476096,
      "boundary_distance_px": 0.30526368393458786,
      "centroid_error_px": 0.14520847275257945,
      "transition_center_error_px": 0.4002272039651871,
      "transition_width_error_px": 0.5250205875910362,
      "mean_abs_error_gray": 5.1070119347423315,
      "images": 144
    },
    "mismatch_n4": {
      "iou": 0.9182311964714942,
      "boundary_distance_px": 0.5526208105981503,
      "centroid_error_px": 0.39989698015986225,
      "transition_center_error_px": 0.5791547000408173,
      "transition_width_error_px": 0.6340229937408913,
      "mean_abs_error_gray": 12.992594372481108,
      "images": 144
    },
    "raw_reference": {
      "iou": 0.9471389301226016,
      "boundary_distance_px": 0.3327567886071645,
      "centroid_error_px": 0.1405377794465827,
      "transition_center_error_px": 0.36642491817474365,
      "transition_width_error_px": 0.5826941237908208,
      "mean_abs_error_gray": 7.348937708884478,
      "images": 144
    }
  },
  "admission": {
    "good_weight_median": 0.9571982622146606,
    "bad_weight_median": 0.8259207606315613,
    "mismatch_nonreference_weight_median": 0.5428687334060669,
    "jackknife_median_gray": 6.323272520676255,
    "jackknife_spearman_vs_mae": 0.17471950718263182
  },
  "motion_exposure": {
    "n1": {
      "motion_median_px": 0.0885657201693063,
      "motion_p95_px": 0.3829804190335049,
      "exposure_median_px": 0.023202540204943764,
      "exposure_p95_px": 0.3809660757827582
    },
    "n2": {
      "motion_median_px": 0.08028059168005891,
      "motion_p95_px": 0.2730188484306305,
      "exposure_median_px": 0.03653288724096894,
      "exposure_p95_px": 0.5110274019499506
    },
    "n4": {
      "motion_median_px": 0.0860015067676355,
      "motion_p95_px": 0.1602504846940069,
      "exposure_median_px": 0.046279671098362785,
      "exposure_p95_px": 0.3638326898788653
    }
  },
  "tile": {
    "n1": {
      "max_abs_gray": 1.519918441772461e-05
    },
    "n2": {
      "max_abs_gray": 1.519918441772461e-05
    },
    "n4": {
      "max_abs_gray": 1.519918441772461e-05
    }
  },
  "decision": {
    "directions": {
      "n2_boundary": true,
      "n4_boundary": false,
      "n2_center": false,
      "n4_center": false,
      "n2_mae": true,
      "n4_mae": true,
      "bad_weight": true,
      "mismatch_fallback": false,
      "jackknife": false,
      "tile": true,
      "motion": true,
      "exposure": false
    },
    "synthetic_gate_passed": false,
    "full_r106_authorized": false,
    "interpretation": "Synthetic short gate failed; do not start full R106."
  }
}
```
