from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
p=Path(str(PROJECT_ROOT / 'Experiments/R137_WeakPSFFeature/results/build_documents.py'));s=p.read_text(encoding='utf-8-sig');prefix,body=s.split('# Reuse only the previously reviewed document formatting class, not the old authoring execution.',1)
pre=p.with_name('prepare_doc_data.py');pre.write_text(prefix+"\nsave(P/'來源與核對/SOURCE_COPIES.json',source)\n",encoding='utf-8')
header='''from pathlib import Path
import ast,json,hashlib,shutil
import numpy as np,pandas as pd
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
R=Path(r'Experiments/R137_WeakPSFFeature');B=R.parent/'R130_Clean';P=Path(r'Deliverables/Thesis_Handoffs/R137_WeakPSF_Web_Documents_20260922');S=R/'results/comparison'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
t=load(R/'runs/formal_8192/training_complete.json');tables={p.stem:pd.read_csv(p) for p in S.glob('*.csv')};g=tables['shape_size_summary'];sem=tables['SEM_comparison']
colors={'Raw':'#777777','R129':'#2774AE','R130-Clean':'#E47722','R137-WeakPSF':'#198754'}
figs={p.stem:p for p in (P/'圖表').glob('*.png')};pillars=pd.read_csv(P/'完整數據/per_pillar_statistics.csv').to_dict('records');source=load(P/'來源與核對/SOURCE_COPIES.json')
explanation='2026年9月22日，使用者補充：這次較慢估計是 GPU 同時被另一個訓練程序佔用。此為使用者提出的可能原因；本輪沒有保存足以重建全程共用程度的 GPU 程序利用率時間序列，故不能量化影響，也不能證實所有時間差都由它造成。'
'''
p.with_name('author_docs.py').write_text(header+body,encoding='utf-8')
p.write_text('''from pathlib import Path
import subprocess
root=Path(__file__).resolve().parent
subprocess.run([rpython,str(root/'prepare_doc_data.py')],check=True)
subprocess.run([r'C:\\Users\\Rio\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe',str(root/'author_docs.py')],check=True)
''',encoding='utf-8')
