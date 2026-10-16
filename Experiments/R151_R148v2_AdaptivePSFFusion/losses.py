import math

import torch


def robust_gray(residual):
    epsilon = 0.5/255
    squared = residual.square()
    return (squared/(torch.sqrt(squared+epsilon*epsilon)+epsilon)).mean()*255


def translated(value, delta):
    height, width = value.shape[-2:]
    nx, ny = math.floor(-float(delta[0])), math.floor(-float(delta[1]))
    fx, fy = -float(delta[0])-nx, -float(delta[1])-ny
    def sample(dy, dx):
        out = torch.zeros_like(value)
        y0, y1 = max(0, -dy), min(height, height-dy)
        x0, x1 = max(0, -dx), min(width, width-dx)
        if y1 > y0 and x1 > x0:
            out[..., y0:y1, x0:x1] = value[..., y0+dy:y1+dy, x0+dx:x1+dx]
        return out
    return (1-fy)*((1-fx)*sample(ny,nx)+fx*sample(ny,nx+1))+fy*((1-fx)*sample(ny+1,nx)+fx*sample(ny+1,nx+1))


def normalize_view(x):
    mean = x.mean((-2,-1), keepdim=True)
    std = torch.sqrt((x-mean).square().mean((-2,-1), keepdim=True)+(0.5/255)**2)
    return (x-mean)/std


def gradient(x):
    p = torch.cat((x[...,1:2].flip(-1),x,x[...,-2:-1].flip(-1)),-1)
    p = torch.cat((p[...,1:2,:].flip(-2),p,p[...,-2:-1,:].flip(-2)),-2)
    return (p[...,1:-1,2:]-p[...,1:-1,:-2])*0.5, (p[...,2:,1:-1]-p[...,:-2,1:-1])*0.5


def boundary_coordinates(x, sdf, valid):
    gx, gy = gradient(x)
    magnitude = torch.sqrt(gx.square()+gy.square()+1e-8)
    band = torch.exp(-sdf.abs()/2)*valid[:,None,None,None].to(x.dtype)
    weight = magnitude*band
    mass = weight.sum((-2,-1))+1e-8
    signed = (weight*sdf).sum((-2,-1))/mass
    spread = (weight*sdf.abs()).sum((-2,-1))/mass
    return signed[:,0], spread[:,0]


def stage_terms(prediction, batch):
    low, high = batch["core"]
    crop = lambda x: x[...,low:high,low:high]
    target = batch["target"]
    residual = crop(prediction-target)
    pgx,pgy = gradient(crop(prediction))
    tgx,tgy = gradient(crop(target))
    terms = {
        "image": robust_gray(residual),
        "gradient": 0.5*(robust_gray(pgx-tgx)+robust_gray(pgy-tgy)),
    }
    normalized = normalize_view(prediction)
    terms["pair_output"] = torch.stack([
        robust_gray(crop(normalized[v:v+1]-translated(normalized[0:1],batch["shifts_xy"][v])))/255
        for v in range(1,4)
    ]).mean()
    ps,pr = boundary_coordinates(crop(prediction),batch["sdf"],batch["geometry_valid"])
    ts,tr = boundary_coordinates(crop(target),batch["sdf"],batch["geometry_valid"])
    valid = batch["geometry_valid"]
    terms["boundary"] = ((ps[valid]-ts[valid]).abs()+0.5*(pr[valid]-tr[valid]).abs()).mean() if valid.any() else prediction.sum()*0
    return terms


def objective(states, batch, model, cfg):
    totals = {k:states[0].sum()*0 for k in ("image","gradient","pair_output","boundary")}
    total = states[0].sum()*0
    for weight, prediction in zip(cfg["stage_weights"], states):
        terms = stage_terms(prediction, batch)
        total = total + weight*sum(cfg["loss"][key]*terms[key] for key in totals)
        for key in totals:
            totals[key] = totals[key] + weight*terms[key]
    predicted_observation = model.optics.blur(states[-1], batch["operator_psf_indices"])
    low, high = batch["observation_core"]
    observation = robust_gray((predicted_observation-batch["source"])[...,low:high,low:high])
    selector = model.psf_fusion.selector_loss(batch["actual_psf_indices"])
    descriptor = model.psf_fusion.descriptor_loss(batch["actual_psf_indices"])
    accuracy, valid_count = model.psf_fusion.selector_accuracy(batch["actual_psf_indices"])
    total = total + cfg["loss"]["observation"]*observation + cfg["loss"]["selector_identity"]*selector + cfg["loss"]["selector_descriptor"]*descriptor
    totals.update({
        "observation": observation,
        "selector": selector,
        "selector_descriptor": descriptor,
        "selector_accuracy": accuracy,
        "selector_valid": valid_count.to(dtype=states[0].dtype),
        "selector_entropy": model.psf_fusion.last_entropy.to(states[0].device),
        "psf_beta": model.psf_fusion.last_beta.to(states[0].device),
    })
    return total, totals
