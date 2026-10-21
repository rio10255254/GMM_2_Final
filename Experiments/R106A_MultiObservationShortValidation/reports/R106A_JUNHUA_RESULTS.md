# R106A Locked JunHua Short Gate

```json
{
  "status": "complete",
  "bundles": 100,
  "median": {
    "n1_center_shift_px": 0.08586775918481712,
    "n2_center_shift_px": 0.08528345056232335,
    "n4_center_shift_px": 0.08563303811870482,
    "wrong_center_shift_px": 0.09654486452600103,
    "n1_radius_change_px": 0.05746357736817487,
    "n2_radius_change_px": 0.05808329462549899,
    "n4_radius_change_px": 0.05867622578205456,
    "n1_edge_ratio": 1.08089896775193,
    "n2_edge_ratio": 1.0813271856910747,
    "n4_edge_ratio": 1.0821693450177863,
    "n2_minus_n1_mae_gray": 0.10827854079252575,
    "n4_minus_n2_mae_gray": 0.22546426378539763,
    "wrong_minus_n1_mae_gray": 0.7432715554023162,
    "n2_second_weight": 0.9990633428096771,
    "n4_neighbor_weight_median": 0.9989208281040192,
    "wrong_neighbor_weight_median": 0.46925070881843567,
    "jackknife_gray": 0.1293694760533981
  },
  "p95": {
    "n1_center_shift_px": 0.18377653989425743,
    "n2_center_shift_px": 0.185289241925496,
    "n4_center_shift_px": 0.1832694268264622,
    "wrong_center_shift_px": 0.21371776623976266,
    "n1_radius_change_px": 0.10119072369050315,
    "n2_radius_change_px": 0.10119072369050315,
    "n4_radius_change_px": 0.10136642340503563,
    "n1_edge_ratio": 1.0827078179488496,
    "n2_edge_ratio": 1.0829977878523938,
    "n4_edge_ratio": 1.0837936575933749,
    "n2_minus_n1_mae_gray": 0.16555567205068655,
    "n4_minus_n2_mae_gray": 0.25880090065766126,
    "wrong_minus_n1_mae_gray": 0.9356525426264852,
    "n2_second_weight": 0.999088117480278,
    "n4_neighbor_weight_median": 0.9990058600902557,
    "wrong_neighbor_weight_median": 0.4704043582081795,
    "jackknife_gray": 0.14005523000378162
  },
  "decision": {
    "directions": {
      "n2_center_not_worse": true,
      "n4_center_not_worse": true,
      "n2_uses_observation": true,
      "n4_uses_cross_observation": true,
      "n4_edge_not_worse": true,
      "wrong_weight_rejected": true,
      "wrong_falls_back": false
    },
    "real_gate_passed": false,
    "synthetic_gate_passed": false,
    "full_r106_authorized": false,
    "interpretation": "Real JunHua gate also failed; do not start full R106."
  }
}
```
