from common import *
from precision_io import write_values,read_values
from infer134 import predict
from validation import reference_circle_core as core
from audit import refit,pair_audit,full_checks
import readout as rd
import cv2,pandas as pd
def main():
    pkg=Path(load(P/'results/package_built.json')['path']);run=pkg/'results/training/r134p_long_01';done=load(run/'completion.json');cp=pkg/done['final_checkpoint']['path'];assert sha(cp)==done['final_checkpoint']['sha256'];state=torch.load(cp,map_location='cpu');assert state['step']==8192
    for path,h in state['binding']['runtime_files'].items():assert sha(pkg/path)==h
    m=create('C',1342001);m.load_state_dict(state['model'],strict=True);m.eval();out=P/'results/final_full201';out.mkdir(exist_ok=False);panel=load(E/'config/motion_panel.json');plan=load(panel['source_plan']['path']);cfg=load(panel['configuration']['path']);tables=[];records=[];fits=[]
    save(out/'started.json',dict(checkpoint=record(cp),source=record(__file__),population=record(panel['source_plan']['path'])))
    for j,f in enumerate(plan['frames']):
        assert sha(f['source']['path'])==f['source']['sha256'];raw8=cv2.imread(f['source']['path'],0);x=torch.from_numpy(raw8.astype(np.float32)/255)[None,None].cuda();value=predict(m,x)[0,0].cpu().numpy();d=out/f['sequence']/f"frame_{f['frame_index']:04d}";exact,preview,high=write_values(d,'reconstruction',value);v=read_values(exact);t,p=rd.measure_frame(core,vars(rd),f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw8.astype(float)/255,v.astype(float),'R134_P1_long8192');t.to_csv(d/'centers.csv',index=False);np.savez_compressed(d/'points.npz',**p);fits+=refit(p['inflection_points'],t);tables.append(t);records.append(dict(source=f['source'],values=record(exact),centers=record(d/'centers.csv'),points=record(d/'points.npz')));atomic(out/'status.json',dict(frames=j+1,total=201));print('Final precision comparison',j+1,'/201',flush=True)
    ct=pd.concat(tables);ct.to_csv(out/'centers.csv',index=False);raw=pd.read_csv(E.parent/'R129_OpticalPriorHybrid/results/continuous_lsc/measurements/Raw/centers.csv');short=pd.read_csv(P/'results/motion/C_s1342001/centers.csv');adj=pd.read_csv(plan['adjacent_pairs']['path']);summaries=[];checks=[];pair_checks=0
    for population,ps in [('locked120',pd.read_csv(plan['locked_pairs']['path'])),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
        result={}
        for method,centers in [('Raw',raw),('C_short512',short),('C_long8192',ct)]:
            t,_=rd.pair_table(centers,ps,cfg,method);pair_checks+=pair_audit(centers,t,cfg);t.to_csv(out/f'{population}_{method}_pairs.csv',index=False);result[method]=t
            if population!='repositioning3':s=rd.summarize_pairs(t);s['population']=population;summaries.append(s)
        if population!='repositioning3':checks+=full_checks(result['C_long8192'],result['Raw'],cfg,load(P/'config/protocol.json')['rules'],population)
    for f in panel['frames']:
        v=read_values(out/f['sequence']/f"frame_{f['frame_index']:04d}/reconstruction.npy");expected=read_values(run/f"evaluations/step08192/real/{f['sequence']}_{f['frame_index']:04d}.npy");assert np.array_equal(v,expected)
    assert len(ct)==len(fits)==1809;pd.concat(summaries).to_csv(out/'summary.csv',index=False);protected();save(out/'complete.json',dict(frames=201,independent_center_refits=len(fits),max_refit_error_px=max(fits),independent_pair_checks=pair_checks,package_full_panel_exact_replays=24,checks=checks,all_original_tolerances_met=all(c['passed'] for c in checks),records=records,checkpoint=record(cp),model_promoted=False));print('Final full201 comparison complete; no automatic promotion',flush=True)
if __name__=='__main__':main()
