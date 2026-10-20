"""Add a uniquely named, reviewed batch to a private draft research release.

Each batch has its own immutable metadata names. A collection-wide manifest and
publication happen after independent download/restore checks, never here.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shutil
import subprocess

from publish_research_assets import command,release_state,upload_one
from research_recovery import digest,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--tag',required=True)
    p.add_argument('--title',required=True);p.add_argument('--target',required=True)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--batch',required=True)
    p.add_argument('--workers',type=int,choices=range(1,5),default=2)
    a=p.parse_args()
    if not re.fullmatch('[A-Z][A-Z0-9_]{0,39}',a.batch):raise ValueError('Invalid batch metadata prefix')
    if not json.loads(command(['repo','view',a.repo,'--json','isPrivate']))['isPrivate']:
        raise ValueError('The authorized research archive is private')
    existing=subprocess.run(['gh','release','view',a.tag,'--repo',a.repo],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if existing.returncode:
        command(['release','create',a.tag,'--repo',a.repo,'--draft','--target',a.target,'--title',a.title,
          '--notes','逐批保存與實際取回核對中；尚未宣稱全專案完成。'])
    if not release_state(a.repo,a.tag)['isDraft']:raise ValueError('Never append archive work to a published collection')
    summary=json.loads((a.bundle/'BUNDLE_SUMMARY.json').read_text(encoding='utf-8-sig'))
    if summary.get('state')!='complete':raise ValueError('Pack and verify the reviewed batch first')
    receipt=a.bundle/'GITHUB_BATCH_UPLOADED_VERIFIED.json'
    if receipt.exists():raise FileExistsError('Batch upload receipt already exists')
    names=[row['name'] for row in summary['assets']]
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        results=list(pool.map(lambda name:upload_one(a.repo,a.tag,a.bundle/name),names))
    for expected in summary['assets']:
        actual=next(r for r in results if r['name']==expected['name'])
        if actual['sha256']!=expected['sha256'] or actual['bytes']!=expected['bytes']:raise ValueError('Uploaded batch differs')
    metadata=[]
    for source in ['RESEARCH_ASSETS.json.gz','BUNDLE_SUMMARY.json']:
        target=a.bundle/(a.batch+'_'+source)
        if target.exists():
            if digest(target)!=digest(a.bundle/source):raise FileExistsError('Existing batch metadata differs')
        else:shutil.copyfile(a.bundle/source,target)
        metadata.append(target)
    sums=a.bundle/(a.batch+'_SHA256SUMS.txt')
    if not sums.exists():
        entries=[{'name':r['name'],'sha256':r['sha256']} for r in summary['assets']]
        entries += [{'name':p.name,'sha256':digest(p)} for p in metadata]
        sums.write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in sorted(entries,key=lambda r:r['name'])),encoding='utf-8')
    metadata.append(sums)
    for path in metadata:results.append(upload_one(a.repo,a.tag,path))
    write_json(receipt,{'status':'PASS','release_is_draft':True,'repo':a.repo,'tag':a.tag,'batch':a.batch,
      'assets':results,'publication_or_recovery_claimed_by_this_upload':False})
    print('BATCH_UPLOADED_AND_SERVER_DIGESTS_VERIFIED',a.batch,len(results),flush=True)

if __name__=='__main__':main()
