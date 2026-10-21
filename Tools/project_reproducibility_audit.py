"""Read-only project/archive inventory and explicitly unverified publication gaps.

Size matches are candidates only. SHA-256 identity is required to claim content
coverage. This tool never moves/deletes data, follows an unreviewed external
directory, starts training, or changes a scientific verdict.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import subprocess
import time

SKIP_DIRS={'.git','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache',
           'node_modules','.venv','venv','site-packages','runtime'}
TEXT_SOURCE={'.py','.m','.ps1','.cmd','.bat','.sh','.c','.cpp','.h','.cu','.js','.ts','.tsx','.jsx','.r','.ipynb'}
TEXT_RECORD={'.json','.csv','.tsv','.jsonl','.log','.txt','.yaml','.yml','.ini','.toml','.xml'}
IMAGES={'.bmp','.png','.jpg','.jpeg','.tif','.tiff','.webp','.gif'}
ARRAYS={'.npy','.npz','.mat','.h5','.hdf5','.bin'}
DOCUMENTS={'.md','.rst','.pdf','.docx','.doc','.pptx','.ppt','.xlsx','.xls','.ods','.svg'}
MODELPARTS={'weights','checkpoints','checkpoint','models','pretrained','model_checkpoints'}
INPUTPARTS={'data','training_data','raw','raw_inputs','inputs','datasets','dataset','source_data','shared_sources'}
ARCHIVE_DOMAINS={'experiments','legacy','lab_system','main_training_history','analyses','active_runs','compatibility_views'}

def safe_relative(value):
    value=str(value).replace('\\','/')
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or ':' in value or not p.parts:
        raise ValueError('Unsafe project-relative path')
    return p.as_posix()

def read_json(path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8-sig') as stream:return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def dependency_directory(path,name):
    if name.casefold() not in SKIP_DIRS:return False
    if name.casefold() not in {'runtime','venv','.venv'}:return True
    # Many research 'runtime' folders hold the exact inference source copied
    # for a historical run. A name is never evidence that it is disposable.
    return any((path/marker).exists() for marker in ['python.exe','pyvenv.cfg','Scripts/python.exe','Lib/site-packages'])

def classify(relative):
    p=PurePosixPath(relative);name=p.name.casefold();suffix=p.suffix.casefold()
    parts={s.casefold() for s in p.parts[:-1]}
    if name in {'.env','credentials.json','token.json','tokens.json','id_rsa','id_ed25519'} or name.endswith('.pem'):
        return 'private_excluded'
    if name.endswith(('.pth.tar','.safetensors','.ckpt','.onnx','.pb')):
        return 'model'
    if suffix in {'.pt','.pth'}:
        if parts&MODELPARTS or any(word in name for word in ['epoch','best','last','model','checkpoint','weight']):return 'model'
        return 'input_numeric' if parts&INPUTPARTS else 'tensor_blob_review'
    if suffix in TEXT_SOURCE:return 'source'
    if suffix in DOCUMENTS:return 'report_or_document'
    if suffix in TEXT_RECORD:return 'numeric_or_execution_record'
    if suffix in ARRAYS:return 'input_numeric' if parts&INPUTPARTS else 'result_numeric'
    if suffix in IMAGES:return 'input_image' if parts&INPUTPARTS else 'result_image'
    if suffix in {'.zip','.7z','.rar','.tar','.gz'}:return 'package'
    return 'other_review'

def coverage(size,actual_sha,published_size,published_sha):
    if published_size is None:return 'absent_path'
    if size!=published_size:return 'size_changed'
    if actual_sha is None:return 'size_candidate_NOT_VERIFIED'
    return 'SHA256_VERIFIED' if actual_sha==published_sha else 'content_changed'

def owner(relative,scopes):
    value=relative.casefold()
    for prefix,identifier in scopes:
        if value==prefix or value.startswith(prefix+'/'):return identifier
    parts=PurePosixPath(relative).parts
    return 'project/'+(parts[0] if len(parts)>1 else 'root_documents')

def bounded_archive_source(physical,archive):
    """An imported path must never expand into the whole archive/operation tree."""
    try:tail=physical.absolute().relative_to(archive.absolute())
    except ValueError:return None
    if not tail.parts or tail.parts[0].casefold() not in ARCHIVE_DOMAINS-{'active_runs','compatibility_views'}:
        return None
    # Domain + registered batch. A drive root or domain-wide projection is not
    # enough evidence to walk unrelated backups, environments or our own output.
    if len(tail.parts)<2:return None
    return tail

def known_manifests(root,archive):
    old=archive/'reproducibility/20261016_github_reproduction'
    prior=archive/'reproducibility/20261020_github_reproduction'
    four=archive/'reproducibility/20261021_four_round_github_reproduction'
    repository_manifest=root/'docs/reproducibility/REPOSITORY_FILES.json.gz'
    repository_release=read_json(repository_manifest).get('fixed_release','research-preservation-20261021')
    return [(repository_manifest,repository_release),
      (old/'training_source_kit_bundle/RESEARCH_ASSETS.json.gz','research-training-kits-20261016'),
      (old/'shared_source_bundle_v2/RESEARCH_ASSETS.json.gz','research-shared-sources-20261016'),
      (old/'results_models_bundle/RESTORE_MANIFEST_20261016.json.gz','research-results-models-20261016'),
      (old/'historical_evidence_bundle/RESEARCH_ASSETS.json.gz','research-historical-evidence-20261016'),
      (prior/'R93_complete_record_bundle/RESEARCH_ASSETS.json.gz','r93-complete-record-20261020'),
      *[(four/f'R{n}_complete_record_bundle/RESEARCH_ASSETS.json.gz',f'r{n}-complete-record-20261021') for n in [94,95,97,98]],
      (four/'camera_origins_bundle/RESEARCH_ASSETS.json.gz','four-round-preview-origins-20261021')]

def derive_archive_maps(root,archive):
    """Infer only well-supported canonical H snapshot projections; keep evidence."""
    old=archive/'reproducibility/20261016_github_reproduction'
    votes=Counter()
    archive_absolute=archive.absolute()
    for filename in ['results_models_selection.json','historical_evidence_selection.json','essential_source_selection.json','final_repository_selection.json']:
        path=old/filename
        if not path.exists():continue
        data=read_json(path);rows=data.get('files',[]) if isinstance(data,dict) else data
        for row in rows:
            source=row.get('source')
            if not source:continue
            physical=Path(source)
            # The old selection is an explicit absolute source list. Resolving
            # every file would perform hundreds of thousands of redundant disk
            # lookups before inventory even starts. Resolve accepted roots below;
            # do not follow a source merely because its lexical path matches.
            if not physical.is_absolute() or '..' in physical.parts:continue
            try:inside=physical.absolute().relative_to(archive_absolute)
            except (OSError,ValueError):continue
            if not inside.parts or inside.parts[0].casefold() not in ARCHIVE_DOMAINS-{'active_runs','compatibility_views'}:continue
            try:logical=PurePosixPath(safe_relative(row['path']))
            except ValueError:continue
            a=physical.parts;b=logical.parts;n=0
            while n<min(len(a),len(b)) and a[-1-n].casefold()==b[-1-n].casefold():n+=1
            if n<3:continue
            physical_prefix=Path(*a[:-n]);logical_prefix=PurePosixPath(*b[:-n]).as_posix()
            if logical_prefix=='.':logical_prefix=''
            if bounded_archive_source(physical_prefix,archive) is None:continue
            votes[(str(physical_prefix),logical_prefix)]+=1
    candidates=[]
    for (physical,logical),count in votes.items():
        if count>=2 and Path(physical).is_dir():candidates.append({'physical':physical,'logical':logical,'supporting_published_files':count,'origin':'published_selection_projection'})
    # Canonical snapshots with an explicit snapshot directory have unambiguous roots.
    for sub,logical in [('main_training_history','Traing_Progress')]:
        for snapshot in (archive/sub).glob('*/snapshot'):
            candidates.append({'physical':str(snapshot),'logical':logical,'supporting_published_files':0,'origin':'registered_snapshot_layout'})
    for snapshot in (archive/'legacy').glob('*/*/snapshot'):
        candidates.append({'physical':str(snapshot),'logical':'Traing_Progress/'+snapshot.parent.parent.name,'supporting_published_files':0,'origin':'legacy_snapshot_layout'})
    for name in (archive/'experiments').glob('*'):
        if not name.is_dir():continue
        for date in name.iterdir():
            if not date.is_dir():continue
            for candidate in [date/'snapshot',date/'payload',date]:
                if any((candidate/n).exists() for n in ['model','training','config','README.md','MANIFEST.md']):
                    candidates.append({'physical':str(candidate),'logical':'Experiments/'+name.name,'supporting_published_files':0,'origin':'experiment_snapshot_layout'});break
    # Multi-root Lab snapshots preserve paths relative to LabSystem_MOSR.
    # Retain contextual records separately from payload rather than mapping
    # backup bookkeeping onto a current experiment's README.
    for name in (archive/'lab_system').glob('*'):
        if not name.is_dir():continue
        for date in name.iterdir():
            if not date.is_dir():continue
            for label in ['payload','snapshot']:
                candidate=date/label
                if candidate.is_dir():
                    candidates.append({'physical':str(candidate),'logical':'Thesis_MOSR_Evidence/LabSystem_MOSR','supporting_published_files':0,'origin':'lab_multi_root_snapshot'});break
    # Include the bounded archive records themselves, including older versions.
    # They cannot pull in reproduction downloads, runtime libraries or live runs.
    for domain in sorted(ARCHIVE_DOMAINS-{'active_runs','compatibility_views'}):
        for batch in (archive/domain).glob('*'):
            if batch.is_dir():
                candidates.append({'physical':str(batch),'logical':'Historical_Archive/'+domain+'/'+batch.name,'supporting_published_files':0,'origin':'bounded_historical_context'})
    # Remove redundant child projections only when their logical mapping agrees.
    accepted=[]
    ordered=sorted(candidates,key=lambda r:(r['origin']=='bounded_historical_context',len(Path(r['physical']).parts),-r['supporting_published_files']))
    for row in ordered:
        source=Path(row['physical']).resolve();logical=PurePosixPath(row['logical']);redundant=False
        for parent in accepted:
            try:tail=source.relative_to(Path(parent['physical']))
            except ValueError:continue
            mapped=(PurePosixPath(parent['logical'])/PurePosixPath(tail.as_posix())).as_posix().strip('./')
            if mapped.casefold()==row['logical'].strip('./').casefold():redundant=True;break
        if not redundant:accepted.append({**row,'physical':str(source)})
    return accepted

def inventory(root,archive,output,resume=False):
    if output.exists() and not resume:raise FileExistsError('Use a new audit operation directory, or explicitly resume its inventory')
    if output.resolve().is_relative_to(root.resolve()):raise ValueError('Keep the large inventory outside the research checkout')
    output.mkdir(parents=True,exist_ok=resume)
    policy=read_json(root/'docs/operations/PROJECT_STORAGE_POLICY.json')
    min_free=int(policy['archive']['minimum_free_gib']*1024**3)
    import shutil
    if shutil.disk_usage(output).free<min_free+2*1024**3:raise RuntimeError('Respect the archive free-space reserve')
    scope_rows=read_json(root/'docs/reproducibility/experiment_index.json')
    scopes=sorted([(r['scope'].replace('\\','/').casefold(),r['id']) for r in scope_rows],key=lambda pair:-len(pair[0]))
    env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
    head=subprocess.check_output(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],cwd=root,env=env).decode().strip()
    baseline={'status':'AUDIT_STARTED','source_HEAD':head,'index_sha256':sha(root/'.git/index'),
      'published_base_commit':subprocess.check_output(['git','rev-parse','codex/research-preservation-20261021'],cwd=root,env=env).decode().strip(),
      'registered_experiment_scopes':len(scope_rows),'minimum_H_free_bytes':min_free,'D_deletion_allowed':False,'GPU_work_allowed':False,
      'completion_criteria':['Every registered experiment and non-experiment research domain has an evidence-based method/source/result entry',
        'All existing necessary model histories, numeric results, important images, failures and irreproducible source bytes are on GitHub or explicitly recorded as historically unavailable',
        'Generated data omitted only with an exact complete rebuild verification, never merely because a seed exists',
        'Independent GitHub-only native/model/numeric replay performed where applicable; external proprietary dependencies and ongoing work identified',
        'No D cleanup, model promotion, active training interference, or thesis source modification']}
    if resume:
        prior=read_json(output/'BASELINE.json')
        if any(prior[k]!=baseline[k] for k in ['source_HEAD','index_sha256','published_base_commit']):
            raise ValueError('Original checkout/index or published source baseline changed')
    else:write_json(output/'BASELINE.json',baseline)
    db=sqlite3.connect(output/'inventory.sqlite',timeout=120)
    if not resume:db.executescript('''
      PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;
      CREATE TABLE published(path_key TEXT PRIMARY KEY,path TEXT,bytes INTEGER,sha256 TEXT,release TEXT,asset TEXT);
      CREATE INDEX published_sha ON published(sha256);
      CREATE TABLE files(id INTEGER PRIMARY KEY,source TEXT UNIQUE,logical_path TEXT,path_key TEXT,scope TEXT,kind TEXT,bytes INTEGER,mtime_ns INTEGER,origin TEXT,sha256 TEXT,published_state TEXT,published_sha TEXT,published_release TEXT);
      CREATE INDEX files_scope_kind ON files(scope,kind);
      CREATE INDEX files_path ON files(path_key);
      CREATE TABLE edges(source TEXT,logical_path TEXT,target TEXT,kind TEXT);
      CREATE TABLE excluded(path TEXT,reason TEXT);
      CREATE TABLE errors(path TEXT,operation TEXT,message TEXT);
    ''')
    for manifest,tag in ([] if resume else known_manifests(root,archive)):
        data=read_json(manifest)
        for row in data['files']:
            key=safe_relative(row['path']).casefold();value=(key,row['path'],row['bytes'],row['sha256'],tag,row.get('asset','ordinary_repository'))
            old=db.execute('SELECT sha256,bytes FROM published WHERE path_key=?',(key,)).fetchone()
            if old and old!=(row['sha256'],row['bytes']):raise ValueError('Published manifests conflict: '+row['path'])
            db.execute('INSERT OR IGNORE INTO published VALUES (?,?,?,?,?,?)',value)
        db.commit()
    print('PUBLISHED_CATALOG_IMPORTED',db.execute('SELECT COUNT(*) FROM published').fetchone()[0],flush=True)
    if resume and (output/'ARCHIVE_PROJECTIONS.json').exists():maps=read_json(output/'ARCHIVE_PROJECTIONS.json')
    else:
        maps=derive_archive_maps(root,archive);write_json(output/'ARCHIVE_PROJECTIONS.json',maps)
    print('BOUNDED_ARCHIVE_ROOTS_REVIEWABLE',len(maps),flush=True)
    queue=[(root,'','D_worktree')]+[(Path(r['physical']),r['logical'],'H_snapshot') for r in maps]
    scanned=set();known_queued={str(p.resolve()).casefold() for p,_,_ in queue};counter=0;started=time.time()
    for physical,logical,origin in queue:
        stack=[(physical,logical)]
        while stack:
            folder,relative=stack.pop();identity=str(folder.absolute()).casefold()
            if identity in scanned:continue
            scanned.add(identity)
            try:entries=list(os.scandir(folder))
            except OSError as e:db.execute('INSERT INTO errors VALUES (?,?,?)',(str(folder),'scandir',type(e).__name__));continue
            for entry in entries:
                target_rel=(PurePosixPath(relative)/entry.name).as_posix()
                try:info=entry.stat(follow_symlinks=False)
                except OSError as e:db.execute('INSERT INTO errors VALUES (?,?,?)',(entry.path,'stat',type(e).__name__));continue
                reparse=bool(getattr(info,'st_file_attributes',0)&stat.FILE_ATTRIBUTE_REPARSE_POINT)
                if entry.is_dir(follow_symlinks=False) or (reparse and Path(entry.path).is_dir()):
                    if dependency_directory(Path(entry.path),entry.name):
                        db.execute('INSERT INTO excluded VALUES (?,?)',(entry.path,'dependency runtime, VCS internals or reproducible cache'));continue
                    if reparse:
                        try:destination=Path(entry.path).resolve();value=str(destination)
                        except OSError as e:db.execute('INSERT INTO errors VALUES (?,?,?)',(entry.path,'resolve',type(e).__name__));continue
                        if not db.execute('SELECT 1 FROM edges WHERE source=?',(entry.path,)).fetchone():
                            db.execute('INSERT INTO edges VALUES (?,?,?,?)',(entry.path,target_rel,value,'directory_reference'))
                        # In-project targets are independently scanned at their real location.
                        if destination.is_relative_to(root.resolve()):continue
                        if destination.is_relative_to(archive.resolve()):
                            identity=str(destination).casefold()
                            if identity not in known_queued:
                                queue.append((destination,target_rel,'registered_H_reference'));known_queued.add(identity)
                        continue
                    stack.append((Path(entry.path),target_rel));continue
                if reparse:
                    db.execute('INSERT INTO excluded VALUES (?,?)',(entry.path,'reparse file requires explicit provenance review'));continue
                logical_safe=safe_relative(target_rel);key=logical_safe.casefold();kind=classify(logical_safe)
                published=db.execute('SELECT bytes,sha256,release FROM published WHERE path_key=?',(key,)).fetchone()
                state=coverage(info.st_size,None,published[0] if published else None,published[1] if published else None)
                db.execute('INSERT OR IGNORE INTO files(source,logical_path,path_key,scope,kind,bytes,mtime_ns,origin,published_state,published_sha,published_release) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (entry.path,logical_safe,key,owner(logical_safe,scopes),kind,info.st_size,info.st_mtime_ns,origin,state,published[1] if published else None,published[2] if published else None))
                if resume:
                    db.execute('UPDATE files SET bytes=?,mtime_ns=?,sha256=NULL,published_state=? WHERE source=? AND (bytes<>? OR mtime_ns<>?)',
                      (info.st_size,info.st_mtime_ns,'source_changed_during_inventory',entry.path,info.st_size,info.st_mtime_ns))
                counter+=1
                if counter%5000==0:db.commit()
                if counter%50000==0:db.commit();print('PROJECT_FILES_INVENTORIED',counter,round(time.time()-started,1),flush=True)
        db.commit()
    summary=[]
    for scope,kind,state,count,size in db.execute('SELECT scope,kind,published_state,COUNT(*),SUM(bytes) FROM files NOT INDEXED GROUP BY scope,kind,published_state'):
        summary.append({'scope':scope,'kind':kind,'publication_state':state,'files':count,'bytes':size})
    errors=db.execute('SELECT COUNT(*) FROM errors').fetchone()[0]
    write_json(output/'SCOPE_INVENTORY.json',{'status':'METADATA_INVENTORY_ONLY_NOT_REPRODUCTION_COMPLETE','files':db.execute('SELECT COUNT(*) FROM files').fetchone()[0],
      'published_original_paths':db.execute('SELECT COUNT(*) FROM published').fetchone()[0],'read_errors':errors,'archive_projections':len(maps),
      'directory_reference_edges':db.execute('SELECT COUNT(*) FROM edges').fetchone()[0],'summary':summary,'seconds':time.time()-started})
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,env=env).decode().strip()==head
    assert sha(root/'.git/index')==baseline['index_sha256']
    print('PROJECT_METADATA_AUDIT_COMPLETE',counter,'errors',errors,flush=True)

def verify(root,output,kinds,workers=2):
    db=sqlite3.connect(output/'inventory.sqlite',timeout=120);db.row_factory=sqlite3.Row
    db.execute('PRAGMA cache_size=-262144')
    # The published catalog is small compared with the research payload. Keeping
    # it in memory avoids two random archive-disk lookups per tiny data file.
    published_paths={};published_objects={}
    for value in db.execute('SELECT path_key,bytes,sha256,release FROM published'):
        entry=dict(value);published_paths[entry['path_key']]=entry
        published_objects.setdefault((entry['sha256'],entry['bytes']),entry)
    where=','.join('?' for _ in kinds)
    total=db.execute(f'SELECT COUNT(*) FROM files WHERE kind IN ({where}) AND sha256 IS NULL',kinds).fetchone()[0]
    # Bound memory even for several million image paths. File ID order keeps
    # physical directory traversal locality and avoids a giant temporary sort.
    cursor=db.execute(f'SELECT * FROM files WHERE kind IN ({where}) AND sha256 IS NULL ORDER BY id',kinds)
    count=0;changed=[];failed=[]
    def inspect(row):
        source=Path(row['source'])
        try:
            before=source.stat();digest=sha(source);after=source.stat()
            if (before.st_size,before.st_mtime_ns)!=(row['bytes'],row['mtime_ns']) or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                return row,None,'changed'
            return row,digest,None
        except OSError as e:return row,None,type(e).__name__
    with ThreadPoolExecutor(max_workers=workers) as pool:
      def results():
          while batch:=cursor.fetchmany(512):
              # The archive is a shared spinning disk. Parallel reads there
              # amplify seeking and can stall the protected training's I/O.
              iterator=pool.map(inspect,batch) if all(r['origin']=='D_worktree' for r in batch) else map(inspect,batch)
              yield from iterator
      for row,digest,error in results():
        if error:
            if error=='changed':changed.append(row['source'])
            else:
                failed.append({'path':row['source'],'error':error})
                db.execute('INSERT INTO errors VALUES (?,?,?)',(row['source'],'hash',error))
            continue
        else:
            published=published_paths.get(row['path_key'])
            state=coverage(row['bytes'],digest,published['bytes'] if published else None,published['sha256'] if published else None)
            if state!='SHA256_VERIFIED':
                alternate=published_objects.get((digest,row['bytes']))
                if alternate:state='SHA256_PRESENT_OTHER_PATH_alias_needed'
            db.execute('UPDATE files SET sha256=?,published_state=? WHERE id=?',(digest,state,row['id']));count+=1
            if count%200==0:db.commit()
            if count%1000==0:print('PROJECT_CONTENTS_CHECKED',count,total,flush=True)
    cursor.close()
    db.commit()
    summary=[dict(r) for r in db.execute('SELECT kind,published_state,COUNT(*) AS files,SUM(bytes) AS bytes FROM files WHERE kind IN ('+where+') GROUP BY kind,published_state',kinds)]
    write_json(output/('CONTENT_CHECK_'+'_'.join(kinds)+'.json'),{'status':'PASS' if not changed and not failed else 'SOURCE_READ_OR_CHANGES_REQUIRE_REVIEW','kinds':kinds,'checked':count,'source_changed':changed,'read_errors':failed,'summary':summary})
    print('PROJECT_CONTENT_AUDIT_FINISHED',json.dumps(summary),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ['inventory','verify']:
        q=sub.add_parser(name);q.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);q.add_argument('--output',type=Path,required=True)
        if name=='inventory':
            q.add_argument('--archive-root',type=Path,default=Path(r'H:\GMM_2_Final_Archive'))
            q.add_argument('--resume',action='store_true')
        else:
            q.add_argument('--kinds',nargs='+',default=['model','tensor_blob_review'])
            q.add_argument('--workers',type=int,choices=range(1,9),default=2)
    a=p.parse_args()
    if a.command=='inventory':inventory(a.root,a.archive_root,a.output,a.resume)
    else:verify(a.root,a.output,a.kinds,a.workers)

if __name__=='__main__':main()
