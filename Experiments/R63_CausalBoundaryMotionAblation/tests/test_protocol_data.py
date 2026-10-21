from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT = Path(__file__).resolve().parents[1]
REPO = EXPERIMENT.parents[1]


def test_synthetic_shift_population_is_complete():
    root = EXPERIMENT / "results" / "synthetic_shift_inputs" / "50x_unseen"
    table = pd.read_csv(root / "shift_manifest.csv")
    assert len(table) == 369
    assert (table["case"] == "reference").sum() == 9
    shifted = table.loc[table["case"].eq("shifted")]
    assert len(shifted) == 360
    assert sorted(shifted["magnitude_px"].unique().tolist()) == [0.08, 0.4, 0.8, 2.0, 8.0]
    assert sorted(shifted["direction_deg"].unique().tolist()) == list(range(0, 360, 45))
    assert shifted.groupby(["magnitude_px", "direction_deg"]).size().eq(9).all()


def test_sem_radius_is_converted_to_diameter_once():
    table = pd.read_csv(
        REPO
        / "Thesis_MOSR_Evidence"
        / "Final_Data_Figures"
        / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
        / "cd"
        / "tables"
        / "center9_cd_per_pillar.csv"
    )
    expected_um = 2.0 * table["sem_radius_nm"].to_numpy(float) / 1000.0
    assert np.allclose(expected_um, table["sem_diameter_um"].to_numpy(float), atol=1e-12)


def test_raw_ranked_lock_has_exactly_30_steps_per_sequence():
    table = pd.read_csv(
        REPO
        / "Thesis_MOSR_Evidence"
        / "Final_Data_Figures"
        / "04_V42_NEURAL_NETWORK_RESULTS"
        / "tables"
        / "top30_raw_motion_selection.csv"
    )
    selected = table.loc[table["top30_raw_motion_selected"].astype(bool)]
    assert selected.groupby("sequence").size().to_dict() == {
        "50x_x_0p5um": 30,
        "50x_x_1um": 30,
        "20x_0p5um": 30,
        "20x_1um": 30,
    }
