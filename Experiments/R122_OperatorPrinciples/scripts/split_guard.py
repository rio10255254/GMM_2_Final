"""Fail closed on missing ancestry or any train/development/evaluation source reuse.

This checks declared lineage, not historical truthfulness or scientific fidelity.
No stored expectation is rewritten by this program.
"""
import argparse,csv,json,pathlib
def audit(records):
    required={'item_id','split','sample_id','acquisition_id','ancestor_ids'};errors=[];owners={};seen=set()
    for r in records:
        if not required<=r.keys() or not all(r.get(k) for k in required):
            errors.append({'type':'missing_lineage','item':r.get('item_id')});continue
        if r['split'] not in {'train','development','evaluation'}:
            errors.append({'type':'unknown_split','item':r['item_id']});continue
        if r['item_id'] in seen:errors.append({'type':'duplicate_id','item':r['item_id']})
        seen.add(r['item_id'])
        if not isinstance(r['ancestor_ids'],list):
            errors.append({'type':'invalid_ancestry','item':r['item_id']});continue
        tokens=['sample:'+r['sample_id'],'acquisition:'+r['acquisition_id']]+['ancestor:'+v for v in r['ancestor_ids']]
        for token in tokens:owners.setdefault(token,set()).add(r['split'])
    for token,splits in owners.items():
        if len(splits)>1:errors.append({'type':'shared_origin','origin':token,'splits':sorted(splits)})
    return {'lineage_disjoint':not errors,'records':len(records),'errors':errors,'limitation':'Checks supplied source history only. Does not certify semantic fidelity, honest metadata, or unseen custody.'}
def self_test():
    E=pathlib.Path(__file__).resolve().parents[1]
    clean=[{'item_id':s,'split':s,'sample_id':'object_'+s,'acquisition_id':'session_'+s,'ancestor_ids':['latent_'+s]} for s in ['train','development','evaluation']]
    assert audit(clean)['lineage_disjoint']
    missing=[dict(r) for r in clean];del missing[1]['ancestor_ids'];assert not audit(missing)['lineage_disjoint']
    shared=[dict(r) for r in clean];shared[2]['ancestor_ids']=clean[0]['ancestor_ids'];assert not audit(shared)['lineage_disjoint']
    same_sample=[dict(r) for r in clean];same_sample[2]['sample_id']=clean[0]['sample_id'];assert not audit(same_sample)['lineage_disjoint']
    # Real V42 frame ancestry is independently recorded by the audit; demonstrate rejection.
    rows=list(csv.DictReader((E/'results/v42_shared_frame_ancestry.csv').open(encoding='utf-8')));actual=[]
    for i,r in enumerate(rows):
        ancestor='/'.join(r[k] for k in ['dataset','sequence','frame'])
        for split in ['train','development']:
            actual.append({'item_id':f'{split}_{i}','split':split,'sample_id':r['dataset'],'acquisition_id':r['dataset']+'/'+r['sequence'],'ancestor_ids':[ancestor]})
    result=audit(actual);assert not result['lineage_disjoint'];assert sum(e.get('origin','').startswith('ancestor:') for e in result['errors'])==301
    (E/'results/split_guard_rejects_v42.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'clean_fixture_pass':True,'missing_lineage_rejected':True,'cross_role_ancestor_rejected':True,'same_sample_rejected':True,'actual_v42_shared_frames_rejected':301}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest');p.add_argument('--self-test',action='store_true');args=p.parse_args()
    if args.self_test:self_test()
    elif args.manifest:
        result=audit(json.loads(pathlib.Path(args.manifest).read_text(encoding='utf-8')));print(json.dumps(result,indent=2));raise SystemExit(0 if result['lineage_disjoint'] else 2)
    else:p.error('Provide --manifest or --self-test')
