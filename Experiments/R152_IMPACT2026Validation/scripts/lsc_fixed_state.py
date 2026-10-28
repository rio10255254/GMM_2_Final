"""Order-independent wrapper around the preserved manuscript boundary + geometric LSC reader."""
import threading
import skimage.segmentation.morphsnakes as morphsnakes
from reference_circle_core import measure_inflection_lsc
_lock=threading.RLock()

def measure_inflection_lsc_fixed(*args,**kwargs):
    """Start every pillar at the native R152 evaluation convention, then restore caller state."""
    with _lock:
        previous=morphsnakes._curvop
        morphsnakes._curvop=morphsnakes._fcycle([
            lambda x:morphsnakes.sup_inf(morphsnakes.inf_sup(x)),
            lambda x:morphsnakes.inf_sup(morphsnakes.sup_inf(x)),
        ])
        try:return measure_inflection_lsc(*args,**kwargs)
        finally:morphsnakes._curvop=previous
