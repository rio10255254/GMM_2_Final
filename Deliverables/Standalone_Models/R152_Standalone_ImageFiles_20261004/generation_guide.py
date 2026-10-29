"""R152影像重新生成說明

一、這次補入什麼
generate_data.py是可直接執行的完整入口。generation/包含清楚場景生成、
固定參數、25顆PSF卷積、位移與光度變化、幾何標記生成，以及原始程式備份。
這批資料當初是Python製作，因此附的是實際Python原始程式，不需要MATLAB。

二、如何重做
直接執行generate_data.py；會從固定種子重建512個訓練、128個開發、128個測試場景。
每個場景有4組視圖，共3072張清楚TIFF、3072張無噪模糊TIFF、3072張幾何TIFF。
新資料放在outputs/generated_data。完成後，執行train.py並附上
--data-dir outputs/generated_data即可使用它。--from-scratch可同時完整重做兩階段訓練。
所有相對路徑都從獨立包位置定位，從別的工作目錄開啟也可以。
如果正式data資料夾已不在，可用--output-dir data直接重建；已有資料時不默默覆寫。

三、重新生成的細節
清楚影像先在8倍細格上生成，再保留4倍清楚場景。4組視圖各自加入原設定的
0.25～8像素位移與亮度／對比變化，使用原PSF插值、卷積與面積平均，最後保存原來
float16捨入後轉float32的值。這個捨入順序不能省略，否則就不是原版訓練資料。
模糊TIFF不預先加噪；正式訓練仍依原種子、資料組別、輪次、場景及視圖加入噪聲
並轉成八位元輸入。所選PSF編號也按原規則重新產生，沒有另抽一套新的分配。
每個場景的固定參數、位移、PSF編號、噪聲、清楚／模糊及幾何值都會核對原版。

四、結果如何看
generation_progress.py顯示完成數。只有生成並核對完全部資料後才會有
generation_result.py與data_index.py。資料夾內沒有訓練NPZ或PNG。
--verify-only會再次打開所有TIFF並核對實際像素。
若中斷，使用--resume；已完成影像會重新核對，未完成的場景才重新生成。
如果已有影像與原版不一致，程式會指出場景並停止，避免覆蓋或帶錯資料進訓練。

五、版本與速度
已驗證numpy 1.26.4、scipy 1.13.1、Pillow 10.4.0，均可從generation/recipe.py查看。
不同版本可能改變最後幾位數值或TIFF壓縮內容；程式會核對像素，不能通過就不算完成。
預設4個場景同時製作，記憶體有限可以使用--workers 1。生成只使用CPU。
原始程式曾生成的舊高斯模糊及第二視圖不被R152使用，因此本入口只重做R152所需
的起始清楚場景；保留完全相同的取樣位置、計算與捨入，未讀取附帶TIFF來充當生成。

六、原始程式的角色
original_sources/r125_geometry_helper.py：原始形狀與幾何計算。
original_sources/r128_scene_generation.py：原始場景、光度、種子與細格影像。
original_sources/r128_build_all.py：原始768場景建置流程。
original_sources/r148_physical_views.py：原始4視圖位移、光度與實測PSF模糊。
original_sources/r148v2_geometry_labels.py：原始幾何標記計算。
五份原始檔完整保留，方便追查。已經能直接操作的版本是generate_data.py，
不需要讀者自行修改當初程式的路徑或補寫生成方式。
"""


if __name__=='__main__':
    print(__doc__)
