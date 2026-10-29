"""Finish the user's TIFF-only selection after the earlier conversion process exits."""
import ast
import json
import pprint
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PACK=ROOT.parents[1]/'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004'

def literal(path,name):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(name)

def main():
    entries=literal(PACK/'data_index.py','ENTRIES')
    for entry in entries:
        for view in entry['images']:
            for key in list(view):
                if '_preview' in key:del view[key]
    (PACK/'data_index.py').write_text('"""Actual TIFF training pairs and fixed split/labels."""\nENTRIES = '+pprint.pformat(entries,width=115,sort_dicts=False)+'\n',encoding='utf-8')
    data_root=(PACK/'data').resolve()
    targets=list(data_root.rglob('*.png'))
    for p in targets:
        resolved=p.resolve()
        assert resolved.is_relative_to(data_root) and resolved.is_file() and not p.is_symlink(),p
        assert p.stem.endswith(('_v0','_v1','_v2','_v3')),p
    for p in targets:p.unlink()
    assert not list(data_root.rglob('*.png')) and not list(data_root.rglob('*.npz'))
    info=literal(PACK/'reference_info.py','REFERENCE')
    info.update(formal_training_image_format='TIFF float32',data_arrays_preserved_in_original_storage_dtype=False,
                original_dataset_storage_dtype='float16',training_float32_values_identical=True,
                clear_images=3072,blur_images=3072,geometry_images=3072,PNG_previews=0)
    (PACK/'reference_info.py').write_text('"""Published R152 identity and exact TIFF image counts."""\nREFERENCE = '+pprint.pformat(info,width=110,sort_dicts=False)+'\n',encoding='utf-8')
    checks=json.loads((OUT/'image_conversion_checks.json').read_text(encoding='utf-8'))
    checks['PNG_previews']=0;checks['only_TIFF_in_training_data']=True
    (OUT/'image_conversion_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print('TIFF ONLY:',len(list(data_root.rglob('*.tif'))),'images; removed',len(targets),'generated PNG previews')

if __name__=='__main__':main()
