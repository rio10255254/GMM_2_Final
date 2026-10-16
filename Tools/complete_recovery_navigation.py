"""Add only missing post-hoc navigation, preserving historical scientific receipts."""
import argparse
import json
from pathlib import Path
import sqlite3

from research_recovery import write_json


def complete(root, catalog):
    notes=json.loads((root/'docs/reproducibility/review_notes.json').read_text(encoding='utf-8'))
    db=sqlite3.connect(catalog);created=[]
    for folder in sorted((root/'Experiments').iterdir()):
        if not folder.is_dir() or folder.name not in notes['main']:
            continue
        note=notes['main'][folder.name];scope=folder.relative_to(root).as_posix()
        card='../../docs/reproducibility/experiments/main__'+folder.name+'.md'
        docs=[p for p, in db.execute("SELECT path FROM files WHERE scope=? AND role='document_or_log' AND path LIKE '%.md' ORDER BY path",(scope,))]
        source=[p for p, in db.execute("SELECT path FROM files WHERE scope=? AND role='code_and_settings' ORDER BY path",(scope,))]
        reports=[p for p in docs if '/reports/' in p or '/selected/reports/' in p]
        if not reports:reports=docs
        if not (folder/'README.md').exists():
            text=[f'# {folder.name} 研究入口','',note[0],'',note[1],'',
                  '這份入口於2026年10月16日補建，用來找回既有研究；不是當初執行前的登錄，也不表示本輪已重新訓練。','',
                  f'[逐輪保存與重做判讀]({card})','']
            if reports:
                text += ['## 原始研究紀錄','']
                text += [f'- [{Path(p).name}]({Path(p).relative_to(Path(scope)).as_posix()})' for p in reports]
            else:
                text += ['現有內容以程式、表格或圖表版本記錄為主；不補造缺失的正式結論。','']
            (folder/'README.md').write_text('\n'.join(text)+'\n',encoding='utf-8');created.append(scope+'/README.md')
        if not (folder/'MANIFEST.md').exists():
            text=[f'# {folder.name} 研究保存清單','',
                  '清單建立日：2026年10月16日。這是整理既有成果時補建的導航清單，並非歷史預登錄、來源鎖或完成收據。原有SOURCE_LOCK、manifest、稽核及失敗記錄均保留原樣。','',
                  '## 研究問題與判讀','',note[0],'',note[1],'',
                  '## 必要來源','',note[2] if len(note)>2 else '依原始生成、設定、資料清單及當時模型來源重做，不以其他同名輪次取代。','',
                  '## 影像保存','',note[3] if len(note)>3 else '保留原圖、答案／重建、固定比較與不利案例；完整數值不按圖片成敗篩選。','',
                  '## 原始報告','']
            text += [f'- [{Path(p).name}]({Path(p).relative_to(Path(scope)).as_posix()})' for p in reports]
            text += ['', '## 程式查找','',
                     '以下列出實際存在的程式；它們是方法查找入口，不代表本次已重新執行所有歷史訓練。','']
            text += [f'- [{Path(p).relative_to(Path(scope)).as_posix()}]({Path(p).relative_to(Path(scope)).as_posix()})' for p in source if len(Path(p).relative_to(Path(scope)).parts)<=3][:35]
            text += ['', '## 保存與重做範圍','',
                     f'[逐輪完整判讀]({card})。本次各項實測與GitHub取回檢查另外記錄；資料可重建、結果可重算及完整訓練已重跑分開判讀。',
                     'D槽原始、正式與論文內容保護；只有完整H副本、GitHub恢復、相依與精確清單核對後才可清理大型副本。','']
            (folder/'MANIFEST.md').write_text('\n'.join(text),encoding='utf-8');created.append(scope+'/MANIFEST.md')
    write_json(root/'docs/reproducibility/navigation_completion_20261016.json',{
        'date':'2026-10-16','kind':'post_hoc_navigation_only','original_scientific_receipts_modified':False,'created':created})
    print(json.dumps({'created_navigation_files':len(created),'files':created},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True)
    a=p.parse_args();complete(a.root,a.catalog)
