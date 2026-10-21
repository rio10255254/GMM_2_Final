import math, torch

def robust_gray(r):
    e = 0.5 / 255
    s = r.square()
    return (s / (torch.sqrt(s + e * e) + e)).mean() * 255

def translated(value, delta):
    h, w = value.shape[-2:]
    nx = math.floor(-float(delta[0]))
    ny = math.floor(-float(delta[1]))
    fx = -float(delta[0]) - nx
    fy = -float(delta[1]) - ny

    def sample(dy, dx):
        out = torch.zeros_like(value)
        y0 = max(0, -dy)
        y1 = min(h, h - dy)
        x0 = max(0, -dx)
        x1 = min(w, w - dx)
        if y1 > y0 and x1 > x0:
            out[..., y0:y1, x0:x1] = value[..., y0 + dy:y1 + dy, x0 + dx:x1 + dx]
        return out
    return (1 - fy) * ((1 - fx) * sample(ny, nx) + fx * sample(ny, nx + 1)) + fy * ((1 - fx) * sample(ny + 1, nx) + fx * sample(ny + 1, nx + 1))

def normalize_view(x):
    mean = x.mean((-2, -1), keepdim=True)
    std = torch.sqrt((x - mean).square().mean((-2, -1), keepdim=True) + (0.5 / 255) ** 2)
    return (x - mean) / std

def gradient(x):
    p = torch.cat((x[..., 1:2].flip(-1), x, x[..., -2:-1].flip(-1)), -1)
    p = torch.cat((p[..., 1:2, :].flip(-2), p, p[..., -2:-1, :].flip(-2)), -2)
    return ((p[..., 1:-1, 2:] - p[..., 1:-1, :-2]) * 0.5, (p[..., 2:, 1:-1] - p[..., :-2, 1:-1]) * 0.5)

def boundary_coordinates(x, sdf, valid):
    gx, gy = gradient(x)
    w = torch.sqrt(gx.square() + gy.square() + 1e-08)
    band = torch.exp(-sdf.abs() / 2) * valid[:, None, None, None].to(x.dtype)
    q = w * band
    mass = q.sum((-2, -1)) + 1e-08
    signed = (q * sdf).sum((-2, -1)) / mass
    spread = (q * sdf.abs()).sum((-2, -1)) / mass
    return (signed[:, 0], spread[:, 0])

def stage_terms(pred, b):
    lo, hi = b['core']
    crop = lambda x: x[..., lo:hi, lo:hi]
    target = b['target']
    r = crop(pred - target)
    pgx, pgy = gradient(crop(pred))
    tgx, tgy = gradient(crop(target))
    terms = dict(image=robust_gray(r), gradient=0.5 * (robust_gray(pgx - tgx) + robust_gray(pgy - tgy)))
    norm = normalize_view(pred)
    terms['pair_output'] = torch.stack([robust_gray(crop(norm[v:v + 1] - translated(norm[0:1], b['shifts_xy'][v]))) / 255 for v in range(1, 4)]).mean()
    ps, pr = boundary_coordinates(crop(pred), b['sdf'], b['geometry_valid'])
    ts, tr = boundary_coordinates(crop(target), b['sdf'], b['geometry_valid'])
    valid = b['geometry_valid']
    terms['boundary'] = ((ps[valid] - ts[valid]).abs() + 0.5 * (pr[valid] - tr[valid]).abs()).mean() if valid.any() else pred.sum() * 0
    return terms

def objective(states, b, model, cfg):
    totals = {k: states[0].sum() * 0 for k in ('image', 'gradient', 'pair_output', 'boundary')}
    total = states[0].sum() * 0
    for weight, pred in zip(cfg['stage_weights'], states):
        t = stage_terms(pred, b)
        total += weight * sum((cfg['loss'][k] * t[k] for k in totals))
        for k in totals:
            totals[k] += weight * t[k]
    predicted = model.optics.blur(states[-1], b['operator_psf_indices'])
    lo, hi = b['observation_core']
    observation = robust_gray((predicted - b['source'])[..., lo:hi, lo:hi])
    total += cfg['loss']['observation'] * observation
    totals['observation'] = observation
    return (total, totals)
