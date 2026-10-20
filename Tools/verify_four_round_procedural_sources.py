"""Verify original on-demand periodic rendering and R98 supplemental sampling."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from dataclasses import fields
import importlib.util
import os
from pathlib import Path
import sys

from four_round_recovery_common import ROUNDS, new_output, read_json, sha, write_json

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value
    spec.loader.exec_module(value)
    return value

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path)
    a=p.parse_args();os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(1)
    from verify_r93_shared_recovery import fingerprint
    out=new_output(a.root,a.output);result={'periodic':{},'R98_texture_focus':{}}
    for n in [97,98]:
        folder=a.root/'Experiments'/ROUNDS[n];design=read_json(folder/'config/experiment_design.json')
        seed=design['independence']['seed'];source=folder/'training/periodic_disambiguation.py'
        module=load(f'r{n}_preserved_periodic',source);rows={}
        for label,actual_seed in [('train_e17_b4',seed+17*1009+4),('train_e33_b4',seed+33*1009+4),
                                  ('train_e48_b4',seed+48*1009+4),('validation',seed+970000)]:
            batch=module.make_periodic_batch(2,256,actual_seed,device='cpu')
            rows[label]={'seed':actual_seed,'fields':{f.name:fingerprint(getattr(batch,f.name)) for f in fields(batch)}}
        result['periodic'][str(n)]={'source_sha256':sha(source),'samples':rows}
        print('NATIVE_PERIODIC_SOURCE_VERIFIED',n,len(rows),flush=True)
    folder=a.root/'Experiments'/ROUNDS[98];design=read_json(folder/'config/experiment_design.json')
    package=a.root/'Experiments/R93_RecoverableDetailSeparatedScratch/data/r93_formal'
    manifest=read_json(package/'manifest.json')
    source=folder/'training/r98_dataset.py';module=load('r98_preserved_focus_dataset',source)
    active=read_json(folder/'runs/active_run.json')
    with (folder/'runs'/('training_'+active['run_id'])/'training_log.csv').open(encoding='utf-8-sig',newline='') as stream:
        observed={int(row['epoch']):row for row in csv.DictReader(stream)}
    for epoch in [1,17,48]:
        row=observed[epoch]
        patch,core,scene_batch=(int(row[key]) for key in ['patch','core','scene_batch'])
        seed=design['independence']['seed']
        dataset=module.R98SceneDataset(package,manifest,'train',patch,core,epoch,master_seed=seed+170003)
        sampler=module.TextureFocusBatchSampler(dataset,scene_batch,seed+epoch*1009,design['data']['texture_focus_roles'],16)
        batches=list(sampler);roles=[dataset.role_at(i) for batch in batches for i in batch]
        if len(batches)!=16 or set(roles)!=set(design['data']['texture_focus_roles']):
            raise ValueError('Supplemental texture-role coverage changed')
        result['R98_texture_focus'][str(epoch)]={'patch':patch,'core':core,'observed_scene_batch':scene_batch,
            'batches':batches,'roles':roles,'role_counts':dict(sorted(Counter(roles).items()))}
    if a.reference and result!=read_json(a.reference)['values']:
        raise ValueError('Independent periodic/sampling replay differs')
    write_json(out/'PROCEDURAL_SOURCE_VERIFIED.json',{'status':'PASS','device':'cpu','historical_training_repeated':False,
        'independent_reference_matched':bool(a.reference),'values':result})

if __name__=='__main__':main()
