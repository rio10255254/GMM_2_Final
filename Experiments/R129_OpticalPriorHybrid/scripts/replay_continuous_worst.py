"""Exercise the portable full-field entry on the worst paired regression and repeat LSC."""
import sys,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from continuous_common import *
import cv2
def main():
    verified=load(OUT/'analysis_verified.json');plan=load(OUT/'plan.json');pkg=Path(plan['package'])
    item=next(x for x in verified['largest_regressions'] if x['reference']=='R128_P_s1285002' and x['metric']=='nominal_abs_error_nm')
    inputs=pkg/'results/continuous_lsc_replay_inputs';inputs.mkdir(exist_ok=False)
    targets=[f for f in plan['frames'] if f['sequence']==item['sequence'] and f['frame_index'] in [item['start'],item['end']]];assert len(targets)==2
    for f in targets:shutil.copy2(f['source']['path'],inputs/f"frame_{f['frame_index']:04d}.bmp")
    command=[sys.executable,'-u','-B',str(pkg/'addons/full_field/infer_fullfield.py'),'--input-dir',str(inputs),'--output-name','continuous_lsc_worst_replay']
    with (OUT/'worst_public_replay.log').open('xb') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
    assert r.returncode==0
    core,scope=reader(plan);cfg=load(plan['configuration']['path']);records=[]
    for f in targets:
        path=pkg/'results/inference/continuous_lsc_worst_replay'/f"frame_{f['frame_index']:04d}.png"
        expected=load(OUT/'images'/f['sequence']/f"frame_{f['frame_index']:04d}"/'record.json')
        assert np.array_equal(cv2.imread(str(path),0),cv2.imread(expected['image']['path'],0))
        raw=scope['load_grayscale'](Path(f['source']['path']));image=scope['load_grayscale'](path)
        table,_=scope['measure_frame'](core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw,image,'R129')
        old=pd.read_csv(OUT/'measurements/R129'/f['sequence']/f"frame_{f['frame_index']:04d}"/'centers.csv')
        diff=float(abs(table[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy()-old[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy()).max());assert diff<1e-8
        records.append(dict(sequence=f['sequence'],frame_index=f['frame_index'],public_image=record(path),image_exact=True,LSC_max_difference_px=diff))
    save(OUT/'worst_replay_verified.json',dict(completed_utc=now(),source=record(__file__),selection=item,records=records,public_addon_manifest=record(pkg/'addons/full_field/ADDON_MANIFEST.json'),no_new_training_or_model_change=True))
    print('Worst pair public full-field replay and LSC match',item,flush=True)
if __name__=='__main__':main()
