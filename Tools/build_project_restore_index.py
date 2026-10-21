"""Build cross-release restore maps only after exact archive verification.

The master maps all worthwhile captured file contents, including older H
versions, to immutable GitHub objects. It does not claim retraining or complete
native scientific validation for every historical experiment.
"""
import argparse,gzip,json,subprocess,hashlib
from pathlib import Path
from collections import defaultdict
from project_reproducibility_audit import known_manifests,owner
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

def verify_exact_batch_receipt(manifest,verified):
    if verified.get('status')!='PASS_FILE_IDENTITY_AND_RESTORATION':
        raise ValueError('A batch has not passed actual byte restoration')
    expected={(row['sha256'],row['bytes']) for row in manifest['files']}
    checks=verified.get('checks',[])
    if len(checks)!=len(expected) or {(r['sha256'],r['bytes']) for r in checks}!=expected:
        raise ValueError('A restoration receipt does not cover the exact declared objects')
    if any(r.get('exact_file_bytes_restored') is not True for r in checks):
        raise ValueError('A declared object was not actually restored with exact bytes')
    def parts(rows):return {(r['name'],r['bytes'],r['sha256']) for r in rows}
    if parts(verified.get('assets',[]))!=parts(manifest['assets']):
        raise ValueError('A restoration receipt belongs to different archive parts')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--operation',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();op=a.operation;root=a.root;archive=Path(r'H:\GMM_2_Final_Archive')
    if a.output.exists():raise FileExistsError('Keep the earlier reviewed restore index')
    if not (op/'ALL_RESEARCH_CONTENT_HASHED.json').exists():raise ValueError('Complete all content-family checks before the master index')
    full_check=read(op/'ALL_RESEARCH_CONTENT_HASHED.json')
    if full_check.get('status')!='ALL_REQUESTED_FAMILIES_CONTENT_CHECKED':raise ValueError('The complete content check has not passed')
    expected_exports={r['family']:r['files'] for r in full_check['families']}
    if set(expected_exports)!={'context','models','numeric','images','packages'}:raise ValueError('A requested content family is missing')
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
        for batch in plan['batches']:
            batch_tag=batch.get('tag',plan['tag']);new_tags.add(batch_tag)
            work=Path(batch['folder']);receipt=work/'BATCH_GITHUB_RESTORE_VERIFIED.json'
            if not receipt.exists():raise ValueError('A reviewed batch has not been actually retrieved: '+batch['batch'])
            component=work/'bundle/RESEARCH_ASSETS.json.gz'
            verify_exact_batch_receipt(read(component),read(receipt))
            add_bundle(component,batch_tag,new=True)
            batch_checks.append({'batch':batch['batch'],'tag':batch_tag,'verification_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
    extra_scopes=read(op/'EXTRA_SCOPE_COLLECTIONS.json')['collections'] if (op/'EXTRA_SCOPE_COLLECTIONS.json').exists() else []
    for extra in extra_scopes:
        component=Path(extra['bundle_manifest']);receipt=Path(extra['verification'])
        verify_exact_batch_receipt(read(component),read(receipt))
        add_bundle(component,extra['tag'],new=True);new_tags.add(extra['tag'])
        batch_checks.append({'batch':extra['id'],'tag':extra['tag'],'verification_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
    # Exact current and historical code objects remain available even when the
    # current README/config differs from an older captured version.
    current_catalog=read(root/'docs/reproducibility/REPOSITORY_FILES.json.gz')
    current_tree=git_tree(root,current_catalog['source_snapshot_commit']);repo_current={}
    source_scopes=sorted([(r['scope'].casefold(),r['id']) for r in read(root/'docs/reproducibility/experiment_index.json')],key=lambda r:-len(r[0]))
    for row in current_catalog['files']:
        key=(row['sha256'],row['bytes']);value={'kind':'repository_blob','provider_path':row['path'],'git_blob':current_tree[row['path']]}
        providers.setdefault(key,value);repo_current[row['path'].casefold()]=row['sha256'];base_files.append({**row,'scope':owner(row['path'],source_scopes)})
    old_catalog_raw=subprocess.check_output(['git','show','6782071d67f5d8d71fa798f7a8926b16804c06b3:docs/reproducibility/REPOSITORY_FILES.json.gz'],cwd=root)
    old_catalog=json.loads(gzip.decompress(old_catalog_raw));old_tree=git_tree(root,old_catalog['source_snapshot_commit'])
    for row in old_catalog['files']:
        providers.setdefault((row['sha256'],row['bytes']),{'kind':'repository_blob','provider_path':row['path'],'git_blob':old_tree[row['path']]})
    large_package_sources={}
    if (op/'LARGE_ORIGINAL_PACKAGES_GITHUB_VERIFIED.json').exists():
        for package in read(op/'LARGE_ORIGINAL_PACKAGES_GITHUB_VERIFIED.json')['packages']:
            key=(package['original_sha256'],package['original_bytes'])
            providers[key]={'kind':'original_package_parts',**package}
            large_package_sources[key]=package
    canonical={};captured=0;missing=[];excluded=[]
    def insert(row,path=None,replace=False):
        relative=safe_relative(path or row['path']).as_posix()
        if relative.casefold()=='docs/reproducibility/repository_files.json.gz':
            # A fixed source clone already has its own self-excluding catalog.
            # Captured earlier task catalogs must survive as history, without
            # replacing that clone's required current recovery identity.
            relative='Historical_Preservation_Metadata/'+row['sha256'][:16]+'/'+relative
        key=relative.casefold();value={'path':relative,'sha256':row['sha256'],'bytes':row['bytes'],'scope':row.get('scope','research'),'role':row.get('role',row.get('kind','research')),
          'source_origin':row.get('origin',row.get('source_origin','previous_GitHub_publication'))}
        old=canonical.get(key)
        if old and old['sha256']!=value['sha256'] and not replace:raise ValueError('Unresolved restore path versions: '+relative)
        canonical[key]=value
    for row in base_files:
        key=row['path'].casefold()
        if key in repo_current and repo_current[key]!=row['sha256']:
            insert(row,'Historical_Publications/'+row['sha256'][:16]+'/'+row['path']);continue
        if key in canonical and canonical[key]['sha256']!=row['sha256']:
            insert(row,'Historical_Publications/'+row['sha256'][:12]+'/'+row['path'])
        else:insert(row)
    own={r['path'].casefold() for r in read(op/'FIRST_SOURCE_COMMIT.json')['files']}
    own.update(['tools/cleanup_verified_preservation_staging.ps1','tools/hash_research_inventory_in_memory.py'])
    owned_additions=op/'TASK_OWNED_SOURCE_CHANGES.json'
    if owned_additions.exists():
        for change in read(owned_additions)['files']:
            relative=safe_relative(change['path']).as_posix()
            if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=change['after_sha256']:
                raise ValueError('A recorded preservation-only source edit changed again: '+relative)
            own.add(relative.casefold())
    projection_file=root/'docs/reproducibility/project_completion/HISTORICAL_PATH_PROJECTIONS.json'
    projections=read(projection_file)['projections'] if projection_file.exists() else []
    export_sources=[(family,op/('HASHED_'+family.upper()+'_FILES.jsonl.gz'),expected_exports[family]) for family in ['context','models','numeric','images','packages']]
    export_sources += [(extra['id'],Path(extra['export']),read(Path(extra['source_audit']))['locations']) for extra in extra_scopes]
    for family,export_path,expected_count in export_sources:
        observed_count=0
        with gzip.open(export_path,'rt',encoding='utf-8') as stream:
          for line in stream:
            row=json.loads(line);captured+=1;observed_count+=1;relative=row['logical_path'];key=relative.casefold()
            if '/portable_runtime/' in '/'+key:
                excluded.append({'path':relative,'reason':'generic reinstallable runtime'});continue
            if row['origin']=='D_worktree' and (key in own or key.startswith('docs/reproducibility/project_completion/')):
                # Current preserved-task documentation lives in the final Git
                # source catalog; earlier task states remain in Git history.
                if key in repo_current:continue
            old=canonical.get(key)
            is_current=row['origin'] in {'D_worktree','registered_H_reference'}
            if not is_current and old and old['sha256']!=row['sha256']:
                relative='Historical_Archive/'+Path(row['source']).relative_to(archive).as_posix();key=relative.casefold()
            elif is_current and old and old['sha256']!=row['sha256']:
                if key in repo_current:raise ValueError('Current Git source differs from a non-owned captured local file: '+relative)
                if old.get('source_origin') in {'D_worktree','registered_H_reference'}:
                    raise ValueError('Two captured current source locations disagree: '+relative)
                insert(old,'Historical_Publications/'+old['sha256'][:16]+'/'+old['path'])
            insert({**row,'path':relative},replace=is_current)
            if row['origin']!='D_worktree':
                physical=Path(row['source'])
                for projection in projections:
                    prefix=archive/Path(projection['archive_relative_prefix'])
                    try:tail=physical.relative_to(prefix).as_posix()
                    except ValueError:continue
                    alias=(Path(projection['project_prefix'])/tail).as_posix();current=canonical.get(alias.casefold())
                    # A later current report/config wins; the historical bytes
                    # stay preserved under their archived version path above.
                    authoritative=projection.get('projection_role')=='current_registered_H_reference'
                    if current and current['sha256']!=row['sha256'] and authoritative:
                        if current.get('source_origin') in {'D_worktree','registered_H_reference'}:
                            raise ValueError('A registered current archive alias conflicts with a current source: '+alias)
                        if alias.casefold() in repo_current:
                            raise ValueError('A registered current archive alias differs from the fixed Git source: '+alias)
                        insert(current,'Historical_Publications/'+current['sha256'][:16]+'/'+current['path'])
                    if current is None or current['sha256']==row['sha256'] or authoritative:
                        insert({**row,'path':alias,'scope':projection['scope'],
                          'origin':'registered_H_reference' if authoritative else row['origin']},replace=authoritative)
        if observed_count!=expected_count:raise ValueError('A frozen content-family export is incomplete: '+family)
    a.output.mkdir(parents=True);groups=defaultdict(list);repo_aliases=[];large_packages=[]
    for row in canonical.values():
        provider=providers.get((row['sha256'],row['bytes']))
        if provider is None:missing.append(row);continue
        if provider['kind']=='repository_blob':
            if repo_current.get(row['path'].casefold())==row['sha256']:continue
            repo_aliases.append({**row,**provider})
        elif provider['kind']=='original_package_parts':
            index=Path(provider['manifest_path']);name=index.name
            (a.output/name).write_bytes(index.read_bytes())
            large_packages.append({'path':row['path'],'tag':provider['tag'],'manifest':name,'manifest_sha256':hashlib.sha256(index.read_bytes()).hexdigest(),
              'original_sha256':row['sha256'],'original_bytes':row['bytes'],'downloaded_parts':provider['downloaded_assets']})
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
      'repository_alias_manifest_sha256':hashlib.sha256((a.output/'REPOSITORY_CONTENT_ALIASES.json.gz').read_bytes()).hexdigest(),
      'source_repository_catalog_sha256':hashlib.sha256((root/'docs/reproducibility/REPOSITORY_FILES.json.gz').read_bytes()).hexdigest(),
      'source_repository_snapshot_commit':current_catalog['source_snapshot_commit'],
      'within_project_references_manifest':'docs/reproducibility/research_path_aliases.json',
      'original_large_packages':large_packages,
      'captured_physical_files':captured,'normalized_logical_locations':len(canonical),'repository_alias_locations':len(repo_aliases),
      'excluded_generic_dependency_files':len(excluded),'scientific_validation_scope':'File preservation verified; native/rebuild/numeric replays separately described',
      'batch_checks':batch_checks,'active_training_and_thesis_originals_protected':True,'D_cleanup_authorized':False})
    print('PROJECT_RESTORE_INDEX_BUILT',len(canonical),len(components),len(repo_aliases),flush=True)

if __name__=='__main__':main()
