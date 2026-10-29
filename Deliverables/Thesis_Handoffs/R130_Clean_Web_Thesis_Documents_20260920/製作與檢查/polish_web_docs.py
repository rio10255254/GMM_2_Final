from pathlib import Path
from docx import Document
from docx.shared import Pt
PROJECT_ROOT = Path(__file__).resolve().parents[4]
P=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R130_Clean_Web_Thesis_Documents_20260920'))
for p in P.glob('*.docx'):
 d=Document(p)
 if p.name.startswith('03_'):
  d.styles['Heading 1'].paragraph_format.space_before=Pt(12)
  d.styles['Heading 1'].paragraph_format.space_after=Pt(5)
  d.save(p)
 if p.name.startswith('05_'):
  for para in d.paragraphs:
   if '4.4.3 是方向感知與局部強度調節殘差' in para.text:
    para.text=para.text.replace('4.4.3 是方向感知與局部強度調節殘差','4.4.3 是方向感知且受限的邊界殘差')
  d.save(p)
  md=P/'閱讀文字版'/(p.stem+'.md');md.write_text(md.read_text(encoding='utf-8').replace('4.4.3 是方向感知與局部強度調節殘差','4.4.3 是方向感知且受限的邊界殘差'),encoding='utf-8')
for name in ['sem_points.npz','tracking.csv']:
 import shutil
 shutil.copy2(Path(str(PROJECT_ROOT / 'Experiments/R130_Clean/evaluation'))/name,P/'完整數據'/name)
