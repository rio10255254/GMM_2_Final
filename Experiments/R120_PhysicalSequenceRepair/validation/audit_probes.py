"""Read-only consistency checks of the four completed scratch probes."""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load


def main():
    matrix=json.loads((ROOT/'results/probe_matrix.json').read_text())
    assert matrix['status']=='complete' and len(matrix['runs'])==4
    assert not (ROOT/'runs/active.lock').exists()
    summaries=[];validation_hashes=set();initial={}
    for entry in matrix['runs']:
        assert entry['returncode']==0
        folder=ROOT/'runs'/entry['run_id']
        state=json.loads((folder/'state.json').read_text())
        summary=json.loads((folder/'SUMMARY.json').read_text())
        assert state==summary and state['status']=='complete'
        assert state['scratch'] and not state['checkpoint_loaded']
        assert state['completed_epochs']==12 and state['steps']==768
        assert not (folder/'failure.json').exists()
        history=list(csv.DictReader((folder/'training_log.csv').open()))
        assert [int(r['epoch']) for r in history]==list(range(1,13))
        assert all(int(r['steps'])==64 for r in history)
        assert all(math.isfinite(float(r[k])) for r in history for k in ['loss','mae_gray','Raw_mae_gray'])
        for epoch in range(1,13):
            ev=json.loads((folder/'validation'/f'e{epoch:03d}.json').read_text())
            assert len(ev['rows'])==192
            validation_hashes.add((ev['source_sha256'],ev['target_sha256']))
        checkpoints=[]
        for epoch in [4,8,12]:
            p=folder/'weights'/f'epoch_{epoch:03d}.pth'
            saved=torch.load(p,map_location='cpu',weights_only=False)
            assert saved['epoch']==epoch and saved['run_id']==entry['run_id']
            assert saved['detail_enabled']==(epoch==12)
            model=load(p)
            assert all(torch.isfinite(t).all() for t in model.state_dict().values())
            checkpoints.append({'epoch':epoch,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        initial[(entry['arm'],entry['seed'])]=state['initialization_sha256']
        summaries.append({'run_id':entry['run_id'],'e12_mae_gray':float(history[-1]['mae_gray']),
            'Raw_mae_gray':float(history[-1]['Raw_mae_gray']),'seconds':state['elapsed_seconds'],
            'checkpoint_checks':checkpoints,'training_source_sha256':state['source_sha256']})
    assert len(validation_hashes)==1
    for seed in [1185001,1185002]:assert initial['A',seed]==initial['B',seed]
    assert initial['A',1185001]!=initial['A',1185002]
    report={'status':'pass','all_48_validation_input_and_target_pairs_identical':True,
            'matched_initializations_within_seed':True,'independent_initializations_between_seeds':True,
            'all_12_checkpoints_reloaded_and_finite':True,'runs':summaries}
    (ROOT/'results/probe_audit.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
