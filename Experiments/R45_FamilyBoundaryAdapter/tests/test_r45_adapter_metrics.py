import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from r45_adapter_metrics import decide_r45_trial_verdict  # noqa: E402


def test_trial_verdict_accepts_target_improvement_without_motion_collapse():
    verdict = decide_r45_trial_verdict(
        base_target_shape=0.3384,
        trial_target_shape=0.3200,
        base_motion=0.3813,
        trial_motion=0.4000,
    )
    assert verdict["is_better"] is True
    assert verdict["target_shape_improvement_pct"] > 5.0


def test_trial_verdict_rejects_motion_collapse_even_if_shape_improves():
    verdict = decide_r45_trial_verdict(
        base_target_shape=0.3384,
        trial_target_shape=0.3000,
        base_motion=0.3813,
        trial_motion=0.5000,
    )
    assert verdict["is_better"] is False
    assert "位移退步過大" in verdict["reason"]
