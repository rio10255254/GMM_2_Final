"""Assemble original-path recovery metadata after every batch was retrieved.

Only objects newly preserved by this collection are included. Earlier release
objects retain their earlier immutable providers in the full master map. This
creates reviewable metadata and does not publish or declare the project done.
Plan-time paths remain provisional: the final published component uses the
global master map, which resolves current relocated H results and shared aliases.
"""
import argparse,gzip,json,hashlib
from pathlib import Path
from collections import Counter
from research_recovery import safe_relative,write_json

def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();plan=json.loads(a.plan.read_text(encoding='utf-8'))
    if a.output.exists():raise FileExistsError('Keep the preceding assembled collection')
    objects={};parts={};receipts=[];issues=[]
    for batch in plan['batches']:
        root=Path(batch['folder']);proof=root/'BATCH_GITHUB_RESTORE_VERIFIED.json'
        if not proof.exists():raise ValueError('A batch is not yet recovered: '+batch['batch'])
        verified=json.loads(proof.read_text(encoding='utf-8'))
        if verified['status']!='PASS_FILE_IDENTITY_AND_RESTORATION':raise ValueError('A batch did not pass exact original restoration')
        m=read_gzip(root/'bundle/RESEARCH_ASSETS.json.gz')
        checked={(r['sha256'],r['bytes']) for r in verified['checks']}
        if checked!={(r['sha256'],r['bytes']) for r in m['files']}:raise ValueError('Batch verification did not cover every packed source')
        for row in m['files']:
            key=row['sha256']
            if key in objects and objects[key]['bytes']!=row['bytes']:raise ValueError('Object byte identity conflict')
            objects[key]=row
        for spec in m['assets']:
            prior=parts.get(spec['name'])
            if prior and (prior['bytes'],prior['sha256'])!=(spec['bytes'],spec['sha256']):raise ValueError('Part name collision')
            parts[spec['name']]=spec
        receipts.append({'batch':batch['batch'],'objects':len(checked),'verification_sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),
          'load_errors_preserved':verified.get('load_errors_preserved',0),'nonfinite_histories_preserved':verified.get('nonfinite_histories_preserved',0)})
        for row in verified['checks']:
            if row.get('load_status')=='LOAD_ERROR_PRESERVED' or row.get('all_tensors_finite') is False or 'FAILURE' in row.get('format_status',''):
                issues.append(row)
    locations=a.plan.parent/('ALL_MODEL_LOCATIONS.jsonl.gz' if (a.plan.parent/'ALL_MODEL_LOCATIONS.jsonl.gz').exists() else 'ALL_ORIGINAL_LOCATIONS.jsonl.gz')
    paths={};scopes=Counter();seen_objects=set();archive=Path(r'H:\GMM_2_Final_Archive')
    with gzip.open(locations,'rt',encoding='utf-8') as stream:
        for line in stream:
            source=json.loads(line);obj=objects.get(source['sha256'])
            if obj is None:continue
            if source['bytes']!=obj['bytes']:raise ValueError('Original source location byte count differs')
            relative=source.get('restore_path',source['logical_path']);key=relative.casefold()
            previous=paths.get(key)
            if previous and previous['sha256']!=source['sha256']:
                if source['origin']=='D_worktree':raise ValueError('Distinct current original files map to one destination')
                relative='Archive/Historical_Archive/'+Path(source['source']).relative_to(archive).as_posix();key=relative.casefold()
            if key in paths:
                if paths[key]['sha256']!=source['sha256']:raise ValueError('Historical source version collision')
                continue
            paths[key]={'path':safe_relative(relative).as_posix(),'sha256':source['sha256'],'bytes':source['bytes'],'asset':obj['asset'],
              'role':source['kind'],'scope':source['scope'],'historical_source':source['source'],
              'reason':'Existing complete source/result/state bytes, with original scope and identity retained; no scientific promotion inferred'}
            scopes[source['scope']]+=1;seen_objects.add(source['sha256'])
    if seen_objects!=set(objects):raise ValueError('A packed object has no preserved original source location')
    rows=list(paths.values());manifest={'schema':1,'state':'complete_objects_path_review_pending','files':rows,'assets':list(parts.values()),'paths':len(rows),
      'unique_objects':len(objects),'original_bytes':sum(r['bytes'] for r in rows),'unique_bytes':sum(r['bytes'] for r in objects.values()),
      'packed_bytes':sum(r['bytes'] for r in parts.values()),'full_historical_training_repeated':False,'deletion_authorized_by_this_manifest':False,
      'scientific_failures_preserved_not_repaired':len(issues)}
    a.output.mkdir(parents=True)
    with gzip.open(a.output/'RESEARCH_ASSETS.json.gz','wt',encoding='utf-8') as stream:json.dump(manifest,stream,ensure_ascii=False,separators=(',',':'))
    write_json(a.output/'BUNDLE_SUMMARY.json',{k:v for k,v in manifest.items() if k!='files'})
    write_json(a.output/'COLLECTION_VERIFICATION.json',{'status':'ALL_BATCH_OBJECTS_ACTUALLY_DOWNLOADED_RESTORED_VERIFIED',
      'tag':plan['tag'],'batch_receipts':receipts,'source_scope_counts':dict(scopes),'historical_inspection_issues_retained':issues,
      'paths':len(rows),'unique_objects':len(objects),'project_complete':False,'collection_publication_pending':True,
      'global_master_path_binding_required':True})
    print('VERIFIED_COLLECTION_ASSEMBLED_WITH_ORIGINAL_PATHS',plan['tag'],len(rows),len(objects),flush=True)

if __name__=='__main__':main()
