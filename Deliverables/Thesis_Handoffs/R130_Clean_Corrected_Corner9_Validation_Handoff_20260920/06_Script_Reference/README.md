# 程式參考

execution_source 保存原執行程式，不重新訓練、不改模型、不更改量測。independent_result_review.py 是執行後另行查核；build_validation_handoff.py 是這次封裝及補齊逐顆數據的程式。

這些程式保留實際工作環境的路徑與相依套件，供讀者檢查公式與來源；不是解壓後可直接執行全部訓練的一鍵環境。verify_package.py 則可獨立核對本包內容。
