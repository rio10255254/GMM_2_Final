# R96 data source

R96 reads the existing audited procedural package containing 1,250 scenes and
5,000 observations.  The large array payload is not duplicated here.  Its
content hash and source location are locked in `config/experiment_design.json`.

Only procedural images, masks and exact hidden-stage replay are used for
training.  Real 5x, 20x, 50x, HS100MG and SEM images remain preview or external
validation inputs and are never training labels or geometry.

R96 changes how the existing exact labels are learned: control maps are
balanced per channel, sparse local targets receive continuous support-aware
supervision, and each private branch is protected during late joint training.
