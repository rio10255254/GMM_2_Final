"""Recover missing PI acquisition BMPs only when their ORIGINAL file hashes match.

R139's independently saved identity diagnostic records a spatially constant gray
offset. Reversing that recorded offset and re-encoding BMP is accepted only if
every byte hashes to the original acquisition fingerprint in the frozen plan.
This never accepts approximate images and never overwrites a source or output.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import cv2
import numpy as np


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def recover(plan_path, diagnostic_path, saved_root, output):
    if output.exists():
        raise FileExistsError('Recovery destination must be a new directory')
    plan=json.loads(plan_path.read_text(encoding='utf-8-sig'))
    diagnostic=json.loads(diagnostic_path.read_text(encoding='utf-8-sig'))
    if not diagnostic or max(x['max_deviation_from_constant_gray'] for x in diagnostic)>0.001:
        raise ValueError('The independent diagnostic does not support constant-offset recovery')
    offset=float(np.mean([x['delta_mean_gray'] for x in diagnostic]))
    identities=[(f['run'],f['index']) for f in plan['frames']]
    if len(set(identities))!=len(identities):
        raise ValueError('Duplicate acquisition identities')
    output.mkdir(parents=True)
    records=[]
    started=time.perf_counter()
    for number,frame in enumerate(plan['frames'],1):
        saved=saved_root/frame['run']/f'{frame["index"]+1:02d}.npz'
        receipt_path=saved.with_suffix('.json')
        if receipt_path.is_file():
            receipt=json.loads(receipt_path.read_text(encoding='utf-8-sig'))
            if receipt.get('output_sha256') and sha(saved)!=receipt['output_sha256']:
                raise ValueError('Saved reconstruction no longer matches its receipt: '+str(saved))
        with np.load(saved,allow_pickle=False) as data:
            image=np.asarray(data['output'],dtype=np.float64)
        if image.shape!=(1544,2064) or not np.isfinite(image).all():
            raise ValueError('Unexpected saved image format')
        original=np.rint(image*255-offset)
        if original.min()<0 or original.max()>255:
            raise ValueError('Recovery would need clipping; refusing an approximate reconstruction')
        ok,encoded=cv2.imencode('.bmp',original.astype(np.uint8))
        actual=hashlib.sha256(encoded).hexdigest() if ok else None
        if actual!=frame['source']['sha256']:
            raise ValueError(f'Restored bytes are NOT the original acquisition: {frame["run"]}/{frame["image"]}')
        relative=Path('raw')/frame['run']/frame['image']
        destination=output/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(encoded)
        if sha(destination)!=actual:
            raise OSError('Saved recovery verification failed: '+str(destination))
        records.append({'path':relative.as_posix(),'bytes':destination.stat().st_size,'sha256':actual,
                        'original_path':frame['source']['path'],'recovery_source':str(saved),
                        'recovery_source_sha256':sha(saved),'run':frame['run'],'index':frame['index'],
                        'original_file_bytes_exact':True})
        if number%31==0 or number==len(plan['frames']):
            progress={'state':'running','verified_original_files':number,'total':len(plan['frames']),
                      'seconds':time.perf_counter()-started}
            (output/'RECOVERY_PROGRESS.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
            print(f'ORIGINAL_BYTES_VERIFIED {number}/{len(plan["frames"])}',flush=True)
    shutil.copy2(plan_path,output/'original_frozen_capture_plan.json')
    shutil.copy2(diagnostic_path,output/'original_R139_identity_diagnostic.json')
    portable=json.loads(json.dumps(plan))
    for frame,record in zip(portable['frames'],records):
        frame['source']['original_historical_path']=frame['source']['path']
        frame['source']['path']=record['path']
    for run in portable['runs']:
        run['positions']['original_csv_file_not_recovered']=True
        run['positions']['available_measurements']='Full per-frame X/Y PI values, time, frame and exposure remain in the frozen capture plan.'
    (output/'portable_capture_plan.json').write_text(json.dumps(portable,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={'schema':1,'state':'complete','files':records,'image_count':len(records),
              'runs':len(plan['runs']),'original_file_hashes_all_match':True,
              'method':'Reverse the independently recorded constant R139 gray offset; accept only original acquisition file SHA-256.',
              'recorded_R139_gray_offset':offset,'frozen_capture_plan_sha256':sha(plan_path),
              'identity_diagnostic_sha256':sha(diagnostic_path),
              'original_positions_csv_bytes_recovered':False,
              'original_per_frame_PI_XY_values_retained_in_frozen_plan':True,
              'seconds':time.perf_counter()-started,
              'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (output/'RAW_RECOVERY_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'RECOVERY_PROGRESS.json').write_text(json.dumps({k:v for k,v in manifest.items() if k!='files'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'},ensure_ascii=False),flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--identity-diagnostic',type=Path,required=True)
    p.add_argument('--saved-output-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();recover(a.plan,a.identity_diagnostic,a.saved_output_root,a.output)


if __name__=='__main__':main()
