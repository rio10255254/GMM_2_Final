"""Keep the original128 supervised pixels and all required mathematical context."""
import math
def window_for(model,metadata):
    radius=math.ceil(model.observation.kernel_radius_internal/model.config.sampling_factor)
    motion=math.ceil(max(abs(float(x)) for x in metadata['shift_xy'])) if metadata['motion_observable'] else 0
    # Modeloutputcontext + extraF inobservationloss + residualinterpolation.
    halo=math.ceil((model.required_halo+radius+motion+2)/16)*16
    if halo>256:raise ValueError(f'Generated640contextdoesnotcovertrainingobjective: halo{halo}')
    return {'halo':halo,'window':[256-halo,384+halo,256-halo,384+halo],'core':[halo,halo+128,halo,halo+128]}
def crop_arrays(arrays,window):
    y0,y1,x0,x1=window['window'];out={}
    for k,a in arrays.items():
        f=4 if k=='latent_target' else 1
        out[k]=a[...,y0*f:y1*f,x0*f:x1*f]
    return out
