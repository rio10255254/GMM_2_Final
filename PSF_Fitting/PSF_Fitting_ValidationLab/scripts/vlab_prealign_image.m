function align_info = vlab_prealign_image(img_cpu, prealign)
img_grad_norm = normlz(imgradient(img_cpu));
gt_crop = prealign.gt_grad_norm(prealign.crop_rows, prealign.crop_cols);

if isfield(prealign, 'search_values')
    search_values = prealign.search_values;
else
    search_values = -prealign.search_radius:prealign.search_step:prealign.search_radius;
end

best_score = -Inf;
best_shift = [0, 0];
for dy = search_values
    for dx = search_values
        shifted_grad = vlab_translate_image(img_grad_norm, dy, dx);
        shifted_crop = shifted_grad(prealign.crop_rows, prealign.crop_cols);
        score = local_ncc(gt_crop, shifted_crop);
        if score > best_score
            best_score = score;
            best_shift = [dy, dx];
        end
    end
end

align_info = struct();
align_info.shift_y = best_shift(1);
align_info.shift_x = best_shift(2);
align_info.score = best_score;
align_info.aligned_image = vlab_translate_image(img_cpu, best_shift(1), best_shift(2));
end

function score = local_ncc(a, b)
a = double(a(:));
b = double(b(:));
a = a - mean(a);
b = b - mean(b);
score = sum(a .* b) / (norm(a) * norm(b) + eps);
end
