# Công cụ Quản lý Sử dụng Đất — Xóm Hạ Hồi
Đồ án 2 | Land Use | Phường Hàng Bài · Hoàn Kiếm · Hà Nội

## Cài đặt & Chạy

### Bước 1 — Cài thư viện
```bash
pip install flask anthropic
```
hoặc:
```bash
pip install -r requirements.txt
```

### Bước 2 — Set API key (cho Tầng 3 AI)
**Windows (CMD):**
```cmd
set ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxx
```
**Mac / Linux:**
```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxx
```
> Tầng 1 (bản đồ) và Dashboard vẫn chạy được khi không có key.

### Bước 3 — Chạy server
```bash
python app.py
```

### Bước 4 — Mở trình duyệt
```
http://localhost:5000
http://localhost:5000/baocao 
(Đây là đường dẫn đến web mà người dân có thể tiến hành phản hồi các vấn đề)
```

---

## Cấu trúc

```
hahoi_tool/
├── app.py            ← Server Flask + toàn bộ frontend (1 file duy nhất)
├── requirements.txt  ← Thư viện cần cài
└── README.md
```

## 3 Tầng chức năng

| Tầng | Tab | Mô tả |
|------|-----|-------|
| Tầng 1 | Bản đồ 2D | Canvas bản đồ ô đất, tô màu 7 nhóm, lớp nhiệt xung đột, popup click |
| Tầng 1 | Dashboard | Biểu đồ cơ cấu SDĐ, ma trận cộng sinh/xung đột có màu |
| Tầng 3 | Kịch bản AI | Rule engine + Claude API phân tích tiếng Việt |

## Dữ liệu sử dụng

- 27 ô đất mẫu phân bố trên canvas
- Ma trận 10 cặp cộng sinh/xung đột từ khảo sát thực địa
- 7 nhóm chức năng: LT · TM · CC · HT · SX · CX · DC
- Thang điểm C1–C7 (−2 đến +2)

## Mở rộng sau này

- Thay PLOTS bằng dữ liệu GeoJSON thực từ ArcGIS
- Thêm Tầng 2 (Supabase) cho nhập liệu thực địa
- Tích hợp model 3D SketchUp qua CesiumJS
