"""Exercise changed real inference plus both actual objectives on real package."""
import sys,time
from common import *
sys.path.insert(0,str(ROOT))
import torch,numpy as np
from training.engine import create,restore,update,state_digest,checkpoint
from training.data import Bank
from training.objectives import objective
from evaluation.real import evaluate

def main():
    cfg=load(ROOT/'config/study.json');pre=load(ROOT/'results/engineering_preflight.json')
    cp=Path(pre['attempt'])/'resume_test.pth'
    model,opt=create(1285999,'cuda',cfg)
    assert restore(cp,model,opt,{'role':'preflight_only'},'P',1285999)==128
    # This is the existing engineering-smoke model, not a full-training seed.
    summary=evaluate(model,ROOT/'results/nonneutral_real_preflight',record(cp),neutral=False)
    if not summary['completed'] or summary['SEM_rows']!=72 or summary['full_motion_frames']!=12:raise RuntimeError('Incomplete nonneutral real evaluator')
    # Scientific scores are recorded regardless of improvement or degradation.
    # Integration success checks coverage and arithmetic only.
    result=dict(passed=True,nonneutral_real_evaluation=record(ROOT/'results/nonneutral_real_preflight/verification.json'),full_training_weights_used=False,scientific_scores_are_not_readiness_thresholds=True,source_sha256={str(p):sha(p) for p in [ROOT/'evaluation/real.py',ROOT/'training/engine.py',ROOT/'training/objectives.py']})
    save(ROOT/'results/nonneutral_integration.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
