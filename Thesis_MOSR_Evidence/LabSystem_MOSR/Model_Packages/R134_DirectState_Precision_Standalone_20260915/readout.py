import numpy as np,pandas as pd
import skimage.segmentation.morphsnakes as morphsnakes
from pathlib import Path
SESSION_TABLE=Path(__file__).parent/"validation/sessions.csv"


def measure_frame(core,scope,sequence,index,specification,raw,image,method):
    centers=np.asarray(specification['centers'],float)
    predicted=scope['session_prediction'](sequence,index,centers,float(specification['expected_signed_dx_px']))
    pitch=float(specification['pitch_px']);radius=float(specification['radius_px']);scale=float(specification['object_um_per_px'])
    mag=specification['magnification'];margin=int(np.ceil(.55*pitch));half=int(np.ceil(.46*pitch))
    x0=max(0,int(np.floor(np.min(predicted[:,1])))-margin);x1=min(raw.shape[1],int(np.ceil(np.max(predicted[:,1])))+margin+1)
    y0=max(0,int(np.floor(np.min(predicted[:,2])))-margin);y1=min(raw.shape[0],int(np.ceil(np.max(predicted[:,2])))+margin+1)
    crop=image[y0:y1,x0:x1];rows=[];boundaries=[];coarse=[];strengths=[]
    for pid,px,py in predicted:
        patch,pc,origin=core.crop_around(crop,(float(px-x0),float(py-y0)),half)
        scope['reset_curvature_cycle']()
        result=core.measure_inflection_lsc(patch,pc,radius,sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark')
        c=result.lsc;assert np.isfinite([c.cx,c.cy,c.radius]).all()
        pts=result.inflection_points_xy+np.array([origin[0]+x0,origin[1]+y0])
        rad=np.linalg.norm(result.inflection_points_xy-np.array([c.cx,c.cy]),axis=1)
        rows.append(dict(sequence=sequence,magnification=mag,frame_index=index,method=method,pillar_id=int(pid),predicted_x_px=float(px),predicted_y_px=float(py),lsc_center_x_px=c.cx+origin[0]+x0,lsc_center_y_px=c.cy+origin[1]+y0,lsc_radius_px=c.radius,gradient_strength_median=float(np.median(result.signed_gradient_strength)),object_um_per_px=scale,radial_residual_rms_px=float(np.sqrt(np.mean((rad-c.radius)**2))),radial_residual_max_abs_px=float(np.max(np.abs(rad-c.radius)))))
        boundaries.append(pts);coarse.append(result.coarse_contour_xy+np.array([origin[0]+x0,origin[1]+y0]));strengths.append(result.signed_gradient_strength)
    return pd.DataFrame(rows),dict(inflection_points=np.stack(boundaries),coarse_contours=np.stack(coarse),gradient_strength=np.stack(strengths),pillar_ids=predicted[:,0].astype(int),roi_bounds=np.array([x0,y0,x1,y1]))

def pair_table(centers,pairs,cfg,method):
    indexed=centers.set_index(['sequence','frame_index','pillar_id']);rows=[];pillar_rows=[]
    for item in pairs.itertuples(index=False):
        s=cfg['sequences'][item.sequence];scale=float(s['object_um_per_px']);nominal=float(s['nominal_step_um']);dx=[];dy=[]
        for pid,_,_ in s['centers']:
            a=indexed.loc[(item.sequence,item.start_frame_index,int(pid))];b=indexed.loc[(item.sequence,item.end_frame_index,int(pid))]
            vx=(float(b.lsc_center_x_px)-float(a.lsc_center_x_px))*scale;vy=(float(b.lsc_center_y_px)-float(a.lsc_center_y_px))*scale
            dx.append(vx);dy.append(vy)
            pillar_rows.append(dict(sequence=item.sequence,start_frame_index=item.start_frame_index,end_frame_index=item.end_frame_index,method=method,pillar_id=int(pid),dx_um=vx,dy_um=vy,radius_change_nm=float(b.lsc_radius_px-a.lsc_radius_px)*scale*1000))
        mx,my=float(np.median(dx)),float(np.median(dy))
        rows.append(dict(sequence=item.sequence,magnification=s['magnification'],pair_rank_raw_locked=item.pair_rank_raw_locked,start_frame_index=item.start_frame_index,end_frame_index=item.end_frame_index,method=method,nominal_step_um=nominal,aggregate_dx_um=mx,aggregate_dy_um=my,measured_step_um=abs(mx),nominal_abs_error_nm=abs(abs(mx)-nominal)*1000,within_grid_sd_nm=float(np.std(dx,ddof=1)*1000),cross_axis_abs_nm=abs(my)*1000))
    return pd.DataFrame(rows),pd.DataFrame(pillar_rows)

def session_prediction(
    sequence: str,
    frame_index: int,
    base_centers: np.ndarray,
    expected_dx_px: float,
) -> np.ndarray:
    sessions = pd.read_csv(SESSION_TABLE)
    candidates = sessions[
        (sessions["sequence"] == sequence)
        & (sessions["start_frame_index"] <= frame_index)
        & (sessions["end_frame_index"] >= frame_index)
    ]
    if len(candidates) != 1:
        raise ValueError(f"frame {frame_index} in {sequence} has {len(candidates)} session records")
    session = candidates.iloc[0]
    delta_index = int(frame_index - int(session["start_frame_index"]))
    predicted = base_centers.copy()
    predicted[:, 1] += float(session["anchor_offset_x_px"]) + delta_index * float(expected_dx_px)
    predicted[:, 2] += float(session["anchor_offset_y_px"])
    return predicted

def summarize_pairs(per_pair: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (sequence, method), group in per_pair.groupby(["sequence", "method"], sort=False):
        rows.append(
            {
                "scope": "per_sequence",
                "sequence": sequence,
                "magnification": group["magnification"].iloc[0],
                "method": method,
                "n_pairs": len(group),
                "step_sd_nm": float(np.std(group["measured_step_um"], ddof=1) * 1000.0),
                "mean_nominal_abs_error_nm": float(np.mean(group["nominal_abs_error_nm"])),
                "median_within_grid_sd_nm": float(np.median(group["within_grid_sd_nm"])),
                "median_cross_axis_abs_nm": float(np.median(group["cross_axis_abs_nm"])),
            }
        )
    for method, group in per_pair.groupby("method", sort=False):
        rows.append(
            {
                "scope": "all_four_sequences",
                "sequence": "combined",
                "magnification": "20x+50x",
                "method": method,
                "n_pairs": len(group),
                "step_sd_nm": float(
                    np.mean(
                        [
                            np.std(sequence_group["measured_step_um"], ddof=1) * 1000.0
                            for _, sequence_group in group.groupby("sequence")
                        ]
                    )
                ),
                "mean_nominal_abs_error_nm": float(np.mean(group["nominal_abs_error_nm"])),
                "median_within_grid_sd_nm": float(np.median(group["within_grid_sd_nm"])),
                "median_cross_axis_abs_nm": float(np.median(group["cross_axis_abs_nm"])),
            }
        )
    return pd.DataFrame(rows)

def reset_curvature_cycle() -> None:
    morphsnakes._curvop = morphsnakes._fcycle([
        lambda values: morphsnakes.sup_inf(morphsnakes.inf_sup(values)),
        lambda values: morphsnakes.inf_sup(morphsnakes.sup_inf(values)),
    ])