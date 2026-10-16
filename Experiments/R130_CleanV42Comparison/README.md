# R130 Clean V42 comparison

One32epoch fresh V42 on the same512source-only parents as R129, four parents per update. R129 weights/data/results are read-only. This is a practical comparison, not matched initialization or a claim of unseen generalization. Shared historical optical calibration remains a limitation. No legacy neural weights/teacher/realSEM targets are used. Architecture retains V42 encoder-decoder, AA, direction-aware boundary head, Raw anchor and quality gate.

Local branch codex/r130-clean-v42. No external issue/message requested. See config/training.json and reports/R130_RESULTS.md for actual execution.

## Completed

32epochs and all real comparisons are complete. [Results and real-image figures](reports/R130_RESULTS.md) show mixed tradeoffs, not automatic adoption. Model: runs/v42_clean/checkpoints/step04096.pth. Single-image entry: scripts/infer_image.py --input IMAGE --output NEW.png. The completed run should not be resumed; further training requires a distinct plan/run. R129 remains unchanged.
