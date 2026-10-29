"""Plan exact missing model objects; keep every source location separately.

This is preservation, not promotion or an inference-quality verdict. Byte-equal
objects from existing releases are reused, including initialization and failure
snapshots. Metadata labels alone never decide scientific model identity.
"""
import argparse,gzip,json
from collections import Counter
from pathlib import Path

from research_recovery import safe_relative,write_json

def json_gz(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--operation',type=Path,required=True)
    p.add_argument('--batch-bytes',type=int,default=16_000_000_000);a=p.parse_args();op=a.operation
    with gzip.open(op/'PUBLISHED_CATALOG.jsonl.gz','rt',encoding='utf-8') as stream:published=[json.loads(line) for line in stream]
    known={(r['sha256'],r['bytes']) for r in published}
    prior_by_path={r['path'].casefold():r['sha256'] for r in published}
    for name in ['training_history_bundle','context_batch_001_bundle']:
        manifest=json_gz(op/name/'RESEARCH_ASSETS.json.gz')
        known.update((r['sha256'],r['bytes']) for r in manifest['files'])
    with gzip.open(op/'HASHED_MODELS_FILES.jsonl.gz','rt',encoding='utf-8') as stream:rows=[json.loads(line) for line in stream]
    if any(r['sha256'] is None for r in rows):raise ValueError('Finish all model content checks first')
    canonical={r['path_key']:r['sha256'] for r in rows if r['origin']=='D_worktree'}
    normalized=[];destinations={};objects={};skipped=Counter();archive=Path(r'H:\GMM_2_Final_Archive')
    def rank(row):
        low=row['logical_path'].casefold()
        return (any(s in low for s in ['aborted_oversized','research_design_effect_review','research_round_library']),row['origin']!='D_worktree',len(row['source']))
    for row in rows:
        if '/portable_runtime/' in '/'+row['logical_path'].casefold():skipped['generic_runtime']+=1;continue
        path=row['logical_path'];key=path.casefold();source=Path(row['source'])
        if row['origin']!='D_worktree' and ((key in canonical and canonical[key]!=row['sha256']) or (key in prior_by_path and prior_by_path[key]!=row['sha256']) or (key in destinations and destinations[key]!=row['sha256'])):
            path='Archive/Historical_Archive/'+source.relative_to(archive).as_posix();key=path.casefold()
        if key in destinations:
            if destinations[key]!=row['sha256']:raise ValueError('Unresolved historical model version: '+path)
            skipped['identical_destination_and_bytes']+=1
        else:
            destinations[key]=row['sha256'];normalized.append({**row,'restore_path':safe_relative(path).as_posix()})
        if (row['sha256'],row['bytes']) in known:continue
        previous=objects.get(row['sha256'])
        if previous is None or rank(row)<rank(previous):objects[row['sha256']]=row
    out=op/'model_batches'
    if out.exists():raise FileExistsError('Keep the reviewed prior model plan')
    out.mkdir();groups=[];current=[];size=0
    for row in sorted(objects.values(),key=lambda r:(r['scope'],r['logical_path'])):
        if current and (size+row['bytes']>a.batch_bytes or len(current)>=12000):groups.append(current);current=[];size=0
        current.append(row);size+=row['bytes']
    if current:groups.append(current)
    plans=[]
    for i,group in enumerate(groups,1):
        label='MODELS_B'+str(i).zfill(3);folder=out/label;folder.mkdir();selection=[]
        for row in group:
            # This is a content store. The completed collection's restore
            # manifest will map these objects back to every original location.
            relative='__archive_objects__/models/'+row['sha256']+'/'+Path(row['source']).name
            selection.append({'path':relative,'source':row['source'],'bytes':row['bytes'],'sha256':row['sha256'],
              'role':'historical_model_or_initialization_state','scope':row['scope'],'original_project_path':row['logical_path'],
              'reason':'Existing saved, initialized, selected, failed or intermediate state; preserve the exact bytes and original identity, never infer adoption from a filename.',
              'collection':'project-models-'+str(i).zfill(3)})
        write_json(folder/'SELECTION.json',{'reviewed':True,'files':selection,'identity_source':'Complete SHA-256 project audit; source is stable and checked again while packing'})
        plans.append({'batch':label,'folder':str(folder),'objects':len(group),'bytes':sum(r['bytes'] for r in group)})
    with gzip.open(out/'ALL_MODEL_LOCATIONS.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as stream:
        for row in normalized:stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    report={'status':'REVIEWED_PLAN_NOT_YET_PUBLISHED','tag':'research-model-history-additions-20261021',
      'source_files':len(rows),'normalized_restore_locations':len(normalized),'new_unique_objects':len(objects),
      'new_unique_bytes':sum(r['bytes'] for r in objects.values()),'batches':plans,'skipped':dict(skipped),
      'full_original_model_locations_preserved_in':'ALL_MODEL_LOCATIONS.jsonl.gz','scientific_model_promotion':False}
    write_json(out/'PLAN.json',report);print('MODEL_HISTORY_BATCHES_PLANNED',len(objects),report['new_unique_bytes'],len(plans),flush=True)

if __name__=='__main__':main()
