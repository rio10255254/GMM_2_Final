"""Frozen R109/R119 path comparison; reproduces each canonical inference route."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,importlib.util
import cv2,numpy as np,torch
import torch.nn.functional as F
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];R109=ROOT.parent/'R109_StagedMidpointWidthScratch'
sys.path.insert(0,str(ROOT))
from inference.run import load,read
from model.network import continuous_width
from model.ops import warp_local
METHODS=['Raw','R109_full','R109_no_position','R109_position_only','R119_full','R119_no_position','R119_position_only','R119_no_detail','R119_width_only']

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def save(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)

def prepare():
    previous=ROOT.parent/'R121_BoundaryAnchorFactorial/reports/protected_inputs.json'
    snapshot=json.loads(previous.read_text());assert all(sha(p)==h for p,h in snapshot.items())
    paths=[R109/'weights/selected/R109.pth',R109/'model/r109_model.py',R109/'inference/run_folder.py',R109/'config/experiment.json',R109/'validation/reconstruct_locked_suites.py',R109/'results/posttraining/E048/state.json',
           ROOT.parent/'R121_BoundaryAnchorFactorial/results/pitch_matched_reference.mat']
    paths.extend((R109/'results/posttraining/E048/SEM').glob('*.bmp'))
    for p in paths:snapshot[str(p)]=sha(p)
    assert sha(R109/'weights/selected/R109.pth')=='77ff8611e764e1350d60592f5d8a25d6786db17897eadce189185cdc4dbc87fc'
    save('protected_inputs_v2.json',snapshot)
    save('protocol_v2.json',{'created_at_utc':datetime.now(timezone.utc).isoformat(),'question':'Does the R109/R119 difference persist across three matched boundary readouts, and which frozen path contributes?',
        'population':'All 36 matched pillars, all existing exposures 13-24; one sample. No training or confirmation evaluation.',
        'methods':METHODS,'references':['historical','global_pitch_matched'],
        'models':{'R109':'selected E48, archived-suite reflect-halo core512/halo192, from validation/reconstruct_locked_suites.py','R119':'B E42, canonical core512/minimum halo224'},
        'interventions':'Recompute with the exact same predicted fields, change only the indicated factor. R109 has no additive-detail branch; its support/blending remains in every R109 intervention. R119 no-detail retains position and width.',
        'readouts':{'ACM':'Unchanged extraction and symmetric contour distance. Report legacy per-method translation for historical parity AND common Raw-derived integer translation for the three-readout comparison.',
                    'half_contrast':'Unique half-contrast crossing along 720 SEM-normal profiles, +/-12px at 1/8px; fixed Raw plateau levels primary, own-method levels as sensitivity.',
                    'steepest_edge':'Maximum positive derivative of Gaussian-smoothed normal profile; sigma 0.75px primary, 1.25px sensitivity; parabolic refinement. Reject boundary maxima, weak slopes <0.01 normalized intensity/px, and competing peaks >=80% of largest separated by >=1px.'},
        'alignment':'Within every pillar/exposure/reference, all three primary readouts use the SAME integer translation determined from Raw-mask versus reference centroids. No per-model rescaling or optical-result fitting.',
        'reference_profile_calibration':'Refine sampling coordinates using only the mask-derived smooth SEM reference, then subtract readout-specific digital-reference offsets. Calibration validates numerics, not physical equivalence of SEM and optical edges.',
        'validity':'Report per-method failures. Main Raw/R109-full/R119-full comparison uses common valid profiles within each readout. Each path comparison separately intersects its full/path/reference validity; no hidden zero filling.',
        'interpretation':'Agreement across readouts supports an output-boundary difference. Rank reversals or insufficient peak validity limit interpretation. Within-model interventions are fixed-weight diagnostics, not matched retraining or proof of unique training cause.',
        'next_step_rule':'Only select a path-specific follow-up if harmful contribution is consistent across readouts and exposures. If ranking is readout dependent, prioritize reference/readout definition; no new training in this task.',
        'budget_gib':2})

def r109_model():
    spec=importlib.util.spec_from_file_location('r109_frozen_diagnostic_model',R109/'model/r109_model.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    saved=torch.load(R109/'weights/selected/R109.pth',map_location='cpu',weights_only=True)
    assert saved['epoch']==48 and saved['scratch']
    model=module.build_model();model.load_state_dict(saved['model'],strict=True)
    return model.cuda().eval().requires_grad_(False)

@torch.inference_mode()
def r109_paths(model,x):
    h,w=x.shape[-2:];halo=192;core=512;padded=F.pad(x,(halo,)*4,mode='reflect')
    outputs={k:torch.empty_like(x) for k in METHODS if k.startswith('R109')}
    max_replay=0.
    for y in range(0,h,core):
        for z in range(0,w,core):
            ch,cw=min(core,h-y),min(core,w-z);tile=padded[...,y:y+ch+2*halo,z:z+cw+2*halo]
            th,tw=tile.shape[-2:];ph,pw=(-th)%8,(-tw)%8
            aligned=F.pad(tile,(0,pw,0,ph),mode='reflect') if ph or pw else tile
            raw=aligned.clamp(0,1);d=model._forward_aligned(aligned)
            def render(flow,gain):
                warped=model.warp(raw.float(),flow*d.support)
                hi=F.max_pool2d(warped,21,1,10);lo=-F.max_pool2d(-warped,21,1,10)
                dynamic=(hi-lo).clamp_min(2/255);unit=((warped-lo)/dynamic).clamp(1e-3,1-1e-3)
                proposal=lo+dynamic*torch.sigmoid(gain*(torch.log(unit)-torch.log1p(-unit)))
                return (raw.float()+d.support*(proposal-raw.float())).clamp(0,1)
            full=render(d.flow,d.width_gain)
            max_replay=max(max_replay,float((full-d.output).abs().max()));assert torch.equal(full,d.output)
            values={'R109_full':d.output,'R109_no_position':render(torch.zeros_like(d.flow),d.width_gain),'R109_position_only':render(d.flow,torch.ones_like(d.width_gain))}
            for name,value in values.items():outputs[name][...,y:y+ch,z:z+cw]=value[...,halo:halo+ch,halo:halo+cw]
    return {k:v[0,0].cpu().numpy() for k,v in outputs.items()},max_replay

@torch.inference_mode()
def r119_paths(model,x):
    h,w=x.shape[-2:];halo=model.minimum_halo_px;core=512
    outputs={k:torch.empty_like(x) for k in METHODS if k.startswith('R119')}
    for y in range(0,h,core):
        for z in range(0,w,core):
            y1,z1=min(y+core,h),min(z+core,w);sy,sz=max(0,y-halo),max(0,z-halo);ey,ez=min(h,y1+halo),min(w,z1+halo)
            tile=x[...,sy:ey,sz:ez];d=model.forward_details(tile)
            width=continuous_width(tile,d.width_gain,d.sdf,d.normals,21)
            values={'R119_full':d.output,'R119_no_position':(width+d.detail).clamp(0,1),'R119_position_only':warp_local(tile,d.flow),
                    'R119_no_detail':d.geometry_output.clamp(0,1),'R119_width_only':width.clamp(0,1)}
            for name,value in values.items():outputs[name][...,y:y1,z:z1]=value[...,y-sy:y1-sy,z-sz:z1-sz]
    return {k:v[0,0].cpu().numpy() for k,v in outputs.items()}

def main():
    torch.set_num_threads(4);cv2.setNumThreads(1);prepare();(OUT/'images_v2').mkdir(exist_ok=False)
    m109=r109_model();m119=load(ROOT/'runs/formal_B_s1195001/weights/epoch_042.pth','cuda')
    records=[]
    for e in range(13,25):
        source=ROOT.parent/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{e}.bmp'
        raw=read(source);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
        r109,replay=r109_paths(m109,x);r119=r119_paths(m119,x)
        arrays={'Raw':raw,**{k:np.rint(v*255).clip(0,255).astype(np.uint8) for k,v in {**r109,**r119}.items()}}
        parity={}
        for name,path in [('R109_full',R109/f'results/posttraining/E048/SEM/{e}.bmp'),('R119_full',ROOT/f'results/formal_sem/reconstructions/{e}.bmp')]:
            old=read(path);difference=np.abs(arrays[name].astype(int)-old.astype(int))
            parity[name]={'different_pixels':int(np.count_nonzero(difference)),'max_gray_difference':int(difference.max())}
            assert np.array_equal(arrays[name],old),(name,e,parity[name])
        dest=OUT/'images_v2'/str(e);dest.mkdir()
        for name,image in arrays.items():assert cv2.imwrite(str(dest/f'{name}.png'),image)
        record={'exposure':e,'historical_image_parity':parity,'R109_recomputed_full_float_max_difference':replay,'files':{p.name:sha(p) for p in dest.iterdir()}}
        with (dest/'record.json').open('x') as f:json.dump(record,f,indent=2)
        records.append(record);print(json.dumps({'exposure':e,'parity':parity}),flush=True)
    snapshot=json.loads((OUT/'protected_inputs_v2.json').read_text());assert all(sha(p)==h for p,h in snapshot.items())
    save('render_record_v2.json',{'images_v2':108,'records':records,'protected_inputs_unchanged':len(snapshot),'source_sha256':sha(__file__)})

if __name__=='__main__':main()
