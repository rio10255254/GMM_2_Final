"""Restore the master archive's exact cross-release maps into a fresh clone.

The master metadata must first be downloaded from its fixed GitHub release.
All parts are checked against current GitHub digests. Existing different files
are protected; no old D/H location is consulted or recreated as a dependency.
"""
import argparse,gzip,json,subprocess,sys,hashlib,uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from download_research_assets import download_asset,select_prefix_assets,select_manifest_assets
from research_asset_bundle import restore
from research_recovery import digest,safe_relative,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True)
    p.add_argument('--master-index',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--downloads',type=Path,required=True);p.add_argument('--prefix',action='append',default=[])
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():raise FileExistsError('Keep the prior master recovery report')
    master=json.loads(a.master_index.read_text(encoding='utf-8-sig'))
    if master.get('state')!='complete':raise ValueError('The complete verified master index is required')
    expected_catalog=master.get('source_repository_catalog_sha256')
    if expected_catalog:
        catalog=a.root/'docs/reproducibility/REPOSITORY_FILES.json.gz'
        if not catalog.is_file() or digest(catalog)!=expected_catalog:
            raise ValueError('Use a fresh clone of the fixed master source version before restoring its data')
    # Each scope or retry retains its own receipt. A prior R93 recovery must
    # not prevent the same download cache from later restoring R94 aliases.
    run_id=uuid.uuid4().hex[:16]
    prefixes=[safe_relative(value) for value in a.prefix]
    token=subprocess.check_output(['gh','auth','token'],text=True).strip();release_cache={};components=[]
    def release(tag):
        if tag not in release_cache:
            ident=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',a.repo,'--json','databaseId']))
            value=json.loads(subprocess.check_output(['gh','api','repos/'+a.repo+'/releases/'+str(ident['databaseId'])]))
            if value['draft']:raise ValueError('A declared final component is still a draft')
            release_cache[tag]=value
        return release_cache[tag]
    for component in master['components']:
        manifest=a.master_index.parent/safe_relative(component['restore_manifest'])
        if digest(manifest)!=component['manifest_sha256']:raise ValueError('Master restore metadata differs')
        with gzip.open(manifest,'rt',encoding='utf-8') as stream:m=json.load(stream)
        selected=[r for r in m['files'] if not prefixes or any(safe_relative(r['path']).is_relative_to(v) for v in prefixes)]
        if not selected:continue
        remote=release(component['tag']);download_root=a.downloads/component['tag'];download_root.mkdir(parents=True,exist_ok=True)
        if a.prefix:assets,count=select_prefix_assets(m,remote['assets'],a.prefix)
        else:assets,count=select_manifest_assets(m,remote['assets'])
        with ThreadPoolExecutor(max_workers=2) as pool:downloaded=list(pool.map(lambda asset:download_asset(a.repo,asset,download_root,token),assets))
        result=restore(manifest,download_root,a.root,prefixes=tuple(a.prefix),keep_identical_existing=True)
        components.append({'tag':component['tag'],'downloaded_parts':downloaded,'restoration':result})
    aliases=a.master_index.parent/safe_relative(master['repository_alias_manifest'])
    if digest(aliases)!=master['repository_alias_manifest_sha256']:raise ValueError('Repository alias metadata differs from the master index')
    alias_report=a.downloads/('REPOSITORY_ALIASES_RESTORED_'+run_id+'.json');a.downloads.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,str(Path(__file__).with_name('restore_repository_content_aliases.py')),'--repo',a.repo,
      '--root',str(a.root),'--manifest',str(aliases),'--report',str(alias_report)]
    for prefix in a.prefix:command+=['--prefix',prefix]
    subprocess.run(command,check=True)
    large=[]
    for package in master.get('original_large_packages',[]):
        target=safe_relative(package['path'])
        if prefixes and not any(target.is_relative_to(v) for v in prefixes):continue
        manifest=a.master_index.parent/safe_relative(package['manifest'])
        if digest(manifest)!=package['manifest_sha256']:raise ValueError('Original distribution index changed')
        m=json.loads(manifest.read_text(encoding='utf-8-sig'));remote=release(package['tag']);available={r['name']:r for r in remote['assets']}
        folder=a.downloads/package['tag'];folder.mkdir(parents=True,exist_ok=True)
        for part in m['parts']:
            actual=available[part['name']]
            if actual['digest']!='sha256:'+part['sha256'] or actual['size']!=part['bytes']:raise ValueError('Original distribution part differs')
            download_asset(a.repo,actual,folder,token)
        output=a.root/target
        if not output.resolve().is_relative_to(a.root.resolve()):raise ValueError('Original distribution destination redirects outside workspace')
        if output.exists():
            if output.stat().st_size!=package['original_bytes'] or digest(output)!=package['original_sha256']:raise FileExistsError('Existing original package differs')
            large.append({'path':package['path'],'identical_existing':True});continue
        report=folder/(package['original_sha256'][:16]+'_RESTORED_'+run_id+'.json')
        subprocess.run([sys.executable,str(Path(__file__).with_name('restore_original_package_parts.py')),'--manifest',str(manifest),
          '--parts',str(folder),'--output',str(output),'--report',str(report)],check=True)
        large.append(json.loads(report.read_text(encoding='utf-8-sig')))
    shared_references={'status':'NOT_REQUESTED_FOR_SELECTED_PREFIXES'}
    if not a.prefix and master.get('within_project_references_manifest'):
        manifest=a.root/safe_relative(master['within_project_references_manifest'])
        if not manifest.is_file():raise ValueError('The fixed within-project reference metadata is missing from the source clone')
        shared_report=a.downloads/('WITHIN_PROJECT_REFERENCES_'+run_id+'.json')
        subprocess.run([sys.executable,str(Path(__file__).with_name('restore_research_aliases.py')),'--root',str(a.root),
          '--manifest',str(manifest),'--report',str(shared_report)],check=True)
        shared_references=json.loads(shared_report.read_text(encoding='utf-8-sig'))
    write_json(a.report,{'status':'PASS','master_index_sha256':digest(a.master_index),'requested_prefixes':a.prefix,
      'components':components,'repository_aliases':json.loads(alias_report.read_text(encoding='utf-8-sig')),'original_large_packages':large,
      'within_project_references':shared_references,
      'old_research_drive_fallback':False,'existing_differing_files_overwritten':False})
    print('MASTER_PROJECT_RESTORE_VERIFIED',len(components),flush=True)

if __name__=='__main__':main()
