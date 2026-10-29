"""Replay one native full-frame R61 inference per sequence into new folders."""
import os,sys,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2,numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[4]

def main():
    out=ROOT/'results/lsc_comparison';plan=load(out/'plan.json');rows=[]
    cp=plan['checkpoint_R61'];assert sha(str(PROJECT_ROOT / cp['path']))==cp['sha256']
    for seq,entry in plan['R61_manifests'].items():
        frame=next(x for x in plan['frames'] if x['sequence']==seq)
        folder=out/'R61_reproduction'/seq;inputs=folder/'input';inputs.mkdir(parents=True,exist_ok=False)
        src=Path(PROJECT_ROOT / frame['source']['path']);shutil.copyfile(src,inputs/src.name)
        assert sha(inputs/src.name)==frame['source']['sha256']
        cmd=entry['runtime']['command'].copy();cmd[0]=sys.executable
        for option,value in [('--input-dir',str(inputs)),('--recon-root',str(folder/'outputs')),('--output-name','R61_exact_replay')]:cmd[cmd.index(option)+1]=value
        for src_rec in [entry['record'],entry['inference_source']]:assert sha(str(PROJECT_ROOT / src_rec['path']))==src_rec['sha256']
        save(folder/'launch.json',dict(command=cmd,source=frame['source'],expected=frame['R61'],runtime=entry['inference_source'],started_utc=now()))
        env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONIOENCODING']='utf-8'
        with (folder/'run.log').open('x',encoding='utf-8') as log:
            run=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=REPO)
        assert run.returncode==0,folder/'run.log'
        matches=list((folder/'outputs').rglob(src.name));assert len(matches)==1,matches
        a=cv2.imread(str(matches[0]),cv2.IMREAD_UNCHANGED);b=cv2.imread(str(PROJECT_ROOT / frame['R61']['path']),cv2.IMREAD_UNCHANGED)
        assert a.shape==b.shape
        diff=np.abs(a.astype(float)-b.astype(float))
        row=dict(sequence=seq,frame_index=frame['frame_index'],reproduced=record(matches[0]),historical=frame['R61'],exact_pixels=bool(np.array_equal(a,b)),max_gray_difference=float(diff.max()),differing_pixels=int(np.sum(diff!=0)))
        save(folder/'comparison.json',row);rows.append(row);print(json.dumps(row),flush=True)
    save(out/'R61_reproduction.json',dict(completed_utc=now(),comparisons=rows,all_exact=all(x['exact_pixels'] for x in rows),checkpoint=cp,source=record(__file__)))

if __name__=='__main__':main()
