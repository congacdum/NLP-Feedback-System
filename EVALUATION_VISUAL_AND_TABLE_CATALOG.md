# Danh muc hinh va bang danh gia thuat toan

**Muc dich:** catalog nay giup chon loc hinh/bang cho bao cao ve PhoBERT V5. Tat ca gia tri duoi day duoc doc tu artifact thuc te, khong tu screenshot UI.  
**Artifact trung tam:** `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/`  
**Trang thai khoa hoc:** `experimental_only=true`, `scientific_final=false`.

## 1. Quy uoc doc catalog

| Ky hieu | Y nghia |
| --- | --- |
| `NEN DUNG` | Nen dua vao phan than bao cao. |
| `NEN DUNG KEM GHI CHU` | Co gia tri, nhung caption va doan van phai neu ro pham vi. |
| `PHU LUC` | Huu ich de chung minh ky thuat, khong can thiet cho mach chinh. |
| `KHONG DUNG LAM KET QUA` | Co the dung de mo ta du lieu/protocol, nhung khong duoc trinh bay nhu chat luong cuoi cua model. |

Ba nguon danh gia khong duoc tron lan:

| Nhan trong catalog | Nguon | Vai tro dung |
| --- | --- | --- |
| `Dev` | `evaluation_dev/`, `dev_metrics.json` | Chon checkpoint va threshold; khong la held-out Test. |
| `Natural Test` | `evaluation/`, `nlp/data/experimental/test.jsonl` | Test giu rieng trong track experimental, phan bo tu nhien nhung rat lech o class hiem. |
| `Balanced V2` | `evaluation_balanced_v2/`, `nlp/data/raw/test_balanced_v2_candidates.jsonl` | Diagnostic can bang aspect; LLM-generated candidate, chua human-verified, khong la scientific gold. |

## 2. Bo chon loc de xuat cho bao cao

Neu bao cao can gon va manh, chon **5 bang + 5 hinh** sau.

### 2.1 Nam bang nen dua

| Ma | Bang | Noi dung | Vi tri de xuat | Trang thai |
| --- | --- | --- | --- | --- |
| T1 | Tong quan V5 | Artifact, backbone, Train/Dev/Test, seed, best epoch, hyperparameter va 6 threshold. | Cuoi Chuong 7 | `NEN DUNG` |
| T2 | Phan bo ba tap danh gia | So feedback/annotation va support 6 aspect tren Train, Dev, Natural Test, Balanced V2. | Chuong 4 | `NEN DUNG` |
| T3 | Ket qua tong hop ba protocol | Dev, Natural Test, Balanced V2: Strict Pair Macro-F1 va cac chi so phu hop. | Chuong 8 | `NEN DUNG` |
| T4 | Natural Test theo aspect | Precision, Recall, F1, support cua 6 aspect. | Chuong 8, dat canh H3 | `NEN DUNG KEM GHI CHU` |
| T5 | Balanced V2 theo aspect va sentiment | F1/suport can bang, no-aspect 75/120 va bootstrap CI. | Chuong 8 hoac Phu luc | `NEN DUNG KEM GHI CHU` |

### 2.2 Nam hinh nen dua

| Ma | Hinh | File co san | Muc dich | Trang thai |
| --- | --- | --- | --- | --- |
| H1 | Train/Dev loss | `evaluation/plots/train_dev_loss.png` | Cho thay qua trinh toi uu va gap Dev-loss sau epoch 3. | `NEN DUNG` |
| H2 | Dev strict-union Pair Macro-F1 theo epoch | `evaluation/plots/dev_pair_f1.png` | Chung minh epoch 5 duoc chon theo metric muc tieu. | `NEN DUNG` |
| H3 | F1 theo aspect tren Natural Test | `evaluation/plots/aspect_f1.png` | Ket qua aspect detection tren Test tu nhien; phai dat canh support. | `NEN DUNG KEM GHI CHU` |
| H4 | Ma tran nham lan sentiment tren Natural Test | `evaluation/plots/sentiment_confusion.png` | Chi ra neutral/mixed kho hon positive/negative. | `NEN DUNG KEM GHI CHU` |
| H5 | F1 theo aspect tren Balanced V2 | `evaluation_balanced_v2/plots/aspect_f1.png` | So sanh do ben giua 6 aspect khi moi aspect co 360 annotation. | `NEN DUNG KEM GHI CHU` |

Bo nam hinh nay ke duoc mach chinh: **model hoc nhu the nao -> tai sao epoch 5 duoc chon -> hieu nang tren Natural Test -> loi sentiment -> do ben theo aspect tren Balanced diagnostic**.

## 3. Bang de tao tu artifact

Khong co file bang rieng; cac bang nay can duoc dat trong source bao cao tu JSON artifact. Moi bang duoi day co gia tri that va duoc phep tao lai khong can chay model.

### T1. Bang tom tat thuc nghiem V5

**Nguon:** `training_config.json`, `training_manifest.json`, `thresholds.json`, `evaluation/metrics.json`, `evaluation_balanced_v2/metrics.json`.

| Truong | Gia tri V5 |
| --- | --- |
| Artifact runtime | `experimental_phobert_absa_v5_hard_cases_final` |
| Backbone | `vinai/phobert-base-v2` |
| Train / Dev / Natural Test | 18,038 / 2,205 / 2,337 feedback |
| Balanced V2 | 1,800 feedback, 2,160 annotation |
| Epoch / best epoch | 5 / 5 |
| Batch size / max length | 8 / 256 |
| Learning rate / weight decay | `2e-5` / `0.01` |
| Warmup ratio / patience | `0.10` / `2` |
| Optimizer / seed / recorded device | AdamW / 42 / `cuda` |
| Selection metric | Dev strict-union Pair Macro-F1 |
| `product_quality` threshold | 0.36 |
| `delivery` threshold | 0.80 |
| `customer_service` threshold | 0.50 |
| `packaging` threshold | 0.54 |
| `price` threshold | 0.32 |
| `other` threshold | 0.58 |
| Scientific-final | No; experimental only |

**Caption goi y:** `Bang X. Cau hinh, artifact va nguong quyet dinh cua PhoBERT V5 experimental runtime.`

**Thong diep can rut ra:** V5 la artifact duoc dong bang co tokenizer, encoder config, weights va threshold rieng theo aspect; cac gia tri threshold khong phai `0.00` nhu mot screenshot UI co the hien thi sai.

### T2. Bang phan bo du lieu va do tin cay cua support

**Nguon:** cac JSONL va `evaluation_balanced_v2/metrics.json`.

| Split | Feedback | Annotation | product_quality | delivery | price | packaging | customer_service | other | Ghi chu |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| V5 Train | 18,038 | 25,191 | 11,355 | 4,936 | 3,445 | 3,091 | 906 | 1,458 | Experimental Train |
| V5 Dev | 2,205 | 2,936 | 1,400 | 623 | 405 | 361 | 91 | 56 | Dev cho selection/threshold |
| Natural Test | 2,337 | 2,919 | 1,672 | 544 | 390 | 297 | 10 | 6 | Held-out experimental, rat lech class hiem |
| Balanced V2 | 1,800 | 2,160 | 360 | 360 | 360 | 360 | 360 | 360 | Candidate non-human-verified |

**Caption goi y:** `Bang X. Phan bo annotation cua cac tap trong track V5; Natural Test va Balanced V2 phuc vu hai muc dich khac nhau.`

**Thong diep can rut ra:** Natural Test phan anh phan bo tu nhien nhung khong du support de on dinh o `customer_service` va `other`; Balanced V2 sua **can bang so luong** chu khong sua **provenance**.

### T3. Bang ket qua tong hop theo dung protocol

| Protocol | Strict-union Pair Macro-F1 | Pair Micro-F1 | Aspect Macro-F1 | Sentiment Macro-F1 | Exact Match | Ghi chu |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Dev model-selection | 0.8809 | 0.9121 | 0.9779 | 0.8338 | 0.8562 | Cung Dev da chon checkpoint/threshold |
| Natural experimental Test | 0.5609 | 0.8843 | 0.9507 | 0.7745 | 0.8228 | Held-out experimental, rare pairs rat it |
| Balanced V2 diagnostic | 0.7961 | 0.8305 | 0.9114 | 0.8840 | 0.7761 | Candidate, no retraining, frozen Dev threshold |

**Caption goi y:** `Bang X. Ket qua PhoBERT V5 tren ba protocol danh gia; cac dong khong duoc xem la cac benchmark khoa hoc tuong duong.`

**Doan phan tich nen dat ngay sau bang:**

> Ket qua Dev la optimistic model-selection evidence vi checkpoint va threshold deu duoc chon tren Dev. Natural Test cho strict Pair Macro-F1 thap hon, dong thoi co phan bo cap nhan rat lech. Balanced V2 can bang aspect nen phu hop de chan doan do ben tuong doi, nhung nhan van la LLM-generated candidate va chua duoc human verification. Khoang cach giua ba dong la ket qua can duoc thao luan, khong duoc che giau va cung khong duoc suy dien thanh scientific-final.

### T4. Bang Natural Test theo aspect

**Nguon:** `evaluation/metrics.json -> test.per_aspect`.

| Aspect | Precision | Recall | F1 | Support | Cach doc dung |
| --- | ---: | ---: | ---: | ---: | --- |
| product_quality | 0.9586 | 0.9827 | 0.9705 | 1,672 | On dinh nhat vi support lon. |
| delivery | 0.9782 | 0.9890 | 0.9835 | 544 | On dinh tuong doi. |
| customer_service | 0.7692 | 1.0000 | 0.8696 | 10 | Khong du support de ket luan manh. |
| packaging | 0.9159 | 0.9899 | 0.9515 | 297 | On dinh tuong doi. |
| price | 0.8843 | 0.9795 | 0.9294 | 390 | Precision thap hon recall; can xem them polarity. |
| other | 1.0000 | 1.0000 | 1.0000 | 6 | Khong duoc dien giai la perfect; support qua nho. |

**Caption goi y:** `Bang X. Hieu nang phat hien aspect cua PhoBERT V5 tren Natural Test experimental.`

**Canh bao bat buoc duoi bang:** `F1 cua customer_service va other khong on dinh do support lan luot chi la 10 va 6 annotation.`

### T5. Bang Balanced V2 theo aspect va no-aspect

**Nguon:** `evaluation_balanced_v2/metrics.json -> test.per_aspect`, `test.no_aspect`, `test.pair_macro_f1_bootstrap_95`.

| Aspect | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| product_quality | 0.8289 | 0.9556 | 0.8877 | 360 |
| delivery | 0.9481 | 0.9139 | 0.9307 | 360 |
| customer_service | 0.8432 | 0.9861 | 0.9091 | 360 |
| packaging | 0.9137 | 1.0000 | 0.9549 | 360 |
| price | 0.9722 | 0.9722 | 0.9722 | 360 |
| other | 0.7921 | 0.8361 | 0.8135 | 360 |

Them dong tom tat:

| no-aspect support | Dung de trong | Accuracy | False-positive rate | Bootstrap Pair Macro-F1 95% CI |
| ---: | ---: | ---: | ---: | --- |
| 120 | 75 | 0.6250 | 0.3750 | [0.7780, 0.8118] |

**Caption goi y:** `Bang X. Ket qua theo aspect tren Balanced V2 diagnostic voi 360 annotation moi aspect.`

**Canh bao bat buoc:** `Balanced V2 la LLM-generated candidate (`manual_verified=false`, `is_scientific_gold=false`); bang chi dung de chan doan do ben, khong thay the Natural Test hoac human-gold Test.`

### T6. Bang tien trinh phien ban V1 -> V2 -> V5

**Chua co PNG san.** Co the tao bang/column chart moi tu `training_manifest.json` cua tung artifact, neu can minh hoa qua trinh phat trien.

| Phien ban | Dev rows | Best epoch | Dev strict-union Pair Macro-F1 | Vai tro hien tai |
| --- | ---: | ---: | ---: | --- |
| PhoBERT V1 | 1,985 | 5 | 0.4662 | Historical experimental artifact |
| PhoBERT V2 repaired | 2,205 | 4 | 0.8976 | Historical experimental artifact |
| PhoBERT V5 | 2,205 | 5 | 0.8809 | Current experimental runtime |

**Caption goi y:** `Bang X. Moc Dev strict-union Pair Macro-F1 trong qua trinh phat trien artifact PhoBERT.`

**Canh bao bat buoc:** Cac phien ban dung data revision khac nhau; day la **timeline truy vet**, khong phai benchmark controlled chung mot data protocol. Khong goi V2 la current winner; V5 la runtime hien tai.

### T7. Bang baseline tren cung Natural Test

**Nguon:** `evaluation/metrics.json -> comparison_same_test`.

| Model | Pair Macro-F1 | Strict-union Pair Macro-F1 | Pair Micro-F1 | Exact Match |
| --- | ---: | ---: | ---: | ---: |
| Rule | 0.2001 | 0.1917 | 0.4125 | 0.2383 |
| LinearSVM | 0.4299 | 0.4120 | 0.8137 | 0.7317 |
| TF-IDF LR | 0.5124 | 0.4911 | 0.8012 | 0.7231 |
| PhoBERT V5 | 0.5853 | 0.5609 | 0.8843 | 0.8228 |

Bo sung neu can: paired bootstrap Transformer - TF-IDF LR co CI `[-0.0299, 0.1858]`, vi vay khong nen viet ket luan manh ve hon TF-IDF LR theo Pair Macro-F1. Transformer - LinearSVM co CI `[0.0436, 0.2192]`.

**Caption goi y:** `Bang X. So sanh cac model tren cung Natural Test experimental; baseline duoc fit tren Train va tune threshold tren Dev.`

**Trang thai:** `NEN DUNG KEM GHI CHU`, chi khi bao cao can baseline. Khong dung de khang dinh superiority khoa hoc vi Test van experimental/non-gold.

## 4. Danh muc hinh hien co: Natural evaluation

Thu muc: `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/evaluation/plots/`.

| File / kich thuoc | Du lieu va metric | Mo ta chi tiet | Cach dung trong bao cao | Trang thai |
| --- | --- | --- | --- | --- |
| `train_dev_loss.png` (1035x610) | V5 history, epoch 1-5 | Duong train loss giam 1.3791 -> 0.1893. Dev loss giam den 0.5510 o epoch 3 roi tang den 0.6225 o epoch 5. | Dat Chuong 7. Giai thich checkpoint khong chon theo Dev loss thap nhat. | `NEN DUNG` |
| `dev_pair_f1.png` (1035x610) | Dev strict-union Pair Macro-F1 | Metric tang 0.6632 -> 0.8583 -> 0.8519 -> 0.8774 -> 0.8809. Epoch 5 la best theo metric target. | Dat canh H1. | `NEN DUNG` |
| `aspect_f1.png` (1184x656) | Natural Test, F1 theo 6 aspect | Bar chart F1 aspect: product quality 0.9705; delivery 0.9835; customer service 0.8696; packaging 0.9515; price 0.9294; other 1.0000. | Dat canh T4, bat buoc show support. | `NEN DUNG KEM GHI CHU` |
| `sentiment_confusion.png` (813x668) | Natural Test conditional sentiment confusion | Hang la nhan that, cot la du doan; chi danh gia sentiment tai cac gold aspect. Diagonal: positive 1732, neutral 38, negative 638, mixed 254. | Dat Chuong 8. Nhac ro day khong phai confusion end-to-end aspect+sentiment. | `NEN DUNG KEM GHI CHU` |
| `model_comparison.png` (1110x657) | Natural Test, Rule / LinearSVM / TF-IDF LR / Transformer | Bieu do cot so sanh **Pair Macro-F1 gold-active** va Aspect Macro-F1, khong phai strict-union. Tat ca model dung cung Natural Test. | Chi dat neu co muc baseline; caption phai dung ten metric. | `NEN DUNG KEM GHI CHU` |
| `threshold_f1.png` (1184x731) | Dev only | 6 duong F1 theo threshold 0.20-0.80. Giai thich vi sao threshold la per-aspect va duoc chon tren Dev. | Phu luc hoac Chuong 7 neu can chung minh protocol. | `PHU LUC` |
| `pr_curves_dev.png` (1109x806) | Dev only, aspect detection score | Precision-Recall curve rieng cho tung aspect tren Dev truoc khi chon operating threshold. | Phu luc; khong caption nhu Test performance. | `PHU LUC` |
| `dataset_distribution.png` (1184x656) | **V5 Train**, khong phai Natural Test | Bar chart so annotation train: product quality 11,355; delivery 4,936; packaging 3,091; price 3,445; customer service 906; other 1,458. | Chuong 4 de mo ta Train imbalance. Khong dung caption "phan bo Test". | `KHONG DUNG LAM KET QUA` |
| `aspect_sentiment_heatmap.png` (1183x732) | **V5 Train**, khong phai Natural Test | Heatmap dem annotation theo 6 aspect x 4 sentiment trong Train. | Chuong 4/Phu luc de mo ta du lieu; khong phai performance heatmap. | `KHONG DUNG LAM KET QUA` |
| `review_length_distribution.png` (1033x582) | **V5 Train**, whitespace-token length | Histogram do dai feedback trong Train; "token" o day la token tach bang khoang trang, khong phai so PhoBERT subword. | Phu luc neu can mo ta corpus. | `PHU LUC` |

## 5. Danh muc hinh hien co: Dev-only validation

Thu muc: `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/evaluation_dev/plots/`.

Nhung hinh nay la bang chung qua trinh phat trien, **khong duoc goi la ket qua Test**. `train_dev_loss.png`, `dev_pair_f1.png` va `threshold_f1.png` trung noi dung voi cac hinh Natural evaluation cung ten, chi khac noi luu; chon mot ban duy nhat khi dua vao bao cao.

| File | Mo ta | Cach dung | Trang thai |
| --- | --- | --- | --- |
| `aspect_f1.png` | F1 theo aspect tren Dev; support customer service 91, other 56. | Khong can dua neu da co Natural aspect F1; neu dua phai ghi Dev model-selection. | `PHU LUC` |
| `sentiment_f1.png` | F1 Dev theo positive/neutral/negative/mixed; neutral la diem yeu tuong doi. | Huu ich de giai thich selection diagnostics. | `PHU LUC` |
| `aspect_sentiment_f1.png` | Heatmap F1 cua 24 cap aspect-sentiment tren Dev; o cap support 0 hien `-`. | Huu ich cho phan tich chi tiet, nhung de doc. | `PHU LUC` |
| `aspect_support.png` | Support Dev theo 6 aspect. | Ho tro giai thich tai sao khong dien giai F1 class hiem qua manh. | `PHU LUC` |
| `sentiment_confusion.png` | Confusion sentiment conditional tren Dev. | Khong dua cung Natural confusion tru khi can so sanh Dev-Test. | `PHU LUC` |
| `train_dev_loss.png`, `dev_pair_f1.png`, `threshold_f1.png` | Trung noi dung hinh duoc liet ke o Muc 4. | Dung mot ban duy nhat. | `PHU LUC` |

## 6. Danh muc hinh hien co: Balanced V2 diagnostic

Thu muc: `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/evaluation_balanced_v2/plots/`.

| File / kich thuoc | Du lieu va metric | Mo ta chi tiet | Cach dung trong bao cao | Trang thai |
| --- | --- | --- | --- | --- |
| `aspect_f1.png` (1184x656) | Balanced V2 | F1: product quality 0.8877; delivery 0.9307; customer service 0.9091; packaging 0.9549; price 0.9722; other 0.8135. Moi aspect support 360. | H5 trong bo chon loc. Caption phai ghi candidate/non-gold. | `NEN DUNG KEM GHI CHU` |
| `sentiment_f1.png` (1004x612) | Balanced V2 | F1: positive 0.9180; neutral 0.8870; negative 0.9272; mixed 0.8039. Mixed la sentiment kho nhat trong bo can bang nay. | Chuong 8 hoac phu luc de bo sung cho H5. | `NEN DUNG KEM GHI CHU` |
| `aspect_sentiment_f1.png` (1186x762) | Balanced V2 | Heatmap F1 cua 24 cap aspect-sentiment, moi aspect co fixed distribution 120 positive / 72 neutral / 120 negative / 48 mixed. Phat hien cac o mixed yeu nhu delivery mixed 0.2222, price mixed 0.6111, other mixed 0.6780. | Rat gia tri cho phan tich loi; dat phu luc neu main report bi day. | `PHU LUC` |
| `sentiment_confusion.png` (813x680) | Balanced V2 conditional sentiment confusion | Diagonal: positive 644/720, neutral 416/432, negative 681/720, mixed 205/288. Mixed hay bi nham sang negative (37) va positive (29). | Huu ich neu muon phan tich `mixed`; phai ghi conditional. | `NEN DUNG KEM GHI CHU` |
| `dataset_distribution.png` (1184x657) | Balanced V2 dataset | Sau cot bang nhau 360, chung minh aspect balance. | Dua canh H5 hoac T2 de lam ro day la balanced diagnostic. | `NEN DUNG KEM GHI CHU` |
| `aspect_sentiment_heatmap.png` (1183x732) | Balanced V2 dataset | Moi hang co 120 positive, 72 neutral, 120 negative, 48 mixed. Chung minh sentiment distribution cung duoc kiem soat. | Chuong 4/Phu luc. Day la phan bo du lieu, khong phai performance. | `KHONG DUNG LAM KET QUA` |
| `review_length_distribution.png` (1034x582) | Balanced V2 candidate length | Histogram do dai feedback candidate. | Phu luc neu can kiem tra domain/style distribution; khong chung minh chat luong model. | `PHU LUC` |

## 7. Hinh khong nen dua hoac can tranh dung sai

1. Khong dua dong thoi `evaluation/plots/train_dev_loss.png` va ban trung o `evaluation_dev/plots/`; chung la cung V5 training history.
2. Khong dung `evaluation/plots/dataset_distribution.png` de minh hoa Natural Test. File nay ve **Train**.
3. Khong dung `evaluation/plots/aspect_sentiment_heatmap.png` nhu heatmap hieu nang; no chi dem **Train annotation**.
4. Khong dung Natural `aspect_f1.png` ma bo support: `other=1.0000` tren 6 mau se gay ket luan sai.
5. Khong dung Balanced V2 nhu bang chung "model da tot tren human-gold Test".
6. Khong dung `sentiment_confusion.png` nhu confusion matrix end-to-end. Metric nay la conditional sentiment: aspect da co trong gold duoc dung de danh gia polarity.
7. Khong chup trang Seller Model Evaluation co cot threshold `0.00`; gia tri dung nam trong `thresholds.json` va la 0.36/0.80/0.50/0.54/0.32/0.58.
8. Khong dua challenge chart: artifact natural co `challenge_samples=0` va khong co `challenge_performance.png`.

## 8. Caption va doan dien giai mau

### H1 - Training loss

**Caption:** `Hinh X. Duong loss Train va Dev cua PhoBERT V5 trong nam epoch huan luyen.`

**Dien giai:** Train loss giam lien tuc. Dev loss thap nhat o epoch 3, sau do tang nhe. Tuy nhien, checkpoint V5 duoc chon theo Dev strict-union Pair Macro-F1, khong phai theo Dev loss, va metric muc tieu dat 0.8809 o epoch 5. Day la dau hieu can theo doi kha nang tong quat hoa, chua du de ket luan overfitting nang.

### H2 - Dev metric theo epoch

**Caption:** `Hinh X. Dev strict-union Pair Macro-F1 theo epoch va ly do chon checkpoint epoch 5.`

**Dien giai:** Gia tri dat 0.6632, 0.8583, 0.8519, 0.8774 va 0.8809 tu epoch 1 den 5. Do do `model.pt` luu checkpoint epoch 5 theo quy tac selection da dong bang tren Dev.

### H3/T4 - Natural Test theo aspect

**Caption:** `Hinh X. F1 phat hien aspect cua PhoBERT V5 tren Natural Test experimental; xem support trong Bang X.`

**Dien giai:** Ket qua cao o product quality, delivery, packaging va price co support tu 297 den 1,672. Hai aspect customer service va other chi co 10 va 6 annotation, vi vay F1 cua chung chi co y nghia mo ta tren bo nay va khong phai uoc luong on dinh.

### H4 - Natural sentiment confusion

**Caption:** `Hinh X. Ma tran nham lan sentiment conditional tren Natural Test experimental.`

**Dien giai:** Positive va negative co diagonal cao hon; neutral la lop yeu (F1 0.4393), mixed o muc trung binh (F1 0.7840). Ma tran tach bai toan polarity ra khoi loi phat hien aspect, nen can duoc doc cung Pair F1 end-to-end.

### H5/T5 - Balanced V2

**Caption:** `Hinh X. F1 theo aspect tren Balanced V2 diagnostic (360 annotation moi aspect).`

**Dien giai:** Do can bang support, hinh nay lam ro hon kha nang tuong doi giua aspect. `other` (0.8135) va product quality (0.8877) thap hon packaging/price, nhung ket qua chi la diagnostic vi candidate chua duoc human verification. No khong phu dinh hoac thay the Natural Test.

## 9. Chon loc theo do dai bao cao

| Neu bao cao con... | Chon |
| --- | --- |
| 4-6 hinh | H1, H2, H3, H4, H5; giu T1-T5. |
| 7-9 hinh | Them `model_comparison.png`, `threshold_f1.png`, `evaluation_balanced_v2/plots/sentiment_f1.png`. |
| Phu luc ky thuat | Them PR Dev, Dev aspect-sentiment F1, Balanced aspect-sentiment F1, Balanced distribution, review-length histograms. |
| Chi duoc 3 hinh | H1, H3, H5; giu T3 va T4. H2 co the thay bang dong "best epoch=5" trong T1. |

## 10. Checklist truoc khi chen vao bao cao

- [ ] Caption ghi ro `Dev`, `Natural Test experimental` hoac `Balanced V2 diagnostic`.
- [ ] Bieu do Natural aspect F1 co bang support di kem.
- [ ] Bieu do Balanced V2 co ghi `manual_verified=false`, `is_scientific_gold=false` trong van ban/caption gan do.
- [ ] Khong goi Dev hoac Balanced la final Test.
- [ ] Khong dung Pair Macro-F1 va strict-union Pair Macro-F1 thay the cho nhau ma khong ghi ro ten metric.
- [ ] Natural model comparison ghi dung metric tren hinh: Pair Macro-F1 gold-active va Aspect Macro-F1.
- [ ] Threshold trong bang lay tu `thresholds.json`, khong lay tu cot UI dang hien `0.00`.
- [ ] Bat ky ket luan hon/thua baseline deu neu ro Natural Test la experimental va rare-pair support rat lech.

## 11. Nguon file

- `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/training_manifest.json`
- `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/training_config.json`
- `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/thresholds.json`
- `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/evaluation/metrics.json`
- `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/evaluation_dev/metrics.json`
- `model_artifacts/experimental_phobert_absa_v5_hard_cases_final/evaluation_balanced_v2/metrics.json`
- `nlp/evaluation/metrics.py`
- `nlp/evaluation/plots.py`
