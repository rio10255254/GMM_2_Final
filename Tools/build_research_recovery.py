"""Select recovery artifacts from an inventory using the separately authored round reviews.

This records selection decisions and writes navigation only. It does not delete,
move, train, overwrite scientific results, or publish anything.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
from urllib.parse import unquote
import zipfile

from research_recovery import digest, experiment_roots, external_output, safe_relative, write_json

IMAGE_LINK = re.compile(r'!?\[[^\]]*\]\((?:<([^>]+)>|([^\)]+))\)')
TEMPORARY = {'tmp', '.tmp', '_tmp', 'temp', '_build153', 'validations',
             'tmp_render_impact_abstract', '_paper_editing',
             '.codex', '.agents', '.claude', '.history',
             'research_round_library_20260926_aborted_oversized'}
SCIENTIFIC_ARRAY_KEYS = ('point', 'center', 'radi', 'diameter', 'pi_', 'position',
                         'boundary', 'contour', 'mask', 'kernel', 'psf', 'scale', 'direction')


def temporary(path: str) -> bool:
    return any(part.lower() in TEMPORARY or part.lower().startswith('_tmp')
               for part in PurePosixPath(path).parts)


def metadata_keep(path: str) -> bool:
    low = path.lower()
    if temporary(path) or '/training_data/' in low or low.startswith('training_data/'):
        return '/reports/' in low or any(x in PurePosixPath(low).name for x in ['manifest', 'recipe'])
    # Reconstruction receipts preserve the source/model/output identity even
    # when the reproducible image payload itself is not selected.
    if low.startswith('deliverables/'):
        return '/data/' not in low and '/source_data/' not in low
    return True


def array_keep(root: Path, path: str, size: int) -> tuple[bool, str]:
    low = path.lower()
    if temporary(path) or '/data/' in low or '/training_data/' in low or low.startswith('training_data/'):
        return False, '由生成配方重建的訓練陣列；必要凍結來源另作附件'
    if any(x in low for x in ['/internal_maps/', '/feature_maps/', '/reconstruction/',
                               '/reconstructions/', '/raw/', '/predictions/']):
        if not any(x in PurePosixPath(low).name for x in ['point', 'contour', 'mask', 'center']):
            return False, '可由固定模型重建的逐張影像或內部特徵'
    name = PurePosixPath(low).name
    if any(x in name for x in ['point', 'center', 'contour', 'boundary', 'mask', 'psf',
                               'sem_', 'reaggregation', 'fixed_region']) or '/calibration/' in low:
        return True, '保存輪廓／圓心／參照或已固定控制，供重新計算'
    if low.endswith('.mat') and size < 20 * 1024**2:
        return True, '光學／MATLAB數值來源，與來源身分一起保存'
    if low.endswith('.npz') and size < 30 * 1024**2:
        try:
            with zipfile.ZipFile(root / path) as z:
                keys = [PurePosixPath(i.filename).stem.lower() for i in z.infolist()]
            geometry = any(any(word in key for word in ['point','center','diameter','pi_position','radial']) for key in keys)
            image_payload = any(key in {'image','output','restored','prediction','values','source','target'} for key in keys)
            if geometry or (not image_payload and any(any(word in key for word in SCIENTIFIC_ARRAY_KEYS) for key in keys)):
                return True, '保留已保存的幾何／參照陣列，避免只留四捨五入摘要'
        except (OSError, zipfile.BadZipFile):
            return False, '陣列未通過格式檢查，保留原件待核對'
    return False, '大型中間陣列；完整備份保留，未列為可刪除'


def build(root: Path, catalog: Path, output: Path, write_docs: bool):
    root = root.resolve(strict=True)
    output = external_output(root, output)
    output.mkdir(parents=True, exist_ok=True)
    reviews_path = root / 'docs/reproducibility/review_notes.json'
    reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
    db = sqlite3.connect(catalog)
    scopes = experiment_roots(root)
    missing = []
    for scope in scopes:
        group = 'lab' if scope.startswith('Thesis_') else 'legacy' if scope.startswith('Traing_') else 'main'
        if PurePosixPath(scope).name not in reviews[group]:
            missing.append(scope)
    if missing:
        raise ValueError(f'Missing human experiment interpretation: {missing}')
    selected = {}
    payload = {}
    exclusions = Counter()
    broken_images = []
    documents = []

    def choose(path, size, role, reason, force_payload=False):
        row = {'path': path, 'bytes': size, 'role': role, 'reason': reason}
        if force_payload or size > 8 * 1024**2:
            selected.pop(path, None)
            payload[path] = row
        else:
            if path not in payload:
                selected[path] = row

    # The inventory narrows the physical search. Interpretation is supplied by
    # review_notes.json, not inferred from file or folder names.
    for path, size, scope, role in db.execute(
            "SELECT path,bytes,scope,role FROM files WHERE role IN "
            "('code_and_settings','document_or_log','results_and_provenance','numeric_array_candidate')"):
        if temporary(path):
            exclusions['temporary_and_rebuild_validation_runs'] += 1
            continue
        if role == 'code_and_settings':
            if '/source_data/' in path or '/data/' in path and not path.endswith(('.py', '.m')):
                exclusions['generated_data_settings'] += 1
                continue
            choose(path, size, role, '保存實際程式與設定，包括資料生成、訓練、推論與量測')
        elif role == 'document_or_log':
            if PurePosixPath(path).name.lower().endswith(('_pid.txt', '_running.txt')):
                continue
            choose(path, size, role, '保存研究動機、方法、完整判斷、失敗與恢復脈絡')
            if path.lower().endswith(('.md', '.html')):
                documents.append(path)
        elif role == 'results_and_provenance' and metadata_keep(path):
            top_level = len(PurePosixPath(path).parts) == 1
            governance = path.startswith('docs/operations/') and path.lower().endswith('.json') and size <= 2*1024**2
            small_settings = size <= 200*1024 and any(x in path.lower() for x in ['/config/', '/configs/', '/calibration/', '/evaluation/'])
            canonical_summary = size <= 2*1024**2 and ('/reports/data/' in path or '/reports/FINAL_BENCHMARK_THESIS_HANDOFF/data/' in path)
            choose(path, size, role, '保存逐筆結果、排除原因、分組、訓練曲線與來源核對',
                   force_payload=not (top_level or governance or small_settings or canonical_summary))
        elif role == 'numeric_array_candidate':
            keep, reason = array_keep(root, path, size)
            if keep:
                portable_small = '/verification/' in path and size < 2*1024**2
                choose(path, size, role, reason, force_payload=not portable_small)
            else:
                exclusions[reason] += 1

    # Keep the image arguments made in existing reports, including adverse
    # examples. Do not substitute only the nicest output from a later run.
    for rel in documents:
        document = root / rel
        if not document.exists():
            continue
        text = document.read_text(encoding='utf-8-sig', errors='replace')
        for match in IMAGE_LINK.finditer(text):
            raw = (match.group(1) or match.group(2) or '').strip()
            raw = unquote(raw.split(' "')[0].split('#')[0])
            if raw.lower().startswith(('http:', 'https:', 'mailto:', 'codex:', 'data:')):
                continue
            if PurePosixPath(raw.replace('\\', '/')).suffix.lower() not in {'.png', '.svg', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.pdf'}:
                continue
            candidate = Path(os.path.normpath(str(document.parent / raw)))
            try:
                image_rel = candidate.relative_to(root).as_posix()
            except ValueError:
                broken_images.append({'document': rel, 'reference': raw, 'reason': 'outside_project'})
                continue
            if candidate.is_file():
                choose(image_rel, candidate.stat().st_size, 'report_selected_image',
                       '正式報告已引用的比較／控制／失敗圖；與原數值及說明一起保存')
            else:
                broken_images.append({'document': rel, 'reference': raw, 'reason': 'missing'})

    # A report can discuss images without embedding them. Add a small diverse
    # set of comparison, adverse-case and data-design views for each round.
    images_by_scope = defaultdict(list)
    for path, size, scope in db.execute("SELECT path,bytes,scope FROM files WHERE role='image_candidate'"):
        if scope not in scopes or temporary(path) or not path.lower().endswith(('.png', '.svg', '.jpg', '.jpeg')):
            continue
        low = path.lower()
        if any(x in low for x in ['/figures/', '/visuals/', '/dataset_audit/', '/preview/']):
            score = sum(5 if word in low else 0 for word in ['worst', 'fail', 'adverse', 'dark', 'hole'])
            score += sum(3 if word in low else 0 for word in ['compar', 'overlay', 'contact', 'summary', 'overview', 'control'])
            score += 1 if low.endswith('.png') else 0
            images_by_scope[scope].append((score, path, size))
    for scope, rows in images_by_scope.items():
        seen_stems = set()
        added = 0
        for score, path, size in sorted(rows, key=lambda x: (-x[0], x[1])):
            stem = str(PurePosixPath(path).with_suffix(''))
            if stem in seen_stems:
                continue
            seen_stems.add(stem)
            if added >= 8:
                break
            choose(path, size, 'round_comparison_image',
                   '依本輪人工判讀保留資料設計、共同比較與不利案例；完整數值不按圖篩選')
            added += 1

    # Freeze fixed models and initial/teacher references. Per-epoch trajectories
    # remain in the full archive; keep their numeric training history above.
    model_candidates = defaultdict(list)
    for path, size, scope in db.execute("SELECT path,bytes,scope FROM files WHERE role='model_candidate'"):
        if temporary(path):
            continue
        low = path.lower()
        name = PurePosixPath(low).name
        if any(word in name for word in ['best', 'latest', 'selected', 'initial', 'derived', 'complete']):
            choose(path, size, 'fixed_model', '保存當時被採用、比較、初始化或最後完成的精確模型', force_payload=True)
        elif scope in scopes:
            model_candidates[(scope, str(PurePosixPath(path).parent))].append((path, size))
    for (scope, parent), rows in model_candidates.items():
        path, size = sorted(rows, key=lambda x: x[0])[-1]
        choose(path, size, 'endpoint_model', '保存此獨立實驗組實際存在的最後模型；不等於採用', force_payload=True)

    # Sources necessary for the two already designed standalone regenerators.
    for folder in ['Deliverables/Data_Regenerators/R61_TrainingData_Regenerator_20261004',
                   'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004']:
        package = root / folder
        for path in package.rglob('*'):
            if not path.is_file() or any(part in {'outputs', '__pycache__', '.venv'} for part in path.relative_to(package).parts):
                continue
            rel = path.relative_to(root).as_posix()
            if folder.endswith('ImageFiles_20261004') and rel.startswith(folder+'/data/'):
                continue
            if path.suffix.lower() in {'.py', '.md', '.json', '.jsonl', '.txt'} and '/source_data/' not in rel:
                choose(rel, path.stat().st_size, 'verified_regenerator_source', '獨立資料重建包的程式、固定配方與核對依據')
            else:
                choose(rel, path.stat().st_size, 'minimum_frozen_source', '無法僅靠新生成推算取代的必要來源／PSF／模型', force_payload=True)

    # Files created during curation are newer than the metadata inventory.
    for folder in [root/'docs/reproducibility', root/'docs/history', root/'Shared_Sources']:
        for path in folder.rglob('*'):
            if path.is_file() and 'raw' not in path.relative_to(folder).parts and path.suffix != '.zip':
                choose(path.relative_to(root).as_posix(), path.stat().st_size, 'curated_recovery_navigation', '逐輪人工判讀與重做範圍')
    for name in ['research_recovery.py','build_research_recovery.py', 'restore_pi_acquisition.py',
                 'recover_pi_raw_sources.py', 'run_recovery_isolated.py', 'replay_thesis_results.py',
                 'download_research_assets.py', 'research_asset_bundle.py', 'complete_recovery_navigation.py']:
        p = root/'Tools'/name
        choose(p.relative_to(root).as_posix(),p.stat().st_size,'recovery_tool','收集、核對與恢復工具；沒有刪除功能')
    for name in ['publish_research_assets.py', 'restore_research_aliases.py']:
        p = root/'Tools'/name
        choose(p.relative_to(root).as_posix(),p.stat().st_size,'recovery_tool','驗證後保存附件，恢復專案內共用來源；保留原件')
    for name in ['test_research_recovery.py', 'test_restore_pi_acquisition.py', 'test_research_asset_bundle.py', 'test_restore_research_aliases.py']:
        p=root/'Tools/tests'/name
        choose(p.relative_to(root).as_posix(),p.stat().st_size,'recovery_tool_test','恢復越界、覆寫與變更偵測的實測')
    for scope in scopes:
        for name in ['README.md', 'MANIFEST.md']:
            p=root/scope/name
            if p.is_file():
                choose(p.relative_to(root).as_posix(),p.stat().st_size,'experiment_navigation','本輪實際方法、來源與事後補建導引的區別')
    for name in ['.gitignore', '.gitattributes', 'PROJECT_STATE.md', 'ESTIMATOR_POLICY.json',
                 'PROJECT_ARCHITECTURE.md', 'Experiments/INDEX.md']:
        p=root/name
        if p.is_file():choose(name,p.stat().st_size,'current_project_governance','目前研究身分、最新入口及保存規則')

    cards=[]
    for scope in scopes:
        name=PurePosixPath(scope).name
        group='lab' if scope.startswith('Thesis_') else 'legacy' if scope.startswith('Traing_') else 'main'
        note=reviews[group][name]
        source_contract=note[2] if len(note)>2 else '保留本輪原資料生成、來源清單、實際起始模型、實體參照與完整結果；不以主專案同名輪次代替。'
        image_contract=note[3] if len(note)>3 else '共同原圖／答案／重建、實體失敗與各版差異；依正式報告選圖。'
        files=[r for r in list(selected.values())+list(payload.values()) if r['path'].startswith(scope+'/')]
        docs=[r['path'] for r in files if r['path'].lower().endswith('.md')]
        authoritative=[p for p in docs if '/reports/' in p or '/selected/reports/' in p]
        if not authoritative:authoritative=docs
        cards.append({'id':group+'/'+name,'scope':scope,'question':note[0], 'interpretation':note[1],
                      'necessary_sources':source_contract,'image_decision':image_contract,
                      'authoritative_documents':sorted(authoritative),
                      'selected_files':len(files),'selected_bytes':sum(r['bytes'] for r in files),
                      'verification':{'file_export':'pending','full_historical_training_repeated':False,
                                      'portable_execution':'not_yet_verified'},
                      'cleanup_allowed':False})
    selection={'schema':1,'reviewed':True,'review_document':str(reviews_path.relative_to(root)),
               'files':sorted(selected.values(),key=lambda x:x['path'])}
    asset_selection={'schema':1,'reviewed':True,'files':sorted(payload.values(),key=lambda x:x['path'])}
    write_json(output/'repository_selection.json',selection)
    write_json(output/'attachment_selection.json',asset_selection)
    write_json(output/'broken_historical_image_links.json',broken_images)
    write_json(output/'round_cards.json',cards)
    summary={'reviewed_rounds':len(cards),'repository_files':len(selected),
             'repository_bytes':sum(r['bytes'] for r in selected.values()),
             'attachment_files':len(payload),'attachment_bytes':sum(r['bytes'] for r in payload.values()),
             'broken_historical_image_links':len(broken_images),'excluded':dict(exclusions)}
    write_json(output/'selection_summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if write_docs:
        docroot=root/'docs/reproducibility'
        write_json(docroot/'experiment_index.json',cards)
        lines=['# 各輪研究與重做入口','',
               '這裡按實驗逐輪說明研究問題、實際結果、必要來源及選圖理由。正式結論仍以各輪原始報告為準。',
               '', '「已整理」不等於已重新訓練；各輪驗證範圍與缺件另列，原始成功、失敗與中止狀態全部保留。','',
               '| 實驗 | 研究問題 | 判讀與限制 |','|---|---|---|']
        for card in cards:
            filename=card['id'].replace('/','__')+'.md'
            lines.append(f"| [{card['id']}](experiments/{filename}) | {card['question']} | {card['interpretation']} |")
            body=[f"# {card['id']} 研究與重做紀錄",'',card['question'],'',card['interpretation'],'',
                  '## 必要來源','',card['necessary_sources'],'','## 影像保存理由','',card['image_decision'],'',
                  '## 原始方法與結果','',
                  '下列是原始報告與歷史版本；較晚的收尾、因果審查與來源審查優先於早期進度文字。','']
            for rel in card['authoritative_documents']:
                label=PurePosixPath(rel).name
                body.append(f'- [{label}](../../../{rel})')
            body += ['', '## 重做與驗證範圍','',
                     '程式、設定、完整表格與選定影像依保存清單收錄；大型必要來源和固定模型由附件恢復。',
                     '本次沒有重跑這一輪全部歷史訓練。可攜執行、完整數值重算與來源逐份核對的實測範圍，請看總入口的驗證紀錄。',
                     '任何仍須讀取僅存在D／H原工作區的檔案，都不能列為僅靠GitHub已完整重現。','']
            p=docroot/'experiments'/filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\n'.join(body),encoding='utf-8')
        (docroot/'EXPERIMENTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    db.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--catalog',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--write-docs',action='store_true')
    a=parser.parse_args();build(a.root,a.catalog,a.output,a.write_docs)


if __name__=='__main__':main()
