def require_disabled(mode):
    if mode != 'off':
        raise NotImplementedError('This first-stage model supports optical_mode=off only; feature_single/feature_field are reserved, not implemented.')
