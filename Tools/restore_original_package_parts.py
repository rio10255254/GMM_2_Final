"""Reassemble a preserved original distribution ZIP from verified GitHub parts."""
import argparse,hashlib,json
from pathlib import Path
from research_recovery import digest,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--parts',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or a.report.exists():raise FileExistsError('Do not overwrite an original package or verification report')
    m=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    if m.get('state')!='complete':raise ValueError('Incomplete original-package index')
    parts=[]
    for row in m['parts']:
        name=row['name']
        if Path(name).name!=name or ':' in name:raise ValueError('Unsafe part filename')
        source=a.parts/name
        if source.stat().st_size!=row['bytes'] or digest(source)!=row['sha256']:raise ValueError('Downloaded original-package part differs')
        parts.append(source)
    a.output.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();size=0
    with a.output.open('xb') as target:
        for source in parts:
            with source.open('rb') as stream:
                while block:=stream.read(4*1024**2):h.update(block);size+=len(block);target.write(block)
    if size!=m['original_bytes'] or h.hexdigest()!=m['original_sha256'] or digest(a.output)!=m['original_sha256']:
        raise ValueError('Reassembled package differs from the original distribution')
    write_json(a.report,{'status':'PASS','original_package_bytes':size,'original_sha256':m['original_sha256'],
      'parts':len(parts),'output':str(a.output),'research_originals_changed':False})
    print('ORIGINAL_DISTRIBUTION_PACKAGE_REASSEMBLED_VERIFIED',size,flush=True)

if __name__=='__main__':main()
