-- Snapshot query generated from the locked R106A JunHua summary.
WITH real_modes(mode, center_change_px, edge_ratio, incremental_change_gray) AS (
  VALUES
    ('N=1', 0.08586775918481712, 1.08089896775193, 0.0),
    ('N=2', 0.08528345056232335, 1.0813271856910747, 0.10827854079252575),
    ('N=4', 0.08563303811870482, 1.0821693450177863, 0.22546426378539763)
)
SELECT * FROM real_modes;
