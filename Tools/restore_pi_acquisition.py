"""Restore the ORIGINAL camera acquisition ZIP and verify all frozen source records.

Only the 930 BMP photographs and 30 original positions.csv files declared in
the historical capture plan are accepted. Files are copied byte for byte from
the original archive. No reconstruction model or image transformation is used.
"""
import argparse
import csv
import datetime
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

from research_recovery import safe_relative, write_json, digest


def restore(archive, plan_path, output, recovered_comparison=None):
    if output.exists():
        raise FileExistsError('Original acquisition destination must be new')
    plan=json.loads(plan_path.read_text(encoding='utf-8-sig'))
    if len(plan['frames'])!=930 or len(plan['runs'])!=30:
        raise ValueError('Unexpected acquisition scope')
    prefix='20260902_100MF_uncertainty/20260903/'
    expected={prefix+f['run']+'/'+f['image']: f['source']['sha256'] for f in plan['frames']}
    expected.update({prefix+r['run']+'/positions.csv':r['positions']['sha256'] for r in plan['runs']})
    frames_by_run={r['run']:[f for f in plan['frames'] if f['run']==r['run']] for r in plan['runs']}
    rows=[];position_columns=None;recovered_matches=0
    with zipfile.ZipFile(archive) as z:
        names=[i.filename for i in z.infolist() if not i.is_dir()]
        if len(names)!=960 or set(names)!=set(expected):
            raise ValueError('Original archive does not contain precisely the declared 930 photographs and 30 position logs')
        output.mkdir(parents=True)
        for number,name in enumerate(sorted(names),1):
            data=z.read(name)  # ZipFile checks the original entry CRC too.
            sha=hashlib.sha256(data).hexdigest()
            if sha!=expected[name]:
                raise ValueError('Original acquisition hash mismatch: '+name)
            relative=Path('raw')/safe_relative(name[len(prefix):])
            target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(data)
            if digest(target)!=sha:
                raise OSError('Written original source changed: '+str(target))
            if name.endswith('positions.csv'):
                reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
                position_columns=reader.fieldnames
                observations=list(reader);run=relative.parent.name
                if len(observations)!=31:
                    raise ValueError('Position log is incomplete')
                for actual, frozen in zip(observations,sorted(frames_by_run[run],key=lambda f:f['index'])):
                    if not (actual['image']==frozen['image'] and float(actual['x'])==frozen['pi_x_um']
                            and float(actual['y'])==frozen['pi_y_um'] and actual['recorded_at']==frozen['recorded_at']
                            and int(actual['frame'])==frozen['frame'] and float(actual['exposure_us'])==frozen['exposure_us']):
                        raise ValueError('Original instrument record differs from frozen experiment inputs')
            elif recovered_comparison:
                candidate=recovered_comparison/relative
                if digest(candidate)!=sha:
                    raise ValueError('R139 restored copy differs from the direct camera archive')
                recovered_matches+=1
            rows.append({'path':relative.as_posix(),'bytes':len(data),'sha256':sha,
                         'original_archive_member':name,'source_kind':'direct_original_acquisition_archive'})
            if number%96==0:print(f'ORIGINAL_ARCHIVE_FILES_VERIFIED {number}/960',flush=True)
    shutil.copy2(plan_path,output/'original_frozen_capture_plan.json')
    portable=json.loads(json.dumps(plan))
    for frame in portable['frames']:
        frame['source']['historical_path']=frame['source']['path']
        frame['source']['path']='raw/'+frame['run']+'/'+frame['image']
    for run in portable['runs']:
        run['positions']['historical_path']=run['positions']['path']
        run['positions']['path']='raw/'+run['run']+'/positions.csv'
    write_json(output/'portable_capture_plan.json',portable)
    manifest={'schema':1,'state':'complete','source_kind':'direct_original_acquisition_archive',
              'archive_name':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive),
              'original_cloud_file_url':'https://drive.google.com/file/d/18wjpjSrhOT39XoBxDU5lHISxc-Wg8pVl/view',
              'photographs':930,'original_position_logs':30,'scans':30,'photographs_per_scan':31,
              'all_960_original_file_hashes_match_frozen_capture_plan':True,
              'all_original_PI_XY_time_frame_exposure_values_match':True,
              'position_log_columns':position_columns,'R139_restored_copies_matching_originals':recovered_matches,
              'original_source_not_derived_from_model':True,'files':rows,
              'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    write_json(output/'ORIGINAL_ACQUISITION_MANIFEST.json',manifest)
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'},ensure_ascii=False),flush=True)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--compare-r139-recovered',type=Path)
    a=p.parse_args();restore(a.archive,a.plan,a.output,a.compare_r139_recovered)


if __name__=='__main__':main()
