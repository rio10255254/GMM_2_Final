"""Same fixed circle reader on three real R148v2 and R152 reconstructions."""
from __future__ import annotations
import json,sys
from pathlib import Path
import cv2,numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1];BASE=Path(r'D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF');sys.path.insert(0,str(ROOT));sys.path.append(str(BASE))
from evaluation.measurement_interface import measure_image
from model import Model
from utils import load,model_config,now,save,setup,sha

def main():
 setup(1522802);done=load(ROOT/'runs/formal_8192/training_complete.json');rec=done['deployed_checkpoint'];assert sha(rec['path'])==rec['sha256'];model=Model(model_config(),ROOT).cuda().eval();cp=torch.load(rec['path'],map_location='cpu',weights_only=False);model.load_state_dict(cp['model'],strict=True);assert float(model.deployment_scale)==1
 config=load(BASE/'evaluation/measurement_config.json');tracking=pd.read_csv(BASE/'evaluation/tracking.csv');plan=load(BASE/'evaluation/capture_plan.json');rows=[]
 for frame_number in (0,465,929):
  frame=plan['frames'][frame_number];run=frame['run'];index=frame['index'];seeds=tracking[(tracking.run==run)&(tracking['index']==index)].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy();raw=cv2.imread(frame['source']['path'],cv2.IMREAD_UNCHANGED);x=torch.from_numpy(raw.astype(np.float32)[None,None]/255).cuda()
  with np.load(BASE/'results/reconstruction'/run/f'{index+1:02d}.npz',allow_pickle=False) as z:old=z['output'].astype(np.float64)
  with torch.inference_mode():new=model.forward_tiled(x).cpu().numpy()[0,0].astype(np.float64)
  before,detail_before=measure_image(old,seeds,config);after,detail_after=measure_image(new,seeds,config);a=pd.DataFrame(before).sort_values('pillar_id').reset_index(drop=True);b=pd.DataFrame(after).sort_values('pillar_id').reset_index(drop=True)
  center=np.sqrt((a.center_x_px-b.center_x_px)**2+(a.center_y_px-b.center_y_px)**2)*172.5;diameter=2*(a.radius_px-b.radius_px).abs()*172.5;point=np.linalg.norm(detail_before['points']-detail_after['points'],axis=-1)*172.5
  rows.append(dict(frame_number=frame_number,run=run,index=index,circles=len(a),center_shift_nm_mean=float(center.mean()),center_shift_nm_max=float(center.max()),diameter_change_nm_mean=float(diameter.mean()),diameter_change_nm_max=float(diameter.max()),contour_point_change_nm_mean=float(point.mean()),contour_point_change_nm_max=float(point.max()),image_rms_change_gray=float(np.sqrt(np.square(new-old).mean())*255)))
 result=dict(status='passed',scope='three_preselected_real_frames_nine_circles_each',checkpoint_sha256=rec['sha256'],frames=rows,completed_utc=now());save(ROOT/'results/three_real_measurement_audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
