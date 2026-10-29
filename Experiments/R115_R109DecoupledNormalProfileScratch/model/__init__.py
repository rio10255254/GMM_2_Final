from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# The locked ACM runner imports its audited R114 model module before R115
# replaces only the inference adapter.  Extend this package search path so
# both audited modules can coexist without copying either implementation.
_r114_model = Path(str(PROJECT_ROOT / 'Experiments/R114_ConfidenceGatedRecoverableScratch/model'))
if str(_r114_model) not in __path__:
    __path__.append(str(_r114_model))

from .r115_model import R115Model, build_model, count_parameters, load_r109_for_probe

__all__ = ["R115Model", "build_model", "count_parameters", "load_r109_for_probe"]
