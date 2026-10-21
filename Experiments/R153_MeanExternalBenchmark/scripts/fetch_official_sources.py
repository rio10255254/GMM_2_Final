"""Fetch pinned author repositories, source/configuration/license files only."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
SPECS={
 'EDSR':('sanghyun-son/EDSR-PyTorch',['src/model/','src/option.py','src/template.py']),
 'RDN':('yulunzhang/RDN',['RDN_TrainCode/code/model/']),
 'RCAN':('yulunzhang/RCAN',['RCAN_TrainCode/code/model/','RCAN_TrainCode/code/option.py']),
 'NAFNet':('megvii-research/NAFNet',['basicsr/models/archs/','options/train/']),
 'SwinIR':('JingyunLiang/SwinIR',['models/','main_test_swinir.py']),
 'Restormer':('swz30/Restormer',['basicsr/models/archs/','Denoising/Options/','Motion_Deblurring/Options/']),
 'MambaIRv2':('csguoh/MambaIR',['basicsr/archs/','options/train/mambairv2/','requirements.txt','environment.yaml']),
 'USRNet':('cszn/USRNet',['models/','main_test_realapplication.py','main_test_table1.py']),
 'UNet':('lmb-freiburg/Unet-Segmentation',['resources/','caffe/']),
}


def get(url):
    for attempt in range(4):
        response=requests.get(url,timeout=90,headers={'User-Agent':'MOSR-research-reproducibility'})
        if response.status_code==200:return response
        if response.status_code not in (429,500,502,503,504):response.raise_for_status()
        time.sleep(2**attempt)
    response.raise_for_status()


def download(job):
    dest,url=job
    data=get(url).content
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and dest.read_bytes()!=data:raise RuntimeError('Pinned source changed: '+str(dest))
    dest.write_bytes(data)
    return {'path':str(dest.relative_to(ROOT)).replace('\\','/'),'url':url,
            'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}


def main():
    records={}
    for label,(repo,prefixes) in SPECS.items():
        meta=get('https://api.github.com/repos/'+repo).json()
        # Record redirects rather than silently attributing a fork as an author source.
        canonical=meta['full_name']
        commit=get(f'https://api.github.com/repos/{canonical}/commits/{meta["default_branch"]}').json()['sha']
        tree=get(f'https://api.github.com/repos/{canonical}/git/trees/{commit}?recursive=1').json()
        assert not tree.get('truncated')
        paths=[]
        for entry in tree['tree']:
            path=entry['path'];name=Path(path).name
            if entry['type']!='blob':continue
            is_root='/' not in path
            is_record=is_root and (name.lower().startswith(('readme','license','copying')) or name in ('requirements.txt','environment.yaml'))
            is_source=any(path.startswith(prefix) for prefix in prefixes) and Path(path).suffix.lower() in {'.py','.lua','.yaml','.yml','.prototxt','.txt','.json'}
            if is_record or is_source:paths.append(path)
        destination=ROOT/'vendor'/label
        jobs=[(destination/p,f'https://raw.githubusercontent.com/{canonical}/{commit}/{p}') for p in paths]
        with ThreadPoolExecutor(max_workers=8) as pool:
            files=list(pool.map(download,jobs))
        records[label]={'requested_repository':repo,'canonical_repository':canonical,'commit':commit,
                        'url':'https://github.com/'+canonical,'files':files,
                        'pretrained_weights_downloaded':False,
                        'source_tree_paths':[e['path'] for e in tree['tree'] if e['type']=='blob']}
        (ROOT/'config/official_sources.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        print('OFFICIAL SOURCE',label,canonical,commit,'files',len(files),flush=True)
    print('All official source snapshots saved without pretrained weights.',flush=True)


if __name__=='__main__':main()
