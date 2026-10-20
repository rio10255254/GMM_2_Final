"""Build cross-release restore maps only after exact archive verification.

The master maps all worthwhile captured file contents, including older H
versions, to immutable GitHub objects. It does not claim retraining or complete
native scientific validation for every historical experiment.
"""
import argparse,gzip,json,subprocess,hashlib
from pathlib import Path
from collections import defaultdict
from project_reproducibility_audit import known_manifests
from research_recovery import safe_relative,write_json

def read(path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):
    with gzip.open(path,'wt',encoding='utf-8',compresslevel=1) as stream:json.dump(value,stream,ensure_ascii=False,separators=(',',':'))
def git_tree(root,ref):
    raw=subprocess.check_output(['git','-c','core.longpaths=true','ls-tree','-r','-z',ref],cwd=root);values={}
    for line in raw.split(b'\0'):
        if not line:continue
        left,name=line.split(b'\t',1);mode,kind,oid=left.decode().split()
        if kind=='blob':values[name.decode('utf-8')]=oid
    return values

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--operation',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();op=a.operation;root=a.root;archive=Path(r'H:\GMM_2_Final_Archive')
    if a.output.exists():raise FileExistsError('Keep the earlier reviewed restore index')
    if not (op/'ALL_RESEARCH_CONTENT_HASHED.json').exists():raise ValueError('Complete all content-family checks before the master index')
    providers={};specs={};base_files=[];new_tags=set();batch_checks=[]
    def add_bundle(path,tag,new=False):
        m=read(path)
        if m.get('state')!='complete':raise ValueError('Incomplete component: '+tag)
        specifications={r['name']:r for r in m['assets']};specs.setdefault(tag,{})
        for name,spec in specifications.items():
            prior=specs[tag].get(name)
            if prior and (prior['sha256'],prior['bytes'])!=(spec['sha256'],spec['bytes']):raise ValueError('Immutable part names conflict')
            specs[tag][name]=spec
        for row in m['files']:
            relative=safe_relative(row['path']).as_posix();key=(row['sha256'],row['bytes'])
            value={'kind':'release_object','tag':tag,'asset':row['asset'],'sha256':row['sha256'],'bytes':row['bytes']}
            if new or key not in providers:providers[key]=value
            if not relative.startswith('__archive_objects__/'):base_files.append({'path':relative,'sha256':row['sha256'],'bytes':row['bytes'],'scope':row.get('scope','published_source'),'role':row.get('role','preserved_research')})
    manifests=known_manifests(root,archive)
    # The source tree is handled below; use the actual original frozen release
    # manifests for previously verified large content, never inferred filenames.
    for path,tag in manifests:
        if path.name=='REPOSITORY_FILES.json.gz':continue
        add_bundle(path,tag)
    add_bundle(op/'training_history_bundle/RESEARCH_ASSETS.json.gz','research-training-history-supplement-20261021',new=True)
    if not (op/'GITHUB_CONTEXT_FAST_ISOLATED_GUARD.json').exists():raise ValueError('The full Context recovery must finish')
    if read(op/'GITHUB_CONTEXT_FAST_ISOLATED_GUARD.json')['status']!='PASS':raise ValueError('Context restoration has not passed')
    add_bundle(op/'context_batch_001_bundle/RESEARCH_ASSETS.json.gz','research-project-context-20261021',new=True)
    for family in ['model','numeric','image','package']:
        folder=op/(family+'_batches')
        plan=read(folder/'PLAN.json')
        if plan.get('large_original_containers_require_separate_chunk_preservation'):
            if not (op/'LARGE_ORIGINAL_PACKAGES_GITHUB_VERIFIED.json').exists():raise ValueError('Large original distribution containers remain unfinished')
        new_tags.add(plan['tag'])
        for batch in plan['batches']:
            work=Path(batch['folder']);receipt=work/'BATCH_GITHUB_RESTORE_VERIFIED.json'
            if not receipt.exists() or read(receipt)['status']!='PASS_FILE_IDENTITY_AND_RESTORATION':raise ValueError('A reviewed batch has not been actually retrieved: '+batch['batch'])
            add_bundle(work/'bundle/RESEARCH_ASSETS.json.gz',plan['tag'],new=True)
            batch_checks.append({'batch':batch['batch'],'tag':plan['tag'],'verification_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
    # Exact current and historical code objects remain available even when the
    # current README/config differs from an older captured version.
    current_catalog=read(root/'docs/reproducibility/REPOSITORY_FILES.json.gz')
    current_tree=git_tree(root,current_catalog['source_snapshot_commit']);repo_current={}
    for row in current_catalog['files']:
        key=(row['sha256'],row['bytes']);value={'kind':'repository_blob','provider_path':row['path'],'git_blob':current_tree[row['path']]}
        providers.setdefault(key,value);repo_current[row['path'].casefold()]=row['sha256'];base_files.append({**row,'scope':'repository_source'})
    old_catalog_raw=subprocess.check_output(['git','show','6782071d67f5d8d71fa798f7a8926b16804c06b3:docs/reproducibility/REPOSITORY_FILES.json.gz'],cwd=root)
    old_catalog=json.loads(gzip.decompress(old_catalog_raw));old_tree=git_tree(root,old_catalog['source_snapshot_commit'])
    for row in old_catalog['files']:
        providers.setdefault((row['sha256'],row['bytes']),{'kind':'repository_blob','provider_path':row['path'],'git_blob':old_tree[row['path']]})
    canonical={};captured=0;missing=[];excluded=[]
    def insert(row,path=None,replace=False):
        relative=safe_relative(path or row['path']).as_posix();key=relative.casefold();value={'path':relative,'sha256':row['sha256'],'bytes':row['bytes'],'scope':row.get('scope','research'),'role':row.get('role',row.get('kind','research'))}
        old=canonical.get(key)
        if old and old['sha256']!=value['sha256'] and not replace:raise ValueError('Unresolved restore path versions: '+relative)
        canonical[key]=value
    for row in base_files:
        key=row['path'].casefold()
        if key in repo_current and repo_current[key]!=row['sha256']:
            insert(row,'Historical_Publications/preserved_before_current_source/'+row['path']);continue
        if key in canonical and canonical[key]['sha256']!=row['sha256']:
            insert(row,'Historical_Publications/'+row['sha256'][:12]+'/'+row['path'])
        else:insert(row)
    own={r['path'].casefold() for r in read(op/'FIRST_SOURCE_COMMIT.json')['files']}
    own.update(['tools/cleanup_verified_preservation_staging.ps1','tools/hash_research_inventory_in_memory.py'])
    for family in ['context','models','numeric','images','packages']:
        with gzip.open(op/('HASHED_'+family.upper()+'_FILES.jsonl.gz'),'rt',encoding='utf-8') as stream:
          for line in stream:
            row=json.loads(line);captured+=1;relative=row['logical_path'];key=relative.casefold()
            if '/portable_runtime/' in '/'+key:
                excluded.append({'path':relative,'reason':'generic reinstallable runtime'});continue
            if row['origin']=='D_worktree' and (key in own or key.startswith('docs/reproducibility/project_completion/')):
                # Current preserved-task documentation lives in the final Git
                # source catalog; earlier task states remain in Git history.
                if key in repo_current:continue
            old=canonical.get(key)
            if row['origin']!='D_worktree' and old and old['sha256']!=row['sha256']:
                relative='Historical_Archive/'+Path(row['source']).relative_to(archive).as_posix();key=relative.casefold()
            elif row['origin']=='D_worktree' and old and old['sha256']!=row['sha256']:
                if key in repo_current:raise ValueError('Current Git source differs from a non-owned captured local file: '+relative)
                insert(old,'Historical_Publications/'+old['sha256'][:12]+'/'+old['path'])
            insert({**row,'path':relative},replace=row['origin']=='D_worktree')
    a.output.mkdir(parents=True);groups=defaultdict(list);repo_aliases=[]
    for row in canonical.values():
        provider=providers.get((row['sha256'],row['bytes']))
        if provider is None:missing.append(row);continue
        if provider['kind']=='repository_blob':
            if repo_current.get(row['path'].casefold())==row['sha256']:continue
            repo_aliases.append({**row,**provider})
        else:groups[provider['tag']].append({**row,'asset':provider['asset']})
    if missing:
        write_json(a.output/'MISSING_PUBLIC_OBJECTS_REQUIRING_REVIEW.json',{'files':missing});raise ValueError('Some exact source objects still lack a verified GitHub provider')
    components=[]
    for tag,rows in sorted(groups.items()):
        assets=list(specs[tag].values());objects={(r['sha256'],r['bytes']) for r in rows};name='RESTORE_'+tag+'.json.gz'
        m={'schema':1,'state':'complete','files':rows,'assets':assets,'paths':len(rows),'unique_objects':len(objects),
          'original_bytes':sum(r['bytes'] for r in rows),'unique_bytes':sum(size for sha,size in objects),
          'full_historical_training_repeated':False,'deletion_authorized_by_this_manifest':False}
        save(a.output/name,m);components.append({'tag':tag,'restore_manifest':name,'files':len(rows),'manifest_sha256':hashlib.sha256((a.output/name).read_bytes()).hexdigest(),'new_collection':tag in new_tags})
    save(a.output/'REPOSITORY_CONTENT_ALIASES.json.gz',{'schema':1,'state':'complete','files':repo_aliases})
    write_json(a.output/'MASTER_RESTORE_INDEX.json',{'schema':1,'state':'complete','components':components,'repository_alias_manifest':'REPOSITORY_CONTENT_ALIASES.json.gz',
      'captured_physical_files':captured,'normalized_logical_locations':len(canonical),'repository_alias_locations':len(repo_aliases),
      'excluded_generic_dependency_files':len(excluded),'scientific_validation_scope':'File preservation verified; native/rebuild/numeric replays separately described',
      'batch_checks':batch_checks,'active_training_and_thesis_originals_protected':True,'D_cleanup_authorized':False})
    print('PROJECT_RESTORE_INDEX_BUILT',len(canonical),len(components),len(repo_aliases),flush=True)

if __name__=='__main__':main()
