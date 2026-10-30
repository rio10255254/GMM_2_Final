"""Phase 4 hand fixes after apply: paths inside strings, which a decision can only keep.
Traing_Progress split in two: organized_* batches went to Experiments/Legacy, training_progress_* runs to
Experiments/Training_Runs. Every replacement must match exactly once; one already made is skipped, so this reruns."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]    # the project root
FIXES = {
    'Experiments/R46_CornerAwareFineTune/scripts/run_r46_pipeline.py': [
        ('not found in Traing_Progress/")', 'not found in Experiments/Training_Runs/")')],
    # logical project paths of archived snapshots, matched against the Release manifests (moved in phase 5)
    'Tools/project_reproducibility_audit.py': [
        ("[('main_training_history','Traing_Progress')]", "[('main_training_history','Experiments/Training_Runs')]"),
        ("'logical':'Traing_Progress/'+snapshot.parent.parent.name", "'logical':'Experiments/Legacy/'+snapshot.parent.parent.name")],
    'Tools/replay_legacy_multiscale_selection.py': [
        ('relative = f"Traing_Progress/{folder}/selected/reports/', 'relative = f"Experiments/Legacy/{folder}/selected/reports/')],
    'Tools/replay_shared_model_history.py': [
        ("relative='Traing_Progress/'+run+'/epoch_'", "relative='Experiments/Training_Runs/'+run+'/epoch_'")],
    # ROOT.parents[1] held LabSystem_MOSR; with LabSystem at the root it is the project root, so the original
    # 'LabSystem_MOSR/...' joins are right as written. apply had climbed back into Thesis_MOSR_Evidence.
    'LabSystem_MOSR/psf_calibration/scripts/validate_inner_circle_psf_fit.py': [
        ("return (ROOT.parents[1] / 'Thesis_MOSR_Evidence') / path_text\n", "return ROOT.parents[1] / path_text\n"),
        ("return (ROOT.parents[1] / 'Thesis_MOSR_Evidence') / path\n", "return ROOT.parents[1] / path\n")],
}
for rel, pairs in FIXES.items():
    p = REPO / rel
    s = p.read_bytes().decode('utf-8')
    for old, new in pairs:
        if s.count(old) == 0 and new in s:
            continue
        assert s.count(old) == 1, (rel, old)
        s = s.replace(old, new)
    p.write_bytes(s.encode('utf-8'))
    print('fixed', rel)
