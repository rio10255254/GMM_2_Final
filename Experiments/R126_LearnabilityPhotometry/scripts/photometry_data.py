"""Matched affine optical-intensity intervention; original physical data stay intact.

Unit-mass convolution on the source renderer's actual exterior commutes with
positive affine radiometry. Apply it to the clean optical object/observation,
then draw matched independent sensor noise and quantize. Do not transform a
noisy camera image and pretend its noise stayed fixed. Never read real/SEM data.
"""
from common import *
from training.context import window_for,crop_arrays

PACKAGE=R125/'data/package_v2'
MANIFEST=json.loads((PACKAGE/'manifest.json').read_text())

def plan(updates=128):
    if updates!=128:raise ValueError('Only declared two-pass128 plan')
    rng=np.random.default_rng(1267001)
    indices=np.concatenate([rng.permutation(64),rng.permutation(64)])
    cells=np.arange(updates)%12;rng.shuffle(cells)
    return [dict(step=i+1,index=int(idx),contrast_scale=[.125,.25,.5,1.][int(cell)//3],placement_fraction=[0.,.5,1.][int(cell)%3],photometry_cell=int(cell),noise_seed=1269000+i) for i,(idx,cell) in enumerate(zip(indices,cells))]

def load_base(index):
    e=MANIFEST['scenes'][index];ap=PACKAGE/e['arrays_path'];mp=PACKAGE/e['metadata_path']
    assert sha(ap)==e['sha256']['arrays'] and sha(mp)==e['sha256']['metadata']
    meta=json.loads(mp.read_text());assert meta['external_training_inputs']==[] and not meta['existing_test_answer_access']
    with np.load(ap) as d:arrays={k:d[k] for k in d.files}
    return arrays,meta,e

def transform(arrays,meta,slot,expanded):
    out={k:v for k,v in arrays.items()};meta=json.loads(json.dumps(meta));photo=meta['photometry']
    scale=1.;offset=0.
    if expanded:
        scale=float(slot['contrast_scale'])
        if meta['identity']:
            old_diff=(photo['high']-photo['low'])*255
            scale=round(scale*old_diff)/old_diff
        lower=float(arrays['latent_target'].min());upper=float(arrays['latent_target'].max())
        lo=16/255-scale*lower;hi=235/255-scale*upper
        if lo>hi:raise ValueError('Requested intensity envelope impossible')
        offset=lo+float(slot['placement_fraction'])*(hi-lo)
        if meta['identity']:offset=(round((scale*photo['low']+offset)*255)/255)-scale*photo['low']
        for key in ['target','latent_target','noiseless']:
            out[key]=(scale*arrays[key].astype(np.float64)+offset).astype(np.float32)
        if meta['identity']:
            out['target']=np.rint(out['target']*255).astype(np.float32)/np.float32(255)
            out['latent_target']=out['target'].repeat(4,-2).repeat(4,-1)
            out['noiseless']=out['target'].copy()
        photo['low']=scale*photo['low']+offset;photo['high']=scale*photo['high']+offset
        photo['texture_amplitude']*=scale
    # Same normal variates and actual sensor sigma in both treatment arms.
    sigma=float(meta['noise_sigma_gray'])
    rng=np.random.default_rng(slot['noise_seed']);noise=rng.normal(0,sigma/255,out['noiseless'].shape)
    pre=out['noiseless'].astype(np.float64)+noise
    out['source']=np.rint(np.clip(pre,0,1)*255).astype(np.uint8)
    if meta['identity']:out['source']=np.rint(out['target']*255).astype(np.uint8)
    meta['photometry_intervention']=dict(contrast_scale=scale,intensity_offset=offset,placement_fraction=slot['placement_fraction'],expanded=expanded,noise_seed=slot['noise_seed'],actual_sensor_sigma_gray=sigma,applied_before_sensor_noise=True)
    meta['source_package']='R125 immutable procedural v2';meta['R126_slot']=slot
    meta['physical_full_image_saturated_pixels']=int(((out['source']==0)|(out['source']==255)).sum())
    meta['training_core_slice']=[256,384,256,384]
    return out,meta

def batch(m,slot,expanded):
    arrays,meta,e=load_base(slot['index']);arrays,meta=transform(arrays,meta,slot,expanded)
    m.observation=from_observation(observation_from_profile(meta['profile']),checkpoint_ops=True).cuda()
    window=window_for(m,meta);meta['training_core_slice']=window['core'];meta['R126_window']=window
    arrays=crop_arrays(arrays,window)
    source=torch.from_numpy(arrays['source'].astype(np.float32)/255)[:,None].cuda()
    targets={k:torch.from_numpy(arrays[k])[:,None].cuda() for k in ['target','latent_target','noiseless','sdf','boundary']}
    return source,targets,meta,e

if __name__=='__main__':
    a,m,e=load_base(0);print(transform(a,m,plan()[0],True)[1]['photometry_intervention'])
