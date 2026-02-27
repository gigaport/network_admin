# Plan: 회원사 매입내역 (purchase-contract)

## Overview
회선계약 관리 메뉴 하위에 "회원사 매입내역" 화면을 추가한다.
Excel 데이터(회원사_매입계약내역.xlsx)를 `purchase_contract` 테이블에 적재하고,
`network_cost.code`를 JOIN하여 매입금액(cost_price)을 함께 표시한다.

## Data Source
- **파일**: `/home/sysmon/data/회원사_매입계약내역.xlsx`
- **데이터**: 110건 (31개 회원사, 4개 데이터센터, 2개 통신사)

### Excel 필드 → DB 컬럼 매핑

| Excel 헤더 | DB 컬럼 | 타입 | 설명 |
|-----------|---------|------|------|
| member_code | member_code | varchar(10) NOT NULL | 회원사코드 (KY, SH, KR 등) |
| datacenter_code | datacenter_code | varchar(10) | 데이터센터 (DC1, DC2, DC3, DR) |
| provider | provider | varchar(20) | 통신사 (KT, LGU) |
| billing_start_date | billing_start_date | date | 과금시작일 |
| contract_end_date | contract_end_date | date | 계약종료일 |
| service_id | service_id | varchar(30) | 서비스ID (KT: C18000504 등) |
| nni_id | nni_id | varchar(30) | NNI ID |
| cost_code | cost_code | varchar(20) | 원가코드 → network_cost.code FK |

### purchase_contract 테이블 DDL

```sql
CREATE TABLE purchase_contract (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) NOT NULL,
    datacenter_code VARCHAR(10),
    provider VARCHAR(20),
    billing_start_date DATE,
    contract_end_date DATE,
    service_id VARCHAR(30),
    nni_id VARCHAR(30),
    cost_code VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### JOIN 관계
```
purchase_contract.cost_code → network_cost.code
→ network_cost.cost_price (매입금액)
→ network_cost.cost_standart (비용기준 표시)
→ network_cost.provider (통신사 확인)
```

### 사용되는 cost_code 값 (5종)
| cost_code | cost_standart | cost_price |
|-----------|--------------|------------|
| KT-M-001 | 기본료(서울경기권)-10G | 4,500,000원 |
| LGU-M-001 | 기본료(서울경기권)-10G | 1,850,000원 |
| LGU-M-002 | 기본료(서울경기권)-10G+임차료포함 | 2,450,000원 |
| LGU-M-003 | 기본료(서울경기권)-10G+RT장비이중화 | 1,600,000원 |
| LGU-M-004 | 기본료(서울경기권)-10G+RT장비 이중화+XC비용 | 1,800,000원 |

## 변경 파일

### 1. DB: purchase_contract 테이블 생성 + 데이터 import
- 테이블 DDL 실행
- Excel 110건 데이터 INSERT (Python openpyxl 활용)
- Excel 수식(=EDATE) 셀은 계산된 값 또는 NULL 처리

### 2. FastAPI: `fastapi/routers/network.py`
**4개 엔드포인트 추가:**

| Method | Path | 설명 |
|--------|------|------|
| GET | `/purchase_contract` | 전체 조회 (network_cost JOIN) |
| POST | `/purchase_contract` | 추가 |
| PUT | `/purchase_contract/{id}` | 수정 |
| DELETE | `/purchase_contract/{id}` | 삭제 |

**GET 조회 SQL:**
```sql
SELECT pc.*, nc.cost_price, nc.cost_standart
FROM purchase_contract pc
LEFT JOIN network_cost nc ON pc.cost_code = nc.code
ORDER BY pc.member_code, pc.datacenter_code, pc.provider
```

**추가 엔드포인트:**

| Method | Path | 설명 |
|--------|------|------|
| GET | `/network_cost/codes` | cost_code 선택용 목록 (code + cost_standart + cost_price) |

### 3. Django: `net_admin/setting/views.py` + `urls.py`
- 프록시 뷰 5개 (CRUD + cost_codes 목록)
- URL 패턴 등록

### 4. Template: `net_admin/templates/purchase_contract.html`
- 회원사별 그룹핑 리스트 (subscriber_codes JOIN으로 회사명 표시)
- 각 항목: member_code, datacenter, provider, billing_start, contract_end, service_id, nni_id, cost_code, **매입금액(cost_price)**
- 추가/수정 모달: cost_code는 select (network_cost.code + cost_standart 표시)
- 요약 통계 카드: 전체 건수, 총 매입금액, 통신사별 건수/금액

### 5. JS: `net_admin/static/assets/js/net_admin/purchase_contract.js`
- loadPurchaseContract(): 데이터 로드 + 회원사별 그룹 렌더링
- loadCostCodes(): network_cost 코드 목록 로드 (select 옵션용)
- saveAdd() / saveEdit() / deleteItem()
- cost_code select 변경 시 매입금액 자동 표시

### 6. Menu: `net_admin/templates/components/base.html`
- 회선계약 관리 하위에 "회원사 매입내역" 메뉴 추가
- URL: `/purchase_contract`

## 화면 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│ 회선계약 관리 > 회원사 매입내역                                │
├─────────────────────────────────────────────────────────────┤
│ [전체 110건] [KT 31건/1.4억] [LGU 79건/1.7억] [항목추가]     │
├─────────────────────────────────────────────────────────────┤
│ ▼ 키움증권 (KY) - 4건                                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ DC1 | KT  | 2025-02-01~2030-01-31 | C18000504 |        │ │
│ │     | KT-M-001 | 매입: 4,500,000원            | ✏️ 🗑️  │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ DC1 | LGU | 2025-02-01~2030-02-01 |           |        │ │
│ │     | LGU-M-001 | 매입: 1,850,000원           | ✏️ 🗑️  │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ▼ 신한투자증권 (SH) - 3건                                     │
│ ...                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 추가/수정 모달
```
┌─────────────────────────────────────┐
│ 매입내역 추가                         │
├─────────────────────────────────────┤
│ 회원사코드: [KY    ]                  │
│ 데이터센터: [DC1   ]                  │
│ 통신사:     [KT ▼  ]                  │
│ 과금시작일: [2025-02-01]              │
│ 계약종료일: [2030-01-31]              │
│ 서비스ID:   [C18000504]              │
│ NNI ID:    [250026110064]            │
│ 원가코드:   [KT-M-001 ▼]             │
│   → 기본료(서울경기권)-10G / 4,500,000원 │
├─────────────────────────────────────┤
│         [취소]  [저장]                 │
└─────────────────────────────────────┘
```

## 구현 순서

1. DB 테이블 생성 + Excel 데이터 import
2. FastAPI CRUD 엔드포인트 + cost_codes 목록 API
3. Django 프록시 뷰 + URL 등록
4. base.html 메뉴 추가
5. purchase_contract.html 템플릿 작성
6. purchase_contract.js 작성
7. staticfiles 복사 + 컨테이너 재시작
8. 동작 검증

## 검증

1. 화면 로드 시 110건 데이터 회원사별 그룹핑 표시
2. 각 항목에 매입금액(cost_price) 정상 표시
3. 항목 추가 시 cost_code select에서 network_cost 코드 + 비용기준 표시
4. cost_code 선택 시 매입금액 자동 표시
5. 추가/수정/삭제 정상 동작
6. 메뉴 "회원사 매입내역" 클릭 시 정상 이동
