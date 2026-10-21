"""Seal the actual complete GitHub attachment list against reviewed manifests.

This is a final server-metadata check, separate from the already required
actual object-download/restoration receipts. Asset lists are explicitly paged;
drafts are allowed only for preliminary single-component inspection.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

from research_recovery import safe_relative,write_json


def gh_json(*args):
    return json.loads(subprocess.check_output(['gh',*args]))


def release_snapshot(repo,tag,allow_draft=False):
    identity=gh_json('release','view',tag,'--repo',repo,'--json','databaseId')
    value=gh_json('api','repos/'+repo+'/releases/'+str(identity['databaseId']))
    if value['tag_name']!=tag:raise ValueError('The returned release tag differs')
    if value['draft'] and not allow_draft:raise ValueError('A final component is still an unpublished draft')
    pages=gh_json('api','--paginate','--slurp','repos/'+repo+'/releases/'+str(value['id'])+'/assets?per_page=100')
    if not isinstance(pages,list) or any(not isinstance(page,list) for page in pages):
        raise ValueError('The complete paginated asset response is required')
    assets=[row for page in pages for row in page]
    if len({row['id'] for row in assets})!=len(assets) or len({row['name'] for row in assets})!=len(assets):
        raise ValueError('Asset identities repeat across the current server pages')
    commit=None
    if not value['draft']:
        obj=gh_json('api','repos/'+repo+'/git/ref/tags/'+quote(tag,safe=''))['object']
        for _ in range(8):
            if obj['type']=='commit':commit=obj['sha'];break
            if obj['type']!='tag':raise ValueError('The published tag does not name a commit')
            obj=gh_json('api','repos/'+repo+'/git/tags/'+obj['sha'])['object']
        if commit is None:raise ValueError('An annotated source tag could not be resolved')
    return {'tag':tag,'release_id':value['id'],'draft':value['draft'],'tag_commit':commit,
            'server_pages':len(pages),'assets':assets}


def check_assets(specs,snapshot):
    actual={row['name']:row for row in snapshot['assets']};checked=[];names=set()
    for spec in specs:
        name=spec['name']
        if name in names:raise ValueError('A declared attachment name is repeated')
        names.add(name)
        if safe_relative(name).name!=name:raise ValueError('A declared attachment name contains directories')
        row=actual.get(name)
        if row is None:raise ValueError('A declared attachment is absent from GitHub: '+name)
        if row['state']!='uploaded' or (row['size'],row.get('digest'))!=(spec['bytes'],'sha256:'+spec['sha256']):
            raise ValueError('The actual stored attachment differs: '+name)
        checked.append({'name':name,'asset_id':row['id'],'bytes':row['size'],'sha256':spec['sha256']})
    return checked


def read(path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True)
    parser.add_argument('--master-index',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--tag')
    parser.add_argument('--allow-draft',action='store_true')
    parser.add_argument('--expected-new-source-commit')
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo):raise ValueError('Use one explicit repository')
    if args.report.exists():raise FileExistsError('Preserve the earlier server attachment check')
    if bool(args.master_index)==bool(args.manifest):raise ValueError('Select exactly one complete master or component manifest')
    if args.master_index and args.allow_draft:raise ValueError('A final master check must reject all unpublished components')
    snapshots={};checks=[]
    def snapshot(tag):
        if tag not in snapshots:snapshots[tag]=release_snapshot(args.repo,tag,args.allow_draft)
        return snapshots[tag]
    if args.manifest:
        if not args.tag:raise ValueError('Name the component tag explicitly')
        manifest=read(args.manifest)
        if manifest.get('state')!='complete':raise ValueError('Only an exact complete object manifest can be checked')
        checks.append({'tag':args.tag,'assets':check_assets(manifest['assets'],snapshot(args.tag))})
    else:
        master=read(args.master_index)
        if master.get('state')!='complete':raise ValueError('A review-only path map is not a restorable master')
        for component in master['components']:
            path=args.master_index.parent/safe_relative(component['restore_manifest'])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=component['manifest_sha256']:
                raise ValueError('The component metadata differs from its master binding')
            manifest=read(path)
            if manifest.get('state')!='complete':raise ValueError('A component still has provisional restore paths')
            remote=snapshot(component['tag'])
            if args.expected_new_source_commit and component.get('new_collection') and remote['tag_commit']!=args.expected_new_source_commit:
                raise ValueError('A new collection is pinned to a different source commit')
            checks.append({'tag':component['tag'],'assets':check_assets(manifest['assets'],remote)})
        for package in master.get('original_large_packages',[]):
            path=args.master_index.parent/safe_relative(package['manifest'])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=package['manifest_sha256']:
                raise ValueError('The original package index differs from its master binding')
            manifest=read(path)
            if manifest.get('state')!='complete':raise ValueError('An original-container index is incomplete')
            remote=snapshot(package['tag'])
            if args.expected_new_source_commit and remote['tag_commit']!=args.expected_new_source_commit:
                raise ValueError('An original-container collection uses a different fixed source')
            checks.append({'tag':package['tag'],'assets':check_assets(manifest['parts'],remote)})
    write_json(args.report,{'status':'PASS_ALL_DECLARED_SERVER_ATTACHMENTS_EXACT',
        'preliminary_draft_check':args.allow_draft,'components':checks,
        'actual_paginated_releases':[{key:value for key,value in snapshot.items() if key!='assets'} for snapshot in snapshots.values()],
        'actual_server_asset_totals':{tag:len(value['assets']) for tag,value in snapshots.items()},
        'already_required_download_restore_receipts_replaced_by_this_check':False,
        'whole_project_complete':False})
    print('ACTUAL_PAGINATED_GITHUB_ATTACHMENTS_VERIFIED',len(checks),sum(len(row['assets']) for row in checks),flush=True)


if __name__=='__main__':main()
