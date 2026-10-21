"""Frozen objective and transfer diagnosis. No optimizer, no new training."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import replace,fields
import hashlib,json,sys
import numpy as np,pandas as pd,cv2,torch
from scipy.io import loadmat
from scipy.ndimage import distance_transform_edt,gaussian_filter
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
from inference.run import load,read
from model.network import Details,geometric_normals,continuous_width
from model.ops import warp_local
from training.r119_dataset import R119Scenes,flatten
from training.objectives import objective,location_xy
from torch.utils.data._utils.collate import default_collate

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)

def prepare():
    older=ROOT/'analysis/sem_position_audit_20260906/input_snapshot.json'
    snapshot=json.loads(older.read_text())
    assert all(sha(p)==h for p,h in snapshot.items())
    additional=[ROOT/'config/experiment.json',ROOT/'runs/formal_B_s1195001/weights/epoch_024.pth',
                ROOT/'reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md',ROOT/'analysis/sem_position_audit_20260906/analysis_summary.json']
    snapshot.update({str(p):sha(p) for p in additional})
    save('input_snapshot.json',snapshot)
    save('protocol.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'question':'Why can R119 learn a position path which expands real contours?',
        'checks':['Known-answer concentric expansion fixture: which original objective terms notice it?',
                  'Equivalent-output counterexample: can displacement be compensated by allowed additive detail without changing loss?',
                  'Distance/normal/shift joint-sign invariance: separate convention from actual geometric error.',
                  'E24 and E42: fixed first 96 train and 96 existing development scenes, B policy, same epoch-42 observation realization for both models; full versus position-off with geometry/width/detail held.',
                  'E42 real SEM stack: predicted normals versus SEM outward normals, and output displacement sign along the same fixed contour; no true model update.'],
        'populations':{'train':list(range(96)),'validation':'first 96 manifest entries, IDs recorded in outputs','real_exposures':list(range(13,25))},
        'interpretation_limits':['Sensitivity of frozen outputs is not historical loss-term causation.','Equivalent output does not prove compensation occurred during training.','A fixed-image path intervention is not a retrained ablation.','Existing train/development data and real SEM are not new holdouts.'],
        'no_training':True,'no_confirmation_evaluation':True})

def tensors_to_numbers(terms):return {k:float(v) for k,v in terms.items()}

@torch.inference_mode()
def fixtures(weights):
    y,x=torch.meshgrid(torch.arange(128.),torch.arange(128.),indexing='ij');radius=torch.sqrt((x-63.5)**2+(y-63.5)**2)
    rows=[]
    for polarity in [-1,1]:
        for contrast in [.08,.4]:
            sdf=(28-radius)[None,None].repeat(2,1,1,1)*polarity
            profile=lambda r: .5+polarity*contrast*(torch.sigmoid((r-radius)/1.5)-.5)
            target=profile(28)[None,None].repeat(2,1,1,1)
            nx,ny=geometric_normals(sdf);normal=torch.cat([nx,ny],1)
            boundary=torch.exp(-sdf.abs()/2.5).clamp(1e-6,1-1e-6)
            zero=torch.zeros_like(target)
            d=Details(target,sdf.clamp(-16,16),torch.logit(boundary),normal,zero,torch.cat([zero,zero],1),torch.ones_like(target),target,zero)
            batch={'source':target,'target':target,'sdf':sdf,'fine_reliability':torch.ones_like(target),'identity':torch.zeros(2,dtype=torch.bool),'flat':torch.zeros(2,dtype=torch.bool),'shift_xy':torch.zeros(1,2),'scenes':1}
            baseline,base_terms=objective(None,d,batch,weights)
            expanded=profile(28.4)[None,None].repeat(2,1,1,1)
            _,exp_terms=objective(None,replace(d,output=expanded),batch,weights)
            # Allowed local displacement with an equal-and-opposite detail output.
            shift=torch.full_like(target,.25);flow=normal*shift;anchor=warp_local(target,flow);compensation=target-anchor
            assert compensation.abs().max()<24/255
            alternate=replace(d,shift=shift,flow=flow,geometry_output=anchor,detail=compensation,output=anchor+compensation)
            alt_loss,alt_terms=objective(None,alternate,batch,weights)
            gain=torch.ones_like(target)*1.6
            a=continuous_width(anchor,gain,sdf,normal,21);b=continuous_width(anchor,gain,-sdf,-normal,21)
            wrong=continuous_width(anchor,gain,-sdf,normal,21)
            assert torch.equal(a,b)
            row={'polarity':polarity,'contrast':contrast,'known_outward_expansion_px':.4,
                 'expansion_loss_increases':{k:float(exp_terms[k]-base_terms[k]) for k in base_terms},
                 'compensated_displacement_px':.25,'compensating_detail_max_gray':float(compensation.abs().max()*255),
                 'compensated_output_max_difference':float((alternate.output-target).abs().max()),
                 'compensated_objective_max_term_difference':max(float((alt_terms[k]-base_terms[k]).abs()) for k in base_terms),
                 'joint_sign_change_render_max_difference':float((a-b).abs().max()),'unpaired_sign_change_render_max_gray_difference':float((a-wrong).abs().max()*255)}
            rows.append(row)
    save('known_answer_fixtures.json',rows);print('Known-answer fixtures complete',flush=True)

def crop_details(d,start,end):
    return Details(**{f.name:getattr(d,f.name)[start:end] for f in fields(d)})

@torch.inference_mode()
def common_synthetic(weights):
    rows=[];view_records=[]
    for epoch in [24,42]:
        model=load(ROOT/f'runs/formal_B_s1195001/weights/epoch_{epoch:03d}.pth','cuda')
        for split in ['train','validation']:
            ds=R119Scenes(split,epoch=42,limit=96,candidate='B',data_seed=1196001)
            for start in range(0,len(ds),4):
                items=[ds[i] for i in range(start,min(start+4,len(ds)))];batch=flatten(default_collate(items),'cuda')
                d=model.forward_details(batch['source'])
                no_shift=(continuous_width(batch['source'],d.width_gain,d.sdf,d.normals,model.config['local_range_window'])+d.detail).clamp(0,1)
                for j,item in enumerate(items):
                    a,b=2*j,2*j+2
                    one={k:v[a:b] for k,v in batch.items() if k not in ['shift_xy','scenes']}
                    one['shift_xy']=batch['shift_xy'][j:j+1];one['scenes']=1
                    details=crop_details(d,a,b)
                    loss,terms=objective(model,details,one,weights)
                    other_loss,other_terms=objective(model,replace(details,output=no_shift[a:b]),one,weights)
                    base_mae=float((details.output-one['target']).abs().mean()*255)
                    off_mae=float((no_shift[a:b]-one['target']).abs().mean()*255)
                    rec=ds.records[start+j]
                    row={'epoch':epoch,'split':split,'scene_id':item['scene_index'],'family':item['family'],'role':item['role'],'polarity':rec['polarity'],
                         'input_sha256':hashlib.sha256(one['source'].cpu().numpy().tobytes()).hexdigest(),
                         'full_loss':float(loss),'no_shift_loss':float(other_loss),'loss_change_no_shift_minus_full':float(other_loss-loss),
                         'full_mae_gray':base_mae,'no_shift_mae_gray':off_mae,'mae_change_no_shift_minus_full':off_mae-base_mae}
                    for name in terms:
                        row[name+'_weighted_change']=float((other_terms[name]-terms[name])*weights[name])
                    rows.append(row)
                print(json.dumps({'epoch':epoch,'split':split,'scenes_done':min(start+4,len(ds))}),flush=True)
        del model
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'synthetic_path_effects.csv',index=False,mode='x')
    for _,g in frame.groupby(['split','scene_id']):assert g.input_sha256.nunique()==1
    summary=[]
    for (epoch,split),g in frame.groupby(['epoch','split']):
        edge=g[g.role.isin(['edge','textured_edge'])]
        for scope,f in [('all',g),('edge_and_texture',edge),('dark_edges',edge[edge.polarity==-1]),('bright_edges',edge[edge.polarity==1])]:
            summary.append({'epoch':int(epoch),'split':split,'scope':scope,'scenes':len(f),
                'no_shift_lower_loss':int((f.loss_change_no_shift_minus_full<-1e-8).sum()),
                'no_shift_higher_loss':int((f.loss_change_no_shift_minus_full>1e-8).sum()),
                'no_shift_lower_mae':int((f.mae_change_no_shift_minus_full<-1e-7).sum()),
                'no_shift_higher_mae':int((f.mae_change_no_shift_minus_full>1e-7).sum()),
                'mean_loss_change':float(f.loss_change_no_shift_minus_full.mean()),
                'mean_mae_full':float(f.full_mae_gray.mean()),'mean_mae_no_shift':float(f.no_shift_mae_gray.mean()),
                'mean_weighted_term_changes':{k:float(f[k].mean()) for k in f.columns if k.endswith('_weighted_change')}})
    save('synthetic_summary.json',summary)

@torch.inference_mode()
def real_fields():
    model=load(ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth','cuda')
    saved=loadmat(ROOT/'results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['truth_masks','opt_centers','global_index'])
    normals=[];bands=[]
    for p in range(36):
        truth=saved['truth_masks'][:,:,p].astype(bool)
        sdf=distance_transform_edt(~truth)-distance_transform_edt(truth)
        smooth=gaussian_filter(sdf,1.);gy,gx=np.gradient(smooth);length=np.maximum(np.hypot(gx,gy),1e-8)
        normals.append((gx/length,gy/length));bands.append(np.abs(sdf)<=3)
    records=[]
    for exposure in range(13,25):
        raw=read(ROOT.parent/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{exposure}.bmp')
        x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();h,w=raw.shape;halo=model.minimum_halo_px
        images={k:np.empty((h,w),np.float32) for k in ['flow_x','flow_y','normal_x','normal_y','shift','width_gain']}
        for y in range(0,h,512):
            for z in range(0,w,512):
                y1,z1=min(h,y+512),min(w,z+512);sy,sz=max(0,y-halo),max(0,z-halo);ey,ez=min(h,y1+halo),min(w,z1+halo)
                d=model.forward_details(x[...,sy:ey,sz:ez])
                fields={'flow_x':d.flow[:,0:1],'flow_y':d.flow[:,1:2],'normal_x':d.normals[:,0:1],'normal_y':d.normals[:,1:2],'shift':d.shift,'width_gain':d.width_gain}
                for key,value in fields.items():images[key][y:y1,z:z1]=value[0,0,y-sy:y1-sy,z-sz:z1-sz].cpu().numpy()
        for r in range(6):
            for c in range(6):
                p=int(saved['global_index'][r,c])-1;cx,cy=np.floor(saved['opt_centers'][r*6+c]+.5).astype(int)-1
                patch=lambda key:images[key][cy-52:cy+52,cx-52:cx+52]
                nx,ny=normals[p];band=bands[p]
                alignment=patch('normal_x')*nx+patch('normal_y')*ny
                outward=-(patch('flow_x')*nx+patch('flow_y')*ny)
                records.append({'exposure':exposure,'pillar':p+1,'boundary_pixels':int(band.sum()),
                    'median_predicted_normal_dot_SEM_outward':float(np.median(alignment[band])),
                    'median_implied_outward_output_displacement_px':float(np.median(outward[band])),
                    'outward_displacement_fraction':float(np.mean(outward[band]>0)),
                    'median_signed_shift_parameter_px':float(np.median(patch('shift')[band])),
                    'median_width_gain':float(np.median(patch('width_gain')[band]))})
        print(json.dumps({'real_exposure_fields':exposure}),flush=True)
    f=pd.DataFrame(records);f.to_csv(OUT/'real_position_fields.csv',index=False,mode='x')
    save('real_position_fields_summary.json',{'observations':len(f),
        'median_normal_alignment':float(f.median_predicted_normal_dot_SEM_outward.median()),
        'median_implied_outward_displacement_px':float(f.median_implied_outward_output_displacement_px.median()),
        'observations_with_positive_median_outward_displacement':int((f.median_implied_outward_output_displacement_px>0).sum()),
        'median_outward_fraction':float(f.outward_displacement_fraction.median()),
        'interpretation':'Output-displacement sign is minus the input-sampling flow projected onto SEM outward normals. This is an operator-field diagnostic, not a measured final contour displacement.'})

def main():
    torch.set_num_threads(4);cv2.setNumThreads(1)
    prepare()
    weights=json.loads((ROOT/'config/experiment.json').read_text())['training']['weights']
    fixtures(weights);common_synthetic(weights);real_fields()
    snapshot=json.loads((OUT/'input_snapshot.json').read_text());changed=[p for p,h in snapshot.items() if sha(p)!=h]
    assert not changed,changed
    save('execution_record.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),'protected_files_unchanged':len(snapshot),'optimizer_steps':0,'checkpoint_updates':0,'confirmation_evaluations':0,'source_code_sha256':sha(__file__)})
    print('Diagnosis finished without modifying protected inputs',flush=True)

if __name__=='__main__':main()
