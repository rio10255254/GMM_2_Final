"""Versioned untrained-prototype artifacts with explicit observation identity."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import torch
from .calibration import observation_from_profile
from .network import build_model


def _profile_digest(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save_initialization(path, model, profile: dict, seed: int):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    expected = observation_from_profile(profile)
    actual = model.observation
    for key in ('kernel', 'gain', 'bias', 'noise_variance'):
        if not torch.equal(getattr(actual, key).detach().cpu(), getattr(expected, key)):
            raise ValueError(f'Profile does not describe actual observation {key}')
    if actual.get_extra_state() != expected.get_extra_state():
        raise ValueError('Observation provenance differs from profile')
    payload = {'schema_version': 1, 'kind': 'untrained_prototype_initialization',
               'optimizer_updates': 0, 'seed': int(seed), 'config': model.config_dict(),
               'observation_profile': profile, 'observation_profile_sha256': _profile_digest(profile),
               'state_dict': model.state_dict(), 'instrument_qualified': False,
               'uncertainty_calibrated': False}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        torch.save(payload, f)


def load_initialization(path, device='cpu'):
    payload = torch.load(path, map_location='cpu', weights_only=True)
    if payload.get('schema_version') != 1 or payload.get('kind') != 'untrained_prototype_initialization':
        raise ValueError('Not an R124 untrained initialization artifact')
    if payload.get('optimizer_updates') != 0 or payload.get('instrument_qualified') is not False:
        raise ValueError('Prototype loader does not accept training or qualification claims')
    if payload.get('uncertainty_calibrated') is not False:
        raise ValueError('Prototype uncertainty is not calibrated')
    profile = payload['observation_profile']
    if _profile_digest(profile) != payload['observation_profile_sha256']:
        raise ValueError('Observation profile digest mismatch')
    obs = observation_from_profile(profile)
    expected_buffers = {key: getattr(obs, key).clone() for key in ('kernel', 'gain', 'bias', 'noise_variance')}
    expected_meta = obs.get_extra_state().copy()
    model = build_model(payload['config'], obs)
    model.load_state_dict(payload['state_dict'], strict=True)
    for key, value in expected_buffers.items():
        if not torch.equal(getattr(model.observation, key), value):
            raise ValueError(f'Checkpoint observation buffer differs from declared profile: {key}')
    if model.observation.get_extra_state() != expected_meta:
        raise ValueError('Checkpoint observation provenance differs from declared profile')
    return model.to(device).eval(), payload
