"""Rebuild actual model inputs without importing the treatment loader/trainer."""
from collections import Counter
import math
from common import ROOT,R125,np,json,sha,save,hashlib,time

def main():
    package=R125/'data/package_v2';manifest=json.loads((package/'manifest.json').read_text());slots=json.loads((ROOT/'config/photometry_slots.json').read_text())
    audit=json.loads((ROOT/'results/photometry_admission.json').read_text());lookup={(r['step'],r['expanded']):r for r in audit['rows']}
    result=[];start=time.perf_counter()
    for slot in slots:
        e=manifest['scenes'][slot['index']];mp=package/e['metadata_path'];ap=package/e['arrays_path'];assert sha(mp)==e['sha256']['metadata'] and sha(ap)==e['sha256']['arrays']
        meta=json.loads(mp.read_text())
        with np.load(ap) as d:noiseless=d['noiseless'];latent=d['latent_target'];target=d['target']
        radius=(len(meta['profile']['kernel']['values'])-1)//2
        model_halo=math.ceil((math.ceil(4*(3*(radius+3)+41)/4)+3)/16)*16
        motion=math.ceil(max(abs(v) for v in meta['shift_xy'])) if meta['motion_observable'] else 0
        halo=math.ceil((model_halo+math.ceil(radius/4)+motion+2)/16)*16
        l,u=256-halo,384+halo
        for arm in ['P','Q']:
            a=1.;b=0.
            if arm=='Q':
                a=slot['contrast_scale']
                if meta['identity']:
                    diff=(meta['photometry']['high']-meta['photometry']['low'])*255;a=round(a*diff)/diff
                low_shift=16/255-a*float(latent.min());high_shift=235/255-a*float(latent.max());b=low_shift+slot['placement_fraction']*(high_shift-low_shift)
                if meta['identity']:b=round((a*meta['photometry']['low']+b)*255)/255-a*meta['photometry']['low']
                clean=(noiseless.astype(float)*a+b).astype(np.float32)
            else:clean=noiseless
            noise=np.random.default_rng(slot['noise_seed']).normal(0,meta['noise_sigma_gray']/255,clean.shape)
            pixels=np.rint(np.clip(clean.astype(float)+noise,0,1)*255).astype(np.uint8)
            if meta['identity']:
                reference=((a*target.astype(float)+b).astype(np.float32)) if arm=='Q' else target
                pixels=np.rint(reference*255).astype(np.uint8)
            core=np.ascontiguousarray(pixels[:,256:384,256:384]);corehash=hashlib.sha256(core.tobytes()).hexdigest()
            assert corehash==lookup[slot['step'],arm=='Q']['actual_core_source_sha256']
            tensor=np.ascontiguousarray(pixels[:,None,l:u,l:u].astype(np.float32)/np.float32(255))
            result.append(dict(arm=arm,step=slot['step'],index=slot['index'],scene_id=meta['scene_id'],input_shape=list(tensor.shape),actual_input_sha256=hashlib.sha256(tensor.tobytes()).hexdigest(),core_sha256=corehash,window=[l,u,l,u],core=[halo,halo+128,halo,halo+128],scale=a,offset=b,source_arrays_sha256=e['sha256']['arrays']))
        if slot['step']%32==0:print(json.dumps(dict(replayed_slots=slot['step'],seconds=time.perf_counter()-start)),flush=True)
    save(ROOT/'results/independent_input_replay.json',dict(status='all256_inputs_rebuilt',records=result,slots_sha256=sha(ROOT/'config/photometry_slots.json'),data_admission_sha256=sha(ROOT/'results/photometry_admission.json'),script_sha256=sha(__file__),every_core_matches_pretraining_admission=True,training_loader_imported=False,seconds=time.perf_counter()-start))

if __name__=='__main__':main()
