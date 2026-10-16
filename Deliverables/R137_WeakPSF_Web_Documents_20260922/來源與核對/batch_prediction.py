def predict_batch(model,batch):
 cue=None
 if model.optical_enabled and model.optical_gain!=0:cue=model.optics(batch['optical_source'])[...,32:352,32:352]
 return model(batch['source'],optical_cue=cue)
