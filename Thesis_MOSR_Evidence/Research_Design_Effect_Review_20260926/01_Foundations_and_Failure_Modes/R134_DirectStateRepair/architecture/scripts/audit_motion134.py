from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from infer134 import predict
from motion134 import load_reader
from scipy.optimize import least_squares
import cv2,pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[6]

def main():
    while not (ROOT/'results/motion_screen.json').exists():
        if (ROOT/'results/motion_not_triggered.json').exists():return
        time.sleep(5)
    screen=load(ROOT/'results/motion_screen.json');panel=load(ROOT/'config/motion_panel.json');cfg=load(str(PROJECT_ROOT / panel['configuration']['path']));_,scope=load_reader()(load(str(PROJECT_ROOT / panel['source_plan']['path'])));raw=pd.read_csv(ROOT/'results/motion/Raw_pairs.csv');checks=[];records=[];refits=[]
    def wrong(t):return sum(int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][s]['expected_signed_dx_px'])).sum()) for s,g in t.groupby('sequence'))
    for seed in load(ROOT/'config/study.json')['seeds']:
        counts={}
        for arm in ['A','C']:
            tag=f'{arm}_s{seed}';folder=ROOT/'results/motion'/tag;cp=ROOT/f'runs/R134_{arm}_s{seed}/step0512.pth';assert load(folder/'complete.json')['checkpoint']==record(cp);t=pd.read_csv(folder/'pairs.csv');counts[arm]=wrong(t)
            centers=pd.read_csv(folder/'centers.csv');assert len(centers)==24*9;idx=centers.set_index(['sequence','frame_index','pillar_id'])
            for row in t.itertuples():
                spec=cfg['sequences'][row.sequence];ids=[int(x[0]) for x in spec['centers']];a=idx.loc[[(row.sequence,row.start_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();b=idx.loc[[(row.sequence,row.end_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();v=(b-a)*spec['object_um_per_px'];x,y=np.median(v,0);assert abs(abs(x)-row.measured_step_um)<1e-8;assert abs(np.std(v[:,0],ddof=1)*1000-row.within_grid_sd_nm)<1e-7
            for f in panel['frames']:
                case=f"{f['sequence']}/frame_{f['frame_index']:04d}";d=folder/case;points=np.load(d/'points.npz')['inflection_points'];ct=pd.read_csv(d/'centers.csv')
                for xy,row in zip(points,ct.itertuples()):
                    o=xy.mean(0);z=xy-o
                    def fun(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
                    c=least_squares(fun,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x+o;e=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px));assert e<1e-4;refits.append(e)
                records.append(dict(tag=tag,case=case,source=f['source'],image=record(d/'reconstruction.png'),centers=record(d/'centers.csv'),points=record(d/'points.npz')))
            # One actual whole-field replay per checkpoint, in addition to all
            # saved-point and pair-arithmetic checks.
            f=panel['frames'][0];raw8=cv2.imread(str(PROJECT_ROOT / f['source']['path']),0);m=create(arm,seed);m.load_state_dict(torch.load(cp,map_location='cpu')['model']);m.eval();x=torch.from_numpy(raw8.astype(np.float32)/255)[None,None].cuda();value=predict(m,x)[0,0].cpu().numpy();img=np.rint(value*255).clip(0,255).astype(np.uint8);old=folder/f['sequence']/f"frame_{f['frame_index']:04d}/reconstruction.png";assert np.array_equal(img,cv2.imread(str(old),0));del m;torch.cuda.empty_cache()
        checks.append(dict(seed=seed,A_wrong=counts['A'],C_wrong=counts['C'],Raw_wrong=wrong(raw),passed=counts['C']<=counts['A'] and counts['C']<=wrong(raw)))
    verify();save(ROOT/'results/motion_audit.json',dict(passed=all(r['passed'] for r in checks),wrong_direction_checks=checks,all_pairs_valid=True,independent_center_refits=len(refits),maximum_center_refit_difference_px=max(refits),whole_field_replays=4,records=records,source=record(__file__)));print('Motion audit complete',flush=True)
if __name__=='__main__':main()
