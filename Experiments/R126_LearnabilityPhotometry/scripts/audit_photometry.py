"""Admission independently checks every planned source and selected8x rerenders."""
import importlib.util
from scipy import signal
from photometry_data import *

def main():
    setup();slots=plan();save(ROOT/'config/photometry_slots.json',slots)
    rows=[];rerenders=[];start=time.perf_counter()
    spec=importlib.util.spec_from_file_location('r125_generator_independent',R125/'data/generator_v2.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    for j,slot in enumerate(slots):
        base,meta,e=load_base(slot['index'])
        for expanded in [False,True]:
            a,m=transform(base,meta,slot,expanded);obs=from_observation(observation_from_profile(m['profile']),checkpoint_ops=False).cuda()
            # Extra original source context beyond the central128 readout.
            rr=int(np.ceil(obs.kernel_radius_internal/4))+2;l=256-rr;u=384+rr
            latent=torch.from_numpy(a['latent_target'][...,4*l:4*u,4*l:4*u])[:,None].cuda()
            with torch.no_grad():
                prediction=obs(latent).cpu().numpy()[:,0,rr:rr+128,rr:rr+128]
            error=(prediction-a['noiseless'][:,256:384,256:384])*255
            sigma=np.sqrt(float(m['profile']['noise_variance']))*255
            area=a['latent_target'].reshape(2,640,4,640,4).mean((2,4))
            cs=a['source'][:,256:384,256:384]
            record=dict(step=slot['step'],scene_id=m['scene_id'],index=slot['index'],expanded=expanded,photometry_cell=slot['photometry_cell'],category=m['category'],rms_sigma=float(np.sqrt(np.mean(error.astype(float)**2))/sigma),p99_sigma=float(np.quantile(np.abs(error),.99)/sigma),area_target_max=float(np.max(np.abs(area-a['target']))),core_saturated_pixels=int(((cs==0)|(cs==255)).sum()),target_range_gray=[float(a['latent_target'].min()*255),float(a['latent_target'].max()*255)],plateaus_gray=[m['photometry']['low']*255,m['photometry']['high']*255],contrast_gray=(m['photometry']['high']-m['photometry']['low'])*255,transform=m['photometry_intervention'],source_original_arrays_sha256=e['sha256']['arrays'],actual_core_source_sha256=hashlib.sha256(np.ascontiguousarray(cs).tobytes()).hexdigest(),noise_sigma_gray=m['noise_sigma_gray'])
            record['admitted']=bool(record['rms_sigma']<=.25 and record['p99_sigma']<=1 and record['area_target_max']<=2e-7 and record['core_saturated_pixels']==0 and 0<=a['latent_target'].min()<=a['latent_target'].max()<=1)
            if m['identity']:record['identity_exact']=bool(np.array_equal(a['source'].astype(np.float32)/255,a['target']));record['admitted'] &= record['identity_exact']
            rows.append(record)
            # Fixed first occurrence of indices000..005, independent physical
            # construction of transformed intensities before8x convolution.
            if expanded and slot['index']<6 and not any(r['index']==slot['index'] for r in rerenders):
                radius=int(meta['rendering_profile']['radius_native']);axis=(np.arange((128+2*radius)*8,dtype=np.float64)+.5)/8+256-radius
                region=slice(radius*8,(radius+128)*8);kernel=np.asarray(meta['rendering_profile']['kernel'],dtype=np.float64)
                checks=[]
                for view,shift in enumerate(meta['view_shift_xy']):
                    optical,_,_=g.intensity_at(axis[None,:],axis[:,None],meta['shape_params'],m['photometry'],shift)
                    blurred=optical if meta['identity'] else signal.fftconvolve(optical,kernel,mode='same')
                    truth=g.area_average(optical[region,region],8);noiseless=g.area_average(blurred[region,region],8)
                    checks.append(dict(view=view,target_max_gray=float(np.max(np.abs(truth-a['target'][view,256:384,256:384]))*255),noiseless_max_gray=float(np.max(np.abs(noiseless-a['noiseless'][view,256:384,256:384]))*255)))
                rerenders.append(dict(index=slot['index'],step=slot['step'],views=checks))
        if (j+1)%16==0:print(json.dumps(dict(checked_slots=j+1,failed=sum(not r['admitted'] for r in rows),seconds=time.perf_counter()-start)),flush=True)
    failed=[r for r in rows if not r['admitted']]
    independent=max(v[k] for row in rerenders for v in row['views'] for k in ['target_max_gray','noiseless_max_gray'])
    result=dict(status='photometry_admission_evaluated',slots_sha256=sha(ROOT/'config/photometry_slots.json'),source_manifest_sha256=sha(PACKAGE/'manifest.json'),script_sources={str(p):sha(p) for p in [Path(__file__),ROOT/'scripts/photometry_data.py']},rows=rows,independent8x_rerenders=rerenders,independent8x_max_gray=independent,failures=failed,pilot_admitted=not failed and independent<.0001,actual_core_checks=256,affine_transform_never_amplifies_existing_representation_error=all(r['transform']['contrast_scale']<=1+1e-12 for r in rows),real_images_or_SEM_answers_used=False)
    save(ROOT/'results/photometry_admission.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows','independent8x_rerenders','script_sources']}),flush=True)

if __name__=='__main__':main()
