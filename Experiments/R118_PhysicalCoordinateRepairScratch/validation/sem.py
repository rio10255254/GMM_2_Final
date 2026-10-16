"""Reconstruct the shared SEM-matched optical exposures and run locked ACM."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import numpy as np
import pandas as pd
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load,tiled,read,write
SOURCE=ROOT.parent/'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'
SCRIPT=ROOT.parent/'R69_ACMContourSEMValidation/scripts/run_acm_extraction.m'
MATLAB=Path(r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--output',required=True);parser.add_argument('--name',default='R118')
    args=parser.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    model=load(args.checkpoint,'cuda');recon=out/'reconstructions';records=[]
    for exposure in range(13,25):
        source=SOURCE/f'{exposure}.bmp';raw=read(source)
        with torch.inference_mode():result=tiled(model,torch.tensor(raw.astype(np.float32)/255)[None,None].cuda())
        write(recon/source.name,np.rint(result[0,0].cpu().numpy().clip(0,1)*255).astype(np.uint8))
        records.append({'exposure':exposure,'raw_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    (out/'source_manifest.json').write_text(json.dumps(records,indent=2))
    expression=f"addpath('{SCRIPT.parent.as_posix()}');run_acm_extraction('{out.as_posix()}','{SOURCE.as_posix()}','{recon.as_posix()}','{args.name}');"
    completed=subprocess.run([str(MATLAB),'-batch',expression],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (out/'matlab_stdout.log').write_text(completed.stdout,encoding='utf-8');(out/'matlab_stderr.log').write_text(completed.stderr,encoding='utf-8')
    if completed.returncode:raise RuntimeError(completed.stderr[-2000:])
    table=pd.read_csv(out/'results/tables/primary_contour_metrics.csv')
    if len(table)!=864 or table.isna().any().any():raise RuntimeError('SEM evaluation incomplete')
    metric='mean_boundary_distance_pitch_pct'
    per=table.groupby(['method','pillar_id'])[metric].median().unstack('method')
    delta=per['Raw']-per[args.name]
    summary={'status':'complete','independent_pillars':36,'repeated_exposures':12,
             'median_boundary_gain_pitch_pct':float(delta.median()),'improved_pillars':int((delta>0).sum()),
             'source_is_raw':True,'development_evaluation':True}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
if __name__=='__main__':main()
