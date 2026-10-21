"""Actual learned per-stage corrections on the fixed dark real image center."""
import cv2
from common import *

def main():
    setup();torch.backends.cudnn.allow_tf32=True;torch.backends.cudnn.deterministic=True;cp=ROOT/'runs/photo_Q_s1265002/step0128.pth';payload=torch.load(cp,map_location='cpu',weights_only=True);m=new_model(True,1265002)
    learned={k:v for k,v in payload['model_state'].items() if not k.startswith('observation.')};loaded=m.load_state_dict(learned,strict=False);assert not loaded.unexpected_keys;m.eval()
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());item=next(x for x in panel['full_images'] if x['name']=='sem_optical_exposure24');p=item['source']['path'];assert sha(p)==item['source']['sha256']
    whole=cv2.imread(p,0).astype(np.float32)/255;h,w=whole.shape;cy,cx=h//2,w//2;halo=m.required_halo;sl=(slice(cy-64-halo,cy+64+halo),slice(cx-64-halo,cx+64+halo));source=torch.from_numpy(whole[sl])[None,None].cuda();c=lambda x:x[...,halo:halo+128,halo:halo+128]
    with torch.no_grad():d=m.forward_details(source,trace=True)
    arrays={'source':c(source).cpu().numpy()[0,0]};rows=[];sum_correction=torch.zeros_like(c(source))
    for i,t in enumerate(d.traces):
        row={'stage':i+1};closure=t['state_before']+t['prior_correction']+t['observation_correction']+t['projection_correction']-t['state_after'];row['maximum_algebraic_closure_error']=float(closure.abs().max())
        for kind in ['prior_correction','observation_correction','projection_correction']:
            native=c(m.observation.integrate(t[kind]));arrays[f'stage{i+1}_{kind}']=native.cpu().numpy()[0,0];sum_correction+=native
            row[kind+'_mean_absolute_gray']=float(native.abs().mean()*255)
            row[kind+'_maximum_absolute_gray']=float(native.abs().max()*255)
        arrays[f'stage{i+1}_output']=c(t['native_output']).cpu().numpy()[0,0];rows.append(row)
    telescoping=float((c(source)+sum_correction-c(d.output)).abs().max())
    saved=ROOT/'results/real_Q_s1265002_step0128/full_images/sem_optical_exposure24/output_float.npz'
    with np.load(saved) as a:expected=a['output'][cy-64:cy+64,cx-64:cx+64]
    parity=float(np.max(np.abs(expected-arrays['stage4_output'])))
    out=ROOT/'results/learned_real_trace_matched';out.mkdir(exist_ok=False);np.savez_compressed(out/'native_stage_arrays.npz',**arrays)
    result=dict(runtime={'cudnn_allow_tf32':True,'cudnn_deterministic':True,'matches_frozen_primary_evaluator':True},original_cross_runtime_failure='results/learned_real_trace/summary.json',checkpoint_sha256=sha(cp),source=item['source'],actual_source_window_yxyx=[cy-64-halo,cx-64-halo,cy+64+halo,cx+64+halo],supervised_core_yxyx=[cy-64,cx-64,cy+64,cx+64],source_selection='center128 of the same fixed exposure24 full image',rows=rows,sum_of_native_corrections_error=telescoping,parity_to_saved_full_image=parity,passed=telescoping<3e-6 and parity<3e-6 and all(x['maximum_algebraic_closure_error']<3e-6 for x in rows),calibration_qualified=False,interpretation='Computational attribution only. Prior corrections are not pure position/width/detail causes and are not physical truth.')
    save(out/'summary.json',result);print(json.dumps(result),flush=True)
    if not result['passed']:raise ValueError('Learned trace decomposition failed')

if __name__=='__main__':main()
