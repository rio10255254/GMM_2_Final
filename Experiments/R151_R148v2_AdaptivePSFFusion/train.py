"""Scratch training for the R151 paper-aligned adaptive PSF fusion model."""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import torch

from dataset import Bank
from losses import objective
from model import Model
from training_policy import optimizer
from utils import ROOT, data_config, load, model_config, now, save, setup, sha, train_config, verify_bank_lock
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def learning_rate(step, total, cfg):
    settings = cfg["optimizer"]
    warm = min(cfg["warmup"], max(8, total//8))
    if step <= warm:
        return settings["max_lr"]*step/warm
    return settings["min_lr"] + 0.5*(settings["max_lr"]-settings["min_lr"])*(1+math.cos(math.pi*(step-warm)/(total-warm)))


def assess(model, bank, split, device, cfg, limit=None):
    model.eval()
    count = cfg["splits"][split] if limit is None else min(limit, cfg["splits"][split])
    values, parts = [], []
    with torch.inference_mode():
        for index in range(count):
            batch = bank.batch(split,index,device)
            _, states = model(batch["source"],batch["operator_psf_indices"],True)
            loss, terms = objective(states,batch,model,cfg)
            values.append(float(loss))
            parts.append({key:float(value) for key,value in terms.items()})
    return {
        "split":split,
        "parents":count,
        "mean_loss":sum(values)/count,
        "mean_terms":{key:sum(row[key] for row in parts)/count for key in parts[0]},
        "individual_loss":values,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-name",required=True)
    parser.add_argument("--short-updates",type=int)
    parser.add_argument("--seed",type=int)
    parser.add_argument("--assessment-limit",type=int,default=16)
    args=parser.parse_args()
    cfg=train_config();mc=model_config();reference=data_config()
    seed=cfg["model_seed"] if args.seed is None else args.seed
    setup(seed);verify_bank_lock();bank=Bank(cfg);device=cfg["device"]
    model=Model(mc,ROOT).to(device)
    selector_parameters=list(model.psf_fusion.estimator.parameters())
    selector_ids={id(p) for p in selector_parameters}
    main_parameters=[p for p in model.parameters() if id(p) not in selector_ids]
    opt=torch.optim.AdamW([
        {"params":main_parameters,"lr_scale":1.0},
        {"params":selector_parameters,"lr_scale":float(cfg["selector_lr_multiplier"])},
    ],lr=cfg["optimizer"]["max_lr"],weight_decay=cfg["optimizer"]["weight_decay"])
    run=ROOT/"runs"/args.run_name
    if run.exists() and not (run/"latest.json").exists():
        raise FileExistsError("Run exists without a resumable checkpoint")
    run.mkdir(parents=True,exist_ok=True);(run/"checkpoints").mkdir(exist_ok=True)
    latest=run/"latest.json";log=run/"updates.jsonl";start=0
    total=cfg["updates"] if args.short_updates is None else args.short_updates
    formal=args.short_updates is None
    if latest.exists():
        record=load(latest)
        if sha(record["path"])!=record["sha256"]:raise RuntimeError("Checkpoint identity changed")
        checkpoint=torch.load(record["path"],map_location="cpu",weights_only=False)
        if checkpoint["model_config"]!=mc or checkpoint["seed"]!=seed:raise RuntimeError("Resume configuration changed")
        model.load_state_dict(checkpoint["model"],strict=True);opt.load_state_dict(checkpoint["optimizer"])
        torch.set_rng_state(checkpoint["torch_rng"]);torch.cuda.set_rng_state_all(checkpoint["cuda_rng"])
        start=checkpoint["step"]
        if len(log.read_text(encoding="utf-8").splitlines())!=start:raise RuntimeError("Training log length mismatch")
    save(run/"run_config.json",{
        "model":mc,"train":cfg,"seed":seed,"total":total,"formal":formal,
        "source_experiment":str(PROJECT_ROOT / reference["source_experiment"]),
        "payload_manifest_sha256":reference["payload_manifest_sha256"],
        "geometry_manifest_sha256":reference["geometry_manifest_sha256"],
        "psf_bank_sha256":sha(ROOT/mc["psf_bank"]),"started_utc":now(),
    })
    limit=None if formal else args.assessment_limit
    if start==0:
        save(run/"dev_initial.json",assess(model,bank,"dev",device,cfg,limit))
    begin=time.perf_counter()

    def checkpoint_file(step):
        path=run/"checkpoints"/f"step{step:05d}.pth";temporary=path.with_suffix(".tmp")
        torch.save({
            "model_name":mc["model_name"],"model":{k:v.detach().cpu() for k,v in model.state_dict().items()},
            "optimizer":opt.state_dict(),"step":step,"seed":seed,"model_config":mc,"train_config":cfg,
            "payload_manifest_sha256":reference["payload_manifest_sha256"],
            "geometry_manifest_sha256":reference["geometry_manifest_sha256"],
            "psf_bank_sha256":sha(ROOT/mc["psf_bank"]),
            "checkpoint_kind":"trained_model" if formal and step==8192 else "short_test" if not formal and step==total else "incomplete_training",
            "torch_rng":torch.get_rng_state(),"cuda_rng":torch.cuda.get_rng_state_all(),
        },temporary)
        os.replace(temporary,path);save(latest,{"path":str(path),"step":step,"sha256":sha(path)})

    with log.open("a",encoding="utf-8",buffering=1) as handle:
        for step in range(start+1,total+1):
            epoch=(step-1)//512;index=int(bank.order(epoch)[(step-1)%512]);batch=bank.batch("train",index,device,epoch)
            model.train();opt.zero_grad(set_to_none=True)
            _,states=model(batch["source"],batch["operator_psf_indices"],True)
            loss,terms=objective(states,batch,model,cfg);loss.backward()
            selector_gradient=0.0
            for parameter in model.psf_fusion.estimator.parameters():
                if parameter.grad is not None:selector_gradient+=float(parameter.grad.detach().double().square().sum())
            selector_gradient=selector_gradient**0.5
            torch.nn.utils.clip_grad_norm_(model.parameters(),cfg["optimizer"]["gradient_clip"],error_if_nonfinite=True)
            rate=learning_rate(step,total,cfg)
            for group in opt.param_groups:group["lr"]=rate*group.get("lr_scale",1.0)
            opt.step()
            weights=model.psf_fusion.last_weights
            record={
                "step":step,"epoch":epoch,"parent_id":batch["parent_id"],"category":batch["category"],"loss":float(loss),
                **{key:float(value) for key,value in terms.items()},
                "eta":(mc["eta_max"]*torch.sigmoid(model.step_logits)).detach().cpu().tolist(),
                "selector_gradient_l2":selector_gradient,
                "selector_weight_min":float(weights.min()),"selector_weight_max":float(weights.max()),
                "selector_top_indices":weights.argmax(1).cpu().tolist(),
                "learning_rate":rate,"utc":now(),
            }
            handle.write(json.dumps(record,ensure_ascii=False)+"\n")
            if step%32==0 or step==total:
                save(run/"status.json",{"state":"training","step":step,"total":total,"loss":float(loss),"elapsed_seconds":time.perf_counter()-begin,"updated_utc":now()})
                print("TRAIN",args.run_name,step,"/",total,float(loss),"selector",float(terms["selector"]),"acc",float(terms["selector_accuracy"]),flush=True)
            if step%128==0 or step==total:checkpoint_file(step)
            if formal and step%cfg["dev_every"]==0:save(run/f"dev_{step:05d}.json",assess(model,bank,"dev",device,cfg))
    final=assess(model,bank,"test" if formal else "dev",device,cfg,limit)
    save(run/("test_final.json" if formal else "dev_final.json"),final)
    if formal:
        save(run/"training_complete.json",{"updates":total,"checkpoint":load(latest),"real_validation_complete":False,"completed_utc":now()})
    else:
        save(run/"short_complete.json",{
            "updates":total,"checkpoint":load(latest),"seed":seed,
            "dev_initial":load(run/"dev_initial.json")["mean_loss"],"dev_final":final["mean_loss"],
            "selector_initial":load(run/"dev_initial.json")["mean_terms"]["selector"],
            "selector_final":final["mean_terms"]["selector"],
            "selector_descriptor_initial":load(run/"dev_initial.json")["mean_terms"]["selector_descriptor"],
            "selector_descriptor_final":final["mean_terms"]["selector_descriptor"],
            "selector_accuracy_initial":load(run/"dev_initial.json")["mean_terms"]["selector_accuracy"],
            "selector_accuracy_final":final["mean_terms"]["selector_accuracy"],
            "not_a_formal_model":True,"completed_utc":now(),
        })
    save(run/"status.json",{"state":"training_complete" if formal else "short_complete","step":total,"total":total,"updated_utc":now()})
    print("FINISHED",args.run_name,flush=True)


if __name__=="__main__":main()
