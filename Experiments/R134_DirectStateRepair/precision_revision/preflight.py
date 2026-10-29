from common import *
from precision_io import write_values,read_values
from validation import reference_circle_core as core
import readout as rd
import pandas as pd,cv2
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    out=P/'results/preflight';out.mkdir(exist_ok=False);protected();scope=vars(rd)
    panel=load(E/'config/motion_panel.json');cfg=load(str(PROJECT_ROOT / panel['configuration']['path']));plan=load(str(PROJECT_ROOT / panel['source_plan']['path']));spec=cfg['sequences']['20x_0p5um'];checks=[]
    for i in [16,17]:
        value=np.load(E/f'results/cross_axis_diagnosis/images/C_s1342001/{i:04d}.npz')['image'];path,preview,view16=write_values(out,str(i),value);loaded=read_values(path);assert np.array_equal(value,loaded)
        source=next(f['source']['path'] for f in plan['frames'] if f['sequence']=='20x_0p5um' and f['frame_index']==i);raw=cv2.imread(source,0).astype(float)/255
        t,p=rd.measure_frame(core,scope,'20x_0p5um',i,spec,raw,loaded.astype(float),'P1');old=pd.read_csv(E/f'results/cross_axis_precision_v2/measurements/C_float/frame_{i:04d}/centers.csv');assert np.allclose(t[['lsc_center_x_px','lsc_center_y_px']],old[['lsc_center_x_px','lsc_center_y_px']],rtol=0,atol=1e-9);checks.append(i)
    try:read_values(preview)
    except ValueError:rejected_preview=True
    else:raise AssertionError('Preview accepted as measurement')
    try:write_values(out,'17',value)
    except FileExistsError:rejected_overwrite=True
    else:raise AssertionError('Overwrite accepted')
    save(out/'boolean_serialization.json',dict(true=np.bool_(True),false=np.bool_(False)));assert load(out/'boolean_serialization.json')==dict(true=True,false=False)
    try:save(out/'must_not_exist.json',dict(value=np.nan))
    except ValueError:assert not (out/'must_not_exist.json').exists()
    else:raise AssertionError('Nonfinite accepted')
    save(out/'complete.json',dict(passed=True,actual_real_image_roundtrips=checks,reader_matches_float_diagnosis=True,rejected_preview=rejected_preview,rejected_overwrite=rejected_overwrite,boolean_and_nonfinite_serialization_tested=True));print('Precision IO and unchanged-reader preflight passed')
if __name__=='__main__':main()
