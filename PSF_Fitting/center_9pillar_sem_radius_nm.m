function radius_nm = center_9pillar_sem_radius_nm()
%CENTER_9PILLAR_SEM_RADIUS_NM SEM-fitted pillar radii in physical orientation.
% Source: via_pilar.xlsx, sheet "SEM data", range J8:L10.
% Rows are top-to-bottom; columns are left-to-right.
% The bottom-left entry is the pillar nearest the physical sample center.
radius_nm = [
    1310.1071872032830, 1310.0081858573494, 1321.1577900710545
    1310.2142785890380, 1304.3597689145038, 1329.3068965988240
    1310.8899993469824, 1299.3758269507834, 1338.3982848246214];
end
