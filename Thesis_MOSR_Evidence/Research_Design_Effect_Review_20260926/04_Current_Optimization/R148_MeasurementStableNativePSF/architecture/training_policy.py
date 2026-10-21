import torch
def optimizer(model,base_lr,weight_decay,optical_lr_multiplier):
 main=[];opt=[]
 for n,p in model.named_parameters():(opt if n=='optical_step_logits' else main).append(p)
 return torch.optim.AdamW([{'params':main,'lr':base_lr,'name':'main'},{'params':opt,'lr':base_lr*optical_lr_multiplier,'name':'optical_step'}],weight_decay=weight_decay)
