"""Hash the frozen research inventory without random archive-disk DB traffic.

Source files are read only. A bounded-memory pool reads SSD files in parallel
and the shared archive disk sequentially. A durable append journal preserves
progress. An existing NTFS hardlink can reuse an already hashed file identity;
equal names/sizes alone never establish identity.
"""
import argparse,gzip,hashlib,json,os,sqlite3,sys,time
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

from project_reproducibility_audit import sha,coverage,classify,owner,write_json

FAMILIES=[('context',['source','report_or_document','numeric_or_execution_record']),
 ('models',['model','tensor_blob_review']),('numeric',['input_numeric','result_numeric']),
 ('images',['input_image','result_image']),('packages',['package','other_review'])]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    op=a.output;src=op/'verified_inventory/inventory.sqlite';started=time.time()
    if os.name=='nt':
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in ['total','available','total_page','available_page','total_virtual','available_virtual','extended']]
        info=MemoryStatus();info.length=ctypes.sizeof(info)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):raise OSError('Cannot check available memory')
        if info.available<src.stat().st_size*1.5+12*1024**3:raise RuntimeError('Leave sufficient memory for the protected training; memory-index audit not started')
    source=sqlite3.connect('file:'+str(src)+'?mode=ro',uri=True,timeout=120)
    mem=sqlite3.connect(':memory:');mem.row_factory=sqlite3.Row;mem.execute('PRAGMA temp_store=MEMORY')
    last=[0]
    def progress(status,remaining,total):
        done=total-remaining
        if done-last[0]>=100000 or not remaining:
            print('AUDIT_METADATA_COPIED_TO_MEMORY',done,total,flush=True);last[0]=done
    source.backup(mem,pages=8192,progress=progress);source.close()
    print('SOURCE_FILES_WILL_REMAIN_READ_ONLY',flush=True)
    journal=op/'CONTENT_HASH_PROGRESS.jsonl'
    if journal.exists():
        with journal.open('r',encoding='utf-8') as stream:
            for line in stream:
                try:r=json.loads(line)
                except json.JSONDecodeError:continue # only a torn final record can be incomplete
                mem.execute('UPDATE files SET sha256=?,published_state=? WHERE id=? AND bytes=? AND mtime_ns=?',
                  (r['sha256'],r['state'],r['id'],r['bytes'],r['mtime_ns']))
        mem.commit()
    # Refresh only source files created/edited by this preservation task.
    own=json.loads((op/'FIRST_SOURCE_COMMIT.json').read_text(encoding='utf-8'))['files']
    own += [{'path':v} for v in ['Tools/publish_research_batch.py','Tools/replay_shared_model_history.py','Tools/hash_research_inventory_in_memory.py']]
    scopes=sorted([(r['scope'].casefold(),r['id']) for r in json.loads((a.root/'docs/reproducibility/experiment_index.json').read_text(encoding='utf-8-sig'))],key=lambda r:-len(r[0]))
    for row in own:
        path=a.root/row['path'];info=path.stat();prior=mem.execute('SELECT id,bytes,mtime_ns FROM files WHERE source=?',(str(path),)).fetchone()
        if prior:
            if (prior['bytes'],prior['mtime_ns'])!=(info.st_size,info.st_mtime_ns):
                mem.execute('UPDATE files SET bytes=?,mtime_ns=?,sha256=NULL,published_state=? WHERE id=?',(info.st_size,info.st_mtime_ns,'owned_source_refreshed',prior['id']))
        else:
            mem.execute('INSERT INTO files(source,logical_path,path_key,scope,kind,bytes,mtime_ns,origin,published_state) VALUES (?,?,?,?,?,?,?,?,?)',
              (str(path),row['path'],row['path'].casefold(),owner(row['path'],scopes),classify(row['path']),info.st_size,info.st_mtime_ns,'D_worktree','owned_source_added'))
    mem.commit()
    published={};objects={}
    for row in mem.execute('SELECT path_key,path,bytes,sha256,release,asset FROM published'):
        value=dict(row);published[value['path_key']]=value;objects.setdefault((value['sha256'],value['bytes']),value)
    with gzip.open(op/'PUBLISHED_CATALOG.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as stream:
        for value in published.values():stream.write(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')
    identity_cache={};lock=Lock();errors=[];proof_counts=Counter();family_reports=[]
    def inspect(row):
        path=Path(row['source'])
        try:
            before=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(row['bytes'],row['mtime_ns']):return row,None,'SOURCE_CHANGED',None
            identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
            with lock:known=identity_cache.get(identity) if before.st_ino and before.st_nlink>1 else None
            if known:checksum=known;proof='same_file_identity'
            else:checksum=sha(path);proof='read_and_hashed'
            after=path.stat()
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):return row,None,'SOURCE_CHANGED',None
            if before.st_ino and before.st_nlink>1:
                with lock:identity_cache[identity]=checksum
            return row,checksum,None,proof
        except OSError as error:return row,None,type(error).__name__,None
    with journal.open('a',encoding='utf-8',buffering=1024**2) as log,ThreadPoolExecutor(max_workers=4) as pool:
      for family,kinds in FAMILIES:
        placeholders=','.join('?' for _ in kinds)
        cursor=mem.execute('SELECT * FROM files WHERE kind IN ('+placeholders+') AND sha256 IS NULL ORDER BY id',kinds)
        total=mem.execute('SELECT COUNT(*) FROM files WHERE kind IN ('+placeholders+') AND sha256 IS NULL',kinds).fetchone()[0]
        done=0;new_bytes=0
        while batch:=cursor.fetchmany(512):
            results=pool.map(inspect,batch) if all(r['origin']=='D_worktree' for r in batch) else map(inspect,batch)
            for row,checksum,error,proof in results:
                if error:
                    errors.append({'id':row['id'],'source':row['source'],'error':error});continue
                prior=published.get(row['path_key'])
                state=coverage(row['bytes'],checksum,prior['bytes'] if prior else None,prior['sha256'] if prior else None)
                if state!='SHA256_VERIFIED' and (checksum,row['bytes']) in objects:state='SHA256_PRESENT_OTHER_PATH_alias_needed'
                mem.execute('UPDATE files SET sha256=?,published_state=? WHERE id=?',(checksum,state,row['id']))
                log.write(json.dumps({'id':row['id'],'bytes':row['bytes'],'mtime_ns':row['mtime_ns'],'sha256':checksum,'state':state,'proof':proof},separators=(',',':'))+'\n')
                done+=1;new_bytes+=row['bytes'];proof_counts[proof]+=1
                if done%1000==0:
                    log.flush();mem.commit()
                    write_json(op/'ALL_CONTENT_MEMORY_PROGRESS.json',{'family':family,'checked':done,'to_check':total,'bytes_checked':new_bytes,'seconds':time.time()-started,'errors':errors,'completed_families':family_reports})
                    print('RESEARCH_CONTENT_CHECKED',family,done,total,new_bytes,flush=True)
        cursor.close();mem.commit();log.flush()
        export=op/('HASHED_'+family.upper()+'_FILES.jsonl.gz');count=0;size=0;states=Counter()
        with gzip.open(export,'wt',encoding='utf-8',compresslevel=1) as stream:
            for row in mem.execute('SELECT * FROM files WHERE kind IN ('+placeholders+') ORDER BY id',kinds):
                stream.write(json.dumps(dict(row),ensure_ascii=False,separators=(',',':'))+'\n');count+=1;size+=row['bytes'];states[row['published_state']]+=1
        report={'family':family,'files':count,'bytes':size,'new_checks':done,'states':dict(states),'export':export.name}
        family_reports.append(report);write_json(op/('CONTENT_'+family.upper()+'_HASHED.json'),{'status':'PASS' if not errors else 'REVIEW_REQUIRED',**report,'errors':errors})
        print('CONTENT_FAMILY_EXPORTED',family,count,size,flush=True)
        if errors:raise RuntimeError('Source changed or could not be read; no publication-complete claim is allowed')
    final=op/'inventory_content_verified.sqlite'
    if final.exists():raise FileExistsError('Keep the prior completed inventory')
    destination=sqlite3.connect(final);mem.backup(destination,pages=8192);destination.close()
    write_json(op/'ALL_RESEARCH_CONTENT_HASHED.json',{'status':'ALL_REQUESTED_FAMILIES_CONTENT_CHECKED','families':family_reports,
      'proof_counts':dict(proof_counts),'seconds':time.time()-started,'verified_inventory':final.name,'publication_complete':False,'original_research_files_modified':False})
    print('ALL_RESEARCH_CONTENT_HASHED_NOT_YET_PUBLICATION_COMPLETE',flush=True)

if __name__=='__main__':main()
