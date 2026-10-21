import pandas as pd
from photometry_data import *

def main():
    setup();cfg=json.loads((ROOT/'config/reference_diagnostic.json').read_text());records=[]
    for seed in [1265001,1265002]:
        records.append(dict(arm='initial_shared',seed=seed,step=0,path=ROOT/'runs/photometry_initial'/f'P_s{seed}_step0000.pth'))
        for arm in ['P','Q']:records.append(dict(arm=arm,seed=seed,step=128,path=ROOT/'runs'/f'photo_{arm}_s{seed}'/'step0128.pth'))
    rows=[];start=time.perf_counter()
    for rec in records:
        m=new_model(True,rec['seed']);payload=torch.load(rec['path'],map_location='cpu',weights_only=True)
        learned={k:v for k,v in payload['model_state'].items() if not k.startswith('observation.')}
        missing=m.load_state_dict(learned,strict=False);assert not missing.unexpected_keys and all(k.startswith('observation.') for k in missing.missing_keys)
        m.eval()
        for idx in cfg['source_indices']:
            for ci,name in enumerate(cfg['conditions']):
                slot=dict(step=idx*3+ci+1,index=idx,contrast_scale=1. if name!='dark_low_contrast' else .125,placement_fraction=1. if name=='bright_full_contrast' else 0.,photometry_cell=-1,noise_seed=1269900+10*idx+ci)
                source,a,meta,e=batch(m,slot,name!='original');l,u,x0,x1=meta['training_core_slice'];c=lambda x:x[...,l:u,x0:x1]
                with torch.no_grad():
                    d=m.forward_details(source);native=(c(d.output-a['target'])).abs().flatten(1).mean(1)*255
                    latent=(d.latent-a['latent_target'])[...,l*4:u*4,x0*4:x1*4].abs().flatten(1).mean(1)*255
                    obs=(c(m.observation(d.latent)-a['noiseless'])).abs().flatten(1).mean(1)*255
                    raw=(c(source-a['target'])).abs().flatten(1).mean(1)*255
                for v in range(2):rows.append(dict(arm=rec['arm'],seed=rec['seed'],step=rec['step'],index=idx,category=meta['category'],condition=name,view=v,native_mae_gray=float(native[v]),latent_mae_gray=float(latent[v]),observation_noiseless_mae_gray=float(obs[v]),raw_native_mae_gray=float(raw[v]),actual_input_sha256=thash(source),checkpoint_sha256=sha(rec['path'])))
        print(json.dumps(dict(model={k:str(v) for k,v in rec.items()},rows=len(rows),seconds=time.perf_counter()-start)),flush=True)
    out=ROOT/'results/reference_diagnostic';out.mkdir(exist_ok=False)
    df=pd.DataFrame(rows);df.to_csv(out/'measurements.csv',index=False)
    summary=df.groupby(['arm','seed','step','condition'],as_index=False)[['native_mae_gray','latent_mae_gray','observation_noiseless_mae_gray','raw_native_mae_gray']].mean();summary.to_csv(out/'summary.csv',index=False)
    equal=df.groupby(['index','condition','view']).actual_input_sha256.nunique().eq(1).all();assert equal
    save(out/'verification.json',dict(rows=len(rows),common_actual_inputs_verified=bool(equal),protocol_sha256=sha(ROOT/'config/reference_diagnostic.json'),seconds=time.perf_counter()-start,unseen_holdout=False))
if __name__=='__main__':main()
