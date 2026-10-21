# Training

Open `train_r75.py`, edit the clearly marked settings at the top, and press Run. The default starts the formal 5,120-image, 100-epoch training run from random initialization. Full precision is the safe default because AMP overflows this loss and can skip every update; the trainer now aborts if an epoch applies zero optimizer steps. It reconstructs the fixed center-nine pillar Raw crop every five epochs for visual observation only. Set `ACTION = "check_only"` to validate everything without training, or `ACTION = "build_data_only"` to prepare data only.

Completed checkpoints are copied into `weights`; full logs and the epoch 5/10/.../100 pillar reconstructions stay in `runs`. The pillar image does not affect loss, checkpoint selection, or training controls. The `runtime` subfolder is the locally pinned trainer required by this experiment.
