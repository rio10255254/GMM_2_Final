# Live validation images

These three copied real microscope frames are reconstruction-only observations.
They never enter a dataset loader, loss, early stopping rule, learning-rate rule,
or checkpoint ranking.  The trainer writes raw/reconstruction comparisons every
five epochs so visual failure can be audited after the run.

