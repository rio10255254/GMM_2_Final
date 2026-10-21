"""Plan exact missing array/image/package objects from completed audit exports.

Existing release objects and already planned model/data objects are reused by
SHA-256. Original paths/roles remain in the frozen family exports and are mapped
back by the collection restore manifests. No source is moved or deleted.
"""
import argparse,gzip,json,zipfile
from pathlib import Path
from research_recovery import write_json
from research_preservation_exclusions import load_exclusions,excluded as private_excluded

def manifest(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)

def predicted_parts(rows,limit=1_800_000_000):
    """Use the exact byte grouping/order and 256-byte allowance of the packer."""
    parts=0;size=0;nonempty=False
    for row in sorted(rows,key=lambda r:r['sha256']):
        if nonempty and size+row['bytes']+256>limit:
            parts+=1;size=0;nonempty=False
        size+=row['bytes']+256;nonempty=True
    return parts+int(nonempty)

def assign_release_shards(batches,base_tag,maximum_batch_assets=900):
    shard=1;used=0;releases={}
    for batch in batches:
        count=batch['predicted_parts']+3 # unique per-batch manifest, summary, sums
        if count>maximum_batch_assets:raise ValueError('One batch is too large for a release')
        if used and used+count>maximum_batch_assets:shard+=1;used=0
        tag=base_tag if shard==1 else base_tag+'-'+str(shard).zfill(2)
        batch['tag']=tag;used+=count;releases[tag]=used
    return [{'tag':tag,'planned_batch_assets':count,'space_reserved_for_final_metadata':100} for tag,count in releases.items()]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--operation',type=Path,required=True)
    p.add_argument('--family',choices=['numeric','images','packages'],required=True);p.add_argument('--batch-bytes',type=int,default=16_000_000_000)
    a=p.parse_args();op=a.operation
    private_policy=load_exclusions(Path(__file__).resolve().parents[1])
    if not (op/('CONTENT_'+a.family.upper()+'_HASHED.json')).exists():raise ValueError('Finish this complete content family before planning')
    known=set();published_by_path={}
    with gzip.open(op/'PUBLISHED_CATALOG.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);known.add((row['sha256'],row['bytes']));published_by_path[row['path'].casefold()]=row['sha256']
    for folder in ['training_history_bundle','context_batch_001_bundle']:
        known.update((row['sha256'],row['bytes']) for row in manifest(op/folder/'RESEARCH_ASSETS.json.gz')['files'])
    extra_index=op/'EXTRA_SCOPE_COLLECTIONS.json'
    if extra_index.exists():
        for extra in json.loads(extra_index.read_text(encoding='utf-8'))['collections']:
            proof=json.loads(Path(extra['verification']).read_text(encoding='utf-8'))
            if proof.get('status')!='PASS_FILE_IDENTITY_AND_RESTORATION':raise ValueError('An extra source collection is not yet actually recovered')
            known.update((row['sha256'],row['bytes']) for row in manifest(Path(extra['bundle_manifest']))['files'])
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
            if private_excluded(row,private_policy):
                excluded.append({'path':row['logical_path'],'reason':'private nonresearch tool backup; original retained locally, not sent to GitHub'});continue
            if Path(row['source']).suffix.casefold()=='.zip':
                with zipfile.ZipFile(row['source']) as archive:
                    private_names={'auth.json','credentials.json','credentials','id_rsa','id_ed25519','.env','.env.local','tokens.json','token.json'}
                    if any(Path(item.filename.replace('\\','/')).name.casefold() in private_names for item in archive.infolist()):
                        raise ValueError('An original ZIP contains a private-named member requiring review before upload: '+row['logical_path'])
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
            source=Path(row['source'])
            if row['logical_path'].casefold()=='docs/reproducibility/repository_files.json.gz':
                import hashlib
                source=op/'captured_task_metadata'/row['sha256']/'REPOSITORY_FILES.json.gz'
                if not source.is_file():raise ValueError('Freeze the checked task catalog before planning its changing live source')
                with source.open('rb') as stream:identity=hashlib.file_digest(stream,'sha256').hexdigest()
                if (source.stat().st_size,identity)!=(row['bytes'],row['sha256']):raise ValueError('The captured task catalog differs from its full-audit identity')
            selection.append({'path':'__archive_objects__/'+a.family+'/'+row['sha256']+'/'+Path(row['source']).name,
              'source':str(source),'sha256':row['sha256'],'bytes':row['bytes'],'role':'exact_historical_input_or_full_result',
              'source_kind':row['kind'],'scope':row['scope'],'original_project_path':row['logical_path'],
              'reason':'Preserve existing raw/frozen input or complete stored result bytes, including adverse and failed cases; source roles and original locations remain distinct.',
              'collection':'project-'+a.family+'-'+str(i).zfill(3)})
        write_json(folder/'SELECTION.json',{'reviewed':True,'files':selection,'source_family':a.family})
        plans.append({'batch':label,'folder':str(folder),'objects':len(group),'bytes':sum(r['bytes'] for r in group),
          'predicted_parts':predicted_parts(group)})
    releases=assign_release_shards(plans,tag)
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
      'new_unique_bytes':sum(r['bytes'] for r in objects.values()),'batches':plans,'releases':releases,
      'release_limit_source':'https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases',
      'excluded_generic_dependencies':excluded,
      'large_original_containers_require_separate_chunk_preservation':too_large,'original_source_files_changed':False}
    write_json(out/'PLAN.json',report);print('RESEARCH_DATA_BATCHES_PLANNED',a.family,len(objects),report['new_unique_bytes'],len(plans),'large_containers',len(too_large),flush=True)

if __name__=='__main__':main()
