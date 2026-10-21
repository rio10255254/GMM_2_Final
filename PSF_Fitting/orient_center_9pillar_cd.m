function oriented_cd_nm = orient_center_9pillar_cd(cd_nm, image_corner)
%ORIENT_CENTER_9PILLAR_CD Rotate physical SEM layout into image orientation.
arguments
    cd_nm (3,3) double {mustBePositive}
    image_corner (1,1) string
end
switch image_corner
    case "bottom-left"
        oriented_cd_nm = cd_nm;
    case "top-left"
        oriented_cd_nm = rot90(cd_nm, -1);
    case "top-right"
        oriented_cd_nm = rot90(cd_nm, 2);
    case "bottom-right"
        oriented_cd_nm = rot90(cd_nm, 1);
    otherwise
        error('center9:UnsupportedCorner', 'Unsupported corner: %s', image_corner);
end
end
