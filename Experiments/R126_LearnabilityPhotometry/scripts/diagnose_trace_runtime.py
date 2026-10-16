"""Preserve and diagnose a cross-runtime replay discrepancy; no threshold change."""
import cv2
from common import *

def main():
    setup();cp=ROOT/'runs/photo_Q_s1265002/step0128.pth';p=torch.load(cp,map_location='cpu',weights_only=True);m=new_model(True,1265002);m.load_state_dict({k:v for k,v in p['model_state'].items() if not k.startswith('observation.')},strict=False);m.eval()
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());item=next(x for x in panel['full_images'] if x['name']=='sem_optical_exposure24');raw=cv2.imread(item['source']['path'],0)
    a=raw.astype(np.float32)/255;b=(raw.astype(float)/255).astype(np.float32);same=np.array_equal(a,b);source=torch.from_numpy(b[266:554,266:554])[None,None].cuda()
    with np.load(ROOT/'results/real_Q_s1265002_step0128/full_images/sem_optical_exposure24/output_float.npz') as d:expected=d['output'][346:474,346:474]
    rows=[]
    for tf32,deterministic in [(False,False),(False,True),(True,False),(True,True)]:
        torch.backends.cudnn.allow_tf32=tf32;torch.backends.cudnn.deterministic=deterministic
        with torch.no_grad():out=m(source).cpu().numpy()[0,0,80:208,80:208]
        rows.append(dict(cudnn_allow_tf32=tf32,cudnn_deterministic=deterministic,maximum_replay_error=float(np.max(np.abs(expected-out))),mean_replay_error=float(np.mean(np.abs(expected-out)))))
    save(ROOT/'results/trace_runtime_diagnosis.json',dict(rows=rows,normalization_routes_bitwise_equal=same,primary_evaluator_source_sha256=sha(ROOT/'scripts/evaluate_real.py'),primary_inference_config='cudnn deterministic=True, TF32 library defaultTrue; all8evaluations same launcher',failed_original_trace_preserved=True,primary_outputs_changed=False,tolerance_unchanged=3e-6))
    print(json.dumps(rows),flush=True)

if __name__=='__main__':main()
