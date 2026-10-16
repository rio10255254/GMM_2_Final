"""Preserve observations whose declared forward problem is already solved.

The current prototype admits known procedural evidence only for this guarantee.
Real instrument qualification is not implemented or invented. Unknown imaging
conditions continue to be explicitly unqualified, rather than guessed clean.
"""
import math
import torch

def exact_native_identity(observation):
    k=observation.kernel.detach()
    return bool(k.numel()==1 and float(k.reshape(-1)[0])==1. and float(observation.gain)==1. and float(observation.bias)==0.)

def reconstruct(model,raw,*,sensor_noise_sigma_gray=None,evidence_kind='unqualified_real_assumption'):
    model._validate_input(raw)
    if sensor_noise_sigma_gray is not None and (not math.isfinite(sensor_noise_sigma_gray) or sensor_noise_sigma_gray<0):raise ValueError('Invalid physical sensor noise declaration')
    if evidence_kind not in ['known_procedural_operator','unqualified_real_assumption']:raise ValueError('Real instrument qualification must be independently implemented, not asserted through a string')
    identity=exact_native_identity(model.observation)
    known_noiseless=evidence_kind=='known_procedural_operator' and sensor_noise_sigma_gray==0
    if identity and known_noiseless:
        # For an identity native observation and no noise, the observed native
        # image is already the unique native answer. Avoid arithmetic averaging
        # of repeated cells as well as unnecessary neural changes.
        return raw.clone(),dict(action='preserved_known_noiseless_native_identity',exact_preservation_guaranteed=True,guarantee_scope='known native identity observation and declared zero sensor noise',physical_real_accuracy_qualified=False,neural_restoration_executed=False)
    out=model(raw)
    return out,dict(action='ordinary_reconstruction',exact_preservation_guaranteed=False,guarantee_scope=None,physical_real_accuracy_qualified=False,neural_restoration_executed=True,reason='No proof that the native input is already the clean answer')
