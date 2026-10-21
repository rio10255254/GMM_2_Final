function cd_nm = center_9pillar_sem_cd()
%CENTER_9PILLAR_SEM_CD Convert the measured SEM radii to pillar diameters.
% Rows are displayed top-to-bottom; columns are left-to-right.
% The bottom-left entry is the sample-center pillar.
cd_nm = 2 * center_9pillar_sem_radius_nm();
end
