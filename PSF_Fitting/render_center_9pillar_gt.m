function [gt, metadata] = render_center_9pillar_gt(image_size, centers, cd_nm, magnification, camera_pixel_um, supersample)
%RENDER_CENTER_9PILLAR_GT Render anti-aliased disks using the measured SEM CDs.
arguments
    image_size (1,2) double {mustBeInteger, mustBePositive}
    centers (9,2) double {mustBeFinite}
    cd_nm (3,3) double {mustBePositive}
    magnification (1,1) double {mustBePositive}
    camera_pixel_um (1,1) double {mustBePositive} = 3.45
    supersample (1,1) double {mustBeInteger, mustBePositive} = 8
end

diameter_px = center_9pillar_cd_pixels(cd_nm, magnification, camera_pixel_um);
diameter_row_major = reshape(diameter_px.', [], 1);

high_h = image_size(1) * supersample;
high_w = image_size(2) * supersample;
x_coords = ((1:high_w) - 0.5) / supersample + 0.5;
y_coords = ((1:high_h) - 0.5) / supersample + 0.5;
[x_grid, y_grid] = meshgrid(x_coords, y_coords);
gt_high = zeros(high_h, high_w, 'double');

for pillar_idx = 1:9
    radius = diameter_row_major(pillar_idx) / 2;
    disk = hypot(x_grid - centers(pillar_idx, 1), y_grid - centers(pillar_idx, 2)) <= radius;
    gt_high(disk) = 1;
end

gt = imresize(gt_high, image_size, 'box');
metadata = struct();
metadata.cd_nm_by_display_row = cd_nm;
metadata.diameter_px_by_display_row = diameter_px;
metadata.sample_center_cd_nm = cd_nm(3, 1);
metadata.sample_center_xy = centers(7, :);
metadata.object_pixel_um = camera_pixel_um / magnification;
metadata.camera_pixel_um = camera_pixel_um;
metadata.magnification = magnification;
metadata.orientation = 'rows top-to-bottom, columns left-to-right; bottom-left is sample center';
end
