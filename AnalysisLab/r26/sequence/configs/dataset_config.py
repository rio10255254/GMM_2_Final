"""Dataset configuration for the three NTU pitch-step sequences."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]

_RECON_ROOT = Path(
    str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_r18_r22_r25_r26/r26_sm035/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260316_190408')
)

_GMF_ROOT = Path(
    str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_r18_r22_r25_r26/r26_sm035/gmf_results/raw')
)

_INPUT_ROOT = Path(r"C:\Users\Rio\Downloads\NTU_ImageDataset")


@dataclass
class DatasetConfig:
    name: str
    short_name: str
    input_dir: Path
    recon_dir: Path
    expected_step_px: float
    gmf_score_path: Path | None = None
    gmf_baseline_step_std: float | None = None


DATASETS: list[DatasetConfig] = [
    DatasetConfig(
        name="Pitch1um_Y_100",
        short_name="pitch1um_y_100",
        input_dir=_INPUT_ROOT / "Pitch1um_Y_100" / "Cropped_Output",
        recon_dir=_RECON_ROOT / "pitch1um_y_100_odd",
        expected_step_px=8.0,
        gmf_score_path=_GMF_ROOT / "pitch8px" / "GMF_score.txt",
        gmf_baseline_step_std=0.205193,
    ),
    DatasetConfig(
        name="Pitch0.1um_Y_60",
        short_name="pitch0p1um_y_60",
        input_dir=_INPUT_ROOT / "Pitch0.1um_Y_60" / "Cropped_Output",
        recon_dir=_RECON_ROOT / "pitch0p1um_y_60_odd",
        expected_step_px=0.8,
        gmf_score_path=_GMF_ROOT / "pitch0p8px" / "GMF_score.txt",
        gmf_baseline_step_std=0.167862,
    ),
    DatasetConfig(
        name="Pitch0.01um_Y_40",
        short_name="pitch0p01um_y_40",
        input_dir=_INPUT_ROOT / "Pitch0.01um_Y_40" / "Cropped_Output",
        recon_dir=_RECON_ROOT / "pitch0p01um_y_40_odd",
        expected_step_px=0.08,
        gmf_score_path=_GMF_ROOT / "pitch0p08px" / "GMF_score.txt",
        gmf_baseline_step_std=0.15772,
    ),
]
