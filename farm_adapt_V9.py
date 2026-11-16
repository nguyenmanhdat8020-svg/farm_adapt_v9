# -*- coding: utf-8 -*-
"""
FARM ADAPT — Farm Adaptation and Rotation Planning System  (v0.9 · NASA Space Apps 2026)
Tác giả: Nguyễn Mai Chi · Nguyễn Mạnh Đạt (email liên hệ đặt trong .env: FARM_AUTHOR1_EMAIL, FARM_AUTHOR2_EMAIL)
v0.9.4: ma trận luân canh chỉ để xem (bỏ bấm ô để cấm K4); chế độ chuỗi có bảng điểm cho từng bước của chuỗi tốt nhất.
v0.9.3: SONG NGỮ Việt – Anh (nút VI/EN; từ điển I18N_EN trước phần API, thuật ngữ nông học – GIS chuẩn; số theo định dạng của ngôn ngữ).
v0.9.2: ẩn thẻ "So sánh 3 cột" ở trang chủ, phóng to phần so sánh kịch bản; tên + email tác giả đọc từ .env dạng "Họ tên - email".
v0.9.1: bỏ thẻ so sánh 3 cột (giữ kịch bản kéo thanh, chạy cho cả vụ tới và chuỗi luân canh); thẻ "Nhóm tác giả" ở thanh bên và trang Nguồn.
v0.9: HAI BÀI TOÁN — (1) đề xuất cây cho VỤ TỚI: V(c) = S × M(cây trước, c); (2) đề xuất CHUỖI LUÂN CANH trong [ngày bắt đầu, ngày kết thúc]:
      Score(P) = (1/T)[S(c1) + Σ S(ct)·M(c_{t−1},ct)], M = 1 + E/100 (Mudare et al. 2025). Thêm F1 giá trị kinh tế (G = P × A × Y_base),
      K3 (không trồng một cây 2 vụ liền), K4 (cặp cấm), trang ma trận luân canh, kịch bản 2^n so sánh 3 cột baseline · Δ+ · Δ−.
v0.8: TRANG CHỦ = GIÁM SÁT & CẢNH BÁO (GiamSat.md: bản đồ NASA POWER A1–A3/B1 có thanh thời gian, 2 phương pháp × 3 mức cảnh báo, cấu hình của người dùng)
      + SO SÁNH KỊCH BẢN cho vụ tới; khai báo vụ kèm cây trồng & chọn ngày trên lịch; theo BaiToan1 chuẩn (A3 Kt ≥0,60/0,50/0,35, C5 bảng CEC, K1 sương giá, K2).
v0.7: BÀI TOÁN 1 — "Cây này có phù hợp để trồng vào VỤ TỚI trên thửa này không?" (SMCA 12 tiêu chí, BaiToan1.md)
  • Người dùng khai báo các vụ (ngày bắt đầu + số ngày) → công cụ xác định vụ hiện tại và VỤ CẦN RA QUYẾT ĐỊNH.
  • Crop Requirement Database (CRD) mới: 4 cây có dữ liệu chắc chắn (lúa mì đông, cao lương, ngô, đậu tương) + đất nghỉ, có nguồn từng ô.
  • 12 tiêu chí A1–A3, B1, C1–C6, D1, E1 quy về 0–1 (hàm hình thang, phân hạng Sys, hàm năng suất–nước FAO); K1 là điều kiện loại trừ.
  • Người dùng chọn tiêu chí nào được dùng và trọng số từng tiêu chí (hoặc bộ ưu tiên theo tài liệu); tiêu chí thiếu dữ liệu tự bỏ & chia lại trọng số.
  • Kịch bản thời tiết ΔT, ΔP, ΔKt, Δθ so với trung bình nhiều năm hoặc năm gần nhất.
  • Dữ liệu tự lấy: NASA POWER (T2M, mưa, GWETROOT, ALLSKY_KT), GPM IMERG, SSURGO (Soil Data Access), SoilGrids, SRTM; SMAP qua CSV.

MỘT FILE DUY NHẤT: Flask + giao diện HTML nhúng + bộ máy đánh giá + trợ lý AI. Luồng 7 bước:
  1. Ruộng & chế độ tưới  2. Bài toán & mùa vụ  3. Khí hậu  4. Đất & địa hình  5. Tiêu chí & trọng số  6. Ma trận luân canh  7. Kết quả  (+ Thư viện cây trồng)

Nguyên tắc: Python TÍNH, AI chỉ DIỄN GIẢI (số AI viết ra được đối chiếu lại). Công cụ hỗ trợ, KHÔNG thay thế phán đoán của nông dân và chuyên gia địa phương.

Chạy:
    pip install flask python-dotenv truststore --break-system-packages
    # .env (tùy chọn): EARTHDATA_TOKEN=... (mưa GPM IMERG)  GEMINI_API_KEY=... / GROQ_API_KEY=... / OPENAI_API_KEY=... / ANTHROPIC_API_KEY=...
    # .env (tùy chọn, email nhóm tác giả hiển thị trên trang Nguồn): FARM_AUTHOR1_EMAIL=...  FARM_AUTHOR2_EMAIL=...
    python farm_adapt_V9.py            →  http://localhost:5000
Biến môi trường tùy chọn: PORT, FARM_DATA_DIR, POWER_YEARS (mặc định 15), FARM_DEMO_FALLBACK (1 = cho phép khí hậu MÔ PHỎNG khi không gọi được NASA POWER).
Sửa / bổ sung yêu cầu cây trồng: data/crops.json (ghi đè theo id và theo khóa tiêu chí).
"""
import os, io, re, csv, json, math, time, uuid, bisect, threading, random, statistics
import datetime as dt
import urllib.request, urllib.parse, urllib.error
from flask import Flask, request, jsonify, Response, g, has_request_context

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), encoding="utf-8")   # .env cạnh file, dù chạy từ thư mục nào
    load_dotenv()
except ImportError:
    pass

try:                       # Python trên Windows có thể không tin chuỗi chứng chỉ của vài máy chủ (vd. modis.ornl.gov);
    import truststore      # truststore cho Python dùng kho chứng chỉ của hệ điều hành, giống trình duyệt.  pip install truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

APP_NAME   = "FARM ADAPT"
APP_FULL   = "Farm Adaptation and Rotation Planning System"
APP_SLOGAN = "From NASA Data to Smarter Farming Decisions."
VERSION    = "0.9.4"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.environ.get("FARM_DATA_DIR", os.path.join(_BASE_DIR, "data"))
CACHE_DIR = os.path.join(DATA_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
FARMS_PATH = os.path.join(DATA_DIR, "farms.json")

POWER_YEARS   = max(8, min(30, int(os.environ.get("POWER_YEARS", "15") or 15)))
POWER_TIMEOUT = int(os.environ.get("POWER_TIMEOUT_S", "90") or 90)
DEMO_FALLBACK = os.environ.get("FARM_DEMO_FALLBACK", "1") != "0"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
_LOCK = threading.RLock()

# ───────────────────────── tiện ích số học ─────────────────────────
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x

def mean(a):
    a = list(a)
    return sum(a) / len(a) if a else 0.0

def num(x, default=None):
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default

def pctl(vals, q):
    s = sorted(vals)
    if not s:
        return 0.0
    k = q * (len(s) - 1)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return s[lo] + (s[hi] - s[lo]) * (k - lo)

def stdev(a):
    a = list(a)
    return statistics.pstdev(a) if len(a) > 1 else 0.0

def corr(x, y):
    n = min(len(x), len(y))
    if n < 4:
        return None
    x, y = x[:n], y[:n]
    mx, my = mean(x), mean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)

def theil_sen(xs, ys):
    """Độ dốc Theil–Sen + p-value Mann–Kendall (xấp xỉ chuẩn). Bền vững với ngoại lai — hợp với chuỗi khí hậu ngắn."""
    n = len(xs)
    if n < 5:
        return {"slope": 0.0, "p": 1.0}
    slopes, S = [], 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = xs[j] - xs[i]
            if dx:
                slopes.append((ys[j] - ys[i]) / dx)
            d = ys[j] - ys[i]
            S += (d > 0) - (d < 0)
    var = n * (n - 1) * (2 * n + 5) / 18.0
    z = 0.0 if S == 0 else (S - (1 if S > 0 else -1)) / math.sqrt(var)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"slope": statistics.median(slopes) if slopes else 0.0, "p": p}
# ───────────────────────── CƠ SỞ DỮ LIỆU YÊU CẦU CÂY TRỒNG (Crop Requirement Database – CRD) ─────────────────────────
# Nguồn: file CRD.md của nhóm (FAO ECOCROP, FAO Crop Information, FAO-56, bảng phân hạng kiểu Sys et al. 1993 / ALUES,
# lịch mùa vụ Kansas của K-State & USDA NASS, Panagos et al. 2015). Dạng: tối ưu (opt) / chịu đựng (tol).
# Ghi đè / bổ sung bằng data/crops.json (mỗi phần tử {"id": "maize", "C3": {"opt": [5, 7], "tol": [4.5, 8.5]}, ...} — ghi đè theo khóa cấp 1).
GROUP_VI = {"cereal": "Ngũ cốc", "legume": "Họ đậu"}

CRD_SOURCES = {
    "EC-M": ("FAO ECOCROP – Zea mays", "https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=2175"),
    "EC-S": ("FAO ECOCROP – Sorghum bicolor", "https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=48747"),
    "EC-G": ("FAO ECOCROP – Glycine max", "https://ecocrop.apps.fao.org/ecocrop/srv/en/dataSheet?id=1150"),
    "EC-W": ("Số liệu ECOCROP cho Triticum aestivum, trích lại tại Useful Tropical Plants (không mở được trang ECOCROP gốc)", "https://tropical.theferns.info/viewtropical.php?id=Triticum+aestivum"),
    "FAO-W": ("FAO Crop Information – Wheat", "https://www.fao.org/land-water/databases-and-software/crop-information/wheat/en/"),
    "FAO-WT": ("FAO – Bread wheat: improvement and production, ch. 1", "https://www.fao.org/3/y4011e/y4011e04.htm"),
    "FAO-S": ("FAO Crop Information – Sorghum", "https://www.fao.org/land-water/databases-and-software/crop-information/sorghum/fr/"),
    "FAO-M": ("FAO Crop Information – Maize", "https://www.fao.org/land-water/databases-and-software/crop-information/maize/en/"),
    "FAO-G": ("FAO Crop Information – Soybean", "https://www.fao.org/land-water/databases-and-software/crop-information/soybean/ru/"),
    "FAO-56": ("FAO Irrigation and Drainage Paper 56, Table 22", "https://www.fao.org/4/x0490e/x0490e0e.htm"),
    "FAO-66": ("FAO Irrigation & Drainage Paper 66, Bảng 1 (Ky mùa vụ, lấy từ Paper 33)", "https://fao.org/4/i2800e/i2800e02.pdf"),
    "Sys-M": ("Bảng yêu cầu đất đai cho ngô nhờ mưa, kiểu Sys et al. (1993)", "https://scholars.direct/Articles/soil-and-water-science/jsws-6-030-table5.html"),
    "MUDARE": ("Mudare et al. (2025), Crop rotations synergize yield, nutrition, and revenue: a meta-analysis, Nature Communications — Supplementary Table 5", "https://www.nature.com/ncomms/"),
    "KSU-1": ("K-State eUpdate – Expected number of days to harvest summer crops in Kansas (TB 2011–2015)", "https://eupdate.agronomy.ksu.edu/article/expected-number-of-days-to-harvest-summer-crops-in-kansas-596-4"),
    "KSU-2": ("K-State eUpdate – Expected number of days to plant summer crops in Kansas (USDA NASS 2010)", "https://eupdate.agronomy.ksu.edu/article/expected-number-of-days-to-plant-summer-crops-in-kansas-501-6"),
    "AgM": ("K-State AgManager – Planting days (USDA NASS 2010)", "https://agmanager.info/sites/default/files/PlantingDays.pdf"),
    "NASS-KS": ("USDA NASS Kansas Crop Progress, tuần kết thúc 11/7/2010", "https://data.nass.usda.gov/Statistics_by_State/Kansas/Publications/Crop_Progress_and_Condition/2010/wkly0711.pdf"),
    "ISWS-W": ("Illinois State Water Survey – Alternative Crops: Triticum aestivum", "https://isws.illinois.edu/data/altcrops/cropreq.asp?crop=886"),
    "ALUES": ("Yen et al. (2006), LUSET User's Guide, IRRI (dựa trên Sys et al. 1993) – dữ liệu trong gói R ALUES", "https://cran.r-project.org/package=ALUES"),
    "PAN": ("Panagos et al. (2015), Land Use Policy 48, Bảng 1 – hệ số C hiệu chỉnh cho châu Âu", "https://doi.org/10.1016/j.landusepol.2015.05.021"),
}

TEXTURE_GROUP = {"sand": "light", "loamy sand": "light", "sandy loam": "light",
                 "loam": "medium", "silt loam": "medium", "silt": "medium", "sandy clay loam": "medium",
                 "clay loam": "heavy", "silty clay loam": "heavy", "sandy clay": "heavy", "silty clay": "heavy", "clay": "heavy"}
TEXTURE_GROUP_VI = {"light": "nhẹ", "medium": "trung bình", "heavy": "nặng"}
DRAINAGE = [("excessive", "Quá mức", 1.0), ("somewhat_excessive", "Hơi quá mức", 1.0), ("well", "Tốt", 1.0), ("moderately_well", "Khá tốt", 0.75),
            ("somewhat_poor", "Hơi kém", 0.5), ("poor", "Kém", 0.25), ("very_poor", "Rất kém", 0.0)]
DRAIN_SCORE = {k: s for k, _, s in DRAINAGE}
DRAIN_VI = {k: v for k, v, _ in DRAINAGE}
SSURGO_DRAIN = {"excessively drained": "excessive", "somewhat excessively drained": "somewhat_excessive", "well drained": "well",
                "moderately well drained": "moderately_well", "somewhat poorly drained": "somewhat_poor", "poorly drained": "poor",
                "very poorly drained": "very_poor"}
SYS_SCORE = {"S1": 1.0, "S2": 0.75, "S3": 0.5, "N": 0.0}
# A3: Kt trung bình trong vụ → mức ECOCROP (BaiToan1 chuẩn): Rất sáng ≥ 0,60 · Trời quang 0,50–0,60 · Nhiều mây 0,35–0,50 · Bóng râm < 0,35
KT_CLASSES = [(0.60, "vbright", "Rất sáng"), (0.50, "clear", "Trời quang"), (0.35, "cloudy", "Nhiều mây"), (-1.0, "shade", "Bóng râm")]
# C5: bảng CEC (cmolc/kg) → điểm, theo nhóm cây (BaiToan1 chuẩn)
C5_TABLE = {"demanding": [(24, 1.0, "> 24"), (16, 0.75, "16–24"), (10, 0.5, "10–16"), (-1, 0.0, "< 10")],
            "tolerant": [(24, 1.0, "> 24"), (16, 1.0, "16–24"), (10, 0.75, "10–16"), (-1, 0.5, "< 10")]}
C5_GROUP_VI = {"demanding": "cây kén đất", "tolerant": "cây chịu đất nghèo"}
KT_VI = {k: v for _, k, v in KT_CLASSES}
# Thông số thủy lực theo cấp cơ giới USDA (Rawls, Brakensiek & Saxton 1982, giá trị trung bình) — CHỈ dùng khi thiếu số đo SSURGO.
RAWLS = {"sand": (0.437, 0.091, 0.033), "loamy sand": (0.437, 0.125, 0.055), "sandy loam": (0.453, 0.207, 0.095), "loam": (0.463, 0.270, 0.117),
         "silt loam": (0.501, 0.330, 0.133), "silt": (0.501, 0.330, 0.133), "sandy clay loam": (0.398, 0.255, 0.148), "clay loam": (0.464, 0.318, 0.197),
         "silty clay loam": (0.471, 0.366, 0.208), "sandy clay": (0.430, 0.339, 0.239), "silty clay": (0.479, 0.387, 0.250), "clay": (0.475, 0.396, 0.272)}

CRD = [
    dict(id="wheat", vi="Lúa mì đông", en="Winter wheat", sci="Triticum aestivum", group="cereal", family="Poaceae",
         A1=dict(opt=[15, 20], tol=[4, 32], txt="15–20 / 3–4 đến 30–32", note="Dưới 10–12°C trong vụ là rủi ro. Tháng ngủ đông (TB < 5°C) không tính vào nhiệt độ vụ.", src=["FAO-W", "FAO-WT"], dormant_below=5.0),
         A2=dict(opt=[750, 900], tol=[300, 1600], txt="750–900 / 300–1.600", src=["EC-W"]),
         A3=dict(opt=["vbright"], tol=["clear"], txt="Rất sáng; ưa vị trí nhiều nắng", src=["ISWS-W", "EC-W"]),
         B1=dict(etm=[450, 650], ky=1.05, txt="450–650", src=["FAO-W", "FAO-66"]),
         ZR=dict(range=[1.5, 1.8], src=["FAO-56"]),
         C1=dict(kind="sys", classes=[[50, "S1"], [20, "S2"], [10, "S3"]], txt="> 50 cm (S1), 20–50 (S2), 10–20 (S3), < 10 (N)", src=["ALUES"]),
         C2=dict(opt=["medium"], tol=["heavy", "light"], excl=[], txt="Tối ưu: trung bình. Chịu đựng: nặng, nhẹ. Loại: không có", src=["FAO-W"]),
         C3=dict(opt=[6, 7], tol=[5.5, 8.5], txt="6–7 / 5,5–8,5", src=["EC-W"]),
         C4=dict(habit="dry", txt="Ưa cạn: cần đất thoát nước tốt, mực nước ngầm không quá nông", src=["FAO-W"]),
         C5=dict(kind="demanding", txt="Cây kén đất. Đất giàu dinh dưỡng [EC-W]; CEC > 24: 1 · 16–24: 0,75 · 10–16: 0,5 · < 10: 0", src=["EC-W", "ALUES"]),
         C6=dict(thr=6.0, half=13.0, zero=20.0, txt="6,0 / 13 / 20; lúc nảy mầm ≤ 4", src=["FAO-W"]),
         D1=dict(txt="0–4 (S1), 4–8 (S2), 8–16 (S3), > 16 (N), canh tác cơ giới hóa", src=["ALUES"]),
         E1=dict(c=0.20, assumed=False, txt="Hệ số C (RUSLE) = 0,20", src=["PAN"]),
         K1=dict(sow=[[15, 9], [20, 10]], harvest=[[1, 6], [15, 7]], cycle=[180, 250],
                 txt="Gieo 15/9–20/10; thu chủ yếu tháng 6–7 (năm 2010: 92% đã thu đến 11/7). 180–250 ngày", src=["AgM", "NASS-KS", "FAO-W"])),
    dict(id="sorghum", vi="Cao lương", en="Grain sorghum", sci="Sorghum bicolor", group="cereal", family="Poaceae",
         A1=dict(opt=[22, 35], tol=[8, 40], txt="22–35 / 8–40", note="< 15°C hoặc > 35°C lúc ra hoa làm giảm đậu hạt", src=["EC-S", "FAO-S"]),
         A2=dict(opt=[400, 600], tol=[300, 700], txt="400–600 / 300–700", src=["EC-S"]),
         A3=dict(opt=["vbright"], tol=["clear"], txt="Rất sáng / trời quang đến rất sáng", src=["EC-S"]),
         B1=dict(etm=[450, 650], ky=0.9, txt="450–650 (giống 110–130 ngày)", src=["FAO-S", "FAO-66"]),
         ZR=dict(range=[1.0, 2.0], src=["FAO-56"]),
         C1=dict(kind="trap", opt_low=50, tol_min=50, txt="Sâu 50–150 cm / 50–150 cm", src=["EC-S"]),
         C2=dict(opt=["heavy", "medium"], tol=["light"], excl=[], txt="Tối ưu: nặng, trung bình. Chịu đựng: nhẹ (“mọi loại”). Loại: không có", src=["EC-S"]),
         C3=dict(opt=[5.5, 7.5], tol=[5, 8], txt="5,5–7,5 / 5–8", src=["EC-S"]),
         C4=dict(habit="dry", txt="Ưa cạn: cần đất thoát nước tốt, chỉ chịu úng ngắn", src=["EC-S", "FAO-S"]),
         C5=dict(kind="tolerant", txt="Cây chịu đất nghèo (cao / thấp). CEC > 24: 1 · 16–24: 1 · 10–16: 0,75 · < 10: 0,5", src=["EC-S"]),
         C6=dict(thr=4.0, half=11.0, zero=18.0, txt="4 / 11 / 18", src=["FAO-S"]),
         D1=dict(txt="0–4 (S1), 4–8 (S2), 8–16 (S3), > 16 (N), canh tác cơ giới hóa", src=["ALUES"]),
         E1=dict(c=0.38, assumed=True, txt="Tạm lấy bằng ngô: C = 0,38 (giả định, nguồn [PAN] không có cao lương)", src=["PAN"]),
         K1=dict(sow=[[15, 5], [20, 6]], harvest=[[11, 10], [8, 11]], cycle=[90, 300],
                 txt="Gieo 15/5–20/6; thu 11/10–8/11. 90–300 ngày", src=["KSU-2", "KSU-1", "EC-S"])),
    dict(id="maize", vi="Ngô", en="Maize (corn)", sci="Zea mays", group="cereal", family="Poaceae",
         A1=dict(opt=[18, 33], tol=[10, 47], txt="18–33 / 10–47", note="Cần trung bình > 15°C, không sương giá", src=["EC-M", "FAO-M"]),
         A2=dict(opt=[600, 1200], tol=[400, 1800], txt="600–1.200 / 400–1.800", src=["EC-M"]),
         A3=dict(opt=["vbright"], tol=["clear"], txt="Rất sáng / trời quang đến rất sáng", src=["EC-M"]),
         B1=dict(etm=[500, 800], ky=1.25, txt="500–800 (giống trung ngày)", src=["FAO-M", "FAO-66"]),
         ZR=dict(range=[1.0, 1.7], src=["FAO-56"]),
         C1=dict(kind="sys", classes=[[100, "S1"], [75, "S2"], [50, "S3"]], txt="Sâu 50–150 cm / 20–50 cm. Phân hạng: > 100 cm (S1), 75–100 (S2), 50–75 (S3), < 50 (N)", src=["EC-M", "Sys-M"]),
         C2=dict(opt=["medium"], tol=["heavy", "light"], excl=["sand"], txt="Tối ưu: trung bình. Chịu đựng: nặng, nhẹ (trừ cát). Loại: cát", src=["FAO-M"]),
         C3=dict(opt=[5, 7], tol=[4.5, 8.5], txt="5–7 / 4,5–8,5", src=["EC-M"]),
         C4=dict(habit="dry", txt="Ưa cạn: cần đất thoát nước tốt, úng lúc ra hoa có thể giảm ≥ 50% năng suất", src=["Sys-M", "FAO-M"]),
         C5=dict(kind="demanding", txt="Cây kén đất (cao / thấp). CEC > 24: 1 · 16–24: 0,75 · 10–16: 0,5 · < 10: 0", src=["EC-M", "Sys-M"]),
         C6=dict(thr=1.7, half=5.9, zero=10.0, txt="1,7 / 5,9 / 10", src=["FAO-M"]),
         D1=dict(txt="0–4 (S1), 4–8 (S2), 8–16 (S3), > 16 (N)", src=["Sys-M"]),
         E1=dict(c=0.38, assumed=False, txt="Hệ số C (RUSLE) = 0,38; độc canh ngô có thể gây xói mòn", src=["PAN", "EC-M"]),
         K1=dict(sow=[[19, 4], [17, 5]], harvest=[[13, 9], [18, 10]], cycle=[80, 140],
                 txt="Gieo 19/4–17/5; thu 13/9–18/10. Giống sớm 80–110, trung 110–140 ngày", src=["KSU-1", "FAO-M"])),
    dict(id="soybean", vi="Đậu tương", en="Soybean", sci="Glycine max", group="legume", family="Fabaceae",
         A1=dict(opt=[20, 33], tol=[10, 38], txt="20–33 / 10–38", note="Sinh trưởng chậm lại khi > 35°C hoặc < 18°C", src=["EC-G", "FAO-G"]),
         A2=dict(opt=[600, 1500], tol=[450, 1800], txt="600–1.500 / 450–1.800", src=["EC-G"]),
         A3=dict(opt=["vbright"], tol=["clear"], txt="Rất sáng / trời quang đến rất sáng", src=["EC-G"]),
         B1=dict(etm=[450, 700], ky=0.85, txt="450–700", src=["FAO-G", "FAO-66"]),
         ZR=dict(range=[0.6, 1.3], src=["FAO-56"]),
         C1=dict(kind="trap", opt_low=50, tol_min=20, txt="Sâu 50–150 cm / 20–50 cm", src=["EC-G"]),
         C2=dict(opt=["medium"], tol=["heavy", "light"], excl=["sand"], txt="Tối ưu: trung bình, hữu cơ. Chịu đựng: nặng, nhẹ (trừ cát). Loại: cát (“trừ đất rất cát”)", src=["EC-G", "FAO-G"]),
         C3=dict(opt=[5.5, 6.5], tol=[4.5, 8.4], txt="5,5–6,5 / 4,5–8,4", src=["EC-G"]),
         C4=dict(habit="dry", txt="Ưa cạn: cần đất thoát nước tốt, nhạy úng đầu vụ", src=["EC-G", "FAO-G"]),
         C5=dict(kind="tolerant", txt="Cây chịu đất nghèo (cao / thấp). CEC > 24: 1 · 16–24: 1 · 10–16: 0,75 · < 10: 0,5", src=["EC-G"]),
         C6=dict(thr=5.0, half=7.5, zero=10.0, txt="5 / 7,5 / 10", src=["FAO-G"]),
         D1=dict(txt="0–4 (S1), 4–8 (S2), 8–16 (S3), > 16 (N), canh tác cơ giới hóa", src=["ALUES"]),
         E1=dict(c=0.28, assumed=False, txt="Hệ số C (RUSLE) = 0,28", src=["PAN"]),
         K1=dict(sow=[[10, 5], [14, 6]], harvest=[[4, 10], [1, 11]], cycle=[100, 130],
                 txt="Gieo 10/5–14/6; thu 4/10–1/11. 100–130 ngày", src=["KSU-1", "FAO-G"])),
]
FALLOW = {"id": "fallow", "vi": "Đất nghỉ", "en": "Fallow", "note": "Không có yêu cầu sinh thái: coi là phương án luôn khả thi, chỉ so sánh qua điểm MCA con (làm ở bước sau)."}
CRD_NOTES = ["Đất nghỉ không có yêu cầu sinh thái: coi là phương án luôn khả thi, chỉ so sánh qua điểm MCA con.",
             "Mưa trong ECOCROP là mưa cả năm; khi đánh giá theo vụ nên dùng B1 (nhu cầu nước cả vụ) để so với mưa và ẩm đất của vụ."]


def _doy(d, m):
    """Ngày thứ mấy trong năm (năm tham chiếu không nhuận)."""
    return (dt.date(2001, int(m), min(int(d), [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][int(m) - 1])) - dt.date(2001, 1, 1)).days + 1


def _crd_finish(c):
    k = c["K1"]
    s0, s1 = _doy(*k["sow"][0]), _doy(*k["sow"][1])
    h0, h1 = _doy(*k["harvest"][0]), _doy(*k["harvest"][1])
    mid_s = (s0 + ((s1 - s0) % 365) / 2.0) % 365
    mid_h = (h0 + ((h1 - h0) % 365) / 2.0) % 365
    k["window_days"] = int(round((mid_h - mid_s) % 365))        # số ngày gieo → thu điển hình theo lịch Kansas (dùng để lấy tháng trong vụ)
    c["B1"]["etm_mid"] = round(mean(c["B1"]["etm"]))
    c["ZR"]["mid"] = round(mean(c["ZR"]["range"]), 2)
    return c


def _load_crd():
    crops = {c["id"]: _crd_finish(json.loads(json.dumps(c))) for c in CRD}
    p = os.path.join(DATA_DIR, "crops.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for o in json.load(f):
                    cid = o.get("id")
                    if cid in crops:
                        for k, v in o.items():
                            if isinstance(v, dict) and isinstance(crops[cid].get(k), dict):
                                crops[cid][k].update(v)
                            else:
                                crops[cid][k] = v
                        _crd_finish(crops[cid])
        except Exception as e:                                       # noqa
            print("[crops.json] bỏ qua do lỗi:", e)
    return crops


CROPS = _load_crd()


def cname(cid):
    return CROPS[cid]["vi"] if cid in CROPS else ("Đất nghỉ" if cid == "fallow" else str(cid))

# ───────────────────────── NASA POWER + khí hậu ─────────────────────────
POWER_URL  = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_VARS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "GWETROOT", "GWETTOP", "ALLSKY_SFC_SW_DWN", "RH2M", "ALLSKY_KT"]   # ALLSKY_KT: chỉ số trong suốt khí quyển (tiêu chí A3)
HARGREAVES_K = 0.0135 / 2.45      # ET0 = 0.0135·(T+17.8)·Rs/λ  (Hargreaves–Samani dạng bức xạ đo, Rs: MJ/m²/ngày → mm/ngày)

class PowerError(Exception):
    pass

def power_years():
    end = dt.date.today().year - 1
    return end - POWER_YEARS + 1, end

def _grid_key(lat, lon):
    y0, y1 = power_years()
    return "%.2f_%.2f_%d_%d" % (round(lat * 4) / 4, round(lon * 4) / 4, y0, y1)

def _http_json(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "FARM-ADAPT/%s (NASA Space Apps 2026)" % VERSION})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def power_fetch_raw(lat, lon):
    """Tải chuỗi NGÀY NASA POWER (cộng đồng AG) theo từng khối 5 năm. Không cần khóa API. Nếu máy chủ không nhận ALLSKY_KT → tải lại không có biến này
    (Kt sẽ được tính từ bức xạ mặt đất / bức xạ đỉnh khí quyển theo FAO-56)."""
    try:
        return _power_fetch_vars(lat, lon, POWER_VARS)
    except urllib.error.HTTPError as e:
        if e.code in (400, 422):
            return _power_fetch_vars(lat, lon, [v for v in POWER_VARS if v != "ALLSKY_KT"])
        raise PowerError("Không gọi được NASA POWER: %s" % e)


def _power_fetch_vars(lat, lon, VARS):
    y0, y1 = power_years()
    dates, V, elev, units = [], {v: [] for v in VARS}, None, {}
    for ys in range(y0, y1 + 1, 5):
        ye = min(ys + 4, y1)
        q = urllib.parse.urlencode({"parameters": ",".join(VARS), "community": "AG", "longitude": "%.4f" % lon,
                                    "latitude": "%.4f" % lat, "start": "%d0101" % ys, "end": "%d1231" % ye, "format": "JSON"})
        try:
            data = _http_json(POWER_URL + "?" + q, POWER_TIMEOUT)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise PowerError("Không gọi được NASA POWER: %s" % e)
        try:
            par = data["properties"]["parameter"]
            keys = sorted(par["T2M"].keys())
        except Exception:
            raise PowerError("Phản hồi NASA POWER không đúng định dạng.")
        dates += keys
        for v in VARS:
            d = par.get(v) or {}
            for k in keys:
                x = d.get(k)
                V[v].append(None if x is None or x <= -990 else float(x))
        try:
            elev = elev if elev is not None else data["geometry"]["coordinates"][2]
            for v, meta in (data.get("parameters") or {}).items():
                units[v] = meta.get("units", "")
        except Exception:
            pass
    return {"dates": dates, "v": V, "elev": elev, "units": units, "lat": lat, "lon": lon,
            "source": "NASA POWER (MERRA-2 + GPM IMERG + CERES), lưới ~0,5°×0,625°", "years": [y0, y1]}

def demo_raw(lat, lon):
    """Khí hậu MÔ PHỎNG theo vĩ độ — CHỈ để chạy thử giao diện khi không có mạng. KHÔNG phải dữ liệu NASA."""
    y0, y1 = power_years()
    rnd = random.Random(int(abs(lat) * 1000) * 7919 + int(abs(lon) * 1000))
    nh = lat >= 0
    al = abs(lat)
    base = 27 - 0.5 * max(0.0, al - 10)
    amp = 0.3 * al
    annual_rain = 1500.0 if al < 30 else 800.0
    p_avg, amt = 0.2, annual_rain / (365 * 0.2)
    dates, V = [], {v: [] for v in POWER_VARS if v != "ALLSKY_KT"}
    ar, gw = 0.0, 0.5
    d = dt.date(y0, 1, 1)
    end = dt.date(y1, 12, 31)
    while d <= end:
        doy = d.timetuple().tm_yday
        ph = 2 * math.pi * (doy - (200 if nh else 18)) / 365.25
        ar = 0.7 * ar + rnd.gauss(0, 2.0)
        t = base + amp * math.cos(ph) + ar
        w = 1 + (0.85 if al < 30 else 0.2) * math.cos(ph)
        rain = rnd.expovariate(1.0 / amt) if rnd.random() < clamp(p_avg * w, 0, 0.9) else 0.0
        dtr = 6.5 if rain > 1 else 9.5
        rs = max(3.0, (15 + 7 * math.cos(ph) * min(1.0, al / 45.0)) * (0.6 if rain > 1 else 1.0))
        gw = clamp(gw + 0.005 * rain - 0.014 * max(0.0, (t + 5) / 22.0), 0.05, 0.95)
        dates.append(d.strftime("%Y%m%d"))
        V["T2M"].append(t); V["T2M_MAX"].append(t + dtr / 2); V["T2M_MIN"].append(t - dtr / 2)
        V["PRECTOTCORR"].append(rain); V["GWETROOT"].append(gw); V["GWETTOP"].append(clamp(gw + 0.05 * rnd.gauss(0, 1), 0, 1))
        V["ALLSKY_SFC_SW_DWN"].append(rs); V["RH2M"].append(clamp(60 + 25 * (rain > 1) + rnd.gauss(0, 5), 20, 100))
        d += dt.timedelta(days=1)
    return {"dates": dates, "v": V, "elev": None, "units": {"ALLSKY_SFC_SW_DWN": "MJ/m^2/day"}, "lat": lat, "lon": lon,
            "source": "DEMO — khí hậu MÔ PHỎNG theo vĩ độ (KHÔNG phải dữ liệu NASA)", "years": [y0, y1], "demo": True}

def _fill(arr, default):
    first = next((x for x in arr if x is not None), default)
    out, last = [], first
    for x in arr:
        if x is None:
            x = last
        out.append(x)
        last = x
    return out

def _ra_mj(lat, doy):
    """Bức xạ đỉnh khí quyển ngày (MJ/m²/ngày), FAO-56 công thức 21."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    de = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(clamp(-math.tan(phi) * math.tan(de), -1.0, 1.0))
    return 24 * 60 / math.pi * 0.0820 * dr * (ws * math.sin(phi) * math.sin(de) + math.cos(phi) * math.cos(de) * math.sin(ws))


class Clim:
    """Khí hậu đã tổng hợp theo tháng; giữ chuỗi tháng liên tục (để lấy 'năm khô' từ lịch sử thật) và danh sách ngày đã sắp xếp (đếm ngày cực đoan)."""
    def __init__(self, raw):
        self.raw = raw
        self.is_demo = bool(raw.get("demo"))
        V = raw["v"]
        dates = raw["dates"]
        rs_scale = 3.6 if "kw" in str(raw.get("units", {}).get("ALLSKY_SFC_SW_DWN", "")).lower() else 1.0
        T = _fill(V["T2M"], 15.0); TX = _fill(V["T2M_MAX"], 20.0); TN = _fill(V["T2M_MIN"], 10.0)
        P = [max(0.0, x) for x in _fill(V["PRECTOTCORR"], 0.0)]
        GW = _fill(V["GWETROOT"], 0.5); RS = [x * rs_scale for x in _fill(V["ALLSKY_SFC_SW_DWN"], 15.0)]; RH = _fill(V["RH2M"], 70.0)
        lat = raw.get("lat") or 0.0
        if V.get("ALLSKY_KT"):
            KT = [x if (x is not None and 0 < x <= 1) else None for x in V["ALLSKY_KT"]]
            self.kt_src = "NASA POWER ALLSKY_KT (CERES SYN1deg)"
        else:                                              # Kt = bức xạ mặt đất / bức xạ đỉnh khí quyển Ra (FAO-56, công thức 21)
            KT = []
            for d, rs in zip(dates, RS):
                ra = _ra_mj(lat, dt.date(int(d[:4]), int(d[4:6]), int(d[6:8])).timetuple().tm_yday)
                KT.append(clamp(rs / ra, 0, 1) if ra > 0.5 else None)
            self.kt_src = "Tính từ ALLSKY_SFC_SW_DWN / Ra (FAO-56)" + (" — DEMO" if self.is_demo else "")
        self.day = {"T": T, "TX": TX, "TN": TN, "P": P, "GW": GW, "RS": RS, "KT": KT, "dates": dates}
        self.didx = {d: i for i, d in enumerate(dates)}
        by = {}
        for i, d in enumerate(dates):
            by.setdefault((int(d[:4]), int(d[4:6])), []).append(i)
        years = sorted({y for y, _ in by if all((y, m) in by for m in range(1, 13))})
        self.years = years
        self.ny = len(years)
        self.ser = []
        self.tmin_sorted = [[] for _ in range(12)]
        self.tmax_sorted = [[] for _ in range(12)]
        self.p_sorted = [[] for _ in range(12)]
        for y in years:
            for m in range(1, 13):
                ix = by[(y, m)]
                et0 = sum(max(0.0, HARGREAVES_K * (T[i] + 17.8) * RS[i]) for i in ix)
                kv = [KT[i] for i in ix if KT[i] is not None]
                self.ser.append({"y": y, "m": m, "P": sum(P[i] for i in ix), "T": mean(T[i] for i in ix), "TX": mean(TX[i] for i in ix), "KT": mean(kv) if kv else None,
                                 "TN": mean(TN[i] for i in ix), "RS": sum(RS[i] for i in ix), "ET0": et0, "GW": mean(GW[i] for i in ix),
                                 "RH": mean(RH[i] for i in ix)})
                self.tmin_sorted[m - 1] += [TN[i] for i in ix]
                self.tmax_sorted[m - 1] += [TX[i] for i in ix]
                self.p_sorted[m - 1] += [P[i] for i in ix]
        for m in range(12):
            self.tmin_sorted[m].sort(); self.tmax_sorted[m].sort(); self.p_sorted[m].sort()
        # thống kê theo năm
        self.annual = []
        for y in years:
            ix = [i for m in range(1, 13) for i in by[(y, m)]]
            run = best = 0
            for i in ix:
                run = run + 1 if P[i] < 1.0 else 0
                best = max(best, run)
            es = [e for e in self.ser if e["y"] == y]
            self.annual.append({"year": y, "T": mean(T[i] for i in ix), "P": sum(P[i] for i in ix), "GW": mean(GW[i] for i in ix),
                                "ET0": sum(e["ET0"] for e in es), "heat35": sum(1 for i in ix if TX[i] >= 35), "frost0": sum(1 for i in ix if TN[i] <= 0),
                                "dry_spell": best, "heavy30": sum(1 for i in ix if P[i] >= 30)})

    def cm(self, key, m):                       # trung bình theo tháng lịch (m: 0..11)
        return mean(self.ser[y * 12 + m][key] for y in range(self.ny))

    def summary(self):
        ny = self.ny
        monthly = []
        for m in range(12):
            P = [self.ser[y * 12 + m]["P"] for y in range(ny)]
            et0 = self.cm("ET0", m)
            kts = [self.ser[y * 12 + m]["KT"] for y in range(ny) if self.ser[y * 12 + m]["KT"] is not None]
            monthly.append({"m": m + 1, "KT": mean(kts) if kts else None, "T": self.cm("T", m), "Tx": self.cm("TX", m), "Tn": self.cm("TN", m), "P": mean(P), "P_p20": pctl(P, 0.2),
                            "ET0": et0, "aridity": (mean(P) / et0) if et0 > 0 else None, "GW": self.cm("GW", m), "RH": self.cm("RH", m),
                            "frost0": self._cnt_le(m, 0.0) , "frost2": self._cnt_le(m, -2.0), "heat30": self._cnt_ge(m, 30.0), "heat35": self._cnt_ge(m, 35.0),
                            "heavy30": (len(self.p_sorted[m]) - bisect.bisect_left(self.p_sorted[m], 30.0)) / ny})
        yrs = [a["year"] for a in self.annual]
        trends = {k: theil_sen(yrs, [a[k] for a in self.annual]) for k in ("T", "P", "GW", "ET0")}
        for v in trends.values():
            v["slope_decade"] = v["slope"] * 10
        # bất thường (z-score) 24 tháng cuối so với khí hậu cùng tháng
        anom = []
        for e in self.ser[-24:]:
            m = e["m"] - 1
            row = {"ym": "%d-%02d" % (e["y"], e["m"])}
            for k, nm in (("P", "P_z"), ("GW", "GW_z"), ("T", "T_z")):
                vals = [self.ser[y * 12 + m][k] for y in range(ny)]
                s = stdev(vals)
                row[nm] = (e[k] - mean(vals)) / s if s > 1e-9 else 0.0
            anom.append(row)
        series = [{"ym": "%d-%02d" % (e["y"], e["m"]), "P": e["P"], "T": e["T"], "GW": e["GW"]} for e in self.ser]
        return {"source": self.raw.get("source"), "is_demo": self.is_demo, "years": [self.years[0], self.years[-1]], "n_years": ny,
                "lat": self.raw["lat"], "lon": self.raw["lon"], "elev_m": self.raw.get("elev"), "monthly": monthly, "annual": self.annual,
                "trends": trends, "anomalies": anom, "series": series, "kt_src": self.kt_src,
                "annual_mean": {"T": mean(a["T"] for a in self.annual), "P": mean(a["P"] for a in self.annual), "ET0": mean(a["ET0"] for a in self.annual),
                                "GW": mean(a["GW"] for a in self.annual)},
                "grid_note": "Lưới khí tượng ~0,5°×0,625° (~50 km): phản ánh KHÍ HẬU KHU VỰC, chưa phải vi khí hậu từng thửa. Nên hiệu chỉnh bằng số đo mưa/nhiệt tại ruộng."}

    def _cnt_le(self, m, thr):
        return bisect.bisect_right(self.tmin_sorted[m], thr) / self.ny

    def _cnt_ge(self, m, thr):
        s = self.tmax_sorted[m]
        return (len(s) - bisect.bisect_left(s, thr)) / self.ny

_CLIM_MEM = {}

def get_clim(lat, lon, allow_demo=True):
    """Bộ nhớ → đệm đĩa → gọi NASA POWER → (nếu cho phép) khí hậu DEMO. Trả (Clim, ghi_chú)."""
    key = _grid_key(lat, lon)
    with _LOCK:
        if key in _CLIM_MEM:
            return _CLIM_MEM[key]
    path = os.path.join(CACHE_DIR, "power_%s.json" % key)
    raw, note = None, ""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            note = "đệm trên đĩa"
        except Exception:
            raw = None
    if raw is None:
        try:
            raw = power_fetch_raw(round(lat * 4) / 4, round(lon * 4) / 4)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(raw, f)
            note = "tải mới từ NASA POWER"
        except PowerError as e:
            if not (allow_demo and DEMO_FALLBACK):
                raise
            raw = demo_raw(lat, lon)
            note = "DEMO vì: %s" % e
    out = (Clim(raw), note)
    if not raw.get("demo"):                       # không ghi nhớ DEMO để lần sau còn thử NASA POWER lại
        with _LOCK:
            _CLIM_MEM[key] = out
    return out

# ───────────────────────── lớp dữ liệu bổ sung (NDVI / SMAP / LST / GPM) bằng CSV ─────────────────────────
LAYER_KINDS = {"gpm": "Mưa GPM IMERG (mm/tháng) — dùng cho A2, B1", "smap": "Độ ẩm vùng rễ SMAP L4 (m³/m³) — dùng cho B1", "ndvi": "NDVI (MODIS/Landsat) — tham khảo",
               "lst": "Nhiệt độ bề mặt LST (MODIS/ECOSTRESS, °C) — chỉ để tìm điểm nóng"}

def _parse_date(s):
    s = str(s).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y/%m", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def parse_layer_csv(text, kind):
    """CSV hai cột: ngày + giá trị (có/không tiêu đề). Gộp theo tháng. GPM: ≤5 ngày/điểm → coi là mm/ngày và cộng; ngược lại là tổng tháng."""
    sample = text[:2000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if r and any(c.strip() for c in r)]
    if len(rows) < 7:
        raise ValueError("File quá ít dòng (cần ít nhất ~6 điểm dữ liệu).")
    head = [c.strip().lower() for c in rows[0]]
    has_head = _parse_date(rows[0][0]) is None
    di, vi = 0, 1
    if has_head:
        for i, h in enumerate(head):
            if "date" in h or "time" in h or "ngay" in h or "ngày" in h:
                di = i
        cands = [i for i, h in enumerate(head) if i != di and (kind in h or "value" in h or "mean" in h or "gia" in h or "giá" in h)]
        vi = cands[0] if cands else (1 if di == 0 else 0)
        rows = rows[1:]
    pts = []
    for r in rows:
        if len(r) <= max(di, vi):
            continue
        d = _parse_date(r[di])
        v = num(r[vi].replace(",", ".") if isinstance(r[vi], str) else r[vi])
        if d is not None and v is not None and v > -9000:
            pts.append((d, v))
    if len(pts) < 6:
        raise ValueError("Không đọc được ≥6 cặp (ngày, giá trị). Cần cột ngày dạng YYYY-MM-DD và cột giá trị số.")
    pts.sort()
    vals = [v for _, v in pts]
    if kind == "ndvi" and max(vals) > 2:
        pts = [(d, v / 10000.0) for d, v in pts]
    if kind == "lst":
        if mean(vals) > 1000:
            pts = [(d, v * 0.02) for d, v in pts]
        if mean(v for _, v in pts) > 150:
            pts = [(d, v - 273.15) for d, v in pts]
    spacing = statistics.median([(pts[i + 1][0] - pts[i][0]).days for i in range(len(pts) - 1)] or [30])
    by = {}
    for d, v in pts:
        by.setdefault((d.year, d.month), []).append(v)
    series = []
    for (y, m), arr in sorted(by.items()):
        val = sum(arr) if (kind == "gpm" and spacing <= 5) else mean(arr)
        series.append({"ym": "%d-%02d" % (y, m), "v": round(val, 4)})
    clim = []
    for m in range(1, 13):
        a = [s["v"] for s in series if int(s["ym"][5:]) == m]
        clim.append(round(mean(a), 4) if a else None)
    return {"kind": kind, "label": LAYER_KINDS.get(kind, kind), "n_points": len(pts), "n_months": len(series), "first": series[0]["ym"], "last": series[-1]["ym"],
            "clim": clim, "series": series, "spacing_days": spacing}

# ───────────────────────── TỰ LẤY DỮ LIỆU THEO VỊ TRÍ (v0.6) ─────────────────────────
# Người dùng chỉ chọn vị trí; các lớp dưới đây được gọi API và đệm vào data/cache/. Đầu ra lớp chuỗi thời gian có CÙNG
# cấu trúc với parse_layer_csv → fuse_layers dùng lại nguyên vẹn; khe nạp CSV thủ công vẫn giữ.
# Đã thử thật ngày 14/11/2026 từ Việt Nam: ORNL MODIS (không khóa), GES DISC OPeNDAP IMERG (EARTHDATA_TOKEN),
# SoilGrids (không khóa, chậm), OpenTopoData SRTM (không khóa). AppEEARS KHÔNG nhận token Earthdata (403) nên chưa dùng.
EARTHDATA_TOKEN = (os.environ.get("EARTHDATA_TOKEN") or "").strip()
AUTO_YEARS = max(3, min(20, int(os.environ.get("AUTO_LAYER_YEARS", "6") or 6)))    # số năm NDVI/LST (ORNL chậm: ~10 ngày ảnh/lần gọi)

AUTO_SOURCES = {
    "ndvi":  {"name": "MODIS MOD13Q1 NDVI v6.1", "nasa": True, "res": "250 m, 16 ngày", "via": "ORNL DAAC MODIS/VIIRS Web Service (REST, không cần khóa)",
              "cite": "Didan, K. (2021). MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061. NASA EOSDIS LP DAAC. doi:10.5067/MODIS/MOD13Q1.061"},
    "lst":   {"name": "MODIS MOD11A2 LST v6.1", "nasa": True, "res": "1 km, 8 ngày", "via": "ORNL DAAC MODIS/VIIRS Web Service (REST, không cần khóa)",
              "cite": "Wan, Z., Hook, S., Hulley, G. (2021). MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 Global 1km SIN Grid V061. NASA EOSDIS LP DAAC. doi:10.5067/MODIS/MOD11A2.061"},
    "gpm":   {"name": "GPM IMERG Final Monthly V07 (GPM_3IMERGM)", "nasa": True, "res": "0,1° (~11 km), tháng", "via": "NASA GES DISC OPeNDAP (cần EARTHDATA_TOKEN)",
              "cite": "Huffman, G.J., et al. (2023). GPM IMERG Final Precipitation L3 1 month 0.1 degree x 0.1 degree V07. NASA GES DISC. doi:10.5067/GPM/IMERG/3B-MONTH/07"},
    "soil":  {"name": "SoilGrids 2.0", "nasa": False, "res": "250 m", "via": "ISRIC REST API (không cần khóa, CC BY 4.0)",
              "cite": "Poggio, L., et al. (2021). SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. SOIL 7, 217–240. doi:10.5194/soil-7-217-2021"},
    "ssurgo": {"name": "SSURGO / gSSURGO (USDA NRCS)", "nasa": False, "res": "đơn vị bản đồ đất 1:12.000–1:24.000 (chỉ Hoa Kỳ)", "via": "Soil Data Access (SDA) REST, không cần khóa",
               "cite": "Soil Survey Staff, NRCS, USDA. Soil Survey Geographic (SSURGO) Database. Truy cập qua Soil Data Access: https://sdmdataaccess.nrcs.usda.gov/"},
    "slope": {"name": "SRTM GL1 (30 m)", "nasa": True, "res": "30 m", "via": "OpenTopoData public API (không cần khóa)",
              "cite": "NASA JPL (2013). NASA Shuttle Radar Topography Mission Global 1 arc second. NASA EOSDIS LP DAAC. doi:10.5067/MEaSUREs/SRTM/SRTMGL1.003"},
}

class AutoError(Exception):
    pass

def _xget(url, timeout=60, headers=None, raw=False, retries=2):
    last = None
    for k in range(retries + 1):
        try:
            h = {"User-Agent": "FARM-ADAPT/%s (NASA Space Apps 2026)" % VERSION, "Accept": "*/*" if raw else "application/json"}
            h.update(headers or {})
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                b = r.read()
                return b.decode("utf-8", "replace") if raw else json.loads(b.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = e
        time.sleep(1.5 * (k + 1))
    raise AutoError("Không gọi được %s: %s" % (url.split("?")[0][:80], last))

def _cache_rw(name, fn, max_age_days):
    p = os.path.join(CACHE_DIR, name)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < max_age_days * 86400:
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    out = fn()
    out["retrieved_at"] = dt.datetime.now().isoformat(timespec="seconds")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out

def _layer_from_points(kind, pts, agg, lat, lon, extra=None):
    """(date, value) → cùng cấu trúc với parse_layer_csv, kèm nguồn + toạ độ để giao diện biết lớp thuộc ruộng nào."""
    pts = sorted(p for p in pts if p[1] is not None and math.isfinite(p[1]))
    if len(pts) < 6:
        raise AutoError("Quá ít quan sát hợp lệ (%d) cho lớp %s tại điểm này." % (len(pts), kind))
    by = {}
    for d, v in pts:
        by.setdefault((d.year, d.month), []).append(v)
    series = [{"ym": "%d-%02d" % ym, "v": round(sum(a) if agg == "sum" else mean(a), 4)} for ym, a in sorted(by.items())]
    clim = []
    for m in range(1, 13):
        a = [s["v"] for s in series if int(s["ym"][5:]) == m]
        clim.append(round(mean(a), 4) if a else None)
    sp = statistics.median([(pts[i + 1][0] - pts[i][0]).days for i in range(len(pts) - 1)] or [30])
    out = {"kind": kind, "label": LAYER_KINDS.get(kind, kind), "n_points": len(pts), "n_months": len(series), "first": series[0]["ym"],
           "last": series[-1]["ym"], "clim": clim, "series": series, "spacing_days": sp, "auto": True, "lat": lat, "lon": lon,
           "source": AUTO_SOURCES.get(kind)}
    out.update(extra or {})
    return out

# ---- ORNL DAAC MODIS/VIIRS Web Service
ORNL_API = "https://modis.ornl.gov/rst/api/v1/"

def _ornl_band(product, band, lat, lon, d0, d1, workers=4):
    """Chuỗi [(date, raw)] cho 1 pixel. API giới hạn ≤10 ngày ảnh/yêu cầu → chia khối, gọi song song nhẹ (4 luồng)."""
    import concurrent.futures as cf
    ds = _xget(ORNL_API + "%s/dates?latitude=%.5f&longitude=%.5f" % (product, lat, lon))
    if not isinstance(ds, dict) or "dates" not in ds:
        raise AutoError("ORNL không có %s tại điểm này." % product)
    ds = [x for x in ds["dates"] if d0 <= x["calendar_date"] <= d1]
    blocks = [ds[i:i + 10] for i in range(0, len(ds), 10)]

    def one(b):
        q = urllib.parse.urlencode({"latitude": "%.5f" % lat, "longitude": "%.5f" % lon, "band": band, "startDate": b[0]["modis_date"],
                                    "endDate": b[-1]["modis_date"], "kmAboveBelow": 0, "kmLeftRight": 0})
        return [(dt.date.fromisoformat(s["calendar_date"]), s["data"][0]) for s in _xget(ORNL_API + product + "/subset?" + q, timeout=90).get("subset", [])]
    out = []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(one, blocks):
            out += r
    return out

def auto_ndvi(lat, lon, years=AUTO_YEARS):
    lat, lon = round(lat, 4), round(lon, 4)
    d1 = dt.date.today()
    d0 = dt.date(d1.year - years, 1, 1)

    def run():
        nd = _ornl_band("MOD13Q1", "250m_16_days_NDVI", lat, lon, d0.isoformat(), d1.isoformat())
        rel = dict(_ornl_band("MOD13Q1", "250m_16_days_pixel_reliability", lat, lon, d0.isoformat(), d1.isoformat()))
        good = [(d.isoformat(), v * 0.0001) for d, v in nd if rel.get(d) in (0, 1) and v is not None and v > -3000]   # 0 tốt, 1 tạm; 2 tuyết, 3 mây → bỏ
        return {"pts": good, "n_all": len(nd)}
    r = _cache_rw("ndvi_%.4f_%.4f_%d.json" % (lat, lon, years), run, 30)
    return _layer_from_points("ndvi", [(dt.date.fromisoformat(d), v) for d, v in r["pts"]], "mean", lat, lon,
                              {"qa_kept_pct": round(100.0 * len(r["pts"]) / max(1, r["n_all"]), 1), "retrieved_at": r.get("retrieved_at"),
                               "note": "Pixel 250 m (~6 ha) có thể lẫn nhiều thửa nhỏ → kết luận ở mức tiểu vùng. Đã bỏ quan sát mây/tuyết (pixel reliability ≥ 2)."})

def auto_lst(lat, lon, years=AUTO_YEARS):
    lat, lon = round(lat, 4), round(lon, 4)
    d1 = dt.date.today()
    d0 = dt.date(d1.year - years, 1, 1)

    def run():
        raw = _ornl_band("MOD11A2", "LST_Day_1km", lat, lon, d0.isoformat(), d1.isoformat())
        return {"pts": [(d.isoformat(), v * 0.02 - 273.15) for d, v in raw if v and v > 7500]}   # ×0,02 = K; 0 = không có dữ liệu
    r = _cache_rw("lst_%.4f_%.4f_%d.json" % (lat, lon, years), run, 30)
    return _layer_from_points("lst", [(dt.date.fromisoformat(d), v) for d, v in r["pts"]], "mean", lat, lon,
                              {"retrieved_at": r.get("retrieved_at"), "note": "Nhiệt độ BỀ MẶT ban ngày (đất/tán lá), thường cao hơn nhiệt độ không khí vài độ."})

# ---- GPM IMERG Final Monthly qua GES DISC OPeNDAP (token Earthdata)
IMERG_M = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGM.07/%d/3B-MO.MS.MRG.3IMERG.%d%02d01-S000000-E235959.%02d.%s.HDF5.ascii?precipitation[0:0][%d:%d][%d:%d]"

def auto_gpm(lat, lon, years=None):
    if not EARTHDATA_TOKEN:
        raise AutoError("Chưa có EARTHDATA_TOKEN trong .env — cần token NASA Earthdata (miễn phí) để lấy mưa GPM IMERG.")
    import calendar
    import concurrent.futures as cf
    y1 = dt.date.today().year - 1
    y0 = y1 - (years or POWER_YEARS) + 1
    i = int(round((lon + 179.95) / 0.1)) % 3600            # lưới IMERG: kinh độ trước, tâm ô −179,95 … 179,95
    j = max(0, min(1799, int(round((lat + 89.95) / 0.1))))
    glat, glon = round(-89.95 + 0.1 * j, 2), round(-179.95 + 0.1 * i, 2)

    def one(ym):
        y, m = ym
        for ver in ("V07B", "V07C", "V07A"):
            try:
                txt = _xget(IMERG_M % (y, y, m, m, ver, i, i, j, j), timeout=60, raw=True, headers={"Authorization": "Bearer " + EARTHDATA_TOKEN})
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                if e.code in (401, 403):
                    raise AutoError("GES DISC từ chối token (HTTP %d): kiểm tra token còn hạn và đã cấp quyền 'NASA GESDISC DATA ARCHIVE'." % e.code)
                return None                                  # lỗi lẻ một tháng → bỏ tháng đó, báo tỉ lệ thiếu
            except AutoError:
                return None
            for line in txt.splitlines():
                if line.startswith("precipitation"):
                    v = num(line.split(",")[-1])
                    if v is not None and v >= 0:
                        return (dt.date(y, m, 1).isoformat(), v * 24 * calendar.monthrange(y, m)[1])   # mm/giờ (TB tháng) → mm/tháng
            return None
        return None                                          # tháng chưa có bản Final (trễ ~3–4 tháng)

    def run():
        months = [(y, m) for y in range(y0, y1 + 1) for m in range(1, 13)]
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            pts = [r for r in ex.map(one, months) if r]
        if len(pts) < 0.5 * len(months):
            raise AutoError("Chỉ lấy được %d/%d tháng IMERG — thử lại sau (máy chủ GES DISC có thể đang chậm)." % (len(pts), len(months)))
        return {"pts": pts, "grid": [glat, glon], "n_months_req": len(months)}
    r = _cache_rw("imerg_%.2f_%.2f_%d_%d.json" % (glat, glon, y0, y1), run, 120)
    return _layer_from_points("gpm", [(dt.date.fromisoformat(d), v) for d, v in r["pts"]], "sum", lat, lon,
                              {"grid": r["grid"], "retrieved_at": r.get("retrieved_at"),
                               "note": "Ô lưới IMERG 0,1° tâm (%.2f, %.2f). Tổng tháng = cường độ TB (mm/giờ) × số giờ trong tháng." % tuple(r["grid"])})

# ---- Tam giác kết cấu đất USDA (Soil Survey Manual) → 12 lớp; gom về 4 nhóm hình của công cụ (GIẢ ĐỊNH, ghi rõ trên UI)
def usda_texture(sand, silt, clay):
    if silt + 1.5 * clay < 15: return "sand"
    if silt + 2 * clay < 30: return "loamy sand"
    if clay >= 40 and silt >= 40: return "silty clay"
    if clay >= 40 and sand <= 45: return "clay"
    if clay >= 35 and sand > 45: return "sandy clay"
    if 27 <= clay < 40 and sand <= 20: return "silty clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45: return "clay loam"
    if 20 <= clay < 35 and silt < 28 and sand > 45: return "sandy clay loam"
    if silt >= 80 and clay < 12: return "silt"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12): return "silt loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52: return "loam"
    return "sandy loam"

USDA_VI = {"sand": "Cát", "loamy sand": "Cát pha thịt", "sandy loam": "Thịt pha cát", "loam": "Thịt", "silt loam": "Thịt pha limon (bột)",
           "silt": "Limon (bột)", "sandy clay loam": "Thịt pha sét – cát", "clay loam": "Thịt pha sét", "silty clay loam": "Thịt pha sét – limon",
           "sandy clay": "Sét pha cát", "silty clay": "Sét pha limon", "clay": "Sét"}
USDA_TO_GROUP = {"sand": "sand", "loamy sand": "sand", "sandy loam": "loam", "loam": "loam", "sandy clay loam": "loam", "clay loam": "loam",
                 "silt loam": "silt", "silt": "silt", "silty clay loam": "silt", "sandy clay": "clay", "silty clay": "clay", "clay": "clay"}

# ---- SoilGrids 2.0 → gợi ý hồ sơ đất (nông dân xác nhận/sửa)
def auto_soil(lat, lon):
    def run():
        q = [("lat", "%.5f" % lat), ("lon", "%.5f" % lon)] + [("property", p) for p in ("phh2o", "soc", "clay", "sand", "silt", "nitrogen", "cec")] \
            + [("depth", d) for d in ("0-5cm", "5-15cm", "15-30cm")] + [("value", v) for v in ("mean", "Q0.05", "Q0.95")]
        d = _xget("https://rest.isric.org/soilgrids/v2.0/properties/query?" + urllib.parse.urlencode(q), timeout=90)
        w = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
        props = {}
        for L in d["properties"]["layers"]:
            f = L["unit_measure"]["d_factor"]
            acc, ok = {"mean": 0.0, "Q0.05": 0.0, "Q0.95": 0.0}, True
            for dep in L["depths"]:
                for k in acc:
                    v = dep["values"].get(k)
                    if v is None:
                        ok = False
                    else:
                        acc[k] += v / f * w.get(dep["label"], 0) / 30.0      # trung bình có trọng số độ dày lớp 0–30 cm
            props[L["name"]] = {k: round(v, 3) for k, v in acc.items()} if ok else None
        return {"props": props}
    r = _cache_rw("soil_%.4f_%.4f.json" % (round(lat * 400) / 400, round(lon * 400) / 400), run, 365)
    p, vals = r["props"], {}
    if not any(p.values()):
        raise AutoError("SoilGrids không có dữ liệu tại điểm này (có thể là mặt nước/đô thị).")
    def rng(v, lo, hi, nd=1):
        return {"value": round(v, nd), "p05": round(lo, nd), "p95": round(hi, nd), "wide": (hi - lo) > 0.5 * abs(v) if v else True}
    if p.get("phh2o"):
        vals["ph"] = rng(p["phh2o"]["mean"], p["phh2o"]["Q0.05"], p["phh2o"]["Q0.95"])
    if p.get("soc"):           # SOC g/kg → C hữu cơ % (/10)
        vals["oc_pct"] = rng(p["soc"]["mean"] / 10, p["soc"]["Q0.05"] / 10, p["soc"]["Q0.95"] / 10, 2)
        vals["oc_pct"]["note"] = "C hữu cơ (%) = SOC (g/kg) / 10, trung bình 0–30 cm."
    if p.get("cec"):           # cmol(c)/kg sau khi chia d_factor
        vals["cec"] = rng(p["cec"]["mean"], p["cec"]["Q0.05"], p["cec"]["Q0.95"])
    if p.get("clay") and p.get("sand") and p.get("silt"):
        c, s, si = p["clay"]["mean"], p["sand"]["mean"], p["silt"]["mean"]
        t = (c + s + si) or 1
        c, s, si = 100 * c / t, 100 * s / t, 100 * si / t
        cls = usda_texture(s, si, c)
        vals["texture"] = {"value": cls, "usda": cls, "usda_vi": USDA_VI[cls], "sand": round(s), "silt": round(si), "clay": round(c),
                           "note": "Cấp cơ giới theo tam giác kết cấu đất USDA từ % cát/limon/sét SoilGrids (0–30 cm)."}
    if p.get("nitrogen"):
        vals["nitrogen_g_kg"] = {"value": round(p["nitrogen"]["mean"], 2),
                                 "note": "Đạm tổng số (g/kg). CHƯA quy ra thấp/vừa/cao vì chưa có ngưỡng có nguồn — mức đạm để nông dân nhập."}
    return {"values": vals, "source": AUTO_SOURCES["soil"], "lat": lat, "lon": lon, "retrieved_at": r.get("retrieved_at"),
            "not_available": ["depth_cm", "drainage", "base_sat", "ec"],
            "warning": "Giá trị từ MÔ HÌNH 250 m, không phải mẫu đất của ruộng. Khoảng 5–95% thường rất rộng → nên đo pH/chất hữu cơ thực tế."}

# ---- SSURGO qua Soil Data Access (USDA NRCS): độ sâu tầng cản, cơ giới, pH, thoát nước, CEC, bão hòa bazơ, C hữu cơ, EC, θ, độ dốc
SDA_URL = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"


def _sda(sql):
    body = json.dumps({"query": sql, "format": "JSON+COLUMNNAME"}).encode("utf-8")
    req = urllib.request.Request(SDA_URL, data=body, headers={"Content-Type": "application/json", "User-Agent": "FARM-ADAPT/%s (NASA Space Apps 2026)" % VERSION})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise AutoError("Không gọi được Soil Data Access: %s" % e)
    t = d.get("Table") or []
    return [dict(zip(t[0], row)) for row in t[1:]] if len(t) > 1 else []


def auto_ssurgo(lat, lon):
    def run():
        pt = "point(%.6f %.6f)" % (lon, lat)
        comp = _sda("SELECT TOP 1 mu.mukey, mu.muname, c.cokey, c.compname, c.comppct_r, c.drainagecl, c.slope_r, "
                    "(SELECT MIN(cr.resdept_r) FROM corestrictions cr WHERE cr.cokey = c.cokey) AS resdept_r "
                    "FROM mapunit mu INNER JOIN component c ON c.mukey = mu.mukey "
                    "WHERE mu.mukey IN (SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('%s')) "
                    "ORDER BY c.comppct_r DESC" % pt)
        if not comp:
            raise AutoError("SSURGO không có dữ liệu tại điểm này (SSURGO chỉ phủ Hoa Kỳ; ngoài Mỹ dùng SoilGrids và nhập tay).")
        c = comp[0]
        hz = _sda("SELECT h.hzdept_r, h.hzdepb_r, h.ph1to1h2o_r, h.cec7_r, h.om_r, h.ec_r, h.sumbases_r, h.wfifteenbar_r, h.wthirdbar_r, h.wsatiated_r, "
                  "(SELECT TOP 1 t.texcl FROM chtexturegrp tg INNER JOIN chtexture t ON t.chtgkey = tg.chtgkey WHERE tg.chkey = h.chkey AND tg.rvindicator = 'Yes') AS texcl "
                  "FROM chorizon h WHERE h.cokey = %d ORDER BY h.hzdept_r" % int(c["cokey"]))
        return {"comp": c, "hz": hz}
    r = _cache_rw("ssurgo_%.5f_%.5f.json" % (lat, lon), run, 365)
    c, hz = r["comp"], r["hz"]
    vals = {}

    def wavg(col, top=0, bot=30, f=1.0):          # trung bình theo độ dày, tầng 0–30 cm
        acc = n = 0.0
        for h in hz:
            a, b, v = num(h.get("hzdept_r")), num(h.get("hzdepb_r")), num(h.get(col))
            if a is None or b is None or v is None:
                continue
            o = max(0.0, min(b, bot) - max(a, top))
            acc, n = acc + v * o, n + o
        return acc / n * f if n > 0 else None
    for k, col, f, nd in (("ph", "ph1to1h2o_r", 1, 1), ("cec", "cec7_r", 1, 1), ("ec", "ec_r", 1, 2), ("theta_wp", "wfifteenbar_r", 0.01, 3),
                          ("theta_fc", "wthirdbar_r", 0.01, 3), ("theta_sat", "wsatiated_r", 0.01, 3)):
        v = wavg(col, f=f)
        if v is not None:
            vals[k] = {"value": round(v, nd)}
    om = wavg("om_r")
    if om is not None:
        vals["oc_pct"] = {"value": round(om / 1.724, 2), "note": "C hữu cơ = chất hữu cơ (om_r) / 1,724."}
    sb, cec = wavg("sumbases_r"), wavg("cec7_r")
    if sb is not None and cec:
        vals["base_sat"] = {"value": round(clamp(sb / cec * 100, 0, 100)), "note": "Bão hòa bazơ = tổng bazơ / CEC pH7 × 100."}
    tex = next((str(h.get("texcl")).strip().lower() for h in hz if h.get("texcl") and num(h.get("hzdept_r"), 99) < 30), None)
    if tex in TEXTURE_GROUP:
        vals["texture"] = {"value": tex, "usda_vi": USDA_VI.get(tex, tex)}
    dr = SSURGO_DRAIN.get(str(c.get("drainagecl") or "").strip().lower())
    if dr:
        vals["drainage"] = {"value": dr, "raw": c.get("drainagecl")}
    rd = num(c.get("resdept_r"))
    if rd is not None:
        vals["depth_cm"] = {"value": round(rd), "note": "Độ sâu tới tầng cản (corestrictions)."}
    else:
        deep = max([num(h.get("hzdepb_r"), 0) for h in hz] or [0])
        if deep:
            vals["depth_cm"] = {"value": round(deep), "note": "Không ghi nhận tầng cản: lấy độ sâu mô tả hết phẫu diện (≥ %d cm)." % round(deep)}
    if num(c.get("slope_r")) is not None:
        vals["slope_pct"] = {"value": round(num(c.get("slope_r")), 1), "note": "Độ dốc đại diện của thành phần đất (slope_r)."}
    return {"values": vals, "source": AUTO_SOURCES["ssurgo"], "lat": lat, "lon": lon, "retrieved_at": r.get("retrieved_at"),
            "unit": "%s — %s (%s%%)" % (c.get("muname"), c.get("compname"), c.get("comppct_r")),
            "warning": "Giá trị đại diện của thành phần đất chính trong đơn vị bản đồ, tầng 0–30 cm; nên đối chiếu mẫu đất thực tế."}


# ---- SRTM 30 m → gợi ý độ dốc
def auto_slope(lat, lon, step_m=150):          # bước 150 m: giảm ảnh hưởng nhiễu độ cao SRTM (vài mét) ở đồng bằng
    def run():
        dlat, dlon = step_m / 111320.0, step_m / (111320.0 * math.cos(math.radians(lat)))
        pts = [(lat, lon), (lat + dlat, lon), (lat - dlat, lon), (lat, lon + dlon), (lat, lon - dlon)]
        d = _xget("https://api.opentopodata.org/v1/srtm30m?locations=" + "|".join("%.6f,%.6f" % q for q in pts), timeout=30)
        z = [x.get("elevation") for x in d.get("results", [])]
        if len(z) != 5 or any(v is None for v in z):
            raise AutoError("SRTM không có độ cao tại điểm này.")
        return {"elev": z[0], "slope_pct": round(100 * math.hypot((z[3] - z[4]) / (2 * step_m), (z[1] - z[2]) / (2 * step_m)), 2)}
    r = _cache_rw("srtm_%.5f_%.5f_%d.json" % (lat, lon, step_m), run, 3650)
    pct = r["slope_pct"]
    cls = "flat" if pct < 2 else "gentle" if pct < 6 else "moderate" if pct < 15 else "steep"
    return {"elev_m": r["elev"], "slope_pct": pct, "slope_class": cls, "source": AUTO_SOURCES["slope"], "lat": lat, "lon": lon,
            "note": "Độ dốc tính từ chênh cao SRTM ±150 m quanh điểm. SRTM đo cả nhà/cây; ở đồng bằng sai số vài mét có thể lấn át độ dốc thật — nên xác nhận."}

AUTO_FUNCS = {"ndvi": auto_ndvi, "lst": auto_lst, "gpm": auto_gpm, "soil": auto_soil, "ssurgo": auto_ssurgo, "slope": auto_slope}
_JOBS = {}

def auto_job_start(kind, lat, lon):
    """Chạy nền (ORNL/IMERG có thể mất 1–3 phút lần đầu); có đệm thì xong ngay ở lần sau."""
    key = "%s_%.4f_%.4f" % (kind, lat, lon)
    with _LOCK:
        j = _JOBS.get(key)
        if j and (j["status"] == "running" or (j["status"] == "done" and time.time() - j["t"] < 600)):
            return key
        _JOBS[key] = {"status": "running", "t": time.time(), "kind": kind}

    def work():
        try:
            res = AUTO_FUNCS[kind](lat, lon)
            upd = {"status": "done", "result": res}
        except (AutoError, urllib.error.HTTPError, KeyError, ValueError) as e:
            upd = {"status": "error", "error": str(e)}
        except Exception as e:                                       # noqa — không để lỗi nguồn ngoài làm hỏng ứng dụng
            upd = {"status": "error", "error": "Lỗi không mong đợi: %s" % e}
        with _LOCK:
            _JOBS[key].update(upd, t=time.time())
    threading.Thread(target=work, daemon=True).start()
    return key

# ───────────────────────── BỘ MÁY ĐÁNH GIÁ (Bài toán 1): cây × vụ × thửa — SMCA 12 tiêu chí ─────────────────────────
# Mỗi tiêu chí quy về thang 0–1 (1 = phù hợp nhất); điểm tổng = Σ trọng số × điểm trên các tiêu chí ĐƯỢC CHỌN và ĐỦ DỮ LIỆU.
# K1 (lịch gieo – thu, chu kỳ sinh trưởng) là điều kiện loại trừ, xét trước khi chấm điểm. Python TÍNH, giao diện/AI chỉ hiển thị & diễn giải.
CRIT_ORDER = ["A1", "A2", "A3", "B1", "C1", "C2", "C3", "C4", "C5", "C6", "D1", "E1", "F1"]
GROUP_NAMES = {1: "Khí hậu – thời tiết", 2: "Nước – độ ẩm", 3: "Đất", 4: "Địa hình", 5: "Che phủ đất", 6: "Kinh tế"}
CRIT_DEF = {
    "A1": dict(g=1, vi="Nhiệt độ", unit="°C", need="Nhiệt độ không khí ngày (T2M) các năm lịch sử", auto="NASA POWER (tự lấy)", static=False,
               how="TB nhiệt độ các tháng trong vụ của cây, trung bình qua các năm → hàm hình thang theo CRD."),
    "A2": dict(g=1, vi="Lượng mưa năm", unit="mm", need="Mưa tháng các năm lịch sử", auto="GPM IMERG (tự lấy, cần EARTHDATA_TOKEN) · dự phòng NASA POWER", static=False,
               how="Tổng mưa 12 tháng, trung bình qua các năm → hình thang. Có tưới → 1."),
    "A3": dict(g=1, vi="Bức xạ mặt trời", unit="Kt", need="Chỉ số trong suốt khí quyển Kt (ALLSKY_KT)", auto="NASA POWER (tự lấy)", static=False,
               how="Kt TB trong vụ → Rất sáng (≥ 0,60) = 1 · Trời quang (0,50–0,60) = 0,5 · Nhiều mây (0,35–0,50) hoặc bóng râm (< 0,35) = 0."),
    "B1": dict(g=2, vi="Cân bằng nước", unit="", need="Mưa trong vụ + ẩm đất đầu vụ (θ) + θ điểm héo + độ sâu rễ", auto="IMERG/POWER + SMAP (CSV) hoặc POWER GWETROOT + SSURGO", static=False,
               how="Ya/Ym = 1 − Ky × (1 − ETa/ETm), ETa = mưa vụ + nước đất đầu vụ + tưới; giới hạn [0; 1]. Có tưới → 1."),
    "C1": dict(g=3, vi="Độ sâu tầng đất", unit="cm", need="Độ sâu tới tầng cản", auto="SSURGO (tự lấy – chỉ Hoa Kỳ)", static=True,
               how="Cây có bảng Sys: S1/S2/S3/N = 1/0,75/0,5/0; cây chỉ có ECOCROP: hình thang."),
    "C2": dict(g=3, vi="Thành phần cơ giới", unit="", need="Cấp cơ giới USDA tầng mặt", auto="SSURGO (Hoa Kỳ) · SoilGrids (toàn cầu)", static=True,
               how="Nhẹ / trung bình / nặng; nhóm tối ưu = 1, chịu đựng = 0,5, loại = 0."),
    "C3": dict(g=3, vi="pH, độ chua", unit="pH", need="pH (1:1 trong nước)", auto="SSURGO (Hoa Kỳ) · SoilGrids (toàn cầu)", static=True,
               how="Hàm hình thang theo CRD."),
    "C4": dict(g=3, vi="Thoát nước, úng", unit="", need="Cấp thoát nước (7 cấp)", auto="SSURGO (tự lấy – chỉ Hoa Kỳ)", static=True,
               how="Quá mức/hơi quá mức/tốt = 1; khá tốt 0,75; hơi kém 0,5; kém 0,25; rất kém 0. Cây ưa úng: đảo chiều."),
    "C5": dict(g=3, vi="Độ phì, CEC", unit="cmolc/kg", need="CEC (pH 7)", auto="SSURGO (Hoa Kỳ) · SoilGrids (toàn cầu)", static=True,
               how="Bảng CEC theo nhóm cây: kén đất (lúa mì, ngô) > 24 → 1, 16–24 → 0,75, 10–16 → 0,5, < 10 → 0; chịu đất nghèo (cao lương, đậu tương) > 24 → 1, 16–24 → 1, 10–16 → 0,75, < 10 → 0,5."),
    "C6": dict(g=3, vi="Độ mặn (EC)", unit="dS/m", need="Độ dẫn điện ECe", auto="SSURGO (tự lấy – chỉ Hoa Kỳ)", static=True,
               how="1 nếu EC ≤ ngưỡng bắt đầu giảm; 0 nếu ≥ ngưỡng mất trắng; ở giữa giảm tuyến tính (FAO)."),
    "D1": dict(g=4, vi="Độ dốc", unit="%", need="Độ dốc (%)", auto="SRTM 30 m (tự lấy) · SSURGO", static=True,
               how="0–4% S1 = 1; 4–8% S2 = 0,75; 8–16% S3 = 0,5; > 16% N = 0."),
    "E1": dict(g=5, vi="Che phủ đất", unit="C", need="Hệ số che phủ C (RUSLE) của cây", auto="Có sẵn trong CRD", static=True,
               how="Điểm = 1 − C (C càng thấp, cây che phủ đất càng tốt)."),
    "F1": dict(g=6, vi="Giá trị kinh tế", unit="USD", need="Diện tích ruộng A (ha), giá bán P (USD/tấn) và năng suất cơ sở Y_base (tấn/ha) của từng cây", auto="Bạn nhập (bước 2)", static=True,
               how="G = P × A × Y_base; điểm = (G − G_min)/(G_max − G_min) với G_min = 0 và G_max là G lớn nhất trong các cây đang xét (G ≤ 0 → 0). Không dùng CRD."),
}
GROUP_PROFILES = {   # bộ trọng số nhóm theo tài liệu (13/11/2026); trọng số nhóm Kinh tế là giả định của nhóm
    "equal":  ("Các nhóm như nhau", {1: 1 / 6, 2: 1 / 6, 3: 1 / 6, 4: 1 / 6, 5: 1 / 6, 6: 1 / 6}, "Mặc định khi chưa chọn ưu tiên"),
    "profit": ("Ưu tiên lợi nhuận", {1: .20, 2: .15, 3: .15, 4: .05, 5: .10, 6: .35}, "Ghi chú, FarmSTEPS, RotationARM, Organic"),
    "risk":   ("Ưu tiên giảm rủi ro", {1: .25, 2: .25, 3: .10, 4: .05, 5: .20, 6: .15}, "RotationARM, Review CRM, Ghi chú"),
    "water":  ("Ưu tiên tiết kiệm nước", {1: .20, 2: .40, 3: .15, 4: .05, 5: .10, 6: .10}, "Ghi chú"),
    "soil":   ("Ưu tiên cải thiện đất, chống xói mòn", {1: .10, 2: .15, 3: .35, 4: .20, 5: .15, 6: .05}, "Ghi chú, Organic, FarmSTEPS, UNCCD"),
    "food":   ("Ưu tiên dinh dưỡng, tự cung", {1: .25, 2: .25, 3: .20, 4: .05, 5: .20, 6: .05}, "FarmSTEPS, Meta, Organic"),
}
ASSUMPTIONS = [
    "A1 lúa mì đông: tháng ngủ đông (TB < 5°C) không tính vào nhiệt độ vụ — giả định để khớp ví dụ trong tài liệu (TB tháng 3–6).",
    "Tháng trong vụ của cây = từ ngày bắt đầu vụ, kéo dài min(độ dài vụ, số ngày gieo → thu điển hình theo lịch Kansas).",
    "C2: cách gom 12 cấp cơ giới USDA về 3 nhóm và điểm 0,5 cho nhóm chịu đựng là giả định.",
    "C1 cao lương, đậu tương: chỉ dùng cận dưới (sâu hơn 150 cm vẫn = 1).",
    "B1: khi chưa có SMAP, θ đầu vụ ≈ độ ẩm vùng rễ NASA POWER (GWETROOT, 0–1) × độ rỗng đất; khi chưa có θ điểm héo/đồng ruộng từ SSURGO, dùng bảng Rawls et al. (1982) theo cấp cơ giới.",
    "E1 cao lương tạm lấy bằng ngô (C = 0,38) vì nguồn Panagos et al. không có cao lương.",
    "K1: lịch gieo – thu là số liệu Kansas; ở vùng khác nên tắt K1 hoặc thay lịch địa phương (data/crops.json). Ngày gieo sớm nhất = ngày bắt đầu vụ do bạn khai báo (chưa dùng CDL/NDVI để suy ngày thu vụ trước).",
    "K1 sương giá: ngày sương giá đầu thu = trung vị qua các năm của ngày đầu tiên từ 1/7 có T2M_MIN ≤ 0°C (NASA POWER); cây (trừ lúa mì đông chịu rét) bị loại nếu ngày gieo + chu kỳ tối thiểu vượt qua ngày này.",
]
KANSAS_BBOX = (36.99, 40.01, -102.06, -94.58)


def in_kansas(lat, lon):
    return lat is not None and lon is not None and KANSAS_BBOX[0] <= lat <= KANSAS_BBOX[1] and KANSAS_BBOX[2] <= lon <= KANSAS_BBOX[3]


def profile_weights(pid):
    gw = GROUP_PROFILES.get(pid, GROUP_PROFILES["equal"])[1]
    n_in = {g: sum(1 for k in CRIT_ORDER if CRIT_DEF[k]["g"] == g) for g in GROUP_NAMES}
    return {k: gw[CRIT_DEF[k]["g"]] / n_in[CRIT_DEF[k]["g"]] for k in CRIT_ORDER}


def trap(x, tmin, olo, ohi, tmax):
    """Hàm hình thang: trong [olo, ohi] = 1; ≤ tmin hoặc ≥ tmax = 0; ở giữa tuyến tính."""
    if x is None:
        return None
    if olo <= x <= ohi:
        return 1.0
    if x <= tmin or x >= tmax:
        return 0.0
    if x < olo:
        return (x - tmin) / (olo - tmin)
    return (tmax - x) / (tmax - ohi)


def _lang_en():
    """Ngôn ngữ của yêu cầu hiện tại (tiêu đề X-Lang hoặc ?lang=) — chỉ ảnh hưởng định dạng số; chữ được dịch ở trình duyệt."""
    return has_request_context() and getattr(g, "lang", "vi") == "en"


def _fmt(x, nd=1):
    if x is None:
        return "—"
    s = ("%." + str(nd) + "f") % x
    return s if _lang_en() else s.replace(".", ",")


_MON_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _thou(x):
    s = "{:,.0f}".format(x)
    return s if _lang_en() else s.replace(",", ".")


# ---- mùa vụ do người dùng đặt: ngày bắt đầu (ngày/tháng, lặp lại hằng năm) + độ dài (ngày)
def _mkdate(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return dt.date(y, m, 28)


def clean_seasons(lst):
    out = []
    for i, s in enumerate(lst or []):
        d, m, L = int(num(s.get("start_d"), 1)), int(num(s.get("start_m"), 1)), int(num(s.get("days"), 120))
        if not (1 <= m <= 12 and 1 <= d <= 31 and 20 <= L <= 366):
            continue
        out.append({"id": str(s.get("id") or "s%d" % (i + 1)), "name": (s.get("name") or "Vụ %d" % (i + 1))[:40], "start_d": d, "start_m": m, "days": L, "crop": str(s.get("crop") or "")[:20]})
    return out


def season_calendar(seasons, today, pick=None):
    """Vụ hiện tại (chứa hôm nay) và vụ tới (bắt đầu sớm nhất sau hôm nay). Vụ cần ra quyết định = vụ người dùng chọn hoặc vụ tới."""
    rows = []
    for s in seasons:
        occ = []
        for y in (today.year - 1, today.year, today.year + 1):
            a = _mkdate(y, s["start_m"], s["start_d"])
            occ.append((a, a + dt.timedelta(days=s["days"])))
        cur = next(((a, b) for a, b in occ if a <= today < b), None)
        nxt = next(((a, b) for a, b in occ if a > today), None)
        rows.append(dict(s, cur=cur, nxt=nxt))
    cur = [r for r in rows if r["cur"]]
    up = sorted([r for r in rows if r["nxt"]], key=lambda r: r["nxt"][0])
    tgt = next((r for r in rows if r["id"] == pick), None) if pick and pick != "auto" else None
    tgt = tgt or (up[0] if up else None)

    def pack(r, which):
        a, b = r[which]
        return {"id": r["id"], "name": r["name"], "start": a.isoformat(), "end": (b - dt.timedelta(days=1)).isoformat(), "days": r["days"],
                "start_d": r["start_d"], "start_m": r["start_m"], "crop": r.get("crop") or "", "in_days": (a - today).days, "elapsed": (today - a).days if which == "cur" else None}
    overlaps = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i]["nxt"], rows[j]["nxt"]
            if a and b and a[0] < b[1] and b[0] < a[1]:
                overlaps.append([rows[i]["name"], rows[j]["name"]])
    return {"today": today.isoformat(), "current": [pack(r, "cur") for r in cur], "next": pack(up[0], "nxt") if up else None,
            "target": pack(tgt, "nxt") if tgt else None, "overlaps": overlaps}


def _in_circ(doy, a, b, tol=0):
    span = (b - a) % 365 + 2 * tol
    return (doy - (a - tol)) % 365 <= span


def first_frost_doy(clim, thr=0.0):
    """Ngày sương giá đầu thu (day-of-year, trung vị qua các năm): ngày đầu tiên từ 1/7 (BBC) hoặc 1/1 (NBC) có T2M_MIN ≤ thr."""
    TN, dates = clim.day["TN"], clim.day["dates"]
    south = (clim.raw.get("lat") or 0) < 0 if hasattr(clim, "raw") else False
    out = []
    for y in clim.years:
        st = "%d%s" % (y, "0101" if south else "0701")
        i = clim.didx.get(st)
        if i is None:
            continue
        j = i
        while j < len(dates) and dates[j][:4] == str(y):
            if TN[j] is not None and TN[j] <= thr:
                d = dates[j]
                out.append(dt.date(int(d[:4]), int(d[4:6]), int(d[6:])).timetuple().tm_yday)
                break
            j += 1
    if len(out) < max(3, len(clim.years) // 2):
        return None, len(out)
    return int(statistics.median(out)), len(out)


def k1_check(c, tgt, tol_days=7, enabled=True, frost=None):
    """K1 – không kịp thời vụ: (a) ngày bắt đầu vụ ngoài cửa sổ gieo; (b) vụ ngắn hơn chu kỳ tối thiểu; (c) không chín kịp trước sương giá đầu thu."""
    k = c["K1"]
    s0, s1 = _doy(*k["sow"][0]), _doy(*k["sow"][1])
    sd = _doy(tgt["start_d"], tgt["start_m"])
    sow_ok = _in_circ(sd, s0, s1, tol_days)
    dur_ok = tgt["days"] >= k["cycle"][0]
    frost_ok = True
    reasons = []
    if frost and not c["A1"].get("dormant_below"):
        F = frost
        mat = sd + k["cycle"][0]
        frost_ok = not (sd <= F < mat)
        if not frost_ok:
            md = dt.date(2001, 1, 1) + dt.timedelta(days=(mat - 1) % 365)
            fd = dt.date(2001, 1, 1) + dt.timedelta(days=F - 1)
            reasons.append("Gieo %02d/%02d + chu kỳ tối thiểu %d ngày → chín khoảng %02d/%02d, sau ngày sương giá đầu thu (~%02d/%02d)."
                           % (tgt["start_d"], tgt["start_m"], k["cycle"][0], md.day, md.month, fd.day, fd.month))
    if not sow_ok:
        reasons.insert(0, "Ngày bắt đầu vụ %02d/%02d nằm ngoài cửa sổ gieo %d/%d–%d/%d (cho phép lệch ±%d ngày)."
                       % (tgt["start_d"], tgt["start_m"], k["sow"][0][0], k["sow"][0][1], k["sow"][1][0], k["sow"][1][1], tol_days))
    if not dur_ok:
        reasons.insert(1 if not sow_ok else 0, "Vụ dài %d ngày, ngắn hơn chu kỳ sinh trưởng tối thiểu %d ngày." % (tgt["days"], k["cycle"][0]))
    return {"pass": (sow_ok and dur_ok and frost_ok) or not enabled, "sow_ok": sow_ok, "dur_ok": dur_ok, "frost_ok": frost_ok, "reasons": reasons, "enabled": enabled}


# ---- khí hậu theo cửa sổ vụ của từng cây (từ chuỗi NGÀY NASA POWER)
def _gpm_monthly(layers):
    g = (layers or {}).get("gpm")
    if not g or not g.get("series"):
        return None
    return {s_["ym"]: s_["v"] for s_ in g["series"]}


def window_climate(clim, sm, sd, L, dormant_below=None, gpm=None):
    import calendar
    per = []
    T, P, KT = clim.day["T"], clim.day["P"], clim.day["KT"]
    for y in clim.years:
        st = _mkdate(y, sm, sd)
        days = []
        for k in range(L):
            d = st + dt.timedelta(days=k)
            i = clim.didx.get(d.strftime("%Y%m%d"))
            if i is None:
                days = None
                break
            days.append((d, i))
        if not days:
            continue
        bym = {}
        for d, i in days:
            bym.setdefault((d.year, d.month), []).append(i)
        months = [{"y": yy, "m": mm, "n": len(ix), "T": mean(T[i] for i in ix), "P": sum(P[i] for i in ix)} for (yy, mm), ix in sorted(bym.items())]
        keep = [mo for mo in months if dormant_below is None or mo["T"] >= dormant_below] or months
        pg = None
        if gpm:
            acc, ok = 0.0, True
            for mo in months:
                v = gpm.get("%d-%02d" % (mo["y"], mo["m"]))
                if v is None:
                    ok = False
                    break
                acc += v * mo["n"] / calendar.monthrange(mo["y"], mo["m"])[1]
            pg = acc if ok else None
        kts = [KT[i] for _, i in days if KT[i] is not None]
        per.append({"y": y, "T": sum(mo["T"] * mo["n"] for mo in keep) / sum(mo["n"] for mo in keep), "P": sum(mo["P"] for mo in months), "Pg": pg,
                    "KT": mean(kts) if kts else None, "months": [mo["m"] for mo in months], "kept": [mo["m"] for mo in keep]})
    return per


def _annual_rain(clim, gpm):
    if gpm:
        by = {}
        for ym, v in gpm.items():
            by.setdefault(int(ym[:4]), []).append(v)
        yrs = sorted(y for y, a in by.items() if len(a) == 12)
        if len(yrs) >= 3:
            return {"base": mean(sum(by[y]) for y in yrs), "last": sum(by[yrs[-1]]), "last_year": yrs[-1], "src": "GPM IMERG Final Monthly (%d–%d)" % (yrs[0], yrs[-1]), "n": len(yrs)}
    a = clim.annual
    return {"base": mean(x["P"] for x in a), "last": a[-1]["P"], "last_year": a[-1]["year"], "src": "NASA POWER PRECTOTCORR (%d–%d)" % (clim.years[0], clim.years[-1]), "n": len(a)}


def soil_hydro(soil):
    tex = soil.get("texture")
    r = RAWLS.get(tex)
    out, src = {}, {}
    for k, idx in (("theta_sat", 0), ("theta_fc", 1), ("theta_wp", 2)):
        v = num(soil.get(k))
        if v is not None and v > 1.5:          # nhập % thể tích → m³/m³
            v = v / 100.0
        if v is not None and 0 < v < 1:
            out[k], src[k] = v, SRC_VI.get((soil.get("_src") or {}).get(k), "bạn nhập")
        elif r:
            out[k], src[k] = r[idx], "bảng Rawls 1982 theo cơ giới “%s”" % tex
    return out, src


class SeasonEnv:
    """Toàn bộ dữ liệu đầu vào của MỘT vụ trên MỘT thửa (dùng chung cho các cây) + Δ kịch bản."""
    def __init__(self, clim, farm, layers, tgt, deltas=None):
        self.clim, self.farm, self.layers, self.tgt = clim, farm, layers or {}, tgt
        d = deltas or {}
        self.dT, self.dP, self.dKt, self.dTh = num(d.get("dT"), 0.0) or 0.0, num(d.get("dP"), 0.0) or 0.0, num(d.get("dKt"), 0.0) or 0.0, num(d.get("dTheta"), 0.0) or 0.0
        self.base_mode = "last" if d.get("base") == "last" else "baseline"
        self.irrigated = bool(farm.get("irrigated"))
        s = dict(farm.get("soil") or {})
        s["_src"] = farm.get("soil_src") or {}
        self.soil = s
        self.slope = num(farm.get("slope_pct"))
        self.gpm = _gpm_monthly(self.layers)
        self.annual = _annual_rain(clim, self.gpm)
        self.hydro, self.hydro_src = soil_hydro(s)
        self._win = {}

    def win(self, c):
        L = min(self.tgt["days"], c["K1"]["window_days"])
        key = (L, c["A1"].get("dormant_below"))
        if key not in self._win:
            per = window_climate(self.clim, self.tgt["start_m"], self.tgt["start_d"], L, c["A1"].get("dormant_below"), self.gpm)
            if not per:
                self._win[key] = None
            else:
                pg = [x["Pg"] for x in per if x["Pg"] is not None]
                use_g = len(pg) >= 3
                last = per[-1]
                kts = [x["KT"] for x in per if x["KT"] is not None]
                self._win[key] = {"L": L, "n": len(per), "years": [per[0]["y"], per[-1]["y"]], "months": per[0]["months"], "kept": per[0]["kept"],
                                  "T": mean(x["T"] for x in per), "T_last": last["T"],
                                  "P": mean(pg) if use_g else mean(x["P"] for x in per), "P_last": (last["Pg"] if use_g and last["Pg"] is not None else last["P"]),
                                  "P_src": "GPM IMERG" if use_g else "NASA POWER", "KT": mean(kts) if kts else None, "KT_last": last["KT"], "last_year": last["y"]}
        return self._win[key]

    def theta0(self):
        """θ vùng rễ đầu vụ (m³/m³): baseline TB tháng gieo qua các năm; 'last' = tháng gieo năm gần nhất."""
        m = self.tgt["start_m"]
        sm = self.layers.get("smap")
        if sm and sm.get("clim") and sm["clim"][m - 1] is not None:
            vals = [s_["v"] for s_ in sm["series"] if int(s_["ym"][5:]) == m]
            v = sm["clim"][m - 1] if self.base_mode == "baseline" or not vals else vals[-1]
            return v + self.dTh, "SMAP L4 độ ẩm vùng rễ (lớp CSV, tháng %d)" % m
        sat = self.hydro.get("theta_sat")
        if sat is None:
            return None, None
        if self.base_mode == "last":
            e = [x for x in self.clim.ser if x["m"] == m][-1]
            gw = e["GW"]
        else:
            gw = self.clim.cm("GW", m - 1)
        return gw * sat + self.dTh, "NASA POWER GWETROOT tháng %d (%.2f) × độ rỗng %.2f" % (m, gw, sat)


def _val(env, base, last):
    return last if env.base_mode == "last" else base


def score_crop(c, env):
    """Điểm 0–1 của 12 tiêu chí cho một cây. s=None nghĩa là THIẾU DỮ LIỆU (không đưa vào điểm tổng)."""
    R, w, soil = {}, env.win(c), env.soil

    def put(k, s, v=None, vtxt="", rule="", src="", miss=None, cls=None):
        R[k] = {"s": None if s is None else round(clamp(s), 4), "v": v, "vtxt": vtxt, "rule": rule, "src": src, "miss": miss, "cls": cls}
    # A1 nhiệt độ
    a = c["A1"]
    if w:
        t = _val(env, w["T"], w["T_last"]) + env.dT
        dor = (" (bỏ tháng ngủ đông: chỉ tính %s)" % (", ".join(_MON_EN[m - 1] for m in w["kept"]) if _lang_en() else "T" + ",T".join(str(m) for m in w["kept"]))) if a.get("dormant_below") and len(w["kept"]) < len(w["months"]) else ""
        put("A1", trap(t, a["tol"][0], a["opt"][0], a["opt"][1], a["tol"][1]), round(t, 2), "%s°C TB trong vụ%s" % (_fmt(t), dor),
            "tối ưu %s–%s · chịu đựng %s–%s°C" % (a["opt"][0], a["opt"][1], a["tol"][0], a["tol"][1]),
            "NASA POWER T2M, %d năm (%d–%d)%s" % (w["n"], w["years"][0], w["years"][1], "" if env.base_mode == "baseline" else " — giá trị năm %d" % w["last_year"]))
    else:
        put("A1", None, miss="Chưa có chuỗi nhiệt độ đủ dài cho cửa sổ vụ này")
    # A2 mưa năm
    a = c["A2"]
    if env.irrigated:
        put("A2", 1.0, None, "Có tưới", "ngưỡng mưa ECOCROP chỉ áp dụng cho ruộng không tưới", "Chế độ tưới do bạn chọn")
    else:
        p = _val(env, env.annual["base"], env.annual["last"]) * (1 + env.dP / 100.0)
        put("A2", trap(p, a["tol"][0], a["opt"][0], a["opt"][1], a["tol"][1]), round(p), "%s mm/năm" % _fmt(p, 0),
            "tối ưu %s–%s · chịu đựng %s–%s mm" % (a["opt"][0], a["opt"][1], a["tol"][0], a["tol"][1]), env.annual["src"])
    # A3 bức xạ
    kt = None
    if w and w["KT"] is not None:
        kt = _val(env, w["KT"], w["KT_last"] if w["KT_last"] is not None else w["KT"]) + env.dKt
        cls = next(k for thr, k, _ in KT_CLASSES if kt >= thr)
        s = 1.0 if cls in c["A3"]["opt"] else 0.5 if cls in c["A3"]["tol"] else 0.0
        put("A3", s, round(kt, 3), "Kt %s → %s" % (_fmt(kt, 2), KT_VI[cls]), "Rất sáng ≥ 0,60 → 1 · Trời quang 0,50–0,60 → 0,5 · Nhiều mây / bóng râm → 0",
            env.clim.kt_src, cls=cls)
    else:
        put("A3", None, miss="Chưa có Kt (ALLSKY_KT) cho cửa sổ vụ")
    # B1 cân bằng nước — hàm phản ứng năng suất với nước của FAO
    b, zr = c["B1"], c["ZR"]["mid"]
    if env.irrigated:
        put("B1", 1.0, None, "Có tưới đủ (I = ETm)", "Ya/Ym = 1 − Ky(1 − ETa/ETm)", "Chế độ tưới do bạn chọn")
    elif not w:
        put("B1", None, miss="Chưa có mưa trong vụ")
    else:
        th0, th_src = env.theta0()
        wp, fc = env.hydro.get("theta_wp"), env.hydro.get("theta_fc")
        if th0 is None or wp is None:
            put("B1", None, miss="Thiếu %s" % " và ".join(x for x, ok in (("ẩm đất đầu vụ θ (SMAP hoặc cơ giới đất để ước tính)", th0 is not None), ("θ điểm héo (SSURGO hoặc cơ giới đất)", wp is not None)) if not ok))
        else:
            depth = num(soil.get("depth_cm"))
            zr_eff = min(zr, depth / 100.0) if depth else zr
            w0 = 1000.0 * max(0.0, th0 - wp) * zr_eff
            cap = 1000.0 * max(0.0, (fc or th0) - wp) * zr_eff
            w0c = min(w0, cap) if fc else w0
            pv = _val(env, w["P"], w["P_last"]) * (1 + env.dP / 100.0)
            eta = pv + w0c
            etm = b["etm_mid"]
            s = 1.0 if eta >= etm else 1 - b["ky"] * (1 - eta / etm)
            put("B1", s, round(eta), "ETa %s mm = mưa vụ %s + đất %s mm%s · ETm %d" % (_fmt(eta, 0), _fmt(pv, 0), _fmt(w0c, 0), " (đã chặn ở sức chứa %s mm)" % _fmt(cap, 0) if fc and w0 > cap else "", etm),
                "Ky %s · Zr %s m%s" % (_fmt(b["ky"], 2), _fmt(zr_eff, 2), " (giới hạn bởi tầng đất)" if zr_eff < zr else ""),
                "Mưa: %s · θ: %s · θ héo/đồng ruộng: %s" % (w["P_src"], th_src, env.hydro_src.get("theta_wp")))
    # C1 độ sâu tầng đất
    d1, k1 = num(soil.get("depth_cm")), c["C1"]
    if d1 is None:
        put("C1", None, miss="Thiếu độ sâu tầng đất")
    elif k1["kind"] == "sys":
        cls = next((cl for thr, cl in k1["classes"] if d1 > thr), "N")
        put("C1", SYS_SCORE[cls], d1, "%s cm → %s" % (_fmt(d1, 0), cls), k1["txt"], _srcname(soil, "depth_cm"), cls=cls)
    else:
        put("C1", trap(d1, k1["tol_min"], k1["opt_low"], 1e9, 1e10), d1, "%s cm" % _fmt(d1, 0), k1["txt"], _srcname(soil, "depth_cm"))
    # C2 cơ giới
    tex = soil.get("texture")
    if tex not in TEXTURE_GROUP:
        put("C2", None, miss="Thiếu cấp cơ giới đất")
    else:
        g, k2 = TEXTURE_GROUP[tex], c["C2"]
        s = 0.0 if tex in k2["excl"] else 1.0 if g in k2["opt"] else 0.5 if g in k2["tol"] else 0.0
        put("C2", s, tex, "%s (%s)" % (USDA_VI.get(tex, tex), TEXTURE_GROUP_VI[g]), k2["txt"], _srcname(soil, "texture"), cls=g)
    # C3 pH
    ph, k3 = num(soil.get("ph")), c["C3"]
    if ph is None:
        put("C3", None, miss="Thiếu pH")
    else:
        put("C3", trap(ph, k3["tol"][0], k3["opt"][0], k3["opt"][1], k3["tol"][1]), ph, "pH %s" % _fmt(ph), k3["txt"], _srcname(soil, "ph"))
    # C4 thoát nước
    dr = soil.get("drainage")
    if dr not in DRAIN_SCORE:
        put("C4", None, miss="Thiếu cấp thoát nước")
    else:
        s = DRAIN_SCORE[dr] if c["C4"]["habit"] == "dry" else 1 - DRAIN_SCORE[dr]
        put("C4", s, dr, "Thoát nước: %s" % DRAIN_VI[dr], c["C4"]["txt"], _srcname(soil, "drainage"))
    # C5 độ phì — bảng CEC theo nhóm cây (kén đất / chịu đất nghèo)
    cec, k5 = num(soil.get("cec")), c["C5"]
    if cec is None:
        put("C5", None, miss="Thiếu CEC")
    else:
        sc, lab = next((v, l) for thr, v, l in C5_TABLE[k5["kind"]] if cec > thr)
        put("C5", sc, cec, "CEC %s cmolc/kg (nhóm %s)" % (_fmt(cec), lab), "%s: %s" % (C5_GROUP_VI[k5["kind"]], " · ".join("%s → %s" % (l, _fmt(v, 2)) for _, v, l in C5_TABLE[k5["kind"]])),
            _srcname(soil, "cec"), cls=k5["kind"])
    # C6 độ mặn
    ec, k6 = num(soil.get("ec")), c["C6"]
    if ec is None:
        put("C6", None, miss="Thiếu độ mặn EC")
    else:
        s = 1.0 if ec <= k6["thr"] else 0.0 if ec >= k6["zero"] else 1 - (ec - k6["thr"]) / (k6["zero"] - k6["thr"])
        put("C6", s, ec, "EC %s dS/m" % _fmt(ec), "bắt đầu giảm %s · giảm 50%% %s · mất trắng %s" % (_fmt(k6["thr"]), _fmt(k6["half"]), _fmt(k6["zero"])), _srcname(soil, "ec"))
    # D1 độ dốc
    sl = env.slope
    if sl is None:
        put("D1", None, miss="Thiếu độ dốc")
    else:
        cls = "S1" if sl <= 4 else "S2" if sl <= 8 else "S3" if sl <= 16 else "N"
        put("D1", SYS_SCORE[cls], sl, "dốc %s%% → %s" % (_fmt(sl), cls), c["D1"]["txt"], _srcname({"_src": {"slope_pct": env.farm.get("slope_src")}}, "slope_pct"), cls=cls)
    # E1 che phủ đất
    e = c["E1"]
    put("E1", 1 - e["c"], e["c"], "C = %s%s" % (_fmt(e["c"], 2), " (giả định)" if e.get("assumed") else ""), "điểm = 1 − C", "CRD – Panagos et al. 2015")
    put_f1(R, c["id"], getattr(env, "econ", None))
    return R


SRC_VI = {"ssurgo": "SSURGO (USDA NRCS)", "soilgrids": "SoilGrids 2.0 (mô hình 250 m)", "srtm": "SRTM 30 m", "farmer": "bạn nhập", "preset": "ví dụ mẫu"}


def _srcname(soil, k):
    s = (soil.get("_src") or {}).get(k)
    return SRC_VI.get(s, s or "bạn nhập")


def norm_crit_weights(weights, enabled, available):
    """Chuẩn hóa trọng số trên các tiêu chí được chọn VÀ có dữ liệu. Trả (w, bỏ_vì_thiếu_dữ_liệu)."""
    w = {k: max(0.0, num((weights or {}).get(k), 0.0) or 0.0) for k in CRIT_ORDER}
    on = [k for k in CRIT_ORDER if (enabled or {}).get(k, True) and w[k] > 0]
    use = [k for k in on if k in available]
    tot = sum(w[k] for k in use)
    return ({k: (w[k] / tot if tot > 0 and k in use else 0.0) for k in CRIT_ORDER}, [k for k in on if k not in available])


def evaluate_season(clim, farm, layers, tgt, cfg, deltas=None, tgt_by_crop=None):
    """tgt_by_crop (chế độ chuỗi): {cid: (tgt, ngày gieo)} — mỗi cây đánh giá tại lượt gieo của riêng nó."""
    econ = econ_table(farm)
    env = SeasonEnv(clim, farm, layers, tgt or next(t for t, _ in tgt_by_crop.values() if t), deltas)
    env.econ = econ
    excluded = set(cfg.get("excluded") or [])
    k1_on, tol = cfg.get("k1", True) is not False, int(num(cfg.get("k1_tol"), 7) or 0)
    frost, _ = first_frost_doy(clim)
    prev = cfg.get("_prev")
    rows = []
    for cid, c in CROPS.items():
        if tgt_by_crop is not None:
            t_c, _ = tgt_by_crop.get(cid, (None, None))
            if t_c:
                e_c = SeasonEnv(clim, farm, layers, t_c, deltas)
                e_c.econ = econ
                k1 = k1_check(c, t_c, tol, k1_on, frost)
                rows.append({"id": cid, "vi": c["vi"], "group": c["group"], "k1": k1, "scores": score_crop(c, e_c), "window": e_c.win(c), "slot": t_c})
            else:
                k1 = {"pass": False, "sow_ok": False, "dur_ok": False, "frost_ok": True, "enabled": True,
                      "reasons": ["Không có lượt gieo nào của %s (cửa sổ gieo ± %d ngày, %d ngày gieo → thu) vừa trong khoảng thời gian của chuỗi." % (c["vi"], tol, c["K1"]["window_days"])]}
                rows.append({"id": cid, "vi": c["vi"], "group": c["group"], "k1": k1, "scores": score_crop(c, env), "window": env.win(c), "slot": None})
        else:
            rows.append({"id": cid, "vi": c["vi"], "group": c["group"], "k1": k1_check(c, tgt, tol, k1_on, frost), "scores": score_crop(c, env), "window": env.win(c)})
        r = rows[-1]
        r["user_excluded"] = cid in excluded
        ok34, why34 = k34_check(prev, cid, cfg) if tgt_by_crop is None else (True, [])
        r["k34"] = {"pass": ok34, "reasons": why34}
        E, has, rec = rot_E(prev, cid) if tgt_by_crop is None else (0.0, None, None)
        r["E"], r["E_has"], r["E_rec"] = (E if prev else None), has, rec
        r["M"] = round(1 + E / 100.0, 4)
    available = {k for k in CRIT_ORDER if all(r["scores"][k]["s"] is not None for r in rows)}
    w, dropped = norm_crit_weights(cfg.get("weights") or profile_weights("equal"), cfg.get("enabled"), available)
    for r in rows:
        r["total"] = round(sum(w[k] * r["scores"][k]["s"] for k in CRIT_ORDER if w[k] > 0), 4)
        r["V"] = round(r["total"] * r["M"], 4)
        r["contrib"] = {k: round(w[k] * r["scores"][k]["s"], 4) for k in CRIT_ORDER if w[k] > 0}
        r["feasible"] = r["k1"]["pass"] and not r["user_excluded"] and r["k34"]["pass"]
        r["excl"] = None if r["feasible"] else ("K1" if not r["k1"]["pass"] else "K2" if r["user_excluded"] else "K3/K4")
        used = [k for k in CRIT_ORDER if w[k] > 0]
        r["limiting"] = sorted([k for k in used if r["scores"][k]["s"] < 0.5], key=lambda k: r["scores"][k]["s"])
        r["strengths"] = [k for k in used if r["scores"][k]["s"] >= 0.9]
    feas = sorted([r for r in rows if r["feasible"]], key=lambda r: -r["V"])
    infeas = sorted([r for r in rows if not r["feasible"]], key=lambda r: -r["V"])
    for i, r in enumerate(feas):
        r["rank"] = i + 1
    for r in infeas:
        r["rank"] = None
    rob = {}
    for pid, (nm, _, _) in GROUP_PROFILES.items():
        wp, _ = norm_crit_weights(profile_weights(pid), cfg.get("enabled"), available)
        best = max(feas, key=lambda r: r["M"] * sum(wp[k] * r["scores"][k]["s"] for k in CRIT_ORDER if wp[k] > 0)) if feas else None
        rob[pid] = {"name": nm, "winner": best["id"] if best else None}
    return {"crops": feas + infeas, "weights": w, "frost_doy": frost, "dropped_missing": dropped, "available": sorted(available, key=CRIT_ORDER.index),
            "missing": {k: next((r["scores"][k]["miss"] for r in rows if r["scores"][k]["s"] is None), None) for k in CRIT_ORDER if k not in available},
            "robustness": rob, "irrigated": env.irrigated, "annual_rain": env.annual, "deltas": {"dT": env.dT, "dP": env.dP, "dKt": env.dKt, "dTheta": env.dTh, "base": env.base_mode},
            "theta0": env.theta0()[0] if not env.irrigated else None, "prev": prev, "econ": econ}


def moisture_now(clim, layers):
    """Ẩm đất tháng gần nhất có dữ liệu so với TB cùng tháng — chỉ để biết năm nay ẩm hay khô hơn bình thường."""
    sm = (layers or {}).get("smap")
    if sm and sm.get("series"):
        e = sm["series"][-1]
        m = int(e["ym"][5:])
        ref = sm["clim"][m - 1]
        if ref:
            return {"ym": e["ym"], "v": e["v"], "ref": ref, "pct": (e["v"] / ref - 1) * 100, "src": "SMAP (CSV)"}
    e = clim.ser[-1]
    ref = clim.cm("GW", e["m"] - 1)
    return {"ym": "%d-%02d" % (e["y"], e["m"]), "v": e["GW"], "ref": ref, "pct": (e["GW"] / ref - 1) * 100 if ref else 0.0, "src": "NASA POWER GWETROOT"}


def plain_crop(r, crit_w):
    """Câu chữ đời thường: điểm mạnh, hạn chế, việc cần lưu ý."""
    good = ["%s: %s" % (CRIT_DEF[k]["vi"], r["scores"][k]["vtxt"]) for k in r["strengths"][:4]]
    bad = ["%s: %s (điểm %s)" % (CRIT_DEF[k]["vi"], r["scores"][k]["vtxt"], _fmt(r["scores"][k]["s"], 2)) for k in r["limiting"]]
    watch = list(r["k1"]["reasons"]) + (["K2: bạn đã loại cây này khỏi danh sách."] if r["user_excluded"] else []) + list((r.get("k34") or {}).get("reasons") or [])
    return {"good": good, "bad": bad, "watch": watch}


def _prev_crop(farm, seasons, cal, today):
    prev = farm.get("prev_crop")
    if not prev and cal:      # cây vụ trước = cây của vụ đang diễn ra; nếu không có thì của vụ gần nhất đã kết thúc
        if cal["current"]:
            prev = cal["current"][0].get("crop")
        if not prev:
            past = []
            for s_ in seasons:
                for y in (today.year - 1, today.year):
                    a = _mkdate(y, s_["start_m"], s_["start_d"])
                    b = a + dt.timedelta(days=s_["days"])
                    if b <= today:
                        past.append((b, s_.get("crop") or ""))
            prev = max(past)[1] if past else None
    return prev if (prev in CROPS or prev == "fallow") else None


def run_evaluate(p):
    farm = p.get("farm") or {}
    lat, lon = num(farm.get("lat")), num(farm.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Chưa có vị trí ruộng hợp lệ (bước 1).")
    mode = "chain" if farm.get("mode") == "chain" else "next"
    today = _parse_date(p.get("today") or "") or dt.date.today()
    cfg = dict(p.get("cfg") or {})
    clim, note = get_clim(lat, lon)
    layers = p.get("layers") or {}
    chain = None
    if mode == "chain":
        ch = chain_cfg(farm)
        L = (ch["end"] - ch["start"]).days + 1
        tgt = {"id": "chain", "name": "Chuỗi luân canh", "start": ch["start"].isoformat(), "end": ch["end"].isoformat(), "days": L,
               "start_d": ch["start"].day, "start_m": ch["start"].month, "crop": "", "in_days": (ch["start"] - today).days, "elapsed": None}
        cal = {"today": today.isoformat(), "current": [], "next": tgt, "target": tgt, "overlaps": []}
        prev = ch["prev"]
        tbc = chain_base_targets(ch, cfg)
        base = evaluate_season(clim, farm, layers, None, cfg, None, tbc)
        chain = run_chain(clim, farm, layers, cfg, base, ch)
        scen = None
        d = p.get("deltas") or {}
        if any(abs(num(d.get(k), 0) or 0) > 1e-9 for k in ("dT", "dP", "dKt", "dTheta")) or d.get("base") == "last":
            scen = evaluate_season(clim, farm, layers, None, cfg, d, tbc)
            scen["chain"] = run_chain(clim, farm, layers, cfg, scen, ch, d)
    else:
        seasons = clean_seasons(farm.get("seasons"))
        if not seasons:
            raise ValueError("Chưa khai báo vụ nào (bước 2): cần ngày bắt đầu và độ dài vụ.")
        cal = season_calendar(seasons, today, farm.get("season_pick"))
        tgt = cal["target"]
        if not tgt:
            raise ValueError("Không xác định được vụ cần ra quyết định.")
        prev = _prev_crop(farm, seasons, cal, today)
        cfg["_prev"] = prev
        base = evaluate_season(clim, farm, layers, tgt, cfg)
        d = p.get("deltas") or {}
        scen = None
        if any(abs(num(d.get(k), 0) or 0) > 1e-9 for k in ("dT", "dP", "dKt", "dTheta")) or d.get("base") == "last":
            scen = evaluate_season(clim, farm, layers, tgt, cfg, d)
    for res in (base, scen):
        if res:
            for r in res["crops"]:
                r.update(plain_crop(r, res["weights"]))
    warn = []
    if not in_kansas(lat, lon) and cfg.get("k1", True) is not False:
        warn.append("Ruộng nằm ngoài Kansas nhưng K1 đang dùng lịch gieo – thu của Kansas: nên tắt K1 hoặc thay lịch địa phương.")
    if cal["overlaps"]:
        warn.append("Các vụ chồng thời gian: " + "; ".join(" & ".join(x) for x in cal["overlaps"]) + ".")
    if clim.is_demo:
        warn.append("Đang dùng khí hậu MÔ PHỎNG (DEMO) vì không gọi được NASA POWER — không dùng để quyết định thật.")
    nodata = None
    if mode == "next" and prev:
        nodata = [r["vi"] for r in base["crops"] if r["id"] != prev and r.get("E_has") is False]
    return {"ok": True, "mode": mode, "season": cal, "target": tgt, "prev_crop": prev, "prev_crop_vi": cname(prev) if prev else None, "base": base, "scen": scen,
            "chain": chain, "rot_nodata": nodata, "climate_note": note, "is_demo": clim.is_demo, "climate_years": [clim.years[0], clim.years[-1]], "kt_src": clim.kt_src,
            "moisture_now": moisture_now(clim, layers), "warnings": warn, "assumptions": ASSUMPTIONS + ROT_ASSUMPTIONS, "in_kansas": in_kansas(lat, lon),
            "fallow": FALLOW, "disclaimer": DISCLAIMER}


def run_scenarios(p):
    """Kịch bản 2^n: baseline + mọi tổ hợp tăng/giảm của các tiêu chí đã chọn.
    Bài toán vụ tới: đơn vị so sánh là từng CÂY (xếp theo V). Bài toán chuỗi: đơn vị là từng CHUỖI luân canh (xếp theo Score(P))."""
    farm = p.get("farm") or {}
    sc = p.get("scen") or {}
    crit = [k for k in (sc.get("crit") or []) if k in SCEN_KEYS]
    if not crit:
        raise ValueError("Chọn ít nhất 1 tiêu chí biến động trong A1, A2, A3, B1.")
    lat, lon = num(farm.get("lat")), num(farm.get("lon"))
    if lat is None or lon is None:
        raise ValueError("Chưa có vị trí ruộng hợp lệ (bước 1).")
    today = _parse_date(p.get("today") or "") or dt.date.today()
    cfg = dict(p.get("cfg") or {})
    clim, _ = get_clim(lat, lon)
    layers = p.get("layers") or {}
    base_mode = "last" if sc.get("base") == "last" else "baseline"
    combos, pid, mid = scen_combos(crit, sc.get("mag") or {})
    if farm.get("mode") == "chain":
        ch = chain_cfg(farm)
        tbc = chain_base_targets(ch, cfg)

        def runc(d):
            ev = evaluate_season(clim, farm, layers, None, cfg, d, tbc)
            return chain_pack(run_chain(clim, farm, layers, cfg, ev, ch, d))
        base = runc({"base": base_mode})
        for cb in combos:
            cb["res"] = runc(dict(cb["deltas"], base=base_mode))
            cb["changed"] = cb["res"]["top"] != base["top"]
        tgt = {"name": "Chuỗi luân canh", "start": ch["start"].isoformat(), "end": ch["end"].isoformat()}
        return {"ok": True, "mode": "chain", "target": tgt, "prev_crop": ch["prev"], "base_mode": base_mode, "baseline": base, "combos": combos,
                "plus": pid, "minus": mid, "crit": crit, "is_demo": clim.is_demo}
    seasons = clean_seasons(farm.get("seasons"))
    if not seasons:
        raise ValueError("Chưa khai báo vụ nào (bước 2).")
    cal = season_calendar(seasons, today, farm.get("season_pick"))
    tgt = cal["target"]
    cfg["_prev"] = _prev_crop(farm, seasons, cal, today)

    def pack(res):
        F = [r for r in res["crops"] if r["feasible"]]
        return {"top": F[0]["id"] if F else None,
                "rows": [{"id": r["id"], "vi": r["vi"], "S": r["total"], "M": r["M"], "V": r["V"], "rank": r["rank"], "feasible": r["feasible"], "excl": r["excl"],
                          "clim": {k: r["scores"][k]["s"] for k in ("A1", "A2", "A3", "B1")}} for r in res["crops"]]}
    base = pack(evaluate_season(clim, farm, layers, tgt, cfg, {"base": base_mode}))
    for cb in combos:
        cb["res"] = pack(evaluate_season(clim, farm, layers, tgt, cfg, dict(cb["deltas"], base=base_mode)))
        cb["changed"] = cb["res"]["top"] != base["top"]
    return {"ok": True, "mode": "next", "target": tgt, "prev_crop": cfg["_prev"], "base_mode": base_mode, "baseline": base, "combos": combos, "plus": pid, "minus": mid,
            "crit": crit, "is_demo": clim.is_demo}


DISCLAIMER = ("FARM ADAPT là công cụ HỖ TRỢ: chỉ ra mức độ phù hợp dựa trên dữ liệu quan sát Trái Đất của NASA, dữ liệu đất mở và thông tin bạn nhập. "
              "Công cụ không thay thế kinh nghiệm của nông dân hay tư vấn của chuyên gia nông học địa phương. Giống, lịch gieo thực tế, thị trường, sâu bệnh, vốn và lao động vẫn cần phán đoán của con người.")


# Mọi lưu ý của công cụ — gom về trang cuối (Nguồn dữ liệu, lưu ý & AI)
NOTES = [
    {"g": "Chung", "items": ["FARM ADAPT là công cụ HỖ TRỢ, không thay thế kinh nghiệm của nông dân và tư vấn của chuyên gia nông học địa phương; giống, lịch gieo thực tế, thị trường, sâu bệnh, vốn và lao động vẫn cần phán đoán của con người.",
                             "Khi không gọi được NASA POWER, công cụ dùng khí hậu MÔ PHỎNG (DEMO) để chạy thử và gắn nhãn DEMO ở thanh bên — không dùng số này để quyết định."]},
    {"g": "Mùa vụ & điều kiện bắt buộc", "items": ["K1 dùng lịch gieo – thu của Kansas (K-State, USDA NASS); ruộng ở vùng khác nên tắt K1 hoặc thay lịch địa phương.",
                                                   "K2 là danh sách cây bạn không muốn trồng; cây bị loại vẫn được chấm điểm để tham khảo nhưng không xếp hạng.",
                                                   "Đất nghỉ luôn khả thi và không được chấm điểm phù hợp sinh thái."]},
    {"g": "Dữ liệu đất & địa hình", "items": ["SSURGO cho giá trị đại diện của thành phần đất chính trong đơn vị bản đồ, tầng 0–30 cm — nên đối chiếu mẫu đất thực tế.",
                                              "SoilGrids là mô hình dự đoán 250 m, có thể lệch nhiều ở từng thửa; nhóm tiêu chí C và D dùng dữ liệu tĩnh nên giống nhau ở mọi vụ.",
                                              "Độ dốc SRTM tính từ chênh cao ±150 m quanh điểm; ở đồng bằng sai số vài mét có thể lấn át độ dốc thật."]},
    {"g": "Kết quả & kịch bản", "items": ["Tiêu chí thiếu dữ liệu được tạm bỏ và chia lại trọng số cho các tiêu chí còn lại.",
                                          "Các mức Δ của kịch bản thời tiết hiện do người dùng kéo; sau này sẽ lấy từ ngưỡng của phần cảnh báo.",
                                          "Nếu mọi bộ ưu tiên đều ra cùng một cây thì kết quả khá chắc; nếu khác nhau, đó là quyết định đánh đổi — nên bàn với chuyên gia địa phương.",
                                          "Bộ trọng số theo ưu tiên là số khởi điểm; nên hiệu chỉnh bằng AHP hoặc phỏng vấn nông dân."]},
    {"g": "Giả định của mô hình", "items": ASSUMPTIONS},
    {"g": "Giám sát & cảnh báo", "items": "MON_LIMITS"},
]

# ───────────────────────── LUÂN CANH (Bài toán 2) + KINH TẾ F1 + RÀNG BUỘC K3/K4 + KỊCH BẢN 2^n ─────────────────────────
# Theo tài liệu “Mô tả phương pháp – Đề xuất cây trồng vụ tới bằng SMCA” (13/11/2026).
# V(c) = S(c,t,x) × M(p,c), M = 1 + E(p,c)/100 — chế độ cặp (vụ tới).
# Score(P) = (1/T)[S(c1) + Σ_{t≥2} S(ct)·M(c_{t−1},ct)] — chế độ chuỗi.
ROT_SOURCE = ("Mudare, S. et al. (2025). Crop rotations synergize yield, nutrition, and revenue: a meta-analysis. "
              "Nature Communications — Supplementary Table 5.")
ROT_URL = "https://www.nature.com/ncomms/"
# E(p,c): % thay đổi năng suất cây sau so với độc canh; [CI 95%], n; sig = khoảng tin cậy không chứa 0.
ROT_E = {
    ("wheat", "sorghum"): (21.2, -5.7, 55.9, 10), ("wheat", "maize"): (21.1, 5.8, 38.7, 40), ("wheat", "soybean"): (3.7, -10.0, 19.5, 21),
    ("sorghum", "maize"): (27.9, 7.6, 52.1, 10), ("sorghum", "soybean"): (7.3, -4.1, 20.2, 30),
    ("maize", "wheat"): (9.1, -3.1, 22.9, 49), ("maize", "sorghum"): (-7.4, -19.9, 7.1, 16), ("maize", "soybean"): (7.3, 0.8, 14.2, 237),
    ("soybean", "wheat"): (14.8, 2.0, 29.1, 42), ("soybean", "sorghum"): (18.5, 9.7, 28.0, 106), ("soybean", "maize"): (18.7, 12.8, 25.0, 746),
    ("fallow", "wheat"): (35.3, 23.4, 48.2, 293), ("fallow", "sorghum"): (11.5, -1.4, 25.9, 28), ("fallow", "maize"): (31.0, 16.0, 48.0, 31),
}
ROT_ROWS = ["wheat", "sorghum", "maize", "soybean", "fallow"]
ROT_COLS = ["wheat", "sorghum", "maize", "soybean"]
FALLOW_SKIP_NOTE = ("Đất nghỉ trong chuỗi = bỏ qua một lượt gieo của cây kế tiếp (cây đó gieo vào cửa sổ gieo của năm sau). "
                    "Khoảng trống tự nhiên giữa ngày thu và ngày gieo kế tiếp (ví dụ qua mùa đông) KHÔNG coi là đất nghỉ.")
ROT_ASSUMPTIONS = [
    "Hiệu ứng luân canh E(p,c) lấy từ Mudare et al. (2025) — trung bình toàn cầu, chưa riêng cho Kansas; dùng cả các cặp chưa có ý nghĩa thống kê.",
    "Cặp không có dữ liệu (cao lương → lúa mì, đất nghỉ → đậu tương): E = 0 (M = 1) và được báo trên giao diện.",
    "Chế độ cặp: cây vụ trước = cây của vụ đang diễn ra; không có thì lấy cây của vụ gần nhất đã kết thúc; chưa khai báo → M = 1.",
    "Chế độ chuỗi: vụ đầu chuỗi không nhân M (giả định không có cây trước); K3, K4 vẫn xét cặp cây vụ trước của thửa → cây đầu chuỗi.",
    "Chế độ chuỗi: mỗi cây chiếm số ngày gieo → thu điển hình theo lịch Kansas trong CRD; gieo vào ngày sớm nhất hợp lệ trong cửa sổ gieo (± độ lệch K1).",
    FALLOW_SKIP_NOTE,
    "Chỉ giữ chuỗi “đầy”: sau cây cuối không còn cây nào gieo và thu kịp trước ngày kết thúc; phần thời gian còn lại là đất nghỉ tự nhiên.",
    "Vụ đất nghỉ không cộng điểm S và không tính vào T, nhưng ảnh hưởng cây sau qua M(đất nghỉ, c).",
    "F1: G = P × A × Y_base; chuẩn hóa G/G_max trên 4 cây ứng viên (G ≤ 0 → 0). Trong chuỗi, mỗi cây dùng F1 của chính nó; tổng G của chuỗi hiển thị riêng.",
    "Kịch bản 2^n: Δ+ mặc định là tổ hợp “nóng – khô” (A1↑, A2↓, A3↑, B1↓) khi tiêu chí đầu tiên được chọn tăng theo hướng đó, Δ− là tổ hợp ngược lại.",
]


def rot_E(p, c):
    """(E %, có dữ liệu?, bản ghi) — p là cây trước (có thể 'fallow'), c là cây sau."""
    if not p or p == c:
        return 0.0, None, None
    e = ROT_E.get((p, c))
    if not e:
        return 0.0, False, None
    est, lo, hi, n = e
    return est, True, {"E": est, "lo": lo, "hi": hi, "n": n, "sig": lo > 0 or hi < 0}


def rot_matrix():
    rows = []
    for p in ROT_ROWS:
        cells = []
        for c in ROT_COLS:
            if p == c:
                cells.append({"to": c, "diag": True})
                continue
            est, has, rec = rot_E(p, c)
            cells.append(dict({"to": c, "has": bool(has)}, **(rec or {})))
        rows.append({"from": p, "vi": cname(p), "cells": cells})
    return {"rows": rows, "cols": [{"id": c, "vi": cname(c)} for c in ROT_COLS], "source": ROT_SOURCE, "url": ROT_URL,
            "note": "Hàng là cây trước, cột là cây sau. Mỗi ô: % thay đổi năng suất cây sau so với độc canh [khoảng tin cậy 95%], n = cỡ mẫu. "
                    "In đậm = có ý nghĩa thống kê (khoảng tin cậy không chứa 0). Ô “không có dữ liệu” được tính E = 0."}


# ---- F1 giá trị kinh tế
def econ_table(farm):
    """G = P × A × Y_base cho từng cây; điểm = G / G_max (G_min = 0). Thiếu A hoặc P/Y của cây nào → F1 thiếu dữ liệu."""
    A = num(farm.get("area_ha"))
    E = farm.get("econ") or {}
    rows, miss = {}, []
    for cid in CROPS:
        e = E.get(cid) or {}
        P, Y = num(e.get("price")), num(e.get("yield"))
        if A is None or A <= 0 or P is None or Y is None:
            miss.append(cid)
        rows[cid] = {"P": P, "Y": Y, "G": (P * A * Y) if (A and P is not None and Y is not None) else None}
    if A is None or A <= 0 or miss:
        return {"ok": False, "A": A, "rows": rows, "miss": miss}
    gmax = max(r["G"] for r in rows.values())
    for r in rows.values():
        r["s"] = (max(0.0, r["G"]) / gmax) if gmax and gmax > 0 else 0.0
    return {"ok": True, "A": A, "rows": rows, "gmax": gmax, "miss": []}


def put_f1(R, cid, econ):
    if not econ or not econ["ok"]:
        need = "diện tích ruộng (ha)" if not econ or not econ.get("A") else "giá bán và năng suất cơ sở của %s" % ", ".join(cname(x) for x in econ["miss"])
        R["F1"] = {"s": None, "v": None, "vtxt": "", "rule": "", "src": "", "miss": "Thiếu " + need + " (bước 2)", "cls": None}
        return
    r = econ["rows"][cid]
    R["F1"] = {"s": round(clamp(r["s"]), 4), "v": round(r["G"]), "vtxt": "G = %s USD/t × %s ha × %s t/ha = %s USD" % (_fmt(r["P"], 0), _fmt(econ["A"], 1), _fmt(r["Y"], 2), _thou(r["G"])),
               "rule": "điểm = G / G_max (G_max = %s USD)" % _thou(econ["gmax"]), "src": "Bạn nhập (bước 2)", "miss": None, "cls": None}


# ---- K3 / K4
def k34_check(prev, c, cfg):
    """K3: không trồng cùng một cây 2 vụ liền kề (đất nghỉ cắt quan hệ). K4: cặp cấm do người dùng khai báo."""
    reasons = []
    if not prev or prev == "fallow":
        return True, reasons
    if cfg.get("k3", True) is not False and prev == c:
        reasons.append("K3: không trồng %s hai vụ liền nhau trên cùng thửa." % cname(c))
    for pr in cfg.get("k4") or []:
        if isinstance(pr, (list, tuple)) and len(pr) == 2 and pr[0] == prev and pr[1] == c:
            reasons.append("K4: bạn đã cấm trồng %s sau %s." % (cname(c), cname(prev)))
    return not reasons, reasons


# ---- chế độ chuỗi
def _sow_dates(c, after, tol):
    """Ngày gieo sớm nhất ≥ after nằm trong cửa sổ gieo (± tol) — và lượt của năm kế tiếp (dùng cho đất nghỉ)."""
    k = c["K1"]
    out = []
    for y in range(after.year - 1, after.year + 3):
        a = _mkdate(y, k["sow"][0][1], k["sow"][0][0]) - dt.timedelta(days=tol)
        b = _mkdate(y, k["sow"][1][1], k["sow"][1][0]) + dt.timedelta(days=tol)
        if b < a:
            b = _mkdate(y + 1, k["sow"][1][1], k["sow"][1][0]) + dt.timedelta(days=tol)
        if b >= after:
            out.append(max(a, after))
    return sorted(out)


def _frost_ok(c, sow, frost):
    if not frost or c["A1"].get("dormant_below"):
        return True
    sd = sow.timetuple().tm_yday
    return not (sd <= frost < sd + c["K1"]["cycle"][0])


def chain_slot_tgt(c, sow):
    L = c["K1"]["window_days"]
    return {"id": "chain", "name": "Chuỗi", "start_d": sow.day, "start_m": sow.month, "days": L, "start": sow.isoformat(),
            "end": (sow + dt.timedelta(days=L - 1)).isoformat(), "in_days": None, "elapsed": None, "crop": ""}


def run_chain(clim, farm, layers, cfg, base, ch, deltas=None):
    """Sinh mọi chuỗi hợp lệ trong [start, end]; xếp theo Score(P)."""
    start, end = ch["start"], ch["end"]
    prep, tol = ch["prep"], int(num(cfg.get("k1_tol"), 7) or 0)
    if cfg.get("k1", True) is False:
        tol = 0
    w = base["weights"]
    econ = econ_table(farm)
    frost, _ = first_frost_doy(clim)
    excluded = set(cfg.get("excluded") or [])
    cache = {}

    def S(cid, sow):
        key = (cid, sow.month, sow.day)
        if key not in cache:
            env = SeasonEnv(clim, farm, layers, chain_slot_tgt(CROPS[cid], sow), deltas)
            sc = score_crop(CROPS[cid], env)
            put_f1(sc, cid, econ)
            cache[key] = round(sum(w[k] * sc[k]["s"] for k in CRIT_ORDER if w.get(k, 0) > 0 and sc[k]["s"] is not None), 4)
            S.full[key] = {k: {f: sc[k].get(f) for f in ("s", "vtxt", "rule", "src", "miss")} for k in CRIT_ORDER if w.get(k, 0) > 0}
        return cache[key]
    S.full = {}

    results, count, LIMIT = [], [0], 120000

    def dfs(d, prev, items, fallow_before):
        if count[0] > LIMIT:
            return
        crops = [x for x in items if x["kind"] == "crop"]
        count[0] += 1
        grew = False
        for cid, c in CROPS.items():
            if cid in excluded:
                continue
            sows = _sow_dates(c, d, tol)
            if not sows:
                continue
            for fallow in (False, True):
                if fallow and not crops:
                    continue            # không có đất nghỉ ở đầu chuỗi
                if fallow and len(sows) < 2:
                    continue
                sow = sows[1] if fallow else sows[0]
                harv = sow + dt.timedelta(days=c["K1"]["window_days"])
                if harv > end or not _frost_ok(c, sow, frost):
                    continue
                p_eff = "fallow" if fallow else prev
                ok, _ = k34_check(prev if not crops else p_eff, cid, cfg)
                if not ok:
                    continue
                E, has, rec = rot_E(p_eff, cid) if crops else (0.0, None, None)
                it = {"kind": "crop", "id": cid, "vi": c["vi"], "sow": sow.isoformat(), "harvest": harv.isoformat(), "S": S(cid, sow),
                      "E": E if crops else None, "M": round(1 + E / 100.0, 4) if crops else 1.0, "has": has, "sig": rec["sig"] if rec else None,
                      "prev": p_eff if crops else None, "G": econ["rows"][cid]["G"] if econ["ok"] else None}
                new = list(items)
                if fallow:
                    new.append({"kind": "fallow", "id": "fallow", "vi": "Đất nghỉ", "from": d.isoformat(), "to": (sow - dt.timedelta(days=1)).isoformat()})
                new.append(it)
                grew = True
                dfs(harv + dt.timedelta(days=prep), cid, new, fallow)
        if crops and not grew:          # chỉ giữ chuỗi “đầy”: không xếp thêm được cây nào trước ngày kết thúc
            T = len(crops)
            tot = sum(x["S"] * (x["M"] if i > 0 else 1.0) for i, x in enumerate(crops))
            results.append({"score": round(tot / T, 4), "T": T, "items": [dict(x) for x in items],
                            "G": round(sum(econ["rows"][x["id"]]["G"] for x in crops)) if econ["ok"] else None})

    dfs(start, ch.get("prev") or None, [], False)
    results.sort(key=lambda r: (-r["score"], -(r["G"] or 0), r["T"]))
    seen, uniq = set(), []
    for r in results:
        sig = tuple((x["id"], x.get("sow")) for x in r["items"])
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(r)
    for i, r in enumerate(uniq):
        r["rank"] = i + 1
    nodata = sorted({(x["prev"], x["id"]) for r in uniq[:50] for x in r["items"] if x["kind"] == "crop" and x.get("has") is False})
    out = {"chains": uniq[:50], "n_total": len(uniq), "truncated": count[0] > LIMIT, "start": start.isoformat(), "end": end.isoformat(), "prep": prep,
           "prev": ch.get("prev"), "prev_vi": cname(ch["prev"]) if ch.get("prev") else None, "econ_ok": econ["ok"], "area": econ.get("A"),
           "nodata_pairs": [{"from": a, "to": b, "vi": "%s → %s" % (cname(a), cname(b))} for a, b in nodata],
           "fallow_rule": FALLOW_SKIP_NOTE}
    if deltas is None and uniq:
        out["steps"] = _chain_steps(uniq, ch, cfg, tol, frost, excluded, w, econ, S)
    return out


def _dmy(d):
    return "%02d/%02d/%d" % (d.day, d.month, d.year)


def _chain_steps(uniq, ch, cfg, tol, frost, excluded, w, econ, S):
    """v0.9.4 — Bảng điểm từng bước của chuỗi tốt nhất: tại mỗi bước (mỗi cây / đất nghỉ), mọi phương án có thể chọn ở thời điểm đó,
    điểm từng tiêu chí, S, M, V = S × M và Score(P) tốt nhất của các chuỗi đi tiếp bằng phương án ấy — để thấy vì sao phương án được chọn."""
    best_items, end, prep = uniq[0]["items"], ch["end"], ch["prep"]
    ikey = lambda x: (x["id"], x.get("sow"))

    def best_after(prefix, ok):
        n = len(prefix)
        for r in uniq:                     # uniq đã xếp giảm dần theo Score(P) → chuỗi khớp đầu tiên là tốt nhất
            it = r["items"]
            if len(it) > n and [ikey(y) for y in it[:n]] == prefix and ok(it[n]):
                return r["score"]
        return None

    steps, d = [], ch["start"]
    for i, x in enumerate(best_items):
        prefix = [ikey(y) for y in best_items[:i]]
        crops_before = [y for y in best_items[:i] if y["kind"] == "crop"]
        prev = crops_before[-1]["id"] if crops_before else (ch.get("prev") or None)
        after_f = i > 0 and best_items[i - 1]["kind"] == "fallow"
        if crops_before and not after_f:
            d = dt.date.fromisoformat(crops_before[-1]["harvest"]) + dt.timedelta(days=prep)
        p_eff = "fallow" if after_f else prev
        opts = []
        for cid, c in CROPS.items():
            sows = _sow_dates(c, d, tol)
            sow = (sows[1] if len(sows) > 1 else None) if after_f else (sows[0] if sows else None)
            o = {"id": cid, "vi": c["vi"], "sow": None, "harvest": None, "scores": None, "S": None, "M": 1.0, "E": None, "has": None, "sig": None, "V": None}
            why = "K2: bạn đã loại cây này khỏi danh sách." if cid in excluded else None
            if sow is None:
                why = why or "Không có lượt gieo nào vừa cửa sổ gieo (K1) sau ngày %s." % _dmy(d)
            else:
                harv = sow + dt.timedelta(days=c["K1"]["window_days"])
                o["sow"], o["harvest"] = sow.isoformat(), harv.isoformat()
                o["S"] = S(cid, sow)
                o["scores"] = S.full[(cid, sow.month, sow.day)]
                if not why and harv > end:
                    why = "Không kịp thu hoạch trước ngày kết thúc chuỗi (%s)." % _dmy(end)
                if not why and not _frost_ok(c, sow, frost):
                    why = "Gặp sương giá đầu thu trước khi chín (K1)."
                if not why:
                    ok, rs = k34_check(prev if not crops_before else p_eff, cid, cfg)
                    why = None if ok else rs[0]
                if crops_before:
                    E, has, rec = rot_E(p_eff, cid)
                    o.update(E=E, has=has, sig=rec["sig"] if rec else None, M=round(1 + E / 100.0, 4))
                o["V"] = round(o["S"] * o["M"], 4)
            o["ok"], o["why"] = why is None, why
            o["best"] = best_after(prefix, lambda y, cid=cid, s0=o["sow"]: y["kind"] == "crop" and y["id"] == cid and y["sow"] == s0) if o["ok"] else None
            opts.append(o)
        if crops_before and not after_f:
            fb = best_after(prefix, lambda y: y["kind"] == "fallow")
            opts.append({"id": "fallow", "vi": "Đất nghỉ", "ok": fb is not None, "best": fb,
                         "why": None if fb is not None else "Không còn đủ thời gian để bỏ một lượt gieo trước ngày kết thúc."})
        steps.append({"kind": x["kind"], "chosen": x["id"], "date": d.isoformat(), "prev": prev, "prev_vi": cname(prev) if prev else None,
                      "after_fallow": after_f, "first": not crops_before, "sow": x.get("sow"), "harvest": x.get("harvest"), "options": opts})
    return steps


def chain_cfg(farm):
    ch = farm.get("chain") or {}
    a, b = _parse_date(ch.get("start") or ""), _parse_date(ch.get("end") or "")
    if not a or not b:
        raise ValueError("Chế độ chuỗi luân canh: cần ngày bắt đầu và ngày kết thúc (bước 2).")
    if (b - a).days < 90:
        raise ValueError("Khoảng thời gian của chuỗi quá ngắn (cần ít nhất 90 ngày).")
    if (b - a).days > 366 * 5:
        raise ValueError("Khoảng thời gian của chuỗi tối đa 5 năm.")
    prev = ch.get("prev") or None
    return {"start": a, "end": b, "prep": max(0, min(90, int(num(ch.get("prep"), 10) or 0))), "prev": prev if prev in CROPS or prev == "fallow" else None}


def chain_base_targets(ch, cfg):
    """Cho bảng điểm ở chế độ chuỗi: mỗi cây đánh giá tại lượt gieo sớm nhất của nó trong khoảng chuỗi."""
    tol = int(num(cfg.get("k1_tol"), 7) or 0)
    out = {}
    for cid, c in CROPS.items():
        sows = _sow_dates(c, ch["start"], tol)
        sow = next((s for s in sows if s + dt.timedelta(days=c["K1"]["window_days"]) <= ch["end"]), None)
        out[cid] = (chain_slot_tgt(c, sow), sow) if sow else (None, None)
    return out


# ---- kịch bản 2^n (A1, A2, A3, B1) — so sánh baseline · Δ+ · Δ−
SCEN_KEYS = {"A1": ("dT", "°C"), "A2": ("dP", "%"), "A3": ("dKt", ""), "B1": ("dTheta", "m³/m³")}
HOTDRY = {"A1": 1, "A2": -1, "A3": 1, "B1": -1}


def scen_combos(crit, mag):
    import itertools
    crit = [k for k in crit if k in SCEN_KEYS]
    out = []
    for signs in itertools.product((1, -1), repeat=len(crit)):
        d = {"dT": 0.0, "dP": 0.0, "dKt": 0.0, "dTheta": 0.0}
        lab = []
        for k, sg in zip(crit, signs):
            key = SCEN_KEYS[k][0]
            d[key] = sg * abs(num(mag.get(key), 0) or 0)
            lab.append("%s%s" % (k, "↑" if sg > 0 else "↓"))
        out.append({"id": "".join("p" if s > 0 else "m" for s in signs), "label": " ".join(lab), "deltas": d, "signs": dict(zip(crit, signs))})
    if not crit:
        return out, None, None
    first = crit[0]
    lead = HOTDRY[first]           # Δ+: tiêu chí đầu tiên TĂNG; các tiêu chí khác theo cùng xu hướng nóng – khô / mát – ẩm
    plus = {k: (1 if HOTDRY[k] * lead > 0 else -1) for k in crit}
    pid = "".join("p" if plus[k] > 0 else "m" for k in crit)
    mid = "".join("m" if plus[k] > 0 else "p" for k in crit)
    return out, pid, mid


ROT_LIMITS = [
    "Chỉ số tăng năng suất khi luân canh cây A → cây B (Mudare et al. 2025) có nhiều cặp chưa có ý nghĩa thống kê — chưa đảm bảo có tác động.",
    "Công thức kết hợp V = S × M và Score(P) chưa có dữ liệu thực nghiệm kiểm chứng.",
    "Vụ đầu chuỗi giả định không có cây trước (không nhân M); nhóm Đất (C) và Địa hình (D) giả định không đổi qua các vụ của chuỗi.",
    "SMAP đo trên ô 9 km và chỉ tới độ sâu 1 m: với cây rễ sâu hơn 1 m (lúa mì, ngô) phần nước bên dưới không được tính.",
    "ETm của B1 lấy giá trị giữa khoảng trong CRD, chưa tính riêng theo khí hậu từng thửa (có thể nâng cấp bằng Σ Kc × ET0 theo FAO-56).",
    "Bỏ tiêu chí độ ẩm đất lúc gieo vì đã nằm trong B1; mô hình không cảnh báo riêng rủi ro khó nảy mầm khi đất khô lúc gieo (đáng lưu ý với lúa mì đông gieo mùa thu).",
    "Trọng số nhóm Kinh tế trong các bộ ưu tiên là giả định, chưa có tài liệu làm cơ sở; trọng số tiêu chí con chia đều trong nhóm.",
]
NOTES.insert(len(NOTES) - 2, {"g": "Luân canh, kinh tế & hạn chế nghiên cứu", "items": ROT_ASSUMPTIONS + ROT_LIMITS})


def chain_key(ch):
    return "|".join("%s@%s" % (x["id"], x.get("sow", "")) for x in ch["items"])


def chain_pack(C, n=8):
    """Gói gọn kết quả chuỗi cho bảng so sánh kịch bản: đơn vị là CHUỖI luân canh."""
    rows = [{"key": chain_key(c), "label": " → ".join(x["vi"] for x in c["items"]), "ids": [x["id"] for x in c["items"]], "score": c["score"], "T": c["T"],
             "G": c.get("G"), "rank": c["rank"], "years": " → ".join(("%s/%s" % (x["sow"][5:7], x["sow"][2:4])) if x["kind"] == "crop" else "nghỉ" for x in c["items"])}
            for c in C["chains"][:n]]
    return {"top": rows[0]["key"] if rows else None, "top_label": rows[0]["label"] if rows else None, "rows": rows, "n_total": C["n_total"],
            "rank_of": {chain_key(c): c["rank"] for c in C["chains"]}, "score_of": {chain_key(c): c["score"] for c in C["chains"]}}

# ───────────────────────── GIÁM SÁT & CẢNH BÁO (GiamSat.md) ─────────────────────────
# Theo dõi A1, A2, A3, B1 trên thửa từ dữ liệu NASA POWER gần thời gian thực (độ trễ vài ngày), tính theo cửa sổ trượt.
# 2 phương pháp: (1) ngưỡng nông học theo CRD của cây trên thửa; (2) bất thường thống kê (phân vị so với cùng thửa, ±15 ngày, mọi năm).
# 3 mức: Chú ý → Cảnh báo → Nghiêm trọng. Gộp: mỗi yếu tố một cảnh báo, lấy mức cao nhất, kèm danh sách phương pháp đã báo.
MON_LEVELS = ["Bình thường", "Chú ý", "Cảnh báo", "Nghiêm trọng"]
MON_FACTORS = {
    "A1": {"vi": "Nhiệt độ", "unit": "°C", "win": "TB 7 ngày gần nhất", "var": "T2M", "src": "NASA POWER T2M"},
    "A2": {"vi": "Lượng mưa", "unit": "mm", "win": "Tổng 30 ngày gần nhất", "var": "PRECTOTCORR", "src": "NASA POWER PRECTOTCORR (hiệu chỉnh theo GPM IMERG)"},
    "A3": {"vi": "Bức xạ (Kt)", "unit": "", "win": "TB 7 ngày gần nhất", "var": "ALLSKY_KT", "src": "NASA POWER ALLSKY_KT"},
    "B1": {"vi": "Cân bằng nước", "unit": "", "win": "Ẩm vùng rễ mới nhất · Ya/Ym từ đầu vụ", "var": "GWETROOT", "src": "NASA POWER GWETROOT (+ SMAP nếu có)"},
}
MON_DEFAULT = {"factors": ["A1", "A2", "A3", "B1"], "methods": ["agro", "stat"], "margin_pct": 5.0, "p_watch": 10.0, "p_warn": 5.0, "channels": ["ui"]}
MON_LIMITS = [
    "Ngưỡng CRD là ngưỡng cho cả vụ, không phân theo giai đoạn sinh trưởng; cây nhạy nhất lúc trổ cờ, ra hoa nhưng phương pháp 1 chưa phản ánh được.",
    "Phương pháp 2 cần chuỗi lịch sử đủ dài; SMAP chỉ có từ 2015 nên phân vị của B1 kém tin cậy hơn A1–A3 (hiện B1 dùng GWETROOT của NASA POWER).",
    "Độ trễ dữ liệu NASA POWER vài ngày (ALLSKY_KT có thể trễ hơn) khiến cảnh báo chậm so với thực tế; chưa dùng dự báo thời tiết để báo trước.",
    "A2 theo ngưỡng nông học dùng tổng mưa 365 ngày gần nhất để so với ngưỡng mưa NĂM của ECOCROP; A2 theo thống kê dùng tổng 30 ngày.",
    "Lớp bản đồ dùng dịch vụ ảnh THEO THÁNG của NASA POWER (lưới ~0,5°), chỉ để xem; cảnh báo tính từ chuỗi NGÀY tại toạ độ thửa.",
    "Ví dụ trong tài liệu (lúa mì, m ≈ 2,8°C) tương ứng m = 10% bề rộng vùng chịu đựng; công cụ để mặc định 5% theo phần mô tả và cho phép chỉnh.",
    "Kênh email / thông báo đẩy mới lưu cấu hình, chưa gửi thật (cần hạ tầng triển khai).",
]
POWER_RECENT_VARS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "GWETROOT", "ALLSKY_KT"]


def power_recent(lat, lon, days=430):
    """Chuỗi NGÀY NASA POWER gần thời gian thực: từ (hôm nay − days) đến hôm nay. Ngày chưa có số (−999) để trống. Lưu đệm 6 giờ."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)

    def run():
        for VARS in (POWER_RECENT_VARS, [v for v in POWER_RECENT_VARS if v != "ALLSKY_KT"]):
            q = urllib.parse.urlencode({"parameters": ",".join(VARS), "community": "AG", "longitude": "%.4f" % lon, "latitude": "%.4f" % lat,
                                        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"})
            try:
                data = _http_json(POWER_URL + "?" + q, POWER_TIMEOUT)
            except urllib.error.HTTPError as e:
                if e.code in (400, 422) and "ALLSKY_KT" in VARS:
                    continue
                raise PowerError("Không gọi được NASA POWER: %s" % e)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                raise PowerError("Không gọi được NASA POWER: %s" % e)
            par = data["properties"]["parameter"]
            keys = sorted(par["T2M"].keys())
            V = {v: [(None if (par.get(v) or {}).get(k) is None or par[v][k] <= -990 else float(par[v][k])) for k in keys] for v in POWER_RECENT_VARS}
            return {"dates": keys, "v": V, "demo": False}
        raise PowerError("NASA POWER không trả dữ liệu gần đây.")
    return _cache_rw("recent_%.2f_%.2f_%s.json" % (round(lat * 4) / 4, round(lon * 4) / 4, end.isoformat()), run, 0.25)


def recent_from_clim(clim, days=430):
    """DEMO: dựng chuỗi 'gần đây' từ chính chuỗi khí hậu (lấy ngày cùng ngày-tháng ở năm cũ) — CHỈ để chạy thử khi không có mạng."""
    end = dt.date.today() - dt.timedelta(days=3)
    keys, V = [], {v: [] for v in POWER_RECENT_VARS}
    mp = {"T2M": "T", "T2M_MAX": "TX", "T2M_MIN": "TN", "PRECTOTCORR": "P", "GWETROOT": "GW", "ALLSKY_KT": "KT"}
    for k in range(days, -1, -1):
        d = end - dt.timedelta(days=k)
        y = clim.years[-1 - (d.year % 3)]
        i = clim.didx.get("%d%02d%02d" % (y, d.month, min(d.day, 28)))
        keys.append(d.strftime("%Y%m%d"))
        for v, kk in mp.items():
            V[v].append(clim.day[kk][i] if i is not None else None)
    return {"dates": keys, "v": V, "demo": True}


def _rolling(arr, n, how):
    out, acc, cnt, q = [None] * len(arr), 0.0, 0, []
    for i, x in enumerate(arr):
        q.append(x)
        if x is not None:
            acc += x
            cnt += 1
        if len(q) > n:
            y = q.pop(0)
            if y is not None:
                acc -= y
                cnt -= 1
        if len(q) == n and cnt >= max(1, int(n * 0.7)):
            out[i] = acc / cnt if how == "mean" else acc * n / cnt
    return out


def _pct(vals, x):
    if not vals or x is None:
        return None
    lo = sum(1 for v in vals if v < x)
    eq = sum(1 for v in vals if v == x)
    return 100.0 * (lo + 0.5 * eq) / len(vals)


def _q(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


class MonHist:
    """Phân phối lịch sử cùng thửa: chỉ số cửa sổ trượt (7 ngày, 30 ngày…) tại ±half ngày quanh cùng ngày-tháng, qua mọi năm."""
    def __init__(self, clim):
        self.clim = clim
        d = clim.day
        self.roll = {"A1": _rolling(d["T"], 7, "mean"), "A2": _rolling(d["P"], 30, "sum"), "A3": _rolling(d["KT"], 7, "mean"), "B1": list(d["GW"])}

    def values(self, key, md, half=15):
        out = []
        for y in self.clim.years:
            try:
                c = dt.date(y, md[0], min(md[1], 28))
            except ValueError:
                continue
            for o in range(-half, half + 1):
                i = self.clim.didx.get((c + dt.timedelta(days=o)).strftime("%Y%m%d"))
                if i is not None and self.roll[key][i] is not None:
                    out.append(self.roll[key][i])
        return out


def _agro_level(x, opt, tol, margin_frac):
    """Cách 1: trong tối ưu → 0; ra khỏi tối ưu → Chú ý; cách giới hạn chịu đựng ≤ m → Cảnh báo; vượt chịu đựng → Nghiêm trọng."""
    olo, ohi = opt
    tmin, tmax = tol
    width = (tmax - tmin) if tmax < 1e8 else (olo - tmin) * 2
    m = margin_frac * width
    if x < tmin or x > tmax:
        return 3, m
    if olo <= x <= ohi:
        return 0, m
    d = (x - tmin) if x < olo else (tmax - x)
    return (2 if d <= m else 1), m


def _stat_level(p, x, vals, p_watch, p_warn):
    if p is None:
        return 0
    if vals and (x < min(vals) or x > max(vals)):
        return 3
    if p <= p_warn or p >= 100 - p_warn:
        return 2
    if p <= p_watch or p >= 100 - p_watch:
        return 1
    return 0


def run_monitor(p):
    farm = p.get("farm") or {}
    lat, lon = num(farm.get("lat")), num(farm.get("lon"))
    if lat is None or lon is None:
        raise ValueError("Chưa chọn ruộng: hãy chọn vị trí ruộng ở bước 1.")
    cfg = dict(MON_DEFAULT, **(p.get("cfg") or {}))
    mfrac = max(0.0, min(50.0, num(cfg.get("margin_pct"), 5) or 0)) / 100.0
    pw, pk = num(cfg.get("p_watch"), 10) or 10, num(cfg.get("p_warn"), 5) or 5
    clim, note = get_clim(lat, lon)
    try:
        rec = power_recent(lat, lon) if not clim.is_demo else recent_from_clim(clim)
    except PowerError:
        if not DEMO_FALLBACK:
            raise
        rec = recent_from_clim(clim)
    dates, V = rec["dates"], rec["v"]
    roll = {"A1": _rolling(V["T2M"], 7, "mean"), "A2": _rolling(V["PRECTOTCORR"], 30, "sum"), "A3": _rolling(V["ALLSKY_KT"], 7, "mean"), "B1": list(V["GWETROOT"])}
    last = {k: max((i for i, x in enumerate(roll[k]) if x is not None), default=None) for k in roll}
    ok_idx = [i for i in last.values() if i is not None]
    if not ok_idx:
        raise PowerError("Chưa có dữ liệu NASA POWER gần đây cho điểm này.")
    as_of = dates[max(ok_idx)]
    hist = MonHist(clim)
    # cây trên thửa: cây của vụ đang diễn ra, nếu không có thì vụ tới; người dùng có thể chọn khác
    today = _parse_date(p.get("today") or "") or dt.date.today()
    seasons = clean_seasons(farm.get("seasons"))
    cal = season_calendar(seasons, today) if seasons else {"current": [], "next": None}
    cur = cal["current"][0] if cal.get("current") else None
    crop_id = cfg.get("crop") or ""
    crop_mode = "user" if crop_id else "season"
    if not crop_id and cur:                    # tự động: chỉ xét ngưỡng nông học khi cây ĐANG trong vụ
        crop_id = cur.get("crop") or ""
    crop = CROPS.get(crop_id)
    next_crop = CROPS.get(next((s_.get("crop") for s_ in seasons if cal.get("next") and s_["id"] == cal["next"]["id"]), "") or "")
    irrigated = bool(farm.get("irrigated"))
    out_f = {}
    for k, meta in MON_FACTORS.items():
        i = last[k]
        if i is None:
            out_f[k] = {"vi": meta["vi"], "value": None, "level": 0, "reason": "Chưa có dữ liệu gần đây", "methods": []}
            continue
        x = roll[k][i]
        d = dates[i]
        md = (int(d[4:6]), int(d[6:8]))
        vals = hist.values(k, md)
        sv = sorted(vals)
        base = _q(sv, 0.5)
        pc = _pct(vals, x)
        F = {"vi": meta["vi"], "unit": meta["unit"], "win": meta["win"], "src": meta["src"], "date": d, "value": round(x, 3), "baseline": None if base is None else round(base, 3),
             "p10": None if not sv else round(_q(sv, .1), 3), "p90": None if not sv else round(_q(sv, .9), 3), "pct": None if pc is None else round(pc, 1), "levels": {}}
        if k == "A2":
            j = len(V["PRECTOTCORR"])
            yr = [v for v in V["PRECTOTCORR"][max(0, j - 365):j] if v is not None]
            F["sum365"] = round(sum(yr) * 365 / max(1, len(yr)))
            if cur:
                a = cur["start"].replace("-", "")
                F["since_start"] = round(sum(v for dd, v in zip(dates, V["PRECTOTCORR"]) if dd >= a and v is not None))
        # phương pháp 2: thống kê
        if "stat" in cfg["methods"]:
            lv = _stat_level(pc, x, vals, pw, pk)
            dirn = "cao" if (pc or 50) >= 50 else "thấp"
            word = {"A1": ("nóng", "lạnh"), "A2": ("ướt", "khô"), "A3": ("nắng", "u ám"), "B1": ("ẩm", "khô")}[k][0 if dirn == "cao" else 1]
            F["levels"]["stat"] = {"lvl": lv, "label": "Bất thường thống kê", "word": word,
                                  "reason": ("%s %s — phân vị %s so với cùng giai đoạn %d năm (%s)" % (meta["win"], _fmt(x, 2 if k in ("A3", "B1") else 1), _fmt(pc, 0), len(clim.years),
                                             "thấp hơn mức thấp nhất từng ghi nhận" if vals and x < min(vals) else "cao hơn mức cao nhất từng ghi nhận" if vals and x > max(vals) else "trong phạm vi lịch sử"))}
        # phương pháp 1: ngưỡng nông học (cần biết cây)
        if "agro" in cfg["methods"] and crop:
            c = crop
            if k == "A1":
                if c["A1"].get("dormant_below") is not None and x < c["A1"]["dormant_below"]:
                    F["levels"]["agro"] = {"lvl": 0, "label": "Ngưỡng nông học", "reason": "%s đang ngủ đông (TB 7 ngày %s°C < %s°C) — không xét ngưỡng nhiệt." % (c["vi"], _fmt(x), _fmt(c["A1"]["dormant_below"]))}
                else:
                    lv, m = _agro_level(x, c["A1"]["opt"], c["A1"]["tol"], mfrac)
                    lim = c["A1"]["tol"][1] if x > c["A1"]["opt"][1] else c["A1"]["tol"][0]
                    F["levels"]["agro"] = {"lvl": lv, "label": "Ngưỡng nông học", "reason": "TB 7 ngày %s°C; tối ưu %s–%s, chịu đựng %s–%s°C của %s; còn %s°C tới giới hạn (m = %s°C)"
                                           % (_fmt(x), c["A1"]["opt"][0], c["A1"]["opt"][1], c["A1"]["tol"][0], c["A1"]["tol"][1], c["vi"].lower(), _fmt(abs(lim - x)), _fmt(m))}
            elif k == "A2" and not irrigated:
                y = F["sum365"]
                lv, m = _agro_level(y, c["A2"]["opt"], c["A2"]["tol"], mfrac)
                F["levels"]["agro"] = {"lvl": lv, "label": "Ngưỡng nông học", "reason": "Mưa 365 ngày %s mm; tối ưu %s–%s, chịu đựng %s–%s mm/năm của %s"
                                       % (_fmt(y, 0), c["A2"]["opt"][0], c["A2"]["opt"][1], c["A2"]["tol"][0], c["A2"]["tol"][1], c["vi"].lower())}
            elif k == "A3":
                lv, m = _agro_level(x, [0.60, 1.01], [0.50, 1.01], mfrac)
                cls = next(lab for thr, _, lab in KT_CLASSES if x >= thr)
                F["levels"]["agro"] = {"lvl": lv, "label": "Ngưỡng nông học", "reason": "Kt 7 ngày %s (%s); tối ưu ≥ 0,60 (rất sáng), chịu đựng ≥ 0,50 (trời quang)" % (_fmt(x, 2), cls.lower())}
            elif k == "B1" and not irrigated and cur:
                hyd, _ = soil_hydro(dict(farm.get("soil") or {}, _src=farm.get("soil_src") or {}))
                if hyd.get("theta_sat") and hyd.get("theta_wp"):
                    a = cur["start"].replace("-", "")
                    si = next((j for j, dd in enumerate(dates) if dd >= a), None)
                    if si is not None and V["GWETROOT"][si] is not None:
                        zr = c["ZR"]["mid"]
                        dep = num((farm.get("soil") or {}).get("depth_cm"))
                        zr = min(zr, dep / 100.0) if dep else zr
                        w0 = 1000 * max(0.0, V["GWETROOT"][si] * hyd["theta_sat"] - hyd["theta_wp"]) * zr
                        if hyd.get("theta_fc"):
                            w0 = min(w0, 1000 * max(0.0, hyd["theta_fc"] - hyd["theta_wp"]) * zr)
                        rain = sum(v for v in V["PRECTOTCORR"][si:] if v is not None)
                        el = (dt.date(int(as_of[:4]), int(as_of[4:6]), int(as_of[6:])) - dt.date(int(a[:4]), int(a[4:6]), int(a[6:]))).days + 1
                        etm = c["B1"]["etm_mid"] * min(1.0, el / max(1, c["K1"]["window_days"]))
                        sc = 1.0 if rain + w0 >= etm else clamp(1 - c["B1"]["ky"] * (1 - (rain + w0) / etm))
                        lv = 0 if sc >= 0.999 else 3 if sc <= 0 else 2 if sc <= mfrac else 1
                        F["b1_score"] = round(sc, 3)
                        F["levels"]["agro"] = {"lvl": lv, "label": "Ngưỡng nông học", "reason": "Từ đầu vụ (%d ngày): mưa %s + nước đất đầu vụ %s = %s mm so với nhu cầu %s mm của %s → Ya/Ym = %s"
                                               % (el, _fmt(rain, 0), _fmt(w0, 0), _fmt(rain + w0, 0), _fmt(etm, 0), c["vi"].lower(), _fmt(sc, 2))}
        lvls = [(v["lvl"], kk) for kk, v in F["levels"].items() if kk in cfg["methods"]]
        top = max(lvls) if lvls else (0, None)
        F["level"] = top[0] if k in cfg["factors"] else 0
        F["methods"] = [F["levels"][kk]["label"] for lv, kk in lvls if lv > 0]
        F["reason"] = F["levels"][top[1]]["reason"] if top[1] else "Không có phương pháp nào áp dụng được."
        if top[1] == "agro" and k in ("A1", "A2", "A3"):
            ref = {"A1": crop["A1"]["opt"] if crop else None, "A2": crop["A2"]["opt"] if crop else None, "A3": [0.6, 1.01]}[k]
            yv = F.get("sum365") if k == "A2" else x
            F["word"] = None if not ref else ({"A1": ("lạnh", "nóng"), "A2": ("khô", "ướt"), "A3": ("u ám", "nắng")}[k][0 if yv < ref[0] else 1] if not (ref[0] <= yv <= ref[1]) else None)
        elif top[1] == "agro" and k == "B1":
            F["word"] = "thiếu nước"
        else:
            F["word"] = (F["levels"].get("stat") or {}).get("word")
        out_f[k] = F
    alerts = sorted([dict(code=k, **{kk: v for kk, v in f.items() if kk in ("vi", "level", "methods", "reason", "word", "date")}) for k, f in out_f.items()
                     if k in cfg["factors"] and f.get("level", 0) > 0], key=lambda a: -a["level"])
    # chuỗi cho biểu đồ: N ngày gần nhất + dải phân vị lịch sử 10–50–90
    n = int(num(p.get("days"), 120) or 120)
    n = max(14, min(n, len(dates)))
    sl = slice(len(dates) - n, len(dates))
    band = {}
    for k in ("A1", "A2", "A3", "B1"):
        lo, mid, hi = [], [], []
        for d in dates[sl]:
            sv = sorted(hist.values(k, (int(d[4:6]), int(d[6:8])), 7))
            lo.append(None if not sv else round(_q(sv, .1), 3))
            mid.append(None if not sv else round(_q(sv, .5), 3))
            hi.append(None if not sv else round(_q(sv, .9), 3))
        band[k] = {"p10": lo, "p50": mid, "p90": hi}
    ser = {"dates": dates[sl], "A1": [None if x is None else round(x, 2) for x in roll["A1"][sl]], "A2": [None if x is None else round(x, 1) for x in roll["A2"][sl]],
           "A3": [None if x is None else round(x, 3) for x in roll["A3"][sl]], "B1": [None if x is None else round(x, 3) for x in roll["B1"][sl]],
           "P": V["PRECTOTCORR"][sl], "TX": V["T2M_MAX"][sl], "TN": V["T2M_MIN"][sl]}
    return {"ok": True, "as_of": as_of, "lag_days": (today - dt.date(int(as_of[:4]), int(as_of[4:6]), int(as_of[6:]))).days, "demo": bool(rec.get("demo")) or clim.is_demo,
            "crop": crop_id if crop else None, "crop_vi": crop["vi"] if crop else None, "crop_mode": crop_mode, "next_crop_vi": next_crop["vi"] if next_crop else None, "season": cur, "irrigated": irrigated, "factors": out_f, "alerts": alerts,
            "series": ser, "band": band, "cfg": cfg, "levels": MON_LEVELS, "limits": MON_LIMITS, "climate_years": [clim.years[0], clim.years[-1]], "climate_note": note}
NOTES[-1]["items"] = MON_LIMITS

# ───────────────────────── Trợ lý AI (Gemini REST, tùy chọn) ─────────────────────────
AI_TOTAL_TIMEOUT = int(os.environ.get("AI_TIMEOUT_S", "20") or 20)     # tổng thời gian chờ AI; quá hạn → dùng bản giải thích tại chỗ
AI_PER_CALL      = int(os.environ.get("AI_CALL_TIMEOUT_S", "25") or 25)

def _msgs_openai(system, contents):
    m = [{"role": "system", "content": system}]
    for c in contents:
        m.append({"role": "assistant" if c["role"] == "model" else "user", "content": "".join(x.get("text", "") for x in c["parts"])})
    return m

def _post_json(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=dict({"Content-Type": "application/json"}, **headers))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _call_gemini(system, contents, max_tokens, temperature):
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    models = ([os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else []) + ["gemini-2.5-flash", "gemini-flash-latest"]
    last = None
    for mdl in models:
        gc = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if "2.5" in mdl:
            gc["thinkingConfig"] = {"thinkingBudget": 0}               # tắt 'suy nghĩ' để trả lời nhanh
        try:
            d = _post_json("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % mdl, {"x-goog-api-key": key},
                           {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gc}, AI_PER_CALL)
            txt = "".join(x.get("text", "") for x in d["candidates"][0]["content"]["parts"] if not x.get("thought"))
            if txt.strip():
                return txt.strip(), "gemini:" + mdl
        except Exception as e:                                          # noqa
            last = e
    raise RuntimeError("gemini: %s" % last)

def _call_openai_like(name, base, key, model, system, contents, max_tokens, temperature, extra_headers=None):
    d = _post_json(base.rstrip("/") + "/chat/completions", dict({"Authorization": "Bearer " + key}, **(extra_headers or {})),
                   {"model": model, "messages": _msgs_openai(system, contents), "max_tokens": max_tokens, "temperature": temperature}, AI_PER_CALL)
    txt = d["choices"][0]["message"]["content"]
    if not (txt or "").strip():
        raise RuntimeError("%s: trả lời rỗng" % name)
    return txt.strip(), "%s:%s" % (name, model)

def _call_anthropic(system, contents, max_tokens, temperature):
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
    msgs = [{"role": "assistant" if c["role"] == "model" else "user", "content": "".join(x.get("text", "") for x in c["parts"])} for c in contents]
    d = _post_json("https://api.anthropic.com/v1/messages", {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                   {"model": model, "max_tokens": max_tokens, "temperature": temperature, "system": system, "messages": msgs}, AI_PER_CALL)
    txt = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    if not txt.strip():
        raise RuntimeError("anthropic: trả lời rỗng")
    return txt.strip(), "anthropic:" + model

def ai_providers():
    """Các nhà cung cấp AI có khóa trong môi trường. Thứ tự ưu tiên có thể đặt bằng AI_PROVIDERS=gemini,groq,openai,anthropic,openrouter,deepseek."""
    E = os.environ.get
    avail = {}
    if E("GEMINI_API_KEY") or E("GOOGLE_API_KEY"):
        avail["gemini"] = lambda s, c, mt, t: _call_gemini(s, c, mt, t)
    if E("GROQ_API_KEY"):
        avail["groq"] = lambda s, c, mt, t: _call_openai_like("groq", "https://api.groq.com/openai/v1", E("GROQ_API_KEY"), E("GROQ_MODEL", "llama-3.3-70b-versatile"), s, c, mt, t)
    if E("OPENAI_API_KEY"):
        avail["openai"] = lambda s, c, mt, t: _call_openai_like("openai", E("OPENAI_BASE_URL", "https://api.openai.com/v1"), E("OPENAI_API_KEY"), E("OPENAI_MODEL", "gpt-4o-mini"), s, c, mt, t)
    if E("ANTHROPIC_API_KEY"):
        avail["anthropic"] = lambda s, c, mt, t: _call_anthropic(s, c, mt, t)
    if E("OPENROUTER_API_KEY"):
        avail["openrouter"] = lambda s, c, mt, t: _call_openai_like("openrouter", "https://openrouter.ai/api/v1", E("OPENROUTER_API_KEY"), E("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"), s, c, mt, t)
    if E("DEEPSEEK_API_KEY"):
        avail["deepseek"] = lambda s, c, mt, t: _call_openai_like("deepseek", "https://api.deepseek.com/v1", E("DEEPSEEK_API_KEY"), E("DEEPSEEK_MODEL", "deepseek-chat"), s, c, mt, t)
    order = [x.strip() for x in (E("AI_PROVIDERS") or "").split(",") if x.strip()] or ["gemini", "groq", "openai", "anthropic", "openrouter", "deepseek"]
    return [(k, avail[k]) for k in order if k in avail]

def ai_ready():
    return bool(ai_providers())

def gemini_text(system, contents, max_tokens=1200, temperature=0.3):
    """Gọi SONG SONG mọi nhà cung cấp có khóa, lấy câu trả lời đến trước (AI_RACE=0 để gọi tuần tự). Quá AI_TIMEOUT_S giây → báo lỗi để giao diện dùng bản giải thích tại chỗ."""
    import concurrent.futures as cf
    provs = ai_providers()
    if not provs:
        raise RuntimeError("Chưa cấu hình khóa AI (GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY…).")
    errs = []
    if os.environ.get("AI_RACE", "1") == "0" or len(provs) == 1:
        t0 = time.time()
        for name, fn in provs:
            if time.time() - t0 > AI_TOTAL_TIMEOUT:
                break
            try:
                return fn(system, contents, max_tokens, temperature)
            except Exception as e:                                  # noqa
                errs.append("%s: %s" % (name, e))
        raise RuntimeError("AI không phản hồi (%s)." % "; ".join(errs)[:300])
    ex = cf.ThreadPoolExecutor(max_workers=len(provs))
    futs = {ex.submit(fn, system, contents, max_tokens, temperature): name for name, fn in provs}
    try:
        pending = set(futs)
        deadline = time.time() + AI_TOTAL_TIMEOUT
        while pending and time.time() < deadline:
            done, pending = cf.wait(pending, timeout=max(0.1, deadline - time.time()), return_when=cf.FIRST_COMPLETED)
            for f in done:
                try:
                    return f.result()
                except Exception as e:                              # noqa
                    errs.append("%s: %s" % (futs[f], e))
        raise RuntimeError("AI không phản hồi kịp trong %ds (%s)." % (AI_TOTAL_TIMEOUT, "; ".join(errs)[:300] or "quá chậm"))
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

def _numbers(s):
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", s)]

def unverified_numbers(text, facts):
    """Số AI viết ra (≥10) mà không có trong dữ liệu đầu vào (sai số 1,5% hoặc ±1) → cảnh báo."""
    pool = _numbers(json.dumps(facts, ensure_ascii=False))
    bad = []
    for v in _numbers(text):
        if v < 10:
            continue
        if not any(abs(v - f) <= max(1.0, 0.015 * abs(f)) for f in pool):
            bad.append(v)
    return sorted(set(bad))[:12]

# ---- nhóm tác giả: tên cố định, email liên hệ đọc từ .env (FARM_AUTHOR1_EMAIL, FARM_AUTHOR2_EMAIL)
AUTHORS = [("Nguyễn Mai Chi", "FARM_AUTHOR1_EMAIL"), ("Nguyễn Mạnh Đạt", "FARM_AUTHOR2_EMAIL")]


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def authors_list():
    """.env: FARM_AUTHORn_EMAIL=Họ tên - email@... (hoặc chỉ email). Tên trong .env được ưu tiên; thiếu thì dùng tên mặc định."""
    out = []
    for n, k in AUTHORS:
        raw = (os.environ.get(k) or "").strip().strip('"').strip("'")
        m = _EMAIL_RE.search(raw)
        email = m.group(0) if m else ""
        name = (raw[:m.start()] + raw[m.end():]) if m else raw
        name = re.sub(r"^[\s\-–—:|,<>()]+|[\s\-–—:|,<>()]+$", "", name)
        out.append({"name": name or n, "email": email})
    return out


AI_SYSTEM = ("Bạn là cố vấn nông học thân thiện, giải thích cho nông dân ít kinh nghiệm kỹ thuật bằng tiếng Việt đơn giản, ngắn gọn. "
             "CHỈ dùng số liệu trong phần DỮ LIỆU; tuyệt đối không bịa số hay nguồn. Luôn nói rõ đây là gợi ý hỗ trợ, cần tham khảo "
             "khuyến nông địa phương, và nêu điểm cần phán đoán của con người. Không dùng ký hiệu markdown phức tạp: có thể dùng gạch đầu dòng '-'.")


def compact_facts(a, crop_id=None):
    """Tóm tắt kết quả đánh giá (vụ tới) để gửi AI — chỉ số liệu Python đã tính."""
    res = a.get("base") or {}
    t = a.get("target") or {}
    out = {"vu_can_quyet_dinh": {"ten": t.get("name"), "bat_dau": t.get("start"), "ket_thuc": t.get("end"), "so_ngay": t.get("days")},
           "cay_vu_truoc": a.get("prev_crop_vi"), "co_tuoi": res.get("irrigated"),
           "trong_so_tieu_chi": {k: round(v, 3) for k, v in (res.get("weights") or {}).items() if v > 0},
           "tieu_chi_thieu_du_lieu": res.get("missing"), "cay": []}
    for r in res.get("crops", []):
        if crop_id and r["id"] != crop_id:
            continue
        out["cay"].append({"cay": r["vi"], "hang": r.get("rank"), "kha_thi_K1": r["k1"]["pass"], "ly_do_loai": r["k1"]["reasons"], "diem_tong_0_1": r["total"],
                           "diem_tieu_chi": {k: {"diem": v["s"], "gia_tri": v["vtxt"]} for k, v in r["scores"].items() if v["s"] is not None},
                           "han_che": [CRIT_DEF[k]["vi"] for k in r.get("limiting", [])]})
    if a.get("scen"):
        out["kich_ban_thoi_tiet"] = {"delta": a["scen"]["deltas"], "xep_hang": [{"cay": r["vi"], "diem": r["total"]} for r in a["scen"]["crops"] if r["feasible"]]}
    return out


def local_explain(a, crop_id=None):
    """Giải thích KHÔNG cần AI — luôn dùng được, trả lời ngay."""
    res = a.get("base") or {}
    feas = [r for r in res.get("crops", []) if r.get("feasible")]
    t = a.get("target") or {}
    if not res.get("crops"):
        return "Chưa có kết quả."
    head = "Vụ cần quyết định: %s (từ %s, %s ngày)." % (t.get("name", "—"), t.get("start", "—"), t.get("days", "—"))
    if not feas:
        return head + "\nKhông có cây nào qua được điều kiện lịch gieo (K1) cho vụ này. Hãy xem lại ngày bắt đầu/độ dài vụ, hoặc cân nhắc để đất nghỉ."
    top = next((r for r in feas if r["id"] == crop_id), feas[0]) if crop_id else feas[0]
    out = [head, "Cây phù hợp nhất theo trọng số bạn chọn: %s — %s/100 điểm." % (top["vi"], _fmt(top["total"] * 100, 0))]
    if len(feas) > 1:
        out.append("Xếp sau: " + ", ".join("%s (%s)" % (r["vi"], _fmt(r["total"] * 100, 0)) for r in feas[1:] if r["id"] != top["id"]) + ".")
    if top.get("good"):
        out.append("Điểm mạnh:")
        out += ["- " + x for x in top["good"]]
    if top.get("bad"):
        out.append("Cần lưu ý:")
        out += ["- " + x for x in top["bad"]]
    out_k1 = [r for r in res["crops"] if not r["k1"]["pass"]]
    if out_k1:
        out.append("Bị loại theo lịch gieo (K1): " + "; ".join("%s — %s" % (r["vi"], " ".join(r["k1"]["reasons"])) for r in out_k1))
    if res.get("missing"):
        out.append("Tiêu chí chưa đủ dữ liệu nên chưa tính: " + ", ".join("%s %s" % (k, CRIT_DEF[k]["vi"]) for k in res["missing"]) + ".")
    out.append("Đây chỉ là gợi ý từ dữ liệu NASA, dữ liệu đất mở và thông tin bạn nhập. Hãy trao đổi với cán bộ khuyến nông địa phương trước khi quyết định.")
    return "\n".join(out)


# ───────────────────────── lưu trang trại + báo cáo ─────────────────────────
def _farms_load():
    try:
        with open(FARMS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _farms_save(d):
    tmp = FARMS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, FARMS_PATH)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_report(p):
    a, farm = p.get("analysis") or {}, p.get("farm") or {}
    res, t = a.get("base") or {}, a.get("target") or {}
    w = res.get("weights") or {}
    used = [k for k in CRIT_ORDER if w.get(k, 0) > 0]
    h = ["<!doctype html><html lang='vi'><head><meta charset='utf-8'><title>Báo cáo %s</title><style>"
         "body{font:14px/1.55 'Be Vietnam Pro',Arial,sans-serif;color:#2C2C2C;max-width:960px;margin:24px auto;padding:0 18px}"
         "h1{font:700 26px Georgia,serif;margin:0}h2{font:700 18px Georgia,serif;border-bottom:2px solid #2C2C2C;padding-bottom:4px;margin-top:26px}"
         "table{border-collapse:collapse;width:100%%;font-size:12.5px}td,th{border:1px solid #bbb;padding:4px 6px;text-align:left}th{background:#EFE8D8}"
         ".x{color:#999}.d{background:#FBF7EF;border:1px solid #C9A24B;padding:10px;margin-top:14px;font-size:12.5px}li{margin:2px 0}@media print{.np{display:none}}</style></head><body>" % _esc(APP_NAME)]
    h.append("<img src='data:image/png;base64," + LOGO_B64 + "' alt='logo' style='height:54px;float:right'><h1>%s — %s</h1><div>%s</div><div class='np'><button onclick='print()'>In / Lưu PDF</button></div>" % (_esc(APP_NAME), "Đề xuất chuỗi luân canh" if a.get("mode") == "chain" else "Đề xuất cây trồng cho vụ tới", _esc(APP_SLOGAN)))
    h.append("<h2>1. Ruộng và vụ</h2><p><b>%s</b> · vĩ độ %.4f, kinh độ %.4f · %s</p><p>Vụ cần quyết định: <b>%s</b> — từ %s đến %s (%s ngày). Cây vụ trước: %s.</p>"
             % (_esc(farm.get("name") or "Ruộng"), num(farm.get("lat"), 0), num(farm.get("lon"), 0), "có tưới" if res.get("irrigated") else "không tưới (nhờ mưa)",
                _esc(t.get("name", "—")), _esc(t.get("start", "—")), _esc(t.get("end", "—")), _esc(t.get("days", "—")), _esc(a.get("prev_crop_vi") or "chưa khai báo")))
    if a.get("is_demo"):
        h.append("<p style='color:#B8432F'><b>CẢNH BÁO:</b> báo cáo này dùng khí hậu MÔ PHỎNG (DEMO), không phải dữ liệu NASA.</p>")
    h.append("<h2>2. Bảng điểm phù hợp (0–1)</h2><table><tr><th>#</th><th>Cây</th><th>Tổng</th>" + "".join("<th>%s</th>" % k for k in used) + "<th>M</th><th>V = S×M</th><th>K1–K4</th></tr>")
    for r in res.get("crops", []):
        cls = "" if r.get("feasible") else " class='x'"
        h.append("<tr%s><td>%s</td><td>%s</td><td><b>%.2f</b></td>%s<td>%.2f</td><td><b>%.2f</b></td><td>%s</td></tr>" % (cls, r.get("rank") or "—", _esc(r["vi"]), r["total"],
                 "".join("<td>%.2f</td>" % r["scores"][k]["s"] for k in used), r.get("M", 1), r.get("V", r["total"]), "đạt" if r.get("feasible") else "loại: " + _esc(" ".join(r.get("watch") or r["k1"]["reasons"]))))
    h.append("<tr><td>—</td><td>Đất nghỉ</td><td colspan='%d'>Luôn khả thi — không chấm điểm phù hợp sinh thái.</td></tr></table>" % (len(used) + 4))
    ch = a.get("chain")
    if ch:
        h.append("<h2>2b. Chuỗi luân canh (Score(P) = (1/T)[S(c1) + Σ S(ct)·M(ct−1, ct)])</h2><p>Khoảng %s → %s · làm đất %s ngày · %s chuỗi hợp lệ.</p><table><tr><th>#</th><th>Chuỗi</th><th>Score</th><th>T</th><th>G (USD)</th></tr>"
                 % (_esc(ch["start"]), _esc(ch["end"]), ch["prep"], ch["n_total"]))
        for c in ch["chains"][:15]:
            seq = " → ".join(("Đất nghỉ" if x["kind"] == "fallow" else "%s (%s, S %.2f%s)" % (x["vi"], x["sow"], x["S"], ", M %.2f" % x["M"] if x.get("prev") else "")) for x in c["items"])
            h.append("<tr><td>%d</td><td>%s</td><td><b>%.2f</b></td><td>%d</td><td>%s</td></tr>" % (c["rank"], _esc(seq), c["score"], c["T"], "{:,.0f}".format(c["G"]) if c.get("G") is not None else "—"))
        h.append("</table>")
    elif a.get("prev_crop"):
        h.append("<p>V = S × M, với M = 1 + E(%s, c)/100 theo Mudare et al. (2025).</p>" % _esc(a.get("prev_crop_vi") or ""))
    h.append("<p>Trọng số: " + ", ".join("%s %s %.0f%%" % (k, CRIT_DEF[k]["vi"], w[k] * 100) for k in used) + "</p>")
    if res.get("missing"):
        h.append("<p><b>Chưa tính vì thiếu dữ liệu:</b> " + "; ".join("%s %s (%s)" % (k, CRIT_DEF[k]["vi"], _esc(v or "")) for k, v in res["missing"].items()) + "</p>")
    h.append("<h2>3. Chi tiết theo cây</h2>")
    for r in res.get("crops", []):
        h.append("<h3>%s — %.2f</h3><ul>%s</ul>" % (_esc(r["vi"]), r["total"], "".join("<li><b>%s %s:</b> %s → %.2f <span class='x'>(%s; nguồn: %s)</span></li>"
                 % (k, CRIT_DEF[k]["vi"], _esc(r["scores"][k]["vtxt"]), r["scores"][k]["s"], _esc(r["scores"][k]["rule"]), _esc(r["scores"][k]["src"])) for k in used)))
    h.append("<h2>4. Giả định của mô hình</h2><ul>%s</ul>" % "".join("<li>%s</li>" % _esc(x) for x in a.get("assumptions", [])))
    h.append("<h2>5. Nguồn CRD</h2><ul>%s</ul>" % "".join("<li>[%s] %s — %s</li>" % (k, _esc(v[0]), _esc(v[1])) for k, v in CRD_SOURCES.items()))
    h.append("<div class='d'>%s</div><p style='font-size:11px;color:#777'>Tạo lúc %s · %s v%s · Nhóm tác giả: %s</p></body></html>" % (_esc(DISCLAIMER), dt.datetime.now().strftime("%Y-%m-%d %H:%M"), APP_NAME, VERSION,
             _esc(", ".join("%s%s" % (a["name"], " (%s)" % a["email"] if a["email"] else "") for a in authors_list()))))
    return "".join(h)

# ───────────────────────── LOGO (PNG nền trong suốt, nhúng base64 để giữ MỘT file duy nhất) ─────────────────────────
LOGO_B64 = (
    "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"
    "rkJggg=="
)

INDEX_HTML = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="referrer" content="origin"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__APP_NAME__ — __APP_FULL__</title>
<link rel="icon" type="image/png" href="/logo.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root{--duration-stagger:40ms;--duration-micro:80ms;--duration-quick:150ms;--duration-fast:250ms;--duration-medium:350ms;--duration-slow:400ms;--duration-very-slow:500ms;--ease-smooth-out:cubic-bezier(.22,1,.36,1);--ease-in-out:ease-in-out;--ease-out:ease-out;--ease-linear:linear;--ease-bounce:cubic-bezier(.34,1.36,.64,1);--distance-micro:4px;--distance-base:8px;--distance-medium:12px;--blur-small:2px;--blur-medium:3px;--blur-large:8px;--bg:#F3F1EA;--surface:#fff;--side:#EAE7DD;--ink:#17251D;--ink2:#4B5A51;--line:#DAD6C8;--accent:#1E5B3F;--accent-d:#154631;--accent-t:#E1EEE5;--water:#2B6E8F;--warn:#9F3A22;--warn-t:#FBEAE4;--gold:#B58A1F;--note:#FFF4DB;
--sans:'Be Vietnam Pro',system-ui,sans-serif;--serif:'Newsreader',Georgia,serif;--sh:0 1px 2px rgba(23,37,29,.06),0 6px 16px rgba(23,37,29,.05);--ease:cubic-bezier(.22,1,.36,1);
--paper:var(--bg);--card:var(--surface);--leaf:var(--accent);--leaf-d:var(--accent-d);--sun:var(--gold);--bad:var(--warn);--muted:var(--ink2);--soil:#8A5A2B}
*{box-sizing:border-box;scrollbar-width:thin;scrollbar-color:#B9B49F transparent}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:15px/1.55 var(--sans);color:var(--ink);background:var(--bg);font-variant-numeric:tabular-nums;caret-color:var(--accent)}
::selection{background:#BFDCC9;color:var(--ink)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
h2{font:600 22px/1.25 var(--sans);letter-spacing:-.01em;margin:4px 0 6px;text-wrap:balance}h3{font:600 15px/1.35 var(--sans);margin:0 0 10px}
.sub{color:var(--ink2);margin:0 0 14px;max-width:72ch}small{color:var(--ink2)}
a{color:var(--accent-d);text-underline-offset:3px}
/* khung ứng dụng */
header{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--side);border-bottom:1px solid var(--line);flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:10px;cursor:pointer}.logo img{height:40px;width:auto;display:block}.logo b{font:700 16px var(--sans);letter-spacing:.06em}.logo small{display:block;font-size:11px;line-height:1.3}
nav{display:flex;gap:4px;overflow-x:auto;margin-left:auto;max-width:100%}
nav button{display:flex;align-items:center;gap:9px;border:0;background:none;padding:9px 12px;border-radius:8px;font:500 14px var(--sans);color:var(--ink2);cursor:pointer;white-space:nowrap;text-align:left;transition:background .18s var(--ease),color .18s}
nav button:hover{background:rgba(23,37,29,.07);color:var(--ink)}nav button.on{background:var(--accent);color:#fff}
nav button .n{display:grid;place-items:center;width:20px;height:20px;flex:none}nav button .n svg,.ico svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.mode{display:flex;border:1px solid #BDB8A6;border-radius:8px;overflow:hidden}.mode button{flex:1;border:0;background:transparent;padding:7px 12px;font:600 13px var(--sans);color:var(--ink2);cursor:pointer}.mode button.on{background:var(--ink);color:#fff}
.banner{display:none;background:var(--warn);color:#fff;padding:8px 18px;font-weight:600}.banner.show{display:block}
main{padding:18px;max-width:1400px;margin:0 auto}.tab{display:none}.tab.on{display:block;animation:tin var(--duration-fast) var(--ease-smooth-out) both}
@keyframes tin{from{opacity:0;transform:translateX(var(--distance-base));filter:blur(var(--blur-medium))}to{opacity:1;transform:none;filter:none}}
.appbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:4px 0 18px}.appbar h1{margin:0;font:600 24px/1.2 var(--sans);letter-spacing:-.01em}
#farmBadge{display:flex;flex-direction:column;align-items:flex-end;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:7px 14px}#farmBadge span{font-size:12.5px;color:var(--ink2)}
footer{padding:18px;color:var(--ink2);font-size:12.5px;border-top:1px solid var(--line);margin-top:24px;max-width:80ch}
@media(min-width:1000px){
 header{position:fixed;left:0;top:0;bottom:0;width:248px;flex-direction:column;align-items:stretch;flex-wrap:nowrap;gap:14px;padding:20px 14px;border:0;border-right:1px solid var(--line);overflow:auto}
 header .logo{padding:2px 6px 10px}nav{flex-direction:column;margin:0;overflow:visible}nav button{width:100%}
 .mode{margin-top:auto}#chipAi{text-align:center}
 html:not(.landing) body{padding-left:248px}main{max-width:1180px;margin:0 auto;padding:22px 32px 40px}footer{max-width:1180px;margin:24px auto 0;padding:18px 32px}}
/* khối nội dung */
.grid{display:grid;gap:16px}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g-map{grid-template-columns:1.5fr 1fr}
@media(max-width:1000px){.g2,.g3,.g-map{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px;box-shadow:var(--sh)}
label{display:block;font-size:12.5px;font-weight:600;color:var(--ink2);margin:10px 0 4px}
input,select,textarea{width:100%;padding:9px 11px;border:1px solid #BDB8A6;border-radius:8px;background:#fff;font:15px var(--sans);color:var(--ink);transition:border-color .15s,box-shadow .15s}
input::placeholder{color:#66746B}input:focus,select:focus,textarea:focus{outline:0;border-color:var(--accent);box-shadow:0 0 0 3px rgba(30,91,63,.18)}
input[type=range]{padding:0;accent-color:var(--accent)}input[type=checkbox]{width:auto;accent-color:var(--accent)}input[type=file]{padding:6px;font-size:13px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row>*{flex:1;min-width:90px}.row .fit{flex:none}
button.b{border:1px solid var(--accent);background:var(--accent);color:#fff;padding:9px 16px;border-radius:8px;font:600 14px var(--sans);cursor:pointer;transition:background .15s,transform .12s var(--ease)}
button.b:hover{background:var(--accent-d)}button.b:active{transform:translateY(1px)}button.b.ghost{background:transparent;color:var(--accent-d)}button.b.ghost:hover{background:var(--accent-t)}
button.b.warn{background:var(--warn);border-color:var(--warn)}button.b:disabled{opacity:.55;cursor:wait}button.sm{padding:4px 10px;font-size:12.5px}
#map{height:560px;border:1px solid var(--line);border-radius:12px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{background:#fff;border:1px solid var(--line);border-radius:99px;padding:2px 10px;font-size:12.5px;color:var(--ink2)}.chip.g{border-color:var(--accent);color:var(--accent-d);background:var(--accent-t)}.chip.r{border-color:var(--warn);color:var(--warn);background:var(--warn-t)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}.kpi{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px 12px}.kpi b{display:block;font:600 20px/1.2 var(--sans)}.kpi span{font-size:12.5px;color:var(--ink2)}
table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}th{background:#F0EDE3;font-weight:600;color:var(--ink2);position:sticky;top:0}tbody tr:hover td,table tr:hover>td{background:#FAF9F4}
.scroll{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.note{background:var(--note);border:1px solid #E6CF8E;border-radius:10px;padding:9px 12px;font-size:13px;margin:8px 0}
.err{background:var(--warn-t);border:1px solid var(--warn);color:var(--warn);border-radius:10px;padding:9px 12px;margin:8px 0;display:none}.err.show{display:block}
.spin{display:none;color:var(--ink2);font-size:13px;margin-left:8px}.spin.show{display:inline-flex;align-items:center;gap:8px}.spin.show:before{content:"";width:13px;height:13px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--accent);animation:rot .8s linear infinite}
@keyframes rot{to{transform:rotate(360deg)}}
canvas{max-width:100%}.cbox{position:relative;height:260px}.cbox.tall{height:320px}
.gantt{font-size:12px;margin:4px 0 10px}.gantt .gr{display:grid;grid-template-columns:48px repeat(12,1fr);gap:2px;margin-bottom:2px}.gantt .yl{color:var(--ink2);align-self:center;font-weight:600}.gantt .mh{text-align:center;color:var(--ink2);font-size:11px}
.seg{border-radius:4px;padding:4px 6px;color:#fff;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;min-height:28px;font-weight:600}
.seg.bare{background:repeating-linear-gradient(45deg,#EEEBE1,#EEEBE1 4px,#DEDACB 4px,#DEDACB 8px)!important;color:#5E6A62;border:1px dashed #B9B49F;font-weight:400}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12.5px;margin:4px 0 8px;color:var(--ink2)}.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.rk td.sc{text-align:center;font-weight:600}.bar{height:4px;background:var(--line);border-radius:3px;margin-top:4px}.bar i{display:block;height:4px;border-radius:3px;background:var(--accent)}
.scn{margin-bottom:14px}.scn h3{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.scn h3:before{content:"";width:10px;height:10px;border-radius:3px;background:var(--sc,var(--accent))}
.scn.s1{--sc:#8A5A2B}.scn.s2{--sc:#1E5B3F}.scn.s3{--sc:#2B6E8F}.scn.s4{--sc:#B58A1F}
.scn ul{margin:2px 0 8px 18px;padding:0}.scn li{margin:3px 0}.scn .k{font-weight:600;margin-top:8px}
.badge{background:var(--ink);color:#fff;border-radius:6px;padding:1px 9px;font-size:12px;font-weight:600}.badge.top{background:var(--accent)}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}
.ai{white-space:pre-wrap;background:#FAF9F4;border:1px solid var(--line);border-radius:10px;padding:12px;margin-top:8px}.chat{max-height:300px;overflow:auto;margin:8px 0}.chat div{padding:7px 11px;margin:4px 0;border-radius:10px;background:#F0EDE3;max-width:88%}.chat .u{background:var(--accent-t);margin-left:auto}
.rot{display:grid;grid-template-columns:2fr 1fr 1fr auto;gap:6px;margin-bottom:6px}.sl{display:grid;grid-template-columns:1.3fr 2fr 44px;gap:10px;align-items:center;margin:4px 0}.sl span{font-size:13px}.sl output{font-weight:600;text-align:right}
body.simple{font-size:16px}body.simple .adv{display:none!important}body.expert .sim{display:none!important}
body.simple button.b{padding:12px 20px;font-size:15px}body.simple input,body.simple select{padding:11px 13px;font-size:16px}body.simple h2{font-size:26px}
.pref{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.pref button{border:1px solid #BDB8A6;background:#fff;border-radius:10px;padding:13px 14px;text-align:left;cursor:pointer;font:600 15px var(--sans);color:var(--ink);transition:background .15s,border-color .15s}.pref button small{display:block;font-weight:400;margin-top:3px}.pref button:hover{background:#FAF9F4}.pref button.on{border:2px solid var(--accent);background:var(--accent-t);padding:12px 13px}
.xchip{cursor:pointer;user-select:none;padding:5px 12px;font-size:14px}.xchip.off{background:var(--warn-t);border-color:var(--warn);color:var(--warn);text-decoration:line-through}
.hero{background:var(--accent-t);border-color:#B9D4C2;font-size:17px}.hero h3{font:600 22px/1.3 var(--sans);margin-bottom:6px}
.geo{border:1px solid var(--line);background:#fff;border-radius:10px;margin:6px 0;overflow:hidden}.geo div{padding:9px 12px;cursor:pointer;border-bottom:1px solid var(--line)}.geo div:last-child{border:0}.geo div:hover{background:var(--accent-t)}
.st{display:inline-flex;gap:3px;vertical-align:middle}.st i{width:15px;height:6px;border-radius:2px;background:var(--line)}.st i.on{background:var(--accent)}table.cmp td{vertical-align:middle}#simpleBox li{margin:4px 0}
/* trang mở đầu */
html.landing header,html.landing main,html.landing footer,html.landing #demoBanner{display:none!important}#landing{display:none}html.landing #landing{display:block}
.lhero{position:relative;min-height:100vh;display:flex;flex-direction:column;color:#fff;background:linear-gradient(100deg,rgba(10,32,22,.94) 0%,rgba(10,32,22,.72) 55%,rgba(10,32,22,.38) 100%),url(/hero.jpg),#1E4A33;background-size:cover;background-position:center}
.hero-top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:22px 5vw}.hero-top .logo img{height:48px;filter:brightness(0) invert(1)}.hero-top .logo b{font-size:17px}.hero-tag{font-size:13px;color:#DCE8CF}
.hero-body{margin:auto 0;padding:0 5vw 9vh;max-width:860px;animation:up .7s var(--ease) both}@keyframes up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
.lhero h1{font:500 clamp(42px,6.2vw,88px)/1.02 var(--serif);letter-spacing:-.02em;margin:0 0 18px;text-wrap:balance}.lhero h1 em{font-style:italic;color:#E9D48B}
.lhero p{font-size:clamp(16px,1.5vw,19px);max-width:620px;color:#E4EEDB;margin:0}.lhero p.hero-facts{font-size:14px;color:#C5D6BC;margin-top:26px}
.hero-cta{display:flex;gap:12px;flex-wrap:wrap;margin:28px 0 0}
.lbtn{border:1.5px solid #E9D48B;background:#E9D48B;color:#12301F;padding:14px 26px;border-radius:8px;font:700 16px var(--sans);cursor:pointer;transition:transform .15s var(--ease),background .15s}.lbtn:hover{background:#F2E2A6;transform:translateY(-1px)}.lbtn:active{transform:translateY(1px)}.lbtn.o{background:transparent;color:#fff;border-color:rgba(255,255,255,.65)}.lbtn.o:hover{background:rgba(255,255,255,.1)}
.lcard{position:absolute;right:5vw;bottom:12vh;width:380px;background:#fff;color:var(--ink);border-radius:12px;box-shadow:0 20px 44px rgba(0,0,0,.3);overflow:hidden;display:none}@media(min-width:1150px){.lcard{display:block}}
.lcard .tb{padding:10px 14px;border-bottom:1px solid var(--line);font:600 12.5px var(--sans);color:var(--ink2)}.lcard .bd{padding:14px}.lcard .gantt{margin:0}
.lsec{padding:clamp(56px,11vh,112px) 5vw;max-width:1280px;margin:0 auto}.lsec h2{font:500 clamp(28px,3.4vw,44px)/1.1 var(--serif);letter-spacing:-.015em;margin:0 0 12px}.lead{color:var(--ink2);max-width:520px;margin:0}
.split{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:6vw;align-items:start}@media(max-width:850px){.split{grid-template-columns:1fr;gap:28px}}
ol.steps{list-style:none;margin:0;padding:0;counter-reset:s}ol.steps li{counter-increment:s;display:grid;grid-template-columns:48px 1fr;padding:20px 0;border-top:1px solid var(--line)}ol.steps li:last-child{border-bottom:1px solid var(--line)}ol.steps li:before{content:counter(s);font:500 30px/1 var(--serif);color:var(--accent)}ol.steps b{display:block;font-size:17px;margin-bottom:3px}ol.steps p{margin:0;color:var(--ink2)}
table.croptab{font-size:15px;background:transparent}table.croptab th{background:transparent;position:static;font-size:12.5px}table.croptab td{padding:13px 10px}table.croptab td:first-child{font-weight:600;white-space:nowrap}table.croptab tr:hover td{background:rgba(30,91,63,.05)}
.lband{background:#123B29;color:#fff}.lband h2{color:#fff}.lband .lead{color:#C5D6BC}
.dlist{margin:0}.dr{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.6fr) auto;gap:16px;align-items:center;padding:16px 8px;border-top:1px solid rgba(255,255,255,.2);transition:background .15s}.dr:last-child{border-bottom:1px solid rgba(255,255,255,.2)}.dr:hover{background:rgba(255,255,255,.05)}.dr b{font-size:16px}.dr span{color:#C5D6BC;font-size:14px}
.tg{padding:2px 11px;border-radius:99px;font-size:12.5px;font-weight:600;white-space:nowrap;background:#E9D48B;color:#12301F}.tg.c{background:transparent;color:#E4EEDB;border:1px solid rgba(255,255,255,.5)}.tg.p{background:transparent;color:#C5D6BC;border:1px dashed rgba(255,255,255,.45)}
@media(max-width:700px){.dr{grid-template-columns:1fr auto}.dr span{grid-column:1/-1;order:3}}
.lend{text-align:center;padding:clamp(56px,10vh,100px) 5vw}.lend h2{font:500 clamp(26px,3vw,38px)/1.15 var(--serif);margin:0 0 10px}.lend .lead{margin:0 auto 24px}.lend .lbtn{background:var(--accent);border-color:var(--accent);color:#fff}.lend .lbtn:hover{background:var(--accent-d)}
.lfoot{padding:16px 5vw;color:var(--ink2);font-size:12.5px;border-top:1px solid var(--line);text-align:center}
.leaflet-container{font-family:var(--sans)}

/* ===== v0.4 · biểu tượng thời tiết, chuyển động theo token, bố cục công cụ ===== */
nav button{min-height:44px}
nav button .n{width:32px;height:32px;border-radius:10px;color:var(--tc,var(--accent));transition:background var(--duration-fast) var(--ease-smooth-out),color var(--duration-fast) var(--ease-smooth-out)}
nav button .n svg{width:20px;height:20px}
nav button:hover{background:rgba(23,37,29,.06);color:var(--ink)}
nav button.on{background:#fff;color:var(--ink);box-shadow:var(--sh)}nav button.on .n{background:var(--tc);color:#fff}
body.simple nav button{min-height:50px;font-size:15px}
@media(min-width:1000px){
 header .logo{flex-direction:column;align-items:center;text-align:center;gap:8px;padding:6px 4px 16px;border-bottom:1px solid var(--line)}
 header .logo img{height:76px}header .logo b{font-size:17px}header .logo small{max-width:190px;margin:2px auto 0}
 nav{gap:6px}}
.appbar{padding:4px 0 10px}.appbar h1{font:500 24px/1.2 var(--serif);letter-spacing:-.01em}
.stepper{display:flex;align-items:center;gap:14px;margin:0 0 18px;font-size:13px;font-weight:600;color:var(--ink2)}
.stepper .trk{flex:1;max-width:420px;height:6px;border-radius:99px;background:var(--line);overflow:hidden}
.stepper .trk i{display:block;height:100%;width:0;border-radius:99px;background:var(--tc,var(--accent));transition:width var(--duration-slow) var(--ease-smooth-out)}
.wi{display:inline-grid;place-items:center;flex:none;width:36px;height:36px;border-radius:12px;background:color-mix(in srgb,var(--tc,#1E5B3F) 14%,#fff);color:var(--tc,#1E5B3F)}
.wi svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.wi.big{width:64px;height:64px;border-radius:20px}.wi.big svg{width:36px;height:36px}
.tab>h2{display:flex;align-items:center;gap:14px;margin:0 0 6px}.tab>h2 .wi{width:46px;height:46px;border-radius:14px}.tab>h2 .wi svg{width:26px;height:26px}
.card{border-radius:16px}body.simple .card h3{font-size:17px}
button.b:hover{transform:translateY(-1px)}button.b:active{transform:translateY(1px)}
button.b,.pref button,.xchip{transition:background var(--duration-quick) var(--ease-smooth-out),border-color var(--duration-quick) var(--ease-smooth-out),transform var(--duration-quick) var(--ease-smooth-out)}
.srch input{flex:1 1 100%}
body.simple #tab3 .g2{grid-template-columns:minmax(0,780px)}body.simple #tab3 .row>div{min-width:200px}
.pref button{position:relative}
.pref button.on:after{content:"";position:absolute;right:12px;top:12px;width:22px;height:22px;border-radius:50%;background:var(--accent) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12.5l4.5 4.5L19 7.5'/%3E%3C/svg%3E") center/13px no-repeat;animation:pop var(--duration-fast) var(--ease-bounce) both}
@keyframes pop{from{transform:scale(.6);opacity:0}to{transform:none;opacity:1}}
.quick{padding:6px 0 2px}
.empty .in{display:flex;gap:18px;align-items:center}.empty{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:var(--sh)}
.empty h3{font:600 20px/1.3 var(--sans);margin:0 0 4px}.empty .run-t{display:none}.empty.running .run-t{display:block}.empty.running button{display:none}
.card.hero{display:flex;gap:18px;align-items:center;background:#123B29;border:0;color:#fff;padding:22px 24px}
.hero .wi.big{background:rgba(255,255,255,.12);color:#E9D48B}
.hero .eyebrow{font-size:12.5px;letter-spacing:.08em;text-transform:uppercase;color:#C5D6BC;font-weight:600;margin-bottom:4px}
.hero h3{font:500 clamp(24px,3vw,34px)/1.2 var(--serif);color:#fff;margin:0}.hero p{margin:8px 0 0;color:#E4EEDB;font-size:16px;max-width:60ch}
.wxl{list-style:none;margin:0;padding:0;display:grid;gap:10px}.wxl li{display:flex;gap:12px;align-items:flex-start;margin:0!important}
.wxl .wi{width:34px;height:34px;border-radius:11px}.wxl .wi svg{width:20px;height:20px}
.skel{display:grid;gap:8px;margin:10px 0}.skel i{display:block;height:12px;border-radius:6px;background:var(--line);animation:pulse 1.4s var(--ease-linear) infinite}.skel i:nth-child(2){width:88%}.skel i:nth-child(3){width:62%}
@keyframes pulse{50%{opacity:.4}}
@keyframes reveal{from{opacity:0;filter:blur(var(--blur-small))}to{opacity:1;filter:none}}
.reveal{animation:reveal var(--duration-slow) var(--ease-in-out) both}
.shim{background:linear-gradient(90deg,var(--ink2) 0%,var(--ink2) 40%,var(--ink) 50%,var(--ink2) 60%,var(--ink2) 100%);background-size:200% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;animation:shim 1.8s var(--ease-linear) infinite}
@keyframes shim{from{background-position:100% 0}to{background-position:-100% 0}}
@keyframes rise{from{opacity:0;transform:translateY(var(--distance-base))}to{opacity:1;transform:none}}
#simpleBox>*{animation:rise var(--duration-slow) var(--ease-smooth-out) both}
#simpleBox>*:nth-child(2){animation-delay:calc(1*var(--duration-stagger))}#simpleBox>*:nth-child(3){animation-delay:calc(2*var(--duration-stagger))}#simpleBox>*:nth-child(4){animation-delay:calc(3*var(--duration-stagger))}#simpleBox>*:nth-child(5){animation-delay:calc(4*var(--duration-stagger))}#simpleBox>*:nth-child(n+6){animation-delay:calc(5*var(--duration-stagger))}
.toasts{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:300;display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none;width:max-content;max-width:92vw}
.toast{pointer-events:auto;display:flex;gap:10px;align-items:center;background:var(--ink);color:#fff;padding:12px 18px;border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.25);font:600 14px/1.4 var(--sans);animation:toast-in var(--duration-slow) var(--ease-smooth-out) both}
.toast.err{background:var(--warn)}.toast svg{width:20px;height:20px;flex:none;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.toast.ok svg path{stroke-dasharray:21;stroke-dashoffset:21;animation:draw var(--duration-very-slow) var(--ease-in-out) var(--duration-micro) forwards}
.toast.out{animation:toast-out var(--duration-medium) var(--ease-smooth-out) both}
@keyframes toast-in{from{opacity:0;transform:translateY(16px);filter:blur(var(--blur-small))}to{opacity:1;transform:none;filter:none}}
@keyframes toast-out{to{opacity:0;transform:translateY(var(--distance-base));filter:blur(var(--blur-small))}}
@keyframes draw{to{stroke-dashoffset:0}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}.shim{background:none;color:var(--ink2)}.toast.ok svg path{stroke-dashoffset:0}}

/* ===================== v0.5 · giao diện thống nhất, minh họa, màu theo trang ===================== */
[data-p="1"]{--g1:#E3A526;--g2:#BE7C10;--g3:#8C5509;--pc:#C58213;--pd:#7A4E08;--tint:#FFF4D9;--pl:#FBE8B6}
[data-p="2"]{--g1:#55A9DC;--g2:#2F7DB8;--g3:#1B5890;--pc:#2F7DB8;--pd:#1B4F7E;--tint:#E5F2FB;--pl:#C8E3F5}
[data-p="3"]{--g1:#CC8E58;--g2:#A06236;--g3:#6C3F20;--pc:#A06236;--pd:#5E3719;--tint:#F7ECDF;--pl:#EBD3B6}
[data-p="4"]{--g1:#62B45E;--g2:#35904A;--g3:#1B573B;--pc:#35904A;--pd:#1B573B;--tint:#E7F4E3;--pl:#CDE8C6}
[data-p="5"]{--g1:#4EA9A6;--g2:#2A8088;--g3:#18525E;--pc:#2A8088;--pd:#18525E;--tint:#E2F2F1;--pl:#C2E4E1}
[data-p="6"]{--g1:#F09B4B;--g2:#D9692F;--g3:#A43C1F;--pc:#D9692F;--pd:#9A3A1B;--tint:#FDEBDC;--pl:#F8D3B4}
body.app{background:var(--bg);overflow-x:hidden}
html:not(.landing) body.app{padding-left:0}
#app{display:none}html:not(.landing) #app{display:flex;height:100vh;overflow:hidden}
#side{width:258px;flex:none;height:100vh;overflow:auto;background:linear-gradient(180deg,#F8F4E8,#ECE6D4);border-right:1px solid var(--line);padding:14px 14px 16px;display:flex;flex-direction:column;gap:10px}
#side .brand{text-align:center;padding:2px 6px 14px;border-bottom:1px solid var(--line);cursor:pointer}
#side .brand img{height:84px;width:auto;display:block;margin:0 auto}
#side .brand b{display:block;font:700 17px var(--sans);letter-spacing:.09em;margin-top:6px}
#side .brand small{display:block;font-size:11px;line-height:1.35;color:var(--ink2);margin-top:2px}
#nav{display:flex;flex-direction:column;gap:4px;margin-top:4px}
.nb{display:flex;align-items:center;gap:12px;width:100%;padding:7px 10px;border:0;background:none;border-radius:16px;cursor:pointer;font:600 14.5px var(--sans);color:var(--ink2);text-align:left;transition:background var(--duration-fast) var(--ease-smooth-out),box-shadow var(--duration-fast) var(--ease-smooth-out),color var(--duration-fast)}
.nb .ti{position:relative;flex:none;width:46px;height:46px;border-radius:14px;background:#fff;display:grid;place-items:center;box-shadow:inset 0 0 0 1px var(--line);transition:box-shadow var(--duration-fast) var(--ease-smooth-out),transform var(--duration-fast) var(--ease-smooth-out)}
.nb .ti svg{width:34px;height:34px}
.nb small{display:block;font:500 11.5px var(--sans);color:var(--ink2);opacity:.85;margin-top:1px}
.nb:hover{background:rgba(23,37,29,.05);color:var(--ink)}.nb:hover .ti{transform:scale(1.05)}
.nb.on{background:#fff;color:var(--ink);box-shadow:var(--sh)}.nb.on .ti{box-shadow:0 0 0 2.5px var(--pc),0 6px 14px -4px color-mix(in srgb,var(--pc) 55%,transparent)}
.nb .ok{position:absolute;right:-4px;bottom:-4px;width:18px;height:18px;border-radius:50%;background:#2E9B55;border:2px solid #F3EFE2;display:none;place-items:center}.nb.done .ok{display:grid}.nb .ok svg{width:10px;height:10px;fill:none;stroke:#fff;stroke-width:3.4;stroke-linecap:round;stroke-linejoin:round}
#side .foot{margin-top:auto;display:grid;gap:8px;font-size:12px;color:var(--ink2)}
#side .foot .chip{text-align:center}
#stage{flex:1;min-width:0;height:100vh;display:flex;flex-direction:column;background:linear-gradient(180deg,var(--tint) 0,var(--bg) 360px);transition:background var(--duration-slow) var(--ease-smooth-out)}
#banner{position:relative;flex:none;margin:16px 22px 0;border-radius:22px;height:136px;padding:20px 28px;transition:height var(--duration-fast) var(--ease-smooth-out),padding var(--duration-fast) var(--ease-smooth-out);color:#fff;overflow:hidden;background:linear-gradient(110deg,var(--g1),var(--g2) 55%,var(--g3));box-shadow:0 12px 28px -12px color-mix(in srgb,var(--g3) 60%,transparent)}
#banner .art{position:absolute;right:0;top:0;bottom:0;width:min(60%,620px);pointer-events:none}
#banner .art svg{width:100%;height:100%;display:block}
#banner .tx{position:relative;max-width:min(62%,760px)}
#banner .st{font:700 11.5px var(--sans);letter-spacing:.13em;text-transform:uppercase;opacity:.92}
#banner h1{font:600 clamp(22px,2vw,31px)/1.12 var(--serif);letter-spacing:-.01em;margin:4px 0 6px;text-wrap:balance;text-shadow:0 2px 10px rgba(0,0,0,.18)}
#banner p{margin:0;font-size:14.5px;line-height:1.45;opacity:.96;max-width:52ch}
#banner .art.sw{animation:artin var(--duration-slow) var(--ease-smooth-out) both}
@keyframes artin{from{opacity:0;transform:translateX(var(--distance-medium))}to{opacity:1;transform:none}}
#farmBadge{position:static;display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:8px 12px 8px 8px;box-shadow:0 6px 14px -10px rgba(0,0,0,.3)}
#farmBadge .pn{width:34px;height:34px;border-radius:11px;background:#FBE3DC;display:grid;place-items:center;color:#D84B33;flex:none}#farmBadge .pn svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
#farmBadge b{display:block;font:650 13.5px var(--sans);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:150px}#farmBadge div span{display:block;font-size:11.5px;color:var(--ink2)}
#pages{flex:1;min-height:0;overflow:auto;scroll-behavior:smooth}
.page{display:none;padding:18px 22px 34px}
.page.on{display:block;animation:tin var(--duration-fast) var(--ease-smooth-out) both}
.page.fit.on{display:flex;flex-direction:column;height:100%;padding-bottom:18px}
.page .card,.card{border-radius:18px;border:1px solid color-mix(in srgb,var(--pc,#1E5B3F) 14%,#E4DFD0);box-shadow:0 1px 2px rgba(23,37,29,.05),0 10px 24px -12px rgba(23,37,29,.16);background:#fff}
.ch{display:flex;align-items:center;gap:11px;margin:0 0 12px}.ch .ti{flex:none;width:40px;height:40px;border-radius:13px;background:color-mix(in srgb,var(--pc) 12%,#fff);display:grid;place-items:center}.ch .ti svg{width:28px;height:28px}
.ch h3{margin:0;font:650 16.5px/1.25 var(--sans)}.ch small{display:block;color:var(--ink2);font-size:12.5px;font-weight:400;margin-top:1px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}.two.w{grid-template-columns:1.15fr .85fr}.two.n{grid-template-columns:.85fr 1.15fr}
.stack{display:grid;gap:16px}.mt{margin-top:16px}
@media(max-width:1000px){.two,.two.w,.two.n{grid-template-columns:1fr}}
button.b{background:var(--pc,#1E5B3F);border-color:var(--pc,#1E5B3F);border-radius:12px;padding:10px 18px}button.b:hover{background:var(--pd,#154631)}
button.b.ghost{background:transparent;color:var(--pd,#154631)}button.b.ghost:hover{background:color-mix(in srgb,var(--pc) 10%,#fff)}
button.b.big{padding:14px 26px;font-size:16px;border-radius:14px;box-shadow:0 10px 22px -10px color-mix(in srgb,var(--pc) 80%,transparent)}
.cta{display:flex;gap:10px;align-items:center;justify-content:flex-end;flex-wrap:wrap;margin-top:16px}
.cta .sp{flex:1}
/* ---- trang 1: vừa một màn hình ---- */
.p1{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 372px;gap:16px}
.mapw{position:relative;min-height:0;border-radius:20px;overflow:hidden;border:1px solid color-mix(in srgb,var(--pc) 24%,#d8d2c0);box-shadow:0 12px 28px -14px rgba(23,37,29,.4)}
#map{height:100%;border:0;border-radius:0}
.msearch{position:absolute;left:14px;top:14px;z-index:500;width:min(430px,calc(100% - 90px));}
.msearch .sbar{display:flex;gap:6px;background:#fff;border-radius:14px;padding:5px;box-shadow:0 8px 22px -6px rgba(0,0,0,.35)}
.msearch input{border:0;background:transparent;padding:9px 10px;font-size:15px;box-shadow:none}.msearch input:focus{box-shadow:none}
.msearch button{border:0;border-radius:10px;cursor:pointer;font:600 13.5px var(--sans);padding:0 14px;white-space:nowrap}
.msearch .go{background:var(--pc);color:#fff}.msearch .me{background:color-mix(in srgb,var(--pc) 12%,#fff);color:var(--pd);width:40px;padding:0;display:grid;place-items:center}.me svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
#geoList .geo{margin-top:6px;box-shadow:0 8px 22px -6px rgba(0,0,0,.35);max-height:240px;overflow:auto}
.mtools{position:absolute;left:14px;bottom:30px;z-index:500;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.mtools button{display:flex;gap:6px;align-items:center;border:0;background:#fff;border-radius:12px;padding:8px 12px;font:600 13px var(--sans);cursor:pointer;box-shadow:0 6px 16px -6px rgba(0,0,0,.4);color:var(--ink)}
.mtools button:hover{background:var(--pl)}.mtools svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round}
.mhint{position:absolute;left:14px;top:70px;z-index:400;background:rgba(18,30,22,.78);color:#fff;border-radius:99px;padding:8px 16px;font-size:13px;white-space:nowrap;pointer-events:none;transition:opacity var(--duration-medium)}
.mhint.off{opacity:0}
.mapw .leaflet-control-container .leaflet-top.leaflet-right{top:6px}
.pin{filter:drop-shadow(0 6px 6px rgba(0,0,0,.4))}
.rside{display:flex;flex-direction:column;gap:12px;min-height:0;overflow:auto;padding:2px 2px 4px}
.rside .card{padding:14px 16px}.rside>.b.big{margin-top:auto;flex:none}
.coords{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.coords div{background:color-mix(in srgb,var(--pc) 8%,#fff);border-radius:12px;padding:6px 10px}.coords small{display:block;font-size:11px}.coords input{border:0;background:transparent;padding:0;font:650 15px var(--sans);box-shadow:none}
.exs{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ex{display:block;text-align:left;border:1.5px solid var(--line);background:#fff;border-radius:14px;padding:8px;cursor:pointer;font:inherit;transition:transform var(--duration-quick) var(--ease-smooth-out),box-shadow var(--duration-quick),border-color var(--duration-quick)}
.ex:hover{transform:translateY(-2px);box-shadow:0 10px 18px -10px rgba(0,0,0,.3);border-color:var(--pc)}
.ex .ic{display:flex;gap:2px;height:30px;margin-bottom:5px}.ex .ic svg{height:30px;width:30px}.ex b{display:block;font:650 13px/1.25 var(--sans)}.ex small{display:block;font-size:11.5px;line-height:1.3}
.farms .fr{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px dashed var(--line);font-size:13px}.farms .fr:first-child{border:0}.farms .fr span{flex:1;min-width:0}.farms .fr b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* ---- ô chọn có hình ---- */
.opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:10px}
.opt{position:relative;border:1.5px solid var(--line);background:#fff;border-radius:16px;padding:7px 7px 9px;cursor:pointer;text-align:left;font:inherit;color:var(--ink);transition:transform var(--duration-quick) var(--ease-smooth-out),box-shadow var(--duration-quick),border-color var(--duration-quick),background var(--duration-quick)}
.opt .im{border-radius:11px;overflow:hidden;aspect-ratio:120/72;background:#EEF4F8}.opt .im svg{display:block;width:100%;height:100%}
.opt b{display:block;margin:7px 4px 0;font:650 14px/1.25 var(--sans)}.opt small{display:block;margin:2px 4px 0;font-size:12px;line-height:1.35;color:var(--ink2)}
.opt:hover{transform:translateY(-2px);box-shadow:0 12px 20px -12px rgba(0,0,0,.35);border-color:color-mix(in srgb,var(--pc) 50%,#ddd)}
.opt.on{border-color:var(--pc);background:color-mix(in srgb,var(--pc) 8%,#fff);box-shadow:0 0 0 3px color-mix(in srgb,var(--pc) 20%,transparent)}
.opt.on:after{content:"";position:absolute;right:11px;top:11px;width:24px;height:24px;border-radius:50%;background:var(--pc) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12.5l4.5 4.5L19 7.5'/%3E%3C/svg%3E") center/14px no-repeat;animation:pop var(--duration-fast) var(--ease-bounce) both;box-shadow:0 2px 6px rgba(0,0,0,.25)}
.opt.sm .im{aspect-ratio:2/1}.opt.unk{display:flex;align-items:center;justify-content:center;min-height:54px;border-style:dashed;background:transparent}
.q{margin:0 0 16px}.q h4{margin:0 0 8px;font:650 15px var(--sans);display:flex;gap:8px;align-items:center}.q h4 i{font-style:normal;background:var(--pc);color:#fff;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:12px}
.q .opts.c3{grid-template-columns:repeat(3,1fr)}.q .opts.c4{grid-template-columns:repeat(4,1fr)}.q .opts.c5{grid-template-columns:repeat(5,1fr)}
@media(max-width:700px){.q .opts.c3,.q .opts.c4,.q .opts.c5{grid-template-columns:repeat(2,1fr)}}
.sg{display:inline-flex;background:#fff;border:1px solid var(--line);border-radius:13px;padding:3px;gap:2px;flex-wrap:wrap}
.sg button{border:0;background:none;padding:7px 13px;border-radius:10px;font:600 13px var(--sans);color:var(--ink2);cursor:pointer;display:flex;gap:7px;align-items:center;transition:background var(--duration-quick),color var(--duration-quick)}
.sg button svg{width:20px;height:20px}.sg button:hover{background:color-mix(in srgb,var(--pc) 9%,#fff)}.sg button.on{background:var(--pc);color:#fff}
.tech{background:rgba(255,255,255,.6);border:1.5px dashed color-mix(in srgb,var(--pc) 35%,#d9d3c2);border-radius:16px;padding:10px 16px;margin-top:14px}
.tech>summary{cursor:pointer;font:650 14px var(--sans);color:var(--pd);display:flex;align-items:center;gap:8px;list-style:none}.tech>summary::-webkit-details-marker{display:none}
.tech>summary:before{content:"▸";transition:transform var(--duration-fast) var(--ease-smooth-out);display:inline-block}.tech[open]>summary:before{transform:rotate(90deg)}
.tech .in{padding-top:10px}
.hintrow{display:flex;gap:8px;align-items:center;font-size:13px;color:var(--ink2);margin:6px 0 0}
/* ---- khí hậu ---- */
.kps{display:grid;grid-template-columns:repeat(auto-fit,minmax(176px,1fr));gap:12px}
.kp{display:flex;gap:12px;align-items:center;background:#fff;border-radius:18px;padding:12px 14px;border:1px solid color-mix(in srgb,var(--pc) 14%,#E4DFD0);box-shadow:0 8px 20px -14px rgba(23,37,29,.3)}
.kp .ic{flex:none;width:50px;height:50px;border-radius:15px;background:color-mix(in srgb,var(--pc) 10%,#fff);display:grid;place-items:center}.kp .ic svg{width:38px;height:38px}
.kp b{display:block;font:700 22px/1.1 var(--sans)}.kp b small{font-size:13px;font-weight:600;color:var(--ink2)}.kp span{font-size:12.5px;color:var(--ink2)}
.months{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:7px}
@media(max-width:1300px){.months{grid-template-columns:repeat(6,minmax(0,1fr))}}
.mc{position:relative;background:linear-gradient(180deg,#fff,color-mix(in srgb,var(--pc) 5%,#fff));border:1.5px solid var(--line);border-radius:16px;padding:8px 4px 8px;text-align:center;cursor:pointer;font:inherit;color:var(--ink);transition:transform var(--duration-quick) var(--ease-smooth-out),border-color var(--duration-quick),box-shadow var(--duration-quick)}
.mc:hover{transform:translateY(-3px)}.mc.on{border-color:var(--pc);box-shadow:0 0 0 3px color-mix(in srgb,var(--pc) 22%,transparent)}
.mc .mn{font:700 11.5px var(--sans);color:var(--ink2);letter-spacing:.06em}.mc .mi{width:46px;height:46px;margin:2px auto}.mc .mi svg{width:100%;height:100%}
.mc .mt{font:700 16px var(--sans)}.mc .mt small{font-size:11px;font-weight:600;color:var(--ink2)}
.mc .mb{height:38px;display:flex;align-items:flex-end;justify-content:center;margin-top:5px}.mc .mb i{display:block;width:60%;max-width:26px;border-radius:7px 7px 3px 3px;background:linear-gradient(180deg,#8ED4FA,#2F86CF);min-height:3px;transition:height var(--duration-very-slow) var(--ease-smooth-out)}
.mc .mp{font-size:11px;color:var(--ink2);margin-top:2px}
.mdet{display:flex;gap:14px;align-items:center;background:color-mix(in srgb,var(--pc) 8%,#fff);border-radius:14px;padding:10px 14px;margin-top:10px;font-size:14px}
.mdet svg{width:42px;height:42px;flex:none}.mdet b{font-weight:650}
.wlegend{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px;font-size:12.5px;color:var(--ink2)}.wlegend span{display:flex;align-items:center;gap:5px}.wlegend svg{width:22px;height:22px}
.cwrap{position:relative;height:300px}
.wxl{list-style:none;margin:0;padding:0;display:grid;gap:11px}.wxl li{display:flex;gap:12px;align-items:center;font-size:14.5px}
.wxl .wi{flex:none;width:46px;height:46px;border-radius:14px;background:color-mix(in srgb,var(--pc) 9%,#fff);display:grid;place-items:center}.wxl .wi svg{width:34px;height:34px}
.fine{font-size:12.5px;color:var(--ink2);margin-top:10px}
/* ---- đất & nước ---- */
.soilp{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);gap:16px;align-items:start}
/* v0.6 — khu số liệu đất từ vệ tinh/bản đồ đất */
.sd-head{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;justify-content:space-between}.sd-head h3{margin:0}.sd-head small{color:var(--ink2)}
.sd-act{display:flex;gap:8px;flex-wrap:wrap}
.sd-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;margin-top:14px}
.sdt{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:#fff;display:flex;flex-direction:column;gap:6px}
.sdt.diff{border-color:#E0A21F;box-shadow:0 0 0 2px rgba(224,162,31,.15)}
.sdh{display:flex;justify-content:space-between;gap:8px;align-items:center}.sdh b{font:650 14.5px var(--sans)}
.src{font:600 11px var(--sans);border-radius:99px;padding:2px 8px;white-space:nowrap}.s-sat{background:#E6F1FB;color:#1F5F99}.s-me{background:#FFF1D6;color:#8A5A00}.s-def{background:#EEE;color:#666}
.sdv{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.sdv big{font:700 26px var(--sans);color:var(--ink)}.sdv small{color:var(--ink2);font-size:12.5px}
.rb{position:relative;height:12px;margin:6px 0 0}.rb-t{position:absolute;inset:4px 0;border-radius:4px;background:linear-gradient(90deg,#F3D9B0,#E9F1DD,#CFE3F4)}
.rb-band{position:absolute;top:2px;height:8px;border-radius:4px;background:rgba(31,95,153,.28)}
.rb-m{position:absolute;top:-1px;width:4px;height:14px;margin-left:-2px;border-radius:2px;background:#1F5F99}
.rb-u{position:absolute;top:-3px;width:12px;height:12px;margin-left:-6px;transform:rotate(45deg);background:#E0A21F;border:2px solid #fff;box-shadow:0 0 0 1px #B07A00}
.rb-s{display:flex;justify-content:space-between;font-size:11px;color:var(--ink2)}
.sdu{font-size:13px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.sdi{display:flex;gap:8px;align-items:center;font-size:13px}.sdi input{width:96px;padding:5px 8px}.sdi small{color:var(--ink2);font-size:11.5px}
.tx-bar{display:flex;height:16px;border-radius:6px;overflow:hidden;margin-top:4px}.tx-bar i{display:block;height:100%}
.tx-leg{display:flex;gap:10px;font-size:12px;color:var(--ink2);flex-wrap:wrap}.tx-leg span::before{content:"";display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;background:var(--c)}
.sd-why{margin-top:12px;background:#FBF7EC;border-radius:12px;padding:10px 14px;font-size:13px}.sd-why ul{margin:6px 0 0;padding-left:18px}
.sd-key{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin-top:8px}.sd-key i{display:inline-block;vertical-align:middle;margin-right:4px}
@media(max-width:1100px){.soilp{grid-template-columns:1fr}}
.sticky{position:sticky;top:0}
#fieldSvg svg{display:block;width:100%;height:auto;border-radius:16px}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.badges .bd{display:flex;gap:6px;align-items:center;background:color-mix(in srgb,var(--pc) 10%,#fff);color:var(--pd);border-radius:99px;padding:4px 11px 4px 5px;font:600 12.5px var(--sans)}.bd svg{width:22px;height:22px}
.npk{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.npk .sg{display:flex}.npk .sg button{flex:1;justify-content:center;padding:6px 4px;font-size:12px}
.npk label{display:flex;align-items:center;gap:6px}
.phbar{height:14px;border-radius:99px;background:linear-gradient(90deg,#E0553E,#F0A33C,#E7D84A,#6DBE5A,#3FA7C9,#4A6FC9);position:relative;margin:8px 4px 4px}.phbar i{position:absolute;top:-4px;width:6px;height:22px;border-radius:3px;background:#fff;border:2px solid var(--ink);transform:translateX(-50%);transition:left var(--duration-medium) var(--ease-smooth-out)}
.phs{display:flex;justify-content:space-between;font-size:11px;color:var(--ink2);padding:0 2px}
.cg{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:9px}
.cc{position:relative;border:1.5px solid var(--line);border-radius:16px;background:#fff;padding:9px 6px 8px;text-align:center;cursor:pointer;font:inherit;color:var(--ink);transition:transform var(--duration-quick) var(--ease-smooth-out),box-shadow var(--duration-quick),opacity var(--duration-fast)}
.cc:hover{transform:translateY(-2px);box-shadow:0 10px 16px -10px rgba(0,0,0,.35)}
.cc .ci{width:52px;height:52px;margin:0 auto 4px}.cc .ci svg{width:100%;height:100%}.cc b{display:block;font:650 12.5px/1.25 var(--sans)}.cc small{display:block;font-size:11px;color:var(--ink2);margin-top:1px}
.cc.off{opacity:.42}.cc.off b{text-decoration:line-through}
.cc .ring{position:absolute;right:6px;top:6px;width:30px;height:30px}
.cc .gp{display:inline-block;height:3px;width:60%;border-radius:2px;margin-top:5px}
/* ---- luân canh ---- */
.wheel{display:grid;place-items:center}.wheel svg{width:100%;max-width:300px;height:auto}
.rotp{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:16px;align-items:start}
@media(max-width:1100px){.rotp{grid-template-columns:1fr}}
.ent{display:grid;grid-template-columns:54px 1fr auto;gap:4px 12px;align-items:center;background:#fff;border:1.5px solid var(--line);border-radius:16px;padding:10px 12px;margin-bottom:8px;animation:rise var(--duration-slow) var(--ease-smooth-out) both}
.ent .ci{width:54px;height:54px;border-radius:15px;background:color-mix(in srgb,var(--pc) 9%,#fff);display:grid;place-items:center}.ent .ci svg{width:42px;height:42px}
.ent b{font:650 14.5px var(--sans)}.ent small{color:var(--ink2);font-size:12px;display:block}
.ent .del{border:0;background:none;color:var(--warn);cursor:pointer;font-size:20px;border-radius:9px;width:34px;height:34px}.ent .del:hover{background:var(--warn-t)}
.ent .mons{grid-column:1/-1}.ent .yr{display:flex;gap:4px;align-items:center;margin-top:3px}.ent .yr button{border:1px solid var(--line);background:#fff;border-radius:8px;padding:2px 9px;font:600 12px var(--sans);cursor:pointer;color:var(--ink2)}.ent .yr button.on{background:var(--pc);border-color:var(--pc);color:#fff}
.mons{display:grid;grid-template-columns:repeat(12,1fr);gap:3px;margin-top:6px}.mons button{height:26px;border:0;border-radius:7px;background:#F0ECDF;font:600 11px var(--sans);color:var(--ink2);cursor:pointer;transition:background var(--duration-quick)}
.mons button:hover{background:color-mix(in srgb,var(--pc) 22%,#fff)}.mons .grow{background:color-mix(in srgb,var(--pc) 32%,#fff);color:var(--pd)}.mons .sow{background:var(--pc);color:#fff}
.tpl{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.tpl button{border:1.5px solid var(--line);background:#fff;border-radius:14px;padding:9px 6px;cursor:pointer;font:600 12.5px var(--sans);color:var(--ink);display:flex;flex-direction:column;align-items:center;gap:5px;transition:transform var(--duration-quick) var(--ease-smooth-out),border-color var(--duration-quick)}
.tpl button:hover{transform:translateY(-2px);border-color:var(--pc)}.tpl .ic{display:flex}.tpl .ic svg{width:28px;height:28px}
.prefs{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.prf{position:relative;display:flex;flex-direction:column;gap:4px;align-items:flex-start;border:1.5px solid var(--line);background:#fff;border-radius:16px;padding:10px 12px 12px;cursor:pointer;text-align:left;font:inherit;color:var(--ink);transition:transform var(--duration-quick) var(--ease-smooth-out),border-color var(--duration-quick),background var(--duration-quick),box-shadow var(--duration-quick)}
.prf .pi{width:54px;height:54px}.prf .pi svg{width:100%;height:100%}.prf b{font:650 14.5px/1.25 var(--sans)}.prf small{font-size:12px;color:var(--ink2);line-height:1.35}
.prf:hover{transform:translateY(-2px)}.prf.on{border-color:var(--pc);background:color-mix(in srgb,var(--pc) 9%,#fff);box-shadow:0 0 0 3px color-mix(in srgb,var(--pc) 20%,transparent)}
.prf.on:after{content:"";position:absolute;right:10px;top:10px;width:22px;height:22px;border-radius:50%;background:var(--pc) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12.5l4.5 4.5L19 7.5'/%3E%3C/svg%3E") center/13px no-repeat;animation:pop var(--duration-fast) var(--ease-bounce) both}
.xcrop{display:flex;gap:6px;flex-wrap:wrap}.xc{display:flex;align-items:center;gap:5px;border:1.5px solid var(--line);background:#fff;border-radius:99px;padding:3px 11px 3px 4px;font:600 12.5px var(--sans);cursor:pointer;color:var(--ink);transition:background var(--duration-quick),border-color var(--duration-quick),opacity var(--duration-quick)}
.xc svg{width:24px;height:24px}.xc.off{background:var(--warn-t);border-color:var(--warn);color:var(--warn);text-decoration:line-through}.xc.off svg{opacity:.4}
/* ---- thanh ưu tiên có % sống ---- */
.prio{display:grid;grid-template-columns:34px minmax(0,1fr) 54px;gap:4px 12px;align-items:center;margin:0 0 12px}
.prio .pic{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;color:#fff}.prio .pic svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.prio label{margin:0;font:600 13.5px var(--sans);color:var(--ink);display:flex;justify-content:space-between}.prio label small{font-weight:500}
.prio .pv{font:700 17px var(--sans);text-align:right;font-variant-numeric:tabular-nums;min-width:54px}.prio .pv small{font-size:11px;color:var(--ink2);font-weight:600}
.prio .rg{grid-column:2}
input[type=range].fl{-webkit-appearance:none;appearance:none;height:10px;border-radius:99px;background:linear-gradient(90deg,var(--ck,var(--pc)) var(--v,50%),#E6E1D2 var(--v,50%));outline:0;padding:0;border:0;box-shadow:none;cursor:pointer}
input[type=range].fl::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;border-radius:50%;background:#fff;border:3px solid var(--ck,var(--pc));box-shadow:0 3px 8px rgba(0,0,0,.25);transition:transform var(--duration-quick) var(--ease-smooth-out)}
input[type=range].fl::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:#fff;border:3px solid var(--ck,var(--pc));box-shadow:0 3px 8px rgba(0,0,0,.25)}
input[type=range].fl:active::-webkit-slider-thumb{transform:scale(1.18)}
input[type=range].fl:focus-visible{outline:2px solid var(--pc);outline-offset:3px}
/* ---- mô phỏng ---- */
.stress{display:grid;grid-template-columns:1fr 1fr;gap:14px}.stress .dial{display:flex;gap:12px;align-items:center;background:color-mix(in srgb,var(--pc) 7%,#fff);border-radius:16px;padding:12px 14px}
.stress .dial .ic{flex:none;width:56px;height:56px;transition:transform var(--duration-medium) var(--ease-smooth-out)}.dial .ic svg{width:100%;height:100%}.dial .bd{flex:1;min-width:0}.dial label{margin:0 0 4px;display:flex;justify-content:space-between;font-size:13.5px}.dial label b{font:700 16px var(--sans)}
@media(max-width:800px){.stress{grid-template-columns:1fr}}
.pre{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.pre button{display:flex;align-items:center;gap:6px;border:1.5px solid var(--line);background:#fff;border-radius:99px;padding:4px 13px 4px 5px;font:600 12.5px var(--sans);cursor:pointer;color:var(--ink);transition:border-color var(--duration-quick),background var(--duration-quick)}.pre button svg{width:26px;height:26px}.pre button:hover{border-color:var(--pc);background:color-mix(in srgb,var(--pc) 8%,#fff)}
.heat{display:grid;gap:5px;font-size:13px;margin-top:6px}.heat .hr{display:grid;grid-template-columns:minmax(150px,1.2fr) repeat(var(--n),minmax(0,1fr));gap:5px;align-items:stretch}
.heat .hl{display:flex;gap:8px;align-items:center;font-weight:600}.heat .hl svg{width:34px;height:34px;flex:none}
.heat .hc{border-radius:12px;padding:8px 6px;text-align:center;font-weight:700;color:#17251D;font-variant-numeric:tabular-nums;transition:background var(--duration-slow) var(--ease-smooth-out)}.heat .hc small{display:block;font:500 11px var(--sans);opacity:.95}
.heat .hh{font:650 12px var(--sans);text-align:center;padding:2px 4px;color:var(--ink2);display:flex;align-items:flex-end;justify-content:center}.heat .hh i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px}
.wb{display:grid;gap:9px}.wb .r{display:grid;grid-template-columns:150px minmax(0,1fr) 120px;gap:10px;align-items:center;font-size:13px}.wb .t{height:16px;border-radius:99px;background:#EDEADF;overflow:hidden;display:flex}.wb .t i{display:block;height:100%;transition:width var(--duration-very-slow) var(--ease-smooth-out)}
/* ---- kết quả / lab ---- */
.empty{background:#fff;border:1px solid var(--line);border-radius:20px;padding:34px 26px;text-align:center;box-shadow:var(--sh)}
.empty .em{width:150px;height:110px;margin:0 auto 6px}.empty .em svg{width:100%;height:100%}.empty h3{font:600 22px/1.25 var(--serif);margin:6px 0 4px}.empty p{margin:0 auto 14px;max-width:48ch;color:var(--ink2)}
.reco{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:22px;align-items:center;border-radius:22px;padding:24px 28px;color:#fff;background:linear-gradient(115deg,var(--g1),var(--g2) 45%,var(--g3));box-shadow:0 18px 34px -16px color-mix(in srgb,var(--g3) 80%,transparent);overflow:hidden}
.reco:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 90% 10%,rgba(255,255,255,.28),transparent 45%);pointer-events:none}
.reco .ey{font:700 12px var(--sans);letter-spacing:.12em;text-transform:uppercase;opacity:.92}.reco h2{font:600 clamp(26px,3vw,38px)/1.12 var(--serif);color:#fff;margin:6px 0 8px}.reco p{margin:0 0 6px;font-size:15.5px;max-width:58ch;opacity:.97}
.reco .chips2{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.reco .chips2 span{display:flex;gap:6px;align-items:center;background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.35);border-radius:99px;padding:3px 12px 3px 5px;font:600 12.5px var(--sans)}.chips2 svg{width:22px;height:22px}
.reco .ringw{background:rgba(255,255,255,.96);border-radius:50%;padding:6px;box-shadow:0 14px 28px -10px rgba(0,0,0,.5);width:260px;height:260px}.reco .ringw svg{width:100%;height:100%}
@media(max-width:900px){.reco{grid-template-columns:1fr}.reco .ringw{margin:0 auto;width:220px;height:220px}}
.labw{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.1fr) minmax(0,.8fr);gap:22px;align-items:start}
@media(max-width:1350px){.labw{grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr)}.labw>div:last-child{grid-column:1/-1}}
@media(max-width:1000px){.labw{grid-template-columns:1fr}}
.rk2{position:relative}.rk2 .rr{position:absolute;left:0;right:0;height:64px;display:grid;grid-template-columns:34px minmax(0,1fr) 62px;gap:10px;align-items:center;transition:top var(--duration-very-slow) var(--ease-smooth-out)}
.rk2 .rn{width:34px;height:34px;border-radius:50%;background:#EDEADF;display:grid;place-items:center;font:700 15px var(--sans);transition:background var(--duration-medium),color var(--duration-medium)}.rk2 .rr.first .rn{background:var(--pc);color:#fff;box-shadow:0 6px 12px -4px color-mix(in srgb,var(--pc) 70%,transparent)}
.rk2 .nm{font:650 13.5px/1.2 var(--sans);display:flex;gap:7px;align-items:center;margin-bottom:5px}.rk2 .nm i{width:10px;height:10px;border-radius:3px;flex:none}
.rk2 .bar2{display:flex;height:16px;border-radius:99px;overflow:hidden;background:#EDEADF}.rk2 .bar2 i{display:block;height:100%;transition:width var(--duration-slow) var(--ease-smooth-out)}
.rk2 .sc{font:700 22px var(--sans);text-align:right;font-variant-numeric:tabular-nums}.rk2 .sc small{font-size:11px;color:var(--ink2)}
.ckey{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin-top:8px}.ckey span{display:flex;gap:5px;align-items:center}.ckey i{width:10px;height:10px;border-radius:3px}
.best{display:inline-block;background:var(--pc);color:#fff;border-radius:99px;padding:1px 9px;font:700 11px var(--sans);margin-left:6px;vertical-align:1px}
.cmp2{display:grid;grid-template-columns:minmax(150px,1.2fr) repeat(4,minmax(0,1fr));gap:6px;align-items:center;font-size:13px}.cmp2 .hd{font:650 12px var(--sans);color:var(--ink2);text-align:center;display:flex;gap:6px;justify-content:center;align-items:center}.cmp2 .hd svg{width:26px;height:26px}.cmp2 .c{text-align:center;padding:6px 0;border-top:1px solid var(--line)}.cmp2 .nm2{font-weight:650;padding:6px 0;border-top:1px solid var(--line)}
.scx{background:#fff;border:1px solid var(--line);border-radius:16px;padding:6px 14px;margin-bottom:10px}.scx>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:10px;font:650 14.5px var(--sans);padding:8px 0}.scx>summary::-webkit-details-marker{display:none}
.scx>summary i{width:11px;height:11px;border-radius:3px}.scx .k{font:650 13px var(--sans);margin-top:8px}.scx ul{margin:2px 0 8px 18px;padding:0}.scx li{margin:3px 0;font-size:13.5px}
.ai{white-space:pre-wrap;background:color-mix(in srgb,var(--pc) 6%,#fff);border:1px solid color-mix(in srgb,var(--pc) 22%,#e6e0cf);border-radius:14px;padding:14px;margin-top:10px;font-size:14.5px;line-height:1.55}
.aibtns{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.cbox2{position:relative;height:300px}
.legend2{display:flex;gap:12px;flex-wrap:wrap;font-size:12.5px;color:var(--ink2);margin:4px 0 8px}.legend2 i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
/* ---- hộp chọn cây ---- */
.modal{position:fixed;inset:0;z-index:400;background:rgba(18,30,22,.5);display:none;place-items:center;backdrop-filter:blur(3px)}.modal.on{display:grid;animation:reveal var(--duration-medium) var(--ease-out) both}
.sheet{background:#fff;border-radius:24px;width:min(820px,94vw);max-height:86vh;overflow:auto;padding:22px 24px;box-shadow:0 30px 60px -20px rgba(0,0,0,.5)}
.sheet h3{font:600 22px var(--serif);margin:0 0 4px}.sheet .grp{font:700 11.5px var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--ink2);margin:14px 0 8px}
/* ---- thanh chờ & trạng thái ---- */
.shimbar{position:relative;overflow:hidden;border-radius:12px;background:#ECE8DA;height:14px}.shimbar:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.7),transparent);animation:sweep 1.4s var(--ease-linear) infinite}
@keyframes sweep{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.loading{display:grid;gap:10px;padding:6px 0}
.statusbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.leaflet-container{font-family:var(--sans)}
/* ---- màn hình nhỏ ---- */
#stage.compact #banner{height:66px;padding:10px 24px}#stage.compact #banner p{display:none}#stage.compact #banner .st{display:none}#stage.compact #banner h1{margin:0;font-size:22px;line-height:46px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}#stage.compact #banner .art{opacity:.3}
@media(max-width:1000px){
 html:not(.landing) #app{display:block;height:auto;overflow:visible}
 #side{width:auto;height:auto;flex-direction:row;align-items:center;gap:8px;padding:8px 10px;position:sticky;top:0;z-index:100;border-right:0;border-bottom:1px solid var(--line);overflow-x:auto}
 #side .brand{border:0;padding:0;display:flex;align-items:center;gap:8px;text-align:left}#side .brand img{height:38px}#side .brand b{margin:0;font-size:14px}#side .brand small,#side .foot{display:none}
 #nav{flex-direction:row;margin:0}.nb{width:auto;padding:5px 8px;font-size:12.5px}.nb small{display:none}.nb .ti{width:36px;height:36px}.nb .ti svg{width:26px;height:26px}
 #stage{height:auto;min-height:100vh}#pages{overflow:visible}.page.fit.on{display:block;height:auto}
 #banner{margin:10px 10px 0;padding:16px 18px;min-height:120px}#banner .tx{max-width:100%}#banner .art{opacity:.35;width:100%}#farmBadge{display:none}
 .p1{grid-template-columns:1fr}.mapw{height:62vh}.rside{overflow:visible}
 .months{grid-template-columns:repeat(4,minmax(0,1fr))}.prefs{grid-template-columns:1fr}.wb .r{grid-template-columns:1fr}
}
@media(max-height:860px) and (min-width:1001px){#banner{height:104px;padding:12px 26px;margin-top:12px}#banner h1{font-size:clamp(21px,1.8vw,27px);margin:2px 0 3px}#banner p{font-size:13px;line-height:1.35;max-height:36px;overflow:hidden}#banner .st{font-size:10.5px}.page{padding-top:12px}.page.fit.on{padding-bottom:12px}.rside .card{padding:11px 14px}.rside{gap:9px}.ch{margin-bottom:9px}.ch .ti{width:34px;height:34px}.ch .ti svg{width:24px;height:24px}.ex .ic{height:24px;margin-bottom:3px}.ex .ic svg{height:24px;width:24px}}
@media(prefers-reduced-motion:reduce){.nb,.opt,.mc,.cc,.prf,.ex{transition:none}.shimbar:after{animation:none}}
#pages{max-width:none;margin:0;padding:0}#nav{margin:4px 0 0;max-width:none}
#farmBadge{flex-direction:row;align-items:center}#farmBadge div{display:block;min-width:0}
.dbanner{display:none;background:#FFF3D1;color:#7A4E08;border:1px solid #F0D58A;padding:8px 18px;font-weight:600;margin:10px 22px 0;border-radius:12px;font-size:13.5px}.dbanner.show{display:block}
.wb .dr{display:flex;flex-wrap:wrap;align-items:center;gap:1px}.wb .dr span{display:inline-block;width:16px;height:16px}.wb .dr svg{width:16px;height:16px;display:block}.wb .dr small{flex-basis:100%;font-size:11px;color:var(--ink2)}
.empty .run-t{display:none}.empty.running .run-t{display:block}.empty.running button{display:none}
.pre button svg{width:26px;height:26px;display:block}.pre button span{display:inline-grid}
.spin.show{display:inline-flex}
.sg button svg{display:block}
/* ---- hiệu ứng "AI đang dựng giao diện" (ui-generation.js) ---- */
.t-gen{position:absolute;z-index:900;pointer-events:none}
.t-gen-svg{position:absolute;left:0;top:0;overflow:visible}
.t-gen-dot{fill:#2F8A4A}
.t-gen-wire{fill:none;stroke:#2F8A4A;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
.t-gen-head,.t-gen-flyer{fill:#D9692F}
.t-gen-guide{fill:none;stroke:#2F8A4A;stroke-width:1;opacity:.7}
.t-gen-guide--dashed{stroke-dasharray:4 5}
.t-gen-guide--scan{stroke:#D9692F;stroke-width:1.8;opacity:1}
.t-gen-glow-stop{stop-color:#D9692F}
.t-gen-label{fill:#2F8A4A;font:600 11px 'Be Vietnam Pro',system-ui,sans-serif}
.t-gen-label--tag{fill:#D9692F}
.t-gen-reticle{fill:none;stroke:#D9692F;stroke-width:1.4}
.t-gen-panel,.t-gen-steps{display:none}
.t-gen-label{display:none}
@media(max-width:1000px){#banner .art{opacity:.16}}
/* ===== v0.5.1: banner, hoạt ảnh biểu tượng, cảnh thời tiết, bảng điểm ===== */
#banner .art{-webkit-mask-image:linear-gradient(90deg,transparent 0,#000 24%);mask-image:linear-gradient(90deg,transparent 0,#000 24%)}
#banner .tx{max-width:min(68%,940px)}
@media(min-width:1100px){#banner p{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:none}}
.ch{flex-wrap:wrap}.ch h3{min-width:0}.ch .sg{margin-left:auto}
.ray{transform-box:fill-box;transform-origin:center}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes fall{0%{transform:translateY(-4px);opacity:0}30%{opacity:1}100%{transform:translateY(8px);opacity:0}}
@keyframes flash{0%,84%,100%{opacity:1}88%{opacity:.2}92%{opacity:1}96%{opacity:.35}}
@keyframes drift{50%{transform:translateX(3px)}}
.mc:hover .ray,.mdet .ray,.nb:hover .ray,.nb.on .ray,.pre button:hover .ray,.kp:hover .ray{animation:spin 14s linear infinite}
.mc:hover .dp,.mdet .dp,.nb.on .dp,.kp:hover .dp{animation:fall 1.1s ease-in infinite}
.mc:hover .dp:nth-of-type(2),.mdet .dp:nth-of-type(2){animation-delay:.35s}.mc:hover .dp:nth-of-type(3),.mdet .dp:nth-of-type(3){animation-delay:.7s}
.mc:hover .bo,.mdet .bo,.nb.on .bo{animation:flash 2.4s infinite}
.mc:hover .cl,.mdet .cl,.nb.on .cl{animation:drift 3.2s ease-in-out infinite}
.mc .mi svg,.kp .ic svg,.mdet>svg,.wxl .wi svg,.nb .ti svg,.empty .em svg{filter:drop-shadow(0 2px 3px rgba(20,50,80,.2))}
.mc.k-sun,.mc.k-partly{background:linear-gradient(180deg,#FFF8E3,#fff)}.mc.k-rain,.mc.k-storm{background:linear-gradient(180deg,#E7F3FC,#fff)}
.mc.k-hot{background:linear-gradient(180deg,#FFEBDD,#fff)}.mc.k-dry{background:linear-gradient(180deg,#F6EBD8,#fff)}.mc.k-snow,.mc.k-cloud{background:linear-gradient(180deg,#EDF4FA,#fff)}
/* cảnh thời tiết phản ứng với thanh kéo */
.scene{padding:0;overflow:hidden;margin-bottom:14px}
.scene svg{display:block;width:100%;height:clamp(200px,15vw,280px)}
.scene .cap{display:flex;gap:8px;flex-wrap:wrap;padding:10px 16px;background:#fff;border-top:1px solid var(--line);font-size:13px;color:var(--ink2);align-items:center}
.scene .ray{animation:spin 24s linear infinite}
@keyframes rain{0%{transform:translateY(0);opacity:0}12%{opacity:.95}100%{transform:translateY(130px);opacity:0}}
.rd{animation:rain .9s linear infinite}
@keyframes shim2{50%{transform:translateY(-3px)}}.hz{animation:shim2 2.2s ease-in-out infinite}
@keyframes cloudmove{50%{transform:translateX(14px)}}.cm{animation:cloudmove 9s ease-in-out infinite}
.dial .ic{width:70px;height:70px}
/* bảng điểm có vòng tròn */
.heat .hc{display:flex;align-items:center;gap:10px;justify-content:flex-start;text-align:left;padding:8px 12px;position:relative;color:var(--ink);background:color-mix(in srgb,var(--c) 22%,#fff);border:1.5px solid color-mix(in srgb,var(--c) 45%,#fff)}
.heat .hc.best{box-shadow:0 0 0 2.5px var(--c)}
.heat .rg{flex:none;width:48px;height:48px;border-radius:50%;display:grid;place-items:center;position:relative;background:conic-gradient(var(--c) var(--v),rgba(0,0,0,.09) 0)}
.heat .rg:before{content:"";position:absolute;inset:5px;border-radius:50%;background:#fff}.heat .rg b{position:relative;font:700 15px var(--sans);font-variant-numeric:tabular-nums}
.heat .tx{font-size:11px;line-height:1.25;color:var(--ink2);min-width:0;flex:1}.heat .tx b{font-size:14px;color:var(--ink)}
.heat .mb{display:block;height:4px;border-radius:4px;background:rgba(0,0,0,.09);margin-top:3px;overflow:hidden}.heat .mb u{display:block;height:100%;background:var(--c);transition:width var(--duration-slow) var(--ease-smooth-out)}
.heat .crown{position:absolute;right:8px;top:4px;font-style:normal;font-size:12px;color:#B8860B}
.heat .hh{flex-direction:column;align-items:center;gap:3px;justify-content:flex-end}.heat .hh .cr{display:flex}.heat .hh .cr svg{width:24px;height:24px;margin:0 -2px}
.heat .hr{align-items:center}
/* ===== trang mở đầu v0.5.1 ===== */
html.landing{scroll-behavior:smooth}
#landing{background:#0E2A1E;color:#fff;font-family:var(--sans)}
.lp-hero{position:relative;min-height:100vh;display:flex;flex-direction:column;overflow:hidden;background:linear-gradient(96deg,rgba(7,28,19,.96) 0%,rgba(10,36,24,.84) 46%,rgba(12,42,28,.5) 100%),url(/hero.jpg) center/cover,#12301F}
.lp-hero:after{content:"";position:absolute;left:0;right:0;bottom:0;height:150px;background:linear-gradient(transparent,#0E2A1E);pointer-events:none}
.lp-glow{position:absolute;right:-10%;top:-22%;width:62vw;height:62vw;max-width:900px;max-height:900px;background:radial-gradient(circle,rgba(255,205,92,.34),rgba(255,205,92,0) 62%);pointer-events:none}
.lp-top{position:relative;z-index:3;display:flex;align-items:center;gap:26px;padding:22px 5vw}
.lp-top .logo img{height:46px;filter:brightness(0) invert(1)}.lp-top .logo b{font:700 18px var(--sans);letter-spacing:.1em;color:#fff}.lp-top .sp{flex:1}
.lp-lnk{color:#DDE8D6;text-decoration:none;font:500 14.5px var(--sans);opacity:.9;transition:opacity var(--duration-quick)}.lp-lnk:hover{opacity:1;color:#fff}
.lbtn{border:0;border-radius:14px;background:#EBD56E;color:#1C2A13;font:700 16px var(--sans);padding:15px 28px;cursor:pointer;box-shadow:0 14px 28px -12px rgba(235,213,110,.7);transition:transform var(--duration-quick) var(--ease-smooth-out),box-shadow var(--duration-quick),background var(--duration-quick)}
.lbtn:hover{transform:translateY(-2px);background:#F4E285}.lbtn:active{transform:translateY(1px)}.lbtn.sm{padding:9px 18px;font-size:14px;border-radius:11px;box-shadow:none}
.lbtn.o{background:rgba(255,255,255,.08);color:#fff;border:1.5px solid rgba(255,255,255,.5);box-shadow:none;backdrop-filter:blur(4px)}.lbtn.o:hover{background:rgba(255,255,255,.18)}
.lp-main{position:relative;z-index:2;flex:1;display:grid;grid-template-columns:minmax(0,1.02fr) minmax(0,.98fr);gap:3vw;align-items:center;padding:3vh 5vw 11vh}
.lp-pill{display:inline-flex;align-items:center;gap:9px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.28);border-radius:99px;padding:6px 16px 6px 12px;font:600 13px var(--sans);letter-spacing:.02em;backdrop-filter:blur(6px)}
.lp-pill .dot{width:9px;height:9px;border-radius:50%;background:#7BE08E;box-shadow:0 0 0 4px rgba(123,224,142,.25)}
.lp-copy h1{font:600 clamp(42px,5.2vw,84px)/1.03 var(--serif);letter-spacing:-.02em;margin:20px 0 18px;color:#fff;text-wrap:balance}
.lp-copy h1 em{font-style:italic;color:#F1DA78;font-weight:500}
.lp-copy>p{font-size:clamp(16px,1.25vw,19px);line-height:1.6;color:#E1ECDA;max-width:54ch;margin:0 0 28px}
.lp-cta{display:flex;gap:14px;flex-wrap:wrap}
.lp-stats{display:flex;gap:clamp(18px,2.4vw,40px);margin-top:40px;flex-wrap:wrap}.lp-stats div{border-left:2px solid rgba(235,213,110,.7);padding-left:14px}.lp-stats b{display:block;font:600 clamp(26px,2.6vw,38px)/1 var(--serif);color:#fff}.lp-stats span{font-size:13px;color:#C9D9C2}
.lp-stage{position:relative;height:min(600px,62vh);min-height:470px}
.lp-card{position:absolute;background:rgba(255,255,255,.96);color:var(--ink);border-radius:24px;padding:16px 18px;box-shadow:0 30px 60px -24px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.6);animation:lpfloat 7s ease-in-out infinite alternate}
.lp-card.a{left:0;top:30px;width:min(300px,46%);animation-delay:-2s}.lp-card.b{right:0;top:0;width:min(400px,62%);animation-delay:-4s}.lp-card.c{left:14%;bottom:0;width:min(430px,70%);animation-delay:-1s}
@keyframes lpfloat{from{transform:translateY(-7px)}to{transform:translateY(7px)}}
.lp-ct{font:700 12px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:#5E6B63;margin-bottom:8px}.lp-cs{text-align:center;font:600 15px var(--sans);margin-top:4px}
.lp-card svg{display:block}.lp-card.a svg{width:100%;height:auto}
.lp-mon{display:grid;grid-template-columns:repeat(6,1fr);gap:6px}.lp-mon div{text-align:center;background:linear-gradient(180deg,#F0F7FC,#fff);border:1px solid #E1E9EE;border-radius:12px;padding:6px 2px;font:700 12px var(--sans)}.lp-mon svg{width:34px;height:34px;margin:0 auto 2px}.lp-mon small{display:block;color:#68766E;font-weight:600;font-size:10.5px}.lp-mon i{display:block;margin:5px auto 0;width:12px;border-radius:5px 5px 2px 2px;background:linear-gradient(180deg,#8ED4FA,#2F86CF)}
.lp-rk{display:grid;grid-template-columns:28px 1fr 38px;gap:8px;align-items:center;margin:8px 0}.lp-rk .n{width:26px;height:26px;border-radius:50%;background:#EDEADF;display:grid;place-items:center;font:700 13px var(--sans)}.lp-rk .n.f{background:#35904A;color:#fff}.lp-rk b{font:650 12.5px var(--sans);display:block;margin-bottom:3px}.lp-rk .bar2{display:flex;height:11px;border-radius:99px;overflow:hidden;background:#EDEADF}.lp-rk .bar2 i{display:block;height:100%}.lp-rk .sc{font:700 17px var(--sans);text-align:right}
.lp-fl{position:absolute;pointer-events:none;filter:drop-shadow(0 10px 14px rgba(0,0,0,.35));animation:lpfloat 6s ease-in-out infinite alternate}.lp-fl svg{width:100%;height:100%}.lp-fl.f1{width:92px;height:92px;right:0;bottom:6%;animation-delay:-3s}.lp-fl.f2{width:70px;height:70px;left:44%;top:38%;animation-delay:-5s}
.lp-down{position:absolute;z-index:3;left:50%;bottom:24px;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;color:#DDE8D6;text-decoration:none;font:600 12.5px var(--sans);letter-spacing:.1em;text-transform:uppercase;animation:lpbob 2.2s ease-in-out infinite}.lp-down svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
@keyframes lpbob{50%{transform:translate(-50%,6px)}}
.lp-light{background:var(--bg);color:var(--ink)}.lp-dark{background:#0E2A1E;color:#fff}
.lp-sec{max-width:none;margin:0;padding:88px 5vw}
.lp-eye{font:700 12.5px var(--sans);letter-spacing:.14em;color:var(--accent)}.lp-sec h2{font:600 clamp(30px,3.4vw,52px)/1.1 var(--serif);letter-spacing:-.015em;margin:10px 0 12px}.lp-lead{font-size:17px;color:var(--ink2);max-width:60ch;margin:0 0 38px}.lp-dark .lp-lead{color:#C9D9C2}
.lp-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}
.lp-sc{background:#fff;border-radius:24px;overflow:hidden;border:1px solid color-mix(in srgb,var(--pc) 18%,#E4DFD0);box-shadow:0 12px 30px -18px rgba(23,37,29,.4);transition:transform var(--duration-medium) var(--ease-smooth-out),box-shadow var(--duration-medium)}
.lp-sc:hover{transform:translateY(-6px);box-shadow:0 22px 40px -18px rgba(23,37,29,.5)}
.lp-sc .th{position:relative;height:150px;background:linear-gradient(110deg,var(--g1),var(--g2) 55%,var(--g3))}.lp-sc .th svg{position:absolute;inset:0;width:100%;height:100%}
.lp-sc .nm{position:absolute;left:16px;top:14px;width:36px;height:36px;border-radius:50%;background:#fff;color:var(--pd);display:grid;place-items:center;font:700 17px var(--sans);box-shadow:0 6px 12px -4px rgba(0,0,0,.35)}
.lp-sc .bd{padding:18px 20px 22px}.lp-sc h3{margin:0 0 6px;font:650 19px var(--sans)}.lp-sc p{margin:0;color:var(--ink2);font-size:14.5px;line-height:1.5}
.lp-data{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.lp-dc{display:flex;gap:16px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);border-radius:20px;padding:18px 20px;backdrop-filter:blur(4px);transition:background var(--duration-medium),transform var(--duration-medium) var(--ease-smooth-out)}.lp-dc:hover{background:rgba(255,255,255,.12);transform:translateY(-3px)}
.lp-dc .ic{flex:none;width:58px;height:58px;border-radius:16px;background:rgba(255,255,255,.92);display:grid;place-items:center}.lp-dc .ic svg{width:42px;height:42px}
.lp-dc b{display:block;font:650 16px var(--sans)}.lp-dc span{display:block;font-size:13.5px;color:#C9D9C2;margin:2px 0 8px;line-height:1.45}.lp-dc i{font-style:normal;display:inline-block;border-radius:99px;padding:2px 11px;font:700 11.5px var(--sans)}
.lp-dc i.on{background:#7BE08E;color:#0E3B1C}.lp-dc i.c{background:#F1DA78;color:#4A3A06}.lp-dc i.p{background:rgba(255,255,255,.2);color:#fff}
.lp-end{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.7fr);gap:30px;align-items:center;background:linear-gradient(115deg,#E7A33B,#D9692F 55%,#A8431B);padding:70px 5vw;overflow:hidden}
.lp-endc{max-width:760px}.lp-end h2{font:600 clamp(28px,3.2vw,48px)/1.12 var(--serif);margin:0 0 14px;color:#fff}.lp-end p{font-size:17px;line-height:1.6;color:#FFF0E0;margin:0 0 26px}.lp-end .lbtn{background:#fff;color:#8A3410;box-shadow:0 14px 28px -12px rgba(0,0,0,.4)}
.lp-endart svg{width:100%;height:auto;max-height:240px}
.lp-foot{background:#0A2016;color:#9DB5A5;text-align:center;padding:22px;font-size:13px}
@media(max-width:1000px){.lp-main{grid-template-columns:1fr;padding-bottom:12vh}.lp-stage{display:none}.lp-steps,.lp-data{grid-template-columns:1fr 1fr}.lp-end{grid-template-columns:1fr}.lp-lnk{display:none}}
@media(max-width:640px){.lp-steps,.lp-data{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.lp-card,.lp-fl,.lp-down{animation:none}html.landing{scroll-behavior:auto}}
/* ===== v0.7: luồng mới — mùa vụ, tiêu chí SMCA, kết quả, thư viện cây trồng ===== */
[data-p="7"]{--g1:#8C7BC8;--g2:#6A58A8;--g3:#433578;--pc:#6A58A8;--pd:#3E3170;--tint:#EFEBFA;--pl:#D9D1F2}
#nav .sep{height:1px;background:var(--line);margin:8px 10px}
/* thông báo nhỏ về dữ liệu tiêu chí (sidebar) */
.dq{margin:10px 0 4px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:9px 11px;font-size:12.5px;cursor:pointer;transition:box-shadow var(--duration-fast)}
.dq:hover{box-shadow:0 8px 18px -12px rgba(0,0,0,.35)}
.dq-h{display:flex;align-items:center;gap:8px}.dq-h b{flex:1;font-size:12.5px}.dq-h .n{font:700 12px var(--sans);border-radius:99px;padding:1px 8px;background:#EEE;color:#555}
.dq-h .n.ok{background:var(--accent-t);color:var(--accent-d)}.dq-h .n.warn{background:#FFF1D6;color:#8A5A00}
.dq-dots{display:grid;grid-template-columns:repeat(12,1fr);gap:3px;margin:7px 0 3px}
.dq-dots i{height:16px;border-radius:5px;background:#E9E5D9;font:700 8.5px/16px var(--sans);font-style:normal;text-align:center;color:#fff}
.dq-dots i.ok{background:#4E9F4A}.dq-dots i.auto{background:#E0A21F}.dq-dots i.miss{background:#C4492A}.dq-dots i.off{background:#C9C4B5}
.dq-m{color:var(--ink2);line-height:1.4}.dq-m b{color:var(--ink)}
.dq-a{display:flex;gap:6px;margin-top:6px}.dq-a button{flex:1;border:1px solid var(--line);background:#FBFAF6;border-radius:9px;padding:4px 6px;font:600 11.5px var(--sans);cursor:pointer;color:var(--ink)}
.dq-a button:hover{background:#fff;border-color:var(--accent)}
/* bước 2: mùa vụ */
.ssp{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:16px;align-items:start}
.srow{display:grid;grid-template-columns:14px minmax(0,1.2fr) 74px 104px 96px auto;gap:8px;align-items:center;padding:10px 0;border-top:1px dashed var(--line)}
.srow:first-child{border-top:0}.srow .dot{width:14px;height:14px;border-radius:5px}
.srow input,.srow select{padding:7px 9px}.srow small{grid-column:2/-1;color:var(--ink2);margin-top:-4px}
.srow .del{border:0;background:none;font-size:20px;color:#9A8F7A;cursor:pointer}.srow .del:hover{color:var(--warn)}
.srow .qd{grid-column:2/-1;display:flex;gap:5px;flex-wrap:wrap}.srow .qd button{border:1px solid var(--line);background:#fff;border-radius:99px;padding:2px 9px;font:600 11.5px var(--sans);cursor:pointer;color:var(--ink2)}
.srow .qd button.on,.srow .qd button:hover{border-color:var(--pc);color:var(--pd)}
.shead{display:grid;grid-template-columns:14px minmax(0,1.2fr) 74px 104px 96px auto;gap:8px;font:600 11.5px var(--sans);color:var(--ink2);padding:0 0 4px}
.clock svg{width:100%;max-width:380px;display:block;margin:0 auto}
.snow{display:grid;gap:8px;margin-top:10px}.snow .it{display:flex;gap:10px;align-items:center;border-radius:12px;padding:8px 11px;background:var(--tint)}
.snow .it b{font-size:14px}.snow .it small{display:block;color:var(--ink2)}.snow .it .tg{font:700 10.5px var(--sans);text-transform:uppercase;letter-spacing:.06em;border-radius:99px;padding:2px 8px;background:#fff;color:var(--pd);white-space:nowrap}
.snow .it.next{background:color-mix(in srgb,var(--pc) 16%,#fff);border:1.5px solid var(--pc)}
.k1g{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:9px}
.k1c{display:flex;gap:9px;align-items:flex-start;border:1.5px solid var(--line);border-radius:14px;padding:9px 10px;background:#fff}
.k1c .ci{width:38px;height:38px;flex:none}.k1c .ci svg{width:100%;height:100%}.k1c b{display:block;font-size:13.5px}.k1c small{display:block;color:var(--ink2);font-size:11.5px;line-height:1.35}
.k1c.ok{border-color:#9ACB8F;background:#F5FBF3}.k1c.no{border-color:#E7B4A5;background:#FDF5F2}.k1c .ic{margin-left:auto;font:700 15px var(--sans)}.k1c.ok .ic{color:#2E8B4A}.k1c.no .ic{color:#C4492A}
.pcrop{display:flex;gap:8px;flex-wrap:wrap}.pcrop button{display:flex;align-items:center;gap:6px;border:1.5px solid var(--line);background:#fff;border-radius:12px;padding:5px 10px 5px 6px;font:600 13px var(--sans);cursor:pointer;color:var(--ink)}
.pcrop button svg{width:26px;height:26px}.pcrop button.on{border-color:var(--pc);background:var(--tint)}
/* bước 4: đất */
.sdt .cg2{display:grid;gap:6px}.sdt .alt{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:12px}
.sdt .alt button{border:1px solid #BFD3E6;background:#F2F8FD;color:#1F5F99;border-radius:99px;padding:2px 9px;font:600 11.5px var(--sans);cursor:pointer}
.sdt .alt button:hover{background:#E1EEF9}.sdt .code{font:700 11px var(--sans);background:var(--pc);color:#fff;border-radius:7px;padding:1px 7px;margin-right:6px}
.sdt.flash{animation:flash 1.6s ease}@keyframes flash{0%,100%{box-shadow:none}25%{box-shadow:0 0 0 4px color-mix(in srgb,var(--warn) 40%,transparent)}}
.sdt.miss{border-color:#E7B4A5}.sdt .row2{display:flex;gap:8px;align-items:center}.sdt .row2 input,.sdt .row2 select{max-width:190px;padding:6px 9px}
.cstrip{margin-top:4px}.cstrip .r{display:grid;grid-template-columns:78px 1fr;align-items:center;gap:8px;font-size:11.5px;color:var(--ink2);height:16px}
.cstrip .t{position:relative;height:8px;border-radius:99px;background:#F1EEE6}.cstrip .t i{position:absolute;top:0;bottom:0;border-radius:99px}
.cstrip .t i.tol{opacity:.28}.cstrip .t u{position:absolute;top:-4px;bottom:-4px;width:3px;margin-left:-1px;background:#17251D;border-radius:2px}
.chk{display:grid;gap:5px}.chk div{display:grid;grid-template-columns:34px 1fr auto;gap:8px;align-items:center;font-size:12.5px;padding:5px 0;border-top:1px dashed var(--line)}
.chk div:first-child{border-top:0}.chk code{font:700 11px var(--sans);border-radius:7px;padding:2px 0;text-align:center;color:#fff}
.chk .ok code{background:#4E9F4A}.chk .auto code{background:#E0A21F}.chk .miss code{background:#C4492A}.chk .off code{background:#C9C4B5}
.chk small{color:var(--ink2)}.chk button{border:1px solid var(--line);background:#fff;border-radius:8px;padding:2px 8px;font:600 11.5px var(--sans);cursor:pointer}
/* bước 5: tiêu chí */
.crp{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(300px,.8fr);gap:16px;align-items:start}
.pf{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:6px}.pf button{border:1.5px solid var(--line);background:#fff;border-radius:12px;padding:6px 11px;font:600 12.5px var(--sans);cursor:pointer;color:var(--ink);text-align:left}
.pf button small{display:block;font-weight:500;color:var(--ink2);font-size:11px}.pf button.on{border-color:var(--pc);background:var(--tint)}
.cgh{display:flex;align-items:center;gap:8px;margin:14px 0 2px;font:700 12px var(--sans);text-transform:uppercase;letter-spacing:.06em;color:var(--pd)}
.cgh i{width:10px;height:10px;border-radius:3px}.cgh span{margin-left:auto;font:600 12px var(--sans);text-transform:none;letter-spacing:0;color:var(--ink2)}
.crow{display:grid;grid-template-columns:22px 40px minmax(0,1fr) minmax(120px,170px) 48px;gap:9px;align-items:center;padding:8px 0;border-top:1px dashed var(--line)}
.crow.off{opacity:.5}.crow code{font:700 11.5px var(--sans);border-radius:8px;padding:3px 0;text-align:center;color:#fff}
.crow b{font-size:13.5px}.crow small{display:block;color:var(--ink2);font-size:11.5px;line-height:1.35}.crow .pv{font:700 14px var(--sans);text-align:right}
.crow .ds{font:600 10.5px var(--sans);border-radius:99px;padding:1px 7px;margin-left:6px;vertical-align:1px}
.ds.ok{background:var(--accent-t);color:var(--accent-d)}.ds.auto{background:#FFF1D6;color:#8A5A00}.ds.miss{background:var(--warn-t);color:var(--warn)}
.wst{display:flex;height:26px;border-radius:9px;overflow:hidden;margin:6px 0 10px}.wst i{display:block;height:100%;transition:width var(--duration-medium) var(--ease-smooth-out)}
.wl{display:grid;gap:4px}.wl div{display:grid;grid-template-columns:12px 1fr auto;gap:8px;align-items:center;font-size:12.5px}.wl i{width:12px;height:12px;border-radius:4px}
.tog{display:flex;align-items:center;gap:10px;margin:6px 0}.tog input{width:18px;height:18px}
/* bước 6: kết quả */
.mx{display:grid;gap:3px;overflow-x:auto;padding-bottom:4px}
.mx .h{font:700 11px var(--sans);color:var(--ink2);text-align:center;padding:4px 0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;line-height:1.2}
.mx .h small{font-weight:500;font-size:10px}.mx .gh{font:700 10.5px var(--sans);text-transform:uppercase;letter-spacing:.05em;text-align:center;border-radius:8px 8px 0 0;padding:3px 0;color:#fff}
.mx .rn{display:flex;align-items:center;gap:8px;font:700 13.5px var(--sans);padding-right:6px;min-width:0}.mx .rn svg{width:30px;height:30px;flex:none}
.mx .rn small{display:block;font:600 11px var(--sans);color:var(--ink2)}.mx .rn .k{font:700 11px var(--sans);border-radius:99px;padding:1px 7px;background:var(--warn-t);color:var(--warn);white-space:nowrap}
.mx .c{border-radius:9px;min-height:44px;display:grid;place-items:center;font:700 13px var(--sans);cursor:pointer;border:2px solid transparent;transition:transform var(--duration-quick)}
.mx .c:hover{transform:scale(1.05)}.mx .c.sel{border-color:#17251D}.mx .c.na{background:repeating-linear-gradient(45deg,#F1EEE6,#F1EEE6 5px,#E6E1D4 5px,#E6E1D4 10px);color:#9A917E;font-size:11px;cursor:default}
.mx .t{border-radius:9px;min-height:44px;display:flex;align-items:center;gap:8px;padding:0 10px;font:700 15px var(--sans);background:#fff;border:1.5px solid var(--line)}
.mx .t .bb{flex:1;height:7px;border-radius:99px;background:#EFEBDF;overflow:hidden}.mx .t .bb u{display:block;height:100%;border-radius:99px;background:var(--pc)}
.mx .row-x .c,.mx .row-x .t{opacity:.45}.mx .fal{grid-column:2/-1;border:1.5px dashed var(--line);border-radius:9px;min-height:40px;display:flex;align-items:center;padding:0 12px;font-size:12.5px;color:var(--ink2)}
.cinfo{margin-top:10px;border-radius:12px;background:var(--tint);padding:10px 13px;font-size:13px;line-height:1.5;display:none}.cinfo.on{display:block}
.cinfo b{font-size:14px}.cinfo .f{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#fff;border-radius:7px;padding:2px 6px}
.ctb{display:grid;gap:10px}.ctb .r{display:grid;grid-template-columns:120px 1fr 52px;gap:10px;align-items:center}.ctb .r b{font-size:13.5px}
.ctb .bar2{display:flex;height:16px;border-radius:6px;overflow:hidden;background:#F1EEE6}.ctb .bar2 i{display:block;height:100%}
.ctb .r .v{font:700 14px var(--sans);text-align:right}.ctb .r.x{opacity:.45}
.why h4{margin:10px 0 4px;font-size:14px;display:flex;align-items:center;gap:8px}.why h4 svg{width:26px;height:26px}.why ul{margin:0 0 4px 18px;padding:0;font-size:13px}
.why .ok li::marker{color:#2E8B4A}.why .bad li::marker{color:#C4492A}
.scd{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}@media(max-width:1100px){.scd{grid-template-columns:repeat(2,minmax(0,1fr))}}
.scd .dial{display:block}.scd label{display:flex;justify-content:space-between;font-size:12.5px;font-weight:600}.scd label b{color:var(--pd)}
.cmpt{width:100%;border-collapse:separate;border-spacing:0 4px;font-size:13px}.cmpt th{background:none;border:0;font:600 11.5px var(--sans);color:var(--ink2);text-align:left}
.cmpt td{border:0;background:#FBFAF6;padding:7px 9px}.cmpt td:first-child{border-radius:9px 0 0 9px}.cmpt td:last-child{border-radius:0 9px 9px 0}
.up{color:#2E8B4A;font-weight:700}.dn{color:#C4492A;font-weight:700}
.rob{display:grid;gap:6px}.rob div{display:flex;gap:9px;align-items:center;font-size:13px;padding:6px 9px;border-radius:10px;background:#FBFAF6}.rob svg{width:24px;height:24px}.rob span{flex:1}
.warns{display:grid;gap:6px;margin-top:10px}.warns div{background:var(--note);border:1px solid #EBD3A0;border-radius:11px;padding:7px 11px;font-size:12.5px}
/* trang thư viện cây trồng */
.dbg{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}@media(max-width:1200px){.dbg{grid-template-columns:repeat(3,minmax(0,1fr))}}
.dbc{background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px;position:relative;overflow:hidden;box-shadow:var(--sh)}
.dbc:before{content:"";position:absolute;inset:0 0 auto 0;height:5px;background:var(--cc)}.dbc .ci{width:54px;height:54px}.dbc .ci svg{width:100%;height:100%}
.dbc b{display:block;font:700 17px var(--serif)}.dbc i{display:block;font-size:12px;color:var(--ink2)}.dbc .kv{display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:12px;margin-top:8px}
.dbc .kv span{color:var(--ink2)}.dbc.fal{background:repeating-linear-gradient(135deg,#fff,#fff 10px,#FAF8F2 10px,#FAF8F2 20px)}
.cal{display:grid;grid-template-columns:120px repeat(12,1fr);gap:0;font-size:12px;position:relative}
.cal .mh{text-align:center;font:700 11px var(--sans);color:var(--ink2);padding:4px 0;border-left:1px solid #F0ECE1}
.cal .nm{display:flex;align-items:center;gap:6px;font-weight:700;padding:6px 0}.cal .nm svg{width:24px;height:24px}
.cal .ln{grid-column:2/-1;position:relative;height:30px;border-top:1px dashed #EEE9DC}.cal .ln i{position:absolute;top:7px;height:16px;border-radius:6px}
.cal .ln i.s{background:#4E9F4A}.cal .ln i.h{background:#E0A21F}.cal .ln i.g{top:13px;height:4px;background:#CFC8B5;border-radius:3px}
.cal .ln i.v{top:2px;height:26px;border:2px dashed var(--pc);background:color-mix(in srgb,var(--pc) 8%,transparent);border-radius:8px}
.cal .td{position:absolute;top:0;bottom:0;width:2px;background:#C4492A}
.rng .r{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:center;height:34px}.rng .r b{font-size:13px;display:flex;align-items:center;gap:6px}.rng .r b svg{width:22px;height:22px}
.rng .t{position:relative;height:14px;border-radius:99px;background:#F4F1E9}.rng .t i{position:absolute;top:0;bottom:0;border-radius:99px}.rng .t i.tol{opacity:.3}
.rng .t em{position:absolute;top:16px;font:600 10.5px var(--sans);font-style:normal;color:var(--ink2);transform:translateX(-50%);white-space:nowrap}
.rng .ax{position:relative;height:20px;margin-left:130px;border-top:1px solid var(--line)}.rng .ax span{position:absolute;top:3px;font-size:10.5px;color:var(--ink2);transform:translateX(-50%)}
.rng .me{position:absolute;top:-6px;bottom:-26px;width:2px;background:#17251D}.rng .me span{position:absolute;top:-18px;left:4px;font:700 11px var(--sans);white-space:nowrap;background:#17251D;color:#fff;border-radius:6px;padding:1px 6px}
.rng .wrap{position:relative;padding-top:20px}.rng .lane{position:absolute;top:20px;bottom:20px;left:130px;right:0;pointer-events:none}
table.crd td,table.crd th{vertical-align:top;font-size:12.5px;line-height:1.45}table.crd td:first-child{font-weight:700;min-width:150px}
.sref{font:600 10.5px var(--sans);color:#4B3E8A;background:#EFEBFA;border-radius:6px;padding:0 5px;margin:0 1px;text-decoration:none;white-space:nowrap}
.dbsrc li{margin:4px 0;font-size:13px}.dbsrc li:target{background:#FFF4DB;border-radius:6px}

/* trang nguồn dữ liệu & công cụ AI */
[data-p="8"]{--g1:#5A7FB8;--g2:#2F5D9A;--g3:#1B3B6B;--pc:#2F5D9A;--pd:#1B3B6B;--tint:#E8EFF9;--pl:#C9D8EF}
.srch{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}@media(max-width:1100px){.srch{grid-template-columns:repeat(2,minmax(0,1fr))}}
.srch .kp b{font-size:24px}.srch .kp.ok{border-color:#9ACB8F;background:#F5FBF3}.srch .kp.warn{border-color:#EBD3A0;background:#FFF9EC}
.srcg{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.srcc{border:1px solid var(--line);border-radius:14px;padding:12px 14px;background:#fff;display:flex;flex-direction:column;gap:6px}
.srcc .hd{display:flex;align-items:flex-start;gap:8px}.srcc .hd b{flex:1;font-size:14px;line-height:1.35}.srcc .tag{font:700 10.5px var(--sans);border-radius:99px;padding:2px 8px;white-space:nowrap}
.tag.nasa{background:#0B3D91;color:#fff}.tag.oth{background:#EEE;color:#555}.srcc .kv{display:grid;grid-template-columns:86px 1fr;gap:3px 8px;font-size:12.5px}.srcc .kv span{color:var(--ink2)}
.srcc .use{display:flex;gap:4px;flex-wrap:wrap}.srcc .use i{font:700 10.5px var(--sans);font-style:normal;border-radius:7px;padding:1px 6px;background:var(--tint);color:var(--pd)}
.srcc .st{font-size:12px;border-radius:9px;padding:5px 9px}.st.on{background:var(--accent-t);color:var(--accent-d)}.st.wait{background:#F3F1EA;color:#666}.st.err{background:var(--warn-t);color:var(--warn)}
.srcc .cite{font-size:11.5px;color:var(--ink2);background:#FBFAF6;border-radius:8px;padding:6px 8px;position:relative;padding-right:56px}
.srcc .cite button{position:absolute;right:6px;top:6px;border:1px solid var(--line);background:#fff;border-radius:7px;font:600 11px var(--sans);padding:1px 7px;cursor:pointer}
.rsg{margin-bottom:10px}.rsg h4{margin:6px 0;font-size:13px;color:var(--pd)}.rsg div{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:8px;font-size:12.5px;padding:5px 0;border-top:1px dashed var(--line)}
.rsg div small{display:block;color:var(--ink2)}
.aih{margin:4px 0 8px;font-size:14px}.aip{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.aip span{font:600 12px var(--sans);border-radius:99px;padding:3px 10px;border:1px solid var(--line);color:#888}
.aip span.on{border-color:var(--accent);background:var(--accent-t);color:var(--accent-d)}
.aid{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr) minmax(0,1.4fr) 28px;gap:6px;margin-bottom:6px}.aid input,.aid textarea{padding:6px 8px;font-size:12.5px}.aid textarea{min-height:58px;resize:vertical}
.aid button{border:0;background:none;font-size:18px;color:#9A8F7A;cursor:pointer}.aidh{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr) minmax(0,1.4fr) 28px;gap:6px;font:600 11.5px var(--sans);color:var(--ink2);margin-bottom:4px}
.srcmd{white-space:pre-wrap;font:12px/1.55 ui-monospace,Menlo,monospace;background:#FBFAF6;border:1px solid var(--line);border-radius:12px;padding:12px 14px;max-height:360px;overflow:auto;margin:0}
/* ===== v0.8 ===== */
#nav .navl{font:700 10.5px var(--sans);text-transform:uppercase;letter-spacing:.08em;color:#8A948C;margin:12px 12px 4px}
#farmBadge{cursor:pointer}.chip.warn{background:#FFF1D6;color:#8A5A00;border-color:#EBD3A0}
/* trang chủ – giám sát */
.mongrid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(300px,1fr);gap:14px;align-items:stretch}
@media(max-width:1150px){.mongrid{grid-template-columns:1fr}}
.mapbox{position:relative;border-radius:16px;overflow:hidden;border:1px solid var(--line);min-height:430px;background:#EEF1F4}
.mapbox #monMap{position:absolute;inset:0}.mapbox.full{position:fixed;inset:0;z-index:9000;border-radius:0}
.mlayers{position:absolute;left:10px;top:10px;z-index:500;display:flex;gap:6px;flex-wrap:wrap;max-width:calc(100% - 70px)}
.mlayers button{border:0;border-radius:99px;padding:6px 12px;font:700 12.5px var(--sans);background:rgba(255,255,255,.94);box-shadow:0 2px 8px rgba(0,0,0,.15);cursor:pointer;color:#33413A}
.mlayers button.on{background:#17251D;color:#fff}
.mfull{position:absolute;right:10px;bottom:84px;z-index:500;width:36px;height:36px;border:0;border-radius:10px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.18);font-size:17px;cursor:pointer}
.mtime{position:absolute;left:10px;right:10px;bottom:10px;z-index:500;display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.95);border-radius:12px;padding:7px 12px;box-shadow:0 2px 8px rgba(0,0,0,.15)}
.mtime input{flex:1}.mtime b{font:700 13px var(--sans);white-space:nowrap;min-width:92px;text-align:right}.mtime button{border:0;width:30px;height:30px;border-radius:50%;background:#17251D;color:#fff;cursor:pointer;font-size:12px}
.mleg{position:absolute;left:10px;bottom:62px;z-index:500;background:rgba(255,255,255,.95);border-radius:10px;padding:6px 10px;font-size:11.5px;display:grid;grid-template-columns:auto auto;gap:2px 10px;box-shadow:0 2px 8px rgba(0,0,0,.12)}
.mleg b{grid-column:1/-1;font-size:12px}.mleg i{grid-column:1/-1;display:block;height:9px;border-radius:5px;width:190px}.mleg span:last-child{text-align:right}
.mmsg{position:absolute;left:10px;right:10px;top:52px;z-index:500;font-size:12.5px}.mmsg:not(:empty){background:#FFF4D6;border:1px solid #EBD3A0;border-radius:10px;padding:7px 10px}
.monside{display:flex;flex-direction:column;min-width:0}.mnow{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.mk{border-radius:14px;padding:9px 11px;background:var(--lb);border:1.5px solid color-mix(in srgb,var(--lc) 40%,transparent)}.mk.off{opacity:.55}
.mkh{display:flex;align-items:center;gap:6px}.mkh code{font:700 10.5px var(--sans);border-radius:6px;padding:1px 5px;color:#fff}.mkh b{font-size:13px;flex:1}
.mk .lv,.ma .lv{font:700 10.5px var(--sans);border-radius:99px;padding:1px 8px;background:var(--lc);color:#fff;white-space:nowrap}
.mkv{font:700 21px var(--serif);margin:3px 0 0}.mkv small{display:block;font:500 11px var(--sans);color:var(--ink2)}.mkb{font-size:11.5px;color:var(--ink2);margin-top:3px;line-height:1.4}
.malerts{display:grid;gap:7px;overflow:auto;max-height:260px}.ma{border-radius:12px;padding:8px 11px;background:var(--lb);border-left:4px solid var(--lc);font-size:12.5px}
.ma div{display:flex;gap:8px;align-items:center}.ma small{display:block;margin-top:3px;line-height:1.4}.ma i{display:block;font-size:11px;color:var(--ink2);margin-top:2px}
.ma.ok{--lc:#4E9F4A;--lb:#EAF5E7}
.monchart{margin-top:14px}.monchart .ch2{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}.monchart .cwrap{height:260px}
.moncfg{border:1.5px solid var(--pc);border-radius:16px;padding:14px 16px;margin:0 0 14px;background:#fff}
.mcg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}@media(max-width:1100px){.mcg{grid-template-columns:1fr}}.mcg h4{margin:0 0 6px;font-size:14px}
.mcg select,.mcg input[type=number]{width:100%}
/* kịch bản dùng chung */
.scene-w{position:relative;border-radius:14px;overflow:hidden;margin-bottom:12px}.scene-w .scene svg{display:block;width:100%;height:auto}
.sclab{position:absolute;left:10px;top:10px;display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.92);border-radius:12px;padding:5px 12px 5px 6px;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.12)}
.sclab:empty{display:none}.sclab svg{width:30px;height:30px}.scrow{margin-top:10px;align-items:center;gap:10px;flex-wrap:wrap}.scmsg{font-size:13px;margin:0 0 6px}
/* mùa vụ */
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.scard{border:1.5px solid var(--line);border-top:5px solid var(--sc);border-radius:16px;padding:12px 14px;background:#fff;display:flex;flex-direction:column;gap:8px}
.scard label{font:600 12px var(--sans);color:var(--ink2);margin:0}.sch{display:flex;align-items:center;gap:8px}
.sch .num{width:26px;height:26px;border-radius:50%;background:var(--sc);color:#fff;font:700 13px var(--sans);display:grid;place-items:center;flex:none}
.sch input{flex:1;font:700 15px var(--sans);border:1px solid transparent;background:#FBFAF6;padding:6px 9px;border-radius:9px}.sch input:focus{border-color:var(--sc);background:#fff}
.sch .del{border:0;background:none;font-size:22px;color:#9A8F7A;cursor:pointer;line-height:1}.sch .del:hover{color:var(--warn)}
.scrop{display:flex;gap:6px;flex-wrap:wrap}.scrop button{display:flex;align-items:center;gap:5px;border:1.5px solid var(--line);background:#fff;border-radius:10px;padding:4px 9px 4px 5px;font:600 12.5px var(--sans);cursor:pointer;color:var(--ink)}
.scrop button svg{width:22px;height:22px}.scrop button.on{border-color:var(--sc);background:color-mix(in srgb,var(--sc) 12%,#fff)}
.sdates{display:grid;grid-template-columns:1.3fr 1fr;gap:10px}.sdates label{display:flex;flex-direction:column;gap:4px}.sdates input{padding:7px 9px;font:600 14px var(--sans)}
.dur{display:flex;align-items:center;gap:6px}.dur input{width:100%}.dur i{font-style:normal;font-size:12.5px;color:var(--ink2)}
.scard .qd{display:flex;gap:5px;flex-wrap:wrap}.scard .qd button{border:1px solid var(--line);background:#fff;border-radius:99px;padding:2px 9px;font:600 11.5px var(--sans);cursor:pointer;color:var(--ink2)}
.scard .qd button.on,.scard .qd button:hover{border-color:var(--sc);color:var(--ink)}.send{font-size:12.5px;color:var(--ink2);border-top:1px dashed var(--line);padding-top:7px}
.scard.add{border:2px dashed var(--line);border-top-width:2px;align-items:center;justify-content:center;min-height:160px;cursor:pointer;font:700 14px var(--sans);color:var(--ink2);background:#FBFAF6}
.scard.add span{font-size:30px;line-height:1}.scard.add:hover{border-color:var(--pc);color:var(--pd)}
.snow .it .ci{width:30px;height:30px;flex:none;display:grid;place-items:center}.snow .it .ci svg{width:30px;height:30px}
/* khí hậu */
.c3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.c3 .cwrap{height:260px}
.kpi1{text-align:right}.kpi1 b{display:block;font:700 20px var(--serif)}.kpi1 small{font-size:11.5px;color:var(--ink2)}
/* đất & địa hình */
.igrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:12px}
.ic2{border:1.5px solid var(--line);border-radius:16px;padding:12px 14px;background:#fff;display:flex;flex-direction:column;gap:8px}.ic2.wide{grid-column:1/-1}
.ic2.miss{border-color:#E7B4A5;background:#FFFBF9}.ic2.flash{animation:flash 1.6s ease}
.ich{display:flex;align-items:center;gap:8px}.ich code{font:700 11.5px var(--sans);border-radius:8px;padding:2px 7px;color:#fff}.ich b{font-size:14.5px}
.icv{font:700 24px var(--serif);line-height:1.15}.icv small{font:500 12px var(--sans);color:var(--ink2);margin-left:5px}
.ics{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.ics button{border:1px solid #BFD3E6;background:#F2F8FD;color:#1F5F99;border-radius:99px;padding:2px 9px;font:600 11.5px var(--sans);cursor:pointer}
.ici input,.ici select{width:100%;padding:7px 9px}
.b1r{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px 18px}.b1r div,.e1r div{display:grid;grid-template-columns:150px 1fr 44px;gap:8px;align-items:center;font-size:13.5px}
.b1r span,.e1r span{display:flex;align-items:center;gap:7px;font-weight:600}.b1r span svg,.e1r span svg{width:26px;height:26px}
.b1r i{height:9px;border-radius:99px;background:#F1EEE6;overflow:hidden}.b1r i u{display:block;height:100%;border-radius:99px}.b1r b{text-align:right;font-size:15px}
.e1r{display:grid;gap:6px}.e1r div{grid-template-columns:1fr auto}
/* tiêu chí: cỡ chữ đồng bộ */
.crow{grid-template-columns:24px 46px minmax(0,1fr) minmax(130px,190px) 54px;padding:11px 0}.crow b{font-size:15px}.crow code{font-size:12.5px}.crow .pv{font-size:15.5px}
.crow .ds{font-size:11px}.cgh{font-size:12.5px}.pf button{font-size:13.5px;padding:8px 12px}.pf button small{font-size:11.5px}.wl div{font-size:13.5px}
/* kết quả: cột tổng trung tính */
.mx .t .bb u{background:#17251D}
/* nguồn ở cuối trang + lưu ý */
.pgsrc{margin-top:18px;padding:10px 14px;border-top:1px dashed var(--line);font-size:12px;color:var(--ink2);display:flex;gap:6px 12px;flex-wrap:wrap;align-items:center}
.pgsrc span{font-weight:700}.pgsrc a{color:var(--pd);text-decoration:none;border-bottom:1px dotted currentColor}.pgsrc a.more{margin-left:auto;font-weight:700}
.notes{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px}.ng{border:1px solid var(--line);border-radius:14px;padding:10px 14px;background:#fff}
.ng h4{margin:0 0 6px;font-size:14px}.ng ul{margin:0 0 0 18px;padding:0;font-size:13px;line-height:1.5}.ng.cur{border-color:#EBD3A0;background:#FFF9EC}
.mkh b{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}.scrow{justify-content:flex-start!important}.scrow .sg{width:auto}
#climRecent{margin-top:14px}#climRecent .cwrap{height:340px}

/* v0.9 trang chủ toàn màn hình */
body.landing #side,body.landing #banner{display:none}
body.landing #tab0{padding:0}
#tab0 .hero{position:relative;height:calc(100vh - 54px);min-height:520px}
#tab0 .mapbox{position:absolute;inset:0;border-radius:0;border:0;min-height:0}
.hbrand{position:absolute;left:16px;top:14px;z-index:600;display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.95);border-radius:16px;padding:8px 14px 8px 8px;box-shadow:0 4px 16px rgba(0,0,0,.14)}
.hbrand img{width:42px;height:42px;object-fit:contain}.hbrand b{display:block;font:800 16px var(--sans);letter-spacing:.04em}.hbrand small{display:block;font-size:12px;color:var(--ink2)}
#tab0 .mlayers{left:50%;top:18px;transform:translateX(-50%);max-width:none;justify-content:center}
#tab0 .mlayers button{padding:8px 15px;font-size:13.5px}
.hpanel{position:absolute;right:16px;top:14px;z-index:600;width:min(380px,calc(100vw - 32px));max-height:calc(100% - 120px);display:flex;flex-direction:column;background:rgba(255,255,255,.97);border-radius:18px;box-shadow:0 8px 28px rgba(0,0,0,.18);overflow:hidden}
.hph{display:flex;align-items:center;gap:8px;padding:11px 12px 10px 14px;border-bottom:1px solid var(--line)}
.hph b{font:800 15px var(--sans)}.hdot{width:12px;height:12px;border-radius:50%;background:#4E9F4A;box-shadow:0 0 0 4px color-mix(in srgb,currentColor 0%,transparent)}
.hpanel[data-lv="2"] .hdot,.hpanel[data-lv="3"] .hdot{animation:pulse 1.6s infinite}@keyframes pulse{50%{transform:scale(1.35)}}
.ib{border:0;background:#F1F3F1;border-radius:9px;width:30px;height:30px;cursor:pointer;font-size:15px}
.hpb{padding:10px 14px 14px;overflow:auto}.hpanel.min .hpb{display:none}
.hsub{display:block;font-size:12px;color:var(--ink2);margin-bottom:8px}
.hpanel .malerts{max-height:none}.hnow{margin-top:10px}.hnow summary{cursor:pointer;font:700 13px var(--sans);color:var(--accent)}.hnow .mnow{margin-top:8px}
.hpanel #homeNoFarm p{margin:0 0 10px;font-size:13.5px}
#tab0 .mmsg{left:50%;transform:translateX(-50%);top:66px;right:auto;width:min(560px,60%)}
#tab0 .mleg{left:16px;bottom:84px}
#tab0 .mtime{left:16px;right:auto;bottom:18px;width:min(620px,calc(100% - 420px))}
.hcta{position:absolute;right:16px;bottom:18px;z-index:600;display:flex;flex-direction:column;align-items:flex-end;gap:8px}
.hcta .b.big{box-shadow:0 8px 24px rgba(0,0,0,.25);font-size:17px;padding:14px 24px}
.hdown{border:0;background:rgba(255,255,255,.95);border-radius:99px;padding:8px 14px;font:700 13px var(--sans);cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.15);color:#33413A}
#tab0 .leaflet-bottom.leaflet-right{bottom:120px}
.homelow{max-width:1280px;margin:0 auto;padding:22px 22px 34px}
#monCfg:not([hidden]){position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9500;width:min(1100px,94vw);max-height:90vh;overflow:auto;margin:0;box-shadow:0 0 0 100vmax rgba(20,30,25,.45),0 20px 50px rgba(0,0,0,.3)}
.nhome{display:block;width:100%;text-align:left;border:1px solid var(--line);background:#fff;border-radius:12px;padding:9px 12px;font:700 13px var(--sans);cursor:pointer;color:var(--accent);margin-bottom:4px}
.nhome:hover{background:#F7FAF6}
@media(max-width:900px){#tab0 .mtime{width:calc(100% - 32px);bottom:88px}.hcta{left:16px;right:16px;align-items:stretch}#tab0 .mleg{bottom:150px}.hpanel{top:auto;bottom:220px;max-height:40%}#tab0 .mlayers{top:72px}}
#monCfg{--g1:#55A9DC;--g2:#2F7DB8;--g3:#1B5890;--pc:#2F7DB8;--pd:#1B4F7E;--tint:#E5F2FB;--pl:#C8E3F5}

/* v0.9.1 trang chủ: thẻ mở đầu cùng phong cách với các trang trong */
.hbrand{display:none}
.hcard{position:absolute;left:18px;top:18px;bottom:96px;z-index:600;width:min(440px,calc(100vw - 36px));display:flex;flex-direction:column;gap:12px;background:linear-gradient(180deg,#FBF9F3,#F3F0E6);border:1px solid var(--line);border-radius:24px;padding:14px;box-shadow:0 18px 40px -16px rgba(30,40,30,.35);overflow:auto}
.hcb{display:flex;align-items:center;gap:10px;padding:2px 4px}.hcb img{width:44px;height:44px;object-fit:contain}.hcb b{display:block;font:800 17px var(--sans);letter-spacing:.06em}.hcb small{display:block;font-size:11.5px;color:var(--ink2)}
.hban{position:relative;border-radius:18px;padding:18px 18px 16px;color:#fff;overflow:hidden;background:linear-gradient(115deg,var(--g1),var(--g2) 55%,var(--g3));box-shadow:0 12px 26px -12px color-mix(in srgb,var(--g3) 70%,transparent);min-height:170px}
.hban .art{position:absolute;right:-30px;top:0;bottom:0;width:72%;opacity:.55;pointer-events:none}
.hban .tx{position:relative}.hban .st{font:700 11px var(--sans);letter-spacing:.13em;text-transform:uppercase;opacity:.92}
.hban h1{font:600 28px/1.12 var(--serif);margin:6px 0 8px;text-wrap:balance;text-shadow:0 2px 10px rgba(0,0,0,.18);max-width:15ch}
.hban p{margin:0;font-size:13.5px;line-height:1.45;opacity:.96;max-width:34ch}
.hfarm{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:9px 12px}
.hfarm .pn{width:34px;height:40px;flex:none}.hfarm .pn svg{width:100%;height:100%}.hfarm div{flex:1;min-width:0}.hfarm b{display:block;font-size:14px}.hfarm small{display:block;font-size:12px;color:var(--ink2)}
.hacts{display:flex;gap:8px}.hacts .b.big{flex:1;font-size:16px;padding:13px 16px}
.hsteps small{display:block;font:700 11px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--ink2);margin:2px 4px 6px}
#hSteps{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
#hSteps button{display:flex;align-items:center;gap:6px;border:1px solid var(--line);background:#fff;border-radius:12px;padding:6px 8px;font:600 12.5px var(--sans);color:var(--ink);cursor:pointer;text-align:left}
#hSteps button:hover{border-color:var(--accent);background:#F7FAF6}#hSteps span{width:24px;height:24px;flex:none}#hSteps span svg{width:100%;height:100%}#hSteps b{color:var(--accent)}
#tab0 .mlayers{left:calc(50% + 30px);background:rgba(251,249,243,.92);border:1px solid var(--line);border-radius:99px;padding:4px;box-shadow:0 6px 18px -8px rgba(0,0,0,.25);gap:4px}
#tab0 .mlayers button{box-shadow:none;background:transparent}#tab0 .mlayers button.on{background:var(--accent);color:#fff}
.hpanel{background:linear-gradient(180deg,#FBF9F3,#F6F3EA);border:1px solid var(--line);border-radius:22px;box-shadow:0 18px 40px -16px rgba(30,40,30,.35)}
.hph{background:#fff}
#tab0 .mleg,#tab0 .mtime{background:rgba(251,249,243,.96);border:1px solid var(--line);box-shadow:0 8px 20px -10px rgba(0,0,0,.3)}
#tab0 .mleg{left:auto;right:18px;bottom:84px}
#tab0 .mtime{left:476px;right:18px;width:auto;bottom:18px;border-radius:16px}
#tab0 .mtime button{background:var(--accent)}
#tab0 .leaflet-bottom.leaflet-right{bottom:150px}
.pwimg,.hs{mix-blend-mode:multiply}
#tab0 .hero::after{content:"";position:absolute;left:0;right:0;bottom:0;height:46px;background:linear-gradient(180deg,transparent,var(--bg));z-index:450;pointer-events:none}
#tab0 .leaflet-container{background:#E9EEF0}
@media(max-width:900px){.hcard{position:relative;left:auto;top:auto;bottom:auto;width:auto;margin:12px}#tab0 .hero{height:auto}#tab0 .mapbox{position:relative;height:70vh}#tab0 .mlayers{left:50%}#tab0 .mtime{left:16px}}
.hcard{bottom:auto;max-height:calc(100% - 120px)}
.hban h1{max-width:none;font-size:27px;padding-right:70px}.hban p{max-width:36ch}
.hpanel #homeNoFarm p{color:var(--ink)}

/* v0.9.2 thẻ mở đầu gọn hơn; phần kịch bản toàn màn hình, cùng kiểu banner + thẻ với trang trong */
.hcard{width:min(372px,calc(100vw - 36px));gap:10px;padding:12px;border-radius:22px}
.hcb img{width:36px;height:36px}.hcb b{font-size:15px}.hcb small{font-size:11px}
.hcard .hban{min-height:0;padding:14px 16px;border-radius:16px}
.hcard .hban h1{font-size:22px;margin:4px 0 6px}.hcard .hban p{font-size:12.5px;max-width:32ch}.hcard .hban .st{font-size:10px}
.hfarm{padding:7px 10px;border-radius:14px}.hfarm .pn{width:28px;height:34px}.hfarm b{font-size:13px}.hfarm small{font-size:11.5px}
.hacts .b.big{font-size:14.5px;padding:10px 12px}.hacts .b{padding:9px 12px}
#tab0 .mtime{left:410px}
#tab0 .mlayers{left:calc(50% + 0px)}
.homelow{max-width:none;margin:0;min-height:100vh;display:flex;flex-direction:column;gap:14px;padding:18px 22px 22px;background:linear-gradient(180deg,#FCEBDD 0,var(--bg) 380px)}
.lban{display:flex;align-items:flex-end;gap:16px;min-height:136px;padding:20px 28px;border-radius:22px;flex:none}
.lban .art{right:0;width:min(55%,600px);opacity:1}.lban .tx{flex:1;max-width:min(62%,760px)}
.lban h1{font-size:clamp(22px,2vw,31px);max-width:none}.lban p{max-width:60ch;font-size:14px}
.hsbtn{position:relative;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.hsbtn .b.ghost{background:rgba(255,255,255,.92)}
.hscen{flex:1;display:flex;flex-direction:column;margin:0}
#homeScen{flex:1}
#homeScen .scw{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(380px,1fr);grid-template-rows:auto auto 1fr;gap:12px 18px;height:100%}
#homeScen .scene-w{grid-column:1;grid-row:1;margin:0}
#homeScen .scd{grid-column:1;grid-row:2;grid-template-columns:repeat(2,minmax(0,1fr))}
#homeScen .scrow{grid-column:1;grid-row:3;align-self:start;flex-wrap:wrap}
#homeScen [id$="Cmp"]{grid-column:2;grid-row:1/4;margin:0;background:#FBF9F3;border:1px solid var(--line);border-radius:16px;padding:12px 14px;overflow:auto}
#homeScen .scene svg{height:clamp(220px,30vh,330px);width:100%}
@media(max-width:1150px){#homeScen .scw{grid-template-columns:1fr}#homeScen [id$="Cmp"]{grid-column:1;grid-row:auto}.lban{flex-direction:column;align-items:flex-start}}
#homeScen .scene svg{height:clamp(190px,24vh,250px)}
#homeScen .scrow{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center}
#homeScen .scrow .sg{display:inline-flex;flex-wrap:nowrap;width:auto}#homeScen .scrow .sg button{white-space:nowrap}
#homeScen .scrow .pre{flex-basis:100%;display:flex;flex-wrap:wrap;gap:6px}
.homelow .pgsrc{margin-top:0}
#homeScen .scw{grid-template-rows:1fr auto auto}
#homeScen .scene-w{display:flex;flex-direction:column;min-height:220px}
#homeScen .scene{flex:1;margin:0;position:relative}
#homeScen .scene svg{position:absolute;inset:0;height:100%}
#homeScen{display:flex;flex-direction:column}#homeScen .scw{flex:1;height:auto}
#tab0 .hero{height:100vh}
.hacts .b{white-space:nowrap}.hacts .b.big{flex:1}
/* v0.9 bài toán & luân canh */
.pmode{margin-bottom:14px}.modes{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.mopt{display:flex;align-items:center;gap:12px;text-align:left;border:1.5px solid var(--line);background:#fff;border-radius:16px;padding:12px 14px;cursor:pointer;font:inherit;color:var(--ink)}
.mopt .ti{width:44px;height:44px;flex:none}.mopt .ti svg{width:100%;height:100%}.mopt b{display:block;font-size:15px}.mopt small{display:block;font-size:12.5px;color:var(--ink2);line-height:1.4}
.mopt i{font-style:normal;font:700 12px var(--sans);border-radius:99px;padding:4px 10px;background:#F1EFE7;color:var(--ink2);white-space:nowrap}
.mopt.on{border-color:var(--pc);background:color-mix(in srgb,var(--pc) 8%,#fff);box-shadow:0 0 0 3px color-mix(in srgb,var(--pc) 18%,transparent)}.mopt.on i{background:var(--pc);color:#fff}
@media(max-width:900px){.modes{grid-template-columns:1fr}}
.chform{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.chform label{display:flex;flex-direction:column;gap:4px;font:600 12.5px var(--sans);color:var(--ink2);margin:0}
.chform input,.chform select{font:15px var(--sans);padding:9px 10px;border:1.5px solid var(--line);border-radius:10px;background:#fff}
.chform .dur{display:flex;align-items:center;gap:6px}.chform .dur input{flex:1;min-width:0}
@media(max-width:1000px){.chform{grid-template-columns:1fr 1fr}}
.chtl{margin-top:14px}.tlbar{position:relative;height:80px;border-radius:12px;background:repeating-linear-gradient(90deg,#FBFAF6 0 40px,#F6F3EA 40px 80px);border:1px solid var(--line)}
.tlbar .yr{position:absolute;top:0;bottom:0;border-left:1.5px dashed #C9C2AE;font:700 11px var(--sans);color:var(--ink2);padding-left:4px}
.tlbar .sw{position:absolute;height:9px;border-radius:5px;opacity:.9}
.tll{display:flex;gap:14px;flex-wrap:wrap;margin-top:6px;font-size:12px;color:var(--ink2)}.tll i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.econ{display:grid;gap:10px}.econ .ea{display:flex;align-items:center;gap:10px;font:600 13px var(--sans);margin:0}.econ .ea .dur{display:flex;align-items:center;gap:6px}
.econ input{font:14px var(--sans);padding:7px 9px;border:1.5px solid var(--line);border-radius:9px;width:120px;background:#fff}
.etab{width:100%;border-collapse:collapse;font-size:13.5px}.etab th{text-align:left;font:700 12px var(--sans);color:var(--ink2);padding:6px 8px;border-bottom:1px solid var(--line)}
.etab td{padding:6px 8px;border-bottom:1px solid #F0ECE0}.etab td:first-child{display:flex;align-items:center;gap:6px;font-weight:600}.etab td:first-child svg{width:22px;height:22px}.etab .g{font-weight:700;color:var(--accent)}
.k4l{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}.k4p{display:inline-flex;align-items:center;gap:4px;border:1px solid var(--line);border-radius:99px;padding:3px 4px 3px 8px;font:600 12.5px var(--sans);background:#fff}
.k4p svg{width:18px;height:18px}.k4p button{border:0;background:#F3E3DF;color:#A33;border-radius:50%;width:20px;height:20px;cursor:pointer}
.k4a{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.k4a select{font:13px var(--sans);padding:6px 8px;border:1.5px solid var(--line);border-radius:9px;background:#fff}
.rotw{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,1fr);gap:14px;align-items:start}@media(max-width:1150px){.rotw{grid-template-columns:1fr}}
.rotleg{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:12px;color:var(--ink2)}.rotleg i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:-2px}.rotleg i.g{background:hsl(125 45% 70%)}.rotleg i.r{background:hsl(8 70% 80%)}.rotleg p{flex-basis:100%;margin:2px 0 0}
.rothow p{margin:0 0 9px;font-size:13.5px;line-height:1.5}
.chains{display:grid;gap:8px}.chn{display:grid;grid-template-columns:44px minmax(0,1fr) 110px;align-items:center;gap:10px;border:1px solid var(--line);border-radius:14px;padding:8px 12px;background:#fff}
.chn.top{border-color:var(--pc);background:color-mix(in srgb,var(--pc) 7%,#fff)}.chn .rk{font:700 18px var(--serif);color:var(--pc)}
.chn .seq{display:flex;flex-wrap:wrap;align-items:center;gap:6px}.chn .it{display:inline-flex;flex-direction:column;align-items:flex-start;border:1px solid #EEE9DC;border-radius:11px;padding:4px 9px 5px 32px;position:relative;background:#FBFAF6;min-width:118px}
.chn .it svg{position:absolute;left:6px;top:7px;width:22px;height:22px}.chn .it b{font-size:13px}.chn .it small{font-size:11px;color:var(--ink2);line-height:1.3}.chn .it.fal{background:#F1EFE7;border-style:dashed}
.chn .ar{color:var(--ink2);font-weight:700}.chn .sc{text-align:right}.chn .sc b{display:block;font:700 22px var(--serif)}.chn .sc small{display:block;font-size:11.5px;color:var(--ink2)}
table.vtab{width:100%;border-collapse:collapse;font-size:13.5px}table.vtab th{text-align:left;font:700 12px var(--sans);color:var(--ink2);padding:7px 8px;border-bottom:1.5px solid var(--line)}
table.vtab td{padding:8px;border-bottom:1px solid #F0ECE0;vertical-align:middle}table.vtab td svg{width:22px;height:22px;vertical-align:-6px;margin-right:6px}table.vtab tr.x td{opacity:.55}table.vtab small{color:var(--ink2)}
.mx .t small.vm{display:block;font:600 11px var(--sans);color:var(--pc);margin-top:2px}
#scen3{margin:0}.s3k{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}@media(max-width:1100px){.s3k{grid-template-columns:1fr 1fr}}
.s3i{display:flex;align-items:center;gap:7px;border:1.5px solid var(--line);border-radius:12px;padding:7px 9px;margin:0;font:600 12.5px var(--sans);background:#fff;flex-wrap:wrap}
.s3i.on{border-color:var(--pc);background:color-mix(in srgb,var(--pc) 7%,#fff)}.s3i code{color:#fff;border-radius:6px;padding:1px 6px;font:700 11px var(--sans)}.s3i em{font-style:normal;color:var(--pc)}
.s3i .dur{display:flex;align-items:center;gap:4px;margin-left:auto}.s3i .dur input{width:70px;font:13px var(--sans);padding:5px 6px;border:1.5px solid var(--line);border-radius:8px}.s3i .dur i{font-style:normal;font-size:11.5px;color:var(--ink2)}
.s3b{gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap}.s3b .sp{flex:1}
.s3g{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}@media(max-width:1000px){.s3g{grid-template-columns:1fr}}
.s3c{border:1px solid var(--line);border-radius:16px;padding:10px 12px;background:#FBF9F3}.s3c.pl{border-top:4px solid #D4572A}.s3c.mi{border-top:4px solid #2F86CF}
.s3h b{display:block;font:700 14px var(--sans)}.s3h small{display:block;color:var(--ink2);font-size:12px;margin:2px 0 6px}.s3h select{width:100%;font:13px var(--sans);padding:5px 7px;border:1.5px solid var(--line);border-radius:8px;background:#fff}
.s3r{display:flex;align-items:center;gap:7px;padding:6px 4px;border-bottom:1px dashed #E7E2D4;font-size:13.5px}.s3r svg{width:22px;height:22px}.s3r span{flex:1}.s3r.top{font-weight:700}.s3r.top b{color:var(--pc)}.s3r.x{opacity:.5}
.s3d{margin-top:8px;font-size:12.5px;background:#FDE7D6;border-radius:9px;padding:6px 9px}.s3s{margin-top:8px;font-size:12.5px;color:var(--ink2)}
.s3all{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;font-size:12px;align-items:center}.s3all span{border:1px solid var(--line);border-radius:99px;padding:2px 8px;background:#fff}.s3all span.ch{border-color:#D4572A;color:#A2401C}
.k4a select{width:auto;flex:1;min-width:0}.k4a{flex-wrap:nowrap}

/* v0.9.1 ma trận luân canh — cùng phông, cùng kiểu thẻ/bảng với các trang trước */
#tab9 .scroll{max-height:none;overflow:visible}
table.rotm{width:100%;border-collapse:separate;border-spacing:0;font:14px var(--sans);border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff}
table.rotm th,table.rotm td{border-right:1px solid #EEE9DC;border-bottom:1px solid #EEE9DC}
table.rotm tr>*:last-child{border-right:0}table.rotm tbody tr:last-child>*{border-bottom:0}
table.rotm thead th{background:#FBF9F3;font:700 13px var(--sans);color:var(--ink);padding:10px 8px;text-align:center}
table.rotm .ch2c{display:inline-flex;align-items:center;gap:6px}table.rotm .ch2c svg{width:24px;height:24px}
table.rotm th.corner{text-align:left;font:600 11.5px var(--sans);color:var(--ink2);width:170px}table.rotm th.corner span{display:block}
table.rotm tbody th{background:#FBF9F3;text-align:left;padding:10px 12px;font:700 13.5px var(--sans)}
table.rotm .rc{display:flex;align-items:center;gap:8px}table.rotm .rc svg{width:26px;height:26px;flex:none}table.rotm .rc small{display:block;font:600 11px var(--sans);color:var(--pc)}
table.rotm td{height:58px;text-align:center;font:700 16px var(--sans);color:var(--ink);cursor:pointer;position:relative;transition:filter .15s}
table.rotm td:hover{filter:brightness(.96)}
table.rotm td.sig{box-shadow:inset 0 0 0 2px #2F7A3A}
table.rotm td.nd{background:#F6F4EE;color:var(--ink2);font:500 12.5px var(--sans)}
table.rotm td.dg{background:repeating-linear-gradient(135deg,#F3F1EA 0 6px,#ECE9E0 6px 12px);color:#A8A08C;cursor:default}
table.rotm td.k4{box-shadow:inset 0 0 0 2.5px #C4292A}table.rotm td em{position:absolute;top:4px;right:6px;font:700 10px var(--sans);color:#C4292A;font-style:normal}
table.rotm tr.me th{background:color-mix(in srgb,var(--pc) 14%,#fff)}table.rotm tr.me td:not(.dg){box-shadow:inset 0 3px 0 var(--pc),inset 0 -3px 0 var(--pc)}
.rotleg{gap:16px;font-size:12.5px}
.rothow p{font-size:14px}
/* kết quả chuỗi: dùng phông sans như các bảng khác */
.chn .rk{font:700 16px var(--sans)}.chn .sc b{font:700 20px var(--sans)}
/* bảng kinh tế: các dòng kẻ thẳng hàng */
.etab{border-collapse:collapse;table-layout:fixed}.etab th,.etab td{border-bottom:1px solid #EEE9DC;vertical-align:middle;height:46px;padding:4px 10px}
.etab td:first-child{display:table-cell}.etab td:first-child svg{vertical-align:-6px;margin-right:6px}
.etab th:first-child{width:24%}.etab th:last-child{width:20%}
/* 13 tiêu chí trên một hàng */
.dq-dots{grid-template-columns:repeat(13,1fr);gap:2px}.dq-dots i{font-size:7.5px;border-radius:4px;letter-spacing:-.02em}
table.rotm td,table.rotm th{vertical-align:middle}
/* v0.9.2 bảng điểm & ma trận luân canh: cùng một kiểu ô bo góc, đều nhau */
.mx{gap:5px;background:#FBF9F3;border:1px solid var(--line);border-radius:18px;padding:12px}
.mx .gh{border-radius:8px;padding:4px 0;font-size:10px;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mx .h{height:64px;justify-content:flex-end;gap:1px;padding:0 2px}
.mx .h small{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.2;max-width:100%}
.mx .h small:last-child{display:block;font-weight:700;color:var(--pc)}
.mx .c{min-height:46px;border-radius:11px;font-size:13.5px;border:0;box-shadow:inset 0 0 0 1px rgba(0,0,0,.04);position:relative}
.mx .c:hover{transform:translateY(-1px);box-shadow:0 4px 10px -4px rgba(0,0,0,.25)}
.mx .c.sel{box-shadow:inset 0 0 0 2.5px #17251D}
.mx .t{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:2px 10px;min-height:46px;border-radius:11px;padding:6px 12px}
.mx .t small.vm{grid-column:1/-1;margin:0}
.mx .rn{background:#fff;border:1px solid #EEE9DC;border-radius:11px;padding:0 10px;min-height:46px}
.mx .rn svg{width:26px;height:26px}
/* ma trận luân canh dạng lưới */
.mx.rotg{grid-template-columns:minmax(150px,190px) repeat(4,minmax(96px,1fr));gap:6px}
.rotg .corner{display:flex;flex-direction:column;justify-content:flex-end;font:600 11.5px var(--sans);color:var(--ink2);padding:0 6px 6px}
.rotg .h.rh{height:auto;flex-direction:row;justify-content:center;gap:6px;background:#fff;border:1px solid #EEE9DC;border-radius:11px;padding:10px 6px;font:700 13px var(--sans);color:var(--ink)}
.rotg .h.rh svg{width:24px;height:24px}
.rotg .c{min-height:58px;font:700 16px var(--sans);color:var(--ink)}
.rotg .c.nd{background:#F3F1EA;color:var(--ink2);font:500 12px var(--sans)}
.rotg .c.na{font-size:16px}
.rotg .c.sig{box-shadow:inset 0 0 0 2px #2F7A3A}.rotg .c .st{position:absolute;top:5px;left:8px;font-size:9px;font-style:normal;color:#2F7A3A}
.rotg .c.k4{box-shadow:inset 0 0 0 2.5px #C4292A}.rotg .c em{position:absolute;top:4px;right:7px;font:700 10px var(--sans);color:#C4292A;font-style:normal}
.rotg .rn.me{background:color-mix(in srgb,var(--pc) 12%,#fff);border-color:var(--pc)}.rotg .rn small{color:var(--pc)}
.rotg .c.me{outline:2px solid var(--pc);outline-offset:1px}
.rotleg i.nd{background:#F3F1EA;border:1px solid var(--line)}
/* chữ không tràn khỏi thẻ nguồn */
.srcc .kv>*,.kv>*{min-width:0;overflow-wrap:anywhere}
/* kịch bản theo chuỗi */
.cseq{display:flex;flex-wrap:wrap;align-items:center;gap:4px}.cseq .cq{display:inline-flex;align-items:center;gap:4px;border:1px solid #EEE9DC;border-radius:99px;padding:2px 8px 2px 4px;background:#FBFAF6;font-size:12.5px;font-weight:600}
.cseq .cq svg{width:18px;height:18px}.cseq .cq small{font-size:10.5px;color:var(--ink2);font-weight:500}.cseq .cq.f{background:#F1EFE7;border-style:dashed}.cseq i{font-style:normal;color:var(--ink2)}
.s3q{display:flex;align-items:center;gap:6px;flex:1;min-width:0}.s3q em{font-style:normal;font-weight:700;color:var(--pc);font-size:12px}.s3q small{display:block;font-size:11px;color:var(--ink2);font-weight:500}
.sclab svg{width:22px;height:22px}
.mx .gh{white-space:normal;line-height:1.15;display:flex;align-items:center;justify-content:center;min-height:22px;text-overflow:clip}
.srcc .kv,.kv{grid-template-columns:86px minmax(0,1fr);overflow-wrap:anywhere;word-break:break-word}.srcc{min-width:0}
/* bảng so sánh kịch bản: nền ô đều, không vỡ màu */
.cmpt td{vertical-align:middle;background:#FBFAF6}.cmpt td:not(:nth-child(2)){white-space:nowrap}
.cmpt tr:nth-child(even) td{background:#F6F3EA}
.cmpt td .cseq{display:flex;flex-wrap:wrap;align-items:center;gap:4px}
.cmpt .up,.cmpt .dn{font-weight:700}
.foot .authors{display:flex;flex-direction:column;gap:5px;margin-top:8px;padding:10px 12px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.6);font-size:12px}
.foot .authors b{font:700 10.5px var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--ink2)}
.foot .authors span{display:flex;flex-direction:column;font-weight:700;color:var(--ink)}.foot .authors a{font-weight:500;color:var(--accent);font-size:11.5px;text-decoration:none;overflow-wrap:anywhere}
.foot .authors .ah{font:700 10.5px var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--ink2)}
.foot .authors .au>span{display:flex;flex-direction:column}
.authg{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.authg .au{display:flex;align-items:center;gap:12px;border:1px solid var(--line);border-radius:16px;padding:12px 14px;background:#FBF9F3}
.authg .au i{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;background:var(--pc);color:#fff;font:700 18px var(--sans);font-style:normal;flex:none}
.authg .au span{display:flex;flex-direction:column;min-width:0}.authg .au b{font-size:15px}.authg .au a{color:var(--accent);font-size:13px;overflow-wrap:anywhere}.authg small{color:var(--ink2)}
@media(max-width:800px){.authg{grid-template-columns:1fr}}
/* v0.9.3: nút chuyển ngôn ngữ VI / EN */
#langSw{position:fixed;top:12px;right:16px;z-index:3000;display:flex;background:#fff;border:1px solid var(--line);border-radius:999px;padding:3px;box-shadow:0 4px 14px -6px rgba(20,40,30,.35)}
#langSw button{border:0;background:none;font:700 12px var(--sans);letter-spacing:.06em;color:var(--ink2);padding:5px 11px;border-radius:999px;cursor:pointer}
body.landing #langSw{top:auto;bottom:18px;left:18px;right:auto}
#matrix .h small{hyphens:auto;-webkit-hyphens:auto;overflow-wrap:break-word}#matrix .gh{letter-spacing:0;font-size:9.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#langSw button.on{background:var(--ink,#17251D);color:#fff}#langSw button:not(.on):hover{background:rgba(23,37,29,.07)}
/* v0.9.4: bảng điểm từng bước của chuỗi tốt nhất; ma trận luân canh chỉ để xem */
#rotTable .c{cursor:default}#rotTable .c:hover{transform:none}
.chsteps{display:flex;flex-direction:column;gap:18px}
.chsum{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;align-items:center;padding:10px 14px;border-radius:12px;background:color-mix(in srgb,var(--pc) 10%,#fff);border:1px solid color-mix(in srgb,var(--pc) 35%,#fff);font:600 14px var(--sans)}
.chsum b{font-size:16px;color:var(--pc)}
.chstep{border:1px solid var(--line);border-radius:16px;padding:14px;background:#fff}
.chsh{display:flex;gap:12px;align-items:center;margin-bottom:6px}.chsh .no{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--pc);color:#fff;font:700 14px var(--sans);flex:none}
.chsh h4{margin:0;font:700 16px var(--sans)}.chsh small{color:var(--ink2);font-size:12.5px}
.chwhy{margin:4px 0 10px;font-size:13.5px;line-height:1.55;color:var(--ink)}
.chstep .mx .rn.pick{background:color-mix(in srgb,var(--pc) 13%,#fff);border-radius:10px;outline:2px solid var(--pc);outline-offset:-2px;padding-left:6px}
.chstep .mx .rn .ok{font:700 11px var(--sans);border-radius:99px;padding:1px 7px;background:var(--pc);color:#fff;white-space:nowrap}
.chstep .mx .rn.x{opacity:.6}.chstep .mx .t.pick{border-color:var(--pc);box-shadow:0 0 0 2px color-mix(in srgb,var(--pc) 35%,transparent)}
.chstep .mx .t{flex-direction:column;align-items:stretch;justify-content:center;gap:2px;padding:6px 10px}.chstep .mx .t .tb{display:flex;align-items:center;gap:8px}
.chstep .mx .t small.bp{font:700 11.5px var(--sans);color:var(--ink)}.chstep .mx .t.x{opacity:.55}.chstep .mx .t small.vm{margin:0}
.chstep .mx .fal.x{opacity:.65}.chstep .mx .fal.pick{border-color:var(--pc);border-style:solid;background:color-mix(in srgb,var(--pc) 8%,#fff);color:var(--ink)}
/* v0.9.2: ẩn thẻ "So sánh 3 cột: Baseline · Δ+ · Δ−" (trùng chức năng với so sánh kịch bản kéo thanh) và cho phần kịch bản to ra */
#scen3,#scen3+.card:has(#s3res){display:none!important}
.homelow .hscen{flex:1 1 auto;min-height:calc(100vh - 250px);padding:20px 22px}
#homeScen .scw{grid-template-columns:minmax(0,1.15fr) minmax(440px,1fr);gap:16px 24px}
#homeScen .scene-w{min-height:clamp(320px,46vh,560px)}
#homeScen .scd{gap:14px 22px}#homeScen .dial label{font-size:14.5px}
#homeScen [id$="Cmp"]{padding:16px 18px}
#homeScen .cmpt{font-size:14.5px}#homeScen .cmpt td,#homeScen .cmpt th{padding:9px 8px}
@media(max-width:1150px){#homeScen .scw{grid-template-columns:1fr}#homeScen .scene-w{min-height:300px}}
/* v0.9.2: chữ phụ ở thanh bên không tràn khung; email tác giả nằm trên 1 dòng */
.nb>span:last-child{flex:1;min-width:0}.nb small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.foot .authors,.foot .authors .au,.foot .authors .au>span{min-width:0;max-width:100%}
.foot .authors a{font-size:10.5px;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;overflow-wrap:normal;display:block}
</style></head>
<body class="app">
<div id="app">
<aside id="side">
 <div class="brand" id="logoHome" title="Về trang chủ"><img src="/logo.png" alt="__APP_NAME__"><b>__APP_NAME__</b><small>__APP_FULL__ · v__VERSION__</small></div>
 <div id="farmBadge" title="Ruộng đang chọn"></div>
 <div class="dq" id="dataQ" title="Tình trạng dữ liệu của 13 tiêu chí — bấm để xem"></div>
 <nav id="nav" aria-label="Các bước"></nav>
 <div class="foot"><span class="chip" id="chipDemo" hidden>Khí hậu: DEMO</span><div class="authors" id="authSide"></div></div>
</aside>
<div id="stage" data-p="1">
 <div id="banner" role="banner"><div class="art" id="banArt"></div><div class="tx"><div class="st" id="banSt"></div><h1 id="banT"></h1><p id="banD"></p></div></div>
 <main id="pages">

<!-- 0 · TRANG CHỦ: bản đồ giám sát toàn màn hình + so sánh kịch bản -->
<section class="page on" id="tab0">
 <div class="hero">
  <div class="mapbox" id="monMapBox"><div id="monMap"></div></div>
  <div class="hcard" id="hCard">
   <div class="hcb"><img src="/logo.png" alt=""><div><b>__APP_NAME__</b><small>NASA Space Apps 2026 · Nguyễn Mai Chi & Nguyễn Mạnh Đạt</small></div></div>
   <div class="hban" data-p="2"><div class="art" id="hArt"></div><div class="tx"><div class="st">Trang chủ · Giám sát thời tiết</div><h1>Thời tiết trên thửa của bạn hôm nay thế nào?</h1><p>Bản đồ dữ liệu NASA POWER theo tháng, cảnh báo sớm cho riêng thửa ruộng và gợi ý cây hợp cho vụ tới.</p></div></div>
   <div class="hfarm" id="hFarm"></div>
   <div class="hacts"><button class="b big" id="bStart">Bắt đầu dùng công cụ →</button><button class="b ghost" id="bDown" title="So sánh kịch bản cho vụ tới">Kịch bản ↓</button></div>
  </div>
  <div class="mlayers" id="monLayers"></div>
  <div class="hpanel" id="hPanel">
   <div class="hph"><span class="hdot" id="hDot"></span><b id="hTitle">Cảnh báo thời tiết</b><span class="spin" id="spMon">Đang lấy…</span><span style="flex:1"></span><button class="ib" id="bMonCfg" title="Cấu hình cảnh báo">⚙</button><button class="ib" id="bHpMin" title="Thu gọn">–</button></div>
   <div class="hpb">
    <div id="homeNoFarm" style="display:none"><p>Chọn vị trí ruộng để nhận cảnh báo nhiệt độ, mưa, bức xạ và độ ẩm cho riêng thửa của bạn.</p><div class="row" style="gap:8px"><button class="b sm" data-go="1">Chọn ruộng của tôi</button><button class="b ghost sm" id="bHomeDemo">Dùng ví dụ Kansas</button></div></div>
    <div id="homeBox">
     <small class="hsub" id="monSub">Dữ liệu NASA POWER tại thửa của bạn</small>
     <div class="malerts" id="monAlerts"></div>
     <details class="hnow"><summary>Chỉ số 4 yếu tố hôm nay</summary><div class="mnow" id="monNow"></div></details>
    </div>
   </div>
  </div>
  <div class="mmsg" id="monMapMsg"></div>
  <div class="mleg" id="monLeg"></div>
  <div class="mtime"><button id="bMonPlay" title="Chạy theo thời gian">▶</button><input type="range" id="monTime" min="0" max="0" value="0" aria-label="Thời gian"><b id="monTimeLbl">—</b></div>
 </div>
 <div class="moncfg" id="monCfg" hidden></div>
 <div class="homelow" id="homeLow" data-p="6">
  <div class="hban lban" data-p="6"><div class="art" id="lArt"></div><div class="tx"><div class="st">Trang chủ · So sánh kịch bản</div><h1>Nếu vụ tới nóng hơn, khô hơn… cây nào còn hợp?</h1><p id="hScenSub">Kéo các thanh A1, A2, A3, B1 để xem cây nào còn hợp nếu thời tiết thay đổi</p></div>
   <div class="hsbtn"><button class="b ghost sm" data-go="5">Cấu hình tiêu chí</button><button class="b sm" data-go="6">Xem chi tiết →</button><button class="b ghost sm" id="bUp">↑ Về bản đồ</button></div></div>
  <div class="card hscen"><div id="homeScen"></div></div>
  <div class="pgsrc" data-src="power,power_img,gpm,smap"></div>
 </div>
</section>

<!-- 1 · RUỘNG -->
<section class="page fit" id="tab1">
 <div class="p1">
  <div class="mapw">
   <div id="map"></div>
   <div class="msearch"><div class="sbar"><input id="q" placeholder="Gõ tên xã, huyện, quận (county) hoặc toạ độ…" autocomplete="off" aria-label="Tìm địa điểm"><button class="go" id="bSearch">Tìm</button><button class="me" id="bGeo" title="Vị trí của tôi" aria-label="Vị trí của tôi"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="7.5"/></svg></button></div><div id="geoList"></div></div>
   <div class="mhint" id="mHint">Bấm lên bản đồ để chọn đúng nơi ruộng của bạn</div>
  </div>
  <div class="rside">
   <div class="card"><div class="ch"><span class="ti" data-wi="pin"></span><div><h3>Ruộng của bạn</h3><small>Đặt tên để lần sau mở lại nhanh</small></div></div>
    <input data-path="farm.name" placeholder="vd: Ruộng nhà ông Ba" aria-label="Tên trang trại">
    <div class="coords"><div><small>Vĩ độ</small><input type="number" step="0.0001" data-path="farm.lat" placeholder="—"></div><div><small>Kinh độ</small><input type="number" step="0.0001" data-path="farm.lon" placeholder="—"></div></div>
    <div class="cta" style="margin-top:12px"><button class="b ghost" id="bSave">Lưu trang trại</button></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="humid"></span><div><h3>Chế độ tưới</h3><small>Đặc điểm của thửa — giống nhau cho mọi cây</small></div></div><div id="irrBox"></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="sparkle"></span><div><h3>Thử nhanh bằng ví dụ</h3><small>Đã điền sẵn vụ và đất (số minh hoạ)</small></div></div>
    <div class="exs"><button class="ex" id="bPreKE"><span class="ic" data-crops="maize,soybean"></span><b>Đông Kansas</b><small>Manhattan · vụ hè, nhờ mưa</small></button><button class="ex" id="bPreKW"><span class="ic" data-crops="wheat,sorghum"></span><b>Tây Kansas</b><small>Garden City · lúa mì đông + vụ hai</small></button></div></div>
   <div class="card farms"><div class="ch"><span class="ti" data-wi="folder"></span><div><h3>Trang trại đã lưu</h3></div></div><div id="farmList" class="fine" style="margin:0">Chưa có.</div></div>
   <button class="b big" id="bNext1">Tiếp tục: khai báo mùa vụ →</button>
  </div>
 </div>
 <div class="pgsrc" data-src="esri,osm,geocode"></div>
</section>

<!-- 2 · MÙA VỤ -->
<section class="page" id="tab2">
 <div class="card pmode"><div class="ch"><span class="ti" data-wi="compass"></span><div style="flex:1"><h3>Bạn muốn công cụ giải bài toán nào?</h3><small>Chọn trước khi khai báo mùa vụ — các bước sau sẽ tự đổi theo bài toán</small></div></div><div class="modes" id="modeBox"></div></div>
 <div id="modeNext">
 <div class="ssp">
  <div class="stack">
   <div class="card"><div class="ch"><span class="ti" data-wi="cal"></span><div style="flex:1"><h3>Khai báo các vụ trong năm của ruộng</h3><small>Mỗi vụ: trồng cây gì, bắt đầu ngày nào (chọn trên lịch — lặp lại hằng năm) và kéo dài bao lâu</small></div><button class="b sm" id="bAddSeason">+ Thêm vụ</button></div>
    <div class="sgrid" id="seasonRows"></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="calck"></span><div><h3>Điều kiện K1: cây nào kịp thời vụ tới?</h3><small id="k1Sub">So ngày bắt đầu vụ tới với cửa sổ gieo và chu kỳ sinh trưởng trong CRD</small></div></div><div class="k1g" id="k1Prev"></div></div>
  </div>
  <div class="stack sticky">
   <div class="card"><div class="ch"><span class="ti" data-wi="clock"></span><div><h3>Đồng hồ mùa vụ</h3><small>Vạch đỏ là hôm nay · vụ viền đậm là vụ cần ra quyết định</small></div></div><div class="clock" id="seasonClock"></div><div class="snow" id="seasonNow"></div><div class="fine" id="moistNow"></div></div>
  </div>
 </div>
 </div>
 <div id="modeChain" style="display:none">
  <div class="card"><div class="ch"><span class="ti" data-wi="hourglass"></span><div style="flex:1"><h3>Khoảng thời gian của chuỗi luân canh</h3><small>Chỉ cần ngày bắt đầu và ngày kết thúc — công cụ tự xếp các cây vừa trong khoảng này theo cửa sổ gieo và thời gian sinh trưởng trong CRD</small></div></div>
   <div class="chform" id="chainForm"></div><div class="chtl" id="chainTl"></div></div>
 </div>
 <div class="card mt" id="econCard"><div class="ch"><span class="ti" data-wi="coin"></span><div style="flex:1"><h3>Thông tin kinh tế (tiêu chí F1)</h3><small>G = giá bán P × diện tích A × năng suất cơ sở Y_base — dùng để chấm F1; để trống thì F1 tự bỏ khỏi điểm</small></div></div><div id="econBox"></div></div>
 <div class="cta"><button class="b ghost" data-go="1">← Quay lại</button><span class="sp"></span><button class="b big" id="bNext2">Tiếp tục: khí hậu nơi bạn →</button></div>
 <div class="pgsrc" data-src="AgM,KSU-1,KSU-2,NASS-KS,FAO-W,FAO-S,FAO-M,FAO-G,power"></div>
</section>

<!-- 3 · KHÍ HẬU -->
<section class="page" id="tab3">
 <div class="statusbar"><span id="climMeta" style="display:contents"></span><span style="flex:1"></span><button class="b ghost sm" id="bClim">↻ Tải lại dữ liệu NASA</button><span class="spin" id="spClim">Đang tải…</span></div>
 <div id="climLoad"></div>
 <div id="climBox" style="display:none">
  <div class="c3">
   <div class="card"><div class="ch"><span class="ti" data-wi="hot"></span><div style="flex:1"><h3>A1 · Nhiệt độ</h3><small>TB tháng nhiều năm · dải: TB thấp nhất – cao nhất ngày · nền xanh: tháng của vụ tới</small></div><div class="kpi1" id="kA1"></div></div><div class="cwrap"><canvas id="cA1"></canvas></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="rain"></span><div style="flex:1"><h3>A2 · Lượng mưa năm</h3><small>Tổng mưa từng năm · vạch: trung bình nhiều năm (giá trị dùng cho A2)</small></div><div class="kpi1" id="kA2"></div></div><div class="cwrap"><canvas id="cA2"></canvas></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="sun"></span><div style="flex:1"><h3>A3 · Bức xạ (chỉ số Kt)</h3><small>Kt TB tháng · vạch ngang: ngưỡng rất sáng 0,60 · trời quang 0,50 · nhiều mây 0,35</small></div><div class="kpi1" id="kA3"></div></div><div class="cwrap"><canvas id="cA3"></canvas></div></div>
  </div>
  <div class="card" id="climRecent"><div class="ch"><span class="ti" data-wi="linechart"></span><div style="flex:1"><h3>Diễn biến gần đây so với nhiều năm</h3><small id="climRecentSub">Năm nay so với trung vị và dải phân vị 10–90 cùng kỳ của chính thửa ruộng</small></div></div>
   <div class="monchart"><div class="ch2"><div class="sg" id="monVar"></div><span style="flex:1"></span><span class="fine" style="margin:0">Thời gian xem:</span><div class="sg" id="monRange"></div></div><div class="cwrap"><canvas id="cMon"></canvas></div></div></div>
  <details class="tech"><summary>Dữ liệu bổ sung: mưa GPM IMERG (A2, B1) và độ ẩm SMAP (B1)</summary><div class="in"><div id="layerBox"></div></div></details>
 </div>
 <div class="cta"><button class="b ghost" data-go="2">← Quay lại</button><span class="sp"></span><button class="b big" id="bNext3">Tiếp tục: đất & địa hình →</button></div>
 <div class="pgsrc" data-src="power,gpm,smap"></div>
</section>

<!-- 4 · ĐẤT & ĐỊA HÌNH -->
<section class="page" id="tab4">
 <div class="card" id="soilData"></div>
 <div class="cta"><button class="b ghost" data-go="3">← Quay lại</button><span class="sp"></span><button class="b big" id="bNext4">Tiếp tục: chọn tiêu chí →</button></div>
 <div class="pgsrc" data-src="ssurgo,soil,slope,power,PAN,FAO-56"></div>
</section>

<!-- 5 · TIÊU CHÍ & TRỌNG SỐ -->
<section class="page" id="tab5">
 <div class="crp">
  <div class="card"><div class="ch"><span class="ti" data-wi="checklist"></span><div><h3>Dùng tiêu chí nào, nặng nhẹ ra sao?</h3><small>Bật/tắt từng tiêu chí và kéo trọng số. Tổng luôn được quy về 100%.</small></div></div>
   <label style="margin-top:0">Bắt đầu từ một bộ ưu tiên (trọng số nhóm theo tài liệu, chia đều cho các tiêu chí trong nhóm)</label><div class="pf" id="profBox"></div>
   <div id="critList"></div></div>
  <div class="stack sticky">
   <div class="card"><div class="ch"><span class="ti" data-wi="scale"></span><div><h3>Tỉ trọng sau khi chuẩn hóa</h3></div></div><div id="wViz"></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="shield"></span><div><h3>Điều kiện bắt buộc</h3><small>Loại phương án trước khi chấm điểm</small></div></div>
    <label class="tog"><input type="checkbox" id="k1On"> <span><b>K1 – Lịch gieo & chu kỳ sinh trưởng</b><br><small class="fine" style="margin:0">Loại cây có cửa sổ gieo không khớp ngày bắt đầu vụ, vụ ngắn hơn chu kỳ tối thiểu, hoặc không chín kịp trước sương giá đầu thu</small></span></label>
    <label>Cho phép lệch so với cửa sổ gieo: <b id="k1TolV">±7 ngày</b></label><input type="range" class="fl" id="k1Tol" min="0" max="30" step="1">
    <label class="tog mt" style="margin-bottom:4px"><span><b>K2 – Cây bạn không muốn trồng</b></span></label><div class="pcrop" id="exCrops"></div>
    <label class="tog mt"><input type="checkbox" id="k3On"> <span><b>K3 – Không trồng một cây 2 vụ liền nhau</b><br><small class="fine" style="margin:0">Ví dụ ngô → ngô, đậu tương → đậu tương. Đất nghỉ không tính là cây và cắt quan hệ liền kề.</small></span></label>
    <label class="tog mt" style="margin-bottom:4px"><span><b>K4 – Không trồng cây A sau cây B</b><br><small class="fine" style="margin:0">Khai báo các cặp cấm (cây trước → cây sau); mặc định trống</small></span></label><div class="k4" id="k4Box"></div></div>
  </div>
 </div>
 <div class="err" id="errRun" style="margin-top:14px"></div>
 <div class="cta"><button class="b ghost" data-go="4">← Quay lại</button><span class="sp"></span><button class="b big" data-go="9">Tiếp tục: ma trận luân canh →</button></div>
 <div class="pgsrc" data-src="baitoan"></div>
</section>

<!-- 6 · MA TRẬN LUÂN CANH (độ phủ cặp cây) -->
<section class="page" id="tab9">
 <div class="rotw">
  <div class="card"><div class="ch"><span class="ti" data-wi="cycle"></span><div style="flex:1"><h3>Độ phủ cặp cây: trồng cây sau, sau cây trước</h3><small id="rotSub">% thay đổi năng suất cây sau so với độc canh — Mudare et al. (2025), Supplementary Table 5</small></div></div>
   <div class="mx rotg" id="rotTable"></div><div class="rotleg" id="rotLeg"></div></div>
  <div class="stack">
   <div class="card"><div class="ch"><span class="ti" data-wi="bulb"></span><div><h3>Ma trận được dùng thế nào?</h3></div></div><div id="rotHow" class="rothow"></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="sprout"></span><div><h3>Với ruộng của bạn</h3></div></div><div id="rotMine" class="rothow"></div></div>
  </div>
 </div>
 <div class="err" id="errRun" style="margin-top:14px"></div>
 <div class="cta"><button class="b ghost" data-go="5">← Quay lại</button><span class="spin" id="spRun">Đang tính điểm…</span><span class="sp"></span><button class="b big" id="bRun">Xem kết quả →</button></div>
 <div class="pgsrc" data-src="MUDARE"></div>
</section>

<!-- 6 · KẾT QUẢ -->
<section class="page" id="tab6">
 <div id="resEmpty" class="empty"><div class="em" data-wi="rainbow"></div><h3>Chưa có kết quả cho vụ tới</h3><p>Công cụ cần biết ruộng ở đâu và các vụ trong năm. Đủ rồi thì bấm nút dưới.</p><button class="b big" id="bRunHere">Tính điểm phù hợp</button><div class="run-t shim" style="font-weight:600">Đang lấy dữ liệu và chấm điểm từng cây…</div></div>
 <div id="resBox" style="display:none">
  <div id="resTop"></div>
  <div class="card mt"><div class="ch"><span class="ti" data-wi="grid"></span><div style="flex:1"><h3>Bảng điểm: cây × tiêu chí (0–1)</h3><small>Bấm vào một ô để xem giá trị, ngưỡng và cách tính</small></div><button class="b ghost sm" id="bReport">🖨 In báo cáo</button><button class="b ghost sm" id="bCsv">Tải CSV</button></div><div class="mx" id="matrix"></div><div class="cinfo" id="cellInfo"></div></div>
  
  <div class="card mt" id="rotRes"></div>
  <div class="two mt"><div class="card"><div class="ch"><span class="ti" data-wi="quote"></span><div style="flex:1"><h3>Vì sao & lưu ý</h3></div><div class="sg" id="whyPick"></div></div><div class="why" id="whyBox"></div></div>
   <div class="card"><div class="ch"><span class="ti" data-wi="medal"></span><div><h3>Độ vững của xếp hạng</h3><small>Cây đứng đầu khi đổi sang từng bộ ưu tiên</small></div></div><div class="rob" id="robBox"></div></div></div>
 </div>
 <div class="cta"><button class="b ghost" data-go="9">← Ma trận luân canh</button><button class="b ghost" data-go="5">Đổi tiêu chí & trọng số</button><span class="sp"></span><button class="b ghost" data-go="0">Về trang giám sát</button></div>
 <div class="pgsrc" data-src="power,gpm,ssurgo,soil,slope,crd,MUDARE"></div>
</section>

<!-- THƯ VIỆN CÂY TRỒNG (CRD) -->
<section class="page" id="tab7">
 <div class="dbg" id="dbCrops"></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="cal"></span><div><h3>Lịch gieo – thu ở Kansas (điều kiện K1)</h3><small>Xanh: cửa sổ gieo · vàng: cửa sổ thu · khung nét đứt: vụ tới của bạn · vạch đỏ: hôm nay</small></div></div><div class="cal" id="dbCal"></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="bars"></span><div style="flex:1"><h3>So sánh khoảng phù hợp giữa các cây</h3><small>Dải đậm: tối ưu · dải nhạt: chịu đựng · vạch đen: số của ruộng bạn (nếu có)</small></div></div><div class="sg" id="dbPick" style="margin-bottom:12px"></div><div class="rng" id="dbRange"></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="book"></span><div><h3>Crop Requirement Database — bảng đầy đủ</h3><small>Dạng tối ưu / chịu đựng. Bấm mã nguồn để xem tài liệu gốc.</small></div></div><div class="scroll"><table class="crd" id="dbTable"></table></div><ul class="fine" id="dbNotes"></ul></div>
 <div class="two mt"><div class="card"><div class="ch"><span class="ti" data-wi="ruler"></span><div><h3>Quy tắc quy đổi về thang 0–1</h3></div></div><div id="dbRules" class="fine" style="margin:0"></div></div>
  <div class="card"><div class="ch"><span class="ti" data-wi="links"></span><div><h3>Nguồn</h3></div></div><ol class="dbsrc" id="dbSrc"></ol></div></div>
 <div class="cta"><span class="sp"></span><button class="b big" id="bDbBack">← Quay lại bước đang làm</button></div>
 <div class="pgsrc" data-src="crd"></div>
</section>

<!-- NGUỒN DỮ LIỆU & CÔNG CỤ AI -->
<section class="page" id="tab8">
 <div id="srcTop"></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="pin"></span><div style="flex:1"><h3>Nhóm tác giả</h3><small>Liên hệ về công cụ FARM ADAPT — NASA Space Apps Challenge 2026</small></div></div><div class="authg" id="authSrc"></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="satellite"></span><div style="flex:1"><h3>Dữ liệu NASA</h3><small>Dữ liệu nào, dùng cho tiêu chí nào, lấy bằng cách nào — và trạng thái với ruộng đang chọn</small></div></div><div class="srcg" id="srcNasa"></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="globe"></span><div><h3>Dữ liệu khác (không phải NASA)</h3><small>Bản đồ đất và mô hình đất bổ sung cho nhóm tiêu chí C</small></div></div><div class="srcg" id="srcOther"></div></div>
 <div class="two mt"><div class="card"><div class="ch"><span class="ti" data-wi="book"></span><div><h3>Cơ sở dữ liệu yêu cầu cây trồng (CRD)</h3><small>Nguồn của từng con số trong Thư viện cây trồng</small></div></div><ol class="dbsrc" id="srcCrd"></ol></div>
  <div class="card"><div class="ch"><span class="ti" data-wi="folder"></span><div><h3>Tài nguyên, thư viện & phương pháp</h3><small>Kể cả mã nguồn mở và hình ảnh</small></div></div><div id="srcRes"></div></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="warn"></span><div><h3>Lưu ý & giả định của công cụ</h3><small>Mọi lưu ý được gom về đây để các trang làm việc gọn hơn</small></div></div><div class="notes" id="srcNotes"></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="chip"></span><div><h3>Công cụ AI</h3><small>Cuộc thi cho phép dùng AI nhưng phải ghi rõ dùng ở đâu và như thế nào</small></div></div>
  <div class="two"><div><h4 class="aih">1. AI bên trong công cụ (khi người dùng chạy)</h4><div id="aiRun"></div></div>
   <div><h4 class="aih">2. AI nhóm đã dùng khi phát triển</h4><div id="aiDev"></div><div class="row" style="margin-top:8px;gap:8px"><button class="b ghost sm" id="bAiAdd">+ Thêm công cụ</button><button class="b sm" id="bAiSave">Lưu khai báo</button></div><p class="fine" id="aiDevNote"></p></div></div></div>
 <div class="card mt"><div class="ch"><span class="ti" data-wi="clipboard"></span><div style="flex:1"><h3>Bản khai để dán vào trang nộp bài</h3><small>Tự sinh từ các mục trên — sao chép hoặc tải về dạng Markdown</small></div><button class="b ghost sm" id="bSrcCopy">Sao chép</button><button class="b sm" id="bSrcMd">Tải .md</button></div><pre class="srcmd" id="srcMd"></pre></div>
 <div class="cta"><span class="sp"></span><button class="b big" id="bSrcBack">← Quay lại bước đang làm</button></div>
</section>

 </main>
</div>
</div>
<div class="toasts" id="toasts" aria-live="polite"></div>

<script>
(function(){
/*
 * transitions.dev / UI generation
 *
 * Plays an "agent is generating this" animation over any element, built from the element's own structure:
 * a dot field ripples out, construction guides and corner handles appear, the outline and every part
 * (boxes, text lines, icon paths) are traced in small flowing dots, then the real UI is revealed behind a
 * scan line with a fade and a smooth ease-out.
 *
 * Variants (variant option)
 *   "ui"              the default: the component's dotted wireframe (outline, boxes, text lines, icons), then the reveal
 *   "text"            big type: every glyph traced along its real outline, then fading in    } handled by
 *   "small-text"      a dotted line through each line of text, the characters fading in      } text-image-generation.js,
 *   "image"           a frame, a tone sketch, a halftone of its pixels, colour dots, the photo } which ships alongside
 *   "auto"            text by size and images, in one block                                  }
 *
 * Modes
 *   "skeleton"        the dotted drawing and the reveal
 *   "skeleton-texts"  the same, plus generation texts: an agent log, the motion CSS being written, a step line
 *
 * Usage
 *   import { generate } from "./ui-generation.js";
 *   const run = generate(el, { mode: "skeleton-texts" });
 *   await run.finished;          // resolves when the real UI is fully in
 *   run.cancel();                // stops and shows the element as it is
 *
 *   <div data-t-generate="skeleton"> ... </div>   + UIGeneration.auto()   (plays when it scrolls into view)
 *
 * No dependencies. Works with any framework: call it after the element has rendered.
 * Respects prefers-reduced-motion (a plain fade instead).
 */

const TIG={timeline(){},generate(){}};

const NS = "http://www.w3.org/2000/svg";
const TEXT_IMAGE = ["text", "small-text", "image", "auto"]; // the variants text-image-generation.js draws
// the text and image variants take the same modes: skeleton → trace, skeleton-texts → trace-texts
const toTrace = (o) => Object.assign({}, o, { mode: /texts$/.test(o.mode || "") ? "trace-texts" : "trace" });
// a scrubbable build of the text and image variants (seek(ms)), for video tools: see 03-text.md
const timeline = (el, options = {}) => TIG.timeline(el, toTrace(Object.assign({ variant: "text" }, options)));

// ─── timing: phases of a build, as fractions of `duration` (the reveal runs a little past 1) ───
const PH = {
  dots: [0, 0.3], probe: [0.02, 0.24], guides: [0.04, 0.3], outline: [0.1, 0.42],
  parts: [0.28, 0.74], reveal: [0.74, 1.055], clean: [0.84, 1.04],
};
const END = 1.09; // the build is over (and the overlay removed) at duration × END

const DEFAULTS = {
  mode: "skeleton",          // "skeleton" | "skeleton-texts"
  duration: 2400,            // ms for the drawing; the whole run is about duration × 1.09
  delay: 0,                  // ms before it starts
  steps: ["Planning layout", "Drawing structure", "Writing styles", "Adding motion"],
  done: "Ready",             // last step, shown when the UI is in (skeleton-texts)
  code: null,                // lines for the motion CSS panel; null = derived from the element
  title: null,               // name used in the generated CSS header; null = from aria-label / heading
  maxParts: 60,              // most parts traced (largest first when there are more)
  keys: 5,                   // key elements that get guides, handles and a size label
  onDone: null,
};

// ─── small math ───
const clamp = (x) => Math.max(0, Math.min(1, x));
const lerp = (a, b, p) => a + (b - a) * p;
const smooth = (a, b, x) => { const q = clamp((x - a) / (b - a)); return q * q * (3 - 2 * q); };
const win = (r, p) => clamp((p - r[0]) / (r[1] - r[0]));
const f2 = (n) => (+n).toFixed(2);
const hashN = (x) => { const v = Math.sin(x * 127.1 + 311.7) * 43758.5453; return v - Math.floor(v); };
function bezier(x1, y1, x2, y2) {
  const cx = (t) => 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3;
  const cy = (t) => 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3;
  return (x) => { if (x <= 0) return 0; if (x >= 1) return 1; let lo = 0, hi = 1, m = 0.5; for (let i = 0; i < 28; i++) { m = (lo + hi) / 2; if (cx(m) < x) lo = m; else hi = m; } return cy(m); };
}
const OUT = bezier(0.16, 1, 0.3, 1);          // drawing: a soft, quick-settling ease-out
const SMOOTH_OUT = bezier(0.22, 1, 0.36, 1);  // reveal: --ease-smooth-out

function svg(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function rrPath(x, y, w, h, r) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  return `M${f2(x + r)} ${f2(y)}H${f2(x + w - r)}A${f2(r)} ${f2(r)} 0 0 1 ${f2(x + w)} ${f2(y + r)}V${f2(y + h - r)}A${f2(r)} ${f2(r)} 0 0 1 ${f2(x + w - r)} ${f2(y + h)}H${f2(x + r)}A${f2(r)} ${f2(r)} 0 0 1 ${f2(x)} ${f2(y + h - r)}V${f2(y + r)}A${f2(r)} ${f2(r)} 0 0 1 ${f2(x + r)} ${f2(y)}Z`;
}
// half an outline, from top centre to bottom centre, clockwise (dir 1) or counter-clockwise (dir 0)
function rrHalf(x, y, w, h, r, dir) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  const X = (v) => f2(x + v), Y = (v) => f2(y + v), R = f2(r);
  return dir
    ? `M${X(w / 2)} ${Y(0)}H${X(w - r)}A${R} ${R} 0 0 1 ${X(w)} ${Y(r)}V${Y(h - r)}A${R} ${R} 0 0 1 ${X(w - r)} ${Y(h)}H${X(w / 2)}`
    : `M${X(w / 2)} ${Y(0)}H${X(r)}A${R} ${R} 0 0 0 ${X(0)} ${Y(r)}V${Y(h - r)}A${R} ${R} 0 0 0 ${X(r)} ${Y(h)}H${X(w / 2)}`;
}
const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// ─── 1. read the element: boxes, text lines, icon geometry, key elements ───
function measure(el, opts) {
  const R = el.getBoundingClientRect(), area = R.width * R.height, parts = [];
  const rel = (r) => ({ x: r.left - R.left, y: r.top - R.top, w: r.width, h: r.height });
  const alpha = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return c && c !== "transparent" ? 1 : 0; const p = m[1].split(/[ ,/]+/).filter(Boolean); return p.length > 3 ? +p[3] : 1; };
  // (el itself is hidden while it builds, so the walk stops at it)
  const hidden = (n) => { for (let x = n; x && x !== el; x = x.parentElement) { const cs = getComputedStyle(x); if (cs.display === "none" || cs.visibility === "hidden" || +cs.opacity < 0.05) return true; } return false; };
  // the card's radius: its own, or that of a child that fills it
  let radius = parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0;
  const walk = (node) => {
    for (const c of node.children) {
      if (c.matches("script, style, template, [data-t-generate-skip]") || hidden(c)) continue;
      const r = c.getBoundingClientRect(), cs = getComputedStyle(c);
      if (!r.width || !r.height) { walk(c); continue; }
      if (Math.abs(r.width - R.width) < 2 && Math.abs(r.height - R.height) < 2) radius = Math.max(radius, parseFloat(cs.borderTopLeftRadius) || 0);
      if (c instanceof SVGSVGElement) {
        if (r.width <= 120 && r.height <= 120) {
          const paths = [];
          for (const g of c.querySelectorAll("path, circle, ellipse, rect, line, polyline, polygon")) {
            if (g.closest("defs, clipPath, mask, symbol") || hidden(g)) continue;
            const m = g.getScreenCTM(); if (!m) continue;
            const attrs = {}; for (const a of ["d", "cx", "cy", "r", "rx", "ry", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "points"]) if (g.hasAttribute(a)) attrs[a] = g.getAttribute(a);
            paths.push({ tag: g.tagName.toLowerCase(), attrs, m: [m.a, m.b, m.c, m.d, m.e - R.left, m.f - R.top] });
          }
          if (paths.length) parts.push({ kind: "icon", ...rel(r), paths, name: "svg" });
        }
        continue;
      }
      const big = r.width * r.height > area * 0.6, blurred = /blur/.test(cs.filter);
      const boxy = !big && !blurred && (alpha(cs.backgroundColor) > 0.02 || parseFloat(cs.borderTopWidth) > 0 || /^(IMG|CANVAS|VIDEO|INPUT|BUTTON|TEXTAREA|SELECT)$/.test(c.tagName) || cs.backgroundImage !== "none");
      if (boxy) {
        const interactive = /^(BUTTON|INPUT|A|SELECT|TEXTAREA)$/.test(c.tagName) || /button|tab|switch|checkbox|slider/.test(c.getAttribute("role") || "");
        const name = c.tagName === "INPUT" || c.tagName === "TEXTAREA" ? "input" : c.tagName === "BUTTON" || c.getAttribute("role") === "button" ? "button" : /^(IMG|CANVAS|VIDEO)$/.test(c.tagName) ? "image" : "frame";
        parts.push({ kind: "box", ...rel(r), r: Math.min(parseFloat(cs.borderTopLeftRadius) || 0, r.width / 2, r.height / 2), interactive, name, el: c });
      }
      for (const n of c.childNodes) {
        if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
        const rg = document.createRange(); rg.selectNodeContents(n); const lines = [];
        for (const q of rg.getClientRects()) {
          const last = lines[lines.length - 1], y = q.top - R.top;
          if (last && Math.abs(last.y - y) < 2) last.x2 = Math.max(last.x2, q.right - R.left); else lines.push({ x: q.left - R.left, x2: q.right - R.left, y, h: q.height });
        }
        if (lines.length) parts.push({ kind: "text", lines, x: Math.min(...lines.map((l) => l.x)), y: lines[0].y, w: Math.max(...lines.map((l) => l.x2 - l.x)), h: lines.reduce((a, l) => a + l.h, 0), name: "text", el: c });
      }
      walk(c);
    }
  };
  walk(el);
  // the same box twice (a button and the span that fills it) is drawn once
  for (let i = parts.length - 1; i > 0; i--) {
    const p = parts[i]; if (p.kind !== "box") continue;
    if (parts.some((q, j) => j < i && q.kind === "box" && Math.abs(q.x - p.x) < 1.5 && Math.abs(q.y - p.y) < 1.5 && Math.abs(q.w - p.w) < 1.5 && Math.abs(q.h - p.h) < 1.5)) parts.splice(i, 1);
  }
  // too many parts: keep the largest, in document order
  if (parts.length > opts.maxParts) {
    const keep = new Set([...parts].sort((a, b) => b.w * b.h - a.w * a.h).slice(0, opts.maxParts));
    for (let i = parts.length - 1; i >= 0; i--) if (!keep.has(parts[i])) parts.splice(i, 1);
  }
  // key elements: interactive boxes first, then the largest boxes
  const boxes = parts.filter((p) => p.kind === "box");
  [...boxes.filter((b) => b.interactive), ...boxes.filter((b) => !b.interactive).sort((a, b) => b.w * b.h - a.w * a.h)].slice(0, opts.keys).forEach((k) => (k.key = true));
  return { w: R.width, h: R.height, r: Math.min(radius, R.width / 2, R.height / 2), parts };
}

// ─── 2. the motion CSS the texts panel streams: the element's own values on the transitions.dev token scale ───
function deriveCode(el, M, title) {
  const hex = (c) => { const m = String(c).match(/[\d.]+/g); if (!m || (m[3] !== undefined && +m[3] === 0)) return null; return "#" + m.slice(0, 3).map((v) => Math.round(+v).toString(16).padStart(2, "0")).join(""); };
  const name = (title || el.getAttribute("aria-label") || (el.querySelector("h1,h2,h3,h4,strong,b") || {}).textContent || "component").trim().toLowerCase().slice(0, 32);
  const MOTION = { button: "transition: scale var(--duration-quick) var(--ease-smooth-out);", input: "transition: box-shadow var(--duration-fast) var(--ease-smooth-out);",
    text: "animation: rise-in var(--duration-fast) var(--ease-smooth-out);", image: "transition: opacity var(--duration-slow) var(--ease-in-out);", frame: "transition: opacity var(--duration-fast) var(--ease-smooth-out);" };
  const code = [`/* ${name} / motion */`, ":root {", "  --duration-quick: 150ms;", "  --duration-fast: 250ms;", "  --duration-slow: 400ms;", "  --ease-smooth-out: cubic-bezier(.22, 1, .36, 1);", "  --ease-in-out: ease-in-out;", "}"];
  M.parts.filter((p) => p.el && p.kind !== "icon").slice(0, 12).forEach((p, i) => {
    const cs = getComputedStyle(p.el), r = parseFloat(cs.borderTopLeftRadius) || 0;
    code.push(`.${p.name}-${String(i + 1).padStart(2, "0")} {`);
    if (p.kind === "box" && r) code.push(`  border-radius: ${r > 400 ? 999 : Math.round(r)}px;`);
    if (p.kind === "text") { code.push(`  font: ${parseFloat(cs.fontSize)}px/${Math.round(parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.4)}px;`); const c = hex(cs.color); if (c) code.push(`  color: ${c};`); }
    const bg = p.kind === "box" && hex(cs.backgroundColor); if (bg) code.push(`  background: ${bg};`);
    code.push(`  ${MOTION[p.name] || MOTION.frame}`, "}");
  });
  return code;
}

// ─── 3. build the overlay ───
function buildOverlay(el, M, opts) {
  const R = el.getBoundingClientRect(), w = M.w, h = M.h, MG = 44, SP = 15, DOT_GAP = 4.8, GUIDE_GAP = 6.5;
  const layer = document.createElement("div");
  layer.className = "t-gen" + (opts.mode === "skeleton-texts" ? " t-gen--texts" : "");
  layer.setAttribute("aria-hidden", "true"); // decoration only: assistive tech reads the real element
  Object.assign(layer.style, { left: f2(R.left + scrollX) + "px", top: f2(R.top + scrollY) + "px", width: f2(w) + "px", height: f2(h) + "px" });
  const root = svg("svg", { class: "t-gen-svg", width: f2(w), height: f2(h), viewBox: `0 0 ${f2(w)} ${f2(h)}` }, layer);
  document.body.appendChild(layer); el.__tGenLayer = layer; // in the page first: SVG geometry can only be measured once it renders
  const G = { el, layer, root, w, h, M: MG, n: (buildOverlay.n = (buildOverlay.n || 0) + 1), parts: [], keys: [] };
  const defs = svg("defs", {}, root);

  // dot field + matrix rain columns
  const dots = svg("g", {}, root); G.dots = []; let maxD = 0;
  for (let x = -Math.floor(MG / SP) * SP; x <= w + MG; x += SP) for (let y = -Math.floor(MG / SP) * SP; y <= h + MG; y += SP) {
    const d = Math.hypot(x - w / 2, y - h / 2), out = Math.max(0, -x, x - w, -y, y - h), col = Math.round(x / SP);
    G.dots.push({ el: svg("circle", { cx: x, cy: y, r: 1.1, class: "t-gen-dot" }, dots), x, y, d, edge: 1 - clamp(out / MG), inside: out === 0,
      v: 0.07 + 0.09 * hashN(col * 7.13 + G.n * 31.7), ph: hashN(col * 3.71 + G.n * 11.3) * 900, tr: 50 + 70 * hashN(col * 1.91 + G.n) });
    maxD = Math.max(maxD, d);
  }
  G.maxD = maxD; G.span = h + 2 * MG;

  const stroke = (d, parent, cls = "t-gen-wire", extra = {}) => { const e = svg("path", Object.assign({ d, class: cls }, extra), parent); return { el: e, L: e.getTotalLength(), gap: cls === "t-gen-guide" ? GUIDE_GAP : DOT_GAP }; };
  const head = (parent, r = 2.4) => svg("circle", { r, class: "t-gen-head", opacity: 0 }, parent);

  // probe, guides, size label
  G.probe = svg("path", { d: `M0 ${-MG}V${f2(h + MG)}`, class: "t-gen-guide t-gen-guide--dashed", opacity: 0 }, root);
  G.guides = [[-MG, 0, w + MG, 0], [w, -MG, w, h + MG], [w + MG, h, -MG, h], [0, h + MG, 0, -MG]].map(([a, b, c, d]) => stroke(`M${f2(a)} ${f2(b)}L${f2(c)} ${f2(d)}`, root, "t-gen-guide"));
  G.dim = svg("text", { x: 0, y: -10, class: "t-gen-label" }, root);

  // wireframe: wiped away behind the scan line
  const clip = svg("clipPath", { id: "t-gen-clip-" + G.n }, defs);
  G.clipRect = svg("rect", { x: -MG - 10, y: -MG, width: w + 2 * MG + 20, height: h + 2 * MG }, clip);
  const glow = svg("linearGradient", { id: "t-gen-glow-" + G.n, x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  svg("stop", { offset: 0, class: "t-gen-glow-stop", "stop-opacity": 0 }, glow); svg("stop", { offset: 1, class: "t-gen-glow-stop", "stop-opacity": 0.12 }, glow);
  const wire = svg("g", { "clip-path": `url(#t-gen-clip-${G.n})`, class: "t-gen-wireframe" }, root); G.wire = wire;
  G.outline = [1, 0].map((dir) => Object.assign(stroke(rrHalf(0, 0, w, h, M.r, dir), wire), { head: head(wire, 2.8) }));

  for (const P of M.parts) {
    const strokes = [];
    if (P.kind === "box" && P.key) [1, 0].forEach((dir) => strokes.push(Object.assign(stroke(rrHalf(P.x, P.y, P.w, P.h, P.r, dir), wire), { together: true })));
    else if (P.kind === "box") strokes.push(stroke(rrPath(P.x, P.y, P.w, P.h, P.r), wire));
    if (P.kind === "text") for (const ln of P.lines) {
      const y = ln.y + ln.h * 0.56, s = stroke(`M${f2(ln.x)} ${f2(y)}H${f2(ln.x2)}`, wire);
      s.caps = [svg("circle", { cx: f2(ln.x), cy: f2(y), r: 1.7, class: "t-gen-head", opacity: 0 }, wire), svg("circle", { cx: f2(ln.x2), cy: f2(y), r: 1.7, class: "t-gen-head", opacity: 0 }, wire)];
      strokes.push(s);
    }
    if (P.kind === "icon") for (const src of P.paths) {
      const [a, b, c, d] = src.m, k = Math.sqrt(Math.abs(a * d - b * c)) || 1;
      const g = svg("g", { transform: `matrix(${src.m.map((v) => (+v).toFixed(3)).join(" ")})`, style: `stroke-width:${(1.8 / k).toFixed(3)}` }, wire);
      const e = svg(src.tag, Object.assign({}, src.attrs, { class: "t-gen-wire" }), g);
      strokes.push({ el: e, L: e.getTotalLength ? e.getTotalLength() : 0, gap: 3.6, k, local: g });
    }
    if (!strokes.length) continue;
    strokes.forEach((s) => (s.head = head(s.local || wire, 2.4 / (s.k || 1))));
    let ix = -1; strokes.forEach((s, i) => (s.idx = s.together && i > 0 && strokes[i - 1].together ? ix : ++ix)); strokes.n = ix + 1;
    G.parts.push({ strokes, b: { x: P.x, y: P.y, w: P.w, h: P.h }, name: P.name, key: !!P.key });
  }
  const N = G.parts.length, span = PH.parts[1] - PH.parts[0], dur = Math.min(0.2, span * 0.6);
  G.parts.forEach((pt, i) => { pt.t0 = PH.parts[0] + (N > 1 ? (span - dur) * (i / (N - 1)) : 0); pt.t1 = pt.t0 + dur; });

  // key elements: their own guides, corner handles and size label
  for (const pt of G.parts) {
    if (!pt.key) continue;
    const { x, y, w: bw, h: bh } = pt.b, E = 16;
    G.keys.push({ pt,
      guides: [[x - E, y, x + bw + E, y], [x + bw, y - E, x + bw, y + bh + E], [x + bw + E, y + bh, x - E, y + bh], [x, y + bh + E, x, y - E]].map(([a, b, c, d]) => stroke(`M${f2(a)} ${f2(b)}L${f2(c)} ${f2(d)}`, root, "t-gen-guide", { opacity: 0 })),
      handles: [[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]].map(([hx, hy]) => ({ el: svg("rect", { x: -2, y: -2, width: 4, height: 4, class: "t-gen-handle", transform: `translate(${f2(hx)} ${f2(hy)}) scale(0)` }, root), x: hx, y: hy })),
      dim: svg("text", { x: f2(x), y: f2(y - 5), class: "t-gen-label t-gen-label--small", opacity: 0 }, root) });
  }

  // particles that land on the outline as it is drawn there
  const inv = (f) => { let lo = 0, hi = 1; for (let i = 0; i < 26; i++) { const m = (lo + hi) / 2; if (OUT(m) < f) lo = m; else hi = m; } return lo; };
  G.flyers = [];
  for (let i = 0; i < 44; i++) {
    const half = G.outline[i % 2], f = 0.06 + 0.9 * (Math.floor(i / 2) / 21), pt = half.el.getPointAtLength(half.L * f);
    const ang = hashN(i * 9.1 + G.n) * Math.PI * 2, dist = 30 + 70 * hashN(i * 4.7 + G.n * 2), arr = PH.outline[0] + (PH.outline[1] - PH.outline[0]) * inv(f);
    G.flyers.push({ el: svg("circle", { r: 1.6, class: "t-gen-flyer", opacity: 0 }, root), x0: pt.x + Math.cos(ang) * dist, y0: pt.y + Math.sin(ang) * dist, x1: pt.x, y1: pt.y, arr, s0: arr - 0.09 });
  }

  // reticle, card handles, coordinate readout, scan line
  G.ret = svg("path", { class: "t-gen-reticle", opacity: 0 }, root); G.tag = svg("text", { class: "t-gen-label t-gen-label--tag", opacity: 0 }, root);
  G.handles = [[0, 0, 0.17], [w, 0, 0.17], [w, h, 0.37], [0, h, 0.37]].map(([x, y, at]) => ({ el: svg("rect", { x: -2.5, y: -2.5, width: 5, height: 5, class: "t-gen-handle", transform: `translate(${f2(x)} ${f2(y)}) scale(0)` }, root), x, y, at }));
  G.read = svg("text", { class: "t-gen-label t-gen-label--small", opacity: 0 }, root);
  G.scan = svg("g", { opacity: 0 }, root);
  svg("rect", { x: 0, y: -28, width: w, height: 28, fill: `url(#t-gen-glow-${G.n})` }, G.scan);
  G.scanLine = svg("path", { d: `M-18 0H${f2(w + 18)}`, class: "t-gen-guide t-gen-guide--scan" }, G.scan);
  svg("circle", { cx: 0, cy: 0, r: 2.3, class: "t-gen-head" }, G.scan); svg("circle", { cx: w, cy: 0, r: 2.3, class: "t-gen-head" }, G.scan);

  // generation texts
  if (opts.mode === "skeleton-texts") buildTexts(G, el, M, opts);
  return G;
}

// does `node` contain `el`, across shadow roots (so web components and shadow-DOM hosts count as containers)?
function holds(node, el) { for (let x = el; x; x = x.parentNode || x.host) if (x === node) return true; return false; }

// is this viewport rect empty page (nothing but the element's own containers)? Overlays never count: they take no input.
function isFree(el, x0, y0, x1, y1) {
  if (x0 < 0 || y0 < 0 || x1 > innerWidth || y1 > innerHeight + 400) return false;
  for (let i = 0; i <= 3; i++) for (let j = 0; j <= 4; j++) {
    const x = lerp(x0, x1, i / 3), y = Math.min(innerHeight - 1, lerp(y0, y1, j / 4)), hit = document.elementFromPoint(x, y);
    if (hit && hit !== document.body && hit !== document.documentElement && !holds(hit, el)) return false;
  }
  return true;
}

function buildTexts(G, el, M, opts) {
  // panels beside the element where that space is empty, else one strip under it, else only the step line
  const r = el.getBoundingClientRect(), PW = Math.min(260, (innerWidth - r.width) / 2 - G.M - 24), gap = G.M + 14;
  const side = PW >= 150 && isFree(el, r.left - gap - PW, r.top, r.left - gap, r.bottom) && isFree(el, r.right + gap, r.top, r.right + gap + PW, r.bottom);
  const below = !side && isFree(el, r.left, r.bottom + 20, r.right, r.bottom + 150);
  G.textMode = side ? "side" : below ? "below" : "steps";
  const hexId = (k) => "0x" + Math.floor(hashN(k * 5.3 + G.n * 17.1) * 65535).toString(16).padStart(4, "0");
  G.logLines = G.parts.map((pt, i) => ({ head: `${hexId(i)}  ${pt.name.padEnd(7, " ")} ${String(Math.round(pt.b.x)).padStart(3, "0")},${String(Math.round(pt.b.y)).padStart(3, "0")}  ${(Math.round(pt.b.w) + "×" + Math.round(pt.b.h)).padEnd(7, " ")}`, t0: pt.t0, t1: pt.t1 }));
  G.code = opts.code || deriveCode(el, M, opts.title); G.codeChars = G.code.reduce((a, l) => a + l.length + 1, 0);
  const mk = (cls) => { const d = document.createElement("div"); d.className = cls; G.layer.appendChild(d); return d; };
  if (side) {
    G.logEl = mk("t-gen-panel t-gen-panel--log"); G.codeEl = mk("t-gen-panel t-gen-panel--code");
    G.logEl.style.right = `calc(100% + ${G.M + 14}px)`; G.codeEl.style.left = `calc(100% + ${G.M + 14}px)`;
    G.logEl.style.maxWidth = G.codeEl.style.maxWidth = PW + "px";
  } else if (below) {
    G.logEl = mk("t-gen-panel t-gen-panel--below");
  }
  G.stepEl = mk("t-gen-steps");
  if (!side && !below && !isFree(el, r.left, r.bottom + 20, r.right, r.bottom + 50)) G.stepEl.style.display = "none"; // no room at all: the drawing speaks for itself
  G.steps = [...opts.steps, opts.done].filter(Boolean);
  G.stepEl.innerHTML = G.steps.map((s) => `<div class="t-gen-step"><i></i><span></span></div>`).join("");
  [...G.stepEl.children].forEach((d, i) => (d.lastChild.textContent = G.steps[i]));
}

// ─── 4. one frame of the build: p = progress (0 → END), t = ms since start ───
const FLOW = 0.016;
function drawStroke(s, q, t) {
  const on = q > 0; s.el.style.opacity = on ? 1 : 0;
  if (on) {
    const gap = s.gap / (s.k || 1), n = Math.floor((s.L * Math.min(1, q)) / gap) + 1;
    if (n !== s.n) { s.n = n; s.el.style.strokeDasharray = `${`0 ${f2(gap)} `.repeat(n - 1)}0 ${f2(s.L + 10)}`; }
    s.el.style.strokeDashoffset = f2(-((t * FLOW) / (s.k || 1)) % gap);
  }
  if (s.head) {
    const live = (s.live = q > 0 && q < 1); s.head.setAttribute("opacity", live ? 1 : 0);
    if (live) { const gap = s.gap / (s.k || 1); s.pt = s.el.getPointAtLength(Math.floor((s.L * q) / gap) * gap); s.head.setAttribute("cx", f2(s.pt.x)); s.head.setAttribute("cy", f2(s.pt.y)); }
  }
  if (s.caps) { s.caps[0].setAttribute("opacity", on ? 1 : 0); s.caps[1].setAttribute("opacity", q >= 1 ? 1 : 0); }
}

function frame(G, p, t, D) {
  const { w, h } = G, clean = 1 - smooth(PH.clean[0], PH.clean[1], p);
  // the real element: wiped in behind the scan line, fading and sharpening on a smooth ease-out
  const sq = SMOOTH_OUT(win(PH.reveal, p)), y = sq * (h + 6) - 3, fq = SMOOTH_OUT(win([PH.reveal[0], PH.reveal[1] + 0.03], p)), es = G.el.style;
  const pad = 80; // keeps the element's own shadow inside the clip
  es.opacity = p < PH.reveal[0] ? 0 : f2(fq);
  // past the bottom edge as the scan finishes, so the shadow below the element comes in with it (no pop when the clip goes)
  const yc = y + smooth(0.6, 1, sq) * pad;
  es.clipPath = p >= PH.reveal[1] ? G.prev.clipPath : `inset(-${pad}px -${pad}px ${f2(h - yc - 1)}px -${pad}px)`;
  es.filter = fq > 0 && fq < 0.99 ? `blur(${f2(3 * (1 - fq))}px)` : G.prev.filter;
  G.clipRect.setAttribute("y", f2(p < PH.reveal[0] ? -999 : y)); G.clipRect.setAttribute("height", f2(h + 999));
  G.wire.setAttribute("opacity", f2(1 - 0.6 * fq));
  G.scan.setAttribute("opacity", f2(p >= PH.reveal[0] && p < PH.reveal[1] ? smooth(0, 0.12, sq) * (1 - smooth(0.85, 1, sq)) : 0));
  G.scan.setAttribute("transform", `translate(0 ${f2(y)})`);
  G.scanLine.style.strokeDashoffset = f2(-(t * FLOW * 2) % 5);

  // dot field: ripple from the centre, matrix rain down the columns, lit by the probe and the reticle
  const R = OUT(win(PH.dots, p)) * (G.maxD + 60), rainOn = smooth(0.04, 0.2, p) * (1 - smooth(0.62, 0.86, p));
  const pw = win(PH.probe, p), probeX = lerp(-G.M, w + G.M, OUT(pw)), probeOp = pw > 0 && pw < 1 ? smooth(0, 0.1, pw) * (1 - smooth(0.85, 1, pw)) : 0;
  G.probe.setAttribute("transform", `translate(${f2(probeX)} 0)`); G.probe.setAttribute("opacity", f2(probeOp * 0.8));
  let rb = null, rOp = 0;
  const at = G.parts.reduce((k, pt, i) => (p >= pt.t0 ? i : k), -1);
  if (at >= 0 && p < PH.reveal[0] + 0.06) {
    const pt = G.parts[at], from = at ? G.parts[at - 1].b : { x: 0, y: 0, w, h }, q = OUT(clamp((p - pt.t0) / 0.05)), P = 5;
    rb = { x: lerp(from.x, pt.b.x, q) - P, y: lerp(from.y, pt.b.y, q) - P, w: lerp(from.w, pt.b.w, q) + 2 * P, h: lerp(from.h, pt.b.h, q) + 2 * P };
    rOp = smooth(PH.parts[0], PH.parts[0] + 0.04, p) * (1 - smooth(PH.reveal[0], PH.reveal[0] + 0.06, p));
    const l = Math.min(7, rb.w / 3, rb.h / 3), { x: X, y: Y, w: RW, h: RH } = rb;
    G.ret.setAttribute("d", `M${f2(X)} ${f2(Y + l)}V${f2(Y)}H${f2(X + l)}M${f2(X + RW - l)} ${f2(Y)}H${f2(X + RW)}V${f2(Y + l)}M${f2(X + RW)} ${f2(Y + RH - l)}V${f2(Y + RH)}H${f2(X + RW - l)}M${f2(X + l)} ${f2(Y + RH)}H${f2(X)}V${f2(Y + RH - l)}`);
    G.tag.setAttribute("x", f2(X)); G.tag.setAttribute("y", f2(Y - 4)); G.tag.textContent = `${pt.name} ${Math.round(pt.b.w)}×${Math.round(pt.b.h)}`;
  }
  G.ret.setAttribute("opacity", f2(rOp)); G.tag.setAttribute("opacity", f2(rOp));
  for (const d of G.dots) {
    const lag = R - d.d, env = clamp(lag / 50), front = p < PH.dots[1] + 0.05 ? Math.exp(-(((lag - 6) / 14) ** 2)) : 0;
    const headY = ((t * d.v + d.ph) % (G.span + d.tr)) - G.M, back = headY - d.y;
    const rain = back >= 0 && back < d.tr ? (1 - back / d.tr) ** 1.6 * rainOn * env * d.edge : 0;
    const near = rb ? Math.max(0, 1 - Math.max(rb.x - d.x, d.x - rb.x - rb.w, rb.y - d.y, d.y - rb.y - rb.h, 0) / 16) * (d.x > rb.x && d.x < rb.x + rb.w && d.y > rb.y && d.y < rb.y + rb.h ? 1 : 0.6) : 0;
    const probe = probeOp > 0 ? Math.exp(-(((d.x - probeX) / 9) ** 2)) * probeOp * env : 0;
    const lit = Math.max(front, rain, near * rOp * 0.8, probe), under = d.inside && p >= PH.reveal[0] && d.y < y ? 0 : 1; // gone where the real UI is in
    d.el.setAttribute("opacity", f2(Math.max(env * 0.5 * d.edge, lit * d.edge) * clean * under));
    d.el.setAttribute("r", f2(1.05 + lit * 0.85));
    d.el.classList.toggle("is-lit", lit > 0.35);
  }

  // guides, size label, outline, card handles, particles
  const gOp = 0.5 * (1 - smooth(0.66, 0.92, p));
  G.guides.forEach((g, i) => { const q = OUT(clamp((p - PH.guides[0] - i * 0.03) / (PH.guides[1] - PH.guides[0] - 0.09))); drawStroke(g, q, t); g.el.style.opacity = q > 0 ? gOp : 0; });
  const oq = OUT(win(PH.outline, p));
  G.dim.textContent = `${Math.round(w * oq)} × ${Math.round(h * oq)}   t+${(Math.min(p, 1) * D / 1000).toFixed(2)}s`;
  G.dim.setAttribute("opacity", f2(p > PH.outline[0] ? (1 - smooth(0.66, 0.9, p)) * 0.9 : 0));
  G.outline.forEach((s) => drawStroke(s, oq, t));
  G.handles.forEach((hd) => hd.el.setAttribute("transform", `translate(${f2(hd.x)} ${f2(hd.y)}) scale(${f2(OUT(clamp((p - hd.at) / 0.1)) * (1 - smooth(0.82, 0.96, p)))})`));
  for (const q of G.flyers) {
    const k = clamp((p - q.s0) / (q.arr - q.s0)), on = p >= q.s0 && p < q.arr + 0.01;
    q.el.setAttribute("opacity", on ? f2(smooth(0, 0.25, k)) : 0);
    if (on) { const e = OUT(k); q.el.setAttribute("cx", f2(lerp(q.x0, q.x1, e))); q.el.setAttribute("cy", f2(lerp(q.y0, q.y1, e))); }
  }
  // every part traced in order, icons stroke by stroke; key elements get guides, handles and a size label
  for (const pt of G.parts) { const q = clamp((p - pt.t0) / (pt.t1 - pt.t0)); pt.strokes.forEach((s) => drawStroke(s, OUT(clamp(q * pt.strokes.n - s.idx * 0.75)), t)); }
  const kOut = 1 - smooth(PH.reveal[0] - 0.02, PH.reveal[0] + 0.1, p);
  for (const K of G.keys) {
    const t0 = K.pt.t0 - 0.03, hq = OUT(clamp((p - K.pt.t0 - 0.04) / 0.08)), oq2 = OUT(clamp((p - K.pt.t0) / (K.pt.t1 - K.pt.t0)));
    K.guides.forEach((g, i) => { const q = OUT(clamp((p - t0 - i * 0.012) / 0.1)); drawStroke(g, q, t); g.el.style.opacity = q > 0 ? f2(0.5 * kOut) : 0; });
    K.handles.forEach((hd) => hd.el.setAttribute("transform", `translate(${f2(hd.x)} ${f2(hd.y)}) scale(${f2(hq * kOut)})`));
    K.dim.setAttribute("opacity", f2(p > t0 ? 0.9 * kOut : 0)); K.dim.textContent = `${Math.round(K.pt.b.w * oq2)} × ${Math.round(K.pt.b.h * oq2)}`;
  }
  // coordinate readout on the line being drawn
  let cur = null; for (const s of [...G.outline, ...G.parts.flatMap((pt) => pt.strokes)]) if (s.live && !s.local) cur = s;
  G.read.setAttribute("opacity", cur ? 1 : 0);
  if (cur) { G.read.setAttribute("x", f2(cur.pt.x + 6)); G.read.setAttribute("y", f2(cur.pt.y - 5)); G.read.textContent = `${String(Math.round(cur.pt.x)).padStart(3, "0")}·${String(Math.round(cur.pt.y)).padStart(3, "0")}`; }

  if (G.logLines) texts(G, p, t, D);
}

function texts(G, p, t, D) {
  const vis = smooth(0.03, 0.1, p) * (1 - smooth(0.9, 1.04, p)), blink = Math.floor(t / 260) % 2;
  // agent log: one line per part with its own progress bar
  const rows = G.textMode === "side" ? Math.max(6, Math.floor(G.h / 11)) : 6, shown = G.logLines.filter((l) => p >= l.t0);
  const done = G.logLines.filter((l) => p >= l.t1).length;
  const logRows = shown.slice(-rows).map((l) => {
    const k = clamp((p - l.t0) / 0.035), prog = clamp((p - l.t0) / (l.t1 - l.t0)), full = l.head + (prog >= 1 ? "[  ok  ]" : `[${"#".repeat(Math.round(prog * 6)).padEnd(6, ".")}]`);
    return full.slice(full.length - Math.ceil(full.length * k));
  });
  const head = `AGENT.LOG // PARTS ${String(done).padStart(2, "0")}/${String(G.logLines.length).padStart(2, "0")}`;
  if (G.logEl) G.logEl.style.opacity = f2(vis);
  // motion CSS: streams at a steady rate through the drawing
  const sk = clamp((p - 0.12) / 0.72), typed = Math.floor(G.codeChars * sk); let left = typed; const lines = [];
  for (const ln of G.code) { if (left <= 0) break; lines.push(ln.slice(0, left)); left -= ln.length + 1; }
  const tok = Math.round(typed / 3.4), secs = Math.max(0.1, (Math.min(p, 1) - 0.12) * D / 1000), caret = sk > 0 && sk < 1 && blink ? "_" : "";
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const codeHtml = lines.slice(-(G.textMode === "side" ? Math.max(8, Math.floor(G.h / 11)) : 4)).map((ln, i, a) => {
    const m = ln.match(/^(\s*)([\w-]+)(:)(.*)$/), c = i === a.length - 1 ? caret : "";
    return m ? `<div>${esc(m[1])}<b>${esc(m[2])}</b>:<em>${esc(m[4])}</em>${c}</div>` : `<div class="${/^\/\*/.test(ln) ? "is-comment" : /^[.:]/.test(ln) ? "is-selector" : ""}">${esc(ln)}${c}</div>`;
  }).join("");
  const foot = sk > 0 ? `${Math.round(tok / secs)} TOK/S · ${lines.length} LN · ${sk < 1 ? "WRITING" : "READY"}` : "";
  const logHtml = `<div class="t-gen-panel-head">${head}</div>` + logRows.map((r) => `<div>${esc(r)}</div>`).join("");
  if (G.codeEl) {
    G.codeEl.style.opacity = f2(vis);
    const sig = typed + "|" + caret; if (G.codeSig !== sig) { G.codeSig = sig; G.codeEl.innerHTML = `<div class="t-gen-panel-head">MOTION.CSS // ${String(tok).padStart(4, "0")} TOKENS</div>${codeHtml}<div class="t-gen-panel-foot">${foot}</div>`; }
    if (G.logSig !== logRows.join("|")) { G.logSig = logRows.join("|"); G.logEl.innerHTML = logHtml; }
  } else if (G.logEl) {
    const sig = logRows.join("|") + typed; if (G.logSig !== sig) { G.logSig = sig; G.logEl.innerHTML = logHtml + `<div class="t-gen-panel-foot">${foot}</div>`; }
  }
  // step line: each step for its share of the drawing, the last once the UI is in
  const n = G.steps.length, gone = smooth(0.98, 1.06, p);
  [...G.stepEl.children].forEach((s, i) => {
    const t0 = i < n - 1 ? (i / (n - 1)) * 0.95 : 0.95, t1 = i < n - 1 ? ((i + 1) / (n - 1)) * 0.95 : Infinity;
    const qi = OUT(clamp((p - t0) / 0.06)), qs = OUT(clamp((p - t1) / 0.05)), q = qi * (1 - Math.max(qs, gone));
    s.style.opacity = f2(q); s.style.transform = `translate(-50%, ${f2(5 * (1 - qi) - 5 * qs)}px)`;
    s.style.filter = q > 0.01 && q < 0.99 ? `blur(${f2(2 * (1 - q))}px)` : "none";
    s.classList.toggle("is-done", i === n - 1);
  });
}

// ─── 5. run ───
function generate(el, options = {}) {
  if (TEXT_IMAGE.includes(options.variant)) return TIG.generate(el, toTrace(options));
  const opts = Object.assign({}, DEFAULTS, options);
  if (typeof el === "string") el = document.querySelector(el);
  if (!el) throw new Error("UIGeneration: no element");
  if (el.__tGen) el.__tGen.cancel();
  const prev = { opacity: el.__tGenOpacity !== undefined ? el.__tGenOpacity : el.style.opacity, clipPath: el.style.clipPath, filter: el.style.filter, transition: el.style.transition };
  const restore = () => Object.assign(el.style, prev);
  let resolve, raf = 0, timer = 0, G = null, stopped = false;
  const finished = new Promise((r) => (resolve = r));
  const finish = () => { if (stopped) return; stopped = true; cancelAnimationFrame(raf); clearTimeout(timer); if (G) G.layer.remove(); restore(); el.__tGen = null; if (opts.onDone) opts.onDone(el); resolve(el); };
  const run = { finished, cancel: finish, element: el };
  el.__tGen = run;

  // reduced motion: no drawing, a plain fade
  if (reduced()) {
    el.style.opacity = 0;
    timer = setTimeout(() => { el.style.transition = "opacity 200ms ease-out"; el.style.opacity = prev.opacity || ""; timer = setTimeout(finish, 220); }, opts.delay);
    return run;
  }
  el.style.opacity = 0; // hidden until its reveal
  timer = setTimeout(() => {
    requestAnimationFrame(() => {
      if (stopped) return;
      try { const M = measure(el, opts); G = buildOverlay(el, M, opts); G.prev = prev; }
      catch (e) { if (el.__tGenLayer) el.__tGenLayer.remove(); G = null; console.warn("UIGeneration: could not build the overlay, showing the element", e); return finish(); }
      const D = Math.max(400, +opts.duration || DEFAULTS.duration), t0 = performance.now();
      const tick = (now) => {
        if (stopped) return;
        const t = now - t0, p = t / D;
        frame(G, p, t, D);
        if (p >= END) return finish();
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    });
  }, opts.delay);
  return run;
}

// Plays every [data-t-generate] element once it scrolls into view.
// data-t-generate="skeleton" | "skeleton-texts", optional data-t-generate-variant (ui | text | small-text | image | auto)
// and data-t-generate-duration / -delay (ms).
function auto(root = document) {
  const els = [...root.querySelectorAll("[data-t-generate]")].filter((e) => !e.__tGenAuto);
  const play = (e) => generate(e, { mode: e.dataset.tGenerate || "skeleton", variant: e.dataset.tGenerateVariant || "ui", duration: +e.dataset.tGenerateDuration || undefined, delay: +e.dataset.tGenerateDelay || 0 });
  els.forEach((e) => { e.__tGenAuto = true; e.__tGenOpacity = e.__tTigOpacity = e.style.opacity; e.style.opacity = 0; }); // hidden until it plays
  if (!("IntersectionObserver" in window)) { els.forEach(play); return; }
  const io = new IntersectionObserver((entries) => entries.forEach((en) => { if (en.isIntersecting) { io.unobserve(en.target); play(en.target); } }), { threshold: 0.35 });
  els.forEach((e) => io.observe(e));
}

if (typeof window !== "undefined") window.UIGeneration = { generate, auto, timeline };

})();
/* ======================================================================
   ART · bộ minh họa vector cho FARM ADAPT (thời tiết, cây trồng, lựa chọn, banner)
   Mọi hàm trả về chuỗi SVG; gradient dùng chung nằm trong ART.defs (gắn 1 lần vào body).
   ====================================================================== */
const ART=(()=>{
const defs=`<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>
<radialGradient id="gSun"><stop offset="0" stop-color="#FFF3B0"/><stop offset="1" stop-color="#F7B02E"/></radialGradient>
<radialGradient id="gGlow"><stop offset="0" stop-color="#FFE48A" stop-opacity=".75"/><stop offset="1" stop-color="#FFE48A" stop-opacity="0"/></radialGradient>
<linearGradient id="gCl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#C6DAEA"/></linearGradient>
<linearGradient id="gClD" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#BAC7D5"/><stop offset="1" stop-color="#7B8CA1"/></linearGradient>
<linearGradient id="gDr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#93DCFF"/><stop offset="1" stop-color="#2D8EDB"/></linearGradient>
<linearGradient id="gBolt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE75E"/><stop offset="1" stop-color="#FFA400"/></linearGradient>
<linearGradient id="gHot" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#D9402B"/><stop offset="1" stop-color="#FF9A52"/></linearGradient>
<linearGradient id="gLf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#A3E077"/><stop offset="1" stop-color="#3F9C4F"/></linearGradient>
<linearGradient id="gLfD" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6DBE5A"/><stop offset="1" stop-color="#287A45"/></linearGradient>
<linearGradient id="gSoil" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#BC8752"/><stop offset="1" stop-color="#7B4E2A"/></linearGradient>
<linearGradient id="gWater" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7CCBF2"/><stop offset="1" stop-color="#2F86CF"/></linearGradient>
<linearGradient id="gSand" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F2DDA8"/><stop offset="1" stop-color="#D5B473"/></linearGradient>
<linearGradient id="gLoam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9C6C44"/><stop offset="1" stop-color="#6A4326"/></linearGradient>
<linearGradient id="gSilt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C6B296"/><stop offset="1" stop-color="#A08B6B"/></linearGradient>
<linearGradient id="gClay" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#BD6A4E"/><stop offset="1" stop-color="#8A432D"/></linearGradient>
</defs></svg>`;
const S=(vb,inner,cls)=>`<svg viewBox="${vb}" ${cls?`class="${cls}" `:""}aria-hidden="true" focusable="false">${inner}</svg>`;
const ray=(cx,cy,r1,r2,n,w,col)=>`<g class="ray" stroke="${col}" stroke-width="${w}" stroke-linecap="round">`+Array.from({length:n},(_,i)=>{const a=i*2*Math.PI/n,c=Math.cos(a),s=Math.sin(a);return `<line x1="${(cx+c*r1).toFixed(1)}" y1="${(cy+s*r1).toFixed(1)}" x2="${(cx+c*r2).toFixed(1)}" y2="${(cy+s*r2).toFixed(1)}"/>`}).join("")+"</g>";
const sunAt=(cx,cy,r)=>`<circle cx="${cx}" cy="${cy}" r="${r*2.3}" fill="url(#gGlow)"/>`+ray(cx,cy,r*1.45,r*1.95,8,Math.max(2,r*.28),"#F2A62B")+`<circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#gSun)" stroke="#E58E16" stroke-width="1.1"/>`;
const cloudP="M47 44H19a9 9 0 0 1-1.2-17.9A13 13 0 0 1 43.2 24.6 10 10 0 0 1 47 44z";
const cloud=(tx,ty,sc,g)=>`<g class="cl"><g transform="translate(${tx} ${ty}) scale(${sc})"><path d="${cloudP}" fill="url(#${g||"gCl"})" stroke="${g==="gClD"?"#6E7F94":"#9DB5C9"}" stroke-width="1.2" stroke-linejoin="round"/><path d="M20 30a8 8 0 0 1 8-6" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="${g==="gClD"?".25":".8"}"/></g></g>`;
const cloudC=(cx,cy,sc,g)=>cloud(cx-30*sc,cy-28*sc,sc,g);
const drop=(x,y,s,g)=>`<g class="dp"><path transform="translate(${x} ${y}) scale(${s||1})" d="M0 -5C3.4 -.6 4.6 1.8 4.6 3.4A4.6 4.6 0 0 1 -4.6 3.4C-4.6 1.8 -3.4 -.6 0 -5z" fill="url(#${g||"gDr"})" stroke="#2A7FC4" stroke-width=".7"/><ellipse transform="translate(${x} ${y}) scale(${s||1})" cx="-1.5" cy="2.2" rx=".9" ry="1.6" fill="#fff" opacity=".6"/></g>`;
const bolt=(x,y,s)=>`<g class="bo"><path transform="translate(${x} ${y}) scale(${s||1})" d="M8 0 0 14h6l-3 12L15 9H8.5z" fill="url(#gBolt)" stroke="#E08A00" stroke-width="1" stroke-linejoin="round"/></g>`;
const flake=(cx,cy,r,col,w)=>`<g stroke="${col}" stroke-width="${w}" stroke-linecap="round" fill="none">`+[0,60,120].map(a=>`<g transform="rotate(${a} ${cx} ${cy})"><line x1="${cx}" y1="${cy-r}" x2="${cx}" y2="${cy+r}"/><path d="M${cx-r*.3} ${cy-r*.72}L${cx} ${cy-r*.42}L${cx+r*.3} ${cy-r*.72}M${cx-r*.3} ${cy+r*.72}L${cx} ${cy+r*.42}L${cx+r*.3} ${cy+r*.72}"/></g>`).join("")+"</g>";
/* ---------- thời tiết (64×64) ---------- */
const rbArcs=(cx,cy,r0,w,gap,op)=>{const cols=["#F0605A","#F6A24A","#F7D35B","#7CCB6C","#5BAAE6","#8697E6"];return `<g fill="none" opacity="${op||1}">`+cols.map((c,i)=>{const r=r0-i*(w+gap);return `<path d="M${cx-r} ${cy}A${r} ${r} 0 0 1 ${cx+r} ${cy}" stroke="${c}" stroke-width="${w}"/>`}).join("")+"</g>"};
const W={
 sun:S("0 0 64 64",sunAt(32,32,12.5)),
 partly:S("0 0 64 64",sunAt(23,22,8.5)+cloudC(37,38,.95)),
 cloud:S("0 0 64 64",cloudC(32,32,1.15)),
 rain:S("0 0 64 64",cloudC(32,24,1.1,"gClD")+drop(21,52,1.1)+drop(32,57,1.1)+drop(43,52,1.1)),
 storm:S("0 0 64 64",cloudC(32,22,1.1,"gClD")+bolt(25,36,1.05)+drop(15,53,.9)+drop(50,53,.9)),
 snow:S("0 0 64 64",cloudC(32,24,1.1)+flake(21,53,4.6,"#4FA3DA",1.5)+flake(34,57,4.6,"#4FA3DA",1.5)+flake(46,52,4.6,"#4FA3DA",1.5)),
 frost:S("0 0 64 64",flake(32,32,22,"#4FA3DA",3.2)),
 hot:S("0 0 64 64",`<rect x="26" y="6" width="12" height="38" rx="6" fill="#fff" stroke="#C9D3DC" stroke-width="1.6"/><rect x="30.2" y="14" width="3.6" height="32" rx="1.8" fill="url(#gHot)"/><circle cx="32" cy="48" r="10" fill="url(#gHot)" stroke="#B83A26" stroke-width="1.4"/><circle cx="29" cy="45" r="2.6" fill="#fff" opacity=".55"/><g stroke="#8A97A3" stroke-width="1.6" stroke-linecap="round"><path d="M42 12h5M42 19h3M42 26h5M42 33h3"/></g>`),
 cold:S("0 0 64 64",`<rect x="26" y="6" width="12" height="38" rx="6" fill="#fff" stroke="#C9D3DC" stroke-width="1.6"/><rect x="30.2" y="30" width="3.6" height="16" rx="1.8" fill="#4FA3DA"/><circle cx="32" cy="48" r="10" fill="#4FA3DA" stroke="#2A78B5" stroke-width="1.4"/><circle cx="29" cy="45" r="2.6" fill="#fff" opacity=".55"/><g stroke="#8A97A3" stroke-width="1.6" stroke-linecap="round"><path d="M42 12h5M42 19h3M42 26h5M42 33h3"/></g>`),
 dry:S("0 0 64 64",sunAt(40,18,8)+`<path d="M2 44C14 38 24 46 34 41S54 38 62 43V62H2z" fill="url(#gSoil)"/><path d="M12 62l5-10-4-6M30 62l-3-9 6-5-2-6M48 62l-4-12 7-4" fill="none" stroke="#5E3A1D" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`),
 wind:S("0 0 64 64",`<g fill="none" stroke="#7E9AB3" stroke-width="3.6" stroke-linecap="round"><path d="M8 24h32a7 7 0 1 0-7-7"/><path d="M8 34h44a7 7 0 1 1-7 7"/><path d="M8 44h22a6 6 0 1 1-6 6"/></g>`),
 drop:S("0 0 64 64",`<path d="M32 6C44 22 52 30 52 40a20 20 0 0 1-40 0C12 30 20 22 32 6z" fill="url(#gDr)" stroke="#2A7FC4" stroke-width="1.6"/><ellipse cx="23" cy="40" rx="3.4" ry="6.2" transform="rotate(14 23 40)" fill="#fff" opacity=".55"/>`),
 humid:S("0 0 64 64",`<path d="M26 8C36 22 43 30 43 38a17 17 0 0 1-34 0C9 30 16 22 26 8z" fill="url(#gDr)" stroke="#2A7FC4" stroke-width="1.5"/>`+drop(49,22,1.1)+drop(52,46,1.4)+`<ellipse cx="19" cy="38" rx="2.8" ry="5.2" transform="rotate(14 19 38)" fill="#fff" opacity=".55"/>`),
 evap:S("0 0 64 64",sunAt(22,20,7)+`<g fill="none" stroke="#5DA9DD" stroke-width="3" stroke-linecap="round"><path d="M34 54c-6-5 6-8 0-13s6-8 0-13"/><path d="M46 54c-6-5 6-8 0-13s6-8 0-13"/><path d="M22 54c-6-5 6-8 0-13"/></g>`),
 trend:S("0 0 64 64",`<path d="M8 52L24 36l10 8 22-24" fill="none" stroke="#D9692F" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M42 18h14v14" fill="none" stroke="#D9692F" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>`),
 rainbow:S("0 0 64 64",rbArcs(32,47,27,3.9,.5)+`<path d="M6.2 47A25.8 25.8 0 0 1 57.8 47" fill="none" stroke="#fff" stroke-width="1.3" opacity=".55"/>`+cloudC(13,48,.52)+cloudC(51,48,.52)),
 sprout:S("0 0 64 64",`<path d="M32 58V30" stroke="#4A8F3E" stroke-width="3.4" stroke-linecap="round"/><path d="M32 34C32 20 20 14 8 16c0 12 10 20 24 18z" fill="url(#gLf)" stroke="#2F7D3E" stroke-width="1.4" stroke-linejoin="round"/><path d="M32 28C32 16 42 8 56 10c0 12-10 20-24 18z" fill="url(#gLfD)" stroke="#2F7D3E" stroke-width="1.4" stroke-linejoin="round"/><path d="M18 58h28" stroke="#8A5A2B" stroke-width="4" stroke-linecap="round"/>`),
};
/* ---------- cây trồng (48×48) ---------- */
const grain=(x,y,r,fill,stroke)=>`<ellipse cx="${x}" cy="${y}" rx="2.4" ry="3.6" transform="rotate(${r} ${x} ${y})" fill="${fill}" stroke="${stroke}" stroke-width=".8"/>`;
const leafP=(d,fill)=>`<path d="${d}" fill="${fill||"url(#gLf)"}" stroke="#2F7D3E" stroke-width="1" stroke-linejoin="round"/>`;
const pod=(d,beans,col,stk)=>`<path d="${d}" fill="${col}" stroke="${stk}" stroke-width="1.2" stroke-linejoin="round"/>`+beans;
const C={
 maize:`<path d="M24 5c8 4 13 15 11 27-1 6-5 10-11 11-6-1-10-5-11-11C11 20 16 9 24 5z" fill="#F6C73A" stroke="#C99A12" stroke-width="1.2"/>`+[[19,15],[24,13],[29,15],[18,21],[23,20],[28,20],[33,22],[18,27],[23,27],[28,27],[20,33],[26,33]].map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="2.1" fill="#E4A91D"/>`).join("")+`<path d="M24 20C12 22 6 34 11 44c4-1 9-5 11-12 1-5 1-9 2-12z" fill="#6DBE5A" stroke="#2F7D3E" stroke-width="1"/><path d="M24 20c12 2 18 14 13 24-4-1-9-5-11-12-1-5-1-9-2-12z" fill="#4A9F48" stroke="#2F7D3E" stroke-width="1"/>`,
 rice:`<path d="M8 44C13 30 17 14 29 9c7-2 12 2 12 9" fill="none" stroke="#7CAE3E" stroke-width="2.4" stroke-linecap="round"/>`+[[20,18,-60],[24,13,-35],[29,10,-10],[34,10,15],[38,13,35],[40,18,55],[22,22,-70],[27,17,-30],[33,15,0],[37,19,35]].map(g=>grain(g[0],g[1],g[2],"#EBD25E","#B89A2C")).join("")+`<path d="M8 44c5-9 14-13 26-13" fill="none" stroke="#4F9A47" stroke-width="2.4" stroke-linecap="round"/>`,
 wheat:`<path d="M24 44V12" stroke="#B9902F" stroke-width="2.2" stroke-linecap="round"/>`+[10,16,22,28].map((y,i)=>grain(18,y+4,-28,"#E2B544","#A8801E")+grain(30,y+4,28,"#E2B544","#A8801E")).join("")+grain(24,8,0,"#E2B544","#A8801E")+`<g stroke="#B9902F" stroke-width="1" stroke-linecap="round"><path d="M17 11l-4-7M31 11l4-7M24 5V1"/></g>`+leafP("M24 40C16 40 11 36 9 30c8 0 13 3 15 10z"),
 sorghum:`<path d="M24 44V22" stroke="#7B8F3A" stroke-width="2.4" stroke-linecap="round"/><ellipse cx="24" cy="15" rx="9" ry="12" fill="#B9532F" stroke="#7E2F16" stroke-width="1.2"/>`+[[20,9],[26,8],[18,15],[24,14],[30,15],[21,21],[27,21]].map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="2.2" fill="#D9774C"/>`).join("")+leafP("M24 42c-9-1-14-6-15-13 9 0 14 5 15 13z")+leafP("M24 38c8 0 13-5 15-11-8-1-14 3-15 11z","url(#gLfD)"),
 millet:`<path d="M24 46V28" stroke="#7B8F3A" stroke-width="2.2" stroke-linecap="round"/><path d="M24 30C14 26 16 8 26 4c4 8 7 16-2 26z" fill="#E1B24D" stroke="#A8801E" stroke-width="1.2"/><g stroke="#B58A26" stroke-width="1.2" stroke-linecap="round"><path d="M20 12l5 3M19 18l7 2M20 24l6 1"/></g>`+leafP("M24 44c-8 0-13-4-15-10 8-1 14 3 15 10z"),
 rye:`<path d="M24 46V14" stroke="#7E9A5A" stroke-width="2.2" stroke-linecap="round"/>`+[9,15,21,27].map(y=>grain(19,y+3,-22,"#B9C98A","#7E9A5A")+grain(29,y+3,22,"#B9C98A","#7E9A5A")).join("")+`<g stroke="#8AA06A" stroke-width="1" stroke-linecap="round"><path d="M18 8L11 0M30 8l7-8M24 4V-2"/></g>`+leafP("M24 42c-8 0-13-4-15-10 8-1 14 3 15 10z"),
 soybean:pod("M6 34C10 14 28 6 42 10 38 26 24 40 6 34z",[[16,28],[24,21],[33,16]].map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="4.4" fill="#C6EA8A" stroke="#7DB14A" stroke-width=".9"/>`).join(""),"#8CC64F","#4E8B2E")+leafP("M30 44c-2-8 2-14 10-16 1 8-3 14-10 16z"),
 groundnut:`<g transform="rotate(-28 24 24)"><path d="M9 24a8 8 0 0 1 8-8h3a4 4 0 0 1 4 4 4 4 0 0 1 4-4h3a8 8 0 0 1 8 8 8 8 0 0 1-8 8h-3a4 4 0 0 1-4-4 4 4 0 0 1-4 4h-3a8 8 0 0 1-8-8z" fill="#E0BA83" stroke="#A98349" stroke-width="1.3"/><g fill="#C69A5D"><circle cx="15" cy="21" r="1.2"/><circle cx="18" cy="27" r="1.2"/><circle cx="31" cy="21" r="1.2"/><circle cx="34" cy="27" r="1.2"/><circle cx="22" cy="23" r="1.2"/><circle cx="27" cy="25" r="1.2"/></g></g>`,
 mungbean:`<g fill="none" stroke-linecap="round"><path d="M8 38C12 22 24 10 40 8" stroke="#4E8B2E" stroke-width="7"/><path d="M8 38C12 22 24 10 40 8" stroke="#7DBF4C" stroke-width="4.6"/><path d="M12 44C16 30 28 20 42 20" stroke="#4E8B2E" stroke-width="6"/><path d="M12 44C16 30 28 20 42 20" stroke="#8BCB58" stroke-width="3.8"/></g>`,
 cowpea:`<path d="M6 42C16 40 30 28 36 8" fill="none" stroke="#3F7F2A" stroke-width="6.4" stroke-linecap="round"/><path d="M6 42C16 40 30 28 36 8" fill="none" stroke="#8FD059" stroke-width="4" stroke-linecap="round"/><path d="M38 6c4 0 6 3 6 7-4 0-7-3-6-7z" fill="url(#gLf)" stroke="#2F7D3E" stroke-width="1"/>`,
 pea:`<path d="M5 28C8 14 24 8 43 14 40 30 24 40 5 28z" fill="#7CBF4A" stroke="#3F7F2A" stroke-width="1.3" stroke-linejoin="round"/>`+[[14,24],[22,22],[30,22],[37,19]].map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="4.6" fill="#B6E67C" stroke="#6AA83A" stroke-width=".9"/>`).join("")+`<circle cx="12.4" cy="22.6" r="1.2" fill="#fff" opacity=".7"/>`,
 chickpea:`<path d="M24 9c9 0 15 6 15 15 0 8-7 15-15 15S9 32 9 24c0-6 4-9 9-10 2-2 3-5 6-5z" fill="#E7CD94" stroke="#B8935A" stroke-width="1.3"/><path d="M20 20c3 1 5 3 5 7" fill="none" stroke="#C7A76B" stroke-width="1.4" stroke-linecap="round"/><circle cx="17" cy="28" r="1.2" fill="#C7A76B"/>`,
 lentil:`<g stroke="#9A5A1E" stroke-width="1.2">`+[[17,18,9,"#D58A3A"],[31,19,9,"#C57A2C"],[23,31,10,"#E09A4A"]].map(l=>`<ellipse cx="${l[0]}" cy="${l[1]}" rx="${l[2]}" ry="${l[2]-1.5}" fill="${l[3]}"/>`).join("")+`</g><g fill="#fff" opacity=".4"><ellipse cx="14" cy="15" rx="2.6" ry="1.6"/><ellipse cx="28" cy="16" rx="2.6" ry="1.6"/><ellipse cx="20" cy="28" rx="3" ry="1.8"/></g>`,
 sunflower:`<g>`+Array.from({length:14},(_,i)=>`<ellipse cx="24" cy="9.5" rx="3.2" ry="7" transform="rotate(${i*360/14} 24 24)" fill="#F7B800" stroke="#D68F00" stroke-width=".8"/>`).join("")+`</g><circle cx="24" cy="24" r="8.4" fill="#7A4B1E" stroke="#4E2D0F" stroke-width="1.2"/>`+[[21,21],[27,21],[24,25],[20,27],[28,27],[24,19]].map(p=>`<circle cx="${p[0]}" cy="${p[1]}" r="1.1" fill="#A8703A"/>`).join(""),
 canola:`<path d="M24 46V20M24 30l-10-8M24 26l10-8" stroke="#4F9A47" stroke-width="2.2" stroke-linecap="round" fill="none"/>`+[[24,14],[13,18],[35,14],[24,26]].map(p=>`<g transform="translate(${p[0]} ${p[1]})">`+[0,90,180,270].map(a=>`<ellipse cx="0" cy="-3.8" rx="2.6" ry="3.8" transform="rotate(${a})" fill="#F7D417" stroke="#D1A800" stroke-width=".7"/>`).join("")+`<circle r="1.6" fill="#8CB33B"/></g>`).join(""),
 potato:`<path d="M9 28c-2-9 6-17 17-16 10 1 16 7 14 16-2 9-11 13-20 11-7-2-10-5-11-11z" fill="#D3A468" stroke="#9A6E33" stroke-width="1.3"/><g fill="#9A6E33"><circle cx="18" cy="22" r="1.6"/><circle cx="28" cy="19" r="1.6"/><circle cx="31" cy="29" r="1.6"/><circle cx="20" cy="31" r="1.6"/><circle cx="25" cy="26" r="1.3"/></g><path d="M14 18c4-4 9-5 14-4" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" opacity=".45"/>`,
 sweetpotato:`<path d="M5 30c4-12 18-18 32-14 5 1 7 5 5 9-2 6-12 12-22 13-9 1-16-1-15-8z" fill="#C85A3F" stroke="#8E3420" stroke-width="1.3"/><path d="M12 24c6-5 14-7 22-5" fill="none" stroke="#E79479" stroke-width="2" stroke-linecap="round" opacity=".7"/><path d="M41 18c3-3 4-7 2-10" fill="none" stroke="#6C7F3A" stroke-width="2" stroke-linecap="round"/>`,
 cassava:`<path d="M6 40C14 26 28 14 41 9c3 5 1 11-5 16-8 7-18 12-28 17z" fill="#A87444" stroke="#6E4824" stroke-width="1.3"/><ellipse cx="40" cy="10" rx="4.4" ry="3.2" transform="rotate(-30 40 10)" fill="#F4ECD8" stroke="#6E4824" stroke-width="1"/><path d="M12 34l5-4M20 28l5-4M27 22l5-3" stroke="#6E4824" stroke-width="1.2" stroke-linecap="round"/>`,
 cabbage:`<circle cx="24" cy="25" r="17" fill="#79BC4A" stroke="#3E8A33" stroke-width="1.4"/><path d="M24 8c-8 6-10 18-3 30M24 8c8 6 10 18 3 30" fill="none" stroke="#B4E07C" stroke-width="2.4" stroke-linecap="round"/><path d="M10 28c8-1 20-1 28 0" fill="none" stroke="#B4E07C" stroke-width="2" stroke-linecap="round"/><path d="M24 12v26" stroke="#E7F6C9" stroke-width="1.6" stroke-linecap="round"/>`,
 alfalfa:`<path d="M24 46V8" stroke="#4F9A47" stroke-width="2.2" stroke-linecap="round"/>`+[[24,12,0],[24,24,0],[24,35,0]].map((p,i)=>`<g transform="translate(24 ${p[1]})">`+[-38,0,38].map(a=>`<ellipse cx="0" cy="-5.6" rx="2.9" ry="5.2" transform="rotate(${a})" fill="url(#gLf)" stroke="#2F7D3E" stroke-width=".8"/>`).join("")+`</g>`).join("")+`<circle cx="24" cy="6" r="2.8" fill="#9C6AD1" stroke="#6B3FA0" stroke-width=".7"/>`,
 vetch:`<path d="M12 46C14 32 26 26 26 12M26 12c4-3 8-2 9 2" fill="none" stroke="#4F9A47" stroke-width="2.2" stroke-linecap="round"/>`+[[17,38,-40],[21,30,-30],[28,22,40],[24,16,-20]].map(p=>`<g transform="translate(${p[0]} ${p[1]}) rotate(${p[2]})">`+[-1,1].map(s=>`<ellipse cx="${s*4.5}" cy="0" rx="4.2" ry="2.2" fill="url(#gLf)" stroke="#2F7D3E" stroke-width=".7"/>`).join("")+`</g>`).join("")+`<circle cx="33" cy="30" r="2.4" fill="#D7578C"/><circle cx="36" cy="36" r="2.4" fill="#D7578C"/>`,
 sunnhemp:`<path d="M24 46V10" stroke="#6C8F3A" stroke-width="2.2" stroke-linecap="round"/>`+[[24,12],[16,20],[31,22],[18,31],[30,33]].map(p=>`<g transform="translate(${p[0]} ${p[1]})"><path d="M0 0c-5-1-7-5-6-8 4 1 6 4 6 8zM0 0c5-1 7-5 6-8-4 1-6 4-6 8z" fill="#F1C21B" stroke="#B88F00" stroke-width=".8"/><circle r="1.6" fill="#E08A00"/></g>`).join("")+leafP("M24 42c-7 0-12-3-14-8 7-1 12 2 14 8z"),
};
const crop=(id,cls)=>S("0 0 48 48",C[id]||C.sprout||W.sprout,cls||"");
const cropIn=(id,x,y,sz)=>`<svg x="${x}" y="${y}" width="${sz}" height="${sz}" viewBox="0 0 48 48">${C[id]||""}</svg>`;
/* ---------- lựa chọn có hình (120×72) ---------- */
const spr=(x,y,s)=>`<g transform="translate(${x} ${y}) scale(${s||1})"><path d="M0 0V-8" stroke="#3E8A33" stroke-width="1.6" stroke-linecap="round"/><path d="M0 -6C-1 -10 -5 -11 -8 -9 -7 -5 -3 -4 0 -6zM0 -7C1 -11 5 -12 8 -10 7 -6 3 -5 0 -7z" fill="#5DB05B"/></g>`;
const box=(inner,bg)=>S("0 0 120 72",`<defs><clipPath id="cb"><rect width="120" height="72" rx="10"/></clipPath></defs><g clip-path="url(#cb)">${bg||""}${inner}</g>`);
const dots=(n,seed,x0,y0,x1,y1,rmin,rmax,cols)=>{let s=seed,o="";const r=()=>(s=(s*9301+49297)%233280)/233280;for(let i=0;i<n;i++){o+=`<circle cx="${(x0+r()*(x1-x0)).toFixed(1)}" cy="${(y0+r()*(y1-y0)).toFixed(1)}" r="${(rmin+r()*(rmax-rmin)).toFixed(1)}" fill="${cols[Math.floor(r()*cols.length)]}"/>`}return o};
const sky=`<rect width="120" height="72" fill="#DCEFFB"/>`;
const OPT={
 soil:{
  sand:box(`<rect y="22" width="120" height="50" fill="url(#gSand)"/>`+dots(70,3,0,24,120,72,1.6,3.4,["#D5B574","#F3E0AE","#C9A55C","#FAEBC4"])+`<rect width="120" height="22" fill="#DCEFFB"/><rect y="19" width="120" height="6" fill="#7DBB55"/>`+spr(26,19)+spr(60,19)+spr(96,19)),
  loam:box(`<rect y="22" width="120" height="50" fill="url(#gLoam)"/>`+dots(46,5,0,26,120,72,1.4,3.2,["#6E4527","#A57A52","#5A361C","#B38A62"])+`<g stroke="#D9C2A0" stroke-width="1.4" fill="none" stroke-linecap="round"><path d="M30 26c-3 8 2 12-1 20M72 26c4 6-1 12 3 20M98 26c-2 6 2 10 0 16"/></g><rect width="120" height="22" fill="#DCEFFB"/><rect y="19" width="120" height="6" fill="#6DB24B"/>`+spr(26,19)+spr(60,19)+spr(96,19)),
  silt:box(`<rect y="22" width="120" height="50" fill="url(#gSilt)"/>`+dots(120,9,0,24,120,72,.7,1.3,["#A08A6C","#CDBA9F","#94805F"])+`<g stroke="#A8936F" stroke-width="1" fill="none" opacity=".7"><path d="M0 40h120M0 54h120"/></g><rect width="120" height="22" fill="#DCEFFB"/><rect y="19" width="120" height="6" fill="#74B84F"/>`+spr(26,19)+spr(60,19)+spr(96,19)),
  clay:box(`<rect y="22" width="120" height="50" fill="url(#gClay)"/><g stroke="#7E3E26" stroke-width="1.6" fill="none" stroke-linecap="round"><path d="M0 34q15-5 30 0t30 0 30 0 30 0M0 46q15-5 30 0t30 0 30 0 30 0M0 58q15-5 30 0t30 0 30 0 30 0"/></g><g stroke="#C77A58" stroke-width="1" fill="none" opacity=".7"><path d="M10 40q10-4 20 0M60 52q10-4 20 0M80 38q10-4 20 0"/></g><rect width="120" height="22" fill="#DCEFFB"/><rect y="19" width="120" height="6" fill="#6DB24B"/>`+spr(26,19)+spr(60,19)+spr(96,19)),
 },
 drain:{
  poor:box(`<rect y="20" width="120" height="52" fill="#8B5E3B"/>`+dots(30,2,0,40,120,72,1.2,2.6,["#6E4527","#A57A52"])+`<path d="M0 22q15-4 30 0t30 0 30 0 30 0V50H0z" fill="url(#gWater)" opacity=".92"/><g stroke="#fff" stroke-width="1.4" fill="none" opacity=".6" stroke-linecap="round"><path d="M14 30q6-3 12 0M60 36q6-3 12 0M92 28q6-3 12 0"/></g>`+spr(20,22)+spr(100,22),sky),
  moderate:box(`<rect y="20" width="120" height="52" fill="#8B5E3B"/>`+dots(36,4,0,24,120,72,1.2,2.6,["#6E4527","#A57A52"])+`<path d="M0 50q15-4 30 0t30 0 30 0 30 0V72H0z" fill="url(#gWater)" opacity=".9"/>`+drop(30,34,1.1)+drop(84,38,1.1)+spr(20,20)+spr(60,20)+spr(100,20)+`<rect y="17" width="120" height="4" fill="#6DB24B"/>`,sky),
  good:box(`<rect y="20" width="120" height="52" fill="#9A6B43"/>`+dots(40,6,0,24,120,72,1.4,3,["#7A4E2A","#B88A5E","#C79A6E"])+`<path d="M0 64q15-3 30 0t30 0 30 0 30 0V72H0z" fill="url(#gWater)" opacity=".9"/><g fill="none" stroke="#2D8EDB" stroke-width="1.6" stroke-linecap="round"><path d="M24 30v14M60 28v18M96 30v14"/><path d="M20 40l4 5 4-5M56 42l4 5 4-5M92 40l4 5 4-5"/></g>`+spr(24,20)+spr(60,20)+spr(96,20)+`<rect y="17" width="120" height="4" fill="#6DB24B"/>`,sky),
 },
 slope:(a)=>{const y0=[36,30,22,12][a],y1=[36,42,50,60][a];const pts=`0,${y0} 120,${y1} 120,72 0,72`;let sp="";for(let i=0;i<6;i++){const x=12+i*19,y=y0+(y1-y0)*x/120;sp+=spr(x,y-1,.8)}
  return box(`<polygon points="${pts}" fill="url(#gSoil)"/><polyline points="0,${y0} 120,${y1}" stroke="#6DB24B" stroke-width="4" fill="none"/>`+sp+`<g>${sunAt(100,14,5.5)}</g>`,sky)},
 irrig:[
  box(`<rect y="44" width="120" height="28" fill="#C9A06A"/><path d="M0 44h120" stroke="#6DB24B" stroke-width="4"/>`+cloudC(44,18,.62,"gClD")+drop(32,36,1)+drop(46,32,1)+drop(60,37,1)+spr(88,44)+spr(104,44)+`<g transform="translate(78 12)">${sunAt(14,8,5)}</g>`,sky),
  box(`<rect y="44" width="120" height="28" fill="#9A6B43"/><path d="M0 44h120" stroke="#6DB24B" stroke-width="4"/><rect x="18" y="26" width="8" height="22" fill="#9AA6B3" stroke="#6B7787" stroke-width="1.2"/><path d="M26 30h20a6 6 0 0 1 6 6v2" fill="none" stroke="#6B7787" stroke-width="3" stroke-linecap="round"/>`+drop(52,46,1.3)+`<ellipse cx="60" cy="52" rx="18" ry="4" fill="url(#gWater)"/>`+spr(92,44)+spr(106,44),sky),
  box(`<rect y="48" width="120" height="24" fill="#8B5E3B"/><rect y="44" width="120" height="5" fill="#6DB24B"/><path d="M0 56q10-4 20 0t20 0 20 0 20 0 20 0 20 0V72H0z" fill="url(#gWater)"/><g fill="none" stroke="#2D8EDB" stroke-width="1.6" stroke-linecap="round"><path d="M30 38q8-18 16 0M62 38q8-18 16 0M92 38q8-18 16 0"/></g>`+drop(38,24,1)+drop(70,22,1)+drop(100,24,1)+spr(14,44)+spr(46,44)+spr(80,44),sky)
 ],
 pref:{
  water:S("0 0 56 56",`<path d="M26 5C36 17 43 24 43 32a17 17 0 0 1-34 0C9 24 16 17 26 5z" fill="url(#gDr)" stroke="#2A7FC4" stroke-width="1.5"/><ellipse cx="19" cy="31" rx="2.8" ry="5.4" transform="rotate(14 19 31)" fill="#fff" opacity=".55"/><path d="M40 50c0-8 4-12 13-13 0 8-4 13-13 13z" fill="url(#gLf)" stroke="#2F7D3E" stroke-width="1.2"/>`),
  soil:S("0 0 56 56",`<path d="M4 52c2-14 12-20 24-20s22 6 24 20z" fill="url(#gSoil)" stroke="#6B4122" stroke-width="1.3"/><path d="M28 32V18" stroke="#3E8A33" stroke-width="2.4" stroke-linecap="round"/><path d="M28 24C28 14 20 10 11 11c0 9 7 15 17 13z" fill="url(#gLf)" stroke="#2F7D3E" stroke-width="1.2"/><path d="M28 20C28 11 36 6 45 8c0 9-7 14-17 12z" fill="url(#gLfD)" stroke="#2F7D3E" stroke-width="1.2"/>`),
  income:S("0 0 56 56",`<g stroke="#B7860B" stroke-width="1.3"><ellipse cx="22" cy="44" rx="14" ry="5.5" fill="#F5C842"/><path d="M8 44v-6a14 5.5 0 0 0 28 0v6" fill="#E9B424"/><ellipse cx="22" cy="38" rx="14" ry="5.5" fill="#F8D45E"/><path d="M8 38v-6a14 5.5 0 0 0 28 0v6" fill="#E9B424"/><ellipse cx="22" cy="32" rx="14" ry="5.5" fill="#FAE07E"/></g><path d="M34 22l8-9 6 6 8-11" fill="none" stroke="#3E9B4F" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" transform="translate(-6 0)"/><path d="M42 6h8v8" fill="none" stroke="#3E9B4F" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" transform="translate(-6 0)"/>`),
  safe:S("0 0 56 56",`<path d="M28 6C14 6 6 16 6 26h44C50 16 42 6 28 6z" fill="#E0763A" stroke="#A8431B" stroke-width="1.4"/><path d="M17 26c0-9 4-16 11-20M39 26c0-9-4-16-11-20" fill="none" stroke="#A8431B" stroke-width="1.1"/><path d="M28 26v20a5 5 0 0 1-10 0" fill="none" stroke="#6B4122" stroke-width="2.6" stroke-linecap="round"/><g fill="url(#gDr)"><path d="M10 38l-2 5a2 2 0 1 0 4 0zM44 36l-2 5a2 2 0 1 0 4 0zM36 48l-2 5a2 2 0 1 0 4 0z"/></g>`)
 }
};
/* ---------- banner từng trang (420×150) ---------- */
const hills=(cols,base)=>cols.map((c,i)=>`<path d="M0 ${base[i][0]}C60 ${base[i][1]} 120 ${base[i][2]} 210 ${base[i][3]}S360 ${base[i][4]} 420 ${base[i][5]}V150H0z" fill="${c}"/>`).join("");
const arrowRing=(cx,cy,r,col)=>{let o="";for(let i=0;i<3;i++){const a0=(i*120-62)*Math.PI/180,a1=(i*120+34)*Math.PI/180,x0=cx+r*Math.cos(a0),y0=cy+r*Math.sin(a0),x1=cx+r*Math.cos(a1),y1=cy+r*Math.sin(a1);o+=`<path d="M${x0.toFixed(1)} ${y0.toFixed(1)}A${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}" fill="none" stroke="${col}" stroke-width="9" stroke-linecap="round"/>`;const nx=Math.cos(a1),ny=Math.sin(a1),tx=-ny,ty=nx;o+=`<path d="M${(x1+nx*12).toFixed(1)} ${(y1+ny*12).toFixed(1)}L${(x1+tx*13).toFixed(1)} ${(y1+ty*13).toFixed(1)}L${(x1-nx*12).toFixed(1)} ${(y1-ny*12).toFixed(1)}Z" fill="${col}" stroke="${col}" stroke-width="2.5" stroke-linejoin="round"/>`}return o};
const BAN={
 1:S("0 0 420 150",`<circle cx="330" cy="58" r="64" fill="url(#gGlow)"/>${ray(330,58,38,54,12,5,"#FFE28A")}<circle cx="330" cy="58" r="30" fill="url(#gSun)" stroke="#F0A92A" stroke-width="2"/>`+hills(["#8ECB63","#5FAF4E","#3E8F45","#2A6F3B"],[[104,92,112,90,112,98],[120,108,128,106,126,112],[134,124,140,126,132,128],[146,140,148,144,138,146]])+`<g stroke="#2A6F3B" stroke-width="2" fill="none" opacity=".55"><path d="M20 128q60-12 130-4M40 140q70-10 150-2M200 132q60-8 120 0"/></g>`+`<g transform="translate(96 112) scale(1.5)"><ellipse cx="0" cy="2" rx="13" ry="4" fill="rgba(0,0,0,.18)"/><path d="M0 0C-10-12-16-20-16-28a16 16 0 0 1 32 0C16-20 10-12 0 0z" fill="#E8573E" stroke="#B8402B" stroke-width="1.6" stroke-linejoin="round"/><circle cx="0" cy="-28" r="6.4" fill="#fff"/></g>`),
 2:S("0 0 420 150",`<circle cx="290" cy="50" r="62" fill="url(#gGlow)"/>${ray(290,50,32,46,12,4.5,"#FFE28A")}<circle cx="290" cy="50" r="26" fill="url(#gSun)" stroke="#F0A92A" stroke-width="2"/>`+cloud(300,22,2.1)+cloud(190,52,1.35)+`<g stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".85"><path d="M236 108l-5 14M252 112l-5 14M268 108l-5 14M340 110l-5 14M356 114l-5 14"/></g><g transform="translate(120 22) scale(1.05)">${W.hot.replace(/^<svg[^>]*>|<\/svg>$/g,"")}</g><path d="M0 138c70-16 130 6 210-6s150 10 210-4v22H0z" fill="rgba(255,255,255,.28)"/>`),
 3:S("0 0 420 150",`<path d="M0 62h420v88H0z" fill="url(#gSoil)"/><path d="M0 62C50 52 100 66 160 58s120 8 260-2V70H0z" fill="#6DB24B"/><path d="M0 92h420M0 122h420" stroke="rgba(0,0,0,.14)" stroke-width="2"/>`+dots(46,11,0,70,420,148,2,5.5,["#6E4527","#A57A52","#5A361C","#C79A6E"])+[80,150,230,300,370].map((x,i)=>`<g transform="translate(${x} ${60}) scale(1.6)"><path d="M0 0V-14" stroke="#2F7D3E" stroke-width="2.4" stroke-linecap="round"/><path d="M0 -10C-2 -18 -9 -20 -14 -16 -12 -9 -5 -7 0 -10zM0 -12C2 -20 9 -22 14 -18 12 -11 5 -9 0 -12z" fill="url(#gLf)" stroke="#2F7D3E" stroke-width=".9"/></g>`).join("")+`<g stroke="#E9D9B6" stroke-width="3" fill="none" stroke-linecap="round" opacity=".9"><path d="M80 66v28M80 84l-8 10M80 84l8 12M150 66v34M150 90l-9 10M150 90l9 12M230 66v26M300 66v30M370 66v28"/></g>`+drop(112,28,2)+drop(262,20,2.3)+drop(332,34,1.8)+`<g transform="translate(300 -14)">${sunAt(40,30,15)}</g>`),
 4:S("0 0 420 150",hills(["#8ECB63","#5FAF4E","#2F7F44"],[[112,104,118,100,118,108],[126,118,134,120,128,126],[140,136,144,140,134,142]])+`<g transform="translate(300 78)"><circle r="68" fill="rgba(255,255,255,.14)"/><circle r="58" fill="rgba(255,255,255,.12)"/>${arrowRing(0,0,46,"#fff")}<circle r="31" fill="#fff" opacity=".95"/>${cropIn("rice",-23,-27,22)}${cropIn("soybean",1,-27,22)}${cropIn("maize",-12,-5,24)}</g>`+`<g transform="translate(70 30)">${cropIn("sunflower",0,0,42)}${cropIn("wheat",50,16,40)}</g>`),
 5:S("0 0 420 150",`<circle cx="318" cy="38" r="48" fill="url(#gGlow)"/>${sunAt(330,34,20)}`+cloud(230,22,2.5,"gClD")+cloud(296,40,1.9,"gClD")+`<path transform="translate(290 78) scale(1.9)" d="M8 0 0 14h6l-3 12L15 9H8.5z" fill="url(#gBolt)" stroke="#E08A00" stroke-width="1" stroke-linejoin="round"/><g stroke="#C7E5FA" stroke-width="3.4" stroke-linecap="round" opacity=".9"><path d="M246 104l-6 16M264 108l-6 16M338 106l-6 16M356 100l-6 16M376 108l-6 16"/></g><g transform="translate(100 30) scale(1.05)">${W.hot.replace(/^<svg[^>]*>|<\/svg>$/g,"")}</g><path d="M24 142L84 128 144 136 204 120 264 134 324 118 396 128" fill="none" stroke="rgba(255,255,255,.7)" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 9"/>`),
 6:S("0 0 420 150",`<circle cx="84" cy="50" r="76" fill="url(#gGlow)"/>${sunAt(84,50,19)}`+rbArcs(292,152,120,12,1.2,.97)+`<path d="M170 152A122 122 0 0 1 414 152" fill="none" stroke="rgba(255,255,255,.34)" stroke-width="2.4"/>`+cloudC(172,134,1.5)+cloudC(410,136,1.5)+`<path d="M0 126C70 108 150 132 230 120S370 112 420 124V150H0z" fill="#79C45A"/><path d="M0 138C90 124 170 146 260 134S380 128 420 138V150H0z" fill="#4FA64A"/>`+[30,66,108,150,338,376].map((x,i)=>spr(x,130+(i%3)*5,1.8)).join("")),
};
const BANW={6:S("0 0 420 70",`<circle cx="70" cy="30" r="48" fill="url(#gGlow)"/>${sunAt(70,30,11)}`+rbArcs(300,70,64,7.2,.7,.97)+`<path d="M232.4 70A67.6 67.6 0 0 1 367.6 70" fill="none" stroke="rgba(255,255,255,.4)" stroke-width="1.6"/>`+cloudC(236,58,.95)+cloudC(366,60,.95)+`<path d="M0 58C70 48 150 64 230 56S370 50 420 58V70H0z" fill="#79C45A"/><path d="M0 64C90 56 170 68 260 62S380 58 420 64V70H0z" fill="#4FA64A"/>`+[26,58,96,140,336,376].map((x,i)=>spr(x,63+(i%2)*3,1.15)).join(""))};
return {defs,W,C,BANW,hills,arrowRing,crop,cropIn,OPT,BAN,sunAt,cloud,drop,bolt,spr,dots,S};
})();

"use strict";
/* ---------- v1.0 · SONG NGỮ Việt – Anh (VI/EN) ----------
 * Giao diện viết bằng tiếng Việt; ở chế độ EN, mọi chữ hiển thị được dịch qua từ điển I18N (khóa tiếng Việt → tiếng Anh):
 *  1) khớp nguyên câu; 2) khớp mẫu có ô {} (phần biến được dịch đệ quy); 3) tách theo dấu phân cách rồi khớp từng đoạn;
 *  4) thay các cụm đã biết bên trong câu (dài trước, theo ranh giới từ). Bộ quan sát DOM dịch mọi nội dung được dựng sau đó.
 * Thêm/sửa bản dịch: sửa từ điển I18N_EN trong phần Python (khóa = đúng câu tiếng Việt, {} = phần thay đổi). */
const LANG=(()=>{try{const q=new URLSearchParams(location.search).get("lang");if(q==="en"||q==="vi"){localStorage.setItem("fa_lang",q);return q}return localStorage.getItem("fa_lang")==="en"?"en":"vi"}catch(e){return "vi"}})();
const EN=LANG==="en",DC=EN?".":",";
document.documentElement.lang=LANG;
const I18N=EN?__I18N__:{};
const _VI=/[À-ÃÈ-ÊÌÍÒ-ÕÙÚÝà-ãè-êìíò-õùúýĂăĐđĨĩŨũƠơƯư\u1EA0-\u1EF9]|\bKt TB\b/;
const _EX=new Map(),_TPL=[],_CACHE=new Map();
let _SUB=null;
const _WL=new Set(["Ngô","ngô","Cát","Sét","Thịt","Đất","Nước","Tháng","nhẹ","nặng","Limon","Bước","Tốt","Kém"]);  // từ đơn được thay bên trong câu
(()=>{if(!EN)return;const rx=s=>s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");const subs=[];
 const lit=p=>rx(p).replace(/^ +/,"\\s*").replace(/ +$/,"\\s*").replace(/ +/g,"\\s+");
 const add=(vi,en)=>{if(vi.includes("{}")){const parts=vi.split("{}");const lits=parts.filter(p=>p.trim());
   if(!lits.length)return;_TPL.push({re:new RegExp("^"+parts.map(lit).join("([\\s\\S]*?)")+"$"),lits,en,len:lits.join("").length})}
  else{if(!_EX.has(vi))_EX.set(vi,en);if(_VI.test(vi)&&(/\s/.test(vi)||_WL.has(vi)))subs.push(vi)}};
 const add2=(vi,en)=>{add(vi,en);
  if(/^[·—] /.test(vi)&&en.slice(0,2)===vi.slice(0,2))add(vi.slice(2),en.slice(2));
  if(/:$/.test(vi)&&/:$/.test(en)&&!_EX.has(vi.slice(0,-1).trim()))add(vi.slice(0,-1).trim(),en.slice(0,-1).trim())};
 for(const [vi,en] of Object.entries(I18N)){add2(vi,en);if(vi.includes("~"))add2(vi.replace(/~/g,"≈"),en.replace(/~/g,"≈"))}
 _TPL.sort((a,b)=>b.len-a.len);subs.sort((a,b)=>b.length-a.length);
 _SUB=subs.length?new RegExp("(?<!\\p{L})(?:"+subs.map(rx).join("|")+")(?!\\p{L})","gu"):null})();
function _core(s,d){const n=s.replace(/\s+/g," ");if(_EX.has(n))return _EX.get(n);if(!_VI.test(n))return s;
 for(const t of _TPL){if(!t.lits.every(l=>n.includes(l.trim())))continue;const m=n.match(t.re);if(!m)continue;
  let i=1;return t.en.replace(/\{\}/g,()=>{const g=m[i++]||"";return d<4?_tr(g,d+1):g})}
 return null}
const _DL=["\n",": "," · ","; "," — ",". ",", "," → "," – "];
const _PFX=/^(\[[^\]]*\]\s*|[-*•]\s+|#{1,6}\s+|\d+[.)]\s+)/;
function _tr(s,d){d=d||0;if(!s||!_VI.test(s))return s;const m=s.match(/^(\s*)([\s\S]*?)(\s*)$/),c=m[2];
 let r=_core(c,d);
 if(r==null&&d<8){const pm=c.match(_PFX);if(pm)r=pm[0]+_tr(c.slice(pm[0].length),d+1)}
 if(r==null&&d<8){const ds=_DL.filter(dl=>c.includes(dl));
  for(const dl of ds){if(r!=null)break;const P=c.split(dl),n=P.length;
   for(let k=1;k<n&&r==null;k++){const q=P.slice(k).join(dl);if(!_VI.test(q))continue;const t=_core(q,d+1);if(t!=null)r=_tr(P.slice(0,k).join(dl),d+1)+dl+t}
   for(let k=n-1;k>=1&&r==null;k--){const q=P.slice(0,k).join(dl);if(!_VI.test(q))continue;const h=_core(q,d+1);if(h!=null)r=h+dl+_tr(P.slice(k).join(dl),d+1)}}
  if(r==null&&ds.length)r=c.split(ds[0]).map(x=>_tr(x,d+1)).join(ds[0])}
 if(r==null)r=c;
 if(_SUB&&_VI.test(r))r=r.replace(_SUB,x=>_EX.get(x));
 return m[1]+r+m[3]}
function _t(s){if(!EN||s==null)return s;s=String(s);if(!_VI.test(s))return s;if(_CACHE.has(s))return _CACHE.get(s);const r=_tr(s,0);if(_CACHE.size<20000)_CACHE.set(s,r);return r}
const _TA=["title","placeholder","aria-label","alt"],_SKIP=/^(SCRIPT|STYLE|TEXTAREA|INPUT)$/;
function _trText(n){const p=n.parentNode;if(!p||_SKIP.test(p.nodeName)||(p.closest&&p.closest("[data-notr]")))return;const v=n.nodeValue;if(!_VI.test(v))return;const t=_t(v);if(t!==v)n.nodeValue=t}
function _trAttr(el){for(const a of _TA){const v=el.getAttribute&&el.getAttribute(a);if(v&&_VI.test(v)){const t=_t(v);if(t!==v)el.setAttribute(a,t)}}}
function _trTree(root){if(!EN||!root)return;if(root.nodeType===3){_trText(root);return}if(root.nodeType!==1&&root.nodeType!==9)return;if(root.nodeType===1){if(_SKIP.test(root.nodeName))return;_trAttr(root)}
 const w=document.createTreeWalker(root,5);let n;while((n=w.nextNode())){if(n.nodeType===3)_trText(n);else _trAttr(n)}}
if(EN){_trTree(document.documentElement);
 new MutationObserver(ms=>{for(const m of ms){if(m.type==="childList")m.addedNodes.forEach(_trTree);else if(m.type==="characterData")_trText(m.target);else _trAttr(m.target)}})
  .observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:_TA})}
/* biểu đồ Chart.js vẽ trên canvas: dịch nhãn trước khi vẽ */
function _trChart(cfg){if(!EN)return cfg;const d=cfg.data||{};if(d.labels)d.labels=d.labels.map(_t);(d.datasets||[]).forEach(x=>{if(x.label)x.label=_t(x.label)});
 const o=cfg.options=cfg.options||{};Object.values(o.scales||{}).forEach(s=>{if(s.title&&s.title.text)s.title.text=_t(s.title.text)});
 const tt=((o.plugins||{}).tooltip||{}).callbacks;if(tt&&tt.label){const f=tt.label;tt.label=x=>{const r=f(x);return r==null?r:_t(r)}}return cfg}
/* nút chuyển ngôn ngữ */
(()=>{const b=document.createElement("div");b.id="langSw";b.setAttribute("data-notr","");b.setAttribute("role","group");b.setAttribute("aria-label",EN?"Language":"Ngôn ngữ");
 b.innerHTML=`<button data-lg="vi" class="${EN?"":"on"}" title="Tiếng Việt">VI</button><button data-lg="en" class="${EN?"on":""}" title="English">EN</button>`;
 b.onclick=e=>{const x=e.target.closest("[data-lg]");if(!x||x.dataset.lg===LANG)return;try{localStorage.setItem("fa_lang",x.dataset.lg)}catch(er){}const u=new URL(location.href);u.searchParams.delete("lang");location.href=u.toString()};
 document.body.appendChild(b)})();
function _trHtml(h){if(!EN)return h;const d=new DOMParser().parseFromString(h,"text/html");d.documentElement.lang="en";_trTree(d.documentElement);return "<!doctype html>"+d.documentElement.outerHTML}
/* ---------- v0.9.1 · bộ icon tiêu đề riêng cho từng nội dung (cùng phong cách phẳng, cùng bảng màu) ---------- */
(()=>{const sv=i=>`<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">${i}</svg>`,K="#3E4A43",G="#4A8F3E",LG="#9BCB6B",O="#D9692F",Y="#F2C14E",B="#4FA3DA",R="#E0573E",BR="#9A6B3A",P="#FBF8EF";
 const st=(w)=>`stroke="${K}" stroke-width="${w||2.6}" stroke-linejoin="round" stroke-linecap="round"`;
 Object.assign(ART.W,{
 pin:sv(`<ellipse cx="32" cy="54" rx="22" ry="6" fill="${LG}"/><path d="M14 54h36" stroke="${G}" stroke-width="2.4" stroke-linecap="round"/><path d="M32 52C20 37 15 30 15 22a17 17 0 0 1 34 0c0 8-5 15-17 30z" fill="${R}" ${st()}/><circle cx="32" cy="22" r="6.5" fill="#fff" ${st(2.2)}/>`),
 cal:sv(`<rect x="8" y="12" width="48" height="44" rx="7" fill="#fff" ${st()}/><path d="M8 19a7 7 0 0 1 7-7h34a7 7 0 0 1 7 7v7H8z" fill="${G}" ${st()}/><path d="M20 7v10M44 7v10" ${st(3)}/>`+[[18,35],[28,35],[38,35],[18,46],[28,46]].map(([x,y])=>`<rect x="${x-3}" y="${y-3}" width="7" height="6" rx="1.6" fill="${LG}"/>`).join("")+`<circle cx="44" cy="45" r="7" fill="${O}" ${st(2.2)}/>`),
 calck:sv(`<rect x="8" y="12" width="44" height="42" rx="7" fill="#fff" ${st()}/><path d="M8 19a7 7 0 0 1 7-7h30a7 7 0 0 1 7 7v6H8z" fill="${Y}" ${st()}/><path d="M19 7v9M41 7v9" ${st(3)}/><circle cx="45" cy="45" r="12" fill="${G}" ${st()}/><path d="M39.5 45l4 4 7-8" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>`),
 clock:sv(`<circle cx="32" cy="33" r="24" fill="#fff" ${st()}/><path d="M32 9a24 24 0 0 1 23 17L32 33z" fill="${LG}"/><path d="M55 26a24 24 0 0 1-8 26L32 33z" fill="${Y}"/><circle cx="32" cy="33" r="24" fill="none" ${st()}/><path d="M32 33V18M32 33l9 6" ${st(3.2)}/><circle cx="32" cy="33" r="3" fill="${R}"/>`),
 hourglass:sv(`<path d="M16 8h32M16 56h32" ${st(3.4)}/><path d="M19 9c0 13 10 16 10 23S19 42 19 55h26c0-13-10-16-10-23s10-10 10-23z" fill="#fff" ${st()}/><path d="M24 50c2-6 6-8 8-9 2 1 6 3 8 9z" fill="${Y}"/><path d="M25 16h14c-1 4-4 6-7 8-3-2-6-4-7-8z" fill="${Y}"/><path d="M32 32v8" stroke="${O}" stroke-width="2" stroke-dasharray="2 3"/>`),
 coin:sv(`<ellipse cx="26" cy="46" rx="16" ry="6" fill="${Y}" ${st()}/><path d="M10 40v6c0 3 7 6 16 6s16-3 16-6v-6" fill="${Y}" ${st()}/><ellipse cx="26" cy="40" rx="16" ry="6" fill="#F8D877" ${st()}/><circle cx="42" cy="24" r="15" fill="${Y}" ${st()}/><circle cx="42" cy="24" r="10" fill="none" stroke="#C7962A" stroke-width="2"/><path d="M45 18.5c-1-1.3-2.4-2-4-2-2.2 0-3.8 1.2-3.8 3 0 4.4 8 2.6 8 7 0 1.8-1.7 3.1-4 3.1-1.8 0-3.4-.8-4.3-2.2M41.2 14.5v19" fill="none" stroke="#8A5E12" stroke-width="2.2" stroke-linecap="round"/>`),
 scale:sv(`<path d="M32 10v42M20 56h24" ${st(3.2)}/><path d="M12 18h40" ${st(3)}/><circle cx="32" cy="10" r="4" fill="${O}" ${st(2)}/><path d="M12 18L5 34h14z M52 18l-7 16h14z" fill="none" ${st(2)}/><path d="M4 34a8 5 0 0 0 16 0z" fill="${B}" ${st(2.2)}/><path d="M44 34a8 5 0 0 0 16 0z" fill="${Y}" ${st(2.2)}/>`),
 shield:sv(`<path d="M32 6l21 8v15c0 14-9 24-21 29C20 53 11 43 11 29V14z" fill="${B}" ${st()}/><path d="M32 12l15 6v11c0 10-6 18-15 22z" fill="#8CC5EA"/><path d="M23 31l7 7 12-14" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>`),
 checklist:sv(`<rect x="10" y="8" width="44" height="50" rx="7" fill="#fff" ${st()}/>`+[18,31,44].map((y,i)=>`<rect x="16" y="${y-4}" width="9" height="9" rx="2.4" fill="${i<2?G:"#fff"}" ${st(2)}/>${i<2?`<path d="M18 ${y+.5}l2 2 3.5-4" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/>`:""}<path d="M30 ${y+.5}h${i==1?14:18}" stroke="${[O,B,"#C9C2AE"][i]}" stroke-width="4" stroke-linecap="round"/>`).join("")),
 grid:sv(`<rect x="7" y="9" width="50" height="46" rx="7" fill="#fff" ${st()}/>`+[0,1,2].map(r=>[0,1,2].map(c=>`<rect x="${12+c*14.5}" y="${15+r*13}" width="11.5" height="10" rx="2.4" fill="${[["#7FC36B",Y,"#7FC36B"],[Y,"#7FC36B","#F08A6A"],["#7FC36B","#F08A6A",Y]][r][c]}"/>`).join("")).join("")),
 cycle:sv(`<path d="M50 30A18 18 0 0 0 18 20" fill="none" stroke="${G}" stroke-width="5" stroke-linecap="round"/><path d="M14 34a18 18 0 0 0 32 10" fill="none" stroke="${O}" stroke-width="5" stroke-linecap="round"/><path d="M12 13l6 8 8-5" fill="none" stroke="${G}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M52 51l-6-8-8 5" fill="none" stroke="${O}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M32 41c-6-3-7-9-2-15 5 4 7 10 2 15z" fill="${LG}" stroke="${G}" stroke-width="2"/>`),
 links:sv(`<rect x="5" y="22" width="26" height="20" rx="10" fill="none" stroke="${G}" stroke-width="5.5"/><rect x="33" y="22" width="26" height="20" rx="10" fill="none" stroke="${O}" stroke-width="5.5"/><path d="M24 32h16" stroke="${K}" stroke-width="5" stroke-linecap="round"/>`),
 bulb:sv(`<path d="M32 6a18 18 0 0 0-10 33c2 2 3 4 3 7h14c0-3 1-5 3-7A18 18 0 0 0 32 6z" fill="${Y}" ${st()}/><path d="M25 50h14M27 56h10" ${st(3)}/><path d="M28 30l4 6 4-6" fill="none" stroke="#B5801B" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 14l4 3M56 14l-4 3M32 1v0" stroke="${O}" stroke-width="3" stroke-linecap="round"/>`),
 medal:sv(`<path d="M20 4h10l6 18h-10zM44 4H34l-6 18h10z" fill="${B}" ${st(2.2)}/><circle cx="32" cy="40" r="17" fill="${Y}" ${st()}/><circle cx="32" cy="40" r="11" fill="#F8D877" stroke="#C7962A" stroke-width="2"/><path d="M32 33l2.2 4.6 5 .6-3.7 3.4 1 5-4.5-2.5-4.5 2.5 1-5-3.7-3.4 5-.6z" fill="${O}"/>`),
 target:sv(`<circle cx="30" cy="34" r="23" fill="#fff" ${st()}/><circle cx="30" cy="34" r="15" fill="${R}" opacity=".9"/><circle cx="30" cy="34" r="8" fill="#fff"/><circle cx="30" cy="34" r="3.5" fill="${R}"/><path d="M30 34L54 10" ${st(3)}/><path d="M48 8l7-2-2 7 5 1-6 6-6-1-1-6z" fill="${G}" ${st(2)}/>`),
 book:sv(`<path d="M32 16C25 10 15 10 6 12v38c9-2 19-2 26 4z" fill="#fff" ${st()}/><path d="M32 16c7-6 17-6 26-4v38c-9-2-19-2-26 4z" fill="${P}" ${st()}/><path d="M32 16v38" ${st(2.4)}/><path d="M12 22c5-1 10-1 14 1M12 30c5-1 10-1 14 1M38 23c5-2 10-2 14-1" stroke="${G}" stroke-width="2.6" stroke-linecap="round"/><path d="M46 30c-4 2-6 6-4 11 5-2 7-6 4-11z" fill="${LG}" stroke="${G}" stroke-width="1.8"/>`),
 ruler:sv(`<rect x="4" y="34" width="56" height="16" rx="3.5" fill="${Y}" ${st()}/>`+[11,18,25,32,39,46,53].map((x,i)=>`<path d="M${x} 34v${i%2?5:9}" stroke="${K}" stroke-width="2" stroke-linecap="round"/>`).join("")+`<path d="M14 26L36 6l6 6-22 20z" fill="#fff" ${st(2.4)}/><path d="M14 26l-3 7 7-3" fill="${O}" ${st(2)}/>`),
 bars:sv(`<path d="M8 54h48" ${st(3)}/><rect x="11" y="28" width="11" height="26" rx="2.5" fill="${G}" ${st(2.2)}/><rect x="27" y="14" width="11" height="40" rx="2.5" fill="${O}" ${st(2.2)}/><rect x="43" y="34" width="11" height="20" rx="2.5" fill="${B}" ${st(2.2)}/>`),
 linechart:sv(`<rect x="6" y="8" width="52" height="48" rx="7" fill="#fff" ${st()}/><path d="M12 40c8-2 9-14 17-12s8 10 16 6 7-12 11-14" fill="none" stroke="${B}" stroke-width="3.4" stroke-linecap="round"/><path d="M12 46c8-1 10-8 17-7s9 5 16 3 8-6 11-7" fill="none" stroke="${O}" stroke-width="2.6" stroke-dasharray="3 4" stroke-linecap="round"/><circle cx="45" cy="34" r="3.5" fill="${R}"/>`),
 layers:sv(`<path d="M6 20c8-5 16 4 26-1s18 3 26-2v8H6z" fill="${LG}" ${st(2.2)}/><path d="M6 25h52v10H6z" fill="#B98552" ${st(2.2)}/><path d="M6 35h52v10H6z" fill="${BR}" ${st(2.2)}/><path d="M6 45h52v10H6z" fill="#6E4A2C" ${st(2.2)}/><circle cx="18" cy="40" r="2" fill="#E6CFA6"/><circle cx="40" cy="50" r="2.2" fill="#C9A27A"/><circle cx="46" cy="30" r="1.8" fill="#E6CFA6"/><path d="M28 19V8M28 12c-4-4-9-3-10 0 4 2 8 2 10 0zM28 10c3-4 8-4 10-1-3 3-7 3-10 1z" fill="${G}" stroke="${G}" stroke-width="1.6" stroke-linecap="round"/>`),
 satellite:sv(`<rect x="26" y="22" width="12" height="18" rx="3" transform="rotate(45 32 31)" fill="#E9EEF3" ${st()}/><path d="M18 10l10 10-8 8L10 18z" fill="${B}" ${st(2.2)}/><path d="M44 34l10 10-8 8-10-10z" fill="${B}" ${st(2.2)}/><path d="M22 44c-2 3-2 8 2 11M14 46c-3 5-1 12 4 15" fill="none" stroke="${O}" stroke-width="2.6" stroke-linecap="round"/>`),
 globe:sv(`<circle cx="32" cy="32" r="24" fill="${B}" ${st()}/><path d="M16 20c5 1 7 6 12 6s4 7 0 10-2 9-6 12c-4-4-8-11-8-18 0-4 1-7 2-10zM40 12c3 4 0 7 4 10s9 2 10 7c-2 9-9 17-16 19 1-6 5-8 4-13-1-4-7-4-6-10 1-5 2-9 4-13z" fill="${LG}" stroke="${G}" stroke-width="1.8"/><circle cx="32" cy="32" r="24" fill="none" ${st()}/>`),
 chip:sv(`<rect x="14" y="14" width="36" height="36" rx="8" fill="#E9E3F7" ${st()}/><rect x="22" y="22" width="20" height="20" rx="4" fill="#8E6CC9"/><path d="M27 32h10M32 27v10" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>`+[22,32,42].map(v=>`<path d="M${v} 14V7M${v} 50v7M14 ${v}H7M50 ${v}h7" ${st(2.6)}/>`).join("")),
 clipboard:sv(`<rect x="10" y="10" width="44" height="48" rx="7" fill="#fff" ${st()}/><rect x="22" y="5" width="20" height="11" rx="4" fill="${O}" ${st(2.2)}/><path d="M19 28h26M19 37h26M19 46h16" stroke="#C9C2AE" stroke-width="3.4" stroke-linecap="round"/><path d="M38 44l4 4 9-10" fill="none" stroke="${G}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>`),
 folder:sv(`<path d="M6 18a5 5 0 0 1 5-5h14l5 6h23a5 5 0 0 1 5 5v26a5 5 0 0 1-5 5H11a5 5 0 0 1-5-5z" fill="${Y}" ${st()}/><path d="M6 26h52" ${st(2.2)}/><path d="M24 38c3-6 13-6 16 0" fill="none" stroke="${G}" stroke-width="3" stroke-linecap="round"/><circle cx="32" cy="43" r="3" fill="${G}"/>`),
 sparkle:sv(`<path d="M28 6c2 12 6 16 18 18-12 2-16 6-18 18-2-12-6-16-18-18 12-2 16-6 18-18z" fill="${Y}" ${st(2.2)}/><path d="M48 36c1 6 3 8 9 9-6 1-8 3-9 9-1-6-3-8-9-9 6-1 8-3 9-9z" fill="${O}" ${st(2)}/><circle cx="14" cy="50" r="4" fill="${B}"/>`),
 compass:sv(`<circle cx="32" cy="32" r="24" fill="#fff" ${st()}/><path d="M32 12l6 20-6 20-6-20z" fill="#E9E3D5" ${st(2)}/><path d="M32 12l6 20H26z" fill="${R}" ${st(2)}/><circle cx="32" cy="32" r="3.5" fill="${K}"/><path d="M32 3v4M32 57v4M3 32h4M57 32h4" ${st(2.6)}/>`),
 warn:sv(`<path d="M32 7L59 54H5z" fill="${Y}" ${st()}/><path d="M32 24v14" stroke="${K}" stroke-width="4.4" stroke-linecap="round"/><circle cx="32" cy="46" r="3" fill="${K}"/>`),
 quote:sv(`<rect x="8" y="10" width="48" height="38" rx="9" fill="#fff" ${st()}/><path d="M18 48l-2 10 12-10" fill="#fff" ${st()}/><path d="M20 26h8v8c0 4-2 6-6 7M36 26h8v8c0 4-2 6-6 7" fill="none" stroke="${O}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/>`),
 compare:sv(`<rect x="5" y="12" width="16" height="42" rx="4" fill="#fff" ${st(2.2)}/><rect x="24" y="8" width="16" height="46" rx="4" fill="#FCE3D3" ${st(2.2)}/><rect x="43" y="12" width="16" height="42" rx="4" fill="#DCEEFA" ${st(2.2)}/><path d="M9 22h8M9 30h8M28 18h8M28 26h8M47 22h8M47 30h8" stroke="#9AA59E" stroke-width="2.6" stroke-linecap="round"/><path d="M32 46l3-6h-6zM51 38l3 6h-6z" fill="${O}"/><path d="M51 38l3 6h-6z" fill="${B}"/>`)
 })})();

const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const MON=EN?["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]:["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"];
const GCOL={cereal:"#C79A2E",legume:"#3E9B4F"};
if(window.Chart){const D=Chart.defaults;D.font.family="'Be Vietnam Pro',system-ui,sans-serif";D.color="#4B5A51";D.borderColor="#E7E2D4";D.animation=false;D.plugins.legend.labels.usePointStyle=true;D.plugins.legend.labels.boxWidth=8;D.plugins.legend.labels.boxHeight=8}
const CROPCOL={wheat:"#B98A2E",sorghum:"#B5532F",maize:"#EDB31F",soybean:"#4E9F45",fallow:"#A8A08C"};
const GRPCOL={1:"#E8A21E",2:"#3A8FD0",3:"#9A6B3A",4:"#6C8F3A",5:"#2A8088",6:"#B0477A"};
const CODES=["A1","A2","A3","B1","C1","C2","C3","C4","C5","C6","D1","E1","F1"];
const STEPS=[1,2,3,4,5,9,6],stepNo=n=>STEPS.indexOf(n)+1;
const DEF=()=>({farm:{name:"",lat:null,lon:null,polygon:[],area_ha:null,irrigated:false,soil:{},soil_src:{},slope_pct:null,slope_src:null,seasons:[],season_pick:"auto",prev_crop:"",mode:"next",chain:{start:"",end:"",prep:10,prev:""},econ:{}},
 cfg:{profile:"equal",weights:null,enabled:{},k1:true,k1_tol:7,excluded:[],k3:true,k4:[]},mon:{factors:["A1","A2","A3","B1"],methods:["agro","stat"],margin_pct:5,p_watch:10,p_warn:5,crop:"",channels:["ui"]},layers:{},farmId:null});
const SKEY="fa_state_v09";
let S=DEF(),META=null,SRC=null,CLIM=null,RES=null,MONR=null,CH={},CLIMBUSY=false,RUNNING=false,CUR=0,LASTSTEP=0,SELCELL=null,WHY=null;
try{const raw=localStorage.getItem(SKEY);if(raw){const o=JSON.parse(raw);S=Object.assign(DEF(),o);S.farm=Object.assign(DEF().farm,o.farm||{});S.cfg=Object.assign(DEF().cfg,o.cfg||{});S.mon=Object.assign(DEF().mon,o.mon||{})}}catch(e){}
const save=()=>{try{localStorage.setItem(SKEY,JSON.stringify(S))}catch(e){}};
const esc=s=>String(s==null?"":s).replace(/~/g,"≈").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const f0=x=>x==null?"—":Math.round(x).toLocaleString(EN?"en-US":"vi-VN"),f1=x=>x==null?"—":(+x).toFixed(1).replace(".",DC),f2=x=>x==null?"—":(+x).toFixed(2).replace(".",DC);
const getP=(o,p)=>p.split(".").reduce((a,k)=>a==null?a:a[k],o);
function setP(o,p,v){const ks=p.split(".");let a=o;for(let i=0;i<ks.length-1;i++){if(a[ks[i]]==null||typeof a[ks[i]]!=="object")a[ks[i]]={};a=a[ks[i]]}a[ks[ks.length-1]]=v}
async function api(url,body,opt){const o=body===undefined?{headers:{"X-Lang":LANG}}:{method:"POST",headers:{"Content-Type":"application/json","X-Lang":LANG},body:JSON.stringify(body)};
 const r=await fetch(url,Object.assign(o,opt||{}));let j;try{j=await r.json()}catch(e){throw new Error("Máy chủ trả về lỗi ("+r.status+")")}
 if(!j.ok&&j.ok!==undefined)throw new Error(j.error||"Lỗi");return j}
async function apiT(url,body,ms){const ac=new AbortController();const t=setTimeout(()=>ac.abort(),ms);try{return await api(url,body,{signal:ac.signal})}catch(e){if(e.name==="AbortError")throw new Error("AI trả lời quá lâu — bạn có thể đọc phần giải thích có sẵn ở trên.");throw e}finally{clearTimeout(t)}}
const show=(id,msg)=>{const e=$(id);if(!e)return;e.textContent=msg||"";e.classList.toggle("show",!!msg)};
const spin=(id,on)=>{const e=$(id);if(e)e.classList.toggle("show",on)};
function mk(id,cfg){cfg=_trChart(cfg);const c=$("#"+id);if(!c)return;if(typeof Chart==="undefined"){c.parentElement.innerHTML='<div class="fine">Không tải được Chart.js (cần mạng) — biểu đồ tạm ẩn.</div>';return}
 if(CH[id]){try{CH[id].destroy()}catch(e){}delete CH[id]}
 try{const ex=Chart.getChart(c);if(ex)ex.destroy()}catch(e){}
 const n=document.createElement("canvas");n.id=id;c.replaceWith(n);const err=n.parentElement.querySelector(".chart-err");if(err)err.remove();
 const opt=Object.assign({},cfg.options||{},{responsive:true,maintainAspectRatio:false,animation:false});
 try{CH[id]=new Chart(n,Object.assign({type:"bar"},cfg,{options:opt}));CH[id].resize();CH[id].update("none");CH[id].render()}
 catch(e){console.error(e);n.insertAdjacentHTML("afterend",'<div class="fine chart-err">Không vẽ được biểu đồ: '+esc(e.message)+'</div>')}}
const cropOf=id=>(META&&META.crops.find(c=>c.id===id))||{};
const critOf=k=>(META&&META.criteria.find(c=>c.code===k))||{};
const cname=id=>id==="fallow"?"Đất nghỉ":(cropOf(id).vi||id);
function toast(msg,kind){kind=kind||"info";const h=$("#toasts");if(!h)return;const t=document.createElement("div");t.className="toast "+kind;t.setAttribute("role","status");
 t.innerHTML=(kind==="ok"?'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>':kind==="err"?'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/></svg>':'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.01"/></svg>')+"<span></span>";
 t.lastChild.textContent=msg;h.appendChild(t);setTimeout(()=>{t.classList.add("out");setTimeout(()=>t.remove(),360)},kind==="err"?4800:2800)}
const pad=n=>String(n).padStart(2,"0");
const dmy=d=>pad(d.getDate())+"/"+pad(d.getMonth()+1)+"/"+d.getFullYear();
const isoD=d=>d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate());
const parseIso=s=>{const [y,m,d]=s.split("-").map(Number);return new Date(y,m-1,d)};
const todayD=()=>{const d=new Date();d.setHours(0,0,0,0);return d};

/* ---------- khung ứng dụng: điều hướng, banner ---------- */
const PG=[
 {k:"Giám sát & kịch bản",s:"Trang chủ của nhà nông",ic:"partly",pal:2,art:2,t:"Thời tiết trên thửa của bạn hôm nay thế nào?",d:"Theo dõi nhiệt độ, mưa, bức xạ và cân bằng nước bằng dữ liệu NASA, nhận cảnh báo sớm và thử các kịch bản cho vụ tới."},
 {k:"Ruộng của tôi",s:"Vị trí & chế độ tưới",ic:"pin",pal:1,art:1,t:"Nắng lên trên cánh đồng của bạn",d:"Chọn đúng điểm ruộng của bạn trên bản đồ và cho biết ruộng có tưới hay không."},
 {k:"Bài toán & mùa vụ",s:"Vụ hoặc chuỗi luân canh",ic:"cal",pal:4,art:4,t:"Bạn cần đề xuất cho vụ tới hay cả chuỗi luân canh?",d:"Chọn bài toán, rồi khai báo các vụ trong năm (vụ tới) hoặc chỉ ngày bắt đầu – kết thúc (chuỗi luân canh), cùng giá bán và năng suất để tính giá trị kinh tế."},
 {k:"Khí hậu",s:"A1 · A2 · A3",ic:"partly",pal:2,art:2,t:"Khí hậu nhiều năm tại ruộng của bạn",d:"Nhiệt độ, lượng mưa năm và bức xạ từ NASA POWER — số liệu nền cho tiêu chí A1, A2, A3."},
 {k:"Đất & địa hình",s:"B1 · C1–C6 · D1 · E1",ic:"layers",pal:3,art:3,t:"Đất khỏe thì mùa sau mới vững",d:"Cân bằng nước, các chỉ số đất, độ dốc và độ che phủ: tự lấy từ SSURGO, SoilGrids, SRTM; thiếu chỗ nào nhập tay chỗ đó."},
 {k:"Tiêu chí",s:"Chọn & cân trọng số",ic:"scale",pal:5,art:5,t:"Điều gì quan trọng với bạn?",d:"Chọn tiêu chí được dùng và trọng số của từng tiêu chí, hoặc bắt đầu từ một bộ ưu tiên có sẵn."},
 {k:"Kết quả",s:"Cây / chuỗi đề xuất",ic:"medal",pal:6,art:6,t:"Trồng gì cho hợp với thửa của bạn?",d:"Điểm phù hợp của từng cây, kết hợp với ma trận luân canh: cây đề xuất cho vụ tới hoặc chuỗi luân canh xếp hạng, kèm cách tính và lý do."},
 {k:"Thư viện cây trồng",s:"Crop Requirement DB",ic:"sprout",pal:7,art:4,t:"Mỗi cây cần gì để sống khỏe?",d:"Cơ sở dữ liệu yêu cầu cây trồng (CRD) mà công cụ đang dùng, có nguồn cho từng con số."},
 {k:"Nguồn, lưu ý & AI",s:"Theo luật cuộc thi",ic:"satellite",pal:8,art:2,t:"Dữ liệu từ đâu, cần lưu ý gì?",d:"Mọi nguồn dữ liệu, tài nguyên, lưu ý của mô hình và khai báo công cụ AI — kèm bản khai để dán vào trang nộp bài."}];
PG[9]={k:"Ma trận luân canh",s:"Độ phủ cặp cây",ic:"cycle",pal:7,art:4,t:"Trồng cây gì sau cây gì thì được mùa?",d:"Hiệu ứng luân canh: % thay đổi năng suất cây sau so với độc canh (Mudare et al. 2025) — dùng làm hệ số M khi kết hợp với điểm phù hợp."};
const nb=(n,ic,sub)=>`<button class="nb" data-t="${n}" data-p="${PG[n].pal}"><span class="ti">${ic}<span class="ok"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></span></span><span><span>${PG[n].k}</span><small>${sub||PG[n].s}</small></span></button>`;
function buildNav(){$("#nav").innerHTML=`<button class="nhome" data-home="1">← Trang chủ · bản đồ giám sát</button><div class="navl">Công cụ ra quyết định vụ tới</div>`+STEPS.map(n=>nb(n,ART.W[PG[n].ic],null).replace(`<span>${PG[n].k}</span>`,`<span>${stepNo(n)}. ${PG[n].k}</span>`)).join("")+
 `<div class="sep"></div>`+nb(7,ART.crop("wheat"),(META?META.crops.length:4)+" cây · có nguồn")+nb(8,ART.W.satellite)}
$("#logoHome").onclick=()=>goTab(0);
$("#nav").onclick=e=>{if(e.target.closest("[data-home]")){goTab(0);return}const b=e.target.closest(".nb");if(b)goTab(+b.dataset.t)};
function updNav(){const sc=seasonCal(),RQ=readiness(),nOK=CODES.filter(k=>RQ[k].st==="ok").length;
 const d={0:!!MONR,1:S.farm.lat!=null,2:!!(sc&&sc.target),3:!!CLIM,4:nOK>=11,5:CODES.some(k=>wOf(k)>0),9:!!RES,6:!!RES};$$("#nav .nb").forEach(b=>b.classList.toggle("done",!!d[+b.dataset.t]));renderDQ(RQ);
 const demo=!!((CLIM&&CLIM.is_demo)||(RES&&RES.is_demo)||(MONR&&MONR.demo));const c=$("#chipDemo");if(c){c.hidden=!demo;c.className="chip "+(demo?"warn":"")}}
function updBadge(){const f=S.farm||{},b=$("#farmBadge");if(!b)return;const ok=f.lat!=null&&f.lat!=="";
 b.innerHTML='<span class="pn"><svg viewBox="0 0 24 24"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.6"/></svg></span><div><b>'+(f.name?esc(f.name):"Chưa chọn ruộng")+"</b><span>"+(ok?(+f.lat).toFixed(3)+"°, "+(+f.lon).toFixed(3)+"° · "+(f.irrigated?"có tưới":"nhờ mưa"):"Bấm để chọn ruộng")+"</span></div>"}
$("#farmBadge").onclick=()=>goTab(1);
function setBanner(n){const p=PG[n];$("#banSt").textContent=n===0?"Trang chủ · Giám sát":STEPS.includes(n)?"Bước "+stepNo(n)+"/7 · "+p.k:"Tra cứu · "+p.k;$("#banT").textContent=p.t;$("#banD").textContent=p.d;
 const a=$("#banArt");a.innerHTML=((ART.BANW&&ART.BANW[p.art])||ART.BAN[p.art]).replace("<svg ",'<svg preserveAspectRatio="xMaxYMid slice" ');a.classList.remove("sw");void a.offsetWidth;a.classList.add("sw")}
function goTab(n){if(STEPS.includes(n))LASTSTEP=n;CUR=n;document.body.classList.toggle("landing",n===0);$$(".page").forEach(e=>e.classList.toggle("on",e.id==="tab"+n));$("#stage").dataset.p=PG[n].pal;$$("#nav .nb").forEach(b=>b.classList.toggle("on",+b.dataset.t===n));
 setBanner(n);$("#stage").classList.remove("compact");$("#pages").scrollTop=0;window.scrollTo(0,0);updBadge();updNav();renderPgSrc();
 if(n===0)enterHome();
 if(n===1){renderIrr();if(MAP)setTimeout(()=>MAP.invalidateSize(),60)}
 if(n===2)renderSeasons();
 if(n===3){ensureClim();if(MONR)setTimeout(drawMonChart,30);else runMonitor()}
 if(n===4)renderSoil();
 if(n===5)renderCrit();
 if(n===6)enterRes();
 if(n===7)renderDB();
 if(n===8)renderSources();
 if(n===9)renderRot()}
$("#pages").addEventListener("scroll",()=>{const t=$("#pages").scrollTop,st=$("#stage");if(t>90)st.classList.add("compact");else if(t<12)st.classList.remove("compact")});
document.addEventListener("click",e=>{const g=e.target.closest("[data-go]");if(g)goTab(+g.dataset.go)});
$("#bDbBack").onclick=()=>goTab(LASTSTEP||0);$("#bSrcBack").onclick=()=>goTab(LASTSTEP||0);

/* ---------- ràng buộc dữ liệu ↔ ô nhập ---------- */
function syncEls(path,except){$$(`[data-path="${path}"]`).forEach(el=>{if(el===except)return;const v=getP(S,path);if(el.type==="checkbox")el.checked=!!v;else el.value=v==null?"":v;if(el.classList.contains("fl")&&typeof fillv==="function")fillv(el)})}
function bindAll(root){$$((root||"")+" [data-path]").forEach(el=>{if(el._b)return;el._b=1;const path=el.dataset.path;syncEls(path);
 const h=()=>{let v;if(el.type==="checkbox")v=el.checked;else if(el.type==="number"||el.type==="range"||el.dataset.num)v=el.value===""?null:+el.value;else v=el.value;
  setP(S,path,v);syncEls(path,el);save();onPath(path)};el.addEventListener("input",h);el.addEventListener("change",h)})}
function onPath(p){
 if(p==="farm.lat"||p==="farm.lon"){if(MARK&&S.farm.lat!=null&&S.farm.lon!=null)MARK.setLatLng([S.farm.lat,S.farm.lon]);CLIM=null;RES=null;updBadge();updNav()}
 if(p==="farm.name")updBadge()}

/* ---------- 1. bản đồ & chế độ tưới ---------- */
let MAP,MARK;
const PIN='<svg class="pin" viewBox="0 0 40 52" width="40" height="52"><path d="M20 50C8 34 3 26 3 18a17 17 0 0 1 34 0c0 8-5 16-17 32z" fill="#E8573E" stroke="#fff" stroke-width="3"/><circle cx="20" cy="18" r="7" fill="#fff"/></svg>';
function initMap(){
 const ro={referrerPolicy:"origin"};
 const esri=L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",Object.assign({maxZoom:18,attribution:"Esri"},ro));
 const osm=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",Object.assign({maxZoom:19,attribution:"© OpenStreetMap"},ro));
 MAP=L.map("map",{layers:[esri],zoomControl:false}).setView([S.farm.lat||38.5,S.farm.lon||-98.3],S.farm.lat?13:6);
 L.control.zoom({position:"topright"}).addTo(MAP);L.control.layers({"Ảnh vệ tinh":esri,"Bản đồ OpenStreetMap":osm},null,{position:"topright"}).addTo(MAP);
 const chain=[[esri,osm],[osm,esri]];chain.forEach(([lay,next])=>{let n=0,ok=0;lay.on("tileload",()=>{ok++});lay.on("tileerror",()=>{n++;if(n===6&&!ok&&MAP.hasLayer(lay)){MAP.removeLayer(lay);next.addTo(MAP);toast("Lớp bản đồ này không tải được, đã chuyển sang lớp khác.")}})});
 MAP.on("click",e=>setLoc(e.latlng.lat,e.latlng.lng));
 if(S.farm.lat!=null)placeMarker()}
function placeMarker(){if(!MAP)return;$("#mHint").classList.add("off");if(MARK)MARK.setLatLng([S.farm.lat,S.farm.lon]);else{MARK=L.marker([S.farm.lat,S.farm.lon],{draggable:true,icon:L.divIcon({html:PIN,className:"",iconSize:[40,52],iconAnchor:[20,50]})}).addTo(MAP);MARK.on("dragend",()=>{const p=MARK.getLatLng();setLoc(p.lat,p.lng,true)})}}
function setLoc(lat,lon,keep){S.farm.lat=+lat.toFixed(5);S.farm.lon=+lon.toFixed(5);CLIM=null;RES=null;MONR=null;placeMarker();if(!keep&&MAP)MAP.panTo([lat,lon]);syncEls("farm.lat");syncEls("farm.lon");save();updBadge();updNav()}
$("#bSearch").onclick=async()=>{const q=$("#q").value.trim();if(!q)return;const box=$("#geoList");box.innerHTML='<div class="geo"><div>Đang tìm…</div></div>';
 try{const r=await api("/api/geocode?q="+encodeURIComponent(q));box.innerHTML='<div class="geo">'+r.results.map((x,i)=>`<div data-g="${i}"><b>${esc(x.name)}</b><br><small>${esc(x.label)}</small></div>`).join("")+"</div>";
  box.onclick=e=>{const d=e.target.closest("[data-g]");if(!d)return;const x=r.results[+d.dataset.g];setLoc(x.lat,x.lon);if(MAP)MAP.setView([x.lat,x.lon],13);box.innerHTML="";toast("Đã chọn "+x.name+". Bấm lên bản đồ nếu muốn chỉnh đúng ruộng.","ok")};
  if(r.results.length===1)box.querySelector("[data-g]").click()}catch(e){box.innerHTML='<div class="geo"><div>'+esc(e.message)+"</div></div>"}};
$("#q").addEventListener("keydown",e=>{if(e.key==="Enter")$("#bSearch").click()});
$("#bGeo").onclick=()=>navigator.geolocation?navigator.geolocation.getCurrentPosition(p=>{setLoc(p.coords.latitude,p.coords.longitude);MAP.setView([p.coords.latitude,p.coords.longitude],14)},()=>toast("Không lấy được vị trí (cần cho phép định vị / HTTPS).")):toast("Trình duyệt không hỗ trợ định vị.");
const IRR_O=[[false,"Không tưới","Nhờ mưa — tính đầy đủ A2 (mưa năm) và B1 (cân bằng nước)"],[true,"Có tưới","Mặc định tưới đủ nhu cầu cây → A2 = 1, B1 = 1 cho mọi cây"]];
function renderIrr(){const el=$("#irrBox");if(!el)return;el.innerHTML='<div class="opts c2">'+IRR_O.map((o,i)=>`<button class="opt ${!!S.farm.irrigated===o[0]?"on":""}" data-irr="${o[0]?1:0}"><div class="im">${ART.OPT.irrig[i?2:0]}</div><b>${o[1]}</b><small>${o[2]}</small></button>`).join("")+"</div>"}
$("#irrBox").addEventListener("click",e=>{const b=e.target.closest("[data-irr]");if(!b)return;S.farm.irrigated=b.dataset.irr==="1";RES=null;save();renderIrr();updBadge();updNav();fieldTarget()});
function payloadState(){return {id:S.farmId,farm:S.farm,cfg:S.cfg,mon:S.mon,layers:S.layers}}
$("#bSave").onclick=async()=>{if(S.farm.lat==null){toast("Hãy chọn vị trí trước.");return}try{const r=await api("/api/farms",payloadState());S.farmId=r.id;save();loadFarms();toast("Đã lưu trang trại","ok")}catch(e){toast(e.message,"err")}};
async function loadFarms(){try{const r=await api("/api/farms");const el=$("#farmList");if(!r.farms.length){el.textContent="Chưa có trang trại nào được lưu.";return}
 el.innerHTML=r.farms.map(f=>`<div class="fr"><span><b>${esc(f.name)}</b><small>${f.area_ha!=null?f2(f.area_ha)+" ha · ":""}${esc((f.saved||"").replace("T"," ").slice(0,16))}</small></span><button class="b ghost sm fit" data-load="${f.id}">Mở</button><button class="b ghost sm fit" style="color:var(--warn)" data-del="${f.id}">Xóa</button></div>`).join("")}catch(e){}}
$("#farmList").onclick=async e=>{const l=e.target.dataset.load,d=e.target.dataset.del;
 if(l){const r=await api("/api/farms/"+l);applyState(r.state);S.farmId=l;save();toast("Đã mở trang trại","ok")}
 if(d&&confirm(_t("Xóa trang trại này?"))){await fetch("/api/farms/"+d,{method:"DELETE"});loadFarms()}};
function applyState(st){const d=DEF();S.farm=Object.assign(d.farm,st.farm||{});S.cfg=Object.assign(d.cfg,st.cfg||{});if(!S.cfg.weights)S.cfg.weights=profW(S.cfg.profile||"equal");S.layers=st.layers||{};S.mon=Object.assign(d.mon,st.mon||{});
 CLIM=null;RES=null;MONR=null;refreshAll();if(S.farm.lat!=null){placeMarker();if(MAP)MAP.setView([S.farm.lat,S.farm.lon],13)}updBadge();updNav()}
const PRE_SRC={depth_cm:"preset",texture:"preset",ph:"preset",drainage:"preset",cec:"preset",base_sat:"preset",oc_pct:"preset",ec:"preset"};
// số minh hoạ (giá & năng suất trung bình Kansas, quy đổi USD/tấn và tấn/ha) — người dùng nên sửa theo thực tế
const ECON_EX={wheat:{price:200,yield:3.4},sorghum:{price:160,yield:5},maize:{price:165,yield:8.2},soybean:{price:365,yield:2.7}};
const PRESETS={
 ke:{farm:{name:"Ví dụ: Đông Kansas (Manhattan)",lat:39.19,lon:-96.58,polygon:[],area_ha:10,econ:ECON_EX,irrigated:false,
   soil:{depth_cm:152,texture:"silt loam",ph:6.3,drainage:"well",cec:20,base_sat:85,oc_pct:1.3,ec:0.3},soil_src:Object.assign({},PRE_SRC),slope_pct:3,slope_src:"preset",
   seasons:[{id:"s1",name:"Vụ hè",crop:"soybean",start_d:15,start_m:5,days:150}],season_pick:"auto",prev_crop:""}},
 kw:{farm:{name:"Ví dụ: Tây Kansas (Garden City)",lat:37.97,lon:-100.87,polygon:[],area_ha:20,econ:ECON_EX,irrigated:false,
   soil:{depth_cm:200,texture:"silt loam",ph:7.8,drainage:"well",cec:18,base_sat:100,oc_pct:0.8,ec:1.0},soil_src:Object.assign({},PRE_SRC),slope_pct:1,slope_src:"preset",
   seasons:[{id:"s1",name:"Vụ lúa mì đông",crop:"wheat",start_d:1,start_m:10,days:260},{id:"s2",name:"Vụ hai sau lúa mì",crop:"sorghum",start_d:20,start_m:6,days:100}],season_pick:"auto",prev_crop:""}}};
function preset(k,go){const p=JSON.parse(JSON.stringify(PRESETS[k])),d=DEF();p.farm.name=_t(p.farm.name);p.farm.seasons.forEach(x=>x.name=_t(x.name));d.cfg.weights=profW("equal");applyState({farm:p.farm,cfg:d.cfg,layers:{}});S.farmId=null;save();toast("Đã nạp ví dụ — số đất là số minh hoạ; ở bước 4 có thể lấy số SSURGO thật.","ok");goTab(go==null?2:go)}
$("#bPreKE").onclick=()=>preset("ke");$("#bPreKW").onclick=()=>preset("kw");
$("#bNext1").onclick=()=>{if(S.farm.lat==null){toast("Bạn chưa chọn ruộng. Bấm lên bản đồ hoặc tìm tên nơi nhé.","err");return}goTab(2)};

/* ---------- 2. mùa vụ ---------- */
const SCOLS=["#2F86CF","#35904A","#E0A21F","#C65A3A","#7A5BC0"];
const doyOf=(d,m)=>{const t=new Date(2001,m-1,Math.min(d,[31,28,31,30,31,30,31,31,30,31,30,31][m-1]));return Math.round((t-new Date(2001,0,1))/864e5)+1};
const mkD=(y,m,d)=>{const t=new Date(y,m-1,d);if(t.getMonth()!==m-1)return new Date(y,m-1,28);return t};
function chainCal(){const c=S.farm.chain||{};if(!c.start||!c.end)return null;const a=parseIso(c.start),b=parseIso(c.end);if(!(b>a))return null;const T=todayD(),days=Math.round((b-a)/864e5)+1;
 const tg={id:"chain",name:"Chuỗi luân canh",start_d:a.getDate(),start_m:a.getMonth()+1,days,crop:"",i:0,cur:null,nxt:[a,new Date(b.getTime()+864e5)]};return {today:T,rows:[],current:[],next:tg,target:tg,chain:true}}
function seasonCal(){if(S.farm.mode==="chain")return chainCal();const L=(S.farm.seasons||[]).filter(s=>s.start_d&&s.start_m&&s.days>=20);if(!L.length)return null;const T=todayD();
 const rows=L.map((s,i)=>{const occ=[T.getFullYear()-1,T.getFullYear(),T.getFullYear()+1].map(y=>{const a=mkD(y,+s.start_m,+s.start_d);return [a,new Date(a.getTime()+s.days*864e5)]});
  return Object.assign({},s,{i,cur:occ.find(([a,b])=>a<=T&&T<b)||null,nxt:occ.find(([a])=>a>T)||null})});
 const cur=rows.filter(r=>r.cur),up=rows.filter(r=>r.nxt).sort((a,b)=>a.nxt[0]-b.nxt[0]);
 return {today:T,rows,current:cur,next:up[0]||null,target:up[0]||null}}
function k1Of(c,tgt){const k=c.K1,s0=doyOf(...k.sow[0]),s1=doyOf(...k.sow[1]),sd=doyOf(+tgt.start_d,+tgt.start_m),tol=+S.cfg.k1_tol||0;
 const span=((s1-s0)%365+365)%365+2*tol,x=((sd-(s0-tol))%365+365)%365,sow=x<=span,dur=+tgt.days>=k.cycle[0];return {sow,dur,pass:(sow&&dur)||S.cfg.k1===false}}
const SCROPS=()=>META.crops.map(c=>[c.id,c.vi]).concat([["fallow","Đất nghỉ"],["","Chưa chọn"]]);
function sRow(s,i){const occ=mkD(todayD().getFullYear(),+s.start_m,+s.start_d),end=new Date(occ.getTime()+(+s.days-1)*864e5);
 return `<div class="scard" data-i="${i}" style="--sc:${SCOLS[i%5]}"><div class="sch"><span class="num">${i+1}</span><input data-f="name" value="${esc(s.name)}" aria-label="Tên vụ" placeholder="Tên vụ"><button class="del" data-del="${i}" aria-label="Xóa vụ" title="Xóa vụ">×</button></div>`+
  `<label>Cây trồng trong vụ</label><div class="scrop">${SCROPS().map(([id,vi])=>`<button data-cr="${id}" class="${(s.crop||"")===id?"on":""}">${id?ART.crop(id):""}${esc(vi)}</button>`).join("")}</div>`+
  `<div class="sdates"><label>Ngày bắt đầu<input type="date" data-f="date" value="${isoD(occ)}"></label><label>Kéo dài<span class="dur"><input type="number" min="20" max="366" data-f="days" value="${s.days}"><i>ngày</i></span></label></div>`+
  `<div class="qd">${[90,120,150,180,270].map(n=>`<button data-qd="${n}" class="${+s.days===n?"on":""}">${n} ngày</button>`).join("")}</div>`+
  `<div class="send">${pad(s.start_d)}/${pad(s.start_m)} → ${pad(end.getDate())}/${pad(end.getMonth()+1)} · lặp lại mỗi năm</div></div>`}
function seasonClock(sc,opt){opt=opt||{};const W=320,cx=160,cy=160,R0=134;const rows=sc?sc.rows:[],n=Math.max(1,rows.length),rw=Math.min(26,(R0-62)/n-5);
 const ang=doy=>(-90+(doy-1)/365*360)*Math.PI/180,pt=(r,a)=>[cx+r*Math.cos(a),cy+r*Math.sin(a)];
 const arc=(ro,ri,d0,len)=>{const a0=ang(d0),a1=ang(d0+Math.min(len,364.5)),[x0,y0]=pt(ro,a0),[x1,y1]=pt(ro,a1),[x2,y2]=pt(ri,a1),[x3,y3]=pt(ri,a0),lg=len>182.5?1:0;
  return `M${x0.toFixed(1)} ${y0.toFixed(1)}A${ro} ${ro} 0 ${lg} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}L${x2.toFixed(1)} ${y2.toFixed(1)}A${ri} ${ri} 0 ${lg} 0 ${x3.toFixed(1)} ${y3.toFixed(1)}Z`};
 let o=`<svg viewBox="0 0 ${W} ${W}" role="img" aria-label="Đồng hồ mùa vụ"><circle cx="${cx}" cy="${cy}" r="${R0+12}" fill="#FBFAF6" stroke="#E7E2D4"/>`;
 for(let m=0;m<12;m++){const d=doyOf(1,m+1),[x1,y1]=pt(R0+12,ang(d)),[x2,y2]=pt(R0-n*(rw+5)+2,ang(d)),[lx,ly]=pt(R0+3,ang(d+15));o+=`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="#E7E2D4"/><text x="${lx.toFixed(1)}" y="${(ly+3.5).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#8A948C" font-family="Be Vietnam Pro,sans-serif">${MON[m]}</text>`}
 rows.forEach((r,i)=>{const ro=R0-6-i*(rw+5),ri=ro-rw,d0=doyOf(+r.start_d,+r.start_m),isT=sc.target&&sc.target.id===r.id;
  o+=`<path d="${arc(ro,ri,d0,+r.days)}" fill="${SCOLS[i%5]}" opacity="${isT?1:.5}" stroke="${isT?"#17251D":"#fff"}" stroke-width="${isT?2.2:1.5}"><title>${esc(r.name)}: ${pad(r.start_d)}/${pad(r.start_m)}, ${r.days} ngày</title></path>`;
  const [mx,my]=pt((ro+ri)/2,ang(d0+Math.min(+r.days,364)/2));if(+r.days>40){const rr=(rw/2+1);o+=r.crop&&ART.C[r.crop]?`<circle cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="${rr.toFixed(1)}" fill="#fff"/><svg x="${(mx-rr+2).toFixed(1)}" y="${(my-rr+2).toFixed(1)}" width="${(2*rr-4).toFixed(1)}" height="${(2*rr-4).toFixed(1)}" viewBox="0 0 48 48">${ART.C[r.crop]}</svg>`:`<circle cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="${(rw/2-1).toFixed(1)}" fill="#fff" opacity=".9"/><text x="${mx.toFixed(1)}" y="${(my+4).toFixed(1)}" text-anchor="middle" font-size="11" font-weight="800" fill="${SCOLS[i%5]}" font-family="Be Vietnam Pro,sans-serif">${i+1}</text>`}});
 const T=sc?sc.today:todayD(),td=Math.round((T-new Date(T.getFullYear(),0,1))/864e5)+1,[nx,ny]=pt(R0+12,ang(td)),[ix,iy]=pt(28,ang(td));
 o+=`<line x1="${ix.toFixed(1)}" y1="${iy.toFixed(1)}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="#C4492A" stroke-width="3" stroke-linecap="round"/><circle cx="${cx}" cy="${cy}" r="6" fill="#C4492A"/>`;
 o+=`<text x="${cx}" y="${cy-16}" text-anchor="middle" font-size="11" fill="#6B776F" font-family="Be Vietnam Pro,sans-serif">${opt.title||"Hôm nay"}</text><text x="${cx}" y="${cy+26}" text-anchor="middle" font-size="17" font-weight="700" fill="#17251D" font-family="Newsreader,serif">${pad(T.getDate())}/${pad(T.getMonth()+1)}</text></svg>`;return o}
function renderSeasons(){if(!META)return;renderMode();const L=S.farm.seasons||[];
 $("#seasonRows").innerHTML=L.map(sRow).join("")+`<button class="scard add" id="bAddSeason2"><span>+</span>Thêm vụ</button>`;renderClock()}
function renderClock(){const sc=seasonCal();$("#seasonClock").innerHTML=seasonClock(sc);
 const it=(r,cls,tg,txt)=>`<div class="it ${cls}"><span class="ci">${r.crop?ART.crop(r.crop):`<span class="dot" style="width:14px;height:14px;border-radius:5px;background:${SCOLS[r.i%5]};display:block"></span>`}</span><div style="flex:1"><b>${esc(r.name)}${r.crop?" · "+esc(cname(r.crop)):""}</b><small>${txt}</small></div><span class="tg">${tg}</span></div>`;
 let h="";if(sc){sc.current.forEach(r=>{const el=Math.round((sc.today-r.cur[0])/864e5);h+=it(r,"","Đang ở vụ này",`${dmy(r.cur[0])} → ${dmy(new Date(r.cur[1]-864e5))} · ngày ${el+1}/${r.days}`)});
  if(!sc.current.length)h+=`<div class="it"><div style="flex:1"><b>Hôm nay không thuộc vụ nào</b><small>Ruộng đang giữa hai vụ (đất trống / nghỉ).</small></div></div>`;
  if(sc.target){const r=sc.target,dd=Math.round((r.nxt[0]-sc.today)/864e5);h+=it(r,"next","Vụ cần quyết định",`Bắt đầu ${dmy(r.nxt[0])} (còn ${dd} ngày) · ${r.days} ngày, đến ${dmy(new Date(r.nxt[1]-864e5))}`)}}
 else h='<div class="fine">Thêm ít nhất một vụ để xem đồng hồ mùa vụ.</div>';
 $("#seasonNow").innerHTML=h;renderK1Prev(sc);renderMoist();updNav()}
function renderK1Prev(sc){const el=$("#k1Prev");if(!el)return;if(!sc||!sc.target){el.innerHTML='<div class="fine">Khai báo ít nhất một vụ để xem cây nào hợp lịch.</div>';return}
 const t=sc.target;$("#k1Sub").textContent=`Vụ “${t.name}” bắt đầu ${pad(t.start_d)}/${pad(t.start_m)}, dài ${t.days} ngày · K1 ${S.cfg.k1===false?"đang TẮT":"đang bật (lệch ±"+(+S.cfg.k1_tol||0)+" ngày)"}`;
 el.innerHTML=META.crops.map(c=>{const k=k1Of(c,t),K=c.K1;return `<div class="k1c ${k.pass?"ok":"no"}"><span class="ci">${ART.crop(c.id)}</span><div><b>${esc(c.vi)}</b><small>Gieo ${K.sow[0][0]}/${K.sow[0][1]}–${K.sow[1][0]}/${K.sow[1][1]} ${k.sow?"✓":"✗"} · chu kỳ ≥ ${K.cycle[0]} ngày ${k.dur?"✓":"✗"}</small></div><span class="ic">${k.pass?"✓":"✗"}</span></div>`}).join("")+
  `<div class="k1c ok"><span class="ci">${ART.crop("fallow")}</span><div><b>Đất nghỉ</b><small>Luôn khả thi</small></div><span class="ic">✓</span></div>`}
function renderMoist(){const el=$("#moistNow");if(!el)return;const m=RES&&RES.moisture_now;el.innerHTML=m?`Ẩm đất tháng ${esc(m.ym)}: ${f2(m.v)} so với TB cùng tháng ${f2(m.ref)} → <b>${m.pct>=0?"ẩm hơn":"khô hơn"} bình thường ${f0(Math.abs(m.pct))}%</b>.`:""}
const sChanged=()=>{RES=null;MONR=null;save()};
$("#seasonRows").addEventListener("input",e=>{const r=e.target.closest(".scard"),f=e.target.dataset.f;if(!r||!f)return;const s=S.farm.seasons[+r.dataset.i];
 if(f==="name")s.name=e.target.value;else if(f==="days")s.days=+e.target.value;else if(f==="date"){if(!e.target.value)return;const d=parseIso(e.target.value);s.start_d=d.getDate();s.start_m=d.getMonth()+1}
 sChanged();if(f==="name"){renderClock();return}clearTimeout(window._sT);window._sT=setTimeout(()=>{const a=document.activeElement,keep=a&&a.dataset&&a.dataset.f;renderSeasons();if(keep==="days"){const x=$(`.scard[data-i="${r.dataset.i}"] [data-f="days"]`);if(x){x.focus();x.setSelectionRange&&0}}},500)});
$("#seasonRows").addEventListener("click",e=>{const d=e.target.closest("[data-del]");if(d){S.farm.seasons.splice(+d.dataset.del,1);sChanged();renderSeasons();return}
 if(e.target.closest("#bAddSeason2")){$("#bAddSeason").click();return}
 const r=e.target.closest(".scard");if(!r)return;const s=S.farm.seasons[+r.dataset.i];
 const q=e.target.closest("[data-qd]");if(q){s.days=+q.dataset.qd;sChanged();renderSeasons();return}
 const c=e.target.closest("[data-cr]");if(c){s.crop=c.dataset.cr;if(!s.name||/^Vụ \d+$/.test(s.name))s.name="Vụ "+(c.dataset.cr?cname(c.dataset.cr).toLowerCase():(+r.dataset.i+1));sChanged();renderSeasons()}});
$("#bAddSeason").onclick=()=>{const L=S.farm.seasons=S.farm.seasons||[];const last=L[L.length-1];let d=15,m=5;if(last){const e=new Date(mkD(2027,+last.start_m,+last.start_d).getTime()+last.days*864e5);d=e.getDate();m=e.getMonth()+1}
 L.push({id:"s"+Date.now().toString(36),name:"Vụ "+(L.length+1),crop:"",start_d:d,start_m:m,days:120});sChanged();renderSeasons()};
$("#bNext2").onclick=()=>{if(!seasonCal()){toast(S.farm.mode==="chain"?"Hãy nhập ngày bắt đầu và ngày kết thúc của chuỗi luân canh.":"Hãy khai báo ít nhất một vụ (ngày bắt đầu + số ngày).","err");return}goTab(3)};

function clStatus(h){$("#climLoad").innerHTML=h;$("#climBox").style.display="none"}
function ensureClim(force){if(S.farm.lat==null){clStatus(`<div class="empty"><div class="em">${ART.W.cloud}</div><h3>Chưa biết ruộng của bạn ở đâu</h3><p>Hãy chọn vị trí trên bản đồ, rồi quay lại đây để xem khí hậu NASA tại ruộng.</p><button class="b big" data-go="1">← Chọn ruộng</button></div>`);return Promise.resolve()}
 if(CLIM&&!force){renderClimate();return Promise.resolve()}
 if(CLIMBUSY)return Promise.resolve();CLIMBUSY=true;
 clStatus(`<div class="card"><div class="ch"><span class="ti">${ART.W.evap}</span><div><h3>Đang lấy dữ liệu NASA cho ruộng của bạn…</h3><small>Nhiều năm số liệu hằng ngày, có thể mất 10–60 giây.</small></div></div><div class="loading"><div class="shimbar"></div><div class="shimbar" style="width:82%"></div><div class="shimbar" style="width:64%"></div></div></div>`);
 spin("#spClim",true);
 return api("/api/climate",{lat:S.farm.lat,lon:S.farm.lon}).then(r=>{CLIM=r.climate;renderClimate();autoAllLayers();if(!soilFetched())autoSoil(true)}).catch(e=>{clStatus(`<div class="empty"><div class="em">${ART.W.storm}</div><h3>Chưa lấy được dữ liệu NASA</h3><p>${esc(e.message)}</p><button class="b big" id="bRetryClim">Thử lại</button></div>`);const b=$("#bRetryClim");if(b)b.onclick=()=>ensureClim(true)}).finally(()=>{CLIMBUSY=false;spin("#spClim",false);updNav()})}
$("#bClim").onclick=()=>ensureClim(true);
function renderClimate(){const c=CLIM;if(!c)return;clStatus("");$("#climBox").style.display="block";updNav();
 $("#climMeta").innerHTML=(c.is_demo?`<span class="chip warn">DEMO — khí hậu MÔ PHỎNG (không phải NASA)</span>`:`<span class="chip g">NASA POWER</span>`)+`<span class="chip">${c.years[0]}–${c.years[1]} (${c.n_years} năm)</span><span class="chip">Kt: ${esc(c.kt_src||"")}</span>`;
 const m=c.monthly,SM=seasonMonths(),tMax=Math.max(...m.map(x=>x.Tx))+3,tMin=Math.min(...m.map(x=>x.Tn))-3;
 const ssn=SM.length?[{type:"bar",label:"Tháng của vụ tới",data:m.map((x,i)=>SM.includes(i+1)?tMax:null),backgroundColor:"rgba(53,144,74,.10)",borderWidth:0,barPercentage:1,categoryPercentage:1,order:9}]:[];
 $("#kA1").innerHTML=`<b>${f1(c.annual_mean.T)}°C</b><small>TB năm</small>`;$("#kA2").innerHTML=`<b>${f0(c.annual_mean.P)}</b><small>mm/năm</small>`;
 const kt=m.filter(x=>x.KT!=null);$("#kA3").innerHTML=`<b>${f2(kt.reduce((a,x)=>a+x.KT,0)/(kt.length||1))}</b><small>Kt TB</small>`;
 mk("cA1",{type:"line",data:{labels:MON,datasets:[{label:"TB cao nhất ngày",data:m.map(x=>x.Tx),borderColor:"rgba(224,69,46,.0)",backgroundColor:"rgba(232,162,30,.18)",fill:"+1",pointRadius:0,order:2},
  {label:"TB thấp nhất ngày",data:m.map(x=>x.Tn),borderColor:"rgba(0,0,0,0)",pointRadius:0,fill:false,order:3},
  {label:"Nhiệt độ TB tháng",data:m.map(x=>x.T),borderColor:"#E0452E",backgroundColor:"#E0452E",borderWidth:3,pointRadius:3,tension:.35,fill:false,order:1}].concat(ssn)},
  options:{plugins:{legend:{labels:{filter:i=>i.text!==_t("TB thấp nhất ngày")}},tooltip:{callbacks:{label:x=>x.dataset.type==="bar"?null:`${x.dataset.label}: ${f1(x.raw)}°C`}}},scales:{y:{min:Math.floor(tMin),max:Math.ceil(tMax),title:{display:true,text:"°C"}}}}});
 const an=c.annual,mean=c.annual_mean.P;
 mk("cA2",{data:{labels:an.map(a=>a.year),datasets:[{type:"bar",label:"Tổng mưa năm",data:an.map(a=>a.P),backgroundColor:an.map(a=>a.P<mean*.8?"#E0A21F":a.P>mean*1.2?"#1F6FB2":"#5AA9E6"),borderRadius:6,order:2},
  {type:"line",label:"Trung bình nhiều năm",data:an.map(()=>mean),borderColor:"#17251D",borderDash:[6,4],borderWidth:2,pointRadius:0,order:1}]},
  options:{plugins:{tooltip:{callbacks:{label:x=>`${x.dataset.label}: ${f0(x.raw)} mm`}}},scales:{y:{beginAtZero:true,title:{display:true,text:"mm/năm"}}}}});
 const th=(v,col,lab)=>({type:"line",label:lab,data:MON.map(()=>v),borderColor:col,borderDash:[5,4],borderWidth:1.6,pointRadius:0,order:1});
 mk("cA3",{data:{labels:MON,datasets:[{type:"bar",label:"Kt TB tháng",data:m.map(x=>x.KT),backgroundColor:m.map((x,i)=>x.KT>=.6?"#E8A21E":x.KT>=.5?"#F2CF6B":x.KT>=.35?"#B9C3CC":"#8E9AA6"),borderColor:m.map((x,i)=>SM.includes(i+1)?"#35904A":"transparent"),borderWidth:2.5,borderRadius:7,order:2},
  th(.6,"#C77D0A","Rất sáng ≥ 0,60"),th(.5,"#9A7B2E","Trời quang ≥ 0,50"),th(.35,"#7A8590","Nhiều mây ≥ 0,35")]},
  options:{plugins:{tooltip:{callbacks:{label:x=>`${x.dataset.label}: ${f2(x.raw)}`}}},scales:{y:{min:0,max:.8,title:{display:true,text:"Kt (0–1)"}}}}});
 renderLayers()}
/* ---------- v0.6: tự lấy dữ liệu theo vị trí (chạy nền ở máy chủ, có đệm) ---------- */
var AUTO_LAYERS=["ndvi","lst","gpm"],JOBS={};
var nearHere=o=>!!(o&&o.lat!=null&&S.farm.lat!=null&&Math.abs(o.lat-S.farm.lat)<0.002&&Math.abs(o.lon-S.farm.lon)<0.002);
async function autoJob(kind){let r=await api("/api/auto/start",{kind,lat:S.farm.lat,lon:S.farm.lon});
 while(r.status==="running"){if(kind in JOBS&&AUTO_LAYERS.includes(kind)){JOBS[kind]="đang tải "+(r.elapsed_s||0)+" giây…";renderLayers()}await new Promise(s=>setTimeout(s,3000));r=await api("/api/auto/job/"+encodeURIComponent(r.job))}
 if(r.status==="error")throw new Error(r.error);return r.result}
async function autoLayer(kind,quiet){if(S.farm.lat==null||(kind in JOBS))return;JOBS[kind]="đang gửi…";S.autoErr=S.autoErr||{};delete S.autoErr[kind];renderLayers();
 try{S.layers[kind]=await autoJob(kind);if(!quiet)toast("Đã lấy xong: "+((META&&META.layer_kinds[kind])||kind),"ok");if(RES){RES=null;toast("Có lớp dữ liệu mới — kết quả sẽ được tính lại.","info")}updNav()}
 catch(e){S.autoErr[kind]=e.message;if(!quiet)toast(e.message,"err")}finally{delete JOBS[kind];save();renderLayers()}}
function autoAllLayers(){if(S.farm.lat==null)return;AUTO_LAYERS.forEach(k=>{const l=S.layers[k];if(l&&(!l.auto||nearHere(l)))return;if(l)delete S.layers[k];autoLayer(k,true)})}
function renderLayers(){const K=META?META.layer_kinds:{};$("#layerBox").innerHTML=Object.keys(K).map(k=>{const l=S.layers[k],j=JOBS[k],can=AUTO_LAYERS.includes(k),er=S.autoErr&&S.autoErr[k];
 const tag=l?(l.auto?` <span class="chip">🛰 tự lấy · ${esc((l.source||{}).name||"")}</span>`:` <span class="chip">CSV bạn nạp</span>`):"";
 return `<div style="margin:10px 0"><b>${esc(K[k])}</b> ${l?`<span class="chip g">${l.n_months} tháng · ${l.first}→${l.last}</span>${tag} <button class="b ghost sm" data-rm="${k}">Gỡ</button>`:""}`+
  (can?` <button class="b ghost sm" data-auto="${k}" ${j?"disabled":""}>${j?"⏳ "+esc(j):"🛰 Tự lấy theo vị trí"}</button>`:"")+
  (l&&l.note?`<div class="fine">${esc(l.note)}${l.qa_kept_pct!=null?` Giữ lại ${f0(l.qa_kept_pct)}% quan sát sau lọc mây.`:""}</div>`:"")+
  (er&&!l?`<div class="fine" style="color:#b42318">${esc(er)}</div>`:"")+
  `<div><input type="file" accept=".csv,.txt" data-up="${k}"></div></div>`}).join("")+
 `<div class="fine">Mưa GPM IMERG (cần EARTHDATA_TOKEN), NDVI và nhiệt bề mặt (MODIS) được tự lấy khi bạn mở bước này. Có GPM thì A2, B1 dùng mưa GPM thay cho NASA POWER. SMAP L4 chưa có dịch vụ lấy nhanh → tải CSV độ ẩm vùng rễ (ngày, m³/m³) từ AppEEARS / Earthdata rồi nạp ở trên; có SMAP thì B1 dùng SMAP cho ẩm đất đầu vụ.</div>`}
$("#layerBox").addEventListener("change",async e=>{const k=e.target.dataset.up;if(!k||!e.target.files[0])return;const fd=new FormData();fd.append("kind",k);fd.append("file",e.target.files[0]);
 try{const r=await fetch("/api/layers/parse",{method:"POST",body:fd,headers:{"X-Lang":LANG}});const j=await r.json();if(!j.ok)throw new Error(j.error);S.layers[k]=j.layer;save();renderLayers()}catch(er){toast(er.message,"err")}});
$("#layerBox").addEventListener("click",e=>{const k=e.target.dataset.rm;if(k){delete S.layers[k];save();renderLayers();return}
 const a=e.target.closest("[data-auto]");if(a){if(S.farm.lat==null){toast("Hãy chọn vị trí ruộng trước.","err");return}delete S.layers[a.dataset.auto];autoLayer(a.dataset.auto,false)}});


const fillv=el=>{if(el)el.style.setProperty("--v",((el.value-el.min)/((el.max-el.min)||1)*100)+"%")};
/* tháng thuộc vụ tới (để tô viền trên lịch khí hậu) */
function seasonMonths(){const sc=seasonCal();if(!sc||!sc.target)return[];const a=sc.target.nxt[0],out=new Set();for(let k=0;k<sc.target.days;k+=5){out.add(new Date(a.getTime()+k*864e5).getMonth()+1)}return [...out]}

/* ---------- 4. đất & địa hình ---------- */
var SRC_LAB={ssurgo:"🗺 SSURGO",soilgrids:"🛰 SoilGrids 250 m",srtm:"🛰 SRTM 30 m",farmer:"✍ bạn nhập",preset:"ví dụ mẫu"};
const FIELDS={depth_cm:{c:"C1",lab:"Độ sâu tới tầng cản",unit:"cm",lim:[0,500],nd:0},texture:{c:"C2",lab:"Cấp cơ giới tầng mặt (USDA)",type:"tex"},ph:{c:"C3",lab:"pH (1:1 trong nước)",lim:[3,10],nd:1},
 drainage:{c:"C4",lab:"Cấp thoát nước",type:"drain"},cec:{c:"C5",lab:"CEC (pH 7)",unit:"cmolc/kg",lim:[0,120],nd:1},
 ec:{c:"C6",lab:"Độ mặn ECe",unit:"dS/m",lim:[0,60],nd:2},slope_pct:{c:"D1",lab:"Độ dốc",unit:"%",lim:[0,100],nd:1,farm:true},
 theta_wp:{c:"B1",lab:"θ điểm héo",unit:"m³/m³",lim:[0,.7],nd:3,hidden:true},theta_fc:{c:"B1",lab:"θ đồng ruộng",unit:"m³/m³",lim:[0,.8],nd:3,hidden:true},theta_sat:{c:"B1",lab:"θ bão hòa",unit:"m³/m³",lim:[0,.9],nd:3,hidden:true},
 base_sat:{c:"C5",lab:"Bão hòa bazơ",unit:"%",lim:[0,100],nd:0,hidden:true},oc_pct:{c:"C5",lab:"C hữu cơ",unit:"%",lim:[0,40],nd:2,hidden:true}};
const CARDS=[["C1","depth_cm"],["C2","texture"],["C3","ph"],["C4","drainage"],["C5","cec"],["C6","ec"],["D1","slope_pct"]];
const inUS=()=>{const a=+S.farm.lat,o=+S.farm.lon;return S.farm.lat!=null&&a>24&&a<50&&o>-125&&o<-66};
var nearHere=o=>!!(o&&o.lat!=null&&S.farm.lat!=null&&Math.abs(o.lat-S.farm.lat)<0.002&&Math.abs(o.lon-S.farm.lon)<0.002);
const AUTOSRC={ssurgo:"ssurgo",soilgrids:"soil",srtm:"slope"};
const autoRes=k=>{const a=(S.autoSoil||{})[k];return nearHere(a)?a:null};
const soilFetched=()=>!!(autoRes("ssurgo")||autoRes("soilgrids")||autoRes("srtm"));
function curVal(k){return FIELDS[k].farm?S.farm[k]:(S.farm.soil||{})[k]}
function curSrc(k){return FIELDS[k].farm?S.farm.slope_src:(S.farm.soil_src||{})[k]}
function setVal(k,v,src){if(FIELDS[k].farm){S.farm[k]=v;S.farm.slope_src=v==null?null:src}else{S.farm.soil=S.farm.soil||{};S.farm.soil_src=S.farm.soil_src||{};if(v==null||v===""){delete S.farm.soil[k];delete S.farm.soil_src[k]}else{S.farm.soil[k]=v;S.farm.soil_src[k]=src}}RES=null}
function autoAlts(k){const out=[];const ss=autoRes("ssurgo"),sg=autoRes("soilgrids"),sr=autoRes("srtm");
 if(ss&&ss.values[k])out.push(["ssurgo",ss.values[k].value,ss.values[k].note]);if(sg&&sg.values[k])out.push(["soilgrids",sg.values[k].value,sg.values[k].note,sg.values[k]]);
 if(k==="slope_pct"&&sr)out.unshift(["srtm",sr.slope_pct,sr.note]);return out}
const fmtV=(k,v)=>v==null||v===""?"—":FIELDS[k].type==="tex"?(META.texture_vi[v]||v):FIELDS[k].type==="drain"?((META.drainage.find(d=>d[0]===v)||[0,v])[1]):String((+v).toFixed(FIELDS[k].nd)).replace(".",DC);
function soilCard(code,k){const F=FIELDS[k],v=curVal(k),src=curSrc(k),has=v!=null&&v!=="",alts=autoAlts(k),cr=critOf(code);
 let input;if(F.type==="tex")input=`<select data-sd="${k}"><option value="">— chọn —</option>${["light","medium","heavy"].map(g=>`<optgroup label="Nhóm ${({light:"nhẹ",medium:"trung bình",heavy:"nặng"})[g]}">${Object.keys(META.texture_group).filter(t=>META.texture_group[t]===g).map(t=>`<option value="${t}" ${v===t?"selected":""}>${esc(META.texture_vi[t])}</option>`).join("")}</optgroup>`).join("")}</select>`;
 else if(F.type==="drain")input=`<select data-sd="${k}"><option value="">— chọn —</option>${META.drainage.map(d=>`<option value="${d[0]}" ${v===d[0]?"selected":""}>${d[1]}</option>`).join("")}</select>`;
 else input=`<input type="text" inputmode="decimal" data-sd="${k}" value="${src==="farmer"&&has?String(v).replace(".",DC):""}" placeholder="nhập số${F.unit?" ("+F.unit+")":""}">`;
 return `<div class="ic2 ${has?"":"miss"}" id="sd-${code}"><div class="ich"><code style="background:${CCOL[code]}">${code}</code><b>${esc(cr.vi||F.lab)}</b></div>`+
  `<div class="icv">${has?fmtV(k,v):"—"}${has&&F.unit?`<small>${F.unit}</small>`:""}</div><div class="ics">${has?`<span class="src ${src==="farmer"?"s-me":"s-sat"}">${SRC_LAB[src]||"bạn nhập"}</span>`:`<span class="src s-def">chưa có số</span>`}${alts.filter(a=>a[0]!==src).map(a=>`<button data-use="${k}" data-src="${a[0]}" title="${esc(a[2]||"")}">Dùng ${SRC_LAB[a[0]]}: ${fmtV(k,a[1])}</button>`).join("")}</div>`+
  `<div class="ici">${input}</div></div>`}
let B1RES=null,B1T=0;
function b1Card(){const cr=critOf("B1");let body;
 if(S.farm.irrigated)body=`<div class="b1r">${META.crops.map(c=>`<div><span>${ART.crop(c.id)}${esc(c.vi)}</span><b>1,00</b></div>`).join("")}</div>`;
 else if(!seasonCal())body=`<div class="fine" style="margin:0">Khai báo vụ ở bước 2 để tính B1 cho vụ tới.</div>`;
 else if(!B1RES)body=`<div class="fine shim" style="margin:0">Đang tính cân bằng nước cho vụ tới…</div>`;
 else if(B1RES.err)body=`<div class="fine" style="margin:0">${esc(B1RES.err)}</div>`;
 else{const cs=B1RES.base.crops;const miss=cs[0].scores.B1.s==null;
  body=miss?`<div class="fine" style="margin:0">${esc(cs[0].scores.B1.miss||"Thiếu dữ liệu")}</div>`:`<div class="b1r">${META.crops.map(c=>{const r=cs.find(x=>x.id===c.id),v=r.scores.B1.s;return `<div><span>${ART.crop(c.id)}${esc(c.vi)}</span><i><u style="width:${v*100}%;background:${hcol(v).replace("84%","45%")}"></u></i><b>${f2(v)}</b></div>`}).join("")}</div>`}
 return `<div class="ic2 wide" id="sd-B1"><div class="ich"><code style="background:${CCOL.B1}">B1</code><b>${esc(cr.vi)}</b><span class="ics" style="margin-left:auto">${S.farm.irrigated?'<span class="src s-me">có tưới → 1</span>':'<span class="src s-sat">tính cho vụ tới · Ya/Ym</span>'}</span></div>${body}</div>`}
function e1Card(){return `<div class="ic2" id="sd-E1"><div class="ich"><code style="background:${CCOL.E1}">E1</code><b>${esc(critOf("E1").vi)}</b></div><div class="e1r">${META.crops.map(c=>`<div><span>${ART.crop(c.id)}${esc(c.vi)}</span><b>C = ${f2(c.E1.c)}</b></div>`).join("")}</div><div class="ics"><span class="src s-sat">Hệ số C (RUSLE) có sẵn trong CRD</span></div></div>`}
function refreshB1(){if(S.farm.irrigated||!seasonCal()||S.farm.lat==null){B1RES=null;return}clearTimeout(B1T);B1T=setTimeout(async()=>{try{B1RES=await api("/api/evaluate",evalPayload())}catch(e){B1RES={err:e.message}}if(CUR===4)renderSoilData()},300)}
function renderSoilData(){const el=$("#soilData");if(!el||!META)return;const f=S.farm,busy=("soil" in JOBS);
 let h=`<div class="ch"><span class="ti">${ART.W.layers}</span><div style="flex:1"><h3>Chỉ số nước, đất & địa hình của thửa</h3><small>${f.lat!=null?"Tại "+(+f.lat).toFixed(3)+", "+(+f.lon).toFixed(3)+" · ":""}Số tự lấy theo vị trí; bạn nhập tay sẽ được ưu tiên.</small></div>`+
  `<button class="b sm" id="bSoilAuto" ${busy?"disabled":""}>${busy?"⏳ Đang lấy…":(soilFetched()?"↻ Lấy lại theo vị trí":"🛰 Lấy số liệu theo vị trí")}</button></div>`;
 const er=S.autoSoilErr||{};const ers=Object.entries(er).filter(([,v])=>v);if(ers.length)h+=`<div class="fine" style="color:#b42318">${ers.map(([k,v])=>`${({ssurgo:"SSURGO",soilgrids:"SoilGrids",srtm:"SRTM"})[k]}: ${esc(v)}`).join("<br>")}</div>`;
 h+=`<div class="igrid">`+b1Card()+CARDS.map(([c,k])=>soilCard(c,k)).join("")+e1Card()+`</div>`;el.innerHTML=h}
function renderSoil(){renderSoilData();if(!B1RES)refreshB1()}
var fieldTarget=()=>{};
$("#soilData").addEventListener("click",e=>{if(e.target.closest("#bSoilAuto")){if(S.farm.lat==null){toast("Hãy chọn vị trí ruộng trước.","err");return}autoSoil(false);return}
 const u=e.target.closest("[data-use]");if(u){const k=u.dataset.use,a=autoAlts(k).find(x=>x[0]===u.dataset.src);if(a){setVal(k,a[1],a[0]);save();B1RES=null;renderSoil();updNav()}}});
$("#soilData").addEventListener("change",e=>{const k=e.target.dataset&&e.target.dataset.sd;if(!k)return;const F=FIELDS[k];let x=String(e.target.value).trim().replace(",",".");
 if(x===""){setVal(k,null)}else if(F.type){setVal(k,x,"farmer")}else{const n=parseFloat(x);if(!isFinite(n)||n<F.lim[0]||n>F.lim[1]){toast(`Hãy nhập một số trong khoảng ${F.lim[0]}–${F.lim[1]}.`,"err");return}setVal(k,n,"farmer")}
 save();B1RES=null;renderSoil();updNav();toast(x===""?"Đã xoá số bạn nhập.":"Đã dùng số bạn nhập.","ok")});
async function autoSoil(quiet){if(S.farm.lat==null||("soil" in JOBS))return;JOBS.soil=1;if(CUR===4)renderSoilData();updNav();
 S.autoSoil=S.autoSoil||{};S.autoSoilErr={};const kinds=[["ssurgo","ssurgo"],["soilgrids","soil"],["srtm","slope"]].filter(k=>k[0]!=="ssurgo"||inUS());
 const R=await Promise.allSettled(kinds.map(k=>autoJob(k[1])));
 R.forEach((r,i)=>{const nm=kinds[i][0];if(r.status==="fulfilled")S.autoSoil[nm]=r.value;else S.autoSoilErr[nm]=r.reason.message});
 let n=0;Object.keys(FIELDS).forEach(k=>{const v=curVal(k),src=curSrc(k);if(v!=null&&v!==""&&src==="farmer")return;const a=autoAlts(k)[0];if(a&&a[1]!=null){setVal(k,a[1],a[0]);n++}});
 delete JOBS.soil;save();B1RES=null;if(CUR===4)renderSoil();updNav();
 if(!quiet)toast(n?`Đã điền ${n} số liệu tự lấy — hãy kiểm tra và sửa nếu khác ruộng của bạn.`:"Chưa lấy được thêm số liệu đất; bạn có thể nhập tay.",n?"ok":"err")}
/* ---------- tình trạng dữ liệu của 12 tiêu chí (thông báo nhỏ) ---------- */
function readiness(){const f=S.farm,s=f.soil||{},has=k=>s[k]!=null&&s[k]!=="",irr=!!f.irrigated,loc=f.lat!=null,us=inUS(),R={};
 const soilAuto=(k,ussOnly)=>loc&&!soilFetched()&&(us||!ussOnly)?"auto":"miss";
 const put=(k,st,txt)=>R[k]={st,txt};
 const climTxt=CLIM?"NASA POWER "+CLIM.years[0]+"–"+CLIM.years[1]:"tự lấy NASA POWER khi mở bước Khí hậu";
 put("A1",CLIM?"ok":loc?"auto":"miss",climTxt);
 put("A2",irr?"ok":CLIM?"ok":loc?"auto":"miss",irr?"Có tưới → A2 = 1":(S.layers.gpm?"GPM IMERG":(CLIM?"NASA POWER (chưa có GPM)":climTxt)));
 put("A3",CLIM?"ok":loc?"auto":"miss",CLIM?(CLIM.kt_src||"NASA POWER"):climTxt);
 if(irr)put("B1","ok","Có tưới → B1 = 1");
 else{const th=!!S.layers.smap||has("theta_sat")||has("texture"),wp=has("theta_wp")||has("texture");
  put("B1",CLIM&&th&&wp?"ok":(!th||!wp)?soilAuto("texture"):loc?"auto":"miss",CLIM&&th&&wp?(S.layers.smap?"SMAP + mưa vụ":"POWER GWETROOT + mưa vụ"):"cần mưa vụ (NASA) + cơ giới đất hoặc θ (SSURGO)")}
 [["C1","depth_cm",true],["C2","texture",false],["C3","ph",false],["C4","drainage",true],["C6","ec",true]].forEach(([c,k,uo])=>put(c,has(k)?"ok":soilAuto(k,uo),has(k)?(SRC_LAB[(f.soil_src||{})[k]]||"bạn nhập"):(uo&&!us?"cần nhập tay (ngoài Mỹ không có nguồn tự động)":"tự lấy từ "+(uo?"SSURGO":"SSURGO/SoilGrids")+" hoặc nhập tay")));
 put("C5",has("cec")?"ok":soilAuto("cec",false),has("cec")?(SRC_LAB[(f.soil_src||{}).cec]||"bạn nhập"):"cần CEC (SSURGO/SoilGrids hoặc nhập tay)");
 const sl=f.slope_pct!=null&&f.slope_pct!=="";put("D1",sl?"ok":loc&&!soilFetched()?"auto":"miss",sl?(SRC_LAB[f.slope_src]||"bạn nhập"):"tự lấy SRTM 30 m hoặc nhập tay");
 put("E1","ok","Hệ số C có sẵn trong CRD");
 {const E=f.econ||{},okE=+f.area_ha>0&&(META?META.crops:[]).every(c=>E[c.id]&&E[c.id].price!=null&&E[c.id].price!==""&&E[c.id].yield!=null&&E[c.id].yield!=="");put("F1",okE?"ok":"miss",okE?"Diện tích, giá & năng suất bạn nhập":"cần diện tích + giá bán + năng suất cơ sở (bước 2)")}
 CODES.forEach(k=>{if(S.cfg.enabled&&S.cfg.enabled[k]===false)R[k].off=true});return R}
let DQOPEN=false,LASTN=-1;
function renderDQ(RQ){const el=$("#dataQ");if(!el||!META)return;RQ=RQ||readiness();const ok=CODES.filter(k=>RQ[k].st==="ok"),miss=CODES.filter(k=>RQ[k].st==="miss"),au=CODES.filter(k=>RQ[k].st==="auto");
 const n=ok.length;if(LASTN>=0&&n===CODES.length&&LASTN<CODES.length)toast("Đủ dữ liệu cho cả "+CODES.length+" tiêu chí.","ok");LASTN=n;
 let msg=n===CODES.length?"Đủ dữ liệu cho cả "+CODES.length+" tiêu chí.":`${au.length?`<b>Tự lấy được:</b> ${au.join(", ")}. `:""}${miss.length?`<b>Cần nhập tay:</b> ${miss.join(", ")}.`:""}`;
 el.innerHTML=`<div class="dq-h"><b>Dữ liệu tiêu chí</b><span class="n ${n===CODES.length?"ok":"warn"}">${n}/${CODES.length} ${n===CODES.length?"✓":""}</span></div><div class="dq-dots">${CODES.map(k=>`<i class="${RQ[k].off?"off":RQ[k].st}" title="${k} ${esc(critOf(k).vi||"")}: ${esc(RQ[k].txt)}">${k}</i>`).join("")}</div>`+
  (n<12||DQOPEN?`<div class="dq-m">${msg}</div>`:"")+(n<12?`<div class="dq-a">${au.length?`<button data-dq="auto">Tự lấy</button>`:""}${miss.length?`<button data-dq="manual">Nhập tay</button>`:""}</div>`:"")}
$("#dataQ").addEventListener("click",e=>{const b=e.target.closest("[data-dq]");const RQ=readiness();
 if(b&&b.dataset.dq==="auto"){e.stopPropagation();if(S.farm.lat==null){goTab(1);return}if(!CLIM)ensureClim();autoSoil(false);toast("Đang tự lấy dữ liệu khí hậu và đất…");return}
 if(b&&b.dataset.dq==="manual"){e.stopPropagation();const k=CODES.find(c=>RQ[c].st==="miss");goTab(k&&k[0]==="A"?3:4);setTimeout(()=>{const t=$("#sd-"+k);if(t){t.scrollIntoView({behavior:"smooth",block:"center"});t.classList.remove("flash");void t.offsetWidth;t.classList.add("flash")}},120);return}
 DQOPEN=!DQOPEN;renderDQ(RQ)});
$("#bNext3").onclick=()=>goTab(4);$("#bNext4").onclick=()=>goTab(5);

/* ---------- 5. tiêu chí & trọng số ---------- */
const CCOL={A1:"#E8A21E",A2:"#F2C14E",A3:"#D98A14",B1:"#3A8FD0",C1:"#7A4E2A",C2:"#9A6B3A",C3:"#B8875A",C4:"#5E7E9A",C5:"#C9A27A",C6:"#8E6C9E",D1:"#6C8F3A",E1:"#2A8088",F1:"#B0477A"};
const profW=pid=>{const w={};const P=META&&META.profiles[pid];CODES.forEach(k=>w[k]=P?Math.round(P.weights[k]*1000)/10:10);return w};
const wOf=k=>S.cfg.enabled&&S.cfg.enabled[k]===false?0:Math.max(0,+((S.cfg.weights||{})[k])||0);
const wNorm=()=>{const t=CODES.reduce((a,k)=>a+wOf(k),0)||1;const o={};CODES.forEach(k=>o[k]=wOf(k)/t);return o};
function renderCrit(){if(!META)return;if(!S.cfg.weights)S.cfg.weights=profW("equal");const RQ=readiness(),W=wNorm();
 $("#profBox").innerHTML=Object.entries(META.profiles).map(([k,p])=>`<button data-pf="${k}" class="${S.cfg.profile===k?"on":""}" title="Nguồn kịch bản: ${esc(p.src)}">${esc(p.name)}<small>${Object.values(p.groups).map(v=>Math.round(v*100)).join(" · ")}</small></button>`).join("")+`<button data-pf="custom" class="${S.cfg.profile==="custom"?"on":""}">Tự chỉnh<small>theo ý bạn</small></button>`;
 let h="";[1,2,3,4,5,6].forEach(g=>{const ks=CODES.filter(k=>critOf(k).g===g),gs=ks.reduce((a,k)=>a+W[k],0);
  h+=`<div class="cgh"><i style="background:${GRPCOL[g]}"></i>${g}. ${esc(META.group_names[g])}</div>`;
  ks.forEach(k=>{const c=critOf(k),on=!(S.cfg.enabled&&S.cfg.enabled[k]===false),st=RQ[k].st;
   h+=`<div class="crow ${on?"":"off"}"><input type="checkbox" data-en="${k}" ${on?"checked":""} aria-label="Dùng tiêu chí ${k}"><code style="background:${CCOL[k]}">${k}</code><div><b>${esc(c.vi)}</b><span class="ds ${st}">${st==="ok"?"đủ dữ liệu":st==="auto"?"tự lấy được":"thiếu dữ liệu"}</span></div><input class="fl" type="range" min="0" max="50" step="0.5" data-w="${k}" value="${(S.cfg.weights||{})[k]||0}" ${on?"":"disabled"} aria-label="Trọng số ${k}"><span class="pv" data-pv="${k}">${Math.round(W[k]*100)}%</span></div>`})});
 $("#critList").innerHTML=h;$$("#critList input.fl").forEach(fillv);
 $("#k1On").checked=S.cfg.k1!==false;$("#k1Tol").value=+S.cfg.k1_tol||0;fillv($("#k1Tol"));$("#k1TolV").textContent="±"+(+S.cfg.k1_tol||0)+" ngày";
 $("#exCrops").innerHTML=META.crops.map(c=>`<button data-ex="${c.id}" class="${(S.cfg.excluded||[]).includes(c.id)?"":"on"}" title="Bấm để loại / dùng lại">${ART.crop(c.id)}${esc(c.vi)}</button>`).join("");
 $("#k3On").checked=S.cfg.k3!==false;renderK4();
 renderWViz();updNav()}
function renderWViz(){const W=wNorm(),RQ=readiness();const used=CODES.filter(k=>W[k]>0);
 $("#wViz").innerHTML=`<div class="wst">${used.map(k=>`<i style="width:${W[k]*100}%;background:${CCOL[k]}" title="${k} ${Math.round(W[k]*100)}%"></i>`).join("")}</div><div class="wl">${used.map(k=>`<div><i style="background:${CCOL[k]}"></i><span>${k} · ${esc(critOf(k).vi)}${RQ[k].st!=="ok"?' <span class="ds miss">thiếu dữ liệu</span>':""}</span><b>${f1(W[k]*100)}%</b></div>`).join("")||'<div class="fine">Chưa chọn tiêu chí nào.</div>'}</div>`}
$("#critList").addEventListener("input",e=>{const r=e.target.dataset.w;if(!r)return;S.cfg.weights[r]=+e.target.value;S.cfg.profile="custom";fillv(e.target);RES=null;save();const W=wNorm();$$("#critList [data-pv]").forEach(p=>p.textContent=Math.round(W[p.dataset.pv]*100)+"%");$$("#profBox button").forEach(b=>b.classList.toggle("on",b.dataset.pf==="custom"));renderWViz()});
$("#critList").addEventListener("change",e=>{const k=e.target.dataset.en;if(!k)return;S.cfg.enabled=S.cfg.enabled||{};S.cfg.enabled[k]=e.target.checked;RES=null;save();renderCrit()});
$("#profBox").onclick=e=>{const b=e.target.closest("[data-pf]");if(!b)return;const k=b.dataset.pf;S.cfg.profile=k;if(k!=="custom"){S.cfg.weights=profW(k);S.cfg.enabled={}}RES=null;save();renderCrit()};
$("#k1On").onchange=e=>{S.cfg.k1=e.target.checked;RES=null;save();renderK1Prev(seasonCal())};
$("#k1Tol").oninput=e=>{S.cfg.k1_tol=+e.target.value;fillv(e.target);$("#k1TolV").textContent="±"+e.target.value+" ngày";RES=null;save()};
$("#exCrops").onclick=e=>{const b=e.target.closest("[data-ex]");if(!b)return;const a=S.cfg.excluded=S.cfg.excluded||[],i=a.indexOf(b.dataset.ex);if(i>=0)a.splice(i,1);else a.push(b.dataset.ex);RES=null;save();renderCrit()};

/* ---------- 6. kết quả ---------- */
const hcol=v=>{const t=Math.max(0,Math.min(1,v));return `hsl(${Math.round(t*125)} 55% ${84-12*t}%)`};
function evalPayload(d){return {farm:S.farm,cfg:{weights:S.cfg.weights,enabled:S.cfg.enabled,k1:S.cfg.k1,k1_tol:S.cfg.k1_tol,excluded:S.cfg.excluded,k3:S.cfg.k3,k4:S.cfg.k4},layers:S.layers,today:isoD(todayD()),deltas:d||{}}}
async function runEval(silent){if(RUNNING)return;show("#errRun","");
 const fail=(m,t)=>{if(silent)return;show("#errRun",m);toast(m,"err");if(t)goTab(t)};
 if(S.farm.lat==null){fail("Bạn chưa chọn ruộng ở đâu. Bấm lên bản đồ hoặc gõ tên nơi nhé.",1);return}
 if(!seasonCal()){fail("Bạn chưa khai báo vụ nào. Chọn một mẫu nhanh hoặc bấm “+ Thêm vụ”.",2);return}
 if(!CODES.some(k=>wOf(k)>0)){fail("Hãy bật ít nhất một tiêu chí có trọng số lớn hơn 0.",5);return}
 RUNNING=true;$("#bRun").disabled=true;spin("#spRun",true);const rb=$("#bRunHere");if(rb)rb.disabled=true;$("#resEmpty").classList.add("running");
 try{RES=await api("/api/evaluate",evalPayload());SELCELL=null;WHY=null;SCW.forEach(w=>w.reset());if(silent){if(CUR===0)SCW[0].render();if(CUR===6)enterRes()}else goTab(6)}
 catch(e){if(!silent){show("#errRun",e.message);toast(e.message,"err")}}
 RUNNING=false;$("#bRun").disabled=false;spin("#spRun",false);if(rb)rb.disabled=false;$("#resEmpty").classList.remove("running");updNav()}
$("#bRun").onclick=()=>runEval();$("#bRunHere").onclick=()=>runEval();
function enterRes(){const has=!!RES;$("#resEmpty").style.display=has?"none":"block";$("#resBox").style.display=has?"block":"none";
 if(!has){if(!RUNNING&&S.farm.lat!=null&&seasonCal())runEval();return}renderRes();SCW[1].render()}
const feasOf=res=>res.crops.filter(r=>r.feasible);
function scoreRing(v,crop,lab){const r=96,C=2*Math.PI*r,p=Math.max(0,Math.min(1,v)),big=lab?Math.round(v*100):Math.round(p*100);return `<svg viewBox="0 0 260 260"><circle cx="130" cy="130" r="${r}" fill="none" stroke="#EFEBDF" stroke-width="22"/><circle cx="130" cy="130" r="${r}" fill="none" stroke="${CROPCOL[crop]||"#35904A"}" stroke-width="22" stroke-linecap="round" stroke-dasharray="${(C*p).toFixed(1)} ${C}" transform="rotate(-90 130 130)"/><svg x="80" y="62" width="100" height="100" viewBox="0 0 48 48">${ART.C[crop]||""}</svg><text x="130" y="192" text-anchor="middle" font-size="34" font-weight="700" fill="#17251D" font-family="Newsreader,serif">${big}</text><text x="130" y="212" text-anchor="middle" font-size="12" fill="#6B776F" font-family="Be Vietnam Pro,sans-serif">${lab||"điểm / 100"}</text></svg>`}
function renderRes(){if(!RES)return;const B=RES.base,F=feasOf(B),top=F[0],t=RES.target,used=CODES.filter(k=>B.weights[k]>0);
 const kp=B.crops.filter(r=>r.k1.pass).length,chips=`<div class="chips2"><span>${ART.W.sprout}${kp}/${B.crops.length} cây hợp lịch gieo (K1)</span><span>${ART.W.rainbow}Tính trên ${used.length}/${CODES.filter(k=>wOf(k)>0).length} tiêu chí được chọn${Object.keys(B.missing).length?` · <a href="#" data-go="${Object.keys(B.missing).includes("F1")&&Object.keys(B.missing).length===1?2:4}" style="color:inherit">thiếu ${Object.keys(B.missing).join(", ")}</a>`:""}</span><span>${ART.W.rain}${B.irrigated?"Có tưới":"Nhờ mưa"}</span></div>`;
 if(RES.mode==="chain"){const C=RES.chain,tc=C.chains[0],cr=tc?tc.items.filter(x=>x.kind==="crop"):[];
  $("#resTop").innerHTML=`<div class="reco"><div><div class="ey">Chuỗi luân canh · ${C.start.split("-").reverse().join("/")} → ${C.end.split("-").reverse().join("/")}${C.prev_vi?" · cây vụ trước của thửa: "+esc(C.prev_vi):""}</div>`+
   (tc?`<h2>Chuỗi nên cân nhắc: ${tc.items.map(x=>esc(x.vi)).join(" → ")}</h2><p>Score(P) = ${f2(tc.score)} trên ${tc.T} vụ cây${tc.G!=null?" · tổng giá trị kinh tế ≈ "+f0(tc.G)+" USD":""}. ${C.n_total>1?"Công cụ xếp hạng "+C.n_total+" chuỗi hợp lệ — xem bảng ngay dưới bảng điểm.":""}</p>`
     :`<h2>Chưa xếp được chuỗi nào</h2><p>Không cây nào gieo và thu kịp trong khoảng thời gian này theo cửa sổ gieo (K1) và các điều kiện K2–K4. Hãy kéo dài khoảng thời gian ở bước 2 hoặc nới K1.</p>`)+
   chips+`</div><div class="ringw">${tc?scoreRing(tc.score,cr[0].id,"Score(P) × 100"):""}</div></div>`;
  renderMatrix();renderRotRes();renderWhy();renderRob();return}
 $("#resTop").innerHTML=`<div class="reco"><div><div class="ey">${esc(t.name)} · ${t.start.split("-").reverse().join("/")} → ${t.end.split("-").reverse().join("/")} (${t.days} ngày)${RES.prev_crop_vi?" · vụ trước: "+esc(RES.prev_crop_vi):""}</div>`+
  (top?`<h2>Vụ tới nên cân nhắc: ${esc(top.vi)}</h2><p>${RES.prev_crop?`V = S × M = ${f2(top.total)} × ${f2(top.M)} = <b>${f2(top.V)}</b> (sau ${esc(RES.prev_crop_vi)}). `:""}${top.good&&top.good.length?esc("Mạnh nhất ở "+top.good.slice(0,2).join("; ")+"."):""} ${F.length>1?esc("Xếp sau: "+F.slice(1).map(r=>r.vi+" "+Math.round(r.V*100)).join(", ")+"."):""}</p>`:`<h2>Chưa cây nào hợp lịch vụ này</h2><p>Mọi cây đều bị loại theo K1–K4. Cân nhắc để <b>đất nghỉ</b>, hoặc chỉnh ngày bắt đầu / độ dài vụ ở bước 2.</p>`)+
  chips+`</div><div class="ringw">${top?scoreRing(top.V,top.id,RES.prev_crop?"V × 100":"điểm / 100"):seasonClock(seasonCal(),{title:"Vụ tới"})}</div></div>`;
 renderMatrix();renderRotRes();renderWhy();renderRob()}
function renderMatrix(){const el0=$("#matrix"),hd=el0.closest(".card").querySelector(".ch h3"),sb=el0.closest(".card").querySelector(".ch small");
 if(RES.mode==="chain"){hd.textContent="Bảng điểm từng bước của chuỗi tốt nhất";sb.textContent="Mỗi bảng là một bước của chuỗi: các phương án có thể chọn lúc đó và vì sao phương án tô đậm được chọn · bấm ô để xem cách tính";renderChainSteps();return}
 hd.textContent="Bảng điểm: cây × tiêu chí (0–1)";sb.textContent="Bấm vào một ô để xem giá trị, ngưỡng và cách tính";el0.className="mx";if(SELCELL&&SELCELL.length!==2)SELCELL=null;
 const B=RES.base,cols=CODES.filter(k=>B.weights[k]>0||(B.missing[k]&&wOf(k)>0));const n=cols.length;
 const el=$("#matrix");el.style.gridTemplateColumns=`minmax(150px,190px) repeat(${n},minmax(48px,1fr)) minmax(150px,200px)`;
 let h=`<div></div>`;[1,2,3,4,5,6].forEach(g=>{const c=cols.filter(k=>critOf(k).g===g).length;if(c)h+=`<div class="gh" style="grid-column:span ${c};background:${GRPCOL[g]}" title="${esc(META.group_names[g])}">${esc(META.group_names[g].split(" –")[0])}</div>`});h+=`<div></div>`;
 h+=`<div></div>`+cols.map(k=>`<div class="h" title="${k} · ${esc(critOf(k).vi)}">${k}<small>${esc(critOf(k).vi)}</small><small>${B.weights[k]>0?Math.round(B.weights[k]*100)+"%":"—"}</small></div>`).join("")+`<div class="h">Tổng (0–1)</div>`;
 B.crops.forEach(r=>{const x=!r.feasible;h+=`<div class="rn">${ART.crop(r.id)}<div>${r.rank?"#"+r.rank+" ":""}${esc(r.vi)}${x?`<br><span class="k">${r.excl==="K2"?"bạn loại (K2)":"loại theo "+r.excl}</span>`:""}</div></div>`;
  cols.forEach(k=>{const s=r.scores[k];h+=s.s==null?`<div class="c na" title="${esc(s.miss||"")}">thiếu</div>`:`<div class="c ${SELCELL&&SELCELL[0]===r.id&&SELCELL[1]===k?"sel":""}" data-cell="${r.id}|${k}" style="background:${hcol(s.s)};${x?"opacity:.45":""}" title="${esc(s.vtxt)}">${f2(s.s)}</div>`});
  h+=`<div class="t" style="${x?"opacity:.45":""}">${f2(r.total)}<span class="bb"><u style="width:${r.total*100}%"></u></span>${RES.mode!=="chain"&&RES.prev_crop&&r.M!==1?`<small class="vm" title="V = S × M">× ${f2(r.M)} → V ${f2(r.V)}</small>`:""}</div>`});
 h+=`<div class="rn">${ART.crop("fallow")}<div>Đất nghỉ</div></div><div class="fal">${esc(RES.fallow.note)}</div>`;
 el.innerHTML=h;if(SELCELL)cellInfo(...SELCELL)}
$("#matrix").addEventListener("click",e=>{const c=e.target.closest("[data-cell]");if(!c)return;SELCELL=c.dataset.cell.split("|");$$("#matrix .c.sel").forEach(x=>x.classList.remove("sel"));c.classList.add("sel");cellInfo(...SELCELL)});
function renderChainSteps(){const C=RES.chain,st=C.steps||[],B=RES.base,cols=CODES.filter(k=>B.weights[k]>0),n=cols.length,el=$("#matrix");
 el.className="chsteps";el.style.gridTemplateColumns="";if(SELCELL&&SELCELL.length!==3)SELCELL=null;
 if(!st.length){el.innerHTML=`<div class="fine">Không có chuỗi hợp lệ nên chưa có bảng điểm từng bước.</div>`;return}
 const top=C.chains[0],dm=x=>x?x.split("-").reverse().join("/"):"—",gcols=`minmax(150px,190px) repeat(${n},minmax(44px,1fr)) minmax(170px,230px)`;
 let h=`<div class="chsum"><span>Chuỗi tốt nhất: ${top.items.map(x=>esc(x.vi)).join(" → ")}</span><b>Score(P) ${f2(top.score)}</b></div>`;
 st.forEach((s,j)=>{const ch=s.options.find(o=>o.id===s.chosen)||{},ok=s.options.filter(o=>o.ok&&o.best!=null).sort((a,b)=>b.best-a.best),alt=ok.find(o=>o.id!==s.chosen);
  const crops=s.options.filter(o=>o.id!=="fallow"&&o.ok&&o.V!=null),vmax=crops.length?Math.max(...crops.map(o=>o.V)):null,why=[];
  if(s.kind==="fallow"){const now=ok.find(o=>o.id!=="fallow");why.push(now?`Để đất nghỉ cho Score(P) tốt nhất khi đi tiếp: ${f2(ch.best)}, cao hơn gieo ngay ${esc(now.vi)} (${f2(now.best)}).`:`Để đất nghỉ cho Score(P) tốt nhất khi đi tiếp: ${f2(ch.best)}.`);
   why.push("Đất nghỉ không có điểm S và không tính vào T, nhưng cây gieo sau đó được nhân hệ số M(đất nghỉ, c) và gieo ở cửa sổ gieo năm sau.")}
  else{if(s.first)why.push("Vụ đầu chuỗi: chưa có cây trước nên M = 1.");if(s.after_fallow)why.push("Cây sau đất nghỉ được gieo ở cửa sổ gieo năm sau; hệ số M lấy ở hàng “Đất nghỉ” của ma trận luân canh.");
   why.push(`${esc(ch.vi)} cho Score(P) tốt nhất khi đi tiếp: ${f2(ch.best)}.`);if(alt)why.push(`Phương án kế tiếp: ${esc(alt.vi)} (${f2(alt.best)}).`);
   if(ch.V!=null&&vmax!=null)why.push(ch.V>=vmax-1e-9?`${esc(ch.vi)} cũng có V = S × M cao nhất ở bước này (${f2(ch.V)}).`:`V = S × M của ${esc(ch.vi)} (${f2(ch.V)}) không cao nhất, nhưng chọn nó mở ra các vụ sau tốt hơn.`)}
  h+=`<section class="chstep"><div class="chsh"><span class="no">${j+1}</span><div style="flex:1"><h4>${s.kind==="fallow"?`Bước ${j+1}: để đất nghỉ`:`Bước ${j+1}: chọn ${esc(ch.vi)}`}</h4><small>${[`Thời điểm quyết định ${dm(s.date)}`,`cây trước: ${s.prev?esc(cname(s.prev)):"không có"}`].concat(s.kind==="fallow"?[]:[`gieo ${dm(s.sow)} → thu hoạch ${dm(s.harvest)}`]).join(" · ")}</small></div></div>`+
   `<p class="chwhy">${why.map(x=>`<span>${x}</span>`).join(" ")}</p><div class="mx" style="grid-template-columns:${gcols}">`;
  h+=`<div></div>`;[1,2,3,4,5,6].forEach(g=>{const c=cols.filter(k=>critOf(k).g===g).length;if(c)h+=`<div class="gh" style="grid-column:span ${c};background:${GRPCOL[g]}" title="${esc(META.group_names[g])}">${esc(META.group_names[g].split(" –")[0])}</div>`});h+=`<div></div>`;
  h+=`<div></div>`+cols.map(k=>`<div class="h" title="${k} · ${esc(critOf(k).vi)}">${k}<small>${esc(critOf(k).vi)}</small><small>${Math.round(B.weights[k]*100)}%</small></div>`).join("")+`<div class="h">S × M = V<small>Score(P) nếu chọn</small></div>`;
  s.options.forEach(o=>{const pick=o.id===s.chosen,x=!o.ok,cls=(pick?" pick":"")+(x?" x":"");
   h+=`<div class="rn${cls}">${ART.crop(o.id)}<div>${esc(o.vi)}${pick?`<br><span class="ok">✓ được chọn</span>`:x?`<br><span class="k" title="${esc(o.why||"")}">loại</span>`:""}${o.sow?`<small>ngày gieo ${dm(o.sow)}</small>`:""}</div></div>`;
   if(o.id==="fallow"||!o.scores){h+=`<div class="fal${cls}" style="grid-column:span ${n}">${esc(o.id==="fallow"?(o.why||"Bỏ một lượt gieo: không tính S; cây sau gieo ở cửa sổ gieo năm sau và nhân hệ số M(đất nghỉ, c)."):(o.why||""))}</div>`}
   else cols.forEach(k=>{const sc=o.scores[k]||{};h+=sc.s==null?`<div class="c na" title="${esc(sc.miss||"")}">thiếu</div>`:`<div class="c${SELCELL&&SELCELL[0]==="s"+j&&SELCELL[1]===o.id&&SELCELL[2]===k?" sel":""}" data-cell="s${j}|${o.id}|${k}" style="background:${hcol(sc.s)};${x?"opacity:.45":""}" title="${esc(sc.vtxt||"")}">${f2(sc.s)}</div>`});
   h+=`<div class="t${cls}">${o.id==="fallow"?`<span class="tb">—</span>`:o.S!=null?`<span class="tb">${f2(o.S)}<span class="bb"><u style="width:${o.S*100}%"></u></span></span><small class="vm">${s.first?"M = 1 (vụ đầu)":`× M ${f2(o.M)}${o.has===false?"*":""}`} → V ${f2(o.V)}</small>`:`<span class="tb">—</span>`}<small class="bp">${o.best!=null?`Score(P) ${f2(o.best)}`:esc(x&&o.scores?(o.why||""):"")}</small></div>`});
  h+=`</div></section>`});
 el.innerHTML=h;if(SELCELL)cellInfo(...SELCELL)}
function cellInfo(cid,k,j){if(j!=null){const st=(RES.chain&&RES.chain.steps||[])[+String(cid).slice(1)];if(!st)return;const o=st.options.find(x=>x.id===k);if(!o||!o.scores||!o.scores[j])return;
  const s=o.scores[j],c=critOf(j),w=RES.base.weights[j]||0;$("#cellInfo").classList.add("on");
  $("#cellInfo").innerHTML=`<b>${esc(o.vi)} · ${j} ${esc(c.vi)}: ${f2(s.s)}</b><br>Giá trị: <b>${esc(s.vtxt)}</b><br>Ngưỡng / quy tắc (CRD): ${esc(s.rule)}<br>Cách tính: <span class="f">${esc(c.how)}</span><br>Nguồn dữ liệu: ${esc(s.src)}<br>Đóng góp vào điểm tổng: trọng số ${f1(w*100)}% × ${f2(s.s)} = <b>${f2(w*s.s)}</b>`;return}
 const r=RES.base.crops.find(x=>x.id===cid);if(!r)return;const s=r.scores[k],c=critOf(k),w=RES.base.weights[k]||0;
 $("#cellInfo").classList.add("on");$("#cellInfo").innerHTML=`<b>${esc(r.vi)} · ${k} ${esc(c.vi)}: ${f2(s.s)}</b><br>Giá trị: <b>${esc(s.vtxt)}</b><br>Ngưỡng / quy tắc (CRD): ${esc(s.rule)}<br>Cách tính: <span class="f">${esc(c.how)}</span><br>Nguồn dữ liệu: ${esc(s.src)}<br>Đóng góp vào điểm tổng: trọng số ${f1(w*100)}% × ${f2(s.s)} = <b>${f2(w*s.s)}</b>`}
function renderWhy(){const B=RES.base,F=feasOf(B);WHY=WHY||(F[0]||B.crops[0]).id;
 $("#whyPick").innerHTML=B.crops.map(r=>`<button data-wy="${r.id}" class="${WHY===r.id?"on":""}">${esc(r.vi)}</button>`).join("");
 const r=B.crops.find(x=>x.id===WHY),w=r.window;
 $("#whyBox").innerHTML=`<h4>${ART.crop(r.id)}${esc(r.vi)} — ${Math.round(r.total*100)}/100${r.rank?" · hạng "+r.rank:""}</h4>`+
  (w?`<div class="fine" style="margin:0 0 6px">Khí hậu tính trên ${w.L} ngày từ ngày bắt đầu vụ (tháng ${w.months.join(", ")}), ${w.n} năm ${w.years[0]}–${w.years[1]}${w.kept.length<w.months.length?" · A1 bỏ tháng ngủ đông, chỉ tính tháng "+w.kept.join(", "):""}.</div>`:"")+
  (r.good.length?`<b>Điểm mạnh</b><ul class="ok">${r.good.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:"")+
  (r.bad.length?`<b>Hạn chế (điểm &lt; 0,5)</b><ul class="bad">${r.bad.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:"")+
  (r.watch.length?`<b>Bị loại / cần lưu ý</b><ul class="bad">${r.watch.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:"")+
  ""}
$("#whyPick").onclick=e=>{const b=e.target.closest("[data-wy]");if(!b)return;WHY=b.dataset.wy;renderWhy()};
function renderRob(){const B=RES.base;$("#robBox").innerHTML=Object.entries(B.robustness).map(([k,v])=>`<div>${v.winner?ART.crop(v.winner):""}<span>${esc(v.name)}</span><b>${v.winner?esc(cname(v.winner)):"—"}</b></div>`).join("")}
/* kịch bản thời tiết — một bộ dùng chung cho trang chủ (h) và trang kết quả (r) */
let SCW=[];
const DIALS=[["dT","ΔA1 Nhiệt độ","°C",-3,4,.5],["dP","ΔA2 Lượng mưa","%",-50,40,5],["dKt","ΔA3 Bức xạ (Kt)","",-.1,.1,.01],["dTheta","ΔB1 Ẩm đất đầu vụ (θ)","m³/m³",-.1,.1,.01]];
const healthWord=h=>h>=.8?"tươi tốt":h>=.55?"hơi héo":h>=.3?"héo":"chết";
function makeScen(p,host){if(!host)return {render(){},reset(){}};const st={scn:null,base:"baseline",t:0};
 host.innerHTML=`<div class="scw"><div class="scene-w"><div class="scene" id="${p}Scene"></div><div class="sclab" id="${p}Lab"></div></div><div class="scd">${DIALS.map(d=>`<div class="dial"><label for="${p}${d[0]}">${d[1]} <b id="${p}${d[0]}v"></b></label><input class="fl" id="${p}${d[0]}" type="range" min="${d[3]}" max="${d[4]}" step="${d[5]}" value="0"></div>`).join("")}</div>`+
  `<div class="row scrow"><span class="fine" style="margin:0">So với:</span><div class="sg"><button data-b="baseline" class="on">Trung bình nhiều năm</button><button data-b="last">Năm gần nhất</button></div><div class="pre" data-pre style="margin:0"><button data-t="1.5" data-p="0">${ART.W.hot}Nóng +1,5°C</button><button data-t="0" data-p="-25">${ART.W.dry}Khô −25%</button><button data-t="1.5" data-p="-25">${ART.W.storm}Nóng & khô</button><button data-t="0" data-p="0" data-z="1">${ART.W.partly}Như cũ</button></div><span class="spin" id="${p}Sp">Đang tính…</span></div><div id="${p}Cmp" class="mt"></div></div>`;
 const g=id=>host.querySelector("#"+p+id),val=()=>({dT:+g("dT").value,dP:+g("dP").value,dKt:+g("dKt").value,dTheta:+g("dTheta").value,base:st.base});
 function ui(){DIALS.forEach(d=>{const e=g(d[0]);fillv(e);const v=+e.value;g(d[0]+"v").textContent=(v>0?"+":"")+(d[0]==="dT"?String(v).replace(".",DC):d[0]==="dP"?v:f2(v))+(d[2]?" "+d[2]:"")});
  const v0=val();if(RES&&RES.mode==="chain"){g("Scene").innerHTML=weatherScene(v0.dT,v0.dP).replace("xMidYMax slice","xMaxYMax slice");const C=st.scn?st.scn.chain:RES.chain,tc=C&&C.chains[0];
   g("Lab").innerHTML=tc?`${tc.items.filter(x=>x.kind==="crop").slice(0,4).map(x=>ART.crop(x.id)).join("")}<span><b>${esc(tc.items.map(x=>x.vi).join(" → "))}</b> · chuỗi tốt nhất ${st.scn?"trong kịch bản":"hiện nay"} · Score ${f2(tc.score)}</span>`:"Không xếp được chuỗi nào";return}
  const R=st.scn||(RES&&RES.base),top=R?feasOf(R)[0]:null,v=val();g("Scene").innerHTML=weatherScene(v.dT,v.dP).replace("xMidYMax slice","xMaxYMax slice");
  g("Lab").innerHTML=top?`${ART.crop(top.id)}<span><b>${esc(top.vi)}</b> hợp nhất ${st.scn?"trong kịch bản":"hiện nay"} · ${Math.round(top.total*100)}/100 · cây ${healthWord(top.total)}</span>`:(RES?"Không cây nào khả thi cho vụ tới":"")}
 function tableChain(){const C0=RES.chain,C1=st.scn&&st.scn.chain,key=c=>c.items.map(x=>x.id+"@"+(x.sow||"")).join("|"),seq=c=>c.items.map(x=>x.kind==="fallow"?`<span class="cq f">${ART.crop("fallow")}nghỉ</span>`:`<span class="cq">${ART.crop(x.id)}${esc(x.vi)}<small>${x.sow.slice(5,7)}/${x.sow.slice(2,4)}</small></span>`).join('<i>→</i>');
  if(!C1){g("Cmp").innerHTML=`<table class="cmpt"><tr><th>#</th><th>Chuỗi luân canh</th><th>Score hiện nay</th><th>Số vụ cây</th></tr>${C0.chains.slice(0,6).map(c=>`<tr><td>#${c.rank}</td><td><div class="cseq">${seq(c)}</div></td><td><b>${f2(c.score)}</b></td><td>${c.T}</td></tr>`).join("")}</table><div class="fine" style="margin-top:6px">Đơn vị so sánh là cả chuỗi luân canh. Kéo một thanh hoặc chọn tình huống để xem chuỗi nào còn tốt nhất.</div>`;return}
  const r0={},s0={};C0.chains.forEach(c=>{r0[key(c)]=c.rank;s0[key(c)]=c.score});const t0=C0.chains[0],t1=C1.chains[0];
  g("Cmp").innerHTML=`<div class="scmsg">${t0&&t1&&key(t0)!==key(t1)?`<b class="dn">Đổi chuỗi đứng đầu:</b> ${esc(t0.items.map(x=>x.vi).join(" → "))} → <b>${esc(t1.items.map(x=>x.vi).join(" → "))}</b>`:t1?`Chuỗi đứng đầu không đổi`:"Không xếp được chuỗi nào"} · so với ${st.scn.deltas.base==="last"?"năm gần nhất":"trung bình nhiều năm"}</div>`+
   `<table class="cmpt"><tr><th>Kịch bản</th><th>Chuỗi luân canh</th><th>Hiện nay</th><th>Kịch bản</th><th>Chênh</th></tr>${C1.chains.slice(0,6).map(c=>{const k=key(c),b=s0[k],d=b==null?null:c.score-b;return `<tr><td>#${c.rank}</td><td><div class="cseq">${seq(c)}</div></td><td>${b==null?"—":f2(b)+" (#"+r0[k]+")"}</td><td><b>${f2(c.score)}</b></td><td class="${d>0.005?"up":d<-0.005?"dn":""}">${d==null?"mới":(d>0.005?"▲ +":d<-0.005?"▼ ":"≈ ")+f2(Math.abs(d))}</td></tr>`}).join("")}</table>`}
 function table(){if(RES.mode==="chain"){tableChain();return}const B=RES.base,Sc=st.scn,rk=r=>r.rank?"#"+r.rank:"loại";
  const ico=id=>ART.crop(id).replace("<svg ",'<svg style="width:22px;height:22px;vertical-align:-6px;margin-right:6px" ');
  if(!Sc){g("Cmp").innerHTML=`<table class="cmpt"><tr><th>Cây</th><th>Điểm hiện nay</th><th>Hạng</th><th>Khí hậu – nước (A1 · A2 · A3 · B1)</th></tr>${B.crops.map(r=>`<tr><td>${ico(r.id)}<b>${esc(r.vi)}</b></td><td><b>${Math.round(r.total*100)}</b></td><td>${rk(r)}</td><td>${["A1","A2","A3","B1"].map(k=>r.scores[k].s==null?"—":f2(r.scores[k].s)).join(" · ")}</td></tr>`).join("")}</table><div class="fine" style="margin-top:6px">Kéo một thanh hoặc chọn tình huống để so sánh.</div>`;return}
  const rows=Sc.crops.map(s=>{const b=B.crops.find(x=>x.id===s.id),d=s.total-b.total;
   return `<tr><td>${ico(s.id)}<b>${esc(s.vi)}</b></td><td>${Math.round(b.total*100)} (${rk(b)})</td><td><b>${Math.round(s.total*100)}</b> (${rk(s)})</td><td class="${d>0.005?"up":d<-0.005?"dn":""}">${d>0.005?"▲ +":d<-0.005?"▼ ":"≈ "}${Math.round(d*100)}</td><td>${["A1","A2","A3","B1"].map(k=>s.scores[k].s==null?"":`${k} ${f2(b.scores[k].s)}→${f2(s.scores[k].s)}`).filter(Boolean).join(" · ")}</td></tr>`}).join("");
  const top=feasOf(Sc)[0],top0=feasOf(B)[0];
  g("Cmp").innerHTML=`<div class="scmsg">${top&&top0&&top.id!==top0.id?`<b class="dn">Đổi cây đứng đầu:</b> ${esc(top0.vi)} → <b>${esc(top.vi)}</b>`:top?`Cây đứng đầu không đổi: <b>${esc(top.vi)}</b>`:"Không cây nào khả thi"} · so với ${Sc.deltas.base==="last"?"năm gần nhất":"trung bình nhiều năm"}</div><table class="cmpt"><tr><th>Cây</th><th>Hiện nay</th><th>Kịch bản</th><th>Chênh</th><th>Tiêu chí khí hậu – nước thay đổi</th></tr>${rows}</table>`}
 async function run(){if(!RES)return;const d=val();if(!d.dT&&!d.dP&&!d.dKt&&!d.dTheta&&st.base==="baseline"){st.scn=null;ui();table();return}
  g("Sp").classList.add("show");try{const r=await api("/api/evaluate",evalPayload(d));st.scn=r.scen}catch(e){toast(e.message,"err")}g("Sp").classList.remove("show");ui();table()}
 host.addEventListener("input",e=>{if(e.target.matches("input.fl")){ui();clearTimeout(st.t);st.t=setTimeout(run,420)}});
 host.addEventListener("click",e=>{const b=e.target.closest("[data-b]");if(b){st.base=b.dataset.b;host.querySelectorAll("[data-b]").forEach(x=>x.classList.toggle("on",x===b));run();return}
  const q=e.target.closest("[data-pre] button");if(q){g("dT").value=q.dataset.t;g("dP").value=q.dataset.p;if(q.dataset.z){g("dKt").value=0;g("dTheta").value=0}ui();run()}});
 return {render(){ui();if(RES)table();else g("Cmp").innerHTML=""},reset(){DIALS.forEach(d=>g(d[0]).value=0);st.scn=null;st.base="baseline";host.querySelectorAll("[data-b]").forEach(x=>x.classList.toggle("on",x.dataset.b==="baseline"))}}}

/* ---------- 7. thư viện cây trồng (CRD) ---------- */
let DBK="C3";
const sref=a=>(a||[]).map(k=>`<a class="sref" href="#src-${k}" title="${esc((META.crd_sources[k]||[k])[0])}">${k}</a>`).join("");
const ddm=a=>a[0]+"/"+a[1];
function annRain(){return CLIM?CLIM.annual_mean.P:null}
const RANGES={
 A1:{lab:"Nhiệt độ trong vụ (°C)",mn:0,mx:50,band:c=>[[c.A1.tol[0],c.A1.tol[1],"tol"],[c.A1.opt[0],c.A1.opt[1],"opt"]],me:()=>null,ticks:[0,10,20,30,40,50]},
 A2:{lab:"Mưa năm (mm)",mn:0,mx:2000,band:c=>[[c.A2.tol[0],c.A2.tol[1],"tol"],[c.A2.opt[0],c.A2.opt[1],"opt"]],me:()=>annRain(),meL:"mưa năm ở ruộng",ticks:[0,500,1000,1500,2000]},
 B1:{lab:"Nhu cầu nước cả vụ ETm (mm)",mn:300,mx:900,band:c=>[[c.B1.etm[0],c.B1.etm[1],"opt"]],me:()=>null,ticks:[300,450,600,750,900]},
 ZR:{lab:"Độ sâu rễ hiệu quả Zr (m)",mn:0,mx:2.2,band:c=>[[c.ZR.range[0],c.ZR.range[1],"opt"]],me:()=>{const d=(S.farm.soil||{}).depth_cm;return d?d/100:null},meL:"độ sâu tầng đất",ticks:[0,.5,1,1.5,2]},
 C1:{lab:"Độ sâu tầng đất (cm)",mn:0,mx:200,band:c=>c.C1.kind==="sys"?[[c.C1.classes[2][0],200,"tol"],[c.C1.classes[0][0],200,"opt"]]:[[c.C1.tol_min,200,"tol"],[c.C1.opt_low,200,"opt"]],me:()=>(S.farm.soil||{}).depth_cm,meL:"thửa của bạn",ticks:[0,50,100,150,200]},
 C3:{lab:"pH",mn:4,mx:9,band:c=>[[c.C3.tol[0],c.C3.tol[1],"tol"],[c.C3.opt[0],c.C3.opt[1],"opt"]],me:()=>(S.farm.soil||{}).ph,meL:"pH thửa",ticks:[4,5,6,7,8,9]},
 C6:{lab:"Độ mặn ECe (dS/m)",mn:0,mx:20,band:c=>[[c.C6.thr,c.C6.zero,"tol"],[0,c.C6.thr,"opt"]],me:()=>(S.farm.soil||{}).ec,meL:"EC thửa",ticks:[0,5,10,15,20]},
 E1:{lab:"Hệ số che phủ C (RUSLE) — thấp là tốt",mn:0,mx:.5,band:c=>[[0,c.E1.c,"opt"]],me:()=>null,ticks:[0,.1,.2,.3,.4,.5]}};
function renderDB(){if(!META)return;const C=META.crops,sc=seasonCal();
 $("#dbCrops").innerHTML=C.map(c=>`<div class="dbc" style="--cc:${CROPCOL[c.id]}"><div class="ci">${ART.crop(c.id)}</div><b>${esc(c.vi)}</b><i>${esc(c.sci)} · ${esc(c.en)}</i><div class="kv"><span>Nhóm</span>${esc(META.groups[c.group]||c.group)} · ${esc(c.family)}<span>Gieo (KS)</span>${ddm(c.K1.sow[0])} – ${ddm(c.K1.sow[1])}<span>Thu (KS)</span>${ddm(c.K1.harvest[0])} – ${ddm(c.K1.harvest[1])}<span>Chu kỳ</span>${c.K1.cycle[0]}–${c.K1.cycle[1]} ngày<span>ETm · Ky</span>${c.B1.etm[0]}–${c.B1.etm[1]} mm · ${String(c.B1.ky).replace(".",DC)}<span>Rễ Zr</span>${String(c.ZR.range[0]).replace(".",DC)}–${String(c.ZR.range[1]).replace(".",DC)} m<span>Hệ số C</span>${String(c.E1.c).replace(".",DC)}${c.E1.assumed?" (giả định)":""}</div></div>`).join("")+
  `<div class="dbc fal" style="--cc:${CROPCOL.fallow}"><div class="ci">${ART.crop("fallow")}</div><b>Đất nghỉ</b><i>Fallow</i><div class="fine">${esc(META.fallow.note)}</div></div>`;
 const P=d=>(d-1)/365*100,band=(a,b,cls)=>{const x0=doyOf(...a),x1=doyOf(...b);return x1>=x0?`<i class="${cls}" style="left:${P(x0)}%;width:${Math.max(.6,P(x1)-P(x0))}%"></i>`:`<i class="${cls}" style="left:${P(x0)}%;width:${100-P(x0)}%"></i><i class="${cls}" style="left:0;width:${P(x1)}%"></i>`};
 const gl=(a,b)=>{const x0=doyOf(...a),x1=doyOf(...b);return x1>=x0?`<i class="g" style="left:${P(x0)}%;width:${P(x1)-P(x0)}%"></i>`:`<i class="g" style="left:${P(x0)}%;width:${100-P(x0)}%"></i><i class="g" style="left:0;width:${P(x1)}%"></i>`};
 let vbox="";if(sc&&sc.target){const t=sc.target,a=doyOf(+t.start_d,+t.start_m),e=a+(+t.days);vbox=e<=366?`<i class="v" style="left:${P(a)}%;width:${P(e)-P(a)}%" title="Vụ tới: ${esc(t.name)}"></i>`:`<i class="v" style="left:${P(a)}%;width:${100-P(a)}%"></i><i class="v" style="left:0;width:${P(e-365)}%"></i>`}
 const T=todayD(),td=Math.round((T-new Date(T.getFullYear(),0,1))/864e5)+1;
 $("#dbCal").innerHTML=`<div></div>`+MON.map(m=>`<div class="mh">${m}</div>`).join("")+C.map(c=>`<div class="nm">${ART.crop(c.id)}${esc(c.vi)}</div><div class="ln">${vbox}${gl(c.K1.sow[1],c.K1.harvest[0])}${band(c.K1.sow[0],c.K1.sow[1],"s")}${band(c.K1.harvest[0],c.K1.harvest[1],"h")}<span class="td" style="left:${P(td)}%"></span></div>`).join("");
 $("#dbPick").innerHTML=Object.entries(RANGES).map(([k,r])=>`<button data-db="${k}" class="${DBK===k?"on":""}">${k==="ZR"?"Rễ":k} · ${esc(r.lab.split(" (")[0])}</button>`).join("");
 renderRange();
 const rows=[["A1 – Nhiệt độ (°C, TB trong vụ)",c=>c.A1.txt+(c.A1.note?". "+c.A1.note:""),c=>c.A1.src],["A2 – Mưa năm (mm)",c=>c.A2.txt,c=>c.A2.src],["A3 – Bức xạ",c=>c.A3.txt,c=>c.A3.src],
  ["B1 – Nhu cầu nước cả vụ ETm (mm) · Ky",c=>c.B1.txt+" · Ky "+String(c.B1.ky).replace(".",DC),c=>c.B1.src],["Độ sâu rễ hiệu quả Zr (m), dùng cho B1",c=>c.ZR.range.join("–").replace(/\./g,DC),c=>c.ZR.src],
  ["C1 – Độ sâu tầng đất",c=>c.C1.txt,c=>c.C1.src],["C2 – Thành phần cơ giới",c=>c.C2.txt,c=>c.C2.src],["C3 – pH",c=>c.C3.txt,c=>c.C3.src],["C4 – Thoát nước, úng",c=>c.C4.txt,c=>c.C4.src],
  ["C5 – Độ phì, CEC",c=>c.C5.txt,c=>c.C5.src],["C6 – Độ mặn ECe (dS/m): bắt đầu giảm / giảm 50% / mất trắng",c=>c.C6.txt,c=>c.C6.src],["D1 – Độ dốc (%)",c=>c.D1.txt,c=>c.D1.src],
  ["E1 – Che phủ đất: hệ số C (RUSLE)",c=>c.E1.txt,c=>c.E1.src],["K1 (loại trừ) – Gieo → thu ở Kansas; chu kỳ sinh trưởng",c=>c.K1.txt,c=>c.K1.src]];
 $("#dbTable").innerHTML=`<tr><th>Tiêu chí</th>${C.map(c=>`<th>${esc(c.vi)}</th>`).join("")}</tr>`+rows.map(r=>`<tr><td>${esc(r[0])}</td>${C.map(c=>`<td>${esc(r[1](c))} ${sref(r[2](c))}</td>`).join("")}</tr>`).join("");
 $("#dbNotes").innerHTML=META.crd_notes.map(x=>`<li>${esc(x)}</li>`).join("");
 $("#dbRules").innerHTML=`<ul>${META.criteria.map(c=>`<li><b>${c.code} ${esc(c.vi)}:</b> ${esc(c.how)} <i>Dữ liệu: ${esc(c.auto)}</i></li>`).join("")}</ul>`+
  `<p><b>A3 – lớp bức xạ từ Kt:</b> ${META.kt_classes.map(x=>`${esc(x[2])}${x[0]>0?" (Kt ≥ "+String(x[0]).replace(".",DC)+")":""}`).join(" · ")}</p>`+
  `<p><b>C2 – nhóm cơ giới:</b> nhẹ: ${Object.keys(META.texture_group).filter(t=>META.texture_group[t]==="light").map(t=>META.texture_vi[t]).join(", ")}; trung bình: ${Object.keys(META.texture_group).filter(t=>META.texture_group[t]==="medium").map(t=>META.texture_vi[t]).join(", ")}; nặng: ${Object.keys(META.texture_group).filter(t=>META.texture_group[t]==="heavy").map(t=>META.texture_vi[t]).join(", ")}.</p>`+
  `<p><b>C4 – cấp thoát nước → điểm (cây ưa cạn):</b> ${META.drainage.map(d=>d[1]+" "+String(d[2]).replace(".",DC)).join(" · ")}.</p><p><b>Giả định:</b></p><ul>${META.assumptions.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
 $("#dbSrc").innerHTML=Object.entries(META.crd_sources).map(([k,v])=>`<li id="src-${k}"><b>[${k}]</b> <a href="${esc(v[1])}" target="_blank" rel="noopener">${esc(v[0])}</a></li>`).join("")}
function renderRange(){const R=RANGES[DBK],p=x=>Math.max(0,Math.min(100,(x-R.mn)/(R.mx-R.mn)*100)),me=R.me();
 $("#dbRange").innerHTML=`<div class="wrap">${me!=null&&me!==""?`<div class="lane"><div class="me" style="left:${p(+me)}%"><span>${esc(R.meL)}: ${String(+(+me).toFixed(2)).replace(".",DC)}</span></div></div>`:""}`+
  META.crops.map(c=>`<div class="r"><b>${ART.crop(c.id)}${esc(c.vi)}</b><div class="t">${R.band(c).map(b=>`<i class="${b[2]}" style="left:${p(b[0])}%;width:${Math.max(.8,p(b[1])-p(b[0]))}%;background:${CROPCOL[c.id]}"></i>`).join("")}</div></div>`).join("")+
  `<div class="ax">${R.ticks.map(t=>`<span style="left:${p(t)}%">${String(t).replace(".",DC)}</span>`).join("")}</div></div><div class="fine">${esc(R.lab)}. ${me==null||me===""?(R.meL?"Chưa có số của ruộng bạn để so.":""):""}</div>`}
$("#dbPick").onclick=e=>{const b=e.target.closest("[data-db]");if(!b)return;DBK=b.dataset.db;$$("#dbPick button").forEach(x=>x.classList.toggle("on",x===b));renderRange()};

$("#bReport").onclick=async()=>{try{const r=await fetch("/api/report",{method:"POST",headers:{"Content-Type":"application/json","X-Lang":LANG},body:JSON.stringify({analysis:RES,farm:S.farm})});const h=_trHtml(await r.text());const w=window.open("","_blank");if(w){w.document.write(h);w.document.close()}else{location.href=URL.createObjectURL(new Blob([h],{type:"text/html"}))}}catch(e){toast(e.message,"err")}};
$("#bCsv").onclick=()=>{if(!RES)return;const B=RES.base,used=CODES.filter(k=>B.weights[k]>0);const lines=[["Hạng","Cây","Khả thi (K1)","Tổng 0-1"].concat(used.map(k=>k+" "+critOf(k).vi)).join(",")].concat(B.crops.map(r=>[r.rank||"",'"'+r.vi+'"',r.feasible?"có":"không",r.total].concat(used.map(k=>r.scores[k].s)).join(",")));
 lines.push("");lines.push(["","Trọng số","",""].concat(used.map(k=>B.weights[k].toFixed(4))).join(","));
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob(["﻿"+lines.map(_t).join("\n")],{type:"text/csv"}));a.download=EN?"farm_adapt_next_season_scores.csv":"farm_adapt_diem_vu_toi.csv";a.click()};

/* ---------- khởi động ---------- */
function refreshAll(){$$("[data-path]").forEach(el=>syncEls(el.dataset.path));renderIrr();renderLayers();if(CLIM)renderClimate();if(CUR===2)renderSeasons();if(CUR===4){renderSoil();fieldTarget()}if(CUR===5)renderCrit();if(CUR===6)enterRes();if(CUR===7)renderDB();if(CUR===8)renderSources();if(CUR===0)enterHome();updNav()}
(async function(){document.body.insertAdjacentHTML("afterbegin",ART.defs);$$("[data-wi]").forEach(e=>e.innerHTML=ART.W[e.dataset.wi]);$$("[data-crops]").forEach(e=>e.innerHTML=e.dataset.crops.split(",").map(c=>ART.crop(c)).join(""));
 try{META=await (await fetch("/api/meta")).json()}catch(e){toast("Không tải được /api/meta","err");return}
 try{SRC=await api("/api/sources");AIDEV=JSON.parse(JSON.stringify(SRC.ai_dev)).map(x=>SRC.ai_dev_custom?x:{tool:_t(x.tool),where:_t(x.where),how:_t(x.how)})}catch(e){}
 if(!S.cfg.weights)S.cfg.weights=profW(S.cfg.profile&&S.cfg.profile!=="custom"?S.cfg.profile:"equal");
 buildNav();bindAll();renderAuthors();SCW=[makeScen("h",$("#homeScen")),makeScen("r",$("#resScen"))];
 try{initMap()}catch(e){$("#map").innerHTML='<div class="note" style="margin:90px 24px">Không tải được bản đồ (cần mạng). Bạn vẫn có thể nhập vĩ độ/kinh độ ở khung bên phải hoặc dùng ví dụ.</div>'}
 renderIrr();renderLayers();loadFarms();updBadge();goTab(0)})();

/* ---------- 8. nguồn dữ liệu & công cụ AI (yêu cầu bắt buộc của cuộc thi) ---------- */
let AIDEV=null;
const SRCORDER=["power","power_img","gpm","smap","ndvi","lst","slope","ssurgo","soil"];
function srcStatus(k){const L=S.layers||{},er=(S.autoErr||{})[k],loc=S.farm.lat!=null;const used=src=>Object.values(S.farm.soil_src||{}).filter(x=>x===src).length+(S.farm.slope_src===src?1:0);
 if(!loc)return["wait","Chưa chọn ruộng"];
 if(k==="power_img")return MONLAY?["on","Đang hiển thị lớp "+MLK+" trên bản đồ giám sát"]:["wait","Hiển thị ở bản đồ giám sát (trang chủ)"];
 if(k==="power")return CLIM?(CLIM.is_demo?["err","Không gọi được NASA POWER — đang dùng khí hậu MÔ PHỎNG (DEMO)"]:["on",`Đang dùng: ${CLIM.years[0]}–${CLIM.years[1]} (${CLIM.n_years} năm) · ${esc(CLIM.kt_src||"")}`]):["wait","Sẽ tự tải khi mở bước 3 – Khí hậu"];
 if(k==="gpm"){if(L.gpm)return["on",`Đang dùng: ${L.gpm.n_months} tháng (${L.gpm.first}→${L.gpm.last}) cho A2, B1`];if(JOBS.gpm)return["wait","Đang tải…"];if(!SRC.earthdata_token)return["err","Chưa có EARTHDATA_TOKEN trong .env → A2, B1 đang dùng mưa NASA POWER"];return er?["err",esc(er)]:["wait","Chưa tải (tự tải ở bước 3)"]}
 if(k==="smap")return L.smap?["on",`Đang dùng: ${L.smap.n_months} tháng cho θ đầu vụ (B1)`]:["wait","Chưa nạp CSV → B1 ước tính θ từ NASA POWER GWETROOT"];
 if(k==="ndvi"||k==="lst")return L[k]?["on",`Đã tải ${L[k].n_months} tháng (tham khảo, không vào điểm)`]:JOBS[k]?["wait","Đang tải…"]:er?["err",esc(er)]:["wait","Chưa tải (tự tải ở bước 3)"];
 const map={slope:"srtm",ssurgo:"ssurgo",soil:"soilgrids"},nm=map[k],a=autoRes(nm),e2=(S.autoSoilErr||{})[nm];
 if(k==="ssurgo"&&!inUS())return["wait","Ruộng ngoài Hoa Kỳ — SSURGO không phủ"];
 if(a){const n=used(nm);return n?["on",`Đang dùng cho ${n} trường số liệu của thửa`]:["wait","Đã lấy, nhưng bạn đang dùng số khác (nhập tay / nguồn khác)"]}
 return e2?["err",esc(e2)]:["wait","Chưa lấy (bấm “Lấy số liệu theo vị trí” ở bước 4)"]}
function srcCard(k,v){const st=srcStatus(k);return `<div class="srcc"><div class="hd"><b>${esc(v.name)}</b><span class="tag ${v.nasa?"nasa":"oth"}">${v.nasa?"NASA":"Khác"}</span></div>`+
 `<div class="kv"><span>Độ phân giải</span>${esc(v.res||"—")}<span>Cách lấy</span>${esc(v.via||"—")}${v.vars?`<span>Biến</span>${esc(v.vars)}`:""}<span>Dùng cho</span><div class="use">${(v.used_for||[]).map(u=>`<i>${esc(u)}</i>`).join("")||"—"}</div></div>`+
 `<div class="st ${st[0]}">${st[1]}</div>${v.cite?`<div class="cite">${esc(v.cite)}<button data-cp="${esc(v.cite)}">Chép</button></div>`:""}</div>`}
async function renderSources(force){const top=$("#srcTop");renderNotes();if(!SRC||force){top.innerHTML='<div class="card"><div class="loading"><div class="shimbar"></div><div class="shimbar" style="width:70%"></div></div></div>';
  try{SRC=await api("/api/sources")}catch(e){top.innerHTML=`<div class="err show">${esc(e.message)}</div>`;return}AIDEV=JSON.parse(JSON.stringify(SRC.ai_dev)).map(x=>SRC.ai_dev_custom?x:{tool:_t(x.tool),where:_t(x.where),how:_t(x.how)})}
 const so=SRC.sources,nasa=SRCORDER.filter(k=>so[k]&&so[k].nasa),oth=SRCORDER.filter(k=>so[k]&&!so[k].nasa),onN=nasa.filter(k=>srcStatus(k)[0]==="on").length,act=SRC.ai_runtime.active;
 top.innerHTML=`<div class="srch"><div class="kp ${onN?"ok":"warn"}"><div class="ic">${ART.W.evap}</div><div><b>${nasa.length}</b><span>nguồn dữ liệu NASA · ${onN} đang dùng cho ruộng này</span></div></div>`+
  `<div class="kp"><div class="ic">${ART.W.sprout}</div><div><b>${oth.length+Object.keys(SRC.crd_sources).length}</b><span>nguồn khác (đất + CRD)</span></div></div>`+
  `<div class="kp"><div class="ic">${ART.W.humid}</div><div><b>0</b><span>Không dùng AI khi chạy — mọi số do Python tính</span></div></div>`+
  `<div class="kp ok"><div class="ic">${ART.W.rainbow}</div><div><b>✓</b><span>Có dùng dữ liệu NASA — điều kiện để xét giải toàn cầu</span></div></div></div>`;
 $("#srcNasa").innerHTML=nasa.map(k=>srcCard(k,so[k])).join("");
 $("#srcOther").innerHTML=oth.map(k=>srcCard(k,so[k])).join("");
 $("#srcCrd").innerHTML=Object.entries(SRC.crd_sources).map(([k,v])=>`<li><b>[${k}]</b> <a href="${esc(v[1])}" target="_blank" rel="noopener">${esc(v[0])}</a></li>`).join("");
 $("#srcRes").innerHTML=SRC.other.map(g=>`<div class="rsg"><h4>${esc(g.group)}</h4>${g.items.map(i=>`<div><span><a href="${esc(i.url)}" target="_blank" rel="noopener"><b>${esc(i.name)}</b></a><small>${esc(i.license)}</small></span><span>${esc(i.use)}</span></div>`).join("")}</div>`).join("")+
  `<div class="rsg"><h4>Hình ảnh</h4><div><span><b>Minh hoạ thời tiết, cây trồng, banner</b><small>SVG vẽ bằng mã trong file</small></span><span>Không dùng ảnh do AI tạo; mã vẽ được viết với hỗ trợ của AI (xem mục Công cụ AI).</span></div>`+
  (SRC.hero_image.found?`<div><span><b>${esc(SRC.hero_image.name)}</b><small>Ảnh trang mở đầu (thư mục static/)</small></span><span>Ảnh của bên thứ ba — nhóm cần xác nhận giấy phép sử dụng trước khi nộp.</span></div>`:"")+`</div>`;
 const R=SRC.ai_runtime;$("#aiRun").innerHTML=`<p class="fine" style="margin:0 0 6px"><b>Ở đâu:</b> ${esc(R.what)}</p><div class="aip">${Object.entries(R.providers_all).map(([k,v])=>`<span class="${act.includes(k)?"on":""}">${esc(v)}${act.includes(k)?" ✓":""}</span>`).join("")}</div><b style="font-size:13px">Như thế nào:</b><ul class="fine" style="margin:4px 0 0 18px;padding:0">${R.how.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`;
 renderAiDev();$("#srcMd").textContent=srcMarkdown()}
function renderAiDev(){$("#aiDev").innerHTML=`<div class="aidh"><span>Công cụ</span><span>Dùng ở đâu</span><span>Dùng như thế nào</span><span></span></div>`+AIDEV.map((x,i)=>`<div class="aid" data-i="${i}"><input data-f="tool" value="${esc(x.tool)}" placeholder="vd: ChatGPT"><textarea data-f="where" placeholder="Phần nào của dự án">${esc(x.where)}</textarea><textarea data-f="how" placeholder="Cách dùng, nhóm kiểm tra lại ra sao">${esc(x.how)}</textarea><button data-rm="${i}" aria-label="Xóa">×</button></div>`).join("");
 $("#aiDevNote").innerHTML=SRC.ai_dev_custom?`Đã lưu ở <code>${esc(SRC.ai_dev_path)}</code>.`:`Đây là khai báo mặc định — nhóm hãy sửa cho đúng thực tế (kể cả AI dùng để viết slide, video, ảnh) rồi bấm <b>Lưu khai báo</b>. Ảnh/video do AI tạo phải có dấu "AI-generated" hiển thị.`}
$("#aiDev").addEventListener("input",e=>{const r=e.target.closest(".aid");if(!r)return;AIDEV[+r.dataset.i][e.target.dataset.f]=e.target.value;$("#srcMd").textContent=srcMarkdown()});
$("#aiDev").addEventListener("click",e=>{const b=e.target.closest("[data-rm]");if(!b)return;AIDEV.splice(+b.dataset.rm,1);renderAiDev();$("#srcMd").textContent=srcMarkdown()});
$("#bAiAdd").onclick=()=>{AIDEV.push({tool:"",where:"",how:""});renderAiDev()};
$("#bAiSave").onclick=async()=>{try{const r=await api("/api/ai_tools",{items:AIDEV});AIDEV=r.items;SRC.ai_dev=r.items;SRC.ai_dev_custom=true;renderAiDev();$("#srcMd").textContent=srcMarkdown();toast("Đã lưu khai báo công cụ AI.","ok")}catch(e){toast(e.message,"err")}};
$("#pages").addEventListener("click",e=>{const b=e.target.closest("[data-cp]");if(!b)return;navigator.clipboard&&navigator.clipboard.writeText(_t(b.dataset.cp)).then(()=>toast("Đã chép trích dẫn.","ok"))});
function srcMarkdown(){if(!SRC)return"";const so=SRC.sources,L=[];const st=k=>srcStatus(k)[1].replace(/<[^>]+>/g,"");
 L.push(`# FARM ADAPT v${SRC.version} — Dữ liệu, tài nguyên và công cụ AI`,"","## Nhóm tác giả");((META&&META.authors)||[]).forEach(a=>L.push(`- **${a.name}**${a.email?` — ${a.email}`:""}`));L.push("","## Dữ liệu NASA");
 SRCORDER.filter(k=>so[k]&&so[k].nasa).forEach(k=>{const v=so[k];L.push(`- **${v.name}** (${v.res}) — dùng cho ${(v.used_for||[]).join(", ")}. Truy cập: ${v.via}.`,`  - Trích dẫn: ${v.cite}`)});
 L.push("","## Dữ liệu khác");SRCORDER.filter(k=>so[k]&&!so[k].nasa).forEach(k=>{const v=so[k];L.push(`- **${v.name}** (${v.res}) — dùng cho ${(v.used_for||[]).join(", ")}. Truy cập: ${v.via}.`,`  - Trích dẫn: ${v.cite}`)});
 L.push("","## Cơ sở dữ liệu yêu cầu cây trồng (CRD)");Object.entries(SRC.crd_sources).forEach(([k,v])=>L.push(`- [${k}] ${v[0]} — ${v[1]}`));
 L.push("","## Tài nguyên, thư viện & phương pháp");SRC.other.forEach(g=>g.items.forEach(i=>L.push(`- ${i.name} (${i.license}) — ${i.use}. ${i.url}`)));
 L.push("- Minh hoạ: SVG vẽ bằng mã trong file; không dùng ảnh do AI tạo.");if(SRC.hero_image.found)L.push(`- Ảnh trang mở đầu: ${SRC.hero_image.name} (bên thứ ba — cần xác nhận giấy phép).`);
 L.push("","## Công cụ AI","### AI bên trong công cụ",`- ${SRC.ai_runtime.what}. Nhà cung cấp hỗ trợ: ${Object.values(SRC.ai_runtime.providers_all).join(", ")}.`);SRC.ai_runtime.how.forEach(x=>L.push(`  - ${x}`));
 L.push("","### AI nhóm dùng khi phát triển");(AIDEV||[]).filter(x=>x.tool).forEach(x=>L.push(`- **${x.tool}** — ở đâu: ${x.where}; như thế nào: ${x.how}`));
 if(S.farm.lat!=null){L.push("","## Trạng thái nguồn với ruộng đang chọn",`(${(+S.farm.lat).toFixed(3)}, ${(+S.farm.lon).toFixed(3)})`);SRCORDER.filter(k=>so[k]).forEach(k=>L.push(`- ${so[k].name}: ${st(k)}`))}
 return L.map(_t).join("\n")}
$("#bSrcCopy").onclick=()=>{const t=srcMarkdown();(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>toast("Đã sao chép bản khai.","ok")).catch(()=>toast("Không sao chép được — hãy bôi đen và chép tay.","err"))};
$("#bSrcMd").onclick=()=>{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([srcMarkdown()],{type:"text/markdown"}));a.download=EN?"farm_adapt_data_sources_and_AI.md":"farm_adapt_nguon_du_lieu_va_AI.md";a.click()};

/* ---------- v0.9 · bài toán (vụ tới / chuỗi luân canh), kinh tế F1, K3–K4, ma trận luân canh ---------- */
const MODES=[["next","Đề xuất cây cho vụ tới","Khai báo các vụ trong năm; công cụ chấm điểm từng cây cho vụ sắp tới và nhân với hiệu ứng luân canh sau cây vụ trước: V = S × M.","sprout"],
 ["chain","Đề xuất một chuỗi luân canh","Chỉ cần ngày bắt đầu và ngày kết thúc; công cụ tự xếp mọi chuỗi cây vừa trong khoảng này và xếp hạng theo Score(P).","cycle"]];
function renderMode(){const m=S.farm.mode==="chain"?"chain":"next";
 $("#modeBox").innerHTML=MODES.map(([k,t,d,ic])=>`<button class="mopt ${m===k?"on":""}" data-mode="${k}"><span class="ti">${ART.W[ic]}</span><span><b>${t}</b><small>${d}</small></span><i>${m===k?"Đang chọn":"Chọn"}</i></button>`).join("");
 $("#modeNext").style.display=m==="next"?"":"none";$("#modeChain").style.display=m==="chain"?"":"none";
 if(m==="chain")renderChainForm();renderEcon()}
$("#modeBox").onclick=e=>{const b=e.target.closest("[data-mode]");if(!b)return;S.farm.mode=b.dataset.mode;
 if(S.farm.mode==="chain"&&!S.farm.chain.start){const T=todayD(),a=new Date(T.getFullYear()+1,2,1),z=new Date(T.getFullYear()+3,10,30);S.farm.chain=Object.assign({prep:10,prev:""},S.farm.chain,{start:isoD(a),end:isoD(z)})}
 RES=null;MONR=null;save();renderMode();renderClock();updNav()};
function renderChainForm(){const c=S.farm.chain||{},opts=[["","Không có / không rõ"]].concat(META.crops.map(x=>[x.id,x.vi]),[["fallow","Đất nghỉ"]]);
 $("#chainForm").innerHTML=`<label>Ngày bắt đầu<input type="date" data-ch="start" value="${esc(c.start||"")}"></label><label>Ngày kết thúc<input type="date" data-ch="end" value="${esc(c.end||"")}"></label>`+
  `<label>Thời gian làm đất giữa 2 cây<span class="dur"><input type="number" min="0" max="90" data-ch="prep" value="${c.prep==null?10:c.prep}"><i>ngày</i></span></label>`+
  `<label>Cây vụ trước của thửa<select data-ch="prev">${opts.map(([v,t])=>`<option value="${v}" ${(c.prev||"")===v?"selected":""}>${esc(t)}</option>`).join("")}</select></label>`;
 renderChainTl()}
function renderChainTl(){const sc=chainCal(),el=$("#chainTl");el.innerHTML=sc?`<div class="fine" style="margin:0">${dmy(sc.target.nxt[0])} → ${dmy(new Date(sc.target.nxt[1]-864e5))} · ${sc.target.days} ngày. Công cụ tự xếp cây theo cửa sổ gieo và thời gian sinh trưởng trong CRD.</div>`:'<div class="fine" style="margin:0">Nhập ngày bắt đầu và ngày kết thúc (ít nhất 90 ngày, tối đa 5 năm).</div>'}
$("#chainForm").addEventListener("change",e=>{const k=e.target.dataset.ch;if(!k)return;S.farm.chain=S.farm.chain||{};S.farm.chain[k]=k==="prep"?(e.target.value===""?10:+e.target.value):e.target.value;RES=null;save();renderChainTl();updNav()});
function renderEcon(){const f=S.farm,E=f.econ=f.econ||{};
 $("#econBox").innerHTML=`<div class="econ"><label class="ea">Diện tích ruộng A<span class="dur"><input type="number" min="0" step="0.1" data-ec="area" value="${f.area_ha==null?"":f.area_ha}"><i>ha</i></span></label>`+
  `<table class="etab"><thead><tr><th>Cây</th><th>Giá bán P (USD/tấn)</th><th>Năng suất cơ sở Y_base (tấn/ha)</th><th>G = P × A × Y</th></tr></thead><tbody>`+
  META.crops.map(c=>{const e=E[c.id]||{},G=(+f.area_ha>0&&e.price!==""&&e.price!=null&&e.yield!==""&&e.yield!=null)?(+e.price)*(+f.area_ha)*(+e.yield):null;
   return `<tr><td>${ART.crop(c.id)}${esc(c.vi)}</td><td><input type="number" min="0" step="1" data-ep="${c.id}|price" value="${e.price==null?"":e.price}"></td><td><input type="number" min="0" step="0.1" data-ep="${c.id}|yield" value="${e.yield==null?"":e.yield}"></td><td class="g">${G==null?"—":f0(G)+" USD"}</td></tr>`}).join("")+
  `</tbody></table><div class="row" style="gap:8px;align-items:center"><button class="b ghost sm" id="bEconEx">Điền số minh hoạ Kansas</button><span class="fine" style="margin:0">F1 = G / G lớn nhất trong các cây (G ≤ 0 → 0). Số minh hoạ chỉ để thử — hãy sửa theo giá & năng suất thực tế.</span></div></div>`}
$("#econBox").addEventListener("change",e=>{const t=e.target;if(t.dataset.ec==="area"){S.farm.area_ha=t.value===""?null:+t.value}
 else if(t.dataset.ep){const [cid,k]=t.dataset.ep.split("|");S.farm.econ=S.farm.econ||{};S.farm.econ[cid]=S.farm.econ[cid]||{};S.farm.econ[cid][k]=t.value===""?null:+t.value}else return;
 RES=null;save();renderEcon();updNav()});
$("#econBox").addEventListener("click",e=>{if(e.target.id!=="bEconEx")return;S.farm.econ=JSON.parse(JSON.stringify(ECON_EX));if(!(+S.farm.area_ha>0))S.farm.area_ha=10;RES=null;save();renderEcon();updNav();toast("Đã điền số minh hoạ — nhớ sửa theo thực tế.","ok")});

/* K3 / K4 (bước 5) */
$("#k3On").onchange=e=>{S.cfg.k3=e.target.checked;RES=null;save()};
function renderK4(){const L=S.cfg.k4=S.cfg.k4||[],opts=META.crops.map(c=>`<option value="${c.id}">${esc(c.vi)}</option>`).join("");
 $("#k4Box").innerHTML=`<div class="k4l">${L.length?L.map((p,i)=>`<span class="k4p">${ART.crop(p[0])}${esc(cname(p[0]))} → ${ART.crop(p[1])}${esc(cname(p[1]))}<button data-k4del="${i}" aria-label="Bỏ cặp cấm">×</button></span>`).join(""):'<span class="fine" style="margin:0">Chưa có cặp cấm.</span>'}</div>`+
  `<div class="k4a"><select id="k4a">${opts}</select><span>→</span><select id="k4b">${opts}</select><button class="b ghost sm" id="bK4Add">Thêm cặp cấm</button></div>`}
$("#k4Box").addEventListener("click",e=>{const d=e.target.closest("[data-k4del]");if(d){S.cfg.k4.splice(+d.dataset.k4del,1);RES=null;save();renderK4();return}
 if(e.target.id==="bK4Add"){const a=$("#k4a").value,b=$("#k4b").value;if(S.cfg.k4.some(p=>p[0]===a&&p[1]===b))return;S.cfg.k4.push([a,b]);RES=null;save();renderK4()}});

/* ma trận luân canh (bước 6) */
const isK4=(a,b)=>(S.cfg.k4||[]).some(p=>p[0]===a&&p[1]===b);
const prevNow=()=>{if(S.farm.mode==="chain")return (S.farm.chain||{}).prev||"";if(RES&&RES.mode!=="chain")return RES.prev_crop||"";const sc=seasonCal();return sc&&sc.current&&sc.current[0]&&sc.current[0].crop||""};
function renderRot(){if(!META)return;const R=META.rotation,pv=prevNow(),ecol=v=>v>0?hcol(Math.min(1,.55+v/80)):`hsl(8 62% ${Math.max(76,90+v*.9)}%)`;
 let h=`<div class="corner"><span>Cây sau →</span><span>↓ Cây trước</span></div>`+R.cols.map(c=>`<div class="h rh">${ART.crop(c.id)}<b>${esc(c.vi)}</b></div>`).join("");
 R.rows.forEach(r=>{h+=`<div class="rn ${r.from===pv?"me":""}">${ART.crop(r.from)}<div>${esc(r.vi)}${r.from===pv?'<small>vụ trước của bạn</small>':""}</div></div>`+r.cells.map(c=>{
  if(c.diag)return `<div class="c na" title="Độc canh — mốc so sánh${S.cfg.k3!==false?"; bị loại theo K3":""}">—</div>`;
  const me=r.from===pv?" me":"";
  if(!c.has)return `<div class="c nd${me}" title="Không có dữ liệu — tính E = 0 (M = 1)">Không có dữ liệu</div>`;
  return `<div class="c${c.sig?" sig":""}${me}" style="background:${ecol(c.E)}" title="Khoảng tin cậy 95% [${f1(c.lo)}; ${f1(c.hi)}] · n = ${c.n} · M = ${f2(1+c.E/100)}${c.sig?" · có ý nghĩa thống kê":""}">${c.E>0?"+":""}${f1(c.E)}%${c.sig?'<i class="st">●</i>':""}</div>`}).join("")});
 $("#rotTable").innerHTML=h;
 $("#rotLeg").innerHTML=`<span><i class="g"></i>tăng năng suất</span><span><i class="r"></i>giảm năng suất</span><span><b>●</b> có ý nghĩa thống kê</span><span><i class="nd"></i>không có dữ liệu (E = 0)</span><span>Rê chuột lên ô để xem khoảng tin cậy, n và M</span>`;
 $("#rotHow").innerHTML=`<p><b>Hệ số luân canh</b> M(p, c) = 1 + E(p, c)/100, với E là % thay đổi năng suất của cây c khi trồng sau cây p.</p>`+
  `<p><b>Vụ tới</b> — V(c) = S(c, t, x) × M(p, c): S là điểm phù hợp 0–1 của bảng điểm, p là cây vụ trước. Cây đề xuất là cây có V cao nhất trong số cây qua K1–K4.</p>`+
  `<p><b>Chuỗi luân canh</b> — Score(P) = (1/T)[S(c₁) + Σₜ₌₂ S(cₜ)·M(cₜ₋₁, cₜ)], T là số vụ có cây. Vụ đất nghỉ không cộng S, không tính vào T nhưng tác động cây sau qua M(đất nghỉ, c).</p>`+
  `<p class="fine">Số liệu là trung bình toàn cầu, chưa riêng cho Kansas; nhiều cặp chưa có ý nghĩa thống kê nên chưa chắc có tác động.</p>`;
 const mode=S.farm.mode==="chain";
 $("#rotMine").innerHTML=mode?`<p>Bài toán: <b>chuỗi luân canh</b>. Cây vụ trước của thửa: <b>${pv?esc(cname(pv)):"chưa khai báo"}</b> — chỉ dùng cho K3/K4 với cây đầu chuỗi (vụ đầu không nhân M).</p><p class="fine">${esc(META.rot_assumptions[5]||"")}</p>`:
  `<p>Bài toán: <b>vụ tới</b>. Cây vụ trước: <b>${pv?esc(cname(pv)):"chưa rõ"}</b>${pv?" — hàng tô đậm trong ma trận là các hệ số M sẽ nhân với điểm S.":" — khai báo cây cho vụ đang trồng / vừa xong ở bước 2 để dùng hệ số M (hiện M = 1)."}</p>`;
 $("#rotSub").textContent="% thay đổi năng suất cây sau so với độc canh — "+R.source.split(" — ")[0]}
/* v0.9.4: ma trận luân canh chỉ để xem — cặp cấm K4 khai báo ở bước 5 (Tiêu chí) */

/* bảng kết quả kết hợp (bước 7, dưới bảng điểm) */
let ROTMORE=false;
function renderRotRes(){const el=$("#rotRes");if(!RES){el.innerHTML="";return}
 if(RES.mode==="chain"){const C=RES.chain,L=C.chains.slice(0,ROTMORE?50:10);
  el.innerHTML=`<div class="ch"><span class="ti">${ART.W.links}</span><div style="flex:1"><h3>Kết quả chuỗi luân canh: điểm phù hợp × ma trận luân canh</h3><small>${C.n_total} chuỗi hợp lệ trong ${C.start.split("-").reverse().join("/")} → ${C.end.split("-").reverse().join("/")} · làm đất ${C.prep} ngày</small></div></div>`+
   (L.length?`<div class="chains">${L.map(ch=>`<div class="chn ${ch.rank===1?"top":""}"><span class="rk">#${ch.rank}</span><div class="seq">${ch.items.map(x=>x.kind==="fallow"?`<span class="it fal" title="${esc(x.from)} → ${esc(x.to)}">${ART.crop("fallow")}<b>Đất nghỉ</b><small>bỏ một lượt gieo</small></span>`:
     `<span class="it" title="Gieo ${esc(x.sow)} · thu ${esc(x.harvest)}${x.prev?` · sau ${esc(cname(x.prev))}: E = ${x.has===false?"không có dữ liệu (0)":f1(x.E)+" %"}`:""}">${ART.crop(x.id)}<b>${esc(x.vi)}</b><small>${x.sow.slice(8)}/${x.sow.slice(5,7)}/${x.sow.slice(2,4)} → ${x.harvest.slice(8)}/${x.harvest.slice(5,7)}/${x.harvest.slice(2,4)}</small><small>S ${f2(x.S)}${x.prev?` · M ${f2(x.M)}${x.has===false?"*":""}`:""}</small></span>`).join('<span class="ar">→</span>')}</div>`+
     `<div class="sc"><b>${f2(ch.score)}</b><small>T = ${ch.T}</small>${ch.G!=null?`<small>G ≈ ${f0(ch.G)} USD</small>`:""}</div></div>`).join("")}</div>`+
     (C.chains.length>10?`<button class="b ghost sm mt" id="bRotMore">${ROTMORE?"Thu gọn":"Xem thêm "+(Math.min(50,C.chains.length)-10)+" chuỗi"}</button>`:"")
    :`<div class="fine">Không có chuỗi hợp lệ — kéo dài khoảng thời gian ở bước 2, nới K1 hoặc bỏ bớt cặp cấm K4.</div>`)+
   `<p class="fine mt">${C.nodata_pairs.length?"* Cặp không có dữ liệu trong Mudare et al. (2025), tính E = 0: "+C.nodata_pairs.map(x=>esc(x.vi)).join(", ")+". ":""}${esc(C.fallow_rule)} ${C.econ_ok?"":"F1 chưa có dữ liệu kinh tế (bước 2) nên không có G."}${C.truncated?" Số tổ hợp quá lớn — đã dừng sớm.":""}</p>`;
  const mb=$("#bRotMore");if(mb)mb.onclick=()=>{ROTMORE=!ROTMORE;renderRotRes()};return}
 const B=RES.base,pv=RES.prev_crop;
 el.innerHTML=`<div class="ch"><span class="ti">${ART.W.links}</span><div style="flex:1"><h3>Kết hợp ma trận luân canh: V(c) = S × M(cây trước, c)</h3><small>${pv?"Cây vụ trước: <b>"+esc(cname(pv))+"</b> — hệ số M lấy ở hàng “"+esc(cname(pv))+"” của ma trận luân canh":"Chưa rõ cây vụ trước → M = 1 cho mọi cây (khai báo cây của vụ đang trồng ở bước 2)"}</small></div><button class="b ghost sm" data-go="9">Xem ma trận</button></div>`+
  `<div class="scroll"><table class="vtab"><thead><tr><th>Hạng</th><th>Cây</th><th>S (bảng điểm)</th><th>E(cây trước, c)</th><th>M = 1 + E/100</th><th>V = S × M</th><th>Ghi chú</th></tr></thead><tbody>`+
  B.crops.map(r=>`<tr class="${r.feasible?"":"x"}"><td>${r.rank?"#"+r.rank:"—"}</td><td>${ART.crop(r.id)}${esc(r.vi)}</td><td>${f2(r.total)}</td><td>${!pv?"—":r.id===pv?"độc canh":r.E_has===false?"không có dữ liệu (0)":(r.E>0?"+":"")+f1(r.E)+" %"+(r.E_rec?` <small>[${f1(r.E_rec.lo)}; ${f1(r.E_rec.hi)}], n=${r.E_rec.n}${r.E_rec.sig?" · có ý nghĩa":""}</small>`:"")}</td><td>${f2(r.M)}</td><td><b>${f2(r.V)}</b></td><td>${r.feasible?(r.rank===1?"Đề xuất":""):esc((r.watch||[])[0]||("Loại theo "+r.excl))}</td></tr>`).join("")+
  `</tbody></table></div>${RES.rot_nodata&&RES.rot_nodata.length?`<p class="fine">Cặp không có dữ liệu (E = 0): ${esc(cname(pv))} → ${RES.rot_nodata.map(esc).join(", ")}.</p>`:""}`}

/* ---------- 0. trang chủ: giám sát & cảnh báo (GiamSat.md) ---------- */
/* 11/2026: NASA chuyển dịch vụ ảnh POWER sang /portal/rest/... (đường /image/rest/... cũ trả 404) */
const PSVC={MET:"https://gis.earthdata.nasa.gov/portal/rest/services/POWER/POWER_MONTHLY_METEOROLOGY_LST/ImageServer",RAD:"https://gis.earthdata.nasa.gov/portal/rest/services/POWER/POWER_MONTHLY_RADIATION_LST/ImageServer"};
const MLAY={A1:{lab:"A1 · Nhiệt độ 2 m",unit:"°C",svc:"MET",want:["T2M"],min:-15,max:35,pal:["#2c7bb6","#abd9e9","#ffffbf","#fdae61","#d7191c"]},
 A2:{lab:"A2 · Lượng mưa",unit:"mm/ngày",svc:"MET",want:["PRECTOTCORR","PRECTOTCORR_SUM","PRECTOT"],min:0,max:8,pal:["#f7fbff","#c6dbef","#6baed6","#2171b5","#08306b"]},
 A3:{lab:"A3 · Chỉ số Kt",unit:"",svc:"RAD",want:["ALLSKY_KT"],min:.3,max:.75,pal:["#3b3f46","#8a8f98","#e9d38a","#f3a43b","#e2551f"]},
 B1:{lab:"B1 · Độ ẩm đất mặt",unit:"0–1",svc:"MET",want:["GWETROOT","GWETTOP"],min:0,max:1,pal:["#8c510a","#d8b365","#f6e8c3","#5ab4ac","#01665e"]}};
const LVCOL=["#4E9F4A","#E0A21F","#E26A1B","#C4292A"],LVBG=["#EAF5E7","#FFF4D6","#FDE7D6","#FBE0DD"];
let MONMAP=null,MONLAY=null,MONMARK=null,MLK="A1",MDIM={},MONT=[],MONPLAY=0,MONVAR="A1",MONDAYS=120,MONBUSY=false,MONERR=null;
const HD=Math.min(2,window.devicePixelRatio||1);
const hexRGB=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));
function rampRGB(pal,t){const n=pal.length-1,k=Math.max(0,Math.min(n-1e-9,t*n)),i=Math.floor(k),f=k-i,a=hexRGB(pal[i]),b=hexRGB(pal[Math.min(n,i+1)]);return a.map((v,j)=>Math.round(v+(b[j]-v)*f))}
function rrFor(L){const cm=[];for(let i=0;i<32;i++)cm.push([i].concat(rampRGB(L.pal,i/31)));
 return {rasterFunction:"Colormap",rasterFunctionArguments:{Colormap:cm,Raster:{rasterFunction:"Stretch",rasterFunctionArguments:{StretchType:5,Statistics:[[L.min,L.max,(L.min+L.max)/2,(L.max-L.min)/4]],Min:0,Max:31,DRA:false,UseGamma:false},outputPixelType:"U8"}}}}
const PowerImg=window.L?L.Layer.extend({initialize(o){this.o=o},onAdd(m){this._m=m;m.on("moveend",this._up,this);this._up()},onRemove(m){m.off("moveend",this._up,this);if(this._ov)m.removeLayer(this._ov);this._ov=null},
 set(o){Object.assign(this.o,o);this._up()},
 _url(rr){const m=this._m,b=m.getBounds(),sz=m.getSize(),p0=L.CRS.EPSG3857.project(b.getSouthWest()),p1=L.CRS.EPSG3857.project(b.getNorthEast());
  const q={bbox:[p0.x,p0.y,p1.x,p1.y].map(v=>v.toFixed(0)).join(","),bboxSR:3857,imageSR:3857,size:Math.round(sz.x*HD)+","+Math.round(sz.y*HD),format:"png32",transparent:true,f:"image",interpolation:"RSP_BilinearInterpolation",
   mosaicRule:JSON.stringify({multidimensionalDefinition:[{variableName:this.o.v,dimensionName:"StdTime",values:[this.o.t],isSlice:true}]})};
  if(rr)q.renderingRule=JSON.stringify(rr);return this.o.url+"/exportImage?"+new URLSearchParams(q)},
 _up(){if(!this._m||!this.o.v)return;const b=this._m.getBounds(),seq=(this._seq=(this._seq||0)+1);
  const go=useRR=>{const ov=L.imageOverlay(this._url(useRR?this.o.rr:null),b,{opacity:.85,interactive:false,className:"pwimg"});
   ov.once("load",()=>{if(seq!==this._seq){this._m.removeLayer(ov);return}if(this._ov&&this._ov!==ov)this._m.removeLayer(this._ov);this._ov=ov;this.o.onok&&this.o.onok(useRR)});
   ov.once("error",()=>{this._m.removeLayer(ov);if(seq!==this._seq)return;if(useRR)go(false);else this.o.onerr&&this.o.onerr()});ov.addTo(this._m)};go(true)}}):null;
async function mdimFor(k){const L0=MLAY[k];if(MDIM[k])return MDIM[k];let v=L0.want[0],times=[];
 try{let j=null;try{j=await (await fetch("/api/power_md?svc="+L0.svc)).json();if(!j||!j.multidimensionalInfo)j=null}catch(e){}
  if(!j)j=await (await fetch(PSVC[L0.svc]+"/multiDimensionalInfo?f=json")).json();const vars=(j.multidimensionalInfo||{}).variables||[];
  const hit=L0.want.map(w=>vars.find(x=>x.name===w)).find(Boolean)||vars.find(x=>L0.want.some(w=>x.name.startsWith(w)));
  if(hit){v=hit.name;const d=(hit.dimensions||[]).find(x=>/time/i.test(x.name));if(d&&d.values)times=d.values.map(x=>Array.isArray(x)?x[0]:x)}}catch(e){}
 if(!times.length){const yl=new Date().getUTCFullYear()-1;for(let y=2001;y<=yl;y++)for(let m=0;m<12;m++)times.push(Date.UTC(y,m+1,0))}  // dịch vụ đánh dấu mỗi tháng bằng ngày cuối tháng, 00:00 UTC
 const L1=Object.assign({},L0);if(/_SUM$/.test(v)){L1.unit="mm/tháng";L1.min=0;L1.max=200}
 return (MDIM[k]={v,times:times.sort((a,b)=>a-b),L:L1})}
function initMonMap(){if(MONMAP||!window.L)return;const el=$("#monMap");if(!el)return;const has=S.farm.lat!=null;
 MONMAP=L.map(el,{zoomControl:false,worldCopyJump:true,scrollWheelZoom:false,minZoom:2}).setView(has?[S.farm.lat,S.farm.lon]:[25,10],has?6:3);homeCenter();L.control.zoom({position:"bottomright"}).addTo(MONMAP);
 el.addEventListener("wheel",e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();MONMAP.setZoom(MONMAP.getZoom()+(e.deltaY<0?1:-1))}},{passive:false});
 // nền rõ nét: xám nhạt + bóng địa hình (đè lên lớp dữ liệu, kiểu nhân màu) + ranh giới & địa danh đậm ở trên cùng
 [["hsp",420],["lbl",450]].forEach(([n,z])=>{MONMAP.createPane(n);MONMAP.getPane(n).style.zIndex=z;MONMAP.getPane(n).style.pointerEvents="none"});
 const E="https://server.arcgisonline.com/ArcGIS/rest/services/";
 L.tileLayer(E+"Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",{maxZoom:16,attribution:"Esri, USGS, HERE, Garmin · NASA POWER"}).addTo(MONMAP);
 L.tileLayer(E+"Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}",{maxZoom:16,opacity:.5,pane:"hsp",className:"hs"}).addTo(MONMAP);
 L.tileLayer(E+"Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",{maxZoom:16,pane:"lbl"}).addTo(MONMAP);
 if(has)MONMARK=L.marker([S.farm.lat,S.farm.lon],{icon:L.divIcon({html:PIN,className:"",iconSize:[40,52],iconAnchor:[20,50]})}).addTo(MONMAP);
 $("#monLayers").innerHTML=Object.entries(MLAY).map(([k,v])=>`<button data-ml="${k}" class="${k===MLK?"on":""}">${v.lab}</button>`).join("");setMonLayer(MLK)}
async function setMonLayer(k){MLK=k;$$("#monLayers button").forEach(b=>b.classList.toggle("on",b.dataset.ml===k));$("#monMapMsg").textContent="";const D=await mdimFor(k);MONT=D.times;
 const sl=$("#monTime");sl.max=Math.max(0,MONT.length-1);if(+sl.value>+sl.max||!sl._set){sl.value=sl.max;sl._set=1}fillv(sl);monTimeLbl();
 const o={url:PSVC[D.L.svc],v:D.v,t:MONT[+sl.value],rr:rrFor(D.L),onok:rr=>legend(D.L,rr),onerr:()=>{$("#monMapMsg").innerHTML=`Không tải được lớp NASA POWER (${esc(D.v)}) — kiểm tra mạng hoặc mở <a href="https://power.larc.nasa.gov/data-access-viewer/" target="_blank" rel="noopener">NASA POWER DAV ↗</a>.`}};
 if(!MONLAY){MONLAY=new PowerImg(o);MONLAY.addTo(MONMAP)}else MONLAY.set(o);legend(D.L,true)}
function legend(L0,rr){$("#monLeg").innerHTML=`<b>${esc(L0.lab)}</b>${rr?`<i style="background:linear-gradient(90deg,${L0.pal.join(",")})"></i><span>${String(L0.min).replace(".",DC)}</span><span>${String(L0.max).replace(".",DC)} ${esc(L0.unit)}</span>`:`<span>màu mặc định của dịch vụ</span>`}`}
function monTimeLbl(){const t=MONT[+$("#monTime").value];if(t==null){$("#monTimeLbl").textContent="—";return}const d=new Date(t);$("#monTimeLbl").textContent="Tháng "+(d.getUTCMonth()+1)+"/"+d.getUTCFullYear()}
$("#monLayers").addEventListener("click",e=>{const b=e.target.closest("[data-ml]");if(b)setMonLayer(b.dataset.ml)});
let MTT=0;$("#monTime").addEventListener("input",e=>{fillv(e.target);monTimeLbl();clearTimeout(MTT);MTT=setTimeout(()=>{if(MONLAY)MONLAY.set({t:MONT[+e.target.value]})},250)});
$("#bMonPlay").onclick=()=>{const b=$("#bMonPlay"),sl=$("#monTime");if(MONPLAY){clearInterval(MONPLAY);MONPLAY=0;b.textContent="▶";return}b.textContent="❚❚";if(+sl.value>=+sl.max)sl.value=Math.max(0,+sl.max-23);
 MONPLAY=setInterval(()=>{if(+sl.value>=+sl.max){clearInterval(MONPLAY);MONPLAY=0;b.textContent="▶";return}sl.value=+sl.value+1;fillv(sl);monTimeLbl();if(MONLAY)MONLAY.set({t:MONT[+sl.value]})},1400)};
function monDays(){if(MONDAYS!=="season")return MONDAYS;const sc=seasonCal();if(sc&&sc.current.length)return Math.max(14,Math.round((sc.today-sc.current[0].cur[0])/864e5)+1);return 120}
async function runMonitor(){if(MONBUSY||S.farm.lat==null)return;MONBUSY=true;spin("#spMon",true);
 try{MONR=await api("/api/monitor",{farm:S.farm,cfg:S.mon,today:isoD(todayD()),days:monDays()});MONERR=null;notifyAlerts()}catch(e){MONERR=e.message}
 MONBUSY=false;spin("#spMon",false);renderMon();updNav()}
function fmtF(k,v){return v==null?"—":k==="A1"?f1(v)+"°C":k==="A2"?f0(v)+" mm":f2(v)}
function renderMon(){const sub=$("#monSub");if(MONERR){$("#monNow").innerHTML=`<div class="err show">${esc(MONERR)}</div>`;return}if(!MONR)return;
 sub.innerHTML=`Số liệu đến ngày <b>${MONR.as_of.slice(6)}/${MONR.as_of.slice(4,6)}/${MONR.as_of.slice(0,4)}</b> (trễ ${MONR.lag_days} ngày) · cây theo dõi: <b>${MONR.crop_vi?esc(MONR.crop_vi)+(MONR.crop_mode==="user"?" (bạn chọn)":" (đang trong vụ)"):"không có cây đang trong vụ — chỉ dùng phương pháp thống kê"+(MONR.next_crop_vi?"; vụ tới: "+esc(MONR.next_crop_vi):"")}</b>${MONR.demo?' · <span class="chip warn">DEMO</span>':""}`;
 $("#monNow").innerHTML=Object.entries(MONR.factors).map(([k,f])=>{const lv=f.level||0,on=S.mon.factors.includes(k),d=f.value!=null&&f.baseline!=null?f.value-f.baseline:null;
  return `<div class="mk ${on?"":"off"}" style="--lc:${LVCOL[lv]};--lb:${LVBG[lv]}"><div class="mkh"><code style="background:${CCOL[k]}">${k}</code><b>${esc(f.vi)}</b><span class="lv">${on?META.monitor.levels[lv]:"không theo dõi"}</span></div>`+
   `<div class="mkv">${fmtF(k,f.value)}<small>${esc(f.win||"")}</small></div><div class="mkb">TB cùng kỳ ${fmtF(k,f.baseline)}${d!=null?` · <span class="${d>0?"up":"dn"}">${d>0?"▲":"▼"} ${fmtF(k,Math.abs(d))}</span>`:""}${f.pct!=null?` · phân vị ${f0(f.pct)}`:""}${k==="B1"&&f.b1_score!=null?` · Ya/Ym ${f2(f.b1_score)}`:""}${k==="A2"&&f.since_start!=null?` · từ đầu vụ ${f0(f.since_start)} mm`:""}</div></div>`}).join("");
 $("#monAlerts").innerHTML=MONR.alerts.length?MONR.alerts.map(a=>`<div class="ma" style="--lc:${LVCOL[a.level]};--lb:${LVBG[a.level]}"><div><span class="lv">${META.monitor.levels[a.level]}${a.word?" · "+esc(a.word):""}</span><b>${a.code} ${esc(a.vi)}${MONR.crop_vi?" · "+esc(MONR.crop_vi):""}</b></div><small>${esc(a.reason)}</small><i>Phương pháp đã báo: ${esc(a.methods.join(", "))}</i></div>`).join(""):
  `<div class="ma ok"><b>Không có cảnh báo</b><small>Các yếu tố đang theo dõi đều trong ngưỡng bình thường.</small></div>`;
 const mx=MONR.alerts.reduce((m,a)=>Math.max(m,a.level),0);$("#hDot").style.background=LVCOL[mx];$("#hTitle").textContent=MONR.alerts.length?MONR.alerts.length+" cảnh báo đang mở":"Thời tiết bình thường";$("#hPanel").dataset.lv=mx;
 drawMonChart()}
function notifyAlerts(){const key="fa_alert_seen_"+(+S.farm.lat).toFixed(3)+"_"+(+S.farm.lon).toFixed(3);let seen={};try{seen=JSON.parse(localStorage.getItem(key)||"{}")}catch(e){}
 MONR.alerts.forEach(a=>{if((seen[a.code]||0)<a.level&&S.mon.channels.includes("ui"))toast(`${META.monitor.levels[a.level]}: ${a.code} ${a.vi} — ${a.reason}`,a.level>=2?"err":"info")});
 const now={};Object.entries(MONR.factors).forEach(([k,f])=>now[k]=f.level||0);try{localStorage.setItem(key,JSON.stringify(now))}catch(e){}}
function drawMonChart(){if(!MONR)return;$("#monVar").innerHTML=["A1","A2","A3","B1"].map(k=>`<button data-mv="${k}" class="${MONVAR===k?"on":""}">${k} · ${esc(MONR.factors[k].vi)}</button>`).join("");
 $("#monRange").innerHTML=[[30,"30 ngày"],[90,"90 ngày"],[180,"6 tháng"],[365,"1 năm"],["season","Từ đầu vụ"]].map(([v,l])=>`<button data-mr="${v}" class="${String(MONDAYS)===String(v)?"on":""}">${l}</button>`).join("");
 const se=MONR.series,b=MONR.band[MONVAR],lab=se.dates.map(d=>d.slice(6)+"/"+d.slice(4,6)),k=MONVAR;
 const nm={A1:"Nhiệt độ TB 7 ngày (°C)",A2:"Mưa cộng dồn 30 ngày (mm)",A3:"Kt TB 7 ngày",B1:"Ẩm vùng rễ (0–1)"}[k];
 const ds=[{label:"Phân vị 90 lịch sử",data:b.p90,borderColor:"rgba(0,0,0,0)",backgroundColor:"rgba(58,143,208,.14)",pointRadius:0,fill:"+1",order:3},
  {label:"Phân vị 10 lịch sử",data:b.p10,borderColor:"rgba(0,0,0,0)",pointRadius:0,fill:false,order:4},
  {label:"Trung vị cùng kỳ",data:b.p50,borderColor:"#6B776F",borderDash:[5,4],borderWidth:1.6,pointRadius:0,fill:false,order:2},
  {label:nm+" — năm nay",data:se[k],borderColor:CCOL[k],borderWidth:2.6,pointRadius:0,tension:.25,fill:false,order:1}];
 const c=MONR.crop&&cropOf(MONR.crop);if(c&&k==="A1")ds.push({label:"Tối ưu của "+c.vi.toLowerCase(),data:lab.map(()=>c.A1.opt[1]),borderColor:"#35904A",borderDash:[2,3],borderWidth:1.4,pointRadius:0,fill:false},{label:"_",data:lab.map(()=>c.A1.opt[0]),borderColor:"#35904A",borderDash:[2,3],borderWidth:1.4,pointRadius:0,fill:false});
 if(k==="A3")ds.push({label:"Rất sáng ≥ 0,60",data:lab.map(()=>.6),borderColor:"#C77D0A",borderDash:[2,3],borderWidth:1.4,pointRadius:0,fill:false});
 mk("cMon",{type:"line",data:{labels:lab,datasets:ds},options:{interaction:{mode:"index",intersect:false},plugins:{legend:{labels:{filter:i=>i.text!==_t("Phân vị 10 lịch sử")&&i.text!=="_"}}},scales:{x:{ticks:{maxTicksLimit:10}}}}})}
$("#monVar").addEventListener("click",e=>{const b=e.target.closest("[data-mv]");if(b){MONVAR=b.dataset.mv;drawMonChart()}});
$("#monRange").addEventListener("click",e=>{const b=e.target.closest("[data-mr]");if(b){MONDAYS=b.dataset.mr==="season"?"season":+b.dataset.mr;runMonitor()}});
/* cấu hình cảnh báo */
function renderMonCfg(){const c=S.mon,F=META.monitor.factors,crops=[["","Tự động (cây của vụ đang diễn ra)"]].concat(META.crops.map(x=>[x.id,x.vi]));
 $("#monCfg").innerHTML=`<div class="mcg"><div><h4>1. Yếu tố theo dõi</h4>${Object.entries(F).map(([k,f])=>`<label class="tog"><input type="checkbox" data-mf="${k}" ${c.factors.includes(k)?"checked":""}><span><b>${k} ${esc(f.vi)}</b><br><small class="fine" style="margin:0">${esc(f.win)}</small></span></label>`).join("")}</div>`+
  `<div><h4>2. Phương pháp</h4><label class="tog"><input type="checkbox" data-mm="agro" ${c.methods.includes("agro")?"checked":""}><span><b>Ngưỡng nông học</b><br><small class="fine" style="margin:0">So với ngưỡng chịu đựng của cây trong CRD</small></span></label>`+
  `<label>Biên “sắp đến giới hạn” m: <b id="mMv">${c.margin_pct}%</b> bề rộng vùng chịu đựng</label><input type="range" class="fl" data-mn="margin_pct" min="1" max="20" step="1" value="${c.margin_pct}">`+
  `<label>Cây trên thửa</label><select data-mc>${crops.map(([id,v])=>`<option value="${id}" ${c.crop===id?"selected":""}>${esc(v)}</option>`).join("")}</select>`+
  `<label class="tog mt"><input type="checkbox" data-mm="stat" ${c.methods.includes("stat")?"checked":""}><span><b>Bất thường thống kê</b><br><small class="fine" style="margin:0">Phân vị so với cùng thửa, ±15 ngày, mọi năm</small></span></label>`+
  `<div class="two" style="gap:8px"><label>Chú ý khi ≤ / ≥ phân vị<input type="number" data-mn="p_watch" min="1" max="49" value="${c.p_watch}"></label><label>Cảnh báo khi ≤ / ≥ phân vị<input type="number" data-mn="p_warn" min="1" max="49" value="${c.p_warn}"></label></div></div>`+
  `<div><h4>3. Kênh nhận</h4>${[["ui","Trên giao diện"],["email","Email (chưa kết nối hạ tầng)"],["push","Thông báo đẩy (chưa kết nối hạ tầng)"]].map(([k,v])=>`<label class="tog"><input type="checkbox" data-mch="${k}" ${c.channels.includes(k)?"checked":""}><span>${v}</span></label>`).join("")}`+
  `<p class="fine">Chọn ${c.factors.length} yếu tố × ${c.methods.length} phương pháp = <b>${c.factors.length*c.methods.length} quy tắc</b>. Mỗi yếu tố chỉ hiện một cảnh báo (mức cao nhất); chỉ báo lại khi mức tăng lên.</p>`+
  `<div class="row" style="gap:8px"><button class="b" id="bMonSave">Lưu & áp dụng</button><button class="b ghost" id="bMonClose">Đóng</button></div></div></div>`;$$("#monCfg input.fl").forEach(fillv)}
$("#bMonCfg").onclick=()=>{const p=$("#monCfg");p.hidden=!p.hidden;if(!p.hidden)renderMonCfg()};
$("#monCfg").addEventListener("input",e=>{const t=e.target,c=S.mon;
 if(t.dataset.mf){const a=c.factors;t.checked?a.includes(t.dataset.mf)||a.push(t.dataset.mf):a.splice(a.indexOf(t.dataset.mf),1)}
 if(t.dataset.mm){const a=c.methods;t.checked?a.includes(t.dataset.mm)||a.push(t.dataset.mm):a.splice(a.indexOf(t.dataset.mm),1)}
 if(t.dataset.mch){const a=c.channels;t.checked?a.includes(t.dataset.mch)||a.push(t.dataset.mch):a.splice(a.indexOf(t.dataset.mch),1)}
 if(t.dataset.mn){c[t.dataset.mn]=+t.value;if(t.classList.contains("fl")){fillv(t);$("#mMv").textContent=t.value+"%"}}
 if(t.matches("[data-mc]"))c.crop=t.value});
$("#monCfg").addEventListener("change",e=>{if(e.target.dataset.mf||e.target.dataset.mm)renderMonCfg()});
$("#monCfg").addEventListener("click",e=>{if(e.target.id==="bMonClose")$("#monCfg").hidden=true;
 if(e.target.id==="bMonSave"){const c=S.mon;if(!c.factors.length||!c.methods.length){toast("Chọn ít nhất 1 yếu tố và 1 phương pháp.","err");return}
  if(c.p_warn>=c.p_watch){toast("Mức phân vị “Cảnh báo” phải nhỏ hơn mức “Chú ý”.","err");return}save();$("#monCfg").hidden=true;toast("Đã lưu cấu hình cảnh báo.","ok");runMonitor()}});
function enterHome(){const has=S.farm.lat!=null;if(has&&!CLIM&&!CLIMBUSY)ensureClim();$("#homeNoFarm").style.display=has?"none":"block";$("#homeBox").style.display=has?"block":"none";
 if(!MONMAP)initMonMap();else{setTimeout(()=>MONMAP.invalidateSize(),40);if(has){if(MONMARK)MONMARK.setLatLng([S.farm.lat,S.farm.lon]);else MONMARK=L.marker([S.farm.lat,S.farm.lon],{icon:L.divIcon({html:PIN,className:"",iconSize:[40,52],iconAnchor:[20,50]})}).addTo(MONMAP)}}
 $("#bStart").textContent=has&&LASTSTEP>0?"Tiếp tục dùng công cụ →":"Bắt đầu dùng công cụ →";renderHeroCard();
 if(!has){$("#hDot").style.background="#9AA5A0";$("#hTitle").textContent="Cảnh báo thời tiết";$("#hScenSub").textContent="Chọn ruộng và khai báo mùa vụ để so sánh kịch bản cho vụ tới";$("#homeScen").style.display="none";return}
 $("#homeScen").style.display="";
 if(!MONR||MONERR)runMonitor();else renderMon();
 const sc=seasonCal();$("#hScenSub").textContent=sc&&sc.target?`Vụ tới: ${sc.target.name} · bắt đầu ${dmy(sc.target.nxt[0])} — kéo các thanh A1, A2, A3, B1 để xem cây nào còn hợp`:"Khai báo mùa vụ (bước 2) để so sánh kịch bản cho vụ tới";
 /* v0.9.2: thẻ "So sánh 3 cột" đã ẩn — không dựng nữa */
 $("#homeScen").parentElement.style.display="";if(S.farm.mode==="chain"&&sc)$("#hScenSub").textContent=`Chuỗi luân canh ${dmy(sc.target.nxt[0])} → ${dmy(new Date(sc.target.nxt[1]-864e5))} — kéo các thanh A1, A2, A3, B1 để xem chuỗi nào còn tốt nhất`;
 if(RES&&RES.mode!==(S.farm.mode==="chain"?"chain":"next"))RES=null;
 if(!RES&&sc){SCW[0].render();runEval(true)}else SCW[0].render()}
$("#bHomeDemo").onclick=()=>preset("ke",0);
function homeCenter(){if(!MONMAP)return;const w=$("#hCard")?$("#hCard").offsetWidth:0;if(w&&innerWidth>900)MONMAP.panBy([-(w/2-60),0],{animate:false})}
function renderHeroCard(){const f=S.farm||{},has=f.lat!=null,sc=has?seasonCal():null;
 if(!$("#hArt").innerHTML)$("#hArt").innerHTML=((ART.BANW&&ART.BANW[2])||ART.BAN[2]).replace("<svg ",'<svg preserveAspectRatio="xMaxYMid slice" ');
 $("#hFarm").innerHTML=has?`<span class="pn">${PIN}</span><div><b>${esc(f.name||"Ruộng của tôi")}</b><small>${(+f.lat).toFixed(3)}°, ${(+f.lon).toFixed(3)}° · ${f.irrigated?"có tưới":"nhờ mưa"}${sc&&sc.target?" · vụ tới: "+esc(sc.target.name)+" từ "+dmy(sc.target.nxt[0]):""}</small></div><button class="b ghost sm" data-go="1">Đổi</button>`:
  `<span class="pn">${PIN}</span><div><b>Chưa chọn ruộng</b><small>Bản đồ vẫn xem được; chọn ruộng để nhận cảnh báo riêng.</small></div>`;
 if(!$("#lArt").innerHTML)$("#lArt").innerHTML=((ART.BANW&&ART.BANW[6])||ART.BAN[6]).replace("<svg ",'<svg preserveAspectRatio="xMaxYMid slice" ')}
$("#bStart").onclick=()=>goTab(S.farm.lat!=null&&LASTSTEP>0?LASTSTEP:1);
$("#bDown").onclick=()=>$("#homeLow").scrollIntoView({behavior:"smooth"});
$("#bUp").onclick=()=>{$("#pages").scrollTo({top:0,behavior:"smooth"})};
$("#bHpMin").onclick=()=>{const p=$("#hPanel");p.classList.toggle("min");$("#bHpMin").textContent=p.classList.contains("min")?"+":"–"};
/* nguồn ở cuối mỗi trang + lưu ý gom về trang cuối */
const XSRC={esri:["Esri World Imagery","https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9"],osm:["OpenStreetMap","https://www.openstreetmap.org/copyright"],geocode:["Nominatim / Open-Meteo Geocoding","https://nominatim.org/"],
 power:["NASA POWER API","https://power.larc.nasa.gov/"],power_img:["NASA POWER Image Services","https://gis.earthdata.nasa.gov/image/rest/services/POWER"],gpm:["GPM IMERG","https://gpm.nasa.gov/data/imerg"],smap:["SMAP L4","https://nsidc.org/data/spl4smgp"],
 ssurgo:["SSURGO (USDA NRCS)","https://sdmdataaccess.nrcs.usda.gov/"],soil:["SoilGrids 2.0","https://soilgrids.org"],slope:["SRTM 30 m","https://www.opentopodata.org/datasets/srtm/"],
 crd:["Crop Requirement Database (CRD)","#tab7"],baitoan:["BaiToan1: FarmSTEPS, RotationARM, Review CRM, Organic (SARE), CSA, UNCCD","#tab8"]};
function renderPgSrc(){$$(".pgsrc").forEach(el=>{const ks=el.dataset.src.split(",");el.innerHTML=`<span>Nguồn trên trang này:</span>`+ks.map(k=>{const x=XSRC[k]||(META&&META.crd_sources[k]?[k+" – "+META.crd_sources[k][0],META.crd_sources[k][1]]:[k,"#"]);
  return x[1][0]==="#"?`<a href="#" data-go="${x[1].slice(4)}">${esc(x[0])}</a>`:`<a href="${esc(x[1])}" target="_blank" rel="noopener">${esc(x[0])}</a>`}).join("")+`<a href="#" data-go="8" class="more">Nguồn đầy đủ & lưu ý →</a>`})}
function renderNotes(){const el=$("#srcNotes");if(!el||!META)return;let h=META.notes.map(g=>`<div class="ng"><h4>${esc(g.g)}</h4><ul>${g.items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div>`).join("");
 if(RES&&((RES.warnings||[]).length||Object.keys(RES.base.missing).length))h=`<div class="ng cur"><h4>Lưu ý cho lần tính gần nhất</h4><ul>${(RES.warnings||[]).map(x=>`<li>${esc(x)}</li>`).join("")}${Object.entries(RES.base.missing).map(([k,v])=>`<li>${k} ${esc(critOf(k).vi)} chưa tính vì thiếu dữ liệu: ${esc(v||"")}</li>`).join("")}</ul></div>`+h;
 el.innerHTML=h}
document.body.appendChild($("#monCfg"));  // hộp cấu hình nổi giữa màn hình, không bị khung trang giữ lại
/* ---------- kịch bản 2^n · so sánh 3 cột (full.md – Cấu hình kịch bản so sánh) ---------- */
const S3K=[["A1","dT","ΔT nhiệt độ","°C",0.5,1.5],["A2","dP","ΔP lượng mưa","%",5,20],["A3","dKt","ΔKt bức xạ","",0.01,0.05],["B1","dTheta","Δθ ẩm đất đầu vụ","m³/m³",0.01,0.05]];
let S3R=null;
function s3st(){S.scen3=Object.assign({crit:["A1","A2"],mag:{dT:1.5,dP:20,dKt:0.05,dTheta:0.05},base:"baseline",plus:null,minus:null},S.scen3||{});return S.scen3}
function renderS3(){const s3=$("#scen3");if(s3)s3.style.display="none";return;const c=s3st();$("#scen3").style.display=S.farm.lat==null?"none":"";if(S3R&&S3R.mode!==(S.farm.mode==="chain"?"chain":"next"))S3R=null;
 $("#s3cfg").innerHTML=`<div class="s3k">${S3K.map(([k,key,lab,u,st])=>{const i=c.crit.indexOf(k);return `<label class="s3i ${i>=0?"on":""}"><input type="checkbox" data-s3c="${k}" ${i>=0?"checked":""}><code style="background:${CCOL[k]}">${k}</code><span>${lab}${i>=0?` <em>#${i+1}</em>`:""}</span><span class="dur"><input type="number" min="0" step="${st}" data-s3m="${key}" value="${c.mag[key]}"><i>${u||"±"}</i></span></label>`}).join("")}</div>`+
  `<div class="row s3b"><span class="fine" style="margin:0">Mốc so sánh:</span><div class="sg"><button data-s3b="baseline" class="${c.base==="baseline"?"on":""}">Trung bình nhiều năm</button><button data-s3b="last" class="${c.base==="last"?"on":""}">Năm ngoái</button></div><span class="fine" style="margin:0">${c.crit.length?`${c.crit.length} tiêu chí → ${2**c.crit.length} tổ hợp`:"Chọn ít nhất 1 tiêu chí"}</span><span class="sp"></span><button class="b sm" id="bS3">Chạy so sánh</button></div>`+
  `<p class="fine" style="margin:6px 0 0">A2 và B1 dùng chung mưa: khi có ΔP thì mưa trong vụ của B1 cũng nhận ΔP; Δθ của B1 chỉ áp vào nước trong đất đầu vụ. Δ+ mặc định theo hướng tăng của tiêu chí chọn đầu tiên (nóng – khô nếu A1 trước), Δ− là tổ hợp ngược lại.</p>`;
 renderS3Res()}
function s3colC(title,sub,res,base,cls){if(!res)return "";
 return `<div class="s3c ${cls||""}"><div class="s3h"><b>${title}</b><small>${sub||""}</small></div>${res.rows.slice(0,6).map(r=>`<div class="s3r ${r.key===res.top?"top":""}"><span class="s3q"><em>#${r.rank}</em><span>${esc(r.label)}<small>${esc(r.years)}</small></span></span><b>${f2(r.score)}</b></div>`).join("")||'<div class="fine">Không có chuỗi hợp lệ.</div>'}${base&&res.top!==base.top?`<div class="s3d">Chuỗi đứng đầu khác baseline: <b>${esc(res.top_label||"—")}</b></div>`:base?'<div class="s3s">Chuỗi đứng đầu giữ nguyên</div>':""}</div>`}
function s3col(title,sub,res,base,cls){if(!res)return "";if(res.n_total!==undefined)return s3colC(title,sub,res,base,cls);const F=res.rows;
 return `<div class="s3c ${cls||""}"><div class="s3h"><b>${title}</b><small>${sub||""}</small></div>${F.map(r=>`<div class="s3r ${r.feasible?"":"x"} ${r.id===res.top?"top":""}">${ART.crop(r.id)}<span>${r.rank?"#"+r.rank+" ":""}${esc(r.vi)}${r.feasible?"":` <small>loại (${esc(r.excl)})</small>`}</span><b>${f2(r.V)}</b></div>`).join("")}${base&&res.top!==base.top?`<div class="s3d">Cây đứng đầu khác baseline: ${esc(cname(base.top))} → <b>${esc(cname(res.top))}</b></div>`:base?'<div class="s3s">Cây đứng đầu giữ nguyên</div>':""}</div>`}
function renderS3Res(){const el=$("#s3res");if(!S3R){el.innerHTML="";return}const c=s3st(),cb=id=>S3R.combos.find(x=>x.id===id);
 const p=cb(c.plus)||cb(S3R.plus),m=cb(c.minus)||cb(S3R.minus),opt=sel=>S3R.combos.map(x=>`<option value="${x.id}" ${x.id===sel.id?"selected":""}>${esc(x.label)}${x.changed?" · đổi cây đầu":""}</option>`).join("");
 el.innerHTML=`<div class="s3g">${s3col("Baseline",S3R.base_mode==="last"?"năm ngoái":"trung bình nhiều năm",S3R.baseline)}`+
  s3col(`Kịch bản tăng (Δ+)`,`<select data-s3sel="plus">${opt(p)}</select>`,p.res,S3R.baseline,"pl")+s3col(`Kịch bản giảm (Δ−)`,`<select data-s3sel="minus">${opt(m)}</select>`,m.res,S3R.baseline,"mi")+`</div>`+
  `<div class="s3all"><b>Tất cả ${S3R.combos.length} tổ hợp:</b> ${S3R.combos.map(x=>`<span class="${x.changed?"ch":""}">${esc(x.label)} → ${esc(S3R.mode==="chain"?(x.res.top_label||"—"):cname(x.res.top))}</span>`).join("")}</div>`+
  (S3R.mode==="chain"?`<p class="fine">Đơn vị so sánh là cả chuỗi luân canh: mỗi cột xếp hạng các chuỗi theo Score(P) sau khi chấm lại S của từng vụ với Δ. Khoảng ${S3R.target.start.split("-").reverse().join("/")} → ${S3R.target.end.split("-").reverse().join("/")}.${S3R.is_demo?" Khí hậu DEMO.":""}</p>`
  :`<p class="fine">Mỗi cột: xếp hạng theo V = S × M (M theo cây vụ trước${S3R.prev_crop?": "+esc(cname(S3R.prev_crop)):" — chưa có, M = 1"}). Vụ: ${esc(S3R.target.name)} từ ${S3R.target.start.split("-").reverse().join("/")}.${S3R.is_demo?" Khí hậu DEMO.":""}</p>`)}
async function runS3(){const c=s3st();if(!c.crit.length){toast("Chọn ít nhất 1 tiêu chí biến động.","err");return}spin("#spS3",true);
 try{S3R=await api("/api/scenarios",Object.assign(evalPayload({}),{scen:{crit:c.crit,mag:c.mag,base:c.base}}));c.plus=null;c.minus=null;save();renderS3Res()}catch(e){toast(e.message,"err")}spin("#spS3",false)}
$("#s3cfg")&&$("#s3cfg").addEventListener("change",e=>{const c=s3st(),t=e.target;
 if(t.dataset.s3c){const k=t.dataset.s3c,i=c.crit.indexOf(k);if(t.checked&&i<0)c.crit.push(k);if(!t.checked&&i>=0)c.crit.splice(i,1);S3R=null;save();renderS3();return}
 if(t.dataset.s3m){c.mag[t.dataset.s3m]=Math.abs(+t.value||0);S3R=null;save();renderS3Res()}});
$("#s3cfg")&&$("#s3cfg").addEventListener("click",e=>{const b=e.target.closest("[data-s3b]");if(b){s3st().base=b.dataset.s3b;S3R=null;save();renderS3();return}if(e.target.id==="bS3")runS3()});
$("#s3res")&&$("#s3res").addEventListener("change",e=>{const s=e.target.dataset.s3sel;if(!s)return;s3st()[s]=e.target.value;save();renderS3Res()});

/* nhóm tác giả: thanh bên + trang Nguồn (email lấy từ cấu hình máy chủ) */
function renderAuthors(){const A=(META&&META.authors)||[];if(!A.length)return;
 const one=(a,big)=>`<span class="au">${big?`<i>${esc(a.name.split(" ").slice(-1)[0][0])}</i>`:""}<span><b>${esc(a.name)}</b>${a.email?`<a href="mailto:${esc(a.email)}" title="${esc(a.email)}">${esc(a.email)}</a>`:`<small>chưa đặt email trong .env</small>`}</span></span>`;
 const s=$("#authSide");if(s)s.innerHTML=`<b class="ah">Nhóm tác giả</b>`+A.map(a=>one(a)).join("");
 const p=$("#authSrc");if(p)p.innerHTML=A.map(a=>one(a,true)).join("")}

/* ---------- cảnh thời tiết phản ứng ngay với thanh kéo ---------- */
const lerpC=(a,b,k)=>a.map((v,i)=>Math.round(v+(b[i]-v)*k)),rgbS=a=>`rgb(${a.join(",")})`;
function weatherScene(t,p,crop,health){if(health==null)health=1;const h=Math.max(-.5,Math.min(1,t/4)),hp=Math.max(0,h),cd=Math.max(0,-h),wet=Math.max(0,p)/30,dry=Math.max(0,-p)/40,w=Math.min(1,hp*.7+dry*.85);
 const top=lerpC(lerpC([143,208,245],[247,166,92],hp),[150,175,205],cd*.8),bot=lerpC(lerpC([230,245,252],[255,226,186],hp),[226,236,244],cd*.8);
 const nCl=Math.max(1,Math.min(5,2+Math.round(wet*3)-Math.round(dry*1.4))),dark=wet>.3;
 let o=`<svg viewBox="0 0 1000 230" preserveAspectRatio="xMidYMax slice" role="img" aria-label="Minh họa thời tiết theo thanh kéo"><defs><linearGradient id="wsSky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${rgbS(top)}"/><stop offset="1" stop-color="${rgbS(bot)}"/></linearGradient></defs><rect width="1000" height="230" fill="url(#wsSky)"/>`;
 o+=`<g opacity="${Math.max(.25,1-wet*.75).toFixed(2)}">${ART.sunAt(870,66,26+hp*14)}</g>`;
 if(hp>.3)o+=[0,1,2].map(i=>`<path class="hz" style="animation-delay:${i*.4}s" d="M${380+i*160} ${162-i*4}q15-8 30 0t30 0 30 0 30 0" fill="none" stroke="rgba(255,255,255,${(.55*hp).toFixed(2)})" stroke-width="3" stroke-linecap="round"/>`).join("");
 const cx=[110,340,590,780,950];for(let i=0;i<nCl;i++){o+=`<g class="cm" style="animation-delay:${i*-2.3}s;animation-duration:${8+i*1.7}s">${ART.cloud(cx[i]-60,8+(i%2)*18,2+(i%3)*.25,dark?"gClD":"gCl")}</g>`}
 if(wet>.12){const n=Math.round(10+wet*30);for(let i=0;i<n;i++){const x=20+((i*997)%960),y=64+(i*37)%30;o+=`<line class="rd" x1="${x}" y1="${y}" x2="${x-5}" y2="${y+15}" stroke="#7FC3EE" stroke-width="2.4" stroke-linecap="round" style="animation-delay:${((i*.13)%1).toFixed(2)}s;animation-duration:${(.7+(i%3)*.12).toFixed(2)}s"/>`}}
 o+=`<path d="M0 178q50-9 100 0t100 0 100 0 100 0 100 0 100 0 100 0 100 0 100 0 100 0V230H0z" fill="url(#gSoil)"/><path d="M0 178q50-9 100 0t100 0 100 0 100 0 100 0 100 0 100 0 100 0 100 0 100 0" fill="none" stroke="#5DB05B" stroke-width="7" stroke-linecap="round"/>`;
 if(dry>.25)o+=`<rect y="178" width="1000" height="52" fill="#EBD9A6" opacity="${(dry*.4).toFixed(2)}"/><g stroke="#5E3A1D" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="${Math.min(1,dry*1.2).toFixed(2)}"><path d="M120 230l10-22-8-12M340 230l-6-18 11-10M560 230l8-24-9-14M790 230l-9-20 12-12M930 230l4-16-7-12"/></g>`;
 if(wet>.5)o+=[220,640].map(x=>`<ellipse cx="${x}" cy="183" rx="${40+wet*20}" ry="6" fill="url(#gWater)" opacity=".85"/>`).join("");
 if(crop&&ART.C[crop]){const h=Math.max(0,Math.min(1,health)),dead=h<.3,sat=(.25+.75*Math.min(1,h/.8)).toFixed(2),tint=((1-Math.min(1,h/.8))*.22).toFixed(3);
  o+=`<defs><filter id="wsH" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="${sat}"/><feComponentTransfer><feFuncR type="linear" slope="1" intercept="${tint}"/><feFuncG type="linear" slope="${(1-tint*.6).toFixed(3)}"/><feFuncB type="linear" slope="${(1-tint*2).toFixed(3)}"/></feComponentTransfer></filter></defs>`;
  const amp=dead?72:h>=.8?3:h>=.55?11:24,sy=dead?.75:h>=.8?1:h>=.55?.93:.84,sc=1.55*(dead?.9:1);
  for(let i=0;i<9;i++){const x=58+i*110+(i%2)*8,bend=(i%2?1:-1)*(amp+w*8)*(dead?1:(.7+.3*((i*37)%10)/10));
   o+=`<g transform="translate(${x} 186) rotate(${bend.toFixed(1)}) scale(${sc.toFixed(2)} ${(sc*sy).toFixed(2)})"><g filter="url(#wsH)"><svg x="-24" y="-47" width="48" height="48" viewBox="0 0 48 48" overflow="visible">${ART.C[crop]}</svg></g></g>`}
  return o+"</svg>"}
 const col=lerpC([63,156,79],[190,160,80],w),dk=lerpC([40,120,64],[150,120,60],w),sh=34+wet*12-dry*10;
 for(let i=0;i<16;i++){const x=36+i*60,bend=(i%2?1:-1)*w*34,drop2=w*10;o+=`<g transform="translate(${x} 182) rotate(${bend.toFixed(1)})"><path d="M0 0V${(-sh).toFixed(0)}" stroke="${rgbS(dk)}" stroke-width="3.6" stroke-linecap="round"/><path d="M0 ${(-(sh*.58)).toFixed(0)}C-4 ${(-(sh*.9-drop2)).toFixed(0)} -20 ${(-(sh*.9-drop2*1.4)).toFixed(0)} -26 ${(-(sh*.62-drop2*1.6)).toFixed(0)} -16 ${(-(sh*.42)).toFixed(0)} -5 ${(-(sh*.45)).toFixed(0)} 0 ${(-(sh*.58)).toFixed(0)}z" fill="${rgbS(col)}" stroke="${rgbS(dk)}" stroke-width="1"/><path d="M0 ${(-(sh*.78)).toFixed(0)}C4 ${(-(sh*1.08-drop2)).toFixed(0)} 20 ${(-(sh*1.08-drop2*1.4)).toFixed(0)} 26 ${(-(sh*.82-drop2*1.6)).toFixed(0)} 16 ${(-(sh*.62)).toFixed(0)} 5 ${(-(sh*.65)).toFixed(0)} 0 ${(-(sh*.78)).toFixed(0)}z" fill="${rgbS(col)}" stroke="${rgbS(dk)}" stroke-width="1"/></g>`}
 return o+"</svg>"}
function gaugeT(t){const k=Math.max(0,Math.min(1,(t+2)/6)),col=t>=.5?"#E0452E":t<=-.5?"#3A8FD0":"#E8A21E",y=44-k*30;return `<svg viewBox="0 0 64 64"><rect x="26" y="6" width="12" height="40" rx="6" fill="#fff" stroke="#C9D3DC" stroke-width="1.6"/><rect x="29.8" y="${y.toFixed(1)}" width="4.4" height="${(48-y).toFixed(1)}" rx="2.2" fill="${col}"/><circle cx="32" cy="50" r="10" fill="${col}" stroke="rgba(0,0,0,.18)"/><circle cx="29" cy="47" r="2.6" fill="#fff" opacity=".55"/><g stroke="#8A97A3" stroke-width="1.6" stroke-linecap="round"><path d="M42 12h5M42 19h3M42 26h5M42 33h3M42 40h5"/></g></svg>`}
function gaugeP(p){const k=Math.max(0,Math.min(1,(p+40)/70)),y=(48-k*34).toFixed(1);return `<svg viewBox="0 0 64 64"><clipPath id="gpc"><path d="M17.6 12h28.8l-2.8 43.5H20.4z"/></clipPath><path d="M16 10h32l-3 46a3 3 0 0 1-3 2.6H22a3 3 0 0 1-3-2.6z" fill="#fff" stroke="#C9D3DC" stroke-width="1.6"/><g clip-path="url(#gpc)"><rect x="10" y="${y}" width="44" height="50" fill="url(#gWater)" opacity=".92"/><path d="M12 ${y}q5-4 10 0t10 0 10 0 10 0" stroke="#fff" stroke-width="1.6" fill="none" opacity=".7"/></g><g stroke="#8A97A3" stroke-width="1.5" stroke-linecap="round"><path d="M48 20h4M48 30h3M48 40h4M48 50h3"/></g></svg>`}


</script></body></html>
"""

# ───────────────────────── TỪ ĐIỂN SONG NGỮ (khóa tiếng Việt → tiếng Anh; {} = phần thay đổi: số, tên cây, ngày…) ─────────────────────────
# Thêm câu mới: chép đúng câu tiếng Việt hiển thị trên giao diện làm khóa. Thuật ngữ theo FAO-56/FAO-33, USDA Soil Survey Manual, RUSLE, ECOCROP.
I18N_EN = {
    "FARM ADAPT là công cụ HỖ TRỢ: chỉ ra mức độ phù hợp dựa trên dữ liệu quan sát Trái Đất của NASA, dữ liệu đất mở và thông tin bạn nhập. Công cụ không thay thế kinh nghiệm của nông dân hay tư vấn của chuyên gia nông học địa phương. Giống, lịch gieo thực tế, thị trường, sâu bệnh, vốn và lao động vẫn cần phán đoán của con người.": "FARM ADAPT is a DECISION-SUPPORT tool: it shows how suitable each option is based on NASA Earth observation data, open soil data and the information you enter. It does not replace farmers' experience or advice from local agronomists. Varieties, actual planting dates, markets, pests and diseases, capital and labour still require human judgement.",
    "Đất nghỉ trong chuỗi = bỏ qua một lượt gieo của cây kế tiếp (cây đó gieo vào cửa sổ gieo của năm sau). Khoảng trống tự nhiên giữa ngày thu và ngày gieo kế tiếp (ví dụ qua mùa đông) KHÔNG coi là đất nghỉ.": "Fallow in a sequence = skipping one sowing turn of the next crop (that crop is sown in the following year's planting window). The natural gap between harvest and the next sowing (e.g. over winter) is NOT counted as fallow.",
    "Ngũ cốc": "Cereals",
    "Họ đậu": "Legumes",
    "nhẹ": "light",
    "trung bình": "medium",
    "nặng": "heavy",
    "cây kén đất": "nutrient-demanding crop",
    "cây chịu đất nghèo": "tolerant of poor soils",
    "Đất nghỉ": "Fallow",
    "Không có yêu cầu sinh thái: coi là phương án luôn khả thi, chỉ so sánh qua điểm MCA con (làm ở bước sau).": "No ecological requirements: treated as an always-feasible option, compared only through MCA sub-scores (later step).",
    "Đất nghỉ không có yêu cầu sinh thái: coi là phương án luôn khả thi, chỉ so sánh qua điểm MCA con.": "Fallow has no ecological requirements: it is treated as an always-feasible option and compared only through MCA sub-scores.",
    "Mưa trong ECOCROP là mưa cả năm; khi đánh giá theo vụ nên dùng B1 (nhu cầu nước cả vụ) để so với mưa và ẩm đất của vụ.": "ECOCROP rainfall is annual rainfall; for season-based evaluation use B1 (seasonal crop water requirement) to compare against in-season rainfall and soil moisture.",
    "Mưa GPM IMERG (mm/tháng) — dùng cho A2, B1": "GPM IMERG precipitation (mm/month) — used for A2, B1",
    "Độ ẩm vùng rễ SMAP L4 (m³/m³) — dùng cho B1": "SMAP L4 root-zone soil moisture (m³/m³) — used for B1",
    "NDVI (MODIS/Landsat) — tham khảo": "NDVI (MODIS/Landsat) — reference only",
    "Nhiệt độ bề mặt LST (MODIS/ECOSTRESS, °C) — chỉ để tìm điểm nóng": "Land surface temperature LST (MODIS/ECOSTRESS, °C) — for hotspot detection only",
    "Cát": "Sand",
    "Cát pha thịt": "Loamy sand",
    "Thịt pha cát": "Sandy loam",
    "Thịt": "Loam",
    "Thịt pha limon (bột)": "Silt loam",
    "Limon (bột)": "Silt",
    "Thịt pha sét – cát": "Sandy clay loam",
    "Thịt pha sét": "Clay loam",
    "Thịt pha sét – limon": "Silty clay loam",
    "Sét pha cát": "Sandy clay",
    "Sét pha limon": "Silty clay",
    "Sét": "Clay",
    "Khí hậu – thời tiết": "Climate – weather",
    "Nước – độ ẩm": "Water – moisture",
    "Đất": "Soil",
    "Địa hình": "Terrain",
    "Che phủ đất": "Land cover",
    "Kinh tế": "Economics",
    "A1 lúa mì đông: tháng ngủ đông (TB < 5°C) không tính vào nhiệt độ vụ — giả định để khớp ví dụ trong tài liệu (TB tháng 3–6).": "A1 winter wheat: dormant months (mean < 5°C) are excluded from the season temperature — an assumption made to match the worked example in the document (mean of Mar–Jun).",
    "Tháng trong vụ của cây = từ ngày bắt đầu vụ, kéo dài min(độ dài vụ, số ngày gieo → thu điển hình theo lịch Kansas).": "In-season months of a crop = from the season start date for min(season length, typical sowing → harvest days per the Kansas calendar).",
    "C2: cách gom 12 cấp cơ giới USDA về 3 nhóm và điểm 0,5 cho nhóm chịu đựng là giả định.": "C2: grouping the 12 USDA texture classes into 3 groups and giving a score of 0.5 to the tolerated group are assumptions.",
    "C1 cao lương, đậu tương: chỉ dùng cận dưới (sâu hơn 150 cm vẫn = 1).": "C1 sorghum, soybean: only the lower bound is used (deeper than 150 cm still = 1).",
    "B1: khi chưa có SMAP, θ đầu vụ ≈ độ ẩm vùng rễ NASA POWER (GWETROOT, 0–1) × độ rỗng đất; khi chưa có θ điểm héo/đồng ruộng từ SSURGO, dùng bảng Rawls et al. (1982) theo cấp cơ giới.": "B1: without SMAP, initial θ ≈ NASA POWER root-zone soil wetness (GWETROOT, 0–1) × soil porosity; without SSURGO wilting point/field capacity, the Rawls et al. (1982) table by texture class is used.",
    "E1 cao lương tạm lấy bằng ngô (C = 0,38) vì nguồn Panagos et al. không có cao lương.": "E1 for sorghum is temporarily set equal to maize (C = 0.38) because Panagos et al. do not list sorghum.",
    "K1: lịch gieo – thu là số liệu Kansas; ở vùng khác nên tắt K1 hoặc thay lịch địa phương (data/crops.json). Ngày gieo sớm nhất = ngày bắt đầu vụ do bạn khai báo (chưa dùng CDL/NDVI để suy ngày thu vụ trước).": "K1: sowing–harvest calendars are Kansas data; in other regions turn K1 off or replace with a local calendar (data/crops.json). Earliest sowing date = the season start date you declare (CDL/NDVI is not yet used to infer the previous harvest date).",
    "K1 sương giá: ngày sương giá đầu thu = trung vị qua các năm của ngày đầu tiên từ 1/7 có T2M_MIN ≤ 0°C (NASA POWER); cây (trừ lúa mì đông chịu rét) bị loại nếu ngày gieo + chu kỳ tối thiểu vượt qua ngày này.": "K1 frost: first fall frost date = median across years of the first day from 1 July with T2M_MIN ≤ 0°C (NASA POWER); crops (except cold-hardy winter wheat) are excluded if sowing date + minimum cycle passes this date.",
    "SoilGrids 2.0 (mô hình 250 m)": "SoilGrids 2.0 (250 m model)",
    "bạn nhập": "entered by you",
    "ví dụ mẫu": "sample example",
    "Hiệu ứng luân canh E(p,c) lấy từ Mudare et al. (2025) — trung bình toàn cầu, chưa riêng cho Kansas; dùng cả các cặp chưa có ý nghĩa thống kê.": "Rotation effect E(p,c) taken from Mudare et al. (2025) — a global mean, not Kansas-specific; pairs without statistical significance are also used.",
    "Cặp không có dữ liệu (cao lương → lúa mì, đất nghỉ → đậu tương): E = 0 (M = 1) và được báo trên giao diện.": "Pairs without data (sorghum → wheat, fallow → soybean): E = 0 (M = 1), flagged in the interface.",
    "Chế độ cặp: cây vụ trước = cây của vụ đang diễn ra; không có thì lấy cây của vụ gần nhất đã kết thúc; chưa khai báo → M = 1.": "Pair mode: previous crop = crop of the current season; if none, the crop of the most recently finished season; if not declared → M = 1.",
    "Chế độ chuỗi: vụ đầu chuỗi không nhân M (giả định không có cây trước); K3, K4 vẫn xét cặp cây vụ trước của thửa → cây đầu chuỗi.": "Sequence mode: the first season is not multiplied by M (assumes no previous crop); K3, K4 still check the field's previous crop → first crop of the sequence.",
    "Chế độ chuỗi: mỗi cây chiếm số ngày gieo → thu điển hình theo lịch Kansas trong CRD; gieo vào ngày sớm nhất hợp lệ trong cửa sổ gieo (± độ lệch K1).": "Sequence mode: each crop occupies the typical sowing → harvest days per the Kansas calendar in the CRD; sown on the earliest valid date in the planting window (± K1 tolerance).",
    "Chỉ giữ chuỗi “đầy”: sau cây cuối không còn cây nào gieo và thu kịp trước ngày kết thúc; phần thời gian còn lại là đất nghỉ tự nhiên.": "Only “full” sequences are kept: after the last crop no other crop can be sown and harvested before the end date; the remaining time is natural fallow.",
    "Vụ đất nghỉ không cộng điểm S và không tính vào T, nhưng ảnh hưởng cây sau qua M(đất nghỉ, c).": "A fallow season adds no S score and is not counted in T, but affects the next crop through M(fallow, c).",
    "F1: G = P × A × Y_base; chuẩn hóa G/G_max trên 4 cây ứng viên (G ≤ 0 → 0). Trong chuỗi, mỗi cây dùng F1 của chính nó; tổng G của chuỗi hiển thị riêng.": "F1: G = P × A × Y_base; normalised as G/G_max over the 4 candidate crops (G ≤ 0 → 0). In a sequence each crop uses its own F1; the sequence's total G is shown separately.",
    "Kịch bản 2^n: Δ+ mặc định là tổ hợp “nóng – khô” (A1↑, A2↓, A3↑, B1↓) khi tiêu chí đầu tiên được chọn tăng theo hướng đó, Δ− là tổ hợp ngược lại.": "2^n scenarios: Δ+ defaults to the “hot – dry” combination (A1↑, A2↓, A3↑, B1↓) when the first selected criterion increases in that direction; Δ− is the opposite combination.",
    "Chỉ số tăng năng suất khi luân canh cây A → cây B (Mudare et al. 2025) có nhiều cặp chưa có ý nghĩa thống kê — chưa đảm bảo có tác động.": "The yield-gain index for rotating crop A → crop B (Mudare et al. 2025) has many pairs without statistical significance — an effect is not guaranteed.",
    "Công thức kết hợp V = S × M và Score(P) chưa có dữ liệu thực nghiệm kiểm chứng.": "The combination formulas V = S × M and Score(P) have not yet been validated with experimental data.",
    "Vụ đầu chuỗi giả định không có cây trước (không nhân M); nhóm Đất (C) và Địa hình (D) giả định không đổi qua các vụ của chuỗi.": "The first season of a sequence is assumed to have no previous crop (no M multiplier); the Soil (C) and Terrain (D) groups are assumed constant across the seasons of a sequence.",
    "SMAP đo trên ô 9 km và chỉ tới độ sâu 1 m: với cây rễ sâu hơn 1 m (lúa mì, ngô) phần nước bên dưới không được tính.": "SMAP is measured on 9 km cells and only down to 1 m depth: for crops rooting deeper than 1 m (wheat, maize) water below is not counted.",
    "ETm của B1 lấy giá trị giữa khoảng trong CRD, chưa tính riêng theo khí hậu từng thửa (có thể nâng cấp bằng Σ Kc × ET0 theo FAO-56).": "B1 ETm uses the mid-range value in the CRD, not computed for each field's climate (could be upgraded with Σ Kc × ET0 per FAO-56).",
    "Bỏ tiêu chí độ ẩm đất lúc gieo vì đã nằm trong B1; mô hình không cảnh báo riêng rủi ro khó nảy mầm khi đất khô lúc gieo (đáng lưu ý với lúa mì đông gieo mùa thu).": "The soil-moisture-at-sowing criterion was dropped because it is already in B1; the model gives no separate warning of poor germination when the soil is dry at sowing (relevant for fall-sown winter wheat).",
    "Trọng số nhóm Kinh tế trong các bộ ưu tiên là giả định, chưa có tài liệu làm cơ sở; trọng số tiêu chí con chia đều trong nhóm.": "The Economics group weight in the priority profiles is an assumption without a documented basis; sub-criterion weights are split equally within each group.",
    "Bình thường": "Normal",
    "Chú ý": "Watch",
    "Cảnh báo": "Warning",
    "Nghiêm trọng": "Severe",
    "Ngưỡng CRD là ngưỡng cho cả vụ, không phân theo giai đoạn sinh trưởng; cây nhạy nhất lúc trổ cờ, ra hoa nhưng phương pháp 1 chưa phản ánh được.": "CRD thresholds apply to the whole season, not by growth stage; crops are most sensitive at tasseling and flowering, which method 1 does not yet capture.",
    "Phương pháp 2 cần chuỗi lịch sử đủ dài; SMAP chỉ có từ 2015 nên phân vị của B1 kém tin cậy hơn A1–A3 (hiện B1 dùng GWETROOT của NASA POWER).": "Method 2 needs a long enough historical record; SMAP only exists since 2015, so B1 percentiles are less reliable than A1–A3 (B1 currently uses NASA POWER GWETROOT).",
    "Độ trễ dữ liệu NASA POWER vài ngày (ALLSKY_KT có thể trễ hơn) khiến cảnh báo chậm so với thực tế; chưa dùng dự báo thời tiết để báo trước.": "NASA POWER data lag a few days (ALLSKY_KT may lag more), so warnings come later than reality; weather forecasts are not yet used for early warning.",
    "A2 theo ngưỡng nông học dùng tổng mưa 365 ngày gần nhất để so với ngưỡng mưa NĂM của ECOCROP; A2 theo thống kê dùng tổng 30 ngày.": "A2 with agronomic thresholds uses the last 365-day rainfall total against ECOCROP's ANNUAL rainfall thresholds; A2 with statistics uses the 30-day total.",
    "Lớp bản đồ dùng dịch vụ ảnh THEO THÁNG của NASA POWER (lưới ~0,5°), chỉ để xem; cảnh báo tính từ chuỗi NGÀY tại toạ độ thửa.": "The map layer uses NASA POWER's MONTHLY image service (~0.5° grid), for viewing only; warnings are computed from the DAILY series at the field's coordinates.",
    "Ví dụ trong tài liệu (lúa mì, m ≈ 2,8°C) tương ứng m = 10% bề rộng vùng chịu đựng; công cụ để mặc định 5% theo phần mô tả và cho phép chỉnh.": "The document's example (wheat, m ≈ 2.8°C) corresponds to m = 10% of the tolerance range width; the tool defaults to 5% per the description and lets you adjust it.",
    "Kênh email / thông báo đẩy mới lưu cấu hình, chưa gửi thật (cần hạ tầng triển khai).": "Email / push notification channels only save the settings and do not send yet (deployment infrastructure needed).",
    "~0,5°×0,625°, theo tháng": "~0.5°×0.625°, monthly",
    "ArcGIS ImageServer gis.earthdata.nasa.gov/portal/rest/services/POWER (không cần khóa) — exportImage theo biến (T2M, PRECTOTCORR_SUM, ALLSKY_KT, GWETTOP) & tháng": "ArcGIS ImageServer gis.earthdata.nasa.gov/portal/rest/services/POWER (no key required) — exportImage by variable (T2M, PRECTOTCORR_SUM, ALLSKY_KT, GWETTOP) & month",
    "9 km, 3 giờ": "9 km, 3-hourly",
    "Người dùng tải CSV từ NASA Earthdata / AppEEARS rồi nạp vào công cụ": "Users download a CSV from NASA Earthdata / AppEEARS and load it into the tool",
    "Reichle, R., et al. SMAP L4 Global 3-hourly 9 km EASE-Grid Surface and Root Zone Soil Moisture Geophysical Data (SPL4SMGP). NASA NSIDC DAAC. https://nsidc.org/data/spl4smgp — ghi số phiên bản và DOI theo trang dữ liệu lúc tải.": "Reichle, R., et al. SMAP L4 Global 3-hourly 9 km EASE-Grid Surface and Root Zone Soil Moisture Geophysical Data (SPL4SMGP). NASA NSIDC DAAC. https://nsidc.org/data/spl4smgp — record the version number and DOI from the data page at download time.",
    "Không dùng AI khi chạy: giao diện phiên bản này không có trợ lý AI. Mọi điểm số, xếp hạng, cảnh báo và câu giải thích đều do Python tính theo quy tắc.": "No AI at runtime: this version of the interface has no AI assistant. All scores, rankings, warnings and explanations are computed by Python using rules.",
    "Số liệu ECOCROP cho Triticum aestivum, trích lại tại Useful Tropical Plants (không mở được trang ECOCROP gốc)": "ECOCROP data for Triticum aestivum, as cited by Useful Tropical Plants (the original ECOCROP page could not be opened)",
    "FAO Irrigation & Drainage Paper 66, Bảng 1 (Ky mùa vụ, lấy từ Paper 33)": "FAO Irrigation & Drainage Paper 66, Table 1 (crop Ky, from Paper 33)",
    "Bảng yêu cầu đất đai cho ngô nhờ mưa, kiểu Sys et al. (1993)": "Land requirement table for rainfed maize, Sys et al. (1993) style",
    "USDA NASS Kansas Crop Progress, tuần kết thúc 11/7/2010": "USDA NASS Kansas Crop Progress, week ending 11 July 2010",
    "Yen et al. (2006), LUSET User's Guide, IRRI (dựa trên Sys et al. 1993) – dữ liệu trong gói R ALUES": "Yen et al. (2006), LUSET User's Guide, IRRI (based on Sys et al. 1993) – data in the R package ALUES",
    "Panagos et al. (2015), Land Use Policy 48, Bảng 1 – hệ số C hiệu chỉnh cho châu Âu": "Panagos et al. (2015), Land Use Policy 48, Table 1 – C-factors adjusted for Europe",
    "Quá mức": "Excessively drained",
    "Hơi quá mức": "Somewhat excessively drained",
    "Tốt": "Well drained",
    "Khá tốt": "Moderately well drained",
    "Hơi kém": "Somewhat poorly drained",
    "Kém": "Poorly drained",
    "Rất kém": "Very poorly drained",
    "Rất sáng": "Very bright",
    "Trời quang": "Clear sky",
    "Nhiều mây": "Cloudy",
    "Bóng râm": "Shade",
    "NASA POWER (MERRA-2 + GPM IMERG + CERES), lưới ~0,5°×0,625°": "NASA POWER (MERRA-2 + GPM IMERG + CERES), ~0.5°×0.625° grid",
    "DEMO — khí hậu MÔ PHỎNG theo vĩ độ (KHÔNG phải dữ liệu NASA)": "DEMO — SIMULATED climate by latitude (NOT NASA data)",
    "250 m, 16 ngày": "250 m, 16-day",
    "ORNL DAAC MODIS/VIIRS Web Service (REST, không cần khóa)": "ORNL DAAC MODIS/VIIRS Web Service (REST, no key required)",
    "1 km, 8 ngày": "1 km, 8-day",
    "0,1° (~11 km), tháng": "0.1° (~11 km), monthly",
    "NASA GES DISC OPeNDAP (cần EARTHDATA_TOKEN)": "NASA GES DISC OPeNDAP (EARTHDATA_TOKEN required)",
    "ISRIC REST API (không cần khóa, CC BY 4.0)": "ISRIC REST API (no key required, CC BY 4.0)",
    "đơn vị bản đồ đất 1:12.000–1:24.000 (chỉ Hoa Kỳ)": "soil map units 1:12,000–1:24,000 (United States only)",
    "Soil Data Access (SDA) REST, không cần khóa": "Soil Data Access (SDA) REST, no key required",
    "Soil Survey Staff, NRCS, USDA. Soil Survey Geographic (SSURGO) Database. Truy cập qua Soil Data Access: https://sdmdataaccess.nrcs.usda.gov/": "Soil Survey Staff, NRCS, USDA. Soil Survey Geographic (SSURGO) Database. Accessed via Soil Data Access: https://sdmdataaccess.nrcs.usda.gov/",
    "OpenTopoData public API (không cần khóa)": "OpenTopoData public API (no key required)",
    "C hữu cơ (%) = SOC (g/kg) / 10, trung bình 0–30 cm.": "Organic C (%) = SOC (g/kg) / 10, mean over 0–30 cm.",
    "Giá trị từ MÔ HÌNH 250 m, không phải mẫu đất của ruộng. Khoảng 5–95% thường rất rộng → nên đo pH/chất hữu cơ thực tế.": "Values from a 250 m MODEL, not a soil sample from your field. The 5–95% range is often very wide → measure pH/organic matter in the field.",
    "Giá trị đại diện của thành phần đất chính trong đơn vị bản đồ, tầng 0–30 cm; nên đối chiếu mẫu đất thực tế.": "Representative value of the dominant soil component in the map unit, 0–30 cm layer; compare with an actual soil sample.",
    "Độ dốc tính từ chênh cao SRTM ±150 m quanh điểm. SRTM đo cả nhà/cây; ở đồng bằng sai số vài mét có thể lấn át độ dốc thật — nên xác nhận.": "Slope computed from SRTM elevation differences ±150 m around the point. SRTM includes buildings/trees; on flat plains errors of a few metres can outweigh the true slope — please verify.",
    "Các nhóm như nhau": "Equal groups",
    "Mặc định khi chưa chọn ưu tiên": "Default when no priority is chosen",
    "Ưu tiên lợi nhuận": "Profit first",
    "Ghi chú, FarmSTEPS, RotationARM, Organic": "Notes, FarmSTEPS, RotationARM, Organic",
    "Ưu tiên giảm rủi ro": "Risk reduction first",
    "RotationARM, Review CRM, Ghi chú": "RotationARM, Review CRM, Notes",
    "Ưu tiên tiết kiệm nước": "Water saving first",
    "Ghi chú": "Notes",
    "Ưu tiên cải thiện đất, chống xói mòn": "Soil improvement & erosion control first",
    "Ghi chú, Organic, FarmSTEPS, UNCCD": "Notes, Organic, FarmSTEPS, UNCCD",
    "Ưu tiên dinh dưỡng, tự cung": "Nutrition & self-sufficiency first",
    "điểm = 1 − C": "score = 1 − C",
    "Mùa vụ & điều kiện bắt buộc": "Seasons & mandatory constraints",
    "Dữ liệu đất & địa hình": "Soil & terrain data",
    "Kết quả & kịch bản": "Results & scenarios",
    "Giả định của mô hình": "Model assumptions",
    "Giám sát & cảnh báo": "Monitoring & warnings",
    "Hàng là cây trước, cột là cây sau. Mỗi ô: % thay đổi năng suất cây sau so với độc canh [khoảng tin cậy 95%], n = cỡ mẫu. In đậm = có ý nghĩa thống kê (khoảng tin cậy không chứa 0). Ô “không có dữ liệu” được tính E = 0.": "Rows are the previous crop, columns the following crop. Each cell: % yield change of the following crop compared with monoculture [95% confidence interval], n = sample size. Bold = statistically significant (confidence interval excludes 0). “No data” cells are counted as E = 0.",
    "Bạn nhập (bước 2)": "Entered by you (step 2)",
    "Chuỗi": "Sequence",
    "Luân canh, kinh tế & hạn chế nghiên cứu": "Rotation, economics & research limitations",
    "Nhiệt độ": "Temperature",
    "TB 7 ngày gần nhất": "Mean of last 7 days",
    "Lượng mưa": "Rainfall",
    "Tổng 30 ngày gần nhất": "Total of last 30 days",
    "NASA POWER PRECTOTCORR (hiệu chỉnh theo GPM IMERG)": "NASA POWER PRECTOTCORR (bias-corrected with GPM IMERG)",
    "Bức xạ (Kt)": "Radiation (Kt)",
    "Cân bằng nước": "Water balance",
    "Ẩm vùng rễ mới nhất · Ya/Ym từ đầu vụ": "Latest root-zone moisture · Ya/Ym since season start",
    "NASA POWER GWETROOT (+ SMAP nếu có)": "NASA POWER GWETROOT (+ SMAP if available)",
    "Nguyễn Mai Chi": "Nguyễn Mai Chi",
    "Nguyễn Mạnh Đạt": "Nguyễn Mạnh Đạt",
    "Chưa có kết quả.": "No results yet.",
    "Vụ cần quyết định: {} (từ {}, {} ngày).": "Season to decide: {} (from {}, {} days).",
    "Đây chỉ là gợi ý từ dữ liệu NASA, dữ liệu đất mở và thông tin bạn nhập. Hãy trao đổi với cán bộ khuyến nông địa phương trước khi quyết định.": "This is only a suggestion based on NASA data, open soil data and the information you entered. Please consult your local extension officer before deciding.",
    "3. Chi tiết theo cây": "3. Details by crop",
    "K1 sương giá": "K1 frost",
    "Bước 3 – Khí hậu": "Step 3 – Climate",
    "Giám sát – chuỗi ngày & cảnh báo": "Monitoring – daily series & warnings",
    "Giám sát – bản đồ A1, A2, A3, B1": "Monitoring – A1, A2, A3, B1 maps",
    "Bước 3 – tham khảo": "Step 3 – reference",
    "Bước 3 – tìm điểm nóng": "Step 3 – hotspot detection",
    "Bản đồ nền & tìm địa điểm": "Basemaps & place search",
    "Thư viện & mã nguồn mở": "Libraries & open source",
    "Phương pháp & tài liệu khoa học": "Methods & scientific literature",
    "Điểm phù hợp, kịch bản thời tiết và cảnh báo được tính bằng công thức trong BaiToan1.md và GiamSat.md.": "Suitability scores, weather scenarios and warnings are computed with the formulas in BaiToan1.md and GiamSat.md.",
    "Câu chữ “Vì sao & lưu ý” và báo cáo in được ghép từ số liệu đã tính, không qua mô hình ngôn ngữ.": "The “Why & notes” text and the printable report are assembled from computed values, not generated by a language model.",
    "Mã nguồn vẫn giữ các endpoint /api/ai/* (tắt mặc định, cần khóa API) cho phiên bản sau; nếu bật lại, phải khai báo lại ở đây.": "The source code still keeps the /api/ai/* endpoints (off by default, API key required) for a future version; if re-enabled, they must be declared here again.",
    "Không có ảnh, video hay dữ liệu nào do AI tạo trong giao diện.": "No images, videos or data generated by AI are used in the interface.",
    "Mã nguồn farm_adapt (Python + HTML/JS), bộ máy đánh giá SMCA, giao diện, minh hoạ vector SVG viết bằng mã": "farm_adapt source code (Python + HTML/JS), SMCA evaluation engine, interface, SVG vector illustrations written as code",
    "Sinh và tái cấu trúc mã theo đặc tả của nhóm (BaiToan1.md, CRD.md); nhóm rà soát, chạy thử và đối chiếu công thức với ví dụ trong tài liệu.": "Generating and refactoring code from the team's specifications (BaiToan1.md, CRD.md); the team reviewed, tested and checked the formulas against the worked examples in the documents.",
    "0,5°×0,625° khí tượng; 1°×1° bức xạ; chuỗi ngày": "0.5°×0.625° meteorology; 1°×1° radiation; daily series",
    "POWER API (không cần khóa)": "POWER API (no key required)",
    "Lúa mì đông": "Winter wheat",
    "Cao lương": "Grain sorghum",
    "Ngô": "Maize",
    "Đậu tương": "Soybean",
    "Lưới khí tượng ~0,5°×0,625° (~50 km): phản ánh KHÍ HẬU KHU VỰC, chưa phải vi khí hậu từng thửa. Nên hiệu chỉnh bằng số đo mưa/nhiệt tại ruộng.": "Meteorological grid ~0.5°×0.625° (~50 km): reflects the REGIONAL CLIMATE, not the microclimate of each field. Calibrate with on-farm rainfall/temperature measurements.",
    "đệm trên đĩa": "disk cache",
    "tải mới từ NASA POWER": "freshly downloaded from NASA POWER",
    "File quá ít dòng (cần ít nhất ~6 điểm dữ liệu).": "File has too few rows (at least ~6 data points required).",
    "Không đọc được ≥6 cặp (ngày, giá trị). Cần cột ngày dạng YYYY-MM-DD và cột giá trị số.": "Could not read ≥6 (date, value) pairs. A date column in YYYY-MM-DD format and a numeric value column are required.",
    "Không gọi được {}: {}": "Could not reach {}: {}",
    "Pixel 250 m (~6 ha) có thể lẫn nhiều thửa nhỏ → kết luận ở mức tiểu vùng. Đã bỏ quan sát mây/tuyết (pixel reliability ≥ 2).": "A 250 m pixel (~6 ha) may mix several small fields → conclusions at sub-regional level. Cloud/snow observations removed (pixel reliability ≥ 2).",
    "Nhiệt độ BỀ MẶT ban ngày (đất/tán lá), thường cao hơn nhiệt độ không khí vài độ.": "Daytime SURFACE temperature (soil/canopy), usually a few degrees higher than air temperature.",
    "Chưa có EARTHDATA_TOKEN trong .env — cần token NASA Earthdata (miễn phí) để lấy mưa GPM IMERG.": "No EARTHDATA_TOKEN in .env — a (free) NASA Earthdata token is required to fetch GPM IMERG precipitation.",
    "SoilGrids không có dữ liệu tại điểm này (có thể là mặt nước/đô thị).": "SoilGrids has no data at this point (may be water/urban area).",
    "Cấp cơ giới theo tam giác kết cấu đất USDA từ % cát/limon/sét SoilGrids (0–30 cm).": "Texture class from the USDA soil texture triangle using SoilGrids % sand/silt/clay (0–30 cm).",
    "Đạm tổng số (g/kg). CHƯA quy ra thấp/vừa/cao vì chưa có ngưỡng có nguồn — mức đạm để nông dân nhập.": "Total nitrogen (g/kg). NOT yet classified as low/medium/high because no sourced thresholds exist — nitrogen level is entered by the farmer.",
    "C hữu cơ = chất hữu cơ (om_r) / 1,724.": "Organic C = organic matter (om_r) / 1.724.",
    "Bão hòa bazơ = tổng bazơ / CEC pH7 × 100.": "Base saturation = sum of bases / CEC at pH 7 × 100.",
    "Độ sâu tới tầng cản (corestrictions).": "Depth to restrictive layer (corestrictions).",
    "Độ dốc đại diện của thành phần đất (slope_r).": "Representative slope of the soil component (slope_r).",
    "Nhiệt độ không khí ngày (T2M) các năm lịch sử": "Daily air temperature (T2M) over historical years",
    "NASA POWER (tự lấy)": "NASA POWER (automatic)",
    "TB nhiệt độ các tháng trong vụ của cây, trung bình qua các năm → hàm hình thang theo CRD.": "Mean temperature of the crop's in-season months, averaged across years → trapezoidal function per the CRD.",
    "Lượng mưa năm": "Annual rainfall",
    "Mưa tháng các năm lịch sử": "Monthly rainfall over historical years",
    "GPM IMERG (tự lấy, cần EARTHDATA_TOKEN) · dự phòng NASA POWER": "GPM IMERG (automatic, EARTHDATA_TOKEN required) · fallback NASA POWER",
    "Tổng mưa 12 tháng, trung bình qua các năm → hình thang. Có tưới → 1.": "12-month rainfall total, averaged across years → trapezoid. Irrigated → 1.",
    "Bức xạ mặt trời": "Solar radiation",
    "Chỉ số trong suốt khí quyển Kt (ALLSKY_KT)": "Clearness index Kt (ALLSKY_KT)",
    "Kt TB trong vụ → Rất sáng (≥ 0,60) = 1 · Trời quang (0,50–0,60) = 0,5 · Nhiều mây (0,35–0,50) hoặc bóng râm (< 0,35) = 0.": "Mean in-season Kt → Very bright (≥ 0.60) = 1 · Clear sky (0.50–0.60) = 0.5 · Cloudy (0.35–0.50) or shade (< 0.35) = 0.",
    "Mưa trong vụ + ẩm đất đầu vụ (θ) + θ điểm héo + độ sâu rễ": "In-season rainfall + initial soil moisture (θ) + wilting point θ + rooting depth",
    "IMERG/POWER + SMAP (CSV) hoặc POWER GWETROOT + SSURGO": "IMERG/POWER + SMAP (CSV) or POWER GWETROOT + SSURGO",
    "Ya/Ym = 1 − Ky × (1 − ETa/ETm), ETa = mưa vụ + nước đất đầu vụ + tưới; giới hạn [0; 1]. Có tưới → 1.": "Ya/Ym = 1 − Ky × (1 − ETa/ETm), ETa = seasonal rainfall + initial soil water + irrigation; bounded to [0; 1]. Irrigated → 1.",
    "Độ sâu tầng đất": "Soil depth",
    "Độ sâu tới tầng cản": "Depth to restrictive layer",
    "SSURGO (tự lấy – chỉ Hoa Kỳ)": "SSURGO (automatic – United States only)",
    "Cây có bảng Sys: S1/S2/S3/N = 1/0,75/0,5/0; cây chỉ có ECOCROP: hình thang.": "Crops with a Sys table: S1/S2/S3/N = 1/0.75/0.5/0; crops with ECOCROP only: trapezoid.",
    "Thành phần cơ giới": "Soil texture",
    "Cấp cơ giới USDA tầng mặt": "USDA texture class of the topsoil",
    "SSURGO (Hoa Kỳ) · SoilGrids (toàn cầu)": "SSURGO (United States) · SoilGrids (global)",
    "Nhẹ / trung bình / nặng; nhóm tối ưu = 1, chịu đựng = 0,5, loại = 0.": "Light / medium / heavy; optimal group = 1, tolerated = 0.5, excluded = 0.",
    "pH, độ chua": "pH, acidity",
    "pH (1:1 trong nước)": "pH (1:1 in water)",
    "Hàm hình thang theo CRD.": "Trapezoidal function per the CRD.",
    "Thoát nước, úng": "Drainage, waterlogging",
    "Cấp thoát nước (7 cấp)": "Drainage class (7 classes)",
    "Quá mức/hơi quá mức/tốt = 1; khá tốt 0,75; hơi kém 0,5; kém 0,25; rất kém 0. Cây ưa úng: đảo chiều.": "Excessively/somewhat excessively/well drained = 1; moderately well 0.75; somewhat poorly 0.5; poorly 0.25; very poorly 0. Waterlogging-tolerant crops: reversed.",
    "Độ phì, CEC": "Fertility, CEC",
    "Bảng CEC theo nhóm cây: kén đất (lúa mì, ngô) > 24 → 1, 16–24 → 0,75, 10–16 → 0,5, < 10 → 0; chịu đất nghèo (cao lương, đậu tương) > 24 → 1, 16–24 → 1, 10–16 → 0,75, < 10 → 0,5.": "CEC table by crop group: nutrient-demanding (wheat, maize) > 24 → 1, 16–24 → 0.75, 10–16 → 0.5, < 10 → 0; tolerant of poor soils (sorghum, soybean) > 24 → 1, 16–24 → 1, 10–16 → 0.75, < 10 → 0.5.",
    "Độ mặn (EC)": "Salinity (EC)",
    "Độ dẫn điện ECe": "Electrical conductivity ECe",
    "1 nếu EC ≤ ngưỡng bắt đầu giảm; 0 nếu ≥ ngưỡng mất trắng; ở giữa giảm tuyến tính (FAO).": "1 if EC ≤ yield-decline threshold; 0 if ≥ zero-yield threshold; linear decrease in between (FAO).",
    "Độ dốc": "Slope",
    "Độ dốc (%)": "Slope (%)",
    "SRTM 30 m (tự lấy) · SSURGO": "SRTM 30 m (automatic) · SSURGO",
    "Hệ số che phủ C (RUSLE) của cây": "Crop cover-management factor C (RUSLE)",
    "Có sẵn trong CRD": "Built into the CRD",
    "Điểm = 1 − C (C càng thấp, cây che phủ đất càng tốt).": "Score = 1 − C (the lower C, the better the crop protects the soil).",
    "Giá trị kinh tế": "Economic value",
    "Diện tích ruộng A (ha), giá bán P (USD/tấn) và năng suất cơ sở Y_base (tấn/ha) của từng cây": "Field area A (ha), selling price P (USD/t) and baseline yield Y_base (t/ha) of each crop",
    "G = P × A × Y_base; điểm = (G − G_min)/(G_max − G_min) với G_min = 0 và G_max là G lớn nhất trong các cây đang xét (G ≤ 0 → 0). Không dùng CRD.": "G = P × A × Y_base; score = (G − G_min)/(G_max − G_min) with G_min = 0 and G_max the largest G among the crops considered (G ≤ 0 → 0). The CRD is not used.",
    "Có tưới": "Irrigated",
    "ngưỡng mưa ECOCROP chỉ áp dụng cho ruộng không tưới": "ECOCROP rainfall thresholds only apply to non-irrigated fields",
    "Chế độ tưới do bạn chọn": "Irrigation regime chosen by you",
    "Rất sáng ≥ 0,60 → 1 · Trời quang 0,50–0,60 → 0,5 · Nhiều mây / bóng râm → 0": "Very bright ≥ 0.60 → 1 · Clear sky 0.50–0.60 → 0.5 · Cloudy / shade → 0",
    "Có tưới đủ (I = ETm)": "Fully irrigated (I = ETm)",
    "{}: {} (điểm {})": "{}: {} (score {})",
    "Chưa có vị trí ruộng hợp lệ (bước 1).": "No valid field location yet (step 1).",
    "Chuỗi luân canh": "Crop rotation sequence",
    "Ruộng nằm ngoài Kansas nhưng K1 đang dùng lịch gieo – thu của Kansas: nên tắt K1 hoặc thay lịch địa phương.": "The field is outside Kansas but K1 uses Kansas sowing–harvest calendars: turn K1 off or replace with a local calendar.",
    "Đang dùng khí hậu MÔ PHỎNG (DEMO) vì không gọi được NASA POWER — không dùng để quyết định thật.": "Using SIMULATED climate (DEMO) because NASA POWER could not be reached — do not use for real decisions.",
    "Chọn ít nhất 1 tiêu chí biến động trong A1, A2, A3, B1.": "Select at least 1 varying criterion among A1, A2, A3, B1.",
    "Chưa khai báo vụ nào (bước 2).": "No season declared yet (step 2).",
    "FARM ADAPT là công cụ HỖ TRỢ, không thay thế kinh nghiệm của nông dân và tư vấn của chuyên gia nông học địa phương; giống, lịch gieo thực tế, thị trường, sâu bệnh, vốn và lao động vẫn cần phán đoán của con người.": "FARM ADAPT is a DECISION-SUPPORT tool and does not replace farmers' experience or advice from local agronomists; varieties, actual planting dates, markets, pests and diseases, capital and labour still require human judgement.",
    "Khi không gọi được NASA POWER, công cụ dùng khí hậu MÔ PHỎNG (DEMO) để chạy thử và gắn nhãn DEMO ở thanh bên — không dùng số này để quyết định.": "When NASA POWER cannot be reached, the tool uses SIMULATED climate (DEMO) for testing and shows a DEMO label in the sidebar — do not use these numbers for decisions.",
    "K1 dùng lịch gieo – thu của Kansas (K-State, USDA NASS); ruộng ở vùng khác nên tắt K1 hoặc thay lịch địa phương.": "K1 uses Kansas sowing–harvest calendars (K-State, USDA NASS); for fields in other regions, turn K1 off or replace with a local calendar.",
    "K2 là danh sách cây bạn không muốn trồng; cây bị loại vẫn được chấm điểm để tham khảo nhưng không xếp hạng.": "K2 is the list of crops you do not want to grow; excluded crops are still scored for reference but not ranked.",
    "Đất nghỉ luôn khả thi và không được chấm điểm phù hợp sinh thái.": "Fallow is always feasible and is not given an ecological suitability score.",
    "SSURGO cho giá trị đại diện của thành phần đất chính trong đơn vị bản đồ, tầng 0–30 cm — nên đối chiếu mẫu đất thực tế.": "SSURGO gives the representative value of the dominant soil component in the map unit, 0–30 cm layer — compare with an actual soil sample.",
    "SoilGrids là mô hình dự đoán 250 m, có thể lệch nhiều ở từng thửa; nhóm tiêu chí C và D dùng dữ liệu tĩnh nên giống nhau ở mọi vụ.": "SoilGrids is a 250 m prediction model and may deviate considerably at field level; criterion groups C and D use static data, so they are the same in every season.",
    "Độ dốc SRTM tính từ chênh cao ±150 m quanh điểm; ở đồng bằng sai số vài mét có thể lấn át độ dốc thật.": "SRTM slope is computed from elevation differences ±150 m around the point; on flat plains errors of a few metres can outweigh the true slope.",
    "Tiêu chí thiếu dữ liệu được tạm bỏ và chia lại trọng số cho các tiêu chí còn lại.": "Criteria lacking data are temporarily dropped and their weight is redistributed to the remaining criteria.",
    "Các mức Δ của kịch bản thời tiết hiện do người dùng kéo; sau này sẽ lấy từ ngưỡng của phần cảnh báo.": "Weather-scenario Δ levels are currently set by the user's sliders; later they will come from the warning thresholds.",
    "Nếu mọi bộ ưu tiên đều ra cùng một cây thì kết quả khá chắc; nếu khác nhau, đó là quyết định đánh đổi — nên bàn với chuyên gia địa phương.": "If every priority profile yields the same crop, the result is fairly robust; if they differ, it is a trade-off decision — discuss it with local experts.",
    "Bộ trọng số theo ưu tiên là số khởi điểm; nên hiệu chỉnh bằng AHP hoặc phỏng vấn nông dân.": "Priority weight profiles are starting values; calibrate them with AHP or farmer interviews.",
    "diện tích ruộng (ha)": "field area (ha)",
    "điểm = G / G_max (G_max = {} USD)": "score = G / G_max (G_max = {} USD)",
    "Chế độ chuỗi luân canh: cần ngày bắt đầu và ngày kết thúc (bước 2).": "Crop rotation sequence mode: a start date and an end date are required (step 2).",
    "Khoảng thời gian của chuỗi quá ngắn (cần ít nhất 90 ngày).": "The sequence period is too short (at least 90 days required).",
    "Khoảng thời gian của chuỗi tối đa 5 năm.": "The sequence period is limited to 5 years.",
    "NASA POWER không trả dữ liệu gần đây.": "NASA POWER returned no recent data.",
    "Chưa chọn ruộng: hãy chọn vị trí ruộng ở bước 1.": "No field selected: please choose the field location in step 1.",
    "Chưa có dữ liệu NASA POWER gần đây cho điểm này.": "No recent NASA POWER data for this point yet.",
    "Không có phương pháp nào áp dụng được.": "No applicable method.",
    "anthropic: trả lời rỗng": "anthropic: empty reply",
    "Chưa cấu hình khóa AI (GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY…).": "No AI key configured (GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY…).",
    "Không có cây nào qua được điều kiện lịch gieo (K1) cho vụ này. Hãy xem lại ngày bắt đầu/độ dài vụ, hoặc cân nhắc để đất nghỉ.": "No crop passes the sowing-calendar constraint (K1) for this season. Review the season start date/length, or consider leaving the field fallow.",
    "Cây phù hợp nhất theo trọng số bạn chọn: {} — {}/100 điểm.": "Most suitable crop for your chosen weights: {} — {}/100 points.",
    "Điểm mạnh:": "Strengths:",
    "Cần lưu ý:": "Points to watch:",
    "Báo cáo {}": "Report {}",
    "1. Ruộng và vụ": "1. Field and season",
    "· vĩ độ {}, kinh độ {} · {}": "· latitude {}, longitude {} · {}",
    "Vụ cần quyết định:": "Season to decide:",
    "— từ {} đến {} ({} ngày). Cây vụ trước: {}.": "— from {} to {} ({} days). Previous crop: {}.",
    "CẢNH BÁO:": "WARNING:",
    "báo cáo này dùng khí hậu MÔ PHỎNG (DEMO), không phải dữ liệu NASA.": "this report uses SIMULATED climate (DEMO), not NASA data.",
    "Luôn khả thi — không chấm điểm phù hợp sinh thái.": "Always feasible — no ecological suitability score.",
    "4. Giả định của mô hình": "4. Model assumptions",
    "5. Nguồn CRD": "5. CRD sources",
    "Tạo lúc {} · {} v{} · Nhóm tác giả: {}": "Generated {} · {} v{} · Authors: {}",
    "Hãy gõ tên nơi cần tìm.": "Please type a place name to search.",
    "Không tìm thấy hoặc không kết nối được dịch vụ tìm địa điểm. Bạn có thể bấm thẳng lên bản đồ, hoặc gõ toạ độ dạng 18.67, 105.69. ({})": "Not found or the place-search service could not be reached. You can click directly on the map, or type coordinates such as 18.67, 105.69. ({})",
    "Toạ độ không hợp lệ.": "Invalid coordinates.",
    "Thiếu file hoặc loại lớp không hợp lệ.": "Missing file or invalid layer type.",
    "Chưa có kết quả phân tích.": "No analysis results yet.",
    "Câu hỏi trống.": "Empty question.",
    "Loại dữ liệu không hợp lệ.": "Invalid data type.",
    "Không tìm thấy yêu cầu (máy chủ có thể vừa khởi động lại).": "Request not found (the server may have just restarted).",
    "Danh sách không hợp lệ.": "Invalid list.",
    "Tính từ ALLSKY_SFC_SW_DWN / Ra (FAO-56)": "Computed from ALLSKY_SFC_SW_DWN / Ra (FAO-56)",
    "Quá ít quan sát hợp lệ ({}) cho lớp {} tại điểm này.": "Too few valid observations ({}) for layer {} at this point.",
    "ORNL không có {} tại điểm này.": "ORNL has no {} at this point.",
    "Ô lưới IMERG 0,1° tâm ({}, {}). Tổng tháng = cường độ TB (mm/giờ) × số giờ trong tháng.": "IMERG 0.1° grid cell centred at ({}, {}). Monthly total = mean rate (mm/h) × hours in the month.",
    "SSURGO không có dữ liệu tại điểm này (SSURGO chỉ phủ Hoa Kỳ; ngoài Mỹ dùng SoilGrids và nhập tay).": "SSURGO has no data at this point (SSURGO covers the United States only; elsewhere use SoilGrids and manual entry).",
    "SRTM không có độ cao tại điểm này.": "SRTM has no elevation at this point.",
    "Ngày bắt đầu vụ {}/{} nằm ngoài cửa sổ gieo {}/{}–{}/{} (cho phép lệch ±{} ngày).": "Season start date {}/{} is outside the planting window {}/{}–{}/{} (tolerance ±{} days).",
    "Vụ dài {} ngày, ngắn hơn chu kỳ sinh trưởng tối thiểu {} ngày.": "Season length {} days is shorter than the minimum growth cycle of {} days.",
    "NASA POWER GWETROOT tháng {} ({}) × độ rỗng {}": "NASA POWER GWETROOT month {} ({}) × porosity {}",
    "(bỏ tháng ngủ đông: chỉ tính T{})": "(dormant months excluded: only T{} counted)",
    "{}°C TB trong vụ{}": "{}°C in-season mean{}",
    "tối ưu {}–{} · chịu đựng {}–{}°C": "optimal {}–{} · tolerated {}–{}°C",
    "NASA POWER T2M, {} năm ({}–{}){}": "NASA POWER T2M, {} years ({}–{}){}",
    "Chưa có chuỗi nhiệt độ đủ dài cho cửa sổ vụ này": "No temperature series long enough for this season window",
    "{} mm/năm": "{} mm/year",
    "tối ưu {}–{} · chịu đựng {}–{} mm": "optimal {}–{} · tolerated {}–{} mm",
    "Chưa có Kt (ALLSKY_KT) cho cửa sổ vụ": "No Kt (ALLSKY_KT) for this season window",
    "Thiếu độ sâu tầng đất": "Soil depth missing",
    "Thiếu cấp cơ giới đất": "Soil texture class missing",
    "Thiếu pH": "pH missing",
    "Thiếu cấp thoát nước": "Drainage class missing",
    "Thoát nước: {}": "Drainage: {}",
    "Thiếu CEC": "CEC missing",
    "CEC {} cmolc/kg (nhóm {})": "CEC {} cmolc/kg (group {})",
    "Thiếu độ mặn EC": "Salinity EC missing",
    "bắt đầu giảm {} · giảm 50% {} · mất trắng {}": "yield decline starts {} · 50% decline {} · total loss {}",
    "Thiếu độ dốc": "Slope missing",
    "dốc {}% → {}": "slope {}% → {}",
    "Chưa khai báo vụ nào (bước 2): cần ngày bắt đầu và độ dài vụ.": "No season declared yet (step 2): a start date and season length are required.",
    "Không xác định được vụ cần ra quyết định.": "Could not determine the season to decide.",
    "giá bán và năng suất cơ sở của {}": "selling price and baseline yield of {}",
    "(bước 2)": "(step 2)",
    "K3: không trồng {} hai vụ liền nhau trên cùng thửa.": "K3: do not grow {} in two consecutive seasons on the same field.",
    "Chưa có dữ liệu gần đây": "No recent data yet",
    "thấp": "low",
    "Bất thường thống kê": "Statistical anomaly",
    "thiếu nước": "water deficit",
    "{}: trả lời rỗng": "{}: empty reply",
    "AI không phản hồi ({}).": "AI did not respond ({}).",
    "AI không phản hồi kịp trong {}s ({}).": "AI did not respond within {}s ({}).",
    "Bị loại theo lịch gieo (K1):": "Excluded by sowing calendar (K1):",
    "In / Lưu PDF": "Print / Save PDF",
    "2. Bảng điểm phù hợp (0–1)": "2. Suitability score table (0–1)",
    "Cây": "Crop",
    "Tổng": "Total",
    "2b. Chuỗi luân canh (Score(P) = (1/T)[S(c1) + Σ S(ct)·M(ct−1, ct)])": "2b. Crop rotation sequences (Score(P) = (1/T)[S(c1) + Σ S(ct)·M(ct−1, ct)])",
    "Khoảng {} → {} · làm đất {} ngày · {} chuỗi hợp lệ.": "Period {} → {} · {} days of land preparation · {} valid sequences.",
    "Trọng số:": "Weights:",
    "Dữ liệu quá lớn.": "Data too large.",
    "Không tìm thấy trang trại.": "Farm not found.",
    "Ảnh vệ tinh nền bản đồ (bước 1)": "Satellite imagery basemap (step 1)",
    "Bản đồ nền dự phòng": "Backup basemap",
    "Bản đồ nền trang chủ (giám sát): nền xám, bóng địa hình, ranh giới & địa danh": "Home page basemap (monitoring): light gray canvas, hillshade, boundaries & places",
    "Tìm tên địa điểm → toạ độ": "Place name search → coordinates",
    "Dữ liệu OSM; Open-Meteo CC BY 4.0": "OSM data; Open-Meteo CC BY 4.0",
    "Cổng truy cập SRTM 30 m để tính độ dốc": "Access gateway to SRTM 30 m for slope computation",
    "Mã nguồn MIT; dữ liệu SRTM của NASA": "MIT source code; SRTM data from NASA",
    "Máy chủ, API, cấu hình": "Server, API, configuration",
    "Bản đồ tương tác, vẽ ranh giới thửa": "Interactive map, field boundary drawing",
    "Biểu đồ khí hậu": "Climate charts",
    "Phông chữ giao diện": "Interface fonts",
    "Bức xạ đỉnh khí quyển Ra (tính Kt dự phòng), độ sâu rễ Zr": "Extraterrestrial radiation Ra (fallback Kt), rooting depth Zr",
    "Hàm phản ứng năng suất – nước, hệ số Ky (B1)": "Yield response to water, Ky factor (B1)",
    "θ héo / đồng ruộng / bão hòa theo cơ giới khi thiếu SSURGO": "Wilting point / field capacity / saturation θ by texture when SSURGO is missing",
    "Xu hướng khí hậu nhiều năm (bước 3)": "Multi-year climate trends (step 3)",
    "Phương pháp thống kê": "Statistical method",
    "15–20 / 3–4 đến 30–32": "15–20 / 3–4 to 30–32",
    "Dưới 10–12°C trong vụ là rủi ro. Tháng ngủ đông (TB < 5°C) không tính vào nhiệt độ vụ.": "Below 10–12°C during the season is a risk. Dormant months (mean < 5°C) are not counted in the season temperature.",
    "Rất sáng; ưa vị trí nhiều nắng": "Very bright; prefers sunny locations",
    "Tối ưu: trung bình. Chịu đựng: nặng, nhẹ. Loại: không có": "Optimal: medium. Tolerated: heavy, light. Excluded: none",
    "Ưa cạn: cần đất thoát nước tốt, mực nước ngầm không quá nông": "Prefers dry conditions: needs well-drained soil, water table not too shallow",
    "Cây kén đất. Đất giàu dinh dưỡng [EC-W]; CEC > 24: 1 · 16–24: 0,75 · 10–16: 0,5 · < 10: 0": "Nutrient-demanding crop. Fertile soil [EC-W]; CEC > 24: 1 · 16–24: 0.75 · 10–16: 0.5 · < 10: 0",
    "6,0 / 13 / 20; lúc nảy mầm ≤ 4": "6.0 / 13 / 20; ≤ 4 at germination",
    "0–4 (S1), 4–8 (S2), 8–16 (S3), > 16 (N), canh tác cơ giới hóa": "0–4 (S1), 4–8 (S2), 8–16 (S3), > 16 (N), mechanised farming",
    "Hệ số C (RUSLE) = 0,20": "C-factor (RUSLE) = 0.20",
    "Gieo 15/9–20/10; thu chủ yếu tháng 6–7 (năm 2010: 92% đã thu đến 11/7). 180–250 ngày": "Sow 15/9–20/10; harvest mainly June–July (2010: 92% harvested by 11/7). 180–250 days",
    "< 15°C hoặc > 35°C lúc ra hoa làm giảm đậu hạt": "< 15°C or > 35°C at flowering reduces grain set",
    "Rất sáng / trời quang đến rất sáng": "Very bright / clear sky to very bright",
    "450–650 (giống 110–130 ngày)": "450–650 (110–130-day varieties)",
    "Sâu 50–150 cm / 50–150 cm": "Depth 50–150 cm / 50–150 cm",
    "Tối ưu: nặng, trung bình. Chịu đựng: nhẹ (“mọi loại”). Loại: không có": "Optimal: heavy, medium. Tolerated: light (“all types”). Excluded: none",
    "Ưa cạn: cần đất thoát nước tốt, chỉ chịu úng ngắn": "Prefers dry conditions: needs well-drained soil, tolerates only brief waterlogging",
    "Cây chịu đất nghèo (cao / thấp). CEC > 24: 1 · 16–24: 1 · 10–16: 0,75 · < 10: 0,5": "Tolerant of poor soils (high / low). CEC > 24: 1 · 16–24: 1 · 10–16: 0.75 · < 10: 0.5",
    "Tạm lấy bằng ngô: C = 0,38 (giả định, nguồn [PAN] không có cao lương)": "Temporarily set equal to maize: C = 0.38 (assumption, source [PAN] does not list sorghum)",
    "Gieo 15/5–20/6; thu 11/10–8/11. 90–300 ngày": "Sow 15/5–20/6; harvest 11/10–8/11. 90–300 days",
    "Cần trung bình > 15°C, không sương giá": "Needs a mean > 15°C, frost-free",
    "500–800 (giống trung ngày)": "500–800 (medium-maturity varieties)",
    "Sâu 50–150 cm / 20–50 cm. Phân hạng: > 100 cm (S1), 75–100 (S2), 50–75 (S3), < 50 (N)": "Depth 50–150 cm / 20–50 cm. Classes: > 100 cm (S1), 75–100 (S2), 50–75 (S3), < 50 (N)",
    "Tối ưu: trung bình. Chịu đựng: nặng, nhẹ (trừ cát). Loại: cát": "Optimal: medium. Tolerated: heavy, light (except sand). Excluded: sand",
    "Ưa cạn: cần đất thoát nước tốt, úng lúc ra hoa có thể giảm ≥ 50% năng suất": "Prefers dry conditions: needs well-drained soil; waterlogging at flowering can cut yield by ≥ 50%",
    "Cây kén đất (cao / thấp). CEC > 24: 1 · 16–24: 0,75 · 10–16: 0,5 · < 10: 0": "Nutrient-demanding crop (high / low). CEC > 24: 1 · 16–24: 0.75 · 10–16: 0.5 · < 10: 0",
    "Hệ số C (RUSLE) = 0,38; độc canh ngô có thể gây xói mòn": "C-factor (RUSLE) = 0.38; continuous maize may cause erosion",
    "Gieo 19/4–17/5; thu 13/9–18/10. Giống sớm 80–110, trung 110–140 ngày": "Sow 19/4–17/5; harvest 13/9–18/10. Early varieties 80–110, medium 110–140 days",
    "Sinh trưởng chậm lại khi > 35°C hoặc < 18°C": "Growth slows above 35°C or below 18°C",
    "Sâu 50–150 cm / 20–50 cm": "Depth 50–150 cm / 20–50 cm",
    "Tối ưu: trung bình, hữu cơ. Chịu đựng: nặng, nhẹ (trừ cát). Loại: cát (“trừ đất rất cát”)": "Optimal: medium, organic. Tolerated: heavy, light (except sand). Excluded: sand (“except very sandy soils”)",
    "Ưa cạn: cần đất thoát nước tốt, nhạy úng đầu vụ": "Prefers dry conditions: needs well-drained soil, sensitive to early-season waterlogging",
    "Hệ số C (RUSLE) = 0,28": "C-factor (RUSLE) = 0.28",
    "Gieo 10/5–14/6; thu 4/10–1/11. 100–130 ngày": "Sow 10/5–14/6; harvest 4/10–1/11. 100–130 days",
    "[crops.json] bỏ qua do lỗi:": "[crops.json] skipped due to error:",
    "Không gọi được NASA POWER: {}": "Could not reach NASA POWER: {}",
    "Phản hồi NASA POWER không đúng định dạng.": "NASA POWER response has an unexpected format.",
    "DEMO vì: {}": "DEMO because: {}",
    "ngày": "days",
    "Chỉ lấy được {}/{} tháng IMERG — thử lại sau (máy chủ GES DISC có thể đang chậm).": "Only {}/{} IMERG months retrieved — try again later (the GES DISC server may be slow).",
    "Không gọi được Soil Data Access: {}": "Could not reach Soil Data Access: {}",
    "Không ghi nhận tầng cản: lấy độ sâu mô tả hết phẫu diện (≥ {} cm).": "No restrictive layer recorded: using the full described profile depth (≥ {} cm).",
    "Gieo {}/{} + chu kỳ tối thiểu {} ngày → chín khoảng {}/{}, sau ngày sương giá đầu thu (~{}/{}).": "Sow {}/{} + minimum cycle {} days → maturity around {}/{}, after the first fall frost (~{}/{}).",
    "SMAP L4 độ ẩm vùng rễ (lớp CSV, tháng {})": "SMAP L4 root-zone soil moisture (CSV layer, month {})",
    "Chưa có mưa trong vụ": "No in-season rainfall yet",
    "(giả định)": "(assumed)",
    "K2: bạn đã loại cây này khỏi danh sách.": "K2: you excluded this crop from the list.",
    "Các vụ chồng thời gian:": "Overlapping seasons:",
    "Thiếu": "Missing",
    "K4: bạn đã cấm trồng {} sau {}.": "K4: you banned growing {} after {}.",
    "{} {} — phân vị {} so với cùng giai đoạn {} năm ({})": "{} {} — percentile {} relative to the same period over {} years ({})",
    "Xếp sau:": "Ranked next:",
    "Tiêu chí chưa đủ dữ liệu nên chưa tính:": "Criteria not yet computed due to missing data:",
    "có tưới": "irrigated",
    "không tưới (nhờ mưa)": "not irrigated (rainfed)",
    "V = S × M, với M = 1 + E({}, c)/100 theo Mudare et al. (2025).": "V = S × M, with M = 1 + E({}, c)/100 per Mudare et al. (2025).",
    "Chưa tính vì thiếu dữ liệu:": "Not computed due to missing data:",
    "svc không hợp lệ": "invalid svc",
    "Trợ lý AI đang chậm hoặc chưa kết nối được. Bạn vẫn có thể đọc phần giải thích có sẵn. ({})": "The AI assistant is slow or not connected. You can still read the built-in explanation. ({})",
    "tắt — chưa có khóa AI; vẫn có giải thích tại chỗ": "off — no AI key; built-in explanations still available",
    "Lỗi không mong đợi: {}": "Unexpected error: {}",
    "bảng Rawls 1982 theo cơ giới “{}”": "Rawls 1982 table for texture “{}”",
    "ETa {} mm = mưa vụ {} + đất {} mm{} · ETm {}": "ETa {} mm = seasonal rain {} + soil {} mm{} · ETm {}",
    "Mưa: {} · θ: {} · θ héo/đồng ruộng: {}": "Rain: {} · θ: {} · θ wilting/field capacity: {}",
    "nghỉ": "fallow",
    "Ngưỡng nông học": "Agronomic threshold",
    "quá chậm": "too slow",
    "Đề xuất chuỗi luân canh": "Crop rotation sequence recommendation",
    "Đề xuất cây trồng cho vụ tới": "Crop recommendation for the next season",
    "Ruộng": "Field",
    "chưa khai báo": "not declared",
    "đạt": "pass",
    "Toạ độ": "Coordinates",
    "giá": "price",
    "Vụ {}": "Season {}",
    "— giá trị năm {}": "— value for year {}",
    "Thiếu {}": "Missing {}",
    "Không có lượt gieo nào của {} (cửa sổ gieo ± {} ngày, {} ngày gieo → thu) vừa trong khoảng thời gian của chuỗi.": "No sowing turn of {} (planting window ± {} days, {} days sowing → harvest) fits within the sequence period.",
    "nóng": "hot",
    "lạnh": "cold",
    "ướt": "wet",
    "khô": "dry",
    "nắng": "sunny",
    "u ám": "overcast",
    "ẩm": "moist",
    "thấp hơn mức thấp nhất từng ghi nhận": "below the lowest value on record",
    "{} đang ngủ đông (TB 7 ngày {}°C < {}°C) — không xét ngưỡng nhiệt.": "{} is dormant (7-day mean {}°C < {}°C) — temperature thresholds not checked.",
    "TB 7 ngày {}°C; tối ưu {}–{}, chịu đựng {}–{}°C của {}; còn {}°C tới giới hạn (m = {}°C)": "7-day mean {}°C; optimal {}–{}, tolerated {}–{}°C for {}; {}°C left to the limit (m = {}°C)",
    "Mưa 365 ngày {} mm; tối ưu {}–{}, chịu đựng {}–{} mm/năm của {}": "365-day rainfall {} mm; optimal {}–{}, tolerated {}–{} mm/year for {}",
    "loại:": "excluded:",
    "{}: không có kết quả": "{}: no results",
    "Không lấy được thông tin dịch vụ NASA POWER: {}": "Could not get NASA POWER service information: {}",
    "GES DISC từ chối token (HTTP {}): kiểm tra token còn hạn và đã cấp quyền 'NASA GESDISC DATA ARCHIVE'.": "GES DISC rejected the token (HTTP {}): check that the token is valid and 'NASA GESDISC DATA ARCHIVE' is authorised.",
    "(giới hạn bởi tầng đất)": "(limited by soil depth)",
    "cao hơn mức cao nhất từng ghi nhận": "above the highest value on record",
    "trong phạm vi lịch sử": "within the historical range",
    "Kt 7 ngày {} ({}); tối ưu ≥ 0,60 (rất sáng), chịu đựng ≥ 0,50 (trời quang)": "7-day Kt {} ({}); optimal ≥ 0.60 (very bright), tolerated ≥ 0.50 (clear sky)",
    "({}; nguồn: {})": "({}; source: {})",
    "Trang trại": "Farm",
    "và": "and",
    "(đã chặn ở sức chứa {} mm)": "(capped at the storage capacity {} mm)",
    "Từ đầu vụ ({} ngày): mưa {} + nước đất đầu vụ {} = {} mm so với nhu cầu {} mm của {} → Ya/Ym = {}": "Since season start ({} days): rain {} + initial soil water {} = {} mm against a requirement of {} mm for {} → Ya/Ym = {}",
    "ẩm đất đầu vụ θ (SMAP hoặc cơ giới đất để ước tính)": "initial soil moisture θ (SMAP or soil texture to estimate)",
    "θ điểm héo (SSURGO hoặc cơ giới đất)": "wilting point θ (SSURGO or soil texture)",
    "Về trang chủ": "Back to home",
    "Ruộng đang chọn": "Selected field",
    "Tình trạng dữ liệu của 13 tiêu chí — bấm để xem": "Data status of the 13 criteria — click to view",
    "Các bước": "Steps",
    "Khí hậu: DEMO": "Climate: DEMO",
    "NASA Space Apps 2026 · Nguyễn Mai Chi & Nguyễn Mạnh Đạt": "NASA Space Apps 2026 · Nguyễn Mai Chi & Nguyễn Mạnh Đạt",
    "Trang chủ · Giám sát thời tiết": "Home · Weather monitoring",
    "Thời tiết trên thửa của bạn hôm nay thế nào?": "How is the weather on your field today?",
    "Bản đồ dữ liệu NASA POWER theo tháng, cảnh báo sớm cho riêng thửa ruộng và gợi ý cây hợp cho vụ tới.": "Monthly NASA POWER data maps, early warnings for your own field and suggestions of suitable crops for the next season.",
    "Bắt đầu dùng công cụ →": "Start using the tool →",
    "So sánh kịch bản cho vụ tới": "Compare scenarios for the next season",
    "Kịch bản ↓": "Scenarios ↓",
    "Cảnh báo thời tiết": "Weather warnings",
    "Đang lấy…": "Fetching…",
    "Cấu hình cảnh báo": "Warning settings",
    "Thu gọn": "Collapse",
    "Chọn vị trí ruộng để nhận cảnh báo nhiệt độ, mưa, bức xạ và độ ẩm cho riêng thửa của bạn.": "Choose your field location to receive temperature, rainfall, radiation and moisture warnings for your own field.",
    "Chọn ruộng của tôi": "Choose my field",
    "Dùng ví dụ Kansas": "Use the Kansas example",
    "Dữ liệu NASA POWER tại thửa của bạn": "NASA POWER data at your field",
    "Chỉ số 4 yếu tố hôm nay": "Today's values of the 4 factors",
    "Chạy theo thời gian": "Play through time",
    "Thời gian": "Time",
    "Trang chủ · So sánh kịch bản": "Home · Scenario comparison",
    "Nếu vụ tới nóng hơn, khô hơn… cây nào còn hợp?": "If the next season is hotter or drier… which crops still fit?",
    "Kéo các thanh A1, A2, A3, B1 để xem cây nào còn hợp nếu thời tiết thay đổi": "Drag the A1, A2, A3, B1 sliders to see which crops still fit if the weather changes",
    "Cấu hình tiêu chí": "Criteria settings",
    "Xem chi tiết →": "View details →",
    "↑ Về bản đồ": "↑ Back to map",
    "Gõ tên xã, huyện, quận (county) hoặc toạ độ…": "Type a commune, district, county or coordinates…",
    "Tìm địa điểm": "Search place",
    "Tìm": "Search",
    "Vị trí của tôi": "My location",
    "Bấm lên bản đồ để chọn đúng nơi ruộng của bạn": "Click on the map to select the exact location of your field",
    "Ruộng của bạn": "Your field",
    "Đặt tên để lần sau mở lại nhanh": "Give it a name so you can reopen it quickly next time",
    "vd: Ruộng nhà ông Ba": "e.g. Mr. Ba's field",
    "Tên trang trại": "Farm name",
    "Vĩ độ": "Latitude",
    "Kinh độ": "Longitude",
    "Lưu trang trại": "Save farm",
    "Chế độ tưới": "Irrigation regime",
    "Đặc điểm của thửa — giống nhau cho mọi cây": "A field property — the same for every crop",
    "Thử nhanh bằng ví dụ": "Try an example",
    "Đã điền sẵn vụ và đất (số minh hoạ)": "Seasons and soil pre-filled (illustrative values)",
    "Đông Kansas": "Eastern Kansas",
    "Manhattan · vụ hè, nhờ mưa": "Manhattan · summer season, rainfed",
    "Tây Kansas": "Western Kansas",
    "Garden City · lúa mì đông + vụ hai": "Garden City · winter wheat + double crop",
    "Trang trại đã lưu": "Saved farms",
    "Chưa có.": "None yet.",
    "Tiếp tục: khai báo mùa vụ →": "Next: declare seasons →",
    "Bạn muốn công cụ giải bài toán nào?": "Which problem do you want the tool to solve?",
    "Chọn trước khi khai báo mùa vụ — các bước sau sẽ tự đổi theo bài toán": "Choose before declaring seasons — later steps adapt to the problem",
    "Khai báo các vụ trong năm của ruộng": "Declare the field's seasons in the year",
    "Mỗi vụ: trồng cây gì, bắt đầu ngày nào (chọn trên lịch — lặp lại hằng năm) và kéo dài bao lâu": "Each season: which crop, which start date (pick on the calendar — repeats every year) and how long it lasts",
    "+ Thêm vụ": "+ Add season",
    "Điều kiện K1: cây nào kịp thời vụ tới?": "Constraint K1: which crops fit the next season's timing?",
    "So ngày bắt đầu vụ tới với cửa sổ gieo và chu kỳ sinh trưởng trong CRD": "Compares the next season's start date with the planting window and growth cycle in the CRD",
    "Đồng hồ mùa vụ": "Season clock",
    "Vạch đỏ là hôm nay · vụ viền đậm là vụ cần ra quyết định": "Red line is today · the season with a bold outline is the season to decide",
    "Khoảng thời gian của chuỗi luân canh": "Crop rotation sequence period",
    "Chỉ cần ngày bắt đầu và ngày kết thúc — công cụ tự xếp các cây vừa trong khoảng này theo cửa sổ gieo và thời gian sinh trưởng trong CRD": "Only a start date and an end date are needed — the tool arranges crops that fit within this period by planting window and growth duration in the CRD",
    "Thông tin kinh tế (tiêu chí F1)": "Economic information (criterion F1)",
    "G = giá bán P × diện tích A × năng suất cơ sở Y_base — dùng để chấm F1; để trống thì F1 tự bỏ khỏi điểm": "G = selling price P × area A × baseline yield Y_base — used to score F1; leave blank and F1 is dropped from the score",
    "← Quay lại": "← Back",
    "Tiếp tục: khí hậu nơi bạn →": "Next: your local climate →",
    "↻ Tải lại dữ liệu NASA": "↻ Reload NASA data",
    "Đang tải…": "Loading…",
    "A1 · Nhiệt độ": "A1 · Temperature",
    "TB tháng nhiều năm · dải: TB thấp nhất – cao nhất ngày · nền xanh: tháng của vụ tới": "Multi-year monthly mean · band: mean daily minimum – maximum · green background: months of the next season",
    "A2 · Lượng mưa năm": "A2 · Annual rainfall",
    "Tổng mưa từng năm · vạch: trung bình nhiều năm (giá trị dùng cho A2)": "Total rainfall per year · line: multi-year mean (value used for A2)",
    "A3 · Bức xạ (chỉ số Kt)": "A3 · Radiation (clearness index Kt)",
    "Kt TB tháng · vạch ngang: ngưỡng rất sáng 0,60 · trời quang 0,50 · nhiều mây 0,35": "Monthly mean Kt · horizontal lines: thresholds very bright 0.60 · clear sky 0.50 · cloudy 0.35",
    "Diễn biến gần đây so với nhiều năm": "Recent conditions compared with many years",
    "Năm nay so với trung vị và dải phân vị 10–90 cùng kỳ của chính thửa ruộng": "This year compared with the median and the 10–90 percentile band for the same period at this very field",
    "Thời gian xem:": "Time span:",
    "Dữ liệu bổ sung: mưa GPM IMERG (A2, B1) và độ ẩm SMAP (B1)": "Additional data: GPM IMERG precipitation (A2, B1) and SMAP soil moisture (B1)",
    "Tiếp tục: đất & địa hình →": "Next: soil & terrain →",
    "Tiếp tục: chọn tiêu chí →": "Next: choose criteria →",
    "Dùng tiêu chí nào, nặng nhẹ ra sao?": "Which criteria to use, and how much weight?",
    "Bật/tắt từng tiêu chí và kéo trọng số. Tổng luôn được quy về 100%.": "Turn each criterion on/off and drag its weight. The total is always normalised to 100%.",
    "Bắt đầu từ một bộ ưu tiên (trọng số nhóm theo tài liệu, chia đều cho các tiêu chí trong nhóm)": "Start from a priority profile (group weights from the literature, split equally among the criteria in each group)",
    "Tỉ trọng sau khi chuẩn hóa": "Shares after normalisation",
    "Điều kiện bắt buộc": "Mandatory constraints",
    "Loại phương án trước khi chấm điểm": "Exclude options before scoring",
    "K1 – Lịch gieo & chu kỳ sinh trưởng": "K1 – Sowing calendar & growth cycle",
    "Loại cây có cửa sổ gieo không khớp ngày bắt đầu vụ, vụ ngắn hơn chu kỳ tối thiểu, hoặc không chín kịp trước sương giá đầu thu": "Excludes crops whose planting window does not match the season start date, whose season is shorter than the minimum cycle, or that cannot mature before the first fall frost",
    "Cho phép lệch so với cửa sổ gieo:": "Allowed deviation from the planting window:",
    "±7 ngày": "±7 days",
    "K2 – Cây bạn không muốn trồng": "K2 – Crops you do not want to grow",
    "K3 – Không trồng một cây 2 vụ liền nhau": "K3 – Do not grow the same crop in 2 consecutive seasons",
    "Ví dụ ngô → ngô, đậu tương → đậu tương. Đất nghỉ không tính là cây và cắt quan hệ liền kề.": "E.g. maize → maize, soybean → soybean. Fallow is not a crop and breaks the consecutive relation.",
    "K4 – Không trồng cây A sau cây B": "K4 – Do not grow crop A after crop B",
    "Khai báo các cặp cấm (cây trước → cây sau); mặc định trống": "Declare banned pairs (previous crop → next crop); empty by default",
    "Tiếp tục: ma trận luân canh →": "Next: rotation matrix →",
    "Độ phủ cặp cây: trồng cây sau, sau cây trước": "Crop-pair coverage: growing the next crop after the previous crop",
    "% thay đổi năng suất cây sau so với độc canh — Mudare et al. (2025), Supplementary Table 5": "% yield change of the following crop compared with monoculture — Mudare et al. (2025), Supplementary Table 5",
    "Ma trận được dùng thế nào?": "How is the matrix used?",
    "Với ruộng của bạn": "For your field",
    "Đang tính điểm…": "Computing scores…",
    "Xem kết quả →": "View results →",
    "Chưa có kết quả cho vụ tới": "No results for the next season yet",
    "Công cụ cần biết ruộng ở đâu và các vụ trong năm. Đủ rồi thì bấm nút dưới.": "The tool needs to know where your field is and its seasons in the year. When ready, click the button below.",
    "Tính điểm phù hợp": "Compute suitability scores",
    "Đang lấy dữ liệu và chấm điểm từng cây…": "Fetching data and scoring each crop…",
    "Bảng điểm: cây × tiêu chí (0–1)": "Score table: crop × criterion (0–1)",
    "Bấm vào một ô để xem giá trị, ngưỡng và cách tính": "Click a cell to see its value, thresholds and calculation",
    "🖨 In báo cáo": "🖨 Print report",
    "Tải CSV": "Download CSV",
    "Vì sao & lưu ý": "Why & notes",
    "Độ vững của xếp hạng": "Ranking robustness",
    "Cây đứng đầu khi đổi sang từng bộ ưu tiên": "Top crop under each priority profile",
    "← Ma trận luân canh": "← Rotation matrix",
    "Đổi tiêu chí & trọng số": "Change criteria & weights",
    "Về trang giám sát": "Back to monitoring page",
    "Lịch gieo – thu ở Kansas (điều kiện K1)": "Sowing – harvest calendar in Kansas (constraint K1)",
    "Xanh: cửa sổ gieo · vàng: cửa sổ thu · khung nét đứt: vụ tới của bạn · vạch đỏ: hôm nay": "Green: planting window · yellow: harvest window · dashed box: your next season · red line: today",
    "So sánh khoảng phù hợp giữa các cây": "Compare suitable ranges across crops",
    "Dải đậm: tối ưu · dải nhạt: chịu đựng · vạch đen: số của ruộng bạn (nếu có)": "Dark band: optimal · light band: tolerated · black line: your field's value (if available)",
    "Crop Requirement Database — bảng đầy đủ": "Crop Requirement Database — full table",
    "Dạng tối ưu / chịu đựng. Bấm mã nguồn để xem tài liệu gốc.": "In optimal / tolerated form. Click a source code to open the original document.",
    "Quy tắc quy đổi về thang 0–1": "Rules for converting to the 0–1 scale",
    "Nguồn": "Sources",
    "← Quay lại bước đang làm": "← Back to the current step",
    "Nhóm tác giả": "Authors",
    "Liên hệ về công cụ FARM ADAPT — NASA Space Apps Challenge 2026": "Contact about the FARM ADAPT tool — NASA Space Apps Challenge 2026",
    "Dữ liệu NASA": "NASA data",
    "Dữ liệu nào, dùng cho tiêu chí nào, lấy bằng cách nào — và trạng thái với ruộng đang chọn": "Which data, used for which criteria, how it is obtained — and its status for the selected field",
    "Dữ liệu khác (không phải NASA)": "Other data (non-NASA)",
    "Bản đồ đất và mô hình đất bổ sung cho nhóm tiêu chí C": "Soil maps and soil models supplementing criterion group C",
    "Cơ sở dữ liệu yêu cầu cây trồng (CRD)": "Crop Requirement Database (CRD)",
    "Nguồn của từng con số trong Thư viện cây trồng": "Source of every number in the Crop Library",
    "Tài nguyên, thư viện & phương pháp": "Resources, libraries & methods",
    "Kể cả mã nguồn mở và hình ảnh": "Including open-source code and images",
    "Lưu ý & giả định của công cụ": "Notes & assumptions of the tool",
    "Mọi lưu ý được gom về đây để các trang làm việc gọn hơn": "All notes are gathered here to keep the working pages clean",
    "Công cụ AI": "AI tools",
    "Cuộc thi cho phép dùng AI nhưng phải ghi rõ dùng ở đâu và như thế nào": "The competition allows AI but requires stating where and how it was used",
    "1. AI bên trong công cụ (khi người dùng chạy)": "1. AI inside the tool (at runtime)",
    "2. AI nhóm đã dùng khi phát triển": "2. AI used by the team during development",
    "+ Thêm công cụ": "+ Add tool",
    "Lưu khai báo": "Save declaration",
    "Bản khai để dán vào trang nộp bài": "Declaration to paste into the submission page",
    "Tự sinh từ các mục trên — sao chép hoặc tải về dạng Markdown": "Auto-generated from the sections above — copy or download as Markdown",
    "Sao chép": "Copy",
    "Tải .md": "Download .md",
    "Máy chủ trả về lỗi (": "Server returned an error (",
    "Lỗi": "Error",
    "AI trả lời quá lâu — bạn có thể đọc phần giải thích có sẵn ở trên.": "AI took too long to reply — you can read the built-in explanation above.",
    "Không tải được Chart.js (cần mạng) — biểu đồ tạm ẩn.": "Could not load Chart.js (network required) — charts temporarily hidden.",
    "Không vẽ được biểu đồ:": "Could not draw chart:",
    "Giám sát & kịch bản": "Monitoring & scenarios",
    "Trang chủ của nhà nông": "The farmer's home page",
    "Theo dõi nhiệt độ, mưa, bức xạ và cân bằng nước bằng dữ liệu NASA, nhận cảnh báo sớm và thử các kịch bản cho vụ tới.": "Track temperature, rainfall, radiation and water balance with NASA data, get early warnings and test scenarios for the next season.",
    "Ruộng của tôi": "My field",
    "Vị trí & chế độ tưới": "Location & irrigation",
    "Nắng lên trên cánh đồng của bạn": "Sunrise over your field",
    "Chọn đúng điểm ruộng của bạn trên bản đồ và cho biết ruộng có tưới hay không.": "Pick your field's exact location on the map and tell us whether it is irrigated.",
    "Bài toán & mùa vụ": "Problem & seasons",
    "Vụ hoặc chuỗi luân canh": "Next season or rotation sequence",
    "Bạn cần đề xuất cho vụ tới hay cả chuỗi luân canh?": "Do you need a recommendation for the next season or for a whole rotation sequence?",
    "Chọn bài toán, rồi khai báo các vụ trong năm (vụ tới) hoặc chỉ ngày bắt đầu – kết thúc (chuỗi luân canh), cùng giá bán và năng suất để tính giá trị kinh tế.": "Choose the problem, then declare the seasons in the year (next season) or just a start – end date (rotation sequence), plus selling prices and yields to compute economic value.",
    "Khí hậu": "Climate",
    "Khí hậu nhiều năm tại ruộng của bạn": "Long-term climate at your field",
    "Nhiệt độ, lượng mưa năm và bức xạ từ NASA POWER — số liệu nền cho tiêu chí A1, A2, A3.": "Temperature, annual rainfall and radiation from NASA POWER — the baseline data for criteria A1, A2, A3.",
    "Đất & địa hình": "Soil & terrain",
    "Đất khỏe thì mùa sau mới vững": "Healthy soil makes for a steady next season",
    "Cân bằng nước, các chỉ số đất, độ dốc và độ che phủ: tự lấy từ SSURGO, SoilGrids, SRTM; thiếu chỗ nào nhập tay chỗ đó.": "Water balance, soil indicators, slope and land cover: fetched automatically from SSURGO, SoilGrids, SRTM; enter manually wherever data is missing.",
    "Tiêu chí": "Criteria",
    "Chọn & cân trọng số": "Select & weight",
    "Điều gì quan trọng với bạn?": "What matters to you?",
    "Chọn tiêu chí được dùng và trọng số của từng tiêu chí, hoặc bắt đầu từ một bộ ưu tiên có sẵn.": "Choose which criteria are used and the weight of each, or start from a ready-made priority profile.",
    "Kết quả": "Results",
    "Cây / chuỗi đề xuất": "Recommended crops / sequences",
    "Trồng gì cho hợp với thửa của bạn?": "What should you grow on your field?",
    "Điểm phù hợp của từng cây, kết hợp với ma trận luân canh: cây đề xuất cho vụ tới hoặc chuỗi luân canh xếp hạng, kèm cách tính và lý do.": "Suitability score of each crop combined with the rotation matrix: the recommended crop for the next season or ranked rotation sequences, with calculations and reasons.",
    "Thư viện cây trồng": "Crop library",
    "Mỗi cây cần gì để sống khỏe?": "What does each crop need to thrive?",
    "Cơ sở dữ liệu yêu cầu cây trồng (CRD) mà công cụ đang dùng, có nguồn cho từng con số.": "The Crop Requirement Database (CRD) used by the tool, with a source for every number.",
    "Nguồn, lưu ý & AI": "Sources, notes & AI",
    "Theo luật cuộc thi": "Per competition rules",
    "Dữ liệu từ đâu, cần lưu ý gì?": "Where does the data come from, and what should you keep in mind?",
    "Mọi nguồn dữ liệu, tài nguyên, lưu ý của mô hình và khai báo công cụ AI — kèm bản khai để dán vào trang nộp bài.": "All data sources, resources, model notes and the AI tool declaration — with a ready-made statement for the submission page.",
    "Ma trận luân canh": "Rotation matrix",
    "Độ phủ cặp cây": "Crop-pair coverage",
    "Trồng cây gì sau cây gì thì được mùa?": "Which crop after which gives a good harvest?",
    "Hiệu ứng luân canh: % thay đổi năng suất cây sau so với độc canh (Mudare et al. 2025) — dùng làm hệ số M khi kết hợp với điểm phù hợp.": "Rotation effect: % yield change of the following crop compared with monoculture (Mudare et al. 2025) — used as the M factor combined with the suitability score.",
    "← Trang chủ · bản đồ giám sát": "← Home · monitoring map",
    "Công cụ ra quyết định vụ tới": "Next-season decision tool",
    "cây · có nguồn": "crops · sourced",
    "Chưa chọn ruộng": "No field selected",
    "nhờ mưa": "rainfed",
    "Bấm để chọn ruộng": "Click to choose a field",
    "Trang chủ · Giám sát": "Home · Monitoring",
    "Bước": "Step",
    "Tra cứu ·": "Reference ·",
    "Lớp bản đồ này không tải được, đã chuyển sang lớp khác.": "This map layer failed to load; switched to another layer.",
    "Đang tìm…": "Searching…",
    "Đã chọn": "Selected",
    ". Bấm lên bản đồ nếu muốn chỉnh đúng ruộng.": ". Click on the map if you want to fine-tune the field location.",
    "Không lấy được vị trí (cần cho phép định vị / HTTPS).": "Could not get your location (location permission / HTTPS required).",
    "Trình duyệt không hỗ trợ định vị.": "The browser does not support geolocation.",
    "Không tưới": "Not irrigated",
    "Nhờ mưa — tính đầy đủ A2 (mưa năm) và B1 (cân bằng nước)": "Rainfed — A2 (annual rainfall) and B1 (water balance) are fully computed",
    "Mặc định tưới đủ nhu cầu cây → A2 = 1, B1 = 1 cho mọi cây": "Assumes irrigation fully meets crop demand → A2 = 1, B1 = 1 for every crop",
    "Hãy chọn vị trí trước.": "Please choose a location first.",
    "Đã lưu trang trại": "Farm saved",
    "Chưa có trang trại nào được lưu.": "No farms saved yet.",
    "Mở": "Open",
    "Xóa": "Delete",
    "Đã mở trang trại": "Farm opened",
    "Xóa trang trại này?": "Delete this farm?",
    "Ví dụ: Đông Kansas (Manhattan)": "Example: Eastern Kansas (Manhattan)",
    "Vụ hè": "Summer season",
    "Ví dụ: Tây Kansas (Garden City)": "Example: Western Kansas (Garden City)",
    "Vụ lúa mì đông": "Winter wheat season",
    "Vụ hai sau lúa mì": "Double crop after wheat",
    "Đã nạp ví dụ — số đất là số minh hoạ; ở bước 4 có thể lấy số SSURGO thật.": "Example loaded — soil values are illustrative; in step 4 you can fetch real SSURGO values.",
    "Bạn chưa chọn ruộng. Bấm lên bản đồ hoặc tìm tên nơi nhé.": "You have not chosen a field. Click on the map or search for a place name.",
    "Chưa chọn": "Not selected",
    "Tên vụ": "Season name",
    "Xóa vụ": "Delete season",
    "Cây trồng trong vụ": "Crop in this season",
    "Ngày bắt đầu": "Start date",
    "Kéo dài": "Duration",
    "{} ngày": "{} days",
    "{}/{} → {}/{} · lặp lại mỗi năm": "{}/{} → {}/{} · repeats every year",
    "{}: {}/{}, {} ngày": "{}: {}/{}, {} days",
    "Hôm nay": "Today",
    "Thêm vụ": "Add season",
    "Đang ở vụ này": "Currently in this season",
    "{} → {} · ngày {}/{}": "{} → {} · day {}/{}",
    "Hôm nay không thuộc vụ nào": "Today is not within any season",
    "Ruộng đang giữa hai vụ (đất trống / nghỉ).": "The field is between two seasons (bare / fallow).",
    "Vụ cần quyết định": "Season to decide",
    "Bắt đầu {} (còn {} ngày) · {} ngày, đến {}": "Starts {} ({} days left) · {} days, until {}",
    "Thêm ít nhất một vụ để xem đồng hồ mùa vụ.": "Add at least one season to see the season clock.",
    "Khai báo ít nhất một vụ để xem cây nào hợp lịch.": "Declare at least one season to see which crops fit the calendar.",
    "đang TẮT": "currently OFF",
    "đang bật (lệch ±": "on (tolerance ±",
    "ngày)": "days)",
    "Vụ “{}” bắt đầu {}/{}, dài {} ngày · K1 {}": "Season “{}” starts {}/{}, lasts {} days · K1 {}",
    "Gieo {}/{}–{}/{} {} · chu kỳ ≥ {} ngày {}": "Sow {}/{}–{}/{} {} · cycle ≥ {} days {}",
    "Luôn khả thi": "Always feasible",
    "ẩm hơn": "wetter",
    "khô hơn": "drier",
    "Ẩm đất tháng {}: {} so với TB cùng tháng {} →": "Soil moisture in {}: {} vs. same-month mean {} →",
    "{} bình thường {}%": "{} than normal by {}%",
    "Vụ": "Season",
    "Hãy nhập ngày bắt đầu và ngày kết thúc của chuỗi luân canh.": "Please enter the start and end dates of the rotation sequence.",
    "Hãy khai báo ít nhất một vụ (ngày bắt đầu + số ngày).": "Please declare at least one season (start date + number of days).",
    "Chưa biết ruộng của bạn ở đâu": "We don't know where your field is yet",
    "Hãy chọn vị trí trên bản đồ, rồi quay lại đây để xem khí hậu NASA tại ruộng.": "Choose a location on the map, then come back here to see NASA climate data at your field.",
    "← Chọn ruộng": "← Choose field",
    "Đang lấy dữ liệu NASA cho ruộng của bạn…": "Fetching NASA data for your field…",
    "Nhiều năm số liệu hằng ngày, có thể mất 10–60 giây.": "Many years of daily data, this may take 10–60 seconds.",
    "Chưa lấy được dữ liệu NASA": "Could not get NASA data",
    "Thử lại": "Retry",
    "DEMO — khí hậu MÔ PHỎNG (không phải NASA)": "DEMO — SIMULATED climate (not NASA)",
    "{}–{} ({} năm)": "{}–{} ({} years)",
    "Tháng của vụ tới": "Months of the next season",
    "TB năm": "Annual mean",
    "mm/năm": "mm/year",
    "TB cao nhất ngày": "Mean daily maximum",
    "TB thấp nhất ngày": "Mean daily minimum",
    "Nhiệt độ TB tháng": "Monthly mean temperature",
    "Tổng mưa năm": "Annual rainfall total",
    "Trung bình nhiều năm": "Multi-year mean",
    "Kt TB tháng": "Monthly mean Kt",
    "Rất sáng ≥ 0,60": "Very bright ≥ 0.60",
    "Trời quang ≥ 0,50": "Clear sky ≥ 0.50",
    "Nhiều mây ≥ 0,35": "Cloudy ≥ 0.35",
    "đang tải": "loading",
    "giây…": "seconds…",
    "đang gửi…": "sending…",
    "Đã lấy xong:": "Finished fetching:",
    "Có lớp dữ liệu mới — kết quả sẽ được tính lại.": "New data layer available — results will be recomputed.",
    "🛰 tự lấy · {}": "🛰 automatic · {}",
    "CSV bạn nạp": "CSV you loaded",
    "{} tháng · {}→{}": "{} months · {}→{}",
    "Gỡ": "Remove",
    "🛰 Tự lấy theo vị trí": "🛰 Fetch automatically by location",
    "Giữ lại {}% quan sát sau lọc mây.": "{}% of observations kept after cloud filtering.",
    "Mưa GPM IMERG (cần EARTHDATA_TOKEN), NDVI và nhiệt bề mặt (MODIS) được tự lấy khi bạn mở bước này. Có GPM thì A2, B1 dùng mưa GPM thay cho NASA POWER. SMAP L4 chưa có dịch vụ lấy nhanh → tải CSV độ ẩm vùng rễ (ngày, m³/m³) từ AppEEARS / Earthdata rồi nạp ở trên; có SMAP thì B1 dùng SMAP cho ẩm đất đầu vụ.": "GPM IMERG precipitation (EARTHDATA_TOKEN required), NDVI and land surface temperature (MODIS) are fetched automatically when you open this step. With GPM, A2 and B1 use GPM rainfall instead of NASA POWER. SMAP L4 has no quick-access service yet → download a root-zone soil moisture CSV (date, m³/m³) from AppEEARS / Earthdata and load it above; with SMAP, B1 uses SMAP for initial soil moisture.",
    "Hãy chọn vị trí ruộng trước.": "Please choose the field location first.",
    "✍ bạn nhập": "✍ entered by you",
    "Cấp cơ giới tầng mặt (USDA)": "Topsoil texture class (USDA)",
    "Cấp thoát nước": "Drainage class",
    "Độ mặn ECe": "Salinity ECe",
    "θ điểm héo": "θ wilting point",
    "θ đồng ruộng": "θ field capacity",
    "θ bão hòa": "θ saturation",
    "Bão hòa bazơ": "Base saturation",
    "C hữu cơ": "Organic C",
    "— chọn —": "— select —",
    "nhập số{}": "enter a number{}",
    "chưa có số": "no value yet",
    "Dùng {}: {}": "Use {}: {}",
    "Khai báo vụ ở bước 2 để tính B1 cho vụ tới.": "Declare a season in step 2 to compute B1 for the next season.",
    "Đang tính cân bằng nước cho vụ tới…": "Computing the water balance for the next season…",
    "Thiếu dữ liệu": "Missing data",
    "có tưới → 1": "irrigated → 1",
    "tính cho vụ tới · Ya/Ym": "computed for the next season · Ya/Ym",
    "Hệ số C (RUSLE) có sẵn trong CRD": "C-factor (RUSLE) built into the CRD",
    "Tại": "At",
    "Chỉ số nước, đất & địa hình của thửa": "Water, soil & terrain indicators of the field",
    "Số tự lấy theo vị trí; bạn nhập tay sẽ được ưu tiên.": "Values fetched automatically by location; your manual entries take priority.",
    "⏳ Đang lấy…": "⏳ Fetching…",
    "↻ Lấy lại theo vị trí": "↻ Fetch again by location",
    "🛰 Lấy số liệu theo vị trí": "🛰 Fetch data by location",
    "Hãy nhập một số trong khoảng {}–{}.": "Please enter a number between {}–{}.",
    "Đã xoá số bạn nhập.": "Your entered value was cleared.",
    "Đã dùng số bạn nhập.": "Your entered value is now used.",
    "Đã điền {} số liệu tự lấy — hãy kiểm tra và sửa nếu khác ruộng của bạn.": "Filled {} values automatically — please check and correct them if they differ from your field.",
    "Chưa lấy được thêm số liệu đất; bạn có thể nhập tay.": "No more soil data could be fetched; you can enter values manually.",
    "tự lấy NASA POWER khi mở bước Khí hậu": "fetched automatically from NASA POWER when you open the Climate step",
    "Có tưới → A2 = 1": "Irrigated → A2 = 1",
    "NASA POWER (chưa có GPM)": "NASA POWER (no GPM yet)",
    "Có tưới → B1 = 1": "Irrigated → B1 = 1",
    "SMAP + mưa vụ": "SMAP + seasonal rainfall",
    "POWER GWETROOT + mưa vụ": "POWER GWETROOT + seasonal rainfall",
    "cần mưa vụ (NASA) + cơ giới đất hoặc θ (SSURGO)": "needs seasonal rainfall (NASA) + soil texture or θ (SSURGO)",
    "cần nhập tay (ngoài Mỹ không có nguồn tự động)": "manual entry required (no automatic source outside the US)",
    "tự lấy từ": "fetched automatically from",
    "hoặc nhập tay": "or entered manually",
    "cần CEC (SSURGO/SoilGrids hoặc nhập tay)": "needs CEC (SSURGO/SoilGrids or manual entry)",
    "tự lấy SRTM 30 m hoặc nhập tay": "fetched automatically from SRTM 30 m or entered manually",
    "Hệ số C có sẵn trong CRD": "C-factor built into the CRD",
    "Diện tích, giá & năng suất bạn nhập": "Area, price & yield entered by you",
    "cần diện tích + giá bán + năng suất cơ sở (bước 2)": "needs area + selling price + baseline yield (step 2)",
    "Đủ dữ liệu cho cả": "Data available for all",
    "tiêu chí.": "criteria.",
    "Tự lấy được:": "Can be fetched automatically:",
    "Cần nhập tay:": "Manual entry needed:",
    "Dữ liệu tiêu chí": "Criteria data",
    "Tự lấy": "Fetch automatically",
    "Nhập tay": "Enter manually",
    "Đang tự lấy dữ liệu khí hậu và đất…": "Fetching climate and soil data automatically…",
    "Nguồn kịch bản: {}": "Profile source: {}",
    "Tự chỉnh": "Custom",
    "theo ý bạn": "your own choice",
    "đủ dữ liệu": "data complete",
    "tự lấy được": "can be fetched",
    "thiếu dữ liệu": "missing data",
    "Dùng tiêu chí {}": "Use criterion {}",
    "Trọng số {}": "Weight {}",
    "Bấm để loại / dùng lại": "Click to exclude / include again",
    "Chưa chọn tiêu chí nào.": "No criteria selected.",
    "Bạn chưa chọn ruộng ở đâu. Bấm lên bản đồ hoặc gõ tên nơi nhé.": "You have not chosen where your field is. Click on the map or type a place name.",
    "Bạn chưa khai báo vụ nào. Chọn một mẫu nhanh hoặc bấm “+ Thêm vụ”.": "You have not declared any season. Pick a quick example or click “+ Add season”.",
    "Hãy bật ít nhất một tiêu chí có trọng số lớn hơn 0.": "Please enable at least one criterion with a weight greater than 0.",
    "điểm / 100": "points / 100",
    "thiếu {}": "missing {}",
    "Nhờ mưa": "Rainfed",
    "{}{}/{} cây hợp lịch gieo (K1)": "{}{}/{} crops fit the sowing calendar (K1)",
    "Tính trên {}/{} tiêu chí được chọn{}": "Computed on {}/{} selected criteria{}",
    "· cây vụ trước của thửa:": "· field's previous crop:",
    "Chuỗi luân canh · {} → {}{}": "Crop rotation sequence · {} → {}{}",
    "· tổng giá trị kinh tế ≈": "· total economic value ≈",
    "Công cụ xếp hạng": "The tool ranks",
    "chuỗi hợp lệ — xem bảng ngay dưới bảng điểm.": "valid sequences — see the table right below the score table.",
    "Chuỗi nên cân nhắc: {}": "Recommended sequence: {}",
    "Score(P) = {} trên {} vụ cây{}. {}": "Score(P) = {} over {} crop seasons{}. {}",
    "Chưa xếp được chuỗi nào": "No sequence could be arranged",
    "Không cây nào gieo và thu kịp trong khoảng thời gian này theo cửa sổ gieo (K1) và các điều kiện K2–K4. Hãy kéo dài khoảng thời gian ở bước 2 hoặc nới K1.": "No crop can be sown and harvested within this period given the planting windows (K1) and constraints K2–K4. Extend the period in step 2 or relax K1.",
    "· vụ trước:": "· previous season:",
    "{} · {} → {} ({} ngày){}": "{} · {} → {} ({} days){}",
    "Mạnh nhất ở": "Strongest in",
    "Vụ tới nên cân nhắc: {}": "Recommended for the next season: {}",
    "Chưa cây nào hợp lịch vụ này": "No crop fits this season's calendar",
    "Mọi cây đều bị loại theo K1–K4. Cân nhắc để": "All crops are excluded by K1–K4. Consider leaving the field",
    "đất nghỉ": "fallow",
    ", hoặc chỉnh ngày bắt đầu / độ dài vụ ở bước 2.": ", or adjust the season start date / length in step 2.",
    "Vụ tới": "Next season",
    "Tổng (0–1)": "Total (0–1)",
    "bạn loại (K2)": "excluded by you (K2)",
    "loại theo": "excluded by",
    "thiếu": "missing",
    "Giá trị:": "Value:",
    "Ngưỡng / quy tắc (CRD): {}": "Threshold / rule (CRD): {}",
    "Cách tính:": "Calculation:",
    "Nguồn dữ liệu: {}": "Data source: {}",
    "Đóng góp vào điểm tổng: trọng số {}% × {} =": "Contribution to the total score: weight {}% × {} =",
    "· hạng": "· rank",
    "· A1 bỏ tháng ngủ đông, chỉ tính tháng": "· A1 excludes dormant months, only months",
    "Khí hậu tính trên {} ngày từ ngày bắt đầu vụ (tháng {}), {} năm {}–{}{}.": "Climate computed over {} days from the season start (months {}), {} years {}–{}{}.",
    "Điểm mạnh": "Strengths",
    "Hạn chế (điểm < 0,5)": "Limitations (score < 0.5)",
    "Bị loại / cần lưu ý": "Excluded / points to watch",
    "ΔA1 Nhiệt độ": "ΔA1 Temperature",
    "ΔA2 Lượng mưa": "ΔA2 Rainfall",
    "ΔA3 Bức xạ (Kt)": "ΔA3 Radiation (Kt)",
    "ΔB1 Ẩm đất đầu vụ (θ)": "ΔB1 Initial soil moisture (θ)",
    "tươi tốt": "thriving",
    "hơi héo": "slightly wilted",
    "héo": "wilted",
    "chết": "dead",
    "So với:": "Compared with:",
    "Năm gần nhất": "Most recent year",
    "Nóng +1,5°C": "Hot +1.5°C",
    "Khô −25%": "Dry −25%",
    "Nóng & khô": "Hot & dry",
    "Như cũ": "Unchanged",
    "Đang tính…": "Computing…",
    "trong kịch bản": "in the scenario",
    "hiện nay": "currently",
    "· chuỗi tốt nhất {} · Score {}": "· best sequence {} · Score {}",
    "Không xếp được chuỗi nào": "No sequence could be arranged",
    "hợp nhất {} · {}/100 · cây {}": "best fit {} · {}/100 · crop {}",
    "Không cây nào khả thi cho vụ tới": "No crop is feasible for the next season",
    "Score hiện nay": "Current score",
    "Số vụ cây": "Crop seasons",
    "Đơn vị so sánh là cả chuỗi luân canh. Kéo một thanh hoặc chọn tình huống để xem chuỗi nào còn tốt nhất.": "The unit of comparison is the whole rotation sequence. Drag a slider or choose a situation to see which sequence remains best.",
    "Đổi chuỗi đứng đầu:": "Top sequence changes:",
    "Chuỗi đứng đầu không đổi": "Top sequence unchanged",
    "năm gần nhất": "most recent year",
    "trung bình nhiều năm": "multi-year mean",
    "{} · so với {}": "{} · compared with {}",
    "mới": "new",
    "Kịch bản": "Scenario",
    "Hiện nay": "Current",
    "Chênh": "Difference",
    "loại": "excluded",
    "Điểm hiện nay": "Current score",
    "Hạng": "Rank",
    "Khí hậu – nước (A1 · A2 · A3 · B1)": "Climate – water (A1 · A2 · A3 · B1)",
    "Kéo một thanh hoặc chọn tình huống để so sánh.": "Drag a slider or choose a situation to compare.",
    "Đổi cây đứng đầu:": "Top crop changes:",
    "Cây đứng đầu không đổi:": "Top crop unchanged:",
    "Không cây nào khả thi": "No feasible crop",
    "Tiêu chí khí hậu – nước thay đổi": "Climate – water criteria changed",
    "Nhiệt độ trong vụ (°C)": "In-season temperature (°C)",
    "Mưa năm (mm)": "Annual rainfall (mm)",
    "mưa năm ở ruộng": "annual rainfall at the field",
    "Nhu cầu nước cả vụ ETm (mm)": "Seasonal crop water requirement ETm (mm)",
    "Độ sâu rễ hiệu quả Zr (m)": "Effective rooting depth Zr (m)",
    "độ sâu tầng đất": "soil depth",
    "Độ sâu tầng đất (cm)": "Soil depth (cm)",
    "thửa của bạn": "your field",
    "pH thửa": "field pH",
    "Độ mặn ECe (dS/m)": "Salinity ECe (dS/m)",
    "EC thửa": "field EC",
    "Hệ số che phủ C (RUSLE) — thấp là tốt": "Cover-management factor C (RUSLE) — lower is better",
    "Nhóm": "Group",
    "Chu kỳ": "Cycle",
    "{}–{} ngày": "{}–{} days",
    "Rễ Zr": "Roots Zr",
    "Hệ số C": "C-factor",
    "Vụ tới: {}": "Next season: {}",
    "Rễ": "Roots",
    "A1 – Nhiệt độ (°C, TB trong vụ)": "A1 – Temperature (°C, in-season mean)",
    "A2 – Mưa năm (mm)": "A2 – Annual rainfall (mm)",
    "A3 – Bức xạ": "A3 – Radiation",
    "B1 – Nhu cầu nước cả vụ ETm (mm) · Ky": "B1 – Seasonal crop water requirement ETm (mm) · Ky",
    "Độ sâu rễ hiệu quả Zr (m), dùng cho B1": "Effective rooting depth Zr (m), used for B1",
    "C1 – Độ sâu tầng đất": "C1 – Soil depth",
    "C2 – Thành phần cơ giới": "C2 – Soil texture",
    "C4 – Thoát nước, úng": "C4 – Drainage, waterlogging",
    "C5 – Độ phì, CEC": "C5 – Fertility, CEC",
    "C6 – Độ mặn ECe (dS/m): bắt đầu giảm / giảm 50% / mất trắng": "C6 – Salinity ECe (dS/m): yield decline starts / 50% decline / total loss",
    "D1 – Độ dốc (%)": "D1 – Slope (%)",
    "E1 – Che phủ đất: hệ số C (RUSLE)": "E1 – Land cover: C-factor (RUSLE)",
    "K1 (loại trừ) – Gieo → thu ở Kansas; chu kỳ sinh trưởng": "K1 (exclusion) – Sowing → harvest in Kansas; growth cycle",
    "Dữ liệu: {}": "Data: {}",
    "A3 – lớp bức xạ từ Kt:": "A3 – radiation classes from Kt:",
    "C2 – nhóm cơ giới:": "C2 – texture groups:",
    "nhẹ: {}; trung bình: {}; nặng: {}.": "light: {}; medium: {}; heavy: {}.",
    "C4 – cấp thoát nước → điểm (cây ưa cạn):": "C4 – drainage class → score (dryland crops):",
    "Giả định:": "Assumptions:",
    "Chưa có số của ruộng bạn để so.": "No value from your field to compare yet.",
    "Khả thi (K1)": "Feasible (K1)",
    "Tổng 0-1": "Total 0-1",
    "có": "yes",
    "không": "no",
    "Trọng số": "Weight",
    "Không tải được /api/meta": "Could not load /api/meta",
    "Không tải được bản đồ (cần mạng). Bạn vẫn có thể nhập vĩ độ/kinh độ ở khung bên phải hoặc dùng ví dụ.": "Could not load the map (network required). You can still enter latitude/longitude in the panel on the right or use an example.",
    "Đang hiển thị lớp": "Showing layer",
    "trên bản đồ giám sát": "on the monitoring map",
    "Hiển thị ở bản đồ giám sát (trang chủ)": "Shown on the monitoring map (home page)",
    "Không gọi được NASA POWER — đang dùng khí hậu MÔ PHỎNG (DEMO)": "Could not reach NASA POWER — using SIMULATED climate (DEMO)",
    "Đang dùng: {}–{} ({} năm) · {}": "In use: {}–{} ({} years) · {}",
    "Sẽ tự tải khi mở bước 3 – Khí hậu": "Will load automatically when you open step 3 – Climate",
    "Đang dùng: {} tháng ({}→{}) cho A2, B1": "In use: {} months ({}→{}) for A2, B1",
    "Chưa có EARTHDATA_TOKEN trong .env → A2, B1 đang dùng mưa NASA POWER": "No EARTHDATA_TOKEN in .env → A2, B1 use NASA POWER rainfall",
    "Chưa tải (tự tải ở bước 3)": "Not loaded (loads automatically in step 3)",
    "Đang dùng: {} tháng cho θ đầu vụ (B1)": "In use: {} months for initial θ (B1)",
    "Chưa nạp CSV → B1 ước tính θ từ NASA POWER GWETROOT": "No CSV loaded → B1 estimates θ from NASA POWER GWETROOT",
    "Đã tải {} tháng (tham khảo, không vào điểm)": "Loaded {} months (reference only, not scored)",
    "Ruộng ngoài Hoa Kỳ — SSURGO không phủ": "Field outside the United States — not covered by SSURGO",
    "Đang dùng cho {} trường số liệu của thửa": "Used for {} data fields of the field",
    "Đã lấy, nhưng bạn đang dùng số khác (nhập tay / nguồn khác)": "Fetched, but you are using other values (manual / other source)",
    "Chưa lấy (bấm “Lấy số liệu theo vị trí” ở bước 4)": "Not fetched (click “Fetch data by location” in step 4)",
    "Khác": "Other",
    "Biến": "Variables",
    "Độ phân giải": "Resolution",
    "Cách lấy": "Access",
    "Dùng cho": "Used for",
    "Chép": "Copy",
    "nguồn dữ liệu NASA · {} đang dùng cho ruộng này": "NASA data sources · {} in use for this field",
    "nguồn khác (đất + CRD)": "other sources (soil + CRD)",
    "Không dùng AI khi chạy — mọi số do Python tính": "No AI at runtime — every number is computed by Python",
    "Có dùng dữ liệu NASA — điều kiện để xét giải toàn cầu": "Uses NASA data — a requirement for global award eligibility",
    "Hình ảnh": "Images",
    "Minh hoạ thời tiết, cây trồng, banner": "Weather, crop and banner illustrations",
    "SVG vẽ bằng mã trong file": "SVG drawn in code within the file",
    "Không dùng ảnh do AI tạo; mã vẽ được viết với hỗ trợ của AI (xem mục Công cụ AI).": "No AI-generated images; the drawing code was written with AI assistance (see AI tools).",
    "Ảnh trang mở đầu (thư mục static/)": "Landing page image (static/ folder)",
    "Ảnh của bên thứ ba — nhóm cần xác nhận giấy phép sử dụng trước khi nộp.": "Third-party image — the team must confirm the usage licence before submitting.",
    "Ở đâu:": "Where:",
    "Như thế nào:": "How:",
    "Công cụ": "Tool",
    "Dùng ở đâu": "Where used",
    "Dùng như thế nào": "How used",
    "Phần nào của dự án": "Which part of the project",
    "Cách dùng, nhóm kiểm tra lại ra sao": "How it was used and how the team checked it",
    "Đã lưu ở": "Saved at",
    "Đây là khai báo mặc định — nhóm hãy sửa cho đúng thực tế (kể cả AI dùng để viết slide, video, ảnh) rồi bấm": "This is the default declaration — the team should edit it to reflect reality (including AI used for slides, videos, images), then click",
    ". Ảnh/video do AI tạo phải có dấu \"AI-generated\" hiển thị.": ". AI-generated images/videos must carry a visible \"AI-generated\" label.",
    "Đã lưu khai báo công cụ AI.": "AI tool declaration saved.",
    "Đã chép trích dẫn.": "Citation copied.",
    "# FARM ADAPT v{} — Dữ liệu, tài nguyên và công cụ AI": "# FARM ADAPT v{} — Data, resources and AI tools",
    "## Nhóm tác giả": "## Authors",
    "## Dữ liệu NASA": "## NASA data",
    "- **{}** ({}) — dùng cho {}. Truy cập: {}.": "- **{}** ({}) — used for {}. Access: {}.",
    "- Trích dẫn: {}": "- Citation: {}",
    "## Dữ liệu khác": "## Other data",
    "## Cơ sở dữ liệu yêu cầu cây trồng (CRD)": "## Crop Requirement Database (CRD)",
    "## Tài nguyên, thư viện & phương pháp": "## Resources, libraries & methods",
    "- Minh hoạ: SVG vẽ bằng mã trong file; không dùng ảnh do AI tạo.": "- Illustrations: SVG drawn in code within the file; no AI-generated images.",
    "- Ảnh trang mở đầu: {} (bên thứ ba — cần xác nhận giấy phép).": "- Landing page image: {} (third party — licence to be confirmed).",
    "## Công cụ AI": "## AI tools",
    "### AI bên trong công cụ": "### AI inside the tool",
    "- {}. Nhà cung cấp hỗ trợ: {}.": "- {}. Supported providers: {}.",
    "### AI nhóm dùng khi phát triển": "### AI used by the team during development",
    "- **{}** — ở đâu: {}; như thế nào: {}": "- **{}** — where: {}; how: {}",
    "## Trạng thái nguồn với ruộng đang chọn": "## Source status for the selected field",
    "Đã sao chép bản khai.": "Declaration copied.",
    "Không sao chép được — hãy bôi đen và chép tay.": "Could not copy — please select the text and copy it manually.",
    "Đề xuất cây cho vụ tới": "Crop recommendation for the next season",
    "Khai báo các vụ trong năm; công cụ chấm điểm từng cây cho vụ sắp tới và nhân với hiệu ứng luân canh sau cây vụ trước: V = S × M.": "Declare the seasons in the year; the tool scores each crop for the upcoming season and multiplies by the rotation effect after the previous crop: V = S × M.",
    "Đề xuất một chuỗi luân canh": "Recommend a crop rotation sequence",
    "Chỉ cần ngày bắt đầu và ngày kết thúc; công cụ tự xếp mọi chuỗi cây vừa trong khoảng này và xếp hạng theo Score(P).": "Only a start and end date are needed; the tool arranges every crop sequence that fits within this period and ranks them by Score(P).",
    "Đang chọn": "Selected",
    "Chọn": "Select",
    "Không có / không rõ": "None / unknown",
    "Ngày kết thúc": "End date",
    "Thời gian làm đất giữa 2 cây": "Land preparation time between 2 crops",
    "Cây vụ trước của thửa": "Field's previous crop",
    "{} → {} · {} ngày. Công cụ tự xếp cây theo cửa sổ gieo và thời gian sinh trưởng trong CRD.": "{} → {} · {} days. The tool arranges crops by planting window and growth duration in the CRD.",
    "Nhập ngày bắt đầu và ngày kết thúc (ít nhất 90 ngày, tối đa 5 năm).": "Enter the start and end dates (at least 90 days, at most 5 years).",
    "Diện tích ruộng A": "Field area A",
    "Giá bán P (USD/tấn)": "Selling price P (USD/t)",
    "Năng suất cơ sở Y_base (tấn/ha)": "Baseline yield Y_base (t/ha)",
    "Điền số minh hoạ Kansas": "Fill in illustrative Kansas values",
    "F1 = G / G lớn nhất trong các cây (G ≤ 0 → 0). Số minh hoạ chỉ để thử — hãy sửa theo giá & năng suất thực tế.": "F1 = G / largest G among the crops (G ≤ 0 → 0). Illustrative values are for testing only — edit them to actual prices & yields.",
    "Đã điền số minh hoạ — nhớ sửa theo thực tế.": "Illustrative values filled in — remember to edit them to actual values.",
    "Bỏ cặp cấm": "Remove banned pair",
    "Chưa có cặp cấm.": "No banned pairs yet.",
    "Thêm cặp cấm": "Add banned pair",
    "Cây sau →": "Next crop →",
    "↓ Cây trước": "↓ Previous crop",
    "vụ trước của bạn": "your previous season",
    "; bị loại theo K3": "; excluded by K3",
    "Độc canh — mốc so sánh{}": "Monoculture — baseline for comparison{}",
    "cấm": "banned",
    "Không có dữ liệu{}": "No data{}",
    "Không có dữ liệu — tính E = 0 (M = 1)": "No data — counted as E = 0 (M = 1)",
    "· có ý nghĩa thống kê": "· statistically significant",
    "Khoảng tin cậy 95% [{}; {}] · n = {} · M = {}{}": "95% confidence interval [{}; {}] · n = {} · M = {}{}",
    "tăng năng suất": "yield increase",
    "giảm năng suất": "yield decrease",
    "có ý nghĩa thống kê": "statistically significant",
    "không có dữ liệu (E = 0)": "no data (E = 0)",
    "Rê chuột lên ô để xem khoảng tin cậy, n và M · bấm ô để thêm / bỏ cặp cấm K4": "Hover a cell to see the confidence interval, n and M · click a cell to add / remove a K4 banned pair",
    "Hệ số luân canh": "Rotation factor",
    "M(p, c) = 1 + E(p, c)/100, với E là % thay đổi năng suất của cây c khi trồng sau cây p.": "M(p, c) = 1 + E(p, c)/100, where E is the % yield change of crop c when grown after crop p.",
    "— V(c) = S(c, t, x) × M(p, c): S là điểm phù hợp 0–1 của bảng điểm, p là cây vụ trước. Cây đề xuất là cây có V cao nhất trong số cây qua K1–K4.": "— V(c) = S(c, t, x) × M(p, c): S is the 0–1 suitability score from the score table, p is the previous crop. The recommended crop is the one with the highest V among crops passing K1–K4.",
    "— Score(P) = (1/T)[S(c₁) + Σₜ₌₂ S(cₜ)·M(cₜ₋₁, cₜ)], T là số vụ có cây. Vụ đất nghỉ không cộng S, không tính vào T nhưng tác động cây sau qua M(đất nghỉ, c).": "— Score(P) = (1/T)[S(c₁) + Σₜ₌₂ S(cₜ)·M(cₜ₋₁, cₜ)], T is the number of cropped seasons. A fallow season adds no S and is not counted in T, but affects the next crop through M(fallow, c).",
    "Số liệu là trung bình toàn cầu, chưa riêng cho Kansas; nhiều cặp chưa có ý nghĩa thống kê nên chưa chắc có tác động.": "Values are global means, not Kansas-specific; many pairs are not statistically significant, so an effect is not certain.",
    "Bài toán:": "Problem:",
    "chuỗi luân canh": "crop rotation sequence",
    ". Cây vụ trước của thửa:": ". Field's previous crop:",
    "— chỉ dùng cho K3/K4 với cây đầu chuỗi (vụ đầu không nhân M).": "— only used for K3/K4 with the first crop of the sequence (the first season is not multiplied by M).",
    "chưa rõ": "unknown",
    "— hàng tô đậm trong ma trận là các hệ số M sẽ nhân với điểm S.": "— the highlighted row in the matrix holds the M factors that multiply the S scores.",
    "— khai báo cây cho vụ đang trồng / vừa xong ở bước 2 để dùng hệ số M (hiện M = 1).": "— declare the crop of the current / just-finished season in step 2 to use the M factor (currently M = 1).",
    "vụ tới": "next season",
    ". Cây vụ trước:": ". Previous crop:",
    "% thay đổi năng suất cây sau so với độc canh —": "% yield change of the following crop compared with monoculture —",
    "Đã bỏ cặp cấm {} → {}.": "Removed banned pair {} → {}.",
    "Đã cấm trồng {} sau {} (K4).": "Banned growing {} after {} (K4).",
    "Kết quả chuỗi luân canh: điểm phù hợp × ma trận luân canh": "Rotation sequence results: suitability score × rotation matrix",
    "{} chuỗi hợp lệ trong {} → {} · làm đất {} ngày": "{} valid sequences in {} → {} · {} days of land preparation",
    "bỏ một lượt gieo": "skip one sowing turn",
    "không có dữ liệu (0)": "no data (0)",
    "Xem thêm": "Show",
    "chuỗi": "sequences",
    "Không có chuỗi hợp lệ — kéo dài khoảng thời gian ở bước 2, nới K1 hoặc bỏ bớt cặp cấm K4.": "No valid sequence — extend the period in step 2, relax K1 or remove some K4 banned pairs.",
    "* Cặp không có dữ liệu trong Mudare et al. (2025), tính E = 0:": "* Pairs without data in Mudare et al. (2025), counted as E = 0:",
    "F1 chưa có dữ liệu kinh tế (bước 2) nên không có G.": "F1 has no economic data (step 2), so no G.",
    "Số tổ hợp quá lớn — đã dừng sớm.": "Too many combinations — stopped early.",
    "Cây vụ trước:": "Previous crop:",
    "— hệ số M lấy ở hàng “": "— the M factor is taken from row “",
    "” của ma trận luân canh": "” of the rotation matrix",
    "Chưa rõ cây vụ trước → M = 1 cho mọi cây (khai báo cây của vụ đang trồng ở bước 2)": "Previous crop unknown → M = 1 for every crop (declare the crop of the current season in step 2)",
    "Kết hợp ma trận luân canh: V(c) = S × M(cây trước, c)": "Combining the rotation matrix: V(c) = S × M(previous crop, c)",
    "Xem ma trận": "View matrix",
    "S (bảng điểm)": "S (score table)",
    "E(cây trước, c)": "E(previous crop, c)",
    "độc canh": "monoculture",
    "· có ý nghĩa": "· significant",
    "Đề xuất": "Recommended",
    "Loại theo": "Excluded by",
    "Cặp không có dữ liệu (E = 0): {} → {}.": "Pairs without data (E = 0): {} → {}.",
    "A1 · Nhiệt độ 2 m": "A1 · 2 m air temperature",
    "A2 · Lượng mưa": "A2 · Precipitation",
    "mm/ngày": "mm/day",
    "A3 · Chỉ số Kt": "A3 · Clearness index Kt",
    "B1 · Độ ẩm đất mặt": "B1 · Surface soil wetness",
    "mm/tháng": "mm/month",
    "Không tải được lớp NASA POWER ({}) — kiểm tra mạng hoặc mở": "Could not load the NASA POWER layer ({}) — check the network or open",
    "màu mặc định của dịch vụ": "service default colours",
    "Tháng": "Month",
    "(bạn chọn)": "(your choice)",
    "(đang trong vụ)": "(currently in season)",
    "không có cây đang trong vụ — chỉ dùng phương pháp thống kê": "no crop currently in season — statistical method only",
    "; vụ tới:": "; next season:",
    "Số liệu đến ngày": "Data up to",
    "(trễ {} ngày) · cây theo dõi:": "(lag {} days) · monitored crop:",
    "không theo dõi": "not monitored",
    "· phân vị {}": "· percentile {}",
    "· từ đầu vụ {} mm": "· since season start {} mm",
    "TB cùng kỳ {}{}{}{}{}": "Same-period mean {}{}{}{}{}",
    "Phương pháp đã báo: {}": "Methods that triggered: {}",
    "Không có cảnh báo": "No warnings",
    "Các yếu tố đang theo dõi đều trong ngưỡng bình thường.": "All monitored factors are within normal ranges.",
    "cảnh báo đang mở": "open warnings",
    "Thời tiết bình thường": "Weather is normal",
    "30 ngày": "30 days",
    "90 ngày": "90 days",
    "6 tháng": "6 months",
    "1 năm": "1 year",
    "Từ đầu vụ": "Since season start",
    "Nhiệt độ TB 7 ngày (°C)": "7-day mean temperature (°C)",
    "Mưa cộng dồn 30 ngày (mm)": "30-day cumulative rainfall (mm)",
    "Kt TB 7 ngày": "7-day mean Kt",
    "Ẩm vùng rễ (0–1)": "Root-zone soil wetness (0–1)",
    "Phân vị 90 lịch sử": "Historical 90th percentile",
    "Phân vị 10 lịch sử": "Historical 10th percentile",
    "Trung vị cùng kỳ": "Same-period median",
    "— năm nay": "— this year",
    "Tối ưu của": "Optimum for",
    "Tự động (cây của vụ đang diễn ra)": "Automatic (crop of the current season)",
    "1. Yếu tố theo dõi": "1. Monitored factors",
    "2. Phương pháp": "2. Methods",
    "So với ngưỡng chịu đựng của cây trong CRD": "Compared with the crop's tolerance limits in the CRD",
    "Biên “sắp đến giới hạn” m:": "“Approaching the limit” margin m:",
    "bề rộng vùng chịu đựng": "of the tolerance range width",
    "Cây trên thửa": "Crop on the field",
    "Phân vị so với cùng thửa, ±15 ngày, mọi năm": "Percentile relative to the same field, ±15 days, all years",
    "Chú ý khi ≤ / ≥ phân vị": "Watch at ≤ / ≥ percentile",
    "Cảnh báo khi ≤ / ≥ phân vị": "Warning at ≤ / ≥ percentile",
    "Trên giao diện": "In the interface",
    "Email (chưa kết nối hạ tầng)": "Email (infrastructure not connected)",
    "Thông báo đẩy (chưa kết nối hạ tầng)": "Push notification (infrastructure not connected)",
    "3. Kênh nhận": "3. Delivery channels",
    "Chọn {} yếu tố × {} phương pháp =": "Selected {} factors × {} methods =",
    "{} quy tắc": "{} rules",
    ". Mỗi yếu tố chỉ hiện một cảnh báo (mức cao nhất); chỉ báo lại khi mức tăng lên.": ". Each factor shows only one warning (highest level); it is re-notified only when the level increases.",
    "Lưu & áp dụng": "Save & apply",
    "Đóng": "Close",
    "Chọn ít nhất 1 yếu tố và 1 phương pháp.": "Select at least 1 factor and 1 method.",
    "Mức phân vị “Cảnh báo” phải nhỏ hơn mức “Chú ý”.": "The “Warning” percentile must be lower than the “Watch” percentile.",
    "Đã lưu cấu hình cảnh báo.": "Warning settings saved.",
    "Tiếp tục dùng công cụ →": "Continue using the tool →",
    "Chọn ruộng và khai báo mùa vụ để so sánh kịch bản cho vụ tới": "Choose a field and declare seasons to compare scenarios for the next season",
    "Vụ tới: {} · bắt đầu {} — kéo các thanh A1, A2, A3, B1 để xem cây nào còn hợp": "Next season: {} · starts {} — drag the A1, A2, A3, B1 sliders to see which crops still fit",
    "Khai báo mùa vụ (bước 2) để so sánh kịch bản cho vụ tới": "Declare seasons (step 2) to compare scenarios for the next season",
    "Chuỗi luân canh {} → {} — kéo các thanh A1, A2, A3, B1 để xem chuỗi nào còn tốt nhất": "Crop rotation sequence {} → {} — drag the A1, A2, A3, B1 sliders to see which sequence remains best",
    "· vụ tới:": "· next season:",
    "từ": "from",
    "Đổi": "Change",
    "Bản đồ vẫn xem được; chọn ruộng để nhận cảnh báo riêng.": "The map is still viewable; choose a field to receive your own warnings.",
    "Nguồn trên trang này:": "Sources on this page:",
    "Nguồn đầy đủ & lưu ý →": "Full sources & notes →",
    "{} {} chưa tính vì thiếu dữ liệu: {}": "{} {} not computed due to missing data: {}",
    "Lưu ý cho lần tính gần nhất": "Notes for the latest run",
    "ΔT nhiệt độ": "ΔT temperature",
    "ΔP lượng mưa": "ΔP rainfall",
    "ΔKt bức xạ": "ΔKt radiation",
    "Δθ ẩm đất đầu vụ": "Δθ initial soil moisture",
    "{} tiêu chí → {} tổ hợp": "{} criteria → {} combinations",
    "Chọn ít nhất 1 tiêu chí": "Select at least 1 criterion",
    "Mốc so sánh:": "Baseline:",
    "Năm ngoái": "Last year",
    "Chạy so sánh": "Run comparison",
    "A2 và B1 dùng chung mưa: khi có ΔP thì mưa trong vụ của B1 cũng nhận ΔP; Δθ của B1 chỉ áp vào nước trong đất đầu vụ. Δ+ mặc định theo hướng tăng của tiêu chí chọn đầu tiên (nóng – khô nếu A1 trước), Δ− là tổ hợp ngược lại.": "A2 and B1 share rainfall: with ΔP, B1's in-season rainfall also gets ΔP; B1's Δθ only applies to initial soil water. Δ+ defaults to the increasing direction of the first selected criterion (hot – dry if A1 is first), Δ− is the opposite combination.",
    "Không có chuỗi hợp lệ.": "No valid sequence.",
    "Chuỗi đứng đầu khác baseline:": "Top sequence differs from baseline:",
    "Chuỗi đứng đầu giữ nguyên": "Top sequence unchanged",
    "loại ({})": "excluded ({})",
    "Cây đứng đầu khác baseline: {} →": "Top crop differs from baseline: {} →",
    "Cây đứng đầu giữ nguyên": "Top crop unchanged",
    "· đổi cây đầu": "· top crop changes",
    "năm ngoái": "last year",
    "Kịch bản tăng (Δ+)": "Increase scenario (Δ+)",
    "Kịch bản giảm (Δ−)": "Decrease scenario (Δ−)",
    "Tất cả {} tổ hợp:": "All {} combinations:",
    "Khí hậu DEMO.": "DEMO climate.",
    "Đơn vị so sánh là cả chuỗi luân canh: mỗi cột xếp hạng các chuỗi theo Score(P) sau khi chấm lại S của từng vụ với Δ. Khoảng {} → {}.{}": "The unit of comparison is the whole rotation sequence: each column ranks sequences by Score(P) after re-scoring S for each season with Δ. Period {} → {}.{}",
    "— chưa có, M = 1": "— none yet, M = 1",
    "Mỗi cột: xếp hạng theo V = S × M (M theo cây vụ trước{}). Vụ: {} từ {}.{}": "Each column: ranked by V = S × M (M by previous crop{}). Season: {} from {}.{}",
    "Chọn ít nhất 1 tiêu chí biến động.": "Select at least 1 varying criterion.",
    "chưa đặt email trong .env": "email not set in .env",
    "Minh họa thời tiết theo thanh kéo": "Weather illustration driven by the sliders",
    "đang bật (lệch ±{} ngày)": "on (tolerance ±{} days)",
    "— hệ số M lấy ở hàng “{}” của ma trận luân canh": "— the M factor is taken from the “{}” row of the rotation matrix",
    "Nước": "Water",
    "Tra cứu": "Reference",
    "Nhiệt độ trong vụ": "In-season temperature",
    "Mưa năm": "Annual rainfall",
    "Nhu cầu nước cả vụ ETm": "Seasonal crop water requirement ETm",
    "Độ sâu rễ hiệu quả Zr": "Effective rooting depth Zr",
    "Hệ số che phủ C": "Cover-management factor C",
    "lúa mì đông": "winter wheat",
    "lúa mì": "wheat",
    "ngô": "maize",
    "cao lương": "sorghum",
    "đậu tương": "soybean",
    "tháng": "month",
    "năm": "year",
    "cây": "crop",
    "vụ": "season",
    "Xem thêm {} chuỗi": "Show {} more sequences",
    "{} cây · có nguồn": "{} crops · sourced",
    "% thay đổi năng suất cây sau so với độc canh — {}": "% yield change of the following crop compared with monoculture — {}",
    "· vụ trước: {}": "· previous crop: {}",
    "· cây vụ trước của thửa: {}": "· field's previous crop: {}",
    "Công cụ xếp hạng {} chuỗi hợp lệ — xem bảng ngay dưới bảng điểm.": "The tool ranks {} valid sequences — see the table right below the score table.",
    "có ý nghĩa": "significant",
    "Tại {}": "At {}",
    "{} (loại)": "{} (excluded)",
    "(loại)": "(excluded)",
    "vụ tới: {} từ {}": "next season: {} from {}",
    "(bỏ tháng ngủ đông: chỉ tính {})": "(dormant months excluded: only {} counted)",
    "(sau {}). {}": "(after {}). {}",
    "(sau {}).": "(after {}).",
    "Kt TB": "Mean Kt",
    # v0.9.4 — bảng điểm từng bước của chuỗi
    "Không có lượt gieo nào vừa cửa sổ gieo (K1) sau ngày {}.": "No sowing turn fits the planting window (K1) after {}.",
    "Không kịp thu hoạch trước ngày kết thúc chuỗi ({}).": "Cannot be harvested before the sequence end date ({}).",
    "Gặp sương giá đầu thu trước khi chín (K1).": "Would meet the first fall frost before maturity (K1).",
    "Không còn đủ thời gian để bỏ một lượt gieo trước ngày kết thúc.": "Not enough time left to skip a sowing turn before the end date.",
    "Bảng điểm từng bước của chuỗi tốt nhất": "Step-by-step score tables for the best sequence",
    "Mỗi bảng là một bước của chuỗi: các phương án có thể chọn lúc đó và vì sao phương án tô đậm được chọn · bấm ô để xem cách tính": "Each table is one step of the sequence: the options available at that moment and why the highlighted option was chosen · click a cell to see the calculation",
    "Không có chuỗi hợp lệ nên chưa có bảng điểm từng bước.": "No valid sequence, so there are no step-by-step score tables yet.",
    "Chuỗi tốt nhất: {}": "Best sequence: {}",
    "Để đất nghỉ cho Score(P) tốt nhất khi đi tiếp: {}, cao hơn gieo ngay {} ({}).": "Leaving the field fallow gives the best Score(P) for the rest of the sequence: {}, higher than sowing {} right away ({}).",
    "Để đất nghỉ cho Score(P) tốt nhất khi đi tiếp: {}.": "Leaving the field fallow gives the best Score(P) for the rest of the sequence: {}.",
    "Đất nghỉ không có điểm S và không tính vào T, nhưng cây gieo sau đó được nhân hệ số M(đất nghỉ, c) và gieo ở cửa sổ gieo năm sau.": "Fallow has no S score and is not counted in T, but the crop sown afterwards is multiplied by M(fallow, c) and sown in the following year's planting window.",
    "Vụ đầu chuỗi: chưa có cây trước nên M = 1.": "First season of the sequence: there is no previous crop, so M = 1.",
    "Cây sau đất nghỉ được gieo ở cửa sổ gieo năm sau; hệ số M lấy ở hàng “Đất nghỉ” của ma trận luân canh.": "The crop after fallow is sown in the following year's planting window; its M factor comes from the “Fallow” row of the rotation matrix.",
    "{} cho Score(P) tốt nhất khi đi tiếp: {}.": "{} gives the best Score(P) for the rest of the sequence: {}.",
    "Phương án kế tiếp: {} ({}).": "Next best option: {} ({}).",
    "{} cũng có V = S × M cao nhất ở bước này ({}).": "{} also has the highest V = S × M at this step ({}).",
    "V = S × M của {} ({}) không cao nhất, nhưng chọn nó mở ra các vụ sau tốt hơn.": "{}'s V = S × M ({}) is not the highest, but choosing it opens up better later seasons.",
    "Bước {}: để đất nghỉ": "Step {}: leave the field fallow",
    "Bước {}: chọn {}": "Step {}: choose {}",
    "Thời điểm quyết định {}": "Decision date {}",
    "cây trước: {}": "previous crop: {}",
    "không có": "none",
    "gieo {} → thu hoạch {}": "sow {} → harvest {}",
    "ngày gieo {}": "sown {}",
    "Score(P) nếu chọn": "Score(P) if chosen",
    "✓ được chọn": "✓ chosen",
    "loại": "excluded",
    "Bỏ một lượt gieo: không tính S; cây sau gieo ở cửa sổ gieo năm sau và nhân hệ số M(đất nghỉ, c).": "Skip one sowing turn: no S score; the next crop is sown in the following year's planting window and multiplied by M(fallow, c).",
    "M = 1 (vụ đầu)": "M = 1 (first season)",
    "Rê chuột lên ô để xem khoảng tin cậy, n và M": "Hover a cell to see the confidence interval, n and M",
}

# ───────────────────────── API ─────────────────────────
@app.before_request
def _set_lang():
    g.lang = "en" if (request.headers.get("X-Lang") or request.args.get("lang") or "").lower().startswith("en") else "vi"


def _err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

def poly_area_ha(pts):
    if len(pts) < 3:
        return 0.0, None
    lat0 = mean(p[0] for p in pts)
    kx, ky = 111320.0 * math.cos(math.radians(lat0)), 110540.0
    xy = [((p[1]) * kx, (p[0]) * ky) for p in pts]
    a = sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1] for i in range(len(xy))) / 2.0
    return abs(a) / 10000.0, [mean(p[0] for p in pts), mean(p[1] for p in pts)]

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "app": APP_NAME, "version": VERSION, "ai": ai_ready(), "ai_providers": [k for k, _ in ai_providers()]})

@app.route("/api/meta")
def api_meta():
    y0, y1 = power_years()
    return jsonify({"app": APP_NAME, "full": APP_FULL, "slogan": APP_SLOGAN, "version": VERSION, "ai": ai_ready(), "ai_providers": [k for k, _ in ai_providers()],
                    "power_years": [y0, y1], "crops": list(CROPS.values()), "fallow": FALLOW, "groups": GROUP_VI, "crd_sources": CRD_SOURCES, "crd_notes": CRD_NOTES,
                    "criteria": [dict(CRIT_DEF[k], code=k) for k in CRIT_ORDER], "group_names": GROUP_NAMES,
                    "profiles": {k: {"name": v[0], "groups": v[1], "src": v[2], "weights": profile_weights(k)} for k, v in GROUP_PROFILES.items()},
                    "texture_group": TEXTURE_GROUP, "texture_vi": USDA_VI, "drainage": DRAINAGE, "kt_classes": KT_CLASSES, "rawls": RAWLS,
                    "layer_kinds": LAYER_KINDS, "assumptions": ASSUMPTIONS, "kansas_bbox": KANSAS_BBOX, "earthdata_token": bool(EARTHDATA_TOKEN), "disclaimer": DISCLAIMER,
                    "c5_table": C5_TABLE, "authors": authors_list(), "rotation": rot_matrix(), "rot_assumptions": ROT_ASSUMPTIONS, "scen_keys": SCEN_KEYS, "monitor": {"factors": MON_FACTORS, "default": MON_DEFAULT, "levels": MON_LEVELS, "limits": MON_LIMITS}, "notes": NOTES})

@app.route("/api/crd")
def api_crd():
    return jsonify({"ok": True, "crops": list(CROPS.values()), "fallow": FALLOW, "sources": CRD_SOURCES, "notes": CRD_NOTES})

@app.route("/api/area", methods=["POST"])
def api_area():
    pts = (request.get_json(silent=True) or {}).get("points") or []
    pts = [[num(p[0]), num(p[1])] for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2 and num(p[0]) is not None and num(p[1]) is not None]
    ha, c = poly_area_ha(pts)
    return jsonify({"ok": True, "area_ha": round(ha, 3), "centroid": c, "perimeter_m": None})


def _ascii(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def _geo_nominatim(q):
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"format": "jsonv2", "limit": 6, "accept-language": "vi", "q": q})
    out = []
    for r in _http_json(u, 8):
        out.append({"name": r.get("display_name", "").split(",")[0], "label": r.get("display_name", ""), "lat": float(r["lat"]), "lon": float(r["lon"])})
    return out

def _geo_openmeteo(q):
    u = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({"name": q, "count": 6, "language": "vi", "format": "json"})
    out = []
    for r in (_http_json(u, 8).get("results") or []):
        lab = ", ".join(x for x in (r.get("name"), r.get("admin2"), r.get("admin1"), r.get("country")) if x)
        out.append({"name": r.get("name"), "label": lab, "lat": r["latitude"], "lon": r["longitude"]})
    return out

def _geo_photon(q):
    u = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": q, "limit": 6})
    out = []
    for f in _http_json(u, 8).get("features", []):
        pr, (lon, lat) = f.get("properties", {}), f["geometry"]["coordinates"]
        lab = ", ".join(x for x in (pr.get("name"), pr.get("county"), pr.get("state"), pr.get("country")) if x)
        out.append({"name": pr.get("name") or lab, "label": lab, "lat": lat, "lon": lon})
    return out

@app.route("/api/geocode")
def api_geocode():
    """Tìm địa danh qua MÁY CHỦ (tránh lỗi chặn trình duyệt/CORS). Thử lần lượt Nominatim → Open-Meteo → Photon; hỗ trợ gõ thẳng 'vĩ độ, kinh độ'."""
    q = (request.args.get("q") or "").strip()[:120]
    if not q:
        return _err("Hãy gõ tên nơi cần tìm.")
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)\s*$", q)
    if m and abs(float(m.group(1))) <= 90 and abs(float(m.group(2))) <= 180:
        return jsonify({"ok": True, "results": [{"name": "Toạ độ", "label": "%s, %s" % (m.group(1), m.group(2)), "lat": float(m.group(1)), "lon": float(m.group(2))}], "via": "coords"})
    tried = []
    import concurrent.futures as cf
    jobs = [("nominatim", _geo_nominatim, q), ("open-meteo", _geo_openmeteo, q), ("photon", _geo_photon, q)]
    if _ascii(q) != q:
        jobs += [("open-meteo", _geo_openmeteo, _ascii(q)), ("photon", _geo_photon, _ascii(q))]
    ex = cf.ThreadPoolExecutor(max_workers=len(jobs))
    try:
        futs = {ex.submit(fn, qq): via for via, fn, qq in jobs}      # gọi SONG SONG, không chờ lần lượt
        pending, got, t_first, deadline = set(futs), {}, None, time.time() + 10
        while pending and time.time() < deadline:
            done, pending = cf.wait(pending, timeout=max(0.1, deadline - time.time()), return_when=cf.FIRST_COMPLETED)
            for f in done:
                via = futs[f]
                try:
                    r = f.result()
                except Exception as e:                                # noqa
                    tried.append("%s: %s" % (via, e))
                    continue
                if r:
                    got.setdefault(via, r)
                else:
                    tried.append("%s: không có kết quả" % via)
            if "nominatim" in got:
                break
            if got:
                t_first = t_first or time.time()
                if time.time() - t_first > 2.5:                       # Nominatim chi tiết xã/phường nhất; chờ thêm tối đa 2,5 s
                    break
        if got:
            via = "nominatim" if "nominatim" in got else next(iter(got))
            return jsonify({"ok": True, "results": got[via], "via": via})
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return _err("Không tìm thấy hoặc không kết nối được dịch vụ tìm địa điểm. Bạn có thể bấm thẳng lên bản đồ, hoặc gõ toạ độ dạng 18.67, 105.69. (%s)" % "; ".join(tried)[:200], 502)

@app.route("/api/climate", methods=["POST"])
def api_climate():
    p = request.get_json(silent=True) or {}
    lat, lon = num(p.get("lat")), num(p.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return _err("Toạ độ không hợp lệ.")
    try:
        clim, note = get_clim(lat, lon)
    except PowerError as e:
        return _err(str(e), 502)
    s = clim.summary()
    s["note"] = note
    return jsonify({"ok": True, "climate": s})

@app.route("/api/layers/parse", methods=["POST"])
def api_layer_parse():
    kind = (request.form.get("kind") or "").lower()
    f = request.files.get("file")
    if kind not in LAYER_KINDS or not f:
        return _err("Thiếu file hoặc loại lớp không hợp lệ.")
    try:
        text = f.read().decode("utf-8-sig", "replace")
        return jsonify({"ok": True, "layer": parse_layer_csv(text, kind)})
    except ValueError as e:
        return _err(str(e))

POWER_IMG_SVC = {"MET": "https://gis.earthdata.nasa.gov/portal/rest/services/POWER/POWER_MONTHLY_METEOROLOGY_LST/ImageServer",
                 "RAD": "https://gis.earthdata.nasa.gov/portal/rest/services/POWER/POWER_MONTHLY_RADIATION_LST/ImageServer"}

@app.route("/api/power_md")
def api_power_md():
    """Danh sách biến + mốc thời gian của dịch vụ ảnh NASA POWER (lấy qua máy chủ để tránh CORS; lưu đệm 1 ngày)."""
    svc = request.args.get("svc", "MET")
    if svc not in POWER_IMG_SVC:
        return jsonify({"error": "svc không hợp lệ"}), 400
    try:
        out = _cache_rw("power_md_%s.json" % svc, lambda: _http_json(POWER_IMG_SVC[svc] + "/multiDimensionalInfo?f=json", 20), 1)
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": "Không lấy được thông tin dịch vụ NASA POWER: %s" % e}), 502

@app.route("/api/scenarios", methods=["POST"])
def api_scenarios():
    try:
        return jsonify(run_scenarios(request.get_json(force=True) or {}))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/monitor", methods=["POST"])
def api_monitor():
    """Giám sát A1, A2, A3, B1 trên thửa + cảnh báo theo cấu hình người dùng (GiamSat.md)."""
    try:
        return jsonify(run_monitor(request.get_json(silent=True) or {}))
    except ValueError as e:
        return _err(str(e))
    except PowerError as e:
        return _err(str(e), 502)


@app.route("/api/evaluate", methods=["POST"])
def api_evaluate():
    """Bài toán 1: điểm phù hợp của từng cây cho VỤ TỚI trên thửa này (+ kịch bản thời tiết nếu có Δ)."""
    try:
        return jsonify(run_evaluate(request.get_json(silent=True) or {}))
    except ValueError as e:
        return _err(str(e))
    except PowerError as e:
        return _err(str(e), 502)

@app.route("/api/farms", methods=["GET", "POST"])
def api_farms():
    with _LOCK:
        d = _farms_load()
        if request.method == "GET":
            return jsonify({"ok": True, "farms": [{"id": k, "name": v.get("farm", {}).get("name") or "Trang trại", "area_ha": v.get("farm", {}).get("area_ha"),
                                                    "lat": v.get("farm", {}).get("lat"), "lon": v.get("farm", {}).get("lon"), "saved": v.get("saved")} for k, v in d.items()]})
        p = request.get_json(silent=True) or {}
        if len(json.dumps(p)) > 3_000_000:
            return _err("Dữ liệu quá lớn.")
        fid = p.get("id") or uuid.uuid4().hex[:10]
        p["saved"] = dt.datetime.now().isoformat(timespec="seconds")
        d[fid] = {k: p.get(k) for k in ("farm", "cfg", "layers", "saved")}
        _farms_save(d)
        return jsonify({"ok": True, "id": fid})

@app.route("/api/farms/<fid>", methods=["GET", "DELETE"])
def api_farm_one(fid):
    with _LOCK:
        d = _farms_load()
        if fid not in d:
            return _err("Không tìm thấy trang trại.", 404)
        if request.method == "DELETE":
            d.pop(fid); _farms_save(d)
            return jsonify({"ok": True})
        return jsonify({"ok": True, "state": d[fid], "id": fid})

@app.route("/api/ai/explain", methods=["POST"])
def api_ai_explain():
    p = request.get_json(silent=True) or {}
    a = p.get("analysis")
    if not a:
        return _err("Chưa có kết quả phân tích.")
    local = local_explain(a, p.get("crop_id"))
    facts = compact_facts(a, p.get("crop_id"))
    q = ("DỮ LIỆU (JSON):\n%s\n\nHãy viết cho nông dân (tối đa ~200 từ, câu ngắn, không thuật ngữ): (1) vụ tới nên cân nhắc cây nào và VÌ SAO (dựa trên điểm từng tiêu chí), "
         "(2) cây nào bị loại hoặc điểm thấp và vì sao, (3) 2–3 điều cần tự kiểm tra với địa phương (kể cả tiêu chí còn thiếu dữ liệu). Dùng đúng số trong DỮ LIỆU." % json.dumps(facts, ensure_ascii=False))
    try:
        txt, mdl = gemini_text(AI_SYSTEM, [{"role": "user", "parts": [{"text": q}]}])
    except RuntimeError as e:
        return jsonify({"ok": True, "text": local, "model": "local", "fallback": True, "reason": str(e), "unverified_numbers": []})
    return jsonify({"ok": True, "text": txt, "model": mdl, "unverified_numbers": unverified_numbers(txt, facts)})

@app.route("/api/ai/local", methods=["POST"])
def api_ai_local():
    p = request.get_json(silent=True) or {}
    return jsonify({"ok": True, "text": local_explain(p.get("analysis") or {}, p.get("crop_id"))})

@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    p = request.get_json(silent=True) or {}
    msg = (p.get("message") or "").strip()[:1500]
    a = p.get("analysis")
    if not msg:
        return _err("Câu hỏi trống.")
    facts = compact_facts(a) if a else {}
    sys_ = AI_SYSTEM + "\nDỮ LIỆU phân tích hiện tại (JSON):\n" + json.dumps(facts, ensure_ascii=False)[:14000] + "\nNếu câu hỏi ngoài phạm vi dữ liệu, nói rõ là không có trong phân tích."
    contents = []
    for h in (p.get("history") or [])[-8:]:
        contents.append({"role": "user" if h.get("role") == "user" else "model", "parts": [{"text": str(h.get("text", ""))[:1500]}]})
    contents.append({"role": "user", "parts": [{"text": msg}]})
    try:
        txt, mdl = gemini_text(sys_, contents, max_tokens=1200)
    except RuntimeError as e:
        return _err("Trợ lý AI đang chậm hoặc chưa kết nối được. Bạn vẫn có thể đọc phần giải thích có sẵn. (%s)" % e, 503)
    return jsonify({"ok": True, "text": txt, "model": mdl, "unverified_numbers": unverified_numbers(txt, facts)})

@app.route("/api/auto/start", methods=["POST"])
def api_auto_start():
    """Bắt đầu tự lấy một lớp dữ liệu theo vị trí: kind ∈ ndvi | lst | gpm | soil | ssurgo | slope. Trả job để hỏi lại."""
    p = request.get_json(silent=True) or {}
    kind, lat, lon = p.get("kind"), num(p.get("lat")), num(p.get("lon"))
    if kind not in AUTO_FUNCS:
        return _err("Loại dữ liệu không hợp lệ.")
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return _err("Toạ độ không hợp lệ.")
    return api_auto_job(auto_job_start(kind, lat, lon))

@app.route("/api/auto/job/<jid>")
def api_auto_job(jid):
    with _LOCK:
        j = dict(_JOBS.get(jid) or {})
    if not j:
        return _err("Không tìm thấy yêu cầu (máy chủ có thể vừa khởi động lại).", 404)
    out = {"ok": True, "job": jid, "status": j["status"], "kind": j.get("kind")}
    if j["status"] == "done":
        out["result"] = j["result"]
    elif j["status"] == "error":
        out["error"] = j["error"]
    else:
        out["elapsed_s"] = round(time.time() - j["t"])
    return jsonify(out)

# ---- Danh mục nguồn dữ liệu, tài nguyên & công cụ AI (yêu cầu của Project Submission Guide – NASA Space Apps)
SOURCE_USE = {  # nguồn → tiêu chí / chức năng dùng nó
    "power": ["A1", "A2", "A3", "B1", "K1 sương giá", "Bước 3 – Khí hậu", "Giám sát – chuỗi ngày & cảnh báo"], "power_img": ["Giám sát – bản đồ A1, A2, A3, B1"], "gpm": ["A2", "B1"], "smap": ["B1"], "ssurgo": ["C1", "C2", "C3", "C4", "C5", "C6", "B1", "D1"],
    "soil": ["C2", "C3", "C5"], "slope": ["D1"], "ndvi": ["Bước 3 – tham khảo"], "lst": ["Bước 3 – tìm điểm nóng"]}
POWER_IMG_SOURCE = {"name": "NASA POWER Image Services – Monthly Meteorology & Radiation (POWER_MONTHLY_*_LST)", "nasa": True, "res": "~0,5°×0,625°, theo tháng",
                    "via": "ArcGIS ImageServer gis.earthdata.nasa.gov/portal/rest/services/POWER (không cần khóa) — exportImage theo biến (T2M, PRECTOTCORR_SUM, ALLSKY_KT, GWETTOP) & tháng",
                    "cite": "The NASA Prediction Of Worldwide Energy Resources (POWER) Project at NASA Langley Research Center (LaRC). Image services via NASA Earthdata GIS."}
SMAP_SOURCE = {"name": "SMAP L4 Global 9 km Surface and Root Zone Soil Moisture (SPL4SMGP)", "nasa": True, "res": "9 km, 3 giờ", "via": "Người dùng tải CSV từ NASA Earthdata / AppEEARS rồi nạp vào công cụ",
               "cite": "Reichle, R., et al. SMAP L4 Global 3-hourly 9 km EASE-Grid Surface and Root Zone Soil Moisture Geophysical Data (SPL4SMGP). NASA NSIDC DAAC. https://nsidc.org/data/spl4smgp — ghi số phiên bản và DOI theo trang dữ liệu lúc tải."}
OTHER_RESOURCES = [
    {"group": "Bản đồ nền & tìm địa điểm", "items": [
        ("Esri World Imagery", "Ảnh vệ tinh nền bản đồ (bước 1)", "https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9", "Esri, Maxar, Earthstar Geographics"),
        ("OpenStreetMap", "Bản đồ nền dự phòng", "https://www.openstreetmap.org/copyright", "© OpenStreetMap contributors, ODbL"),
        ("Esri World Light Gray · World Hillshade · World Boundaries and Places", "Bản đồ nền trang chủ (giám sát): nền xám, bóng địa hình, ranh giới & địa danh", "https://www.arcgis.com/home/item.html?id=1b243539f4514b6ba35e7d995890db1d", "Esri, USGS, HERE, Garmin, FAO, NOAA"),
        ("Nominatim / Open-Meteo Geocoding / Photon (Komoot)", "Tìm tên địa điểm → toạ độ", "https://nominatim.org/", "Dữ liệu OSM; Open-Meteo CC BY 4.0"),
        ("OpenTopoData", "Cổng truy cập SRTM 30 m để tính độ dốc", "https://www.opentopodata.org/", "Mã nguồn MIT; dữ liệu SRTM của NASA")]},
    {"group": "Thư viện & mã nguồn mở", "items": [
        ("Python · Flask · python-dotenv · truststore", "Máy chủ, API, cấu hình", "https://flask.palletsprojects.com/", "BSD-3 / MIT"),
        ("Leaflet 1.9.4", "Bản đồ tương tác, vẽ ranh giới thửa", "https://leafletjs.com/", "BSD-2"),
        ("Chart.js 4.4.1", "Biểu đồ khí hậu", "https://www.chartjs.org/", "MIT"),
        ("Google Fonts: Be Vietnam Pro, Newsreader", "Phông chữ giao diện", "https://fonts.google.com/", "SIL Open Font License")]},
    {"group": "Phương pháp & tài liệu khoa học", "items": [
        ("FAO-56 (Allen et al., 1998)", "Bức xạ đỉnh khí quyển Ra (tính Kt dự phòng), độ sâu rễ Zr", "https://www.fao.org/4/x0490e/x0490e00.htm", "FAO"),
        ("FAO-33 / FAO-66", "Hàm phản ứng năng suất – nước, hệ số Ky (B1)", "https://fao.org/4/i2800e/i2800e02.pdf", "FAO"),
        ("Rawls, Brakensiek & Saxton (1982)", "θ héo / đồng ruộng / bão hòa theo cơ giới khi thiếu SSURGO", "https://doi.org/10.13031/2013.33720", "Trans. ASAE 25(5)"),
        ("Theil–Sen & Mann–Kendall", "Xu hướng khí hậu nhiều năm (bước 3)", "https://en.wikipedia.org/wiki/Theil%E2%80%93Sen_estimator", "Phương pháp thống kê")]},
]
AI_RUNTIME = {"what": "Không dùng AI khi chạy: giao diện phiên bản này không có trợ lý AI. Mọi điểm số, xếp hạng, cảnh báo và câu giải thích đều do Python tính theo quy tắc.",
              "how": ["Điểm phù hợp, kịch bản thời tiết và cảnh báo được tính bằng công thức trong BaiToan1.md và GiamSat.md.",
                      "Câu chữ “Vì sao & lưu ý” và báo cáo in được ghép từ số liệu đã tính, không qua mô hình ngôn ngữ.",
                      "Mã nguồn vẫn giữ các endpoint /api/ai/* (tắt mặc định, cần khóa API) cho phiên bản sau; nếu bật lại, phải khai báo lại ở đây.",
                      "Không có ảnh, video hay dữ liệu nào do AI tạo trong giao diện."],
              "providers_all": {"gemini": "Google Gemini", "groq": "Groq (Llama 3.3 70B)", "openai": "OpenAI", "anthropic": "Anthropic Claude", "openrouter": "OpenRouter", "deepseek": "DeepSeek"}}
AI_DEV_DEFAULT = [
    {"tool": "Claude (Anthropic)", "where": "Mã nguồn farm_adapt (Python + HTML/JS), bộ máy đánh giá SMCA, giao diện, minh hoạ vector SVG viết bằng mã",
     "how": "Sinh và tái cấu trúc mã theo đặc tả của nhóm (BaiToan1.md, CRD.md); nhóm rà soát, chạy thử và đối chiếu công thức với ví dụ trong tài liệu."},
]
AI_TOOLS_PATH = os.path.join(DATA_DIR, "ai_tools.json")


def ai_dev_tools():
    try:
        with open(AI_TOOLS_PATH, "r", encoding="utf-8") as f:
            v = json.load(f)
            if isinstance(v, list):
                return v, True
    except Exception:
        pass
    return AI_DEV_DEFAULT, False


@app.route("/api/sources")
def api_sources():
    """Danh mục nguồn dữ liệu, tài nguyên và công cụ AI (tab “Nguồn dữ liệu & công cụ AI” — yêu cầu bắt buộc của cuộc thi)."""
    power = {"name": "NASA POWER (MERRA-2, CERES SYN1deg, GPM IMERG)", "nasa": True, "res": "0,5°×0,625° khí tượng; 1°×1° bức xạ; chuỗi ngày", "via": "POWER API (không cần khóa)",
             "vars": "T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, GWETROOT, GWETTOP, ALLSKY_SFC_SW_DWN, ALLSKY_KT, RH2M",
             "cite": "These data were obtained from the NASA Langley Research Center POWER Project funded through the NASA Earth Science Directorate Applied Science Program."}
    src = dict({"power": power, "power_img": POWER_IMG_SOURCE, "smap": SMAP_SOURCE}, **AUTO_SOURCES)
    for k, v in src.items():
        v = dict(v)
        v["used_for"] = SOURCE_USE.get(k, [])
        v["auto"] = k not in ("smap",)
        src[k] = v
    dev, custom = ai_dev_tools()
    return jsonify({"ok": True, "version": VERSION, "earthdata_token": bool(EARTHDATA_TOKEN), "sources": src, "crd_sources": CRD_SOURCES,
                    "other": [{"group": g["group"], "items": [dict(zip(("name", "use", "url", "license"), it)) for it in g["items"]]} for g in OTHER_RESOURCES],
                    "hero_image": {"found": bool(_hero_path()), "name": os.path.basename(_hero_path() or "")},
                    "ai_runtime": dict(AI_RUNTIME, active=[]), "ai_dev": dev, "ai_dev_custom": custom, "ai_dev_path": AI_TOOLS_PATH})


@app.route("/api/ai_tools", methods=["POST"])
def api_ai_tools():
    """Nhóm tự khai báo công cụ AI đã dùng khi phát triển (lưu data/ai_tools.json)."""
    lst = (request.get_json(silent=True) or {}).get("items")
    if not isinstance(lst, list) or len(lst) > 40:
        return _err("Danh sách không hợp lệ.")
    clean = [{k: str(x.get(k, ""))[:500] for k in ("tool", "where", "how")} for x in lst if isinstance(x, dict) and str(x.get("tool", "")).strip()]
    with open(AI_TOOLS_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
    return jsonify({"ok": True, "items": clean})

@app.route("/api/report", methods=["POST"])
def api_report():
    return Response(render_report(request.get_json(silent=True) or {}), mimetype="text/html")

HERO_WIN = r"E:\1. Do_an_2\hahoi_tool\static\—Pngtree—mountain rice terraces sustainable farming_16261548.jpg"

def _hero_path():
    """Ảnh trang mở đầu: FARM_HERO_IMAGE → static/hero.* cạnh file → đường dẫn ổ E: của bạn → ảnh bất kỳ trong static/."""
    import glob
    sd = os.path.join(_BASE_DIR, "static")
    cands = [os.environ.get("FARM_HERO_IMAGE", "")] + [os.path.join(sd, "hero" + e) for e in (".jpg", ".jpeg", ".png", ".webp")] + [HERO_WIN]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    for e in ("jpg", "jpeg", "png", "webp"):
        g = sorted(glob.glob(os.path.join(sd, "*." + e)))
        if g:
            return g[0]
    return None

@app.route("/hero.jpg")
def hero_img():
    p = _hero_path()
    if not p:
        return Response("", status=404)
    ext = os.path.splitext(p)[1].lower().lstrip(".")
    mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    with open(p, "rb") as f:
        return Response(f.read(), mimetype=mt, headers={"Cache-Control": "public, max-age=3600"})

@app.route("/logo.png")
def logo_png():
    import base64
    return Response(base64.b64decode(LOGO_B64), mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})

@app.route("/")
def index():
    return Response(INDEX_HTML.replace("__APP_NAME__", APP_NAME).replace("__APP_FULL__", APP_FULL).replace("__SLOGAN__", APP_SLOGAN).replace("__VERSION__", VERSION)
                    .replace("__NCROPS__", str(len(CROPS))).replace("__NYEARS__", str(POWER_YEARS)).replace("__NCRIT__", str(len(CRIT_ORDER)))
                    .replace("__I18N__", json.dumps(I18N_EN, ensure_ascii=False).replace("</", "<\\/")),
                    mimetype="text/html", headers={"Cache-Control": "no-store"})

if __name__ == "__main__":
    print("%s v%s — http://localhost:%s   (AI: %s)" % (APP_NAME, VERSION, os.environ.get("PORT", 5000), ", ".join(k for k, _ in ai_providers()) or "tắt — chưa có khóa AI; vẫn có giải thích tại chỗ"))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
