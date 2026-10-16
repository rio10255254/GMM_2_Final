# R130 manifest

Profile: local model/trainer with immutable shared data, not another bulk data copy. Same source-only512/128/128 splits;32epochs,onefreshseed,16384parents,4096updates. V42 original model source retained alongside arithmetic-equivalent deterministic adaptation. No learned tensor is imported from legacy V42/V41 or R129. Fixed PSF data shared withR129 are separately recorded, not independent new calibration.

Completed32epochs:4096uniqueupdates,4098actualcalls due2exact recovery replays. All201realimages/1809LSCcenters,540scheduledSEMmeasurements; independent audit, SEMpublicreplay and matched runtime benchmark saved. Recovery wrapper changes only status IO and is separately recorded; no old/frozen hash rebaseline. No R129 change or promotion.
