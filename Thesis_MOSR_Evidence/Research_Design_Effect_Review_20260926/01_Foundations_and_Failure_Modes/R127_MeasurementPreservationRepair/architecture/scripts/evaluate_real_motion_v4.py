"""Complete real readout comparison with explicit local/context/global roles."""
import cv2,time,pandas as pd
from common import *
from motion_reader_v3 import measure

def bidirectional(a,b):
    f=measure(a,b);r=measure(b,a);cycle=float(np.hypot(f['dx']+r['dx'],f['dy']+r['dy'])) if f['accepted'] and r['accepted'] else None
    return dict(forward=f,reverse=r,cycle_error=cycle,valid=bool(cycle is not None and cycle<=.1))

def main():
    for name in ['motion_hierarchy_calibration_v4.json','motion_hierarchy_validation_v4.json']:assert json.loads((ROOT/'results'/name).read_text())['engineering_checks_passed']
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());out=ROOT/'results/real_motion_v4';out.mkdir(exist_ok=False);rows=[];global_rows=[];sources=[];start=time.perf_counter()
    methods=[('Raw',None)]+[(f'{a}_s{s}',R126/'results'/f'real_{a}_s{s}_step0128') for a in ['P','Q'] for s in [1265001,1265002]]
    for item in panel['motion_pairs']:
        images=[];seq=item['sequence'];x0,y0,x1,y1=item['context_xyxy'];lx,ly,ux,uy=item['core_in_context_xyxy']
        for s in item['sources']:
            assert sha(s['path'])==s['sha256'];sources.append(s);images.append(cv2.imread(s['path'],0).astype(float)/255)
        global_m=bidirectional(*images);global_rows.append(dict(sequence=seq,**global_m));raw_context=[a[y0:y1,x0:x1] for a in images]
        for name,folder in methods:
            if folder is None:context=raw_context;legacy=item['raw_edge_phase']
            else:
                context=[]
                for frame in [0,1]:
                    p=folder/'motion'/seq/f'frame{frame}'/'output_float.npz';sources.append(record(p))
                    with np.load(p) as d:context.append(d['output'].astype(float))
                previous=json.loads((folder/'motion_measurements.json').read_text());legacy=next(x for x in previous if x['sequence']==seq)['candidate']
            assert all(min(a.shape)>288 for a in context)
            large=[a[80:-80,80:-80] for a in context];small=[a[ly:uy,lx:ux] for a in context]
            cm=bidirectional(*large);local=bidirectional(*small);reasons=[]
            if not cm['valid']:reasons.append('context_not_uniquely_reversible')
            if not global_m['valid']:reasons.append('full_field_source_not_uniquely_reversible')
            difference=None
            if cm['valid'] and global_m['valid']:
                c,g=cm['forward'],global_m['forward'];difference=float(np.hypot(c['dx']-g['dx'],c['dy']-g['dy']))
                if difference>.5:reasons.append('context_disagrees_with_full_field_source')
            accepted=not reasons
            rows.append(dict(sequence=seq,method=name,local128=local,valid_context=cm,valid_context_shape=list(large[0].shape),global_source_agreement_px=difference,reportable_context_translation=accepted,reported_dx=cm['forward']['dx'] if accepted else None,reported_dy=cm['forward']['dy'] if accepted else None,reasons=reasons,old_phase=legacy,absolute_stage_truth=False))
        print(json.dumps(dict(sequence=seq,completed=len(rows),global_accepted=global_m['valid'],seconds=time.perf_counter()-start)),flush=True)
    save(out/'measurements.json',dict(rows=rows,global_Raw=global_rows,sources=sources,reader_sources={str(p):sha(p) for p in [ROOT/'scripts/motion_reader.py',ROOT/'scripts/motion_reader_v2.py',ROOT/'scripts/motion_reader_v3.py']},protocol=record(ROOT/'config/motion_real_protocol_v3.json')))
    flat=[]
    for r in rows:
        flat.append(dict(sequence=r['sequence'],method=r['method'],accepted=r['reportable_context_translation'],dx=r['reported_dx'],dy=r['reported_dy'],context_vs_global=r['global_source_agreement_px'],local128_valid=r['local128']['valid'],old_phase_dx=r['old_phase']['dx_px'],old_phase_dy=r['old_phase']['dy_px'],old_phase_response=r['old_phase']['response'],reasons=';'.join(r['reasons'])))
    pd.DataFrame(flat).to_csv(out/'summary.csv',index=False)
    summary=dict(total_context_pairs=len(rows),accepted_context_pairs=sum(r['reportable_context_translation'] for r in rows),valid_full_field_Raw=sum(r['valid'] for r in global_rows),local128_valid=sum(r['local128']['valid'] for r in rows),maximum_accepted_context_global_difference=max((r['global_source_agreement_px'] for r in rows if r['reportable_context_translation']),default=None),physical_accuracy_qualified=False,old_readouts_changed=False,context_scope_not_silently_called_local128=True,seconds=time.perf_counter()-start)
    save(out/'verification.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
