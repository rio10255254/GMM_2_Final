"""Verify data provenance, source images, objective connectivity, and tiling."""
from pathlib import Path
import hashlib
import json
import sys
import cv2
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model
from training.dataset import Scenes,flatten
from training.objectives import objective,location_xy
from inference.run import tiled
from torch.utils.data._utils.collate import default_collate

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    torch.set_num_threads(4);torch.manual_seed(118);config=json.loads((ROOT/'config/experiment.json').read_text())
    package=ROOT/config['data']['package_root'];manifest=json.loads((package/'manifest.json').read_text())
    checks={'counts':manifest['counts']=={'train':5000,'validation':512},
            'optics_before_downsampling':manifest['source_blurred_at_8x_before_downsampling'],
            'no_real_training_pixels':manifest['training_uses_real_pixels'] is False,
            'reference_replay_exact':all(r['reference_replay_max_gray']==0 for r in manifest['records'])}
    train={r['scene_index'] for r in manifest['records'] if r['split']=='train'}
    val={r['scene_index'] for r in manifest['records'] if r['split']=='validation'}
    checks['zero_partition_overlap']=not bool(train&val)
    coverage=[e for stage in config['training']['stages'] for e in range(stage['epochs'][0],stage['epochs'][1]+1)]
    checks['configured_stage_coverage']=coverage==list(range(1,config['training']['formal_epochs']+1))
    checks['real_raw_checksums']=all(sha(ROOT/i['path'])==i['sha256'] for i in config['validation']['real_raw_inputs'])
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model=build_model().to(device).eval()
    with torch.no_grad():
        for head in (model.action_head,model.detail_head):
            head.weight.normal_(0,.005);head.bias.normal_(0,.01)
    image=torch.rand(1,1,513,551,device=device)
    with torch.inference_mode():
        direct=model(image);cut=tiled(model,image,core=192)
    difference=(direct-cut).abs()*255
    parity={'mean_gray':float(difference.mean()),'max_gray':float(difference.max()),'p99_gray':float(torch.quantile(difference.flatten(),.99))}
    checks['nontrivial_tile_parity']=parity['max_gray']<.05
    checks['nontrivial_output']=float((direct-image).abs().max())>1e-5
    ds=Scenes('train',limit=8);b=flatten(default_collate([ds[0],ds[1]]),device)
    details=model.forward_details(b['source'])
    loss,terms=objective(model,details,b,config['training']['weights'])
    checks['all_configured_objectives_used']=set(terms)==set(config['training']['weights'])
    grad=torch.autograd.grad(terms['pair_geometry'],model.groups()['geometry'],retain_graph=True,allow_unused=True)
    norm=sum(float(g.abs().sum()) for g in grad if g is not None)
    checks['pair_geometry_updates_geometry']=norm>0
    checks['all_objectives_finite']=all(torch.isfinite(v).all().item() for v in terms.values())
    result={'status':'pass' if all(checks.values()) else 'fail','checks':checks,'tile_parity':parity,
            'geometry_pair_gradient_abs':norm,'config_sha256':sha(ROOT/'config/experiment.json'),
            'manifest_sha256':sha(package/'manifest.json'),'model_sha256':sha(ROOT/'model/network.py')}
    destination=ROOT/'validation/preflight.json';destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(result,indent=2))
    if result['status']!='pass':raise RuntimeError('preflight failed')
if __name__=='__main__':main()
