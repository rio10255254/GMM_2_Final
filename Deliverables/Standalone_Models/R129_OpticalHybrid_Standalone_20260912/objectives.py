import math
import torch

def robust_gray(residual):
    e = 0.5 / 255
    s = residual.square()
    return (s / (torch.sqrt(s + e * e) + e)).mean() * 255

def translated(value, delta):
    h, w = value.shape[-2:]
    nx = math.floor(-delta[0])
    ny = math.floor(-delta[1])
    fx = -delta[0] - nx
    fy = -delta[1] - ny

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
