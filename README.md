# NLP Feedback System

> Hệ thống phân tích phản hồi tiếng Việt trong thương mại điện tử bằng Aspect-Based Sentiment Analysis (ABSA).

## Giới thiệu

NLP Feedback System là ứng dụng web cho phép khách hàng xem sản phẩm, gửi đánh giá và nhận phản hồi tự động. PhoBERT V5 phân tích từng khía cạnh được nhắc đến trong feedback; kết quả được lưu lại để người bán theo dõi trên dashboard mà không phải chạy lại mô hình.

**Đề tài:** Tìm hiểu Rasa Chatbot và ứng dụng trong việc xây dựng mô-đun phân tích feedback người dùng<br>
**Học phần:** Xử lý ngôn ngữ tự nhiên<br>
**Năm:** 2026

| Thành viên | MSSV |
|---|---:|
| Trần Quang Thái | 24022451 |
| Nguyễn Văn Trung | 24022475 |
| Đàm Quang Tiến | 24022463 |
| Vũ Hải Anh | 24022260 |

## Tính năng chính

- Catalog Lazada 3.000 sản phẩm: tìm kiếm, lọc giá/rating, phân trang và trộn danh mục khi khám phá.
- Khách hàng có thể đăng ký, đăng nhập, đánh giá sao và gửi feedback tại trang chi tiết sản phẩm.
- PhoBERT V5 nhận diện nhiều aspect trong cùng feedback và gán sentiment riêng cho từng aspect.
- Phản hồi tự động bằng tiếng Việt từ kết quả ABSA và lớp evidence/response enrichment.
- Seller Center: thống kê aspect × sentiment, sản phẩm cần chú ý, danh sách feedback, phân tích sản phẩm và đánh giá mô hình.
- Trang đánh giá mô hình đọc metric và biểu đồ đã đóng gói cùng artifact V5.
- Rasa là kênh hội thoại tùy chọn; luồng feedback mặc định gọi PhoBERT trực tiếp qua FastAPI.

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Backend | FastAPI, Uvicorn |
| Giao diện | Jinja2, CSS/JavaScript tĩnh |
| Database | SQLite, SQLAlchemy |
| ABSA runtime | `vinai/phobert-base-v2` (PhoBERT V5) |
| Tiền xử lý tiếng Việt | VnCoreNLP |
| Chatbot tùy chọn | Rasa |
| Dữ liệu catalog | Lazada metadata đã materialize |

## Cài đặt trên máy mới

### 1. Điều kiện cần

- Windows 10/11, PowerShell, Git và Python 3.11–3.13.
- Java JDK 17+.
- VnCoreNLP đã giải nén; thư mục phải chứa `VnCoreNLP-1.2.jar` và `models/wordsegmenter/`.

Launcher sử dụng mặc định:

```text
JAVA_HOME=C:\Program Files\Java\jdk-24
VNCORENLP_DIR=C:\vncorenlp
```

Nếu Java hoặc VnCoreNLP nằm ở vị trí khác, sửa hai giá trị này trong `scripts\windows\START_LOCAL_V5.bat`, hoặc đặt lại biến môi trường khi chạy thủ công.

### 2. Clone source

```powershell
git clone https://github.com/congacdum/NLP-Feedback-System.git
cd NLP-Feedback-System
```

### 3. Tải artifact PhoBERT V5

Artifact không được đưa trực tiếp vào Git do kích thước lớn. Tải `phobert-absa-v5-deploy.zip` từ [Release model-v5.0.0](https://github.com/congacdum/NLP-Feedback-System/releases/tag/model-v5.0.0), sau đó kiểm hash:

```powershell
Get-FileHash .\phobert-absa-v5-deploy.zip -Algorithm SHA256
```

SHA-256 phải khớp:

```text
885313FEF8E70C900CAEE5A916731E06C89F07BA6D8064835519A4BF316EA4EA
```

Giải nén **nội dung** ZIP vào `model_artifacts\` ở root project:

```powershell
Expand-Archive .\phobert-absa-v5-deploy.zip -DestinationPath .\model_artifacts -Force
```

Sau khi giải nén, thư mục phải có:

```text
model_artifacts/
├── model.pt
├── thresholds.json
├── training_config.json
├── training_manifest.json
├── tokenizer/
├── encoder_config/
├── evaluation/
│   ├── metrics.json
│   └── plots/
├── evaluation_balanced_v2/
└── evaluation_dev/
```

Các `evaluation*/plots/` là nguồn biểu đồ cho Seller Center → Đánh giá mô hình.

### 4. Cài Python dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-transformer-runtime.txt
```

Không cần cài `requirements-train.txt` nếu chỉ chạy demo/inference.

### 5. Khởi tạo catalog và database

`data\app.db` là database local nên không được commit. Trên máy mới, nạp catalog trước khi chạy app:

```powershell
.\.venv\Scripts\python.exe scripts\import_products_to_db.py data\lazada_products.json
```

Lệnh tạo `data\app.db`, tài khoản demo và nạp catalog. Không dùng `--reset-catalog-and-feedback` trừ khi chủ động muốn xóa toàn bộ feedback hiện có.

### 6. Chạy ứng dụng

Cách nhanh trên Windows:

```text
scripts\windows\START_LOCAL_V5.bat
```

Truy cập [http://127.0.0.1:8000](http://127.0.0.1:8000) sau khi server sẵn sàng.

```text
Khách hàng: customer@example.com / customer123
Người bán: seller@example.com / seller123
```

### Chạy thủ công bằng PowerShell

```powershell
$env:JAVA_HOME = 'C:\Program Files\Java\jdk-24'
$env:NLP_BACKEND = 'transformer'
$env:TRANSFORMER_ARTIFACT = "$PWD\model_artifacts"
$env:VNCORENLP_DIR = 'C:\vncorenlp'
$env:ALLOW_EXPERIMENTAL_TRANSFORMER = 'true'
$env:TRANSFORMER_DEVICE = 'cpu'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_OFFLINE = '1'

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`NLP_BACKEND=transformer` không fallback sang rule/demo analyzer. Nếu artifact, Java hoặc VnCoreNLP chưa đúng, app sẽ báo lỗi khi khởi động.

## Cách sử dụng

1. Chọn sản phẩm trên catalog.
2. Đăng nhập khách hàng, chọn rating và gửi feedback.
3. Hệ thống lưu feedback gốc, chạy PhoBERT V5, rồi trả phản hồi tự động.
4. Đăng nhập Seller Center để xem thống kê đã lưu.
5. Vào **Đánh giá mô hình** để xem metric và plot đi kèm release artifact.

API phân tích trực tiếp:

```text
POST /api/nlp/analyze
```

Endpoint này trả kết quả phân tích, không tạo feedback trong database như luồng gửi đánh giá trên giao diện.

## Taxonomy ABSA

| Aspect | Ý nghĩa |
|---|---|
| `product_quality` | Chất lượng, công năng, độ bền, vật liệu, lỗi sản phẩm |
| `delivery` | Tốc độ, thời gian và quá trình giao hàng |
| `customer_service` | Tư vấn, hỗ trợ, đổi trả, bảo hành, thái độ shop |
| `packaging` | Hộp, bao bì, niêm phong, chống sốc |
| `price` | Mức giá, đắt/rẻ, khuyến mãi |
| `other` | Nội dung có ý nghĩa nhưng không thuộc năm nhóm trên |

Sentiment gồm `positive`, `neutral`, `negative`, `mixed`. `no_aspect` là trạng thái khi không có aspect nào vượt threshold, không phải aspect thứ bảy.

## Cấu trúc repository

```text
app/                    FastAPI routes, services, templates, static files và persistence
data/                   Catalog Lazada materialize và SQLite local (app.db tạo trên máy)
docs/                   Tài liệu kỹ thuật
├── reports/            Báo cáo PDF
└── presentations/      Slide thuyết trình
model_artifacts/        Artifact V5 tải từ GitHub Release (được gitignore)
nlp/                    Schema, preprocessing, model, training, evaluation và inference
rasa_bot/               Rasa profile và custom action tùy chọn
scripts/                Import dữ liệu, audit, diagnostic và tiện ích
└── windows/            Launcher Windows: START, START_LOCAL_V5, START_WITH_RASA, STOP
tests/                  Automated tests
```

## Script thường dùng

| Script | Mục đích |
|---|---|
| `scripts\windows\START_LOCAL_V5.bat` | Chạy FastAPI với PhoBERT V5 local |
| `scripts\windows\START.bat` | Chạy cấu hình Docker Compose mặc định |
| `scripts\windows\START_WITH_RASA.bat` | Train/chạy profile Rasa tùy chọn qua Docker |
| `scripts\windows\STOP.bat` | Dừng các service Docker liên quan |
| `scripts\import_products_to_db.py` | Nạp catalog JSON vào SQLite |
| `scripts\final_project_audit.py` | Kiểm tra điều kiện bàn giao/audit |

## Kiểm thử và huấn luyện lại

Cài thêm dependencies phát triển để chạy test:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Pipeline huấn luyện/evaluation nằm trong `nlp/training/` và `scripts/`. Đọc tài liệu model và protocol trước khi train lại để giữ đúng phân tách Train/Dev/Test.

## Tài liệu

- [Kiến trúc hệ thống](docs/ARCHITECTURE.md)
- [Model card](docs/MODEL_CARD.md)
- [Nguồn dữ liệu và mapping](docs/DATA_SOURCES_AND_MAPPING.md)
- [Hướng dẫn gán nhãn](docs/ANNOTATION_GUIDELINE.md)
- [Báo cáo dự án](docs/reports/report.pdf)
- [Slide thuyết trình](docs/presentations/slide-thuyet-trinh.pdf)

## Lưu ý

- PhoBERT V5 trong release là artifact experimental, chưa được tuyên bố là `scientific-final` vì chưa có bộ human-verified gold phù hợp cho đánh giá cuối.
- Giá product trong catalog là estimate theo tên sản phẩm khi metadata nguồn không cung cấp giá gốc.
- Một số metadata nguồn không có ảnh sản phẩm; app vẫn giữ chúng để tìm kiếm nhưng ưu tiên card có ảnh trong danh sách mặc định.
