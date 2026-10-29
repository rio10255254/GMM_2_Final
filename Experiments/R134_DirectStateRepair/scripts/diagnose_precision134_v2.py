"""Follow-up of the observed float/export discrepancy on fixed neighboring frames."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from motion134 import load_reader
from infer134 import predict
import cv2,pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    base=ROOT/'results/cross_axis_diagnosis';out=ROOT/'results/cross_axis_precision_v2';out.mkdir(exist_ok=False)
    panel=load(ROOT/'config/motion_panel.json');plan=load(str(PROJECT_ROOT / panel['source_plan']['path']));cfg=load(str(PROJECT_ROOT / panel['configuration']['path']));core,scope=load_reader()(plan);seq='20x_0p5um';spec=cfg['sequences'][seq]
    save(out/'plan.json',dict(scope='Exploratory precision diagnosis after noticing a float versus8bit discrepancy; cannot amend original admission',case=[16,17],neighbor_frames=[15,16,17,18,19,20],bits=[8,10,12,16],source=record(__file__),original_admission=record(ROOT/'results/long_admission.json')))
    rows=[];rasters={}
    def measure(tag,index,image):
        f=next(f for f in plan['frames'] if f['sequence']==seq and f['frame_index']==index);raw=cv2.imread(f['source']['path'],0).astype(float)/255
        t,p=scope['measure_frame'](core,scope,seq,index,spec,raw,image,tag);dest=out/'measurements'/tag/f'frame_{index:04d}';dest.mkdir(parents=True,exist_ok=False);t.to_csv(dest/'centers.csv',index=False);np.savez_compressed(dest/'points.npz',**p);rows.append(t)
    for index in [16,17]:
        value=np.load(base/f'images/C_s1342001/{index:04d}.npz')['image'];rasters[index]=value;measure('C_float',index,value.astype(float))
        for bits in [8,10,12,16]:
            levels=2**bits-1;image=np.rint(value*levels).astype(float)/levels # Match original float32 multiplication before rounding
            if bits==8:assert np.array_equal(np.rint(image*255).astype(np.uint8),cv2.imread(str(ROOT/f'results/full_motion/{seq}/frame_{index:04d}/reconstruction.png'),0))
            if bits==16:
                dest=out/f'C16_{index:04d}.png';assert cv2.imwrite(str(dest),np.rint(image*levels).astype(np.uint16));loaded=cv2.imread(str(dest),cv2.IMREAD_UNCHANGED);assert loaded.dtype==np.uint16 and np.array_equal(loaded,np.rint(image*levels).astype(np.uint16));image=loaded.astype(float)/levels
            measure(f'C_q{bits}',index,image)
    m=create('C',1342001);m.load_state_dict(torch.load(ROOT/'runs/R134_C_s1342001/step0512.pth',map_location='cpu')['model']);m.eval()
    for index in [15,16,17,18,19,20]:
        f=next(f for f in plan['frames'] if f['sequence']==seq and f['frame_index']==index);assert sha(f['source']['path'])==f['source']['sha256'];raw8=cv2.imread(f['source']['path'],0);measure('Raw_exact',index,raw8.astype(float)/255)
        if index not in rasters:
            x=torch.from_numpy(raw8.astype(np.float32)/255)[None,None].cuda();v=predict(m,x)[0,0].cpu().numpy();np.savez_compressed(out/f'C_float_{index:04d}.npz',image=v);rasters[index]=v;measure('C_float',index,v.astype(float))
        value=rasters[index];png=np.rint(value*255).clip(0,255).astype(np.uint8);old=cv2.imread(str(ROOT/f'results/full_motion/{seq}/frame_{index:04d}/reconstruction.png'),0);assert np.array_equal(png,old)
        measure('C_export8',index,png.astype(float)/255);print('Precision neighbors',index,flush=True)
    t=pd.concat(rows);t.to_csv(out/'centers.csv',index=False)
    # Exact Raw current readout against original retained centers.
    original=pd.read_csv(ROOT.parent/'R129_OpticalPriorHybrid/results/continuous_lsc/measurements/Raw/centers.csv');keys=['sequence','frame_index','pillar_id'];a=t[t.method=='Raw_exact'].set_index(keys);b=original.set_index(keys).loc[a.index];err=float(np.abs(a[['lsc_center_x_px','lsc_center_y_px']].values-b[['lsc_center_x_px','lsc_center_y_px']].values).max());assert err<1e-9
    verify();save(out/'complete.json',dict(neighbor_frames=6,exact_original_png_replays=6,Raw_readout_max_replay_error_px=err,measurement_rows=len(t),actual_uint16_png_roundtrip=True,original_admission_unchanged=sha(ROOT/'results/long_admission.json')==load(out/'plan.json')['original_admission']['sha256']))
    print('Precision probes complete',flush=True)
if __name__=='__main__':main()
