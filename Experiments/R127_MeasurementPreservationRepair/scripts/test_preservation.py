"""Executable conditional preservation and nontrivial restoration checks."""
import cv2,torch
from common import *
sys.path.insert(0,str(R124));sys.path.insert(0,str(R125))
from prototype.network import build_model
from prototype.factorized_observation import from_observation
from model.calibration import observation_from_profile,load_observation
from training.context import window_for,crop_arrays
from preservation import reconstruct

def tensor(a):return torch.from_numpy(np.ascontiguousarray(a)).to('cuda')[:,None]

def main():
    torch.set_num_threads(2);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    cp=R126/'runs/photo_Q_s1265002/step0128.pth';payload=torch.load(cp,map_location='cpu',weights_only=True);m=build_model(payload['model_config'],from_observation(load_observation(R125/'config/real_observation_v2.json'),checkpoint_ops=False)).cuda().eval();loaded=m.load_state_dict({k:v for k,v in payload['model_state'].items() if not k.startswith('observation.')},strict=False);assert not loaded.unexpected_keys
    before={'checkpoint':sha(cp)};param_before={n:hashlib.sha256(p.detach().cpu().numpy().tobytes()).hexdigest() for n,p in m.named_parameters()}
    package=R125/'data/package_v2';manifest=json.loads((package/'manifest.json').read_text());rows=[]
    selected=[e for e in manifest['scenes'] if e['category']=='clean_identity']+[manifest['scenes'][i] for i in [0,1,2,3,5]]
    identity_profile=None
    with torch.inference_mode():
        for e in selected:
            meta=json.loads((package/e['metadata_path']).read_text());assert sha(package/e['arrays_path'])==e['sha256']['arrays'];m.observation=from_observation(observation_from_profile(meta['profile']),checkpoint_ops=False).cuda()
            if meta['identity']:identity_profile=meta['profile']
            window=window_for(m,meta);l,u,x0,x1=window['core']
            with np.load(package/e['arrays_path']) as d:arrays=crop_arrays({k:d[k] for k in ['source','target','noiseless']},window)
            raw=tensor(arrays['source'].astype(np.float32)/255);target=tensor(arrays['target']);base=m(raw);output,status=reconstruct(m,raw,sensor_noise_sigma_gray=meta['noise_sigma_gray'],evidence_kind='known_procedural_operator');c=lambda x:x[...,l:u,x0:x1]
            rows.append(dict(scene=e['scene_id'],category=meta['category'],source_arrays_sha256=e['sha256']['arrays'],sensor_noise_sigma_gray=meta['noise_sigma_gray'],status=status,base_mae=float(c(base-target).abs().mean()*255),guard_mae=float(c(output-target).abs().mean()*255),Raw_mae=float(c(raw-target).abs().mean()*255),bitwise_raw_equal=torch.equal(raw,output),bitwise_base_equal=torch.equal(base,output)))
        # General property on100 new arbitrary inputs, not known scene IDs.
        m.observation=from_observation(observation_from_profile(identity_profile),checkpoint_ops=False).cuda();rng=np.random.default_rng(1275001);general=[]
        for i in range(100):
            raw=tensor(rng.random((1,33+i%5,39+i%7),dtype=np.float32));out,status=reconstruct(m,raw,sensor_noise_sigma_gray=0,evidence_kind='known_procedural_operator');general.append(torch.equal(raw,out) and status['exact_preservation_guaranteed'])
        # Nontrivial noisy identity and noise-free blur are not bypassed.
        noise_profile=json.loads(json.dumps(identity_profile));noise_profile['noise_variance']=(9+1/12)/255**2;m.observation=from_observation(observation_from_profile(noise_profile),checkpoint_ops=False).cuda()
        truth=np.full((1,288,288),.4,np.float32);source=np.rint((truth+rng.normal(0,3/255,truth.shape))*255).astype(np.float32)/255;raw=tensor(source);base=m(raw);output,status=reconstruct(m,raw,sensor_noise_sigma_gray=3,evidence_kind='known_procedural_operator');target=tensor(truth)
        noise=dict(status=status,base_equal=torch.equal(base,output),Raw_mae=float((raw-target)[...,80:208,80:208].abs().mean()*255),output_mae=float((output-target)[...,80:208,80:208].abs().mean()*255))
        e=manifest['scenes'][0];meta=json.loads((package/e['metadata_path']).read_text());profile=json.loads(json.dumps(meta['profile']));profile['noise_variance']=(.25+1/12)/255**2;m.observation=from_observation(observation_from_profile(profile),checkpoint_ops=False).cuda();window=window_for(m,meta);l,u,x0,x1=window['core']
        with np.load(package/e['arrays_path']) as d:arrays=crop_arrays({k:d[k] for k in ['noiseless','target']},window)
        raw=tensor(arrays['noiseless']);target=tensor(arrays['target']);base=m(raw);out,status=reconstruct(m,raw,sensor_noise_sigma_gray=0,evidence_kind='known_procedural_operator')
        blur=dict(status=status,base_equal=torch.equal(base,out),Raw_mae=float((raw-target)[...,l:u,x0:x1].abs().mean()*255),output_mae=float((out-target)[...,l:u,x0:x1].abs().mean()*255))
        # Same observed array can also be the exact truth of a noiseless identity
        # camera. This is an information limit, not a hidden image-label test.
        observation_digest=hashlib.sha256(raw.cpu().numpy().tobytes()).hexdigest();m.observation=from_observation(observation_from_profile(identity_profile),checkpoint_ops=False).cuda();out,st=reconstruct(m,raw,sensor_noise_sigma_gray=0,evidence_kind='known_procedural_operator');ambiguity=dict(observation_sha256=observation_digest,same_observation_in_both_worlds=True,mean_truth_difference_gray=float((raw-target).abs().mean()*255),identity_world_exact=torch.equal(out,raw),blur_world_was_not_bypassed=blur['status']['neural_restoration_executed'])
        # Even identity-looking metadata cannot qualify an unknown real source.
        unknown_out,unknown=reconstruct(m,raw,sensor_noise_sigma_gray=0,evidence_kind='unqualified_real_assumption');assert unknown['neural_restoration_executed'] and not unknown['exact_preservation_guaranteed']
        panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());real=[];m.observation=from_observation(load_observation(R125/'config/real_observation_v2.json'),checkpoint_ops=False).cuda()
        for item in panel['full_images']:
            p=item['source']['path'];assert sha(p)==item['source']['sha256'];a=cv2.imread(p,0).astype(np.float32)/255;h,w=a.shape;cy,cx=h//2,w//2;window=[max(0,cy-144),min(h,cy+144),max(0,cx-144),min(w,cx+144)];y0,y1,x0,x1=window;raw=tensor(a[None,y0:y1,x0:x1]);base=m(raw);out,status=reconstruct(m,raw,sensor_noise_sigma_gray=None,evidence_kind='unqualified_real_assumption');real.append(dict(name=item['name'],source=item['source'],window=window,base_equal=torch.equal(base,out),status=status))
    param_after={n:hashlib.sha256(p.detach().cpu().numpy().tobytes()).hexdigest() for n,p in m.named_parameters()};assert param_after==param_before and sha(cp)==before[next(iter(before))]
    identities=[r for r in rows if r['category']=='clean_identity'];other=[r for r in rows if r['category']!='clean_identity'];passed=all(r['bitwise_raw_equal'] and r['guard_mae']==0 for r in identities) and all(r['bitwise_base_equal'] for r in other) and all(general) and noise['base_equal'] and blur['base_equal'] and all(r['base_equal'] and r['status']['neural_restoration_executed'] for r in real)
    save(ROOT/'results/preservation_verification.json',dict(checkpoint=record(cp),rows=rows,arbitrary_inputs_passed=sum(general),arbitrary_inputs_total=100,noisy_identity=noise,noiseless_blur=blur,ambiguous_observation_counterexample=ambiguity,unknown_identity_metadata_not_trusted=unknown,real_checks=real,weights_unchanged=True,optimizer_updates=0,passed=bool(passed),guarantee_is_conditional=True,real_clean_detector_implemented=False))
    print(json.dumps(dict(passed=bool(passed),identity_cases=len(identities),arbitrary100=sum(general),noisy_identity=noise,noiseless_blur=blur,real_inputs=len(real))),flush=True)

if __name__=='__main__':main()
