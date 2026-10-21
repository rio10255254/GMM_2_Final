from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import save,sha,now
from verify_package import FROZEN
def main():
 p=ROOT/'config/SOURCE_LOCK.json'
 if p.exists():raise FileExistsError(p)
 save(p,dict(purpose='R148v2 matched hybrid formal scratch8192',files={x:sha(ROOT/x) for x in FROZEN},created_utc=now()));print('SOURCE_LOCKED',len(FROZEN))
if __name__=='__main__':main()
