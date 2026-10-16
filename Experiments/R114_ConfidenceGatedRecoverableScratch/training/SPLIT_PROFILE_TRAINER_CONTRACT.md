# R114 split-profile trainer parameter contract

The model's `profile_parameters()` method is the only source of truth for the
profile optimizer.  That set contains the shared renderer backbone and the
four bounded profile heads, and excludes controller, width-action, and
shift-action heads.

The trainer validates this contract at optimizer construction and again before
every staged step.  The same check applies to `profile` objectives and to the
`profile_guard` step in `joint_refinement`; alternating geometry guards retain
their independent width/shift optimizer sets.

`test_split_profile_trainer_parameter_contract.py` provides executable checks
for exact set equality, complete gradient reachability over the profile-stage
objective cycle, one diagnostic update of every contracted profile parameter,
no update outside that contract, and the joint-stage shared-backbone path.

These checks do not alter the scratch-only rule, stage order, objective
alternation, or scene-weighted logical-batch/microbatch behavior.
