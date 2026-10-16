import torch
def optimizer(model,lr,weight_decay):return torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=weight_decay)
