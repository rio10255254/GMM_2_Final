"""Plan exact missing array/image/package objects from completed audit exports.

Existing release objects and already planned model/data objects are reused by
SHA-256. Original paths/roles remain in the frozen family exports and are mapped
back by the collection restore manifests. No source is moved or deleted.
"""
import argparse,gzip,json
from pathlib import Path
from research_recovery import write_json

def manifest(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--operation',type=Path,required=True)
    p.add_argument('--family',choices=['numeric','images','packages'],required=True);p.add_argument('--batch-bytes',type=int,default=16_000_000_000)
    a=p.parse_args();op=a.operation
    if not (op/('CONTENT_'+a.family.upper()+'_HASHED.json')).exists():raise ValueError('Finish this complete content family before planning')
    known=set();published_by_path={}
    with gzip.open(op/'PUBLISHED_CATALOG.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);known.add((row['sha256'],row['bytes']));published_by_path[row['path'].casefold()]=row['sha256']
    for folder in ['training_history_bundle','context_batch_001_bundle']:
        known.update((row['sha256'],row['bytes']) for row in manifest(op/folder/'RESEARCH_ASSETS.json.gz')['files'])
    for folder in ['model_batches','numeric_batches','image_batches','package_batches']:
        root=op/folder
        if root.exists():
            for spec in root.glob('*/SELECTION.json'):
                known.update((r['sha256'],r['bytes']) for r in json.loads(spec.read_text(encoding='utf-8'))['files'])
    rows=[];objects={};excluded=[];too_large=[]
    with gzip.open(op/('HASHED_'+a.family.upper()+'_FILES.jsonl.gz'),'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row['sha256'] is None:raise ValueError('An audit source is not yet content-verified')
            low=row['logical_path'].casefold()
            if '/portable_runtime/' in '/'+low:
                excluded.append({'path':row['logical_path'],'reason':'reinstallable generic runtime; original delivery containers separately preserved'});continue
            rows.append(row)
            if (row['sha256'],row['bytes']) in known:continue
            if row['bytes']>1_800_000_000:
                too_large.append(row);continue
            previous=objects.get(row['sha256'])
            def rank(value):return (any(s in value['logical_path'].casefold() for s in ['aborted_oversized','research_round_library','research_design_effect_review']),value['origin']!='D_worktree',len(value['source']))
            if previous is None or rank(row)<rank(previous):objects[row['sha256']]=row
    names={'numeric':('numeric_batches','NUMERIC','research-numeric-data-additions-20261021'),
      'images':('image_batches','IMAGES','research-image-data-additions-20261021'),
      'packages':('package_batches','PACKAGES','research-package-additions-20261021')}
    directory,prefix,tag=names[a.family];out=op/directory
    if out.exists():raise FileExistsError('Preserve the prior reviewed plan')
    out.mkdir();groups=[];group=[];size=0
    for row in sorted(objects.values(),key=lambda r:(r['scope'],r['logical_path'])):
        if group and (size+row['bytes']>a.batch_bytes or len(group)>=12000):groups.append(group);group=[];size=0
        group.append(row);size+=row['bytes']
    if group:groups.append(group)
    plans=[]
    for i,group in enumerate(groups,1):
        label=prefix+'_B'+str(i).zfill(3);folder=out/label;folder.mkdir();selection=[]
        for row in group:
            selection.append({'path':'__archive_objects__/'+a.family+'/'+row['sha256']+'/'+Path(row['source']).name,
              'source':row['source'],'sha256':row['sha256'],'bytes':row['bytes'],'role':'exact_historical_input_or_full_result',
              'source_kind':row['kind'],'scope':row['scope'],'original_project_path':row['logical_path'],
              'reason':'Preserve existing raw/frozen input or complete stored result bytes, including adverse and failed cases; source roles and original locations remain distinct.',
              'collection':'project-'+a.family+'-'+str(i).zfill(3)})
        write_json(folder/'SELECTION.json',{'reviewed':True,'files':selection,'source_family':a.family})
        plans.append({'batch':label,'folder':str(folder),'objects':len(group),'bytes':sum(r['bytes'] for r in group)})
    canonical={r['path_key']:r['sha256'] for r in rows if r['origin']=='D_worktree'}
    archive=Path(r'H:\GMM_2_Final_Archive');destinations={}
    with gzip.open(out/'ALL_ORIGINAL_LOCATIONS.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as stream:
        for row in rows:
            relative=row['logical_path'];key=relative.casefold()
            if row['origin']!='D_worktree' and ((key in canonical and canonical[key]!=row['sha256']) or (key in published_by_path and published_by_path[key]!=row['sha256']) or (key in destinations and destinations[key]!=row['sha256'])):
                relative='Historical_Archive/'+Path(row['source']).relative_to(archive).as_posix();key=relative.casefold()
            previous=destinations.get(key)
            if previous is not None and previous!=row['sha256']:raise ValueError('Unresolved captured historical source versions')
            destinations[key]=row['sha256']
            stream.write(json.dumps({**row,'restore_path':relative},ensure_ascii=False,separators=(',',':'))+'\n')
    report={'status':'REVIEWED_PLAN_NOT_YET_PUBLISHED','family':a.family,'tag':tag,'new_unique_objects':len(objects),
      'new_unique_bytes':sum(r['bytes'] for r in objects.values()),'batches':plans,'excluded_generic_dependencies':excluded,
      'large_original_containers_require_separate_chunk_preservation':too_large,'original_source_files_changed':False}
    write_json(out/'PLAN.json',report);print('RESEARCH_DATA_BATCHES_PLANNED',a.family,len(objects),report['new_unique_bytes'],len(plans),'large_containers',len(too_large),flush=True)

if __name__=='__main__':main()
