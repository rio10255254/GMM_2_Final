"""Read-only extraction of the already locked LSC reader, without script side effects."""
import ast,sys,importlib.util
from pathlib import Path
import numpy as np,pandas as pd
from PIL import Image
import skimage.segmentation.morphsnakes as morphsnakes
from common import *
OUT=ROOT/'results/continuous_lsc'
def reader(plan):
    source=REPO/'Experiments/R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py'
    spec=importlib.util.spec_from_file_location('r129_continuous_lsc_core',source);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    scope=dict(np=np,pd=pd,Path=Path,Image=Image,morphsnakes=morphsnakes,SESSION_TABLE=Path(plan['sessions']['path']))
    sources=[(source.parent/'run_displacement_lsc.py',['session_prediction','load_grayscale','summarize_pairs']),
             (REPO/'Experiments/R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py',['reset_curvature_cycle']),
             (REPO/'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/measure.py',['measure_frame','pair_table'])]
    for path,names in sources:
        nodes=[n for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name in names]
        assert len(nodes)==len(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return module,scope
def atomic(path,value):
    import os,json
    path=Path(path);temp=path.with_suffix('.writing');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)
