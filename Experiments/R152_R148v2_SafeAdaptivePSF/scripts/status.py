from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/formal_8192'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else None
def main():
 status=read(RUN/'status.json');complete=read(RUN/'training_complete.json');latest=read(RUN/'latest.json');print(json.dumps(dict(status=status,latest=latest,complete=complete,stdout=str(ROOT/'runs/formal_8192.stdout.log'),stderr=str(ROOT/'runs/formal_8192.stderr.log')),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
