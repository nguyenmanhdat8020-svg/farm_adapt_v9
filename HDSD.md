# 🛰 Hướng dẫn sử dụng NUDT    https://vanmieu-tool.onrender.com/api/alerts/zalo-chatids
**Sentinel-2 → Random Forest Land Cover Classification**  
Phân loại lớp phủ mặt đất và phân tích biến động đô thị hóa tại khu vực Quảng Ninh

---

## 📦 Cấu trúc thư mục

```
nudt/
├── app.py            ← file chạy chính
├── model.pkl         ← mô hình Random Forest (đặt vào đây)
├── ref_2021.tif      ← ảnh tham chiếu 2021 6-band (đặt vào đây)
└── README.md         ← file này
```

> **Quan trọng:** `model.pkl` và `ref_2021.tif` phải nằm **cùng thư mục** với `app.py`.

---

## 🖥 Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu |
|---|---|
| Hệ điều hành | Windows 10/11 |
| RAM | 16 GB (khuyến nghị 32 GB) |
| Dung lượng ổ | 5–10 GB trống cho file tạm |
| Python | 3.9 – 3.11 |

---

## ⚙ Cài đặt (làm 1 lần duy nhất)

### Bước 1 — Cài Python

Tải Python 3.11 tại: https://www.python.org/downloads/

> ✅ Khi cài, tick vào **"Add Python to PATH"**

### Bước 2 — Tạo môi trường ảo

Mở **Command Prompt** (cmd), điều hướng vào thư mục tool:

```cmd
cd đường\dẫn\đến\nudt
```

Tạo môi trường ảo:

```cmd
python -m venv .venv
```

Kích hoạt môi trường ảo:

```cmd
.venv\Scripts\activate
```

> Bạn sẽ thấy `(.venv)` xuất hiện ở đầu dòng lệnh — đó là dấu hiệu thành công.

### Bước 3 — Cài thư viện

```cmd
pip install streamlit numpy pandas rasterio scipy scikit-image joblib matplotlib scikit-learn openpyxl folium streamlit-folium pillow geopandas
```

Quá trình cài đặt mất khoảng 5–10 phút tùy tốc độ mạng.

> **Lưu ý:** `folium`, `streamlit-folium`, `pillow`, và `geopandas` là các thư viện mới so với phiên bản trước — cần cài đầy đủ để các tính năng bản đồ tương tác và thống kê hành chính hoạt động đúng.

---

## 🚀 Cách chạy tool

**Mỗi lần sử dụng**, mở cmd, vào thư mục tool và chạy:

```cmd
cd đường\dẫn\đến\nudt
.venv\Scripts\activate
.venv\Scripts\streamlit run NUDT.py
```

Trình duyệt sẽ tự mở tại địa chỉ `http://localhost:8501`

---

## 📋 Quy trình sử dụng (5 bước)

Tool được thiết kế theo dạng **wizard 5 bước**, hiển thị thanh tiến trình ở đầu trang.

---

### Bước 1 — Chọn chế độ phân tích

| Chế độ | Mô tả | Kết quả |
|---|---|---|
| **Phân loại đơn** | 1 ảnh Sentinel-2 | Bản đồ phân loại + thống kê diện tích |
| **So sánh biến động** | 2 ảnh Sentinel-2 (2 thời điểm) | Bản đồ ×2 + phân tích biến động đô thị hóa + hotspot |

Nhấn nút chọn chế độ, sau đó nhấn **Tiếp theo** để sang bước 2.

---

### Bước 2 — Cài đặt đầu vào

**Đường dẫn ảnh Sentinel-2 (.SAFE)**

Nhập đường dẫn đến thư mục `.SAFE` của ảnh Sentinel-2 L2A. Trong chế độ so sánh, nhập cả 2 ảnh — tool sẽ tự động nhận diện ảnh cũ hơn và ảnh mới hơn dựa vào ngày chụp trong tên file.

Ví dụ:
```
E:\Data Sentinel2\S2B_MSIL2A_20250104T032039_N0511_R118_T48QYJ_20250104T132148.SAFE
```

> Thư mục phải có đuôi `.SAFE` và là ảnh **Level-2A** (chứa cấu trúc `GRANULE/*/IMG_DATA/R10m/` và `R20m/`)

**Thư mục làm việc tạm**

Nơi lưu file trung gian trong quá trình xử lý. Thư mục này sẽ **bị xóa tự động** sau khi xong.

- Cần khoảng **2–5 GB** dung lượng trống
- Nên dùng ổ D hoặc E thay vì ổ C nếu ổ C gần đầy

Ví dụ: `E:\Temp\nudt_work`

**Thư mục kết quả**

Nơi lưu toàn bộ kết quả cuối cùng. Ví dụ: `E:\Results\nudt_output`

**Cài đặt Hotspot** *(chỉ hiển thị ở chế độ so sánh)*

- **Kích thước cửa sổ phân tích (km × km):** vùng zoom quanh mỗi hotspot, có thể chọn từ 2–15 km, mặc định 5 km
- **Số hotspot:** số vùng biến động lớn nhất cần tìm, có thể chọn 1–6, mặc định 3

**Ranh giới hành chính (tùy chọn)**

Cung cấp file `.shp` ranh giới xã/huyện (cột tên đơn vị: `ten_xa`) để tool tự động tính thêm tab thống kê diện tích Urban/Vegetation/Water theo từng đơn vị hành chính. Bỏ trống nếu không cần.

Ví dụ: `E:\GIS\QuangNinh_phuong_xa.shp`

---

### Bước 3 — Xử lý mây

Tool phân tích lớp **SCL (Scene Classification Layer)** đi kèm với ảnh Sentinel-2 để phát hiện mây, bóng mây và tuyết trước khi phân loại.

**Phân tích SCL**

Nhấn nút **Phân tích SCL** cho từng ảnh. Tool sẽ hiển thị:
- Tỉ lệ mây che phủ tổng thể và trên vùng đất liền
- Bản đồ SCL trực quan (3 panel: SCL gốc / cloud mask / ngữ cảnh)
- Đánh giá có cần Gap Fill không

**Cài đặt nâng cao** *(mở rộng bằng expander)*

- **Gồm Cloud Shadow:** có/không đưa bóng mây (SCL class 3) vào mask, mặc định bật
- **Kernel dilation:** buffer mở rộng quanh viền mây (px), mặc định 5 px ≈ 100 m
- **Iterations:** số vòng lặp dilation, mặc định 2

**Gap Fill — lấp vùng mây bằng ảnh phụ**

Nếu ảnh có mây che phủ vùng đất liền, tool sẽ hướng dẫn tải ảnh bổ sung:

1. Truy cập [dataspace.copernicus.eu](https://dataspace.copernicus.eu) và tìm ảnh **cùng tile** với ảnh chính (tile ID có trong tên file, ví dụ `T48QYJ`)
2. Ưu tiên ảnh trong khoảng **±30 ngày** so với ảnh chính (cùng mùa, phổ tương đồng nhất)
3. Chọn ảnh **Level-2A**, tải về dạng `.SAFE`
4. Nhập đường dẫn ảnh phụ vào ô **Ảnh bổ sung #1**, nhấn **Chạy Gap Fill**
5. Nếu vẫn còn pixel chưa fill (ảnh phụ cũng có mây chồng), thêm ảnh phụ thứ 2, 3...

Tool fill tuần tự: ảnh phụ 1 fill trước, pixel còn tồn đọng chuyển sang ảnh phụ 2, v.v. Sau khi fill, tool hiển thị ảnh so sánh **trước / sau Gap Fill** (RGB tổ hợp B4–B3–B2).

> Có thể nhấn **Bỏ qua Gap Fill — Tiếp tục phân loại** nếu muốn dùng ảnh gốc có mây.

---

### Bước 4 — Phân loại (tự động)

Tool tự động chạy toàn bộ pipeline và hiển thị danh sách task theo thời gian thực. Thời gian xử lý khoảng **10–30 phút** tùy cấu hình máy.

**Các task trong pipeline:**

```
Load RF model
    ↓
Đọc cấu trúc .SAFE → Tìm các band B2/B3/B4/B8/B11/B12
    ↓
Resample B11/B12 từ 20m → 10m → Stack thành 6-band TIF
    ↓
Kiểm tra domain shift (KS test so với ref_2021.tif)
    ↓ nếu KS ≥ 0.10
PIF Normalization → Histogram Matching
    ↓
Tính 5 chỉ số quang phổ: NDVI, NDBI, NDWI, BSI, R11/8
    ↓
Stack thành 11-band TIF → Predict bằng Random Forest (batch)
    ↓
[Nếu 2 ảnh] Phân tích biến động → Hotspot → Excel tổng hợp
    ↓
Xuất kết quả → Xóa file tạm
```

---

### Bước 5 — Kết quả

Kết quả được tổ chức theo tab:

**Chế độ phân loại đơn (5 tab)**

| Tab | Nội dung |
|---|---|
| 🗺 Bản đồ | Bản đồ phân loại màu + thẻ thống kê diện tích (km² và %) theo 3 lớp |
| 🎯 Độ tin cậy | Bản đồ confidence map — pixel đỏ = model kém chắc chắn, xanh = rất chắc chắn |
| 🌐 Bản đồ Tương tác | Bản đồ Folium tương tác — zoom/pan, xem tọa độ, đo khoảng cách |
| 📊 Hành chính | Thống kê diện tích theo từng xã/huyện (nếu có shapefile) |
| 📥 Tải xuống | Tải trực tiếp tất cả file kết quả trong trình duyệt |

**Chế độ so sánh biến động (8 tab)**

| Tab | Nội dung |
|---|---|
| 🗺 Bản đồ năm 1 | Bản đồ + thống kê ảnh cũ hơn |
| 🗺 Bản đồ năm 2 | Bản đồ + thống kê ảnh mới hơn |
| 📈 Biến động | Biểu đồ diện tích, ma trận chuyển đổi, dịch chuyển trọng tâm, phân tích nguồn gốc đất đô thị |
| 🔴 Hotspot | Locator map + timeline của từng vùng biến động mạnh nhất |
| 🎯 Độ tin cậy | Confidence map cho cả 2 ảnh |
| 🌐 Bản đồ Tương tác | Bản đồ Folium tương tác |
| 📊 Hành chính | Thống kê hành chính cho cả 2 năm (nếu có shapefile) |
| 📥 Tải xuống | Tải toàn bộ file kết quả |

Tóm tắt biến động (km² urban mới, thay đổi tỉ lệ đô thị %) hiển thị ngay đầu trang kết quả.

---

## 📊 Kết quả đầu ra

### Chế độ phân loại đơn

```
output/
└── {năm}/
    ├── {năm}_classification.tif        ← bản đồ phân loại (GeoTIFF có georeference)
    ├── {năm}_classification.png        ← ảnh bản đồ màu
    ├── {năm}_statistics.xlsx           ← thống kê diện tích theo lớp
    ├── {năm}_confidence_map.png        ← bản đồ độ tin cậy phân loại
    ├── {năm}_admin_stats.xlsx          ← thống kê hành chính (nếu có shapefile)
    ├── {năm}_admin_chart.png           ← biểu đồ top 15 đơn vị hành chính (nếu có shapefile)
    └── {năm}_cloud_filled.tif          ← ảnh 6 bands đã Gap Fill (nếu đã chạy Gap Fill)
```

### Chế độ so sánh biến động

```
output/
├── {năm1}/                              ← kết quả ảnh 1 (như trên)
├── {năm2}/                              ← kết quả ảnh 2 (như trên)
└── urban_transformation/
    ├── 01_area_chart.png                ← biểu đồ diện tích theo lớp
    ├── 02_transition_matrix.png         ← ma trận chuyển đổi lớp đất (km²)
    ├── 03_centroid_shift.png            ← hướng dịch chuyển trọng tâm đô thị
    ├── 04_comparison_grid.png           ← so sánh 2 bản đồ song song
    ├── 05_land_loss_analysis.png        ← nguồn gốc đất đô thị hóa (phá rừng/lấn biển)
    ├── 06_hotspot_01_locator.png        ← vị trí hotspot #1 trên bản đồ toàn vùng
    ├── 06_hotspot_01_timeline.png       ← diễn biến hotspot #1 theo thời gian
    ├── 06_hotspot_02_locator.png        ← (tương tự cho hotspot #2, #3...)
    ├── 06_hotspot_02_timeline.png
    └── urban_analysis.xlsx              ← tổng hợp số liệu (3 sheet)
```

---

## 🗂 Lớp phân loại

Model Random Forest phân loại thành **5 lớp gốc**, sau đó tool gộp lại thành **3 lớp** để hiển thị và phân tích:

| Lớp hiển thị | Màu | Bao gồm |
|---|---|---|
| **Urban** | 🔴 Đỏ | Built-up (công trình xây dựng) + Road (đường giao thông) + Bare land (đất trống) |
| **Vegetation** | 🟢 Xanh lá | Thực vật / rừng |
| **Water** | 🔵 Xanh dương | Mặt nước / biển |

> **Lưu ý:** Lớp "Urban" trong tool không chỉ là "đô thị" theo nghĩa hành chính, mà là toàn bộ bề mặt phi thực vật, phi thủy vực có tín hiệu quang phổ đặc trưng của môi trường xây dựng và đất trống — phản ánh quá trình chuyển đổi sử dụng đất tổng thể.

---

## 🔴 Phân tích Hotspot

Tính năng tự động tìm các **vùng địa lý có mức độ đô thị hóa cao nhất** giữa 2 thời điểm:

- Tool chia ảnh thành các ô lưới theo kích thước cửa sổ đã chọn, đếm pixel chuyển sang Urban, chọn ra top N ô nhiều nhất
- **Locator map:** hiển thị vị trí các hotspot trên bản đồ toàn vùng, đánh số và tô sáng vùng có nhiều Urban mới nhất
- **Timeline:** phóng to vùng hotspot, so sánh trực quan giữa 2 thời điểm, highlight các pixel Urban mới bằng màu vàng
- Có thể điều chỉnh **kích thước cửa sổ** (2–15 km) và **số hotspot** (1–6) ở Bước 2

---

## ❓ Xử lý lỗi thường gặp

**Lỗi "Không tìm thấy IMG_DATA"**  
→ Kiểm tra đường dẫn `.SAFE` có đúng không; thư mục phải là **L2A** (không phải L1C)

**Lỗi "Thiếu model.pkl" hoặc "Thiếu ref_2021.tif"**  
→ Đặt 2 file này vào **cùng thư mục** với `app.py`; sidebar sẽ hiển thị trạng thái ✓/✗

**Tool chạy chậm hoặc báo hết RAM**  
→ Đóng các ứng dụng khác, đảm bảo còn ít nhất 8 GB RAM trống

**Lỗi khi cài thư viện rasterio trên Windows**  
→ Thử lệnh:
```cmd
pip install rasterio --find-links https://github.com/cgohlke/geospatial-wheels/releases
```

**Lỗi khi cài geopandas trên Windows**  
→ Thử cài theo thứ tự:
```cmd
pip install wheel
pip install shapely fiona pyproj
pip install geopandas
```

**Bản đồ tương tác không hiển thị**  
→ Kiểm tra đã cài `folium` và `streamlit-folium`. Cài lại: `pip install folium streamlit-folium`

**Tab "Hành chính" không có dữ liệu**  
→ Kiểm tra đã nhập đường dẫn shapefile ở Bước 2 và file `.shp` tồn tại; cột tên đơn vị hành chính phải là `ten_xa`

**Trình duyệt không tự mở**  
→ Mở thủ công tại: `http://localhost:8501`

**Kết quả phân loại bị sai (Road chiếm quá nhiều)**  
→ Kiểm tra version scikit-learn: `python -c "import sklearn; print(sklearn.__version__)"`  
→ Phải dùng đúng version đã train model. Cài lại: `pip install scikit-learn==1.7.2`

---

## 📁 Yêu cầu ảnh đầu vào

- Sentinel-2 **Level-2A** (đã hiệu chỉnh khí quyển — bắt buộc vì cần file SCL)
- Tile **T48QYJ** (khu vực Quảng Ninh)
- Ưu tiên **mùa khô** (tháng 10 – tháng 2 năm sau) để hạn chế mây
- Tải từ: https://dataspace.copernicus.eu

---

## 📌 Phạm vi nghiên cứu

Tool được phát triển và kiểm nghiệm trên dữ liệu tile **T48QYJ** bao gồm một phần tỉnh **Quảng Ninh**, Việt Nam — tập trung vào khu vực thành phố Hạ Long và các vùng ven biển lân cận.

---

*Tool được phát triển trong khuôn khổ đề tài NCKH sinh viên 2025–2026*  
*Tác giả: Nguyễn Mạnh Đạt — Hướng dẫn: TS. Nguyễn Bích Ngọc*
