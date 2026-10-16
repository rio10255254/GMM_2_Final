"""User-confirmed ordinary external-model training on the same fixed data."""
COMMON={
    'seed':1482101,'image_order_seed':1482102,'noise_seed':1481003,
    'training_scenes':512,'views_per_scene':4,'images_per_epoch':2048,'batch_size':4,
    'input_size':384,'supervised_core':[144,240],
    'min_epochs':8,'max_epochs':32,'early_stop_patience_epochs':5,
    'meaningful_PSNR_improvement_dB':0.02,'lr_plateau_patience_epochs':2,
    'lr_reduction_factor':0.5,'minimum_lr':1e-6,
    'validation_scenes':128,'test_scenes':128,'validation_every_epochs':1,
    'selection':'highest synthetic validation mean per-image core PSNR; no real-data selection',
    'stopping':'at least 8 epochs, then 5 epochs without a 0.02 dB validation improvement, or 32-epoch cap',
    'precision':'FP32; TF32 disabled','pretrained_weights':False,
    'training_unit':'one independent image/clear pair; all 2048 views shuffled each epoch',
    'extra_training_geometry_pair_observation_losses':False,
    'evaluation_losses':'original five MOSR task terms reported as common diagnostics only',
    'scope':'ordinary author loss/optimizer adapted to fixed grayscale x1 data and common valid supervision region',
}
NORMAL={
    'EDSR-x1':{'loss':'L1','optimizer':'Adam','lr':1e-4,'betas':[.9,.999],'weight_decay':0.,'clip_norm':None,'ema':0.},
    'RDN-x1':{'loss':'L1','optimizer':'Adam','lr':1e-4,'betas':[.9,.999],'weight_decay':0.,'clip_norm':None,'ema':0.},
    'RCAN-x1':{'loss':'L1','optimizer':'Adam','lr':1e-4,'betas':[.9,.999],'weight_decay':0.,'clip_norm':None,'ema':0.},
    'NAFNet':{'loss':'author_PSNRLoss','optimizer':'AdamW','lr':1e-3,'betas':[.9,.9],'weight_decay':1e-3,'clip_norm':.01,'ema':0.},
    'SwinIR':{'loss':'author_Charbonnier','charbonnier_eps':1e-9,'optimizer':'Adam','lr':2e-4,'betas':[.9,.999],'weight_decay':0.,'clip_norm':None,'ema':.999},
    'Restormer':{'loss':'L1','optimizer':'AdamW','lr':3e-4,'betas':[.9,.999],'weight_decay':1e-4,'clip_norm':.01,'ema':0.},
    'USRNet-x1':{'loss':'L1','optimizer':'Adam','lr':1e-4,'betas':[.9,.999],'weight_decay':0.,'clip_norm':None,'ema':0.,'initialization':'author_orthogonal_gain_0.2'},
}
