"""Fix the final real comparison before the32epoch endpoint is available."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
def main():
    old=REPO/'Experiments/R129_OpticalPriorHybrid/results/continuous_lsc/plan.json';plan=load(old)
    sources=[record(old),plan['configuration'],plan['sessions'],plan['locked_pairs'],plan['adjacent_pairs']]
    sources +=[record(REPO/'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/measure.py'),record(REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/run_displacement_lsc.py'),record(REPO/'Experiments/R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py')]
    for method in ['Raw','R129']:
        root=REPO/'Experiments/R129_OpticalPriorHybrid/results/continuous_lsc/measurements'/method
        sources +=[record(root/n) for n in ['centers.csv','locked120_pairs.csv','locked120_summary.csv','within_session194_summary.csv']]
    save(ROOT/'config/final_evaluation_plan.json',dict(created_utc=now(),source=record(__file__),frozen_training=record(ROOT/'config/frozen.json'),endpoint_epoch=32,endpoint_step=4096,frames=plan['frames'],configuration=plan['configuration'],sessions=plan['sessions'],locked_pairs=plan['locked_pairs'],adjacent_pairs=plan['adjacent_pairs'],protected_sources=sources,primary_pairs=120,secondary_within_session_pairs=194,repositioning_pairs=3,reader='Exactly the R129/R128 fixed LSC reader with per-pillar curvature reset',comparison_scope='PureV42 architecture freshly trained32epochs on clean synthetic targets versus frozen R129; not matched initialization/optimizer/complete oldV42 recipe',real_images_are_reused_development=True))
    print('Frozen final201frame and120/194pair comparison')
if __name__=='__main__':main()
