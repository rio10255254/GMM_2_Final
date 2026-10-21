from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
SOURCE=Path(r'D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF\results\training_deep_dive\report_snapshot.json')
target=ROOT/'src/data.json';old=json.loads(target.read_text(encoding='utf-8'));new=json.loads(SOURCE.read_text(encoding='utf-8'));new['id']=old['id'];new['surface']='report';new['buildStatus']='complete' if new['queries']['training_status']['rows'][0].get('formal_training_complete') else 'updating';target.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(target)
