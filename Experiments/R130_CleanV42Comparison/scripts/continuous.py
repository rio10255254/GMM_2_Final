"""Final V42 full-field reconstruction and identical continuous LSC readout."""
import sys,ast,importlib.util,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from io_retry import atomic
import cv2,pandas as pd
from PIL import Image
import skimage.segmentation.morphsnakes as morphsnakes
from validation import reference_circle_core as core
from output_guard import guard
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def reader(plan):
    scope=dict(np=np,pd=pd,Path=Path,Image=Image,morphsnakes=morphsnakes,SESSION_TABLE=Path(PROJECT_ROOT / plan['sessions']['path']))
    files=[(REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/run_displacement_lsc.py',['session_prediction','load_grayscale','summarize_pairs']),(REPO/'Experiments/R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py',['reset_curvature_cycle']),(REPO/'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/measure.py',['measure_frame','pair_table'])]
    for path,names in files:
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name in names];assert len(nodes)==len(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return scope
def main():
    assert load(ROOT/'runs/v42_clean/completion.json')['epochs']==32;verify_frozen();plan=load(ROOT/'config/final_evaluation_plan.json');cfg=load(str(PROJECT_ROOT / plan['configuration']['path']));scope=reader(plan)
    for x in plan['protected_sources']:assert sha(str(PROJECT_ROOT / x['path']))==x['sha256']
    out=ROOT/'results/continuous';out.mkdir(exist_ok=False);cp=ROOT/'runs/v42_clean/checkpoints/step04096.pth';m,_=create();payload=torch.load(cp,map_location='cuda');assert payload['step']==4096;m.load_state_dict(payload['model'],strict=True);m.eval();rows=[];records=[];times=[]
    save(out/'started.json',dict(utc=now(),source=record(__file__),plan=record(ROOT/'config/final_evaluation_plan.json'),checkpoint=record(cp),method='V42_clean32'))
    try:
        for n,f in enumerate(plan['frames'],1):
            assert sha(str(PROJECT_ROOT / f['source']['path']))==f['source']['sha256'];raw=cv2.imread(str(PROJECT_ROOT / f['source']['path']),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();tick=time.perf_counter()
            with torch.no_grad():value=guard(x,m(x))[0,0].cpu().numpy()
            times.append(time.perf_counter()-tick);image=np.rint(value*255).clip(0,255).astype(np.uint8)
            folder=out/'images'/f['sequence']/f"frame_{f['frame_index']:04d}";folder.mkdir(parents=True)
            assert cv2.imwrite(str(folder/'reconstruction.png'),image)
            table,points=scope['measure_frame'](core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw.astype(float)/255,image.astype(float)/255,'V42_clean32')
            table.to_csv(folder/'centers.csv',index=False);np.savez_compressed(folder/'boundaries.npz',**points);rows.append(table)
            rec=dict(sequence=f['sequence'],frame_index=f['frame_index'],source=f['source'],image=record(folder/'reconstruction.png'),centers=record(folder/'centers.csv'),boundaries=record(folder/'boundaries.npz'),forward_seconds=times[-1]);save(folder/'record.json',rec);records.append(rec)
            atomic(out/'status.json',dict(status='running',frames=n,total=201,updated_utc=now()))
            if n%20==0:print('V42 real sequence',n,'/201',flush=True)
        centers=pd.concat(rows,ignore_index=True);assert len(centers)==1809;centers.to_csv(out/'centers.csv',index=False)
        fixed=pd.read_csv(str(PROJECT_ROOT / plan['locked_pairs']['path']));adj=pd.read_csv(str(PROJECT_ROOT / plan['adjacent_pairs']['path']))
        for name,pairs in [('locked120',fixed),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
            per,pp=scope['pair_table'](centers,pairs,cfg,'V42_clean32');per.to_csv(out/(name+'_pairs.csv'),index=False);pp.to_csv(out/(name+'_pillar_pairs.csv'),index=False);scope['summarize_pairs'](per).to_csv(out/(name+'_summary.csv'),index=False)
        verify_frozen();save(out/'complete.json',dict(completed_utc=now(),source=record(__file__),frames=201,centers=1809,records=records,median_full_native_forward_seconds=float(np.median(times[1:])),checkpoint=record(cp),no_R129_change=True));atomic(out/'status.json',dict(status='complete',frames=201))
    except BaseException:
        save(out/'failure.json',dict(utc=now(),error=traceback.format_exc()));raise
if __name__=='__main__':main()
