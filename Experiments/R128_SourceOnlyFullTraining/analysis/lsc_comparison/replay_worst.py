"""Replay the most unfavorable R128-vs-R61 pair using the public trial entry."""
import os,sys,importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd,cv2
from measure import reader,measure_frame

def main():
    out=ROOT/'results/lsc_comparison';plan=load(out/'plan.json');cfg=load(plan['configuration']['path'])
    assert (out/'verification.json').exists()
    worst=pd.read_csv(out/'worst_pairs_vs_R61.csv').iloc[0];seq=str(worst.sequence)
    folder=out/'worst_end_to_end_replay';folder.mkdir(exist_ok=False)
    save(folder/'plan.json',dict(created_utc=now(),selection='largest R128 nominal-error increase versus R61 among all120lockedpairs',sequence=seq,start_frame_index=int(worst.start_frame_index),end_frame_index=int(worst.end_frame_index),source=record(__file__)))
    module_path=ROOT/'trial/restore.py';spec=importlib.util.spec_from_file_location('r128_public_trial_replay',module_path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    core,scope=reader(plan);rows=[]
    for index in [int(worst.start_frame_index),int(worst.end_frame_index)]:
        frame=next(f for f in plan['frames'] if f['sequence']==seq and f['frame_index']==index)
        dest=folder/f'frame_{index:04d}';module.main(frame['source']['path'],dest,'cuda')
        original=load(out/'R128_images'/seq/f'frame_{index:04d}'/'record.json')
        with np.load(dest/'output_float.npz') as a,np.load(original['output_float']['path']) as b:
            assert np.array_equal(a['output'],b['output']) and np.array_equal(a['neural_output'],b['neural_output'])
        assert np.array_equal(cv2.imread(str(dest/'reconstruction.png'),0),cv2.imread(original['image']['path'],0))
        raw=scope['load_grayscale'](Path(frame['source']['path']));image=scope['load_grayscale'](dest/'reconstruction.png')
        measured,_=measure_frame(core,scope,seq,index,cfg['sequences'][seq],raw,image,'R128_P_s1285002')
        old=pd.read_csv(out/'measurements/R128_P_s1285002'/seq/f'frame_{index:04d}'/'centers.csv')
        keys=['lsc_center_x_px','lsc_center_y_px','lsc_radius_px'];err=float(np.max(np.abs(measured[keys].to_numpy()-old[keys].to_numpy())))
        assert err<1e-9
        rows.append(dict(frame_index=index,float_and_neural_arrays_bitwise_equal=True,PNG_bitwise_equal=True,reader_center_max_difference_px=err,trial_record=record(dest/'run_record.json')))
    save(out/'worst_replay_verification.json',dict(completed_utc=now(),sequence=seq,checks=rows,public_trial_source=record(module_path),source=record(__file__),passed=True))
    print(json.dumps(dict(sequence=seq,checks=rows)),flush=True)

if __name__=='__main__':main()
