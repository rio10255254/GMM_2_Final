import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def main():
 lock=json.loads((ROOT/'config/SOURCE_LOCK.json').read_text(encoding='utf-8-sig'));fail=[]
 for relative,expected in lock['files'].items():
  path=ROOT/relative;actual=sha(path) if path.is_file() else None
  if actual!=expected:fail.append(dict(file=relative,expected=expected,actual=actual))
 result=dict(status='passed' if not fail else 'failed',checked=len(lock['files']),failures=fail);print(json.dumps(result,indent=2));sys.exit(1 if fail else 0)
if __name__=='__main__':main()
