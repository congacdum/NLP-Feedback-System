# Annotation Guideline — Vietnamese E-commerce ABSA

Version: 1.0 (frozen taxonomy)

This document defines the project labels. A model trained on inconsistent labels can be technically excellent and still learn the wrong task, so this file is a gate before final training.

## 1. Annotation unit

The unit is one customer feedback/review. One review may have **zero, one, or many aspects**. Each present aspect has exactly one project sentiment after aggregation.

Canonical shape:

```json
{
  "id": "...",
  "text": "Áo đẹp nhưng giao chậm.",
  "annotations": [
    {"aspect": "product_quality", "sentiment": "positive"},
    {"aspect": "delivery", "sentiment": "negative"}
  ]
}
```

Do not infer sentiment from star rating. Annotate the text.

## 2. Aspect taxonomy

### 2.1 `product_quality` — Chất lượng sản phẩm

Use for statements about the product itself:

- material, fabric, smell/taste where intrinsic to the product;
- durability and reliability;
- workmanship, seams, finish;
- design, color, shape, size/fit;
- function, performance, battery/camera/screen/features for electronics;
- defective/broken/not working;
- product matches or materially differs from advertised description/image;
- general product praise/criticism **when the referent is clearly the product**, e.g. “sản phẩm rất tốt”.

Examples:

- “Vải mềm và mặc thoải mái.” → `product_quality#positive`
- “Mới dùng hai hôm đã hỏng.” → `product_quality#negative`
- “Chất lượng bình thường.” → `product_quality#neutral`
- “Vải mềm nhưng đường may quá ẩu.” → `product_quality#mixed`

Do **not** automatically use quality for:

- shipping time / shipper behavior → `delivery`;
- box/protective wrapping → `packaging`;
- seller support / refund / warranty handling → `customer_service`;
- price/value → `price`;
- wrong ordered variant/item fulfillment without a claim that the product itself is defective/different from its listing → normally `other`; add CSKH only if seller resolution/support is discussed.

### 2.2 `delivery` — Giao hàng

Use for logistics and the delivery agent:

- delivery time / late / early / on-time;
- shipping/transport status;
- lost shipment;
- repeated delivery appointments;
- shipper/courier behavior;
- item condition explicitly attributed to transportation.

Examples:

- “Đặt từ tuần trước giờ mới tới.” → `delivery#negative` (implicit; no keyword required)
- “Hôm qua đặt, hôm nay đã nhận.” → `delivery#positive`
- “Shipper lịch sự nhưng hàng tới trễ ba ngày.” → `delivery#mixed`

`shipper` belongs to delivery, not CSKH.

### 2.3 `customer_service` — Dịch vụ CSKH

Use for seller/staff/customer-support interaction:

- consultation and message response;
- attitude of seller/support staff;
- complaint handling;
- return/exchange handling;
- refund handling;
- warranty/after-sales support.

Examples:

- “Shop rep rất nhanh.” → `customer_service#positive`
- “Báo lỗi nhưng shop không hỗ trợ.” → `customer_service#negative`
- “Tư vấn tốt nhưng hoàn tiền quá lâu.” → `customer_service#mixed`

Do not use this aspect merely because the word `shop` appears. “Shop đóng gói kỹ” is packaging; “shop giao nhanh” is delivery unless the sentence specifically evaluates service interaction.

### 2.4 `packaging` — Đóng gói

Use for packaging quality and protective preparation:

- outer box/bag;
- sealing;
- bubble wrap / shock protection;
- protective layers;
- package cleanliness/presentation;
- crushed/torn/open package.

Examples:

- “Bọc chống sốc rất kỹ.” → `packaging#positive`
- “Hộp móp và không có chống sốc.” → `packaging#negative`
- “Niêm phong chắc nhưng hộp ngoài bị rách.” → `packaging#mixed`

If product is broken but packaging/transport is not mentioned, annotate product quality only. Do not invent the cause.

### 2.5 `price` — Giá cả

Use for:

- expensive/cheap;
- value for money;
- price relative to quality;
- discount/promotion when the comment is specifically about economic value.

Examples:

- “Mức giá này rất đáng tiền.” → `price#positive`
- “Hơi đắt so với chất lượng.” → `price#negative` and, only if the sentence also evaluates quality itself, annotate quality accordingly.
- “Giá bình thường.” → `price#neutral`
- “Giá niêm yết cao nhưng giảm xong thì ổn.” → `price#mixed`

### 2.6 `other` — Khác

Use only for **meaningful evaluative content** outside the first five aspects.

Examples:

- “Shop tặng thêm móc khóa khá xinh.” → `other#positive`
- “Thiếu quà tặng kèm đã thông báo.” → `other#negative`
- “Đặt màu đen nhưng nhận màu trắng” when treated as order-fulfillment accuracy rather than an intrinsic product defect → `other#negative`.

`other` is not a trash bin and is not equivalent to source-dataset labels named `OTHERS`.

## 3. `no_aspect`

A review has no project annotation when it does not contain meaningful evaluative information for the taxonomy.

Examples:

- `okkkkkkkkkkkkk`
- random characters
- URLs only
- “hình ảnh mang tính nhận xu” with no product/service evaluation
- copied unrelated prose

Runtime output is `status=no_aspect`. There is no `no_aspect` row in `feedback_analysis`.

## 4. Sentiment rules

### `positive`
Explicit or contextually clear favorable evaluation.

### `negative`
Explicit or contextually clear unfavorable evaluation.

### `neutral`
Meaningful aspect mention/evaluation without favorable/unfavorable polarity, or genuinely middle/ordinary assessment.

Do not misuse neutral to hide conflicting positive/negative evidence.

### `mixed`
Use when **the same project aspect** has both positive and negative evidence in the same review.

Examples:

- “Vải đẹp nhưng đường may quá ẩu.” → quality mixed.
- “Tư vấn nhanh nhưng đổi trả cực chậm.” → CSKH mixed.

Different-aspect polarities are **not** mixed:

- “Áo đẹp nhưng giao chậm.” → quality positive + delivery negative.

## 5. Aggregating finer source labels into a project aspect

When multiple source aspects map to one project aspect:

- positive + negative → mixed
- mixed + anything → mixed
- positive + neutral → positive
- negative + neutral → negative
- neutral only → neutral

This rule is deterministic and must not depend on rating.

## 6. Linguistic phenomena

### Negation

- “không tốt” → negative
- “không tệ” / “không hề tệ” → usually positive, context permitting
- preserve negators during preprocessing.

### Contrast

`nhưng`, `tuy nhiên`, `mỗi tội`, `bù lại` often separate polarities. Annotate meaning, not keyword counts.

### Implicit expressions

- “Đặt từ tuần trước giờ mới tới.” → delivery negative
- “Mặc hai hôm đã bung chỉ.” → quality negative

### Sarcasm/light irony

- “Giao nhanh ghê, có mỗi 10 ngày.” → delivery negative

Annotate only when irony is sufficiently clear; otherwise flag for adjudication.

### Slang/teencode/no accents

Interpret if meaning is recoverable:

- “shop rep nhanh” → CSKH positive
- “ship lau vl” → delivery negative
- “khong he te” → relevant aspect positive if the referent is clear.

Do not silently normalize ambiguous slang into a guessed label.

## 7. Ambiguous edge cases

Use a `needs_adjudication` flag during annotation rather than forcing a label when two competent annotators can reasonably disagree.

Examples:

- “Hàng vỡ khi nhận” with no cause: product condition is negative, so quality negative; do not automatically add packaging/delivery.
- “Shop gửi nhầm màu”: order-fulfillment mismatch → other negative; if the product listing itself is misleading, quality may be appropriate; if seller response is discussed, add CSKH.
- “Hộp móp nhưng hàng không sao”: packaging negative; do not label quality positive unless customer actually evaluates product quality.

## 8. Annotation protocol

1. Freeze this guideline.
2. Pilot about 200 reviews.
3. Prefer two independent annotators.
4. Measure agreement separately for aspect presence and sentiment.
5. Target Cohen’s κ >= 0.80 before scaling annotation.
6. Adjudicate disagreements and update the guideline **before** the full annotation pass.
7. Freeze the guideline version used for the final corpus.
8. Do not rewrite Test labels after inspecting model errors unless creating a new versioned benchmark for a future experiment.

## 9. Challenge-set slices

The final challenge set should explicitly cover:

- negation;
- implicit meaning;
- contrast;
- multi-aspect;
- same-aspect mixed sentiment;
- slang/teencode;
- typo/no-accent;
- mild sarcasm;
- noise/no-aspect;
- neutral statements.

Challenge examples must be human verified and must not be used to fit weights. If they influence architecture/hyperparameters, call them Dev-Challenge and keep a separate final challenge set.
