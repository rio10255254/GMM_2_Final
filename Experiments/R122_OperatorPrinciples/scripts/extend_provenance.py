"""Additional read-only checks; preserves the primary audit outputs."""
import ast, csv, json, os, pathlib, re
import numpy as np
import audit_provenance as a
E,V,D=a.E,a.V,a.D
def main():
    m=a.read(D/'manifest.json');s=a.read(D/'splits/grouped_seed1337_val120/split_meta.json');idx=np.load(a.protect(D/'splits/grouped_seed1337_val120/train_idx.npy'))
    bypath={p['package_src']:p for p in m['pairs']};train=[bypath[s['source_paths_sorted'][i]] for i in idx];sem=[p for p in train if p['role']=='sem_truth_anchor']
    checks=list(csv.DictReader((E/'results/v42_sem_anchor_lineage.csv').open(encoding='utf-8')))
    diff=[r for r in checks if r['same_hash']=='False'];declared={'lbl/'+x for x in m['v42_softlabel_overlay_label_files']}
    assert len(diff)==12 and all(r['package_path'] in declared for r in diff)
    assert all(r['origin_exists']=='True' for r in checks)
    # Compare current center-nine answer values, keeping its corrected mapping explicit.
    cdpath=a.protect(a.ROOT/'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/cd/tables/center9_cd_per_pillar.csv')
    cd=list(csv.DictReader(cdpath.open(encoding='utf-8-sig')));matches=[]
    for r in cd:
        value=float(r['sem_radius_nm']);matched=[p for p in sem if abs(p['target_radius_nm']-value)<1e-5]
        matches.append({'sem_index':r['sem_index'],'current_radius_nm':value,'training_rows_with_same_radius':len(matched),'source_ids':';'.join(map(str,sorted(set(p.get('sem_reference_id',-1) for p in matched))))})
    a.table('v42_current_sem_answer_matches.csv',matches)
    # Execute only the original pure path/pair constructors, never the training module.
    source=a.protect(V/'train_v42.py').read_text(encoding='utf-8-sig');tree=ast.parse(source)
    wanted={'collect_image_paths','SequencePairGrayFolder','MotionPairGrayFolder'}
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in wanted]
    ns={'os':os,'re':re,'Path':pathlib.Path,'np':np,'Dataset':object,'IMAGE_EXTENSIONS':('.png','.jpg','.jpeg','.bmp','.tif','.tiff')}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(V/'train_v42.py'),'exec'),ns)
    constants={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in {'V42_MOTION_INCLUDE_SUBDIRS','V42_SEQ_VAL_INCLUDE_SUBDIRS'}:constants[target.id]=ast.literal_eval(node.value)
    seq=ns['SequencePairGrayFolder'](str(D/'src'),str(D/'lbl'),include_subdirs=constants['V42_MOTION_INCLUDE_SUBDIRS']).pairs[:2400]
    motion=ns['MotionPairGrayFolder'](str(D/'src'),str(D/'lbl'),str(D/'geom'),include_subdirs=constants['V42_MOTION_INCLUDE_SUBDIRS']).pairs[:3600]
    val=ns['SequencePairGrayFolder'](str(D/'src'),str(D/'lbl'),include_subdirs=constants['V42_SEQ_VAL_INCLUDE_SUBDIRS'],random_crop=False).pairs[:1000]
    seqs,motions=set(seq),set(motion);rows=[]
    for x,y in val:
        rows.append({'first':str(pathlib.Path(x).relative_to(D)),'second':str(pathlib.Path(y).relative_to(D)),'also_sequence_training':(x,y) in seqs,'also_motion_training':(x,y) in motions})
    a.table('v42_auxiliary_validation_overlap.csv',rows)
    summary={'sem_payload_differences':{'all_inputs_match_original':all(r['same_hash']=='True' for r in checks if r['package_path'].startswith('src/')),'label_hash_differences':len(diff),'all_differences_are_declared_softlabel_overlay':True,'unchanged_labels':sum(r['same_hash']=='True' for r in checks if r['package_path'].startswith('lbl/')),'overlay_recipe_reexecuted':False},'current_sem_answer_matches':matches,'auxiliary_loaders':{'sequence_training_pairs':len(seq),'motion_training_pairs':len(motion),'sequence_validation_pairs':len(val),'validation_pairs_also_sequence_training':sum(r['also_sequence_training'] for r in rows),'validation_pairs_also_motion_training':sum(r['also_motion_training'] for r in rows),'scope':'Exact pair identity from current original constructor and final launcher constants; random vs center crop differs. Counts alone are not per-batch access logs.'}}
    (E/'results/v42_provenance_extension.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(E/'results/protected_extension.json').write_text(json.dumps(a.fingerprints,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
