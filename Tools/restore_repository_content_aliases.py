"""Restore reviewed file aliases from exact GitHub Git blobs or a fresh clone.

Existing differing files are never overwritten. Older source versions can be
restored under their recorded historical names even when the current README or
program has since changed. This tool does not create old-drive dependencies.
"""
import argparse,base64,gzip,json,subprocess,hashlib,shutil
from pathlib import Path
from research_recovery import digest,safe_relative,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--prefix',action='append',default=[]);a=p.parse_args()
    if a.report.exists():raise FileExistsError('Keep the previous restore report')
    with gzip.open(a.manifest,'rt',encoding='utf-8-sig') as stream:m=json.load(stream)
    if m.get('state')!='complete':raise ValueError('Incomplete repository alias map')
    prefixes=[safe_relative(v) for v in a.prefix];rows=[];root=a.root.resolve()
    for row in m['files']:
        relative=safe_relative(row['path'])
        if prefixes and not any(relative.is_relative_to(prefix) for prefix in prefixes):continue
        target=a.root/relative
        if not target.resolve().is_relative_to(root):raise ValueError('Existing alias path redirects outside the new workspace')
        if target.exists() and (not target.is_file() or target.stat().st_size!=row['bytes'] or digest(target)!=row['sha256']):
            raise FileExistsError('Existing restored alias differs: '+row['path'])
        rows.append(row)
    count=0;downloaded=0;cache={}
    for row in rows:
        target=a.root/safe_relative(row['path'])
        if target.exists():count+=1;continue
        provider=a.root/safe_relative(row['provider_path'])
        if not provider.resolve().is_relative_to(root):raise ValueError('Repository provider redirects outside the new workspace')
        data=None
        if provider.exists() and provider.is_file() and provider.stat().st_size==row['bytes'] and digest(provider)==row['sha256']:
            target.parent.mkdir(parents=True,exist_ok=True)
            with provider.open('rb') as source,target.open('xb') as output:shutil.copyfileobj(source,output,4*1024**2)
        else:
            oid=row['git_blob']
            if oid not in cache:
                if len(oid)!=40 or any(c not in '0123456789abcdef' for c in oid):raise ValueError('Invalid recorded Git object')
                result=json.loads(subprocess.check_output(['gh','api','repos/'+a.repo+'/git/blobs/'+oid]));data=base64.b64decode(result['content'])
                if hashlib.sha256(data).hexdigest()!=row['sha256'] or len(data)!=row['bytes']:raise ValueError('GitHub historical source blob differs')
                cache[oid]=data;downloaded+=1
            data=cache[oid];target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as output:output.write(data)
        if digest(target)!=row['sha256']:raise ValueError('Restored repository alias differs')
        count+=1
    write_json(a.report,{'status':'PASS','original_alias_locations_verified':count,'historical_GitHub_blobs_downloaded':downloaded,
      'existing_differing_files_overwritten':False,'old_D_or_H_research_paths_required':False})
    print('REPOSITORY_CONTENT_ALIASES_RESTORED_VERIFIED',count,flush=True)

if __name__=='__main__':main()
