# Prompt: Generate Candidate ABSA Test Data

Use this prompt in batches. For a full 2,160-annotation set, create six batches
of 200 records with 40 annotations per aspect, then a final batch whose quotas
fill the remaining counts. Save the output as UTF-8 JSONL, then run the project
validator before human review.

```text
You are creating candidate Vietnamese e-commerce feedback for a held-out ABSA
test set. Produce JSONL only: exactly one valid JSON object per line, no
markdown fence, no commentary and no blank lines.

This is candidate data, not final gold data. Never reuse a sentence from
training examples or from a previous batch. Every text must be natural customer
feedback about online shopping, in Vietnamese, and must be independently
understandable without its labels.

Required object schema:
{
  "id": "balanced_v2_XXXXXX",
  "text": "Vietnamese customer feedback",
  "annotations": [{"aspect": "...", "sentiment": "..."}],
  "split": "test_balanced",
  "source": "llm_generated_candidate",
  "manual_verified": false,
  "is_scientific_gold": false,
  "experimental_only": true,
  "difficulty": "single_aspect|multi_aspect|implicit|noisy|contrast|negation"
}

Only these aspects are valid:
- product_quality: material, durability, size, color, finish, function, product defect.
- delivery: shipping speed/status, courier behavior, delivery appointment, transport.
- customer_service: consultation, chat response, returns, refund, warranty, seller support.
- packaging: box/bag, sealing, bubble wrap, protective packing.
- price: selling price, discount, shipping fee, value for money.
- other: invoice, gifts, app/platform issue, or a general issue not covered above.

Only these sentiments are valid: positive, negative, neutral, mixed.

Annotation rules:
1. Give each mentioned aspect exactly one annotation. Do not infer absent aspects.
2. The same aspect must not appear twice. If one aspect contains both praise and
   criticism, assign mixed.
3. A record explicitly requested as `no_aspect` must use `"annotations": []`.
   Its text must be a generic or factual statement with no evaluative claim.
4. "Áo đẹp nhưng nhanh xù" => product_quality/mixed only.
5. "Áo đẹp nhưng giao trễ" => product_quality/positive and delivery/negative.
6. "Đóng gói sơ sài làm hộp móp" => packaging/negative unless the product itself
   is explicitly said to be damaged.
7. "Giá cao nhưng chất lượng xứng đáng" => price/negative and product_quality/positive.
8. "Nhân viên phản hồi chậm nhưng xử lý đổi trả rõ ràng" => customer_service/mixed.
9. "Ứng dụng không hiển thị hóa đơn" => other/negative.
10. A shipper is delivery, not customer_service. Mentioning "shop" alone does not
   imply customer_service.

Quality constraints:
- Do not expose aspect names, English labels, or annotation hints inside text.
- Avoid templated repetition and avoid copied wording across records.
- Use about 15% short (4-10 words), 65% medium (11-35 words), and 20% long
  (36-80 words) feedback.
- Include natural variation: colloquial wording, limited typos, negation,
  implicit sentiment and contrasts. Do not include personal data.
- For this batch, respect the exact quota supplied below. Quotas count
  annotations, not records. Multi-aspect records are allowed only when each
  aspect is genuinely present.

BATCH QUOTA (replace before running):
- product_quality: positive=__, negative=__, neutral=__, mixed=__
- delivery: positive=__, negative=__, neutral=__, mixed=__
- customer_service: positive=__, negative=__, neutral=__, mixed=__
- packaging: positive=__, negative=__, neutral=__, mixed=__
- price: positive=__, negative=__, neutral=__, mixed=__
- other: positive=__, negative=__, neutral=__, mixed=__
- no_aspect feedback records: __

Before outputting, internally verify JSON validity, unique id/text, allowed
labels, no duplicated aspect per record, and exact batch quotas. Output JSONL
only.
```
