"""Reproduce legacy Raw-only ROI selection; freeze coordinates before candidates."""
import ast,json,pathlib
import cv2,numpy as np,pandas as pd
from audit_real_panel import E,protect,fingerprints,image_read
R68=E.parent/'R68_R61_RealFOVFeatureGeneralization'
def main():
    config=json.loads(protect(R68/'config/sequences.json').read_text(encoding='utf-8-sig'))
    source=protect(R68/'scripts/run_r68.py').read_text(encoding='utf-8-sig');tree=ast.parse(source)
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'edge_image','select_tiles'}]
    ns={'cv2':cv2,'np':np};exec(compile(ast.Module(body=funcs,type_ignores=[]),'r68_read_only_roi_functions','exec'),ns)
    table=pd.read_csv(protect(R68/'results/tables/tile_motion_measurements.csv'))
    root=E.parent/'R78_R75v2_BroadRealMicroscopeGeneralization/inputs/locked_raw';records=[]
    for name,c in config['sequences'].items():
        path=protect(root/name/'frame_0000.bmp');raw=image_read(path);selected=ns['select_tiles'](raw,config['tile_grid'])
        old=set(table.loc[table.sequence.eq(name),'tile_id']);assert {r['tile_id'] for r in selected}==old,(name,'ROI identity changed')
        for r in selected:
            assert r['x0']>=0 and r['y0']>=0 and r['x0']+r['width']<=raw.shape[1] and r['y0']+r['height']<=raw.shape[0]
            records.append({'sequence':name,'first_raw':str(path),'first_raw_sha256':fingerprints[str(path)],**r,'source':'R68 Raw-only first-frame selection','semantic_annotation':'legacy_content_score_only; corners/gaps/defects require Raw-only semantic annotation before a corresponding specialized claim'})
    payload={'status':'frozen_from_Raw_before_R123_candidate_outputs','count':len(records),'per_sequence':24,'scope':'full-field motion and preservation ROIs; no new independent detail truth','old_R68_gates_adopted':False,'rois':records}
    (E/'config/frozen_real_rois.json').write_text(json.dumps(payload,indent=2),encoding='utf-8');(E/'results/protected_roi_inputs.json').write_text(json.dumps(fingerprints,indent=2),encoding='utf-8')
    print(json.dumps({'roi_count':len(records),'sequences':len(config['sequences']),'all_match_legacy_Raw_selected_ids':True}))
if __name__=='__main__':main()
