# Training

`train_r87.py` is the formal trainer.  It has no checkpoint or resume input.
The easiest manual entry is `scripts/launch_r87.py`: change `ACTION` and press
Run.  A formal run writes a scratch audit before the first batch and updates the
active-run marker after every epoch.

