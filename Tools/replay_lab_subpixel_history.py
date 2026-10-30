"""Rebuild all 126 historical test inputs and recompute saved table statistics.

The original input generator and original aggregation code run unchanged.
Frozen historical geometry supplies its configuration interface; only physical
source/output paths are relocated. No trained model, raw camera file, saved
result or thesis figure is overwritten. No neural inference/training is run.
"""
import argparse
import ast
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from research_recovery import safe_relative,write_json

BASE='LabSystem_MOSR/Experiments/Subpixel_Translation_Equivariance_20260720'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def replay_tables(root,output):
    source=root/(BASE+'/analyze_subpixel_equivariance.py')
    tree=ast.parse(source.read_text(encoding='utf-8'));namespace={'np':np,'pd':pd,'wilcoxon':wilcoxon}
    constants={'METHOD_LABELS','BOOTSTRAP_SEED','BOOTSTRAP_DRAWS'}
    functions={'bootstrap_ci','holm_adjust'}
    def target(node,name):
        return isinstance(node,ast.Assign) and any(isinstance(value,ast.Name) and value.id==name for value in node.targets)
    selected=[node for node in tree.body if
        (isinstance(node,ast.FunctionDef) and node.name in functions)
        or (isinstance(node,ast.Assign) and any(isinstance(value,ast.Name) and value.id in constants for value in node.targets))]
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),namespace)
    if not constants|functions<=namespace.keys():raise ValueError('The original aggregation definitions differ')
    main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    def section(start,end):
        first=next(index for index,node in enumerate(main.body) if target(node,start))
        last=next(index for index,node in enumerate(main.body) if target(node,end))
        if last<=first:raise ValueError('The historical aggregation section changed')
        return main.body[first:last]
    tables=root/(BASE+'/analysis/tables')
    clusters=pd.read_csv(tables/'cluster_translation_metrics.csv',float_precision='round_trip')
    namespace.update({'cluster_table':clusters,'methods':list(namespace['METHOD_LABELS'])})
    exec(compile(ast.Module(body=section('primary','equivariance_summary'),type_ignores=[]),str(source),'exec'),namespace)
    primary=namespace['primary'];keys={method:set(group.cluster_id) for method,group in primary.groupby('method_key')}
    if len(clusters)!=600 or len(primary)!=500 or len(keys)!=5 or any(len(ids)!=100 for ids in keys.values()) or len(set.intersection(*keys.values()))!=100:
        raise ValueError('The five methods do not cover the exact original 100 paired primary combinations')
    exec(compile(ast.Module(body=section('pair_rows','outputs'),type_ignores=[]),str(source),'exec'),namespace)
    specifications=[('primary_translation_summary_by_method.csv','summary',['method_key']),
        ('primary_translation_summary_by_group.csv','group_summary',['method_key','magnification','morphology']),
        ('primary_translation_summary_by_shift.csv','shift_summary',['method_key','shift_magnitude_px']),
        ('paired_mosr_comparisons.csv','pair_table',['comparator_key'])]
    checks=[];numeric=0;maximum=0.0
    for filename,name,ids in specifications:
        actual=namespace[name].sort_values(ids).reset_index(drop=True)
        expected=pd.read_csv(tables/filename,float_precision='round_trip').sort_values(ids).reset_index(drop=True)
        if list(actual.columns)!=list(expected.columns) or len(actual)!=len(expected):raise ValueError('Original table structure differs: '+filename)
        for column in actual.columns:
            if pd.api.types.is_numeric_dtype(expected[column]):
                a=actual[column].to_numpy(float);b=expected[column].to_numpy(float)
                if not np.allclose(a,b,rtol=1e-12,atol=1e-12,equal_nan=True):raise ValueError('Original numeric table differs: '+filename+'/'+column)
                difference=float(np.nanmax(np.abs(a-b))) if len(a) else 0.0
                numeric+=len(a);maximum=max(maximum,difference)
            elif actual[column].tolist()!=expected[column].tolist():raise ValueError('Original table identity differs: '+filename+'/'+column)
        actual.to_csv(output/filename,index=False,encoding='utf-8-sig')
        checks.append({'table':filename,'rows':len(actual),'all_original_fields_match':True})
    return {'primary_rows':len(primary),'paired_primary_combinations_per_method':100,
            'numeric_fields_checked':numeric,'maximum_absolute_difference':maximum,'tables':checks}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();output=args.output.resolve()
    if output.exists():raise FileExistsError('Use a new owned output directory')
    source_manifest=root/'docs/reproducibility/lab_comparisons/SUBPIXEL_SOURCE_FILES.json'
    manifest=json.loads(source_manifest.read_text(encoding='utf-8'))
    for row in manifest['files']:
        path=root/safe_relative(row['path'])
        if (path.stat().st_size,sha(path))!=(row['bytes'],row['sha256']):raise ValueError('A frozen historical source differs: '+row['path'])
    frozen=json.loads((root/(BASE+'/inputs/input_manifest.json')).read_text(encoding='utf-8'))
    output.mkdir(parents=True);configs=output/'portable_interface_configs';configs.mkdir()
    sources={row['case_id']:root/safe_relative(row['source_project_path']) for row in manifest['case_sources']}
    pillar={};via={}
    for case in frozen['cases']:
        local=sources[case['case_id']];sequence=case['source_sequence'];entry=pillar.setdefault(sequence,{'raw_dir':str(local.parent)})
        if entry['raw_dir']!=str(local.parent):raise ValueError('One historical sequence has conflicting physical sources')
        measurement=case['measurement'];x0,y0,_,_=case['crop_xywh']
        if case['morphology']=='pillar':
            entry.update({key:measurement[key] for key in ['polarity','radius_px','pitch_px','search_radius_px','min_edge_strength']})
            entry['centers']=[[item['feature_id'],item['x']+x0,item['y']+y0] for item in measurement['centers']]
        elif case['morphology']=='via':
            via[sequence]={key:measurement[key] for key in ['polarity','radius_px','pitch_px','search_radius_px']}
            via[sequence]['centers']=[{'sem_cell':item['feature_id'],'x':item['x']+x0,'y':item['y']+y0} for item in measurement['centers']]
    write_json(configs/'pillar.json',{'sequences':pillar});write_json(configs/'via.json',{'sequences':via})
    source=root/(BASE+'/prepare_subpixel_inputs.py')
    spec=importlib.util.spec_from_file_location('original_subpixel_generator',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.PILLAR_CONFIG=configs/'pillar.json';module.VIA_CONFIG=configs/'via.json'
    cv2.setNumThreads(1);module.main(output)
    expected={row['name']:row for row in manifest['expected_input_images']}
    generated=output/'inputs/shifted';actual={path.name for path in generated.iterdir() if path.is_file()}
    if len(expected)!=126 or actual!=set(expected):raise ValueError('The complete historical input file set differs')
    for name,row in expected.items():
        path=generated/name
        if (path.stat().st_size,sha(path))!=(row['bytes'],row['sha256']):raise ValueError('A regenerated original input differs: '+name)
    fresh=json.loads((output/'inputs/input_manifest.json').read_text(encoding='utf-8'))
    fresh_cases={row['case_id']:row for row in fresh['cases']}
    for original in frozen['cases']:
        actual=fresh_cases[original['case_id']]
        if {k:v for k,v in actual.items() if k!='source_path'}!={k:v for k,v in original.items() if k!='source_path'}:
            raise ValueError('Frozen geometry/source metadata differs for '+original['case_id'])
    def input_rows(path):
        with path.open('r',encoding='utf-8-sig',newline='') as stream:
            return [{k:v for k,v in row.items() if k!='source_path'} for row in csv.DictReader(stream)]
    if input_rows(output/'inputs/input_manifest.csv')!=input_rows(root/(BASE+'/inputs/input_manifest.csv')):
        raise ValueError('Original input labels, crop coordinates or imposed shifts differ')
    stats=replay_tables(root,output)
    write_json(output/'LAB_SUBPIXEL_REPLAY_VERIFIED.json',{'status':'PASS_EXACT_126_INPUT_FILES_AND_ORIGINAL_TABLES',
        'regenerated_input_images':126,'source_cases':6,'historical_geometry_interface_rebuilt_from_frozen_case_records':True,
        'distinct_original_full_frames':len({row['source_project_path'] for row in manifest['case_sources']}),
        'reference_crops':6,'mathematically_shifted_inputs':120,'source_bit_depth':8,'derived_input_bit_depth':16,
        'original_generator_and_aggregation_source_modified':False,'scientific_geometry_or_reference_values_modified':False,
        'generated_metadata_physical_paths_relocated':True,'original_input_and_figure_files_modified':False,
        'original_126_input_manifest_rows_match_except_physical_path':True,
        'neural_inference_or_training_repeated':False,**stats})
    print('COMPLETE_LAB_SUBPIXEL_INPUTS_AND_SAVED_TABLES_REPLAY_VERIFIED',126,stats['numeric_fields_checked'],flush=True)


if __name__=='__main__':main()
