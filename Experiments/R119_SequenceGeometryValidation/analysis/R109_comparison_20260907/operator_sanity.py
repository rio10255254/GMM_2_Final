"""Clarify whether the named position paths also alter transition width."""
import json,sys,importlib.util
from pathlib import Path
import numpy as np,pandas as pd,torch,cv2
import render_v2 as render
from profiles import measure
OUT=Path(__file__).resolve().parent
BENCH=render.ROOT/'analysis/controlled_boundary_factors_20260906'

def main():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    with (OUT/'operator_sanity_protocol.json').open('x') as f:json.dump({'reason':'Real-image position-only paths also change widths; verify on clean known-geometry images without noise.','declared_after_real_profile_results':True,'case_ids':[0,3,5,80,83,85,160,163,165],'selection':'All three primary shapes, dark polarity, clean float, blur sigma 0/1.5/4; fixed existing fixtures.','model_changes':'none, same frozen diagnostic path implementations'},f,indent=2)
    spec=importlib.util.spec_from_file_location('controlled_geometry_for_sanity',BENCH/'run.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    cases=json.loads((BENCH/'protocol.json').read_text())['cases']
    m109=render.r109_model();m119=render.load(render.ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth','cuda')
    rows=[]
    for index in [0,3,5,80,83,85,160,163,165]:
        row=cases[index]
        with np.load(BENCH/'cases'/f'{index:03d}'/'images.npz') as f:raw=f['Raw'];target=f['reference']
        x=torch.from_numpy(raw)[None,None].cuda();a,_=render.r109_paths(m109,x);b=render.r119_paths(m119,x)
        coords,_,_=core.samples(row['shape'],row['dx'],row['dy']);inside,outside=.15*row['gain'],.75*row['gain']
        tp,_,_,tw=core.measure(target,coords,inside,outside)
        data={}
        for name,image in {'Raw':raw,**a,**b}.items():
            pos,valid,_,width=core.measure(image,coords,inside,outside);data[name]=(pos,valid,width)
        for name,(pos,valid,width) in data.items():
            common=valid&data['Raw'][1]&np.isfinite(width)&np.isfinite(data['Raw'][2])
            rows.append({'case_id':index,'shape':row['shape'],'sigma':row['sigma'],'method':name,'common_profiles':int(common.sum()),
                         'median_width_px':float(np.median(width[common])),'median_width_change_vs_Raw_px':float(np.median(width[common]-data['Raw'][2][common])),
                         'median_signed_position_error_px':float(np.median((pos-tp)[common]))})
    pd.DataFrame(rows).to_csv(OUT/'operator_sanity.csv',index=False,mode='x')
    print(pd.DataFrame(rows).query("method in ['Raw','R109_position_only','R119_position_only']")[['shape','sigma','method','median_width_change_vs_Raw_px','median_signed_position_error_px']].round(5).to_string(index=False))

if __name__=='__main__':main()
