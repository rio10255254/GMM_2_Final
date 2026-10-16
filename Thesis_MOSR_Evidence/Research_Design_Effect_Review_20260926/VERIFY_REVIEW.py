from pathlib import Path
import csv,hashlib,json,re
ROOT=Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 m=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'));missing=[];wrong=[]
 for r in m['records']:
  p=ROOT/r['destination']
  if not p.is_file():missing.append(r['destination'])
  elif sha(p)!=r['sha256']:wrong.append(r['destination'])
 source=list(csv.DictReader((ROOT/'SOURCE_INDEX.csv').open(encoding='utf-8-sig')));missing_sources=[r['source_path'] for r in source if not Path(r['source_path']).is_dir()]
 commentaries=list(ROOT.glob('0[1-4]_*/*/COMMENTARY.md'));round_readmes=list(ROOT.glob('0[1-4]_*/*/README.md'))
 review_docs=[ROOT/'README.md',ROOT/'00_START_HERE/README.md',*list((ROOT/'05_Cross_Round_Analysis').glob('*.md'))]
 broken=[]
 for p in review_docs:
  for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
   if target.startswith(('http://','https://')):continue
   if not (p.parent/target).exists():broken.append(f'{p.relative_to(ROOT)} -> {target}')
 result=dict(passed=not(missing or wrong or missing_sources or broken) and len(source)==21 and len(commentaries)==21 and len(round_readmes)==21,manifest_files=len(m['records']),manifest_bytes=m['bytes'],experiments=len(source),commentaries=len(commentaries),round_readmes=len(round_readmes),missing=missing,wrong_hash=wrong,missing_sources=missing_sources,broken_review_links=broken)
 (ROOT/'VERIFICATION_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
