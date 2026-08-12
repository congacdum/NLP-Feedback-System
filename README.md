# Hệ thống phân tích phản hồi người dùng trong thương mại điện tử

> **Đề tài:** Tìm hiểu Rasa Chatbot và ứng dụng trong việc xây dựng mô-đun phân tích feedback người dùng  
> **Học phần:** Xử lý ngôn ngữ tự nhiên  
> **Năm:** 2026

## Thành viên nhóm

| Họ và tên | Mã sinh viên |
|---|---:|
| Trần Quang Thái | 24022451 |
| Nguyễn Văn Trung | 24022475 |
| Đàm Quang Tiến | 24022463 |
| Vũ Hải Anh | 24022260 |

---

## 1. Giới thiệu

Dự án xây dựng hệ thống **phân tích cảm xúc theo khía cạnh (Aspect-Based Sentiment Analysis - ABSA)** cho phản hồi thương mại điện tử tiếng Việt.

Khác với phân loại cảm xúc toàn câu, hệ thống xác định **từng khía cạnh được đề cập** và **cảm xúc tương ứng của từng khía cạnh**. Ví dụ:

```text
Phản hồi:
"Sản phẩm đẹp, giá ổn nhưng giao hàng hơi lâu."

Kết quả:
product_quality -> positive
price           -> positive
delivery        -> negative
```

Runtime hiện tại sử dụng **PhoBERT V5** làm nguồn quyết định chính cho aspect và sentiment. **Rasa** được giữ như một thành phần hội thoại tùy chọn, không thay thế bộ phân tích ABSA của PhoBERT.

---

## 2. Chức năng chính

### Khách hàng

- Xem danh sách và chi tiết sản phẩm.
- Tìm kiếm, lọc, sắp xếp và phân trang.
- Xem phản hồi đã có của sản phẩm.
- Chọn điểm đánh giá và gửi feedback tiếng Việt.
- Nhận phản hồi tự động sau khi hệ thống phân tích nội dung.

### Mô-đun NLP

- Phát hiện nhiều aspect trong cùng một feedback.
- Phân loại sentiment riêng cho từng aspect.
- Hỗ trợ `positive`, `neutral`, `negative`, `mixed`.
- Hỗ trợ `no_aspect` khi nội dung không đủ bằng chứng.
- Xử lý feedback dài bằng `sliding windows`.
- Dùng threshold riêng cho từng aspect.

### Người bán

- Thống kê phản hồi theo aspect và sentiment.
- Sử dụng kết quả `FeedbackAnalysis` đã lưu, không chạy lại PhoBERT khi mở dashboard.
- Khai thác evidence bổ sung để giải thích nguyên nhân phản hồi.

---

## 3. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Backend | FastAPI |
| Giao diện | Jinja2 |
| ORM | SQLAlchemy |
| Cơ sở dữ liệu | SQLite |
| Mô hình NLP | `vinai/phobert-base-v2` |
| Tiền xử lý tiếng Việt | VnCoreNLP |
| Chatbot | Rasa, sử dụng tùy chọn |
| Container hóa | Docker / Docker Compose |

Ứng dụng, mô hình suy luận và pipeline huấn luyện chính **không yêu cầu LLM trả phí hoặc API bên ngoài**.

---

## 4. Kiến trúc và luồng xử lý

```text
Khách hàng / Người bán
         |
         v
      FastAPI
         |
         v
  Feedback Service
     /       \
    v         v
PhoBERT V5   SQLite
    |
    v
Schema Validation
    |
    v
Evidence + Response Builder
    |
    +----> Phản hồi cho khách hàng
    |
    +----> FeedbackAnalysis ----> Seller Analytics
```

Khi người dùng gửi feedback chính thức:

```text
1. Kiểm tra product_id, rating và nội dung
2. Lưu feedback gốc với status=pending
3. Gọi PhoBERT V5 để phân tích ABSA
4. Kiểm tra schema kết quả
5. Tạo evidence và câu phản hồi tiếng Việt
6. Lưu FeedbackAnalysis theo từng aspect
7. Cập nhật status=ok hoặc no_aspect
8. Trả kết quả cho khách hàng
```

Feedback gốc được lưu **trước khi suy luận**. Nếu NLP hoặc tích hợp gặp lỗi, nội dung vẫn được bảo toàn và trạng thái chuyển thành `failed`.

Các trạng thái chính:

- `pending`: đã lưu feedback, đang chờ xử lý NLP.
- `ok`: phân tích thành công và có aspect hợp lệ.
- `no_aspect`: không có aspect nào vượt threshold.
- `failed`: xảy ra lỗi trong quá trình phân tích hoặc tích hợp.

---

## 5. Taxonomy của bài toán

### Sáu aspect

| Aspect | Ý nghĩa |
|---|---|
| `product_quality` | Chất lượng, công năng, độ bền, vật liệu, kích thước hoặc lỗi sản phẩm |
| `delivery` | Tốc độ, thời gian, lịch và quá trình giao hàng |
| `customer_service` | Tư vấn, hỗ trợ, đổi trả, bảo hành và thái độ bên bán |
| `packaging` | Hộp, bao bì, niêm phong, chống sốc và khả năng bảo vệ sản phẩm |
| `price` | Mức giá, đắt/rẻ, tính hợp lý và ưu đãi trực tiếp |
| `other` | Nội dung đánh giá có ý nghĩa nhưng không thuộc năm nhóm trên |

### Bốn sentiment

- `positive`: tích cực.
- `neutral`: trung tính.
- `negative`: tiêu cực.
- `mixed`: cùng một aspect có cả tín hiệu tích cực và tiêu cực đáng kể.

### `other` và `no_aspect`

`other` là một **aspect hợp lệ**. `no_aspect` chỉ là **trạng thái xử lý**, không phải aspect thứ bảy.

```text
"Áo đẹp nhưng giao chậm."
-> product_quality=positive, delivery=negative

"Không biết nói gì, cho 5 sao."
-> no_aspect
```

Điểm đánh giá 1-5 sao chỉ được lưu dưới dạng **metadata** và không dùng để ghi đè sentiment do PhoBERT dự đoán.

---

## 6. Mô hình PhoBERT V5

Artifact runtime hiện tại:

```text
model_artifacts/experimental_phobert_absa_v5_hard_cases_final/
```

Backbone:

```text
vinai/phobert-base-v2
```

Mô hình sử dụng một encoder PhoBERT dùng chung và hai head:

```text
PhoBERT encoder
    |
    +--> Aspect head: 6 sigmoid outputs
    |
    +--> Sentiment head: 6 x 4 logits
```

- Aspect detection là bài toán đa nhãn, sử dụng BCE-based loss.
- Sentiment sử dụng Cross-Entropy có mask tại các aspect hợp lệ.
- Mỗi aspect có threshold riêng được chọn trên Dev.
- Không dùng top-1 fallback khi tất cả aspect đều dưới threshold.
- Feedback dài được xử lý bằng các cửa sổ token chồng lấn.

### Tiền xử lý

```text
Feedback gốc
 -> Unicode NFC + làm sạch HTML/khoảng trắng
 -> mask URL / email / số điện thoại
 -> giữ dấu, phủ định, emoji và dấu câu
 -> VnCoreNLP word segmentation
 -> PhoBERT tokenizer
 -> PhoBERT V5
```

Train và inference sử dụng cùng logic phân đoạn từ để hạn chế sai khác phân phối đầu vào.

---

## 7. Dữ liệu và cấu hình huấn luyện

Track V5 sử dụng:

```text
Train: nlp/data/experimental_v2/train.jsonl
Dev:   nlp/data/experimental_v2/dev.jsonl
Test:  nlp/data/experimental/test.jsonl
```

| Tập dữ liệu | Feedback | Annotation | Vai trò |
|---|---:|---:|---|
| Train | 18,038 | 25,191 | Cập nhật trọng số |
| Dev | 2,205 | 2,936 | Chọn checkpoint và threshold |
| Natural Test | 2,337 | 2,919 | Held-out experimental evaluation |
| Balanced V2 | 1,800 | 2,160 | Diagnostic cân bằng |

Natural Test có phân bố aspect:

| Aspect | Support |
|---|---:|
| `product_quality` | 1,672 |
| `delivery` | 544 |
| `price` | 390 |
| `packaging` | 297 |
| `customer_service` | 10 |
| `other` | 6 |

Hai aspect `customer_service` và `other` có support rất thấp trên Natural Test nên các chỉ số riêng của chúng cần được diễn giải thận trọng.

Cấu hình V5:

| Tham số | Giá trị |
|---|---|
| Epoch | 5 |
| Batch size | 8 |
| Max length | 256 |
| Learning rate | `2e-5` |
| Weight decay | `0.01` |
| Warmup ratio | `0.10` |
| Optimizer | AdamW |
| Seed | 42 |
| Gradient clipping | 1.0 |
| Selection metric | Dev strict-union Pair Macro-F1 |

Threshold đóng băng:

| Aspect | Threshold |
|---|---:|
| `product_quality` | 0.36 |
| `delivery` | 0.80 |
| `customer_service` | 0.50 |
| `packaging` | 0.54 |
| `price` | 0.32 |
| `other` | 0.58 |

---

## 8. Kết quả đánh giá

| Protocol | Strict-union Pair Macro-F1 | Pair Micro-F1 | Aspect Macro-F1 | Sentiment Macro-F1 | Exact Match |
|---|---:|---:|---:|---:|---:|
| Dev | 0.8809 | 0.9121 | 0.9779 | 0.8338 | 0.8562 |
| Natural Test | **0.5609** | **0.8843** | **0.9507** | **0.7745** | **0.8228** |
| Balanced V2 | 0.7961 | 0.8305 | 0.9114 | 0.8840 | 0.7761 |

Dev được dùng để lựa chọn checkpoint và threshold nên không được xem là đánh giá độc lập cuối cùng.

Natural Test là tập held-out trong track thực nghiệm hiện tại. Balanced V2 là tập diagnostic cân bằng, được tạo với hỗ trợ của mô hình ngôn ngữ và chưa phải human-gold Test.

### So sánh baseline trên Natural Test

| Mô hình | Pair Macro-F1 | Strict-union Pair Macro-F1 | Pair Micro-F1 | Exact Match |
|---|---:|---:|---:|---:|
| Rule | 0.2001 | 0.1917 | 0.4125 | 0.2383 |
| LinearSVM | 0.4299 | 0.4120 | 0.8137 | 0.7317 |
| TF-IDF LR | 0.5124 | 0.4911 | 0.8012 | 0.7231 |
| **PhoBERT V5** | **0.5853** | **0.5609** | **0.8843** | **0.8228** |

PhoBERT V5 có point estimate cao nhất trong bảng. Tuy nhiên, toàn bộ track hiện tại vẫn được báo cáo ở phạm vi **experimental**, chưa phải `scientific-final`.

---

## 9. Hướng dẫn chạy nhanh

### Yêu cầu

- Python và `requirements-transformer-runtime.txt`.
- Java khả dụng trong môi trường.
- VnCoreNLP có `VnCoreNLP-1.2.jar` và `models/wordsegmenter`.
- Artifact V5 nằm đúng trong `model_artifacts/`.

### Chạy local bằng PowerShell

```powershell
python -m pip install -r requirements-transformer-runtime.txt

$env:NLP_BACKEND = 'transformer'
$env:TRANSFORMER_ARTIFACT = "$PWD\model_artifacts\experimental_phobert_absa_v5_hard_cases_final"
$env:VNCORENLP_DIR = 'C:\vncorenlp'
$env:ALLOW_EXPERIMENTAL_TRANSFORMER = 'true'
$env:TRANSFORMER_DEVICE = 'auto'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_OFFLINE = '1'

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Truy cập:

```text
http://127.0.0.1:8000
```

Tài khoản demo:

```text
Khách hàng: customer@example.com / customer123
Người bán:   seller@example.com / seller123
```

API phân tích trực tiếp:

```text
POST /api/nlp/analyze
```

Endpoint này phân tích trực tiếp và không persist feedback như luồng gửi feedback chính thức.

---

## 10. Vai trò của Rasa và lớp evidence

Source Rasa nằm trong:

```text
rasa_bot/
```

Khi được bật, custom action của Rasa gọi:

```text
POST /api/nlp/analyze
```

Rasa có thể quản lý intent, rule, policy và luồng hội thoại nhưng **không có một bộ phân loại ABSA thứ hai**. Website mặc định không bắt buộc đi qua Rasa.

Sau khi PhoBERT quyết định aspect và sentiment, lớp evidence có thể trích cụm từ giải thích, ví dụ:

```text
delivery -> negative
Evidence: "giao hàng quá chậm"
```

Lớp evidence không được phép tự thêm, xóa hoặc thay đổi aspect/sentiment do PhoBERT quyết định.

---

## 11. Kiểm thử, Docker và cấu trúc project

Audit hiện tại ghi nhận:

```text
38 passed
```

Các test tập trung vào feedback submission, persistence, feedback UI, response builder và một số logic tích hợp.

Project có Dockerfile và Docker Compose, nhưng runtime V5 Transformer **chưa được xác minh là có thể tái tạo đầy đủ trên mọi máy chỉ bằng `docker compose up`**. Việc chạy trong container còn phụ thuộc vào Java, VnCoreNLP, Transformer dependencies, artifact và biến môi trường tương ứng.

Cấu trúc chính:

```text
app/                FastAPI routes, services, templates và persistence
nlp/                schema, preprocessing, model, training, evaluation, inference
data/               SQLite và dữ liệu ứng dụng
model_artifacts/    checkpoint, config, tokenizer, threshold và kết quả đánh giá
docs/               tài liệu kiến trúc, dữ liệu và gán nhãn
scripts/            chuẩn bị dữ liệu, diagnostic, audit và tiện ích
rasa_bot/           tài nguyên Rasa tùy chọn
```

Tài liệu nên đọc khi cần tìm hiểu sâu hơn:

1. `PROJECT_KNOWLEDGE.md`
2. `AI_CHANGELOG.md`
3. `docs/ANNOTATION_GUIDELINE.md`
4. `docs/DATA_SOURCES_AND_MAPPING.md`
5. `docs/ARCHITECTURE.md`
6. `docs/MODEL_CARD.md`

---

## 12. Huấn luyện lại V5

Trước khi huấn luyện cần chạy preflight để kiểm tra dữ liệu, taxonomy, hash và cấu hình.

```bash
python -m nlp.training.preflight_transformer \
  --train nlp/data/experimental_v2/train.jsonl \
  --dev nlp/data/experimental_v2/dev.jsonl \
  --vncorenlp-dir "$VNCORENLP_DIR" \
  --output-dir model_artifacts/preflight_phobert_v5_hard_cases_final \
  --cuda-steps 20 \
  --forward-steps 8 \
  --mini-samples 64
```

Chỉ huấn luyện khi:

```text
overall_preflight = PASS
full_training_allowed = true
```

Lệnh huấn luyện:

```bash
python -m nlp.training.train_transformer \
  --backbone phobert \
  --train nlp/data/experimental_v2/train.jsonl \
  --dev nlp/data/experimental_v2/dev.jsonl \
  --out model_artifacts/experimental_phobert_absa_v5_hard_cases_final \
  --vncorenlp-dir "$VNCORENLP_DIR" \
  --epochs 5 \
  --batch-size 8 \
  --max-length 256 \
  --device cuda \
  --experimental \
  --preflight-report model_artifacts/preflight_phobert_v5_hard_cases_final/preflight_transformer_report.json
```

Checkpoint và threshold chỉ được lựa chọn trên Train/Dev. Natural Test không được dùng để lựa chọn mô hình hoặc điều chỉnh threshold.

---

## 13. Hạn chế và hướng phát triển

Hạn chế chính của phiên bản hiện tại:

- Chưa có corpus sáu aspect được con người gán nhãn và thẩm định độc lập để làm scientific-gold evaluation.
- Natural Test có rất ít mẫu `customer_service` và `other`.
- Balanced V2 chỉ là diagnostic cân bằng, chưa phải human-gold Test.
- Confidence sigmoid/softmax chưa được xem là xác suất thực tế đã calibration.
- Docker V5 chưa được chứng minh fully reproducible trên mọi môi trường.
- API phân tích trực tiếp cần thêm access control/rate limiting nếu triển khai production.

Hướng phát triển ưu tiên:

1. Xây dựng tập dữ liệu human-verified với nhiều annotator và quy trình adjudication.
2. Đóng băng Train/Dev/Test chuẩn và thực hiện scientific-final evaluation.
3. Bổ sung calibration và chính sách abstention.
4. Tăng dữ liệu cho `customer_service`, `other`, `neutral`, `mixed` và `no_aspect`.
5. Chuẩn hóa Docker runtime để provision đầy đủ Java, VnCoreNLP và Transformer dependencies.
6. Hoàn thiện bảo mật cho API nếu triển khai ngoài môi trường học tập.

---

## Ghi chú

PhoBERT V5 là runtime thực nghiệm hiện tại. Các phiên bản V1-V4 chỉ được giữ để truy vết quá trình phát triển và không nên dùng số liệu lịch sử của chúng thay cho kết quả V5.

Các kết quả Dev, Natural Test và Balanced V2 phục vụ những mục đích đánh giá khác nhau. Project trình bày chúng đúng phạm vi và **không tuyên bố scientific-final** khi chưa có tập dữ liệu human-gold phù hợp.
