from pathlib import Path
import hashlib,json,zipfile,shutil
from PIL import Image,ImageChops
from docx import Document
PROJECT_ROOT = Path(__file__).resolve().parents[3]
P=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R130_Clean_Web_Thesis_Documents_20260920'));R=Path(str(PROJECT_ROOT / 'Experiments/R130_Clean'));H=Path(str(PROJECT_ROOT / 'Deliverables/Thesis_Handoffs/R130_Clean_Corrected_Corner9_Validation_Handoff_20260920'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n in [1,3,4,5,6]:
 a=Image.open(R/f'results/web_docs_qa_final/05/page-{n}.png');b=Image.open(R/f'results/web_docs_qa_polished/05/page-{n}.png');assert ImageChops.difference(a,b).getbbox() is None
thesis=Path(r'C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文_v34_SEM與不利論述_完整標註版.docx');assert sha(thesis)=='d85a7987bbea8f5f58585334104f9d0425f3a42a92e51bbbb187cca2c5a9fc12'
qa=json.loads((P/'製作與檢查/validation.json').read_text(encoding='utf-8'));qa.update(rendered_pages={'01':2,'02':5,'03':3,'04':18,'05':6},rendered_page_images_visually_reviewed=True)
(P/'製作與檢查/validation.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
# Include a compact, user-facing table inventory with row counts and columns.
import pandas as pd
inventory=[]
for q in sorted((P/'完整數據').glob('*.csv')):
 v=pd.read_csv(q);inventory.append(dict(file=q.name,rows=len(v),columns=list(v.columns),sha256=sha(q)))
(P/'完整數據/TABLE_INVENTORY.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
(P/'完整數據/README.md').write_text('''# 全部詳細數據

主文 01 到 05 已包含可直接構思論文的解釋、主要數字與圖表。此處供查表、重新計算與追溯。

all_circles 是全部圓心和直徑；all_displacements 是九顆合成的位移；individual_circle_displacements 是逐顆位移。不能把兩種位移表混為同一統計單位。

position_statistics 是逐位置跨30趟；scan_statistics 是每趟30段；nine_pillar_size_shape 是逐顆；geometry_by_position 是逐位置的尺寸輪廓。angular_repeatability 是插值方向資料，不是新增量測點。

SEM_comparison 保留两個既有方向候選；sem_points、sem_scale 和 sem_mapping_candidates 是其參考來源。輪廓原始點保存每方法每趟的 31×9×64×2 實際邊界；radial_profiles 是720方向的插值半徑。

TABLE_INVENTORY 列出每張CSV的列數、欄名及內容識別。所有來源CSV均原值複製；Word表格因閱讀需要只顯示六位小數。訓練曲線來源及設定亦保存，不包含整套合成影像陣列或930張完整重建影像。

本包整理完成於2026年9月21日，採用2026年9月20日完成的固定實驗；資料夹和文件日期為該實驗日期。
''',encoding='utf-8')
shutil.copy2(H/'verify_package.py',P/'verify_package.py')
sources=[R/'reports/R130_CLEAN_RESULTS.md',R/'reports/TRAINING_PROVENANCE.md',R/'config/source_lock.json',R/'config_r130_clean.yaml',R/'model_r130_clean.py',R/'losses_r130_clean.py',R/'dataset_r130_clean.py',R/'compare_measurements.py',H/'MANIFEST.json',thesis]
(P/'製作與檢查/SOURCE_REFERENCES.json').write_text(json.dumps([dict(path=str(q),sha256=sha(q)) for q in sources],ensure_ascii=False,indent=2),encoding='utf-8')
items=[dict(path=q.relative_to(P).as_posix(),bytes=q.stat().st_size,sha256=sha(q)) for q in sorted(P.rglob('*')) if q.is_file() and q.name!='MANIFEST.json']
(P/'MANIFEST.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
small=P.parent.parent/'R130_Clean_五份論文文件_20260920.zip';full=P.with_suffix('.zip')
for dest,files in [(small,list(P.glob('*.docx'))+[P/'00_上傳與閱讀說明.md']),(full,[q for q in P.rglob('*') if q.is_file()])]:
 assert not dest.exists()
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for q in files:z.write(q,q.relative_to(P).as_posix())
 with zipfile.ZipFile(dest) as z:
  assert z.testzip() is None
  for q in files:assert hashlib.sha256(z.read(q.relative_to(P).as_posix())).hexdigest()==sha(q)
 dest.with_suffix('.zip.sha256').write_text(sha(dest)+'  '+dest.name+'\n',encoding='utf-8')
 print(dest.name,round(dest.stat().st_size/1024**2,2),'MiB')
print('FINAL:',len(items),'payload files; 5 documents; 34 rendered pages; archive contents independently compared')
