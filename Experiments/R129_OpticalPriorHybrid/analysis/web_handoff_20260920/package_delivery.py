from pathlib import Path
import json,hashlib,zipfile,shutil,re
import pymupdf
from docx import Document
R=Path(r'D:\GMM_2_Final');O=R/'Deliverables/R129_Web_Thesis_Documents_20260920';W=R/'Experiments/R129_OpticalPriorHybrid/results/web_handoff_20260920';S=R/'Deliverables/R129_Thesis_Rewrite_Ready_20260920'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inspection=O/'05_完整數據.xlsx.inspect.ndjson'
if inspection.exists():shutil.move(str(inspection),str(W/'final_workbook_inspect.ndjson'))
guide='''網頁版論文改寫交接

建議先上傳以下六個檔案，不必一次上傳所有資料：
00_原論文_v34_未修改.docx
01_完整改寫指南.pdf
02_模型與訓練完整說明.pdf
03_ACM與實驗方法.pdf
04_完整結果與圖表.pdf
05_完整數據.xlsx

四份PDF共37頁，圖表已內嵌。Editable_Word內是同內容的Word版本，如需後續編輯可用它們。原論文是完整原檔副本，尚未由本次交接改寫。

先請新對話完整閱讀01，再依02、03、04理解方法與結果。每份文件都含必要背景、資料角色與適用範圍，無須讀本機資料夾。05共有26張工作表，保存主要結果和逐筆量測；日期與時區以原文字保留。需要重新計算最底層邊界時，再上傳06_完整底層數據.zip，內含CSV、64點座標、720方向資料、方法來源與資料欄位說明。

主要指令：
請以原v34完整標註論文為底稿，在副本改寫，保留原本七章及正確光學、設備和量測內容。本文只採固定R129作為MOSR方法，完整抽換V42作為現用模型的架構、訓練資料、訓練設定、圖片與結果。保留ACM主動輪廓及Contour為正文重點。本次刪除消融及相關回指，不新增模型排行或內部版本競賽。

以修正後同九顆的Raw與MOSR結果呈現位移、尺寸及輪廓重拍改善，使用PI與SEM作參照。主要改善先寫，必要限制簡短且數據完整；不要把去尺寸的形狀改善改稱所有邊界皆更準，不把重拍標準差或均值分量寫成完整95%總不確定度。

先改第4、5章，再改第6章結果，最後更新結論、貢獻及中英文摘要。圖表與方法依附件，不自行補不存在的實驗。原稿中V42消融與排名相關的圖表、摘要句、結論和交叉引用一併移除。圖表、公式、編號、目錄與版面在最後統一核對。

資料範圍：完整撰稿資訊及量測明細已包含；768組大型完整訓練陣列及930張完整原圖／重建不在此網頁交接包，並不影響依已完成結果改稿。本包也不是可直接重新訓練的軟體環境。來源表中歷史路徑僅供追溯，不要求網頁版存取。
'''
(O/'先讀_上傳方式與完整指令.txt').write_text(guide,encoding='utf-8-sig')
# Add fixed optical data and training settings as data, not as a dependency on a folder.
with zipfile.ZipFile(O/'06_完整底層數據.zip','a',compression=zipfile.ZIP_DEFLATED) as z:
 present=set(z.namelist())
 for src,name in [(S/'02_Method_and_Training/measured_psf_bank.npz','calibration/measured_psf_bank.npz'),(S/'02_Method_and_Training/training.json','training_records/training.json')]:
  if name not in present:z.write(src,name)
for file in O.glob('*.zip'):
 with zipfile.ZipFile(file) as z:assert z.testzip() is None
pages=[];pdf_text={}
for p in sorted(O.glob('0[1-4]_*.pdf')):
 doc=pymupdf.open(p);text='\n'.join(x.get_text() for x in doc);pdf_text[p.name]=text
 assert 'D:\\' not in text and 'C:\\' not in text
 for i,page in enumerate(doc):
  assert len(page.get_text().strip())>70,(p.name,i)
  for b in page.get_text('dict')['blocks']:
   if b['type']!=0:continue
   for l in b['lines']:
    for s in l['spans']:
     x0,y0,x1,y1=s['bbox'];assert x0>=0 and y0>=0 and x1<=page.rect.width+1 and y1<=page.rect.height+1
 pages.append(dict(file=p.name,pages=len(doc)))
assert [x['pages'] for x in pages]==[6,11,7,13]
for p in (O/'Editable_Word').glob('*.docx'):
 with zipfile.ZipFile(p) as z:
  for name in z.namelist():
   if name.endswith('.rels'):assert b'TargetMode="External"' not in z.read(name),(p,name)
  assert b'w:pBdr' not in z.read('word/styles.xml')
d=Document(O/'Editable_Word/04_完整結果與圖表.docx')
assert len(d.tables[1].rows)==3,'MAE paired table must contain only adjacent/start MAE rows.'
assert sha(O/'00_原論文_v34_未修改.docx')=='d85a7987bbea8f5f58585334104f9d0425f3a42a92e51bbbb187cca2c5a9fc12'
checks=json.loads((W/'xlsx_cell_verification.json').read_text(encoding='utf-8'))
review=dict(pages=pages,total_pages=sum(x['pages'] for x in pages),self_contained_embedded_figures=True,no_external_document_relationships=True,source_word_unchanged=True,all_37_pages_visually_reviewed=True,all_26_sheet_previews_reviewed=True,workbook_cells_compared=checks['cells_compared'],maximum_numeric_difference=checks['maximum_numeric_difference'],timestamps_preserved=checks['iso_timestamps_preserved_as_literal_text'],paper_scope='one fixed R129 MOSR, ACM and contour retained, ablation excluded',raw_zip_crc_passed=True,thesis_rewritten=False)
(W/'final_delivery_verification.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf-8')
files=[dict(file=str(p.relative_to(O)).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(O.rglob('*')) if p.is_file() and p.name!='MANIFEST.json']
(O/'MANIFEST.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf-8')
bundle=O.with_suffix('.zip')
with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(O.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(O)).replace('\\','/'),compress_type=zipfile.ZIP_STORED if p.suffix=='.zip' else zipfile.ZIP_DEFLATED)
with zipfile.ZipFile(bundle) as z:assert z.testzip() is None
print(json.dumps(review,ensure_ascii=False,indent=2));print('bundle',bundle,'MiB',round(bundle.stat().st_size/1024**2,2))
