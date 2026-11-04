-- Snapshot query generated from the locked R106A synthetic summary.
WITH mode_metrics(mode, observation_count, boundary_distance_px, centroid_error_px,
                  transition_center_error_px, transition_width_error_px,
                  image_mae_gray, motion_p95_px, exposure_median_px) AS (
  VALUES
    ('N=1', 1, 0.32053637004078017, 0.16620128487013044, 0.3806201219558716, 0.5154141441869813, 6.8886095099151134, 0.3829804190335049, 0.023202540204943764),
    ('N=2', 2, 0.2946120819877336, 0.12953515196639687, 0.3874908536672592, 0.5103412694854864, 5.802539438009262, 0.2730188484306305, 0.03653288724096894),
    ('N=4', 4, 0.30526368393458786, 0.14520847275257945, 0.4002272039651871, 0.5250205875910362, 5.1070119347423315, 0.1602504846940069, 0.046279671098362785)
)
SELECT *,
       0.08087783626472207 AS boundary_n2_gain,
       0.036154667775294295 AS boundary_n4_regression,
       0.9945950180274649 AS exposure_regression
FROM mode_metrics;
