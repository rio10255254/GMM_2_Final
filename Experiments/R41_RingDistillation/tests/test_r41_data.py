from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R41_RingDistillation" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r41_train_profile_has_exact_role_mix():
    import r41_data

    profile = r41_data.PROFILES["r41_ring_recover_train"]
    plan = r41_data.build_plan(REPO_ROOT, profile)

    assert len(plan.pairs) == 1200
    assert plan.count_by_role == {"ring": 700, "shape": 250, "micro": 250}


def test_r41_train_and_micro_val_are_disjoint():
    import r41_data

    train = r41_data.build_plan(REPO_ROOT, r41_data.PROFILES["r41_ring_recover_train"])
    val = r41_data.build_plan(REPO_ROOT, r41_data.PROFILES["micro_val_unseen"])

    assert not (set(train.source_paths) & set(val.source_paths))
