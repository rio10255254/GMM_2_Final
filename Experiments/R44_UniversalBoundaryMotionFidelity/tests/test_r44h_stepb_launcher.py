from pathlib import Path
from types import SimpleNamespace
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_stepb_launcher_is_single_teacher_large_region_probe():
    import launch_r44h_stepb

    assert launch_r44h_stepb.TARGET_STATIC_STAGES == ("stage_38_boundary_regions",)
    assert launch_r44h_stepb.TARGET_MOTION_STAGES == ("stage_45_motion_regions",)
    assert launch_r44h_stepb.STUDENT_START_CHECKPOINT.exists()
    assert launch_r44h_stepb.LARGE_REGION_TEACHER_CHECKPOINT.exists()


def test_stepb_configure_enables_region_kd_without_global_kd():
    import launch_r44h_stepb

    class FakeCfg:
        pass

    class FakeTrainer:
        CFG = FakeCfg()
        MODEL_NAME_BASE = ""

    args = SimpleNamespace(
        candidate="r44h_stepb_region_kd_main",
        base_checkpoint=launch_r44h_stepb.STUDENT_START_CHECKPOINT,
        teacher_checkpoint=launch_r44h_stepb.LARGE_REGION_TEACHER_CHECKPOINT,
        num_epoch=12,
        max_train_batches=50,
        val_ratio=0.05,
        batch_size=2,
        val_batch_size=4,
        device="cpu",
    )
    static_dir = REPO_ROOT / "Training_Data" / "r42_microscopy_boundary_fidelity" / "r42_boundary_research_train"
    motion_dir = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion" / "r44_motion_research_train"

    summary = launch_r44h_stepb.configure_stepb(FakeTrainer, args, static_dir, motion_dir)
    cfg = FakeTrainer.CFG

    assert cfg.KD_ENABLE is False
    assert cfg.REGION_KD_ENABLE is True
    assert cfg.REGION_KD_TEACHER_PATH == str(launch_r44h_stepb.LARGE_REGION_TEACHER_CHECKPOINT)
    assert cfg.REGION_KD_WEIGHT > 0.0
    assert cfg.TRAIN_INCLUDE_SUBDIRS == launch_r44h_stepb.TARGET_STATIC_STAGES
    assert cfg.MOTION_INCLUDE_SUBDIRS == launch_r44h_stepb.TARGET_MOTION_STAGES
    assert cfg.RESUME_CHECKPOINT == str(launch_r44h_stepb.STUDENT_START_CHECKPOINT)
    assert summary["teacher_id"] == "r44b_from_combo"
