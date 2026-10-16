"""Explicit larger-context measurement; retains unobservable local results.

V3 remains the numerical estimator and keeps all of its limits. Vertical stripe
patches cannot reliably identify a full2D translation by themselves. Supplying
more of the same observed pair is an information change, not a looser cutoff.
"""
from motion_reader_v3 import measure as measure_patch

def measure(a,b,context=None):
    local=measure_patch(a,b)
    if context is None:
        return {**local,'measurement_scope':'supplied_patch','local_measurement':local,'context_measurement':None}
    ca,cb=context
    if ca.shape!=cb.shape or ca.shape[0]<a.shape[0] or ca.shape[1]<a.shape[1]:raise ValueError('Context must cover the supplied pair')
    wider=measure_patch(ca,cb)
    return {**wider,'measurement_scope':'larger_observed_context','local_measurement':local,'context_measurement':wider,'local_validity_not_promoted':True}
