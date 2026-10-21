import torch
from torch.nn import functional as F

class Bilinear2x(torch.autograd.Function):

    @staticmethod
    def forward(ctx, x):
        return F.interpolate(x, scale_factor=2, mode='bilinear', align_corners=False)

    @staticmethod
    def backward(ctx, g):
        even, odd = (g[..., 0::2, :], g[..., 1::2, :])
        y = 0.75 * (even + odd)
        y[..., 1:, :] += 0.25 * odd[..., :-1, :]
        y[..., :-1, :] += 0.25 * even[..., 1:, :]
        y[..., :1, :] += 0.25 * even[..., :1, :]
        y[..., -1:, :] += 0.25 * odd[..., -1:, :]
        even, odd = (y[..., 0::2], y[..., 1::2])
        x = 0.75 * (even + odd)
        x[..., 1:] += 0.25 * odd[..., :-1]
        x[..., :-1] += 0.25 * even[..., 1:]
        x[..., :1] += 0.25 * even[..., :1]
        x[..., -1:] += 0.25 * odd[..., -1:]
        return x
