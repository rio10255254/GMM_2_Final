function diameter_px = center_9pillar_cd_pixels(cd_nm, magnification, camera_pixel_um)
%CENTER_9PILLAR_CD_PIXELS Convert SEM diameters to object-plane image pixels.
arguments
    cd_nm (:,:) double {mustBePositive}
    magnification (1,1) double {mustBePositive}
    camera_pixel_um (1,1) double {mustBePositive} = 3.45
end
object_pixel_um = camera_pixel_um / magnification;
diameter_px = (cd_nm / 1000) / object_pixel_um;
end
