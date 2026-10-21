# Internal programs

`r75_dataset.py` creates and audits the three data packages. `launch_r75.py` locks the scratch-only training rules, checks the local model files, starts the frozen trainer, and exports completed weights. The PowerShell files remain optional command-line shortcuts; normal manual use starts from `training/train_r75.py` or `inference/infer_r75.py`.
