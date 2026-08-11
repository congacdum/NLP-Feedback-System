# NLP Data Quality Report

- Total samples: **19680**
- Split counts: `{'train': 15358, 'dev': 1985, 'test': 2337}`
- No-aspect: **2881**
- Multi-aspect rate: **36.32%**
- Mixed annotations: **2302**
- Exact duplicate rows: **0**
- Near-duplicate candidates: **0**

## Source distribution

- UIT-ViSD4SA: 3613
- beauty_absa_2022: 15878
- project_demo_fixture: 189

## Aspect × sentiment

| Aspect | Positive | Neutral | Negative | Mixed |
|---|---:|---:|---:|---:|
| product_quality | 8096 | 481 | 2817 | 2279 |
| delivery | 3403 | 347 | 1711 | 4 |
| customer_service | 15 | 8 | 12 | 7 |
| packaging | 2884 | 26 | 116 | 4 |
| price | 3370 | 99 | 154 | 5 |
| other | 8 | 4 | 7 | 3 |

## Review length

`{'min': 1, 'median': 20.0, 'mean': 23.535924796747967, 'max': 170}`

> This report does not make data scientific gold. Run the strict gold assembly and leakage gates separately.
