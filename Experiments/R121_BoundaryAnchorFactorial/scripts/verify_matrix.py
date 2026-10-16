"""Verify actual logs/checkpoints/inputs, independently of completion markers."""
from pathlib import Path
import csv,hashlib,json,sys
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def model_hash(model):
    digest=hashlib.sha256()
    for key,value in sorted(model.state_dict().items()):digest.update(key.encode());digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()

def main():
    torch.set_num_threads(4)
    matrix=json.loads((ROOT/'results/matrix_finished_v2.json').read_text())['runs']
    assert len(matrix)==8 and len({r['run_id'] for r in matrix})==8
    assert 'probe_C_s1215001' not in [r['run_id'] for r in matrix]
    assert not (ROOT/'runs/active.lock').exists()
    initial={}
    for seed in [1215001,1215002]:torch.manual_seed(seed);initial[seed]=model_hash(build_model())
    rows=[];inputs=set()
    for row in matrix:
        folder=ROOT/'runs'/row['run_id'];summary=json.loads((folder/'SUMMARY.json').read_text());state=json.loads((folder/'state.json').read_text())
        assert summary==state and summary['status']=='complete'
        assert summary['scratch'] and not summary['checkpoint_loaded']
        assert summary['initialization_sha256']==initial[row['seed']]
        history=list(csv.DictReader((folder/'training_log.csv').open()))
        assert [int(h['epoch']) for h in history]==list(range(1,13)) and sum(int(h['steps']) for h in history)==768
        for h in history:
            assert int(h['steps'])==64
            for key in ['loss','mae_gray','Raw_mae_gray']:assert torch.isfinite(torch.tensor(float(h[key])))
            if row['arm'] in ['C','D'] and int(h['epoch'])>4:
                for key in ['position_before_detail','position_after_detail']:assert float(h[key])>=0
        for epoch in range(1,13):
            value=json.loads((folder/'validation'/f'e{epoch:03d}.json').read_text());assert len(value['rows'])==192
            inputs.add((value['source_sha256'],value['target_sha256']))
        checked=[]
        for epoch in [4,8,12]:
            p=folder/'weights'/f'epoch_{epoch:03d}.pth';saved=torch.load(p,map_location='cpu',weights_only=True)
            assert saved['epoch']==epoch and saved['run_id']==row['run_id'] and saved['arm']==row['arm']
            assert saved['detail_enabled']==(epoch==12) and all(torch.isfinite(t).all() for t in saved['model'].values())
            checked.append({'epoch':epoch,'sha256':sha(p)})
        assert all(sha(ROOT/path)==digest for path,digest in summary['source_sha256'].items())
        rows.append({'run_id':row['run_id'],'epoch_rows':len(history),'steps':768,'checkpoints':checked,'initialization_reproduced':True})
    assert len(inputs)==1
    protected=json.loads((ROOT/'reports/protected_inputs.json').read_text());assert all(sha(p)==h for p,h in protected.items())
    report={'verification':'Eight valid bounded runs, actual records and frozen sources checked; no scientific verdict implied','runs':rows,
            'shared_validation_banks':len(inputs),'protected_inputs_unchanged':len(protected),'initialization_hashes':initial,'excluded_v1_interruption_preserved':(ROOT/'runs/probe_C_s1215001/interruption.json').exists()}
    with (ROOT/'results/matrix_verification.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({'runs_checked':len(rows),'checkpoints_checked':24,'validation_banks':len(inputs),'protected_inputs':len(protected)},indent=2))

if __name__=='__main__':main()
