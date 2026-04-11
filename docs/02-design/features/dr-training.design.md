# Design: 재해복구훈련 (DR Training) 인터페이스 모니터링

> Plan 참조: `docs/01-plan/features/dr-training.plan.md`

## 1. 시스템 구조

```
[Browser]
    │
    ├─ GET /dr_training ──→ [Django View: dr_training()] ──→ dr_training.html 렌더링
    │
    └─ GET /dr_training/get_dr_training_status ──→ [Django View: get_dr_training_status()]
                                                        │
                                                        ▼
                                              [FastAPI GET /api/v1/network/dr-training/status]
                                                        │
                                                        ▼ (concurrent.futures 병렬)
                                              [nxapi_client.query_interfaces()]
                                                        │
                                         ┌──────────────┼──────────────┐
                                         ▼              ▼              ▼
                                   172.30.172.13  172.28.172.29  192.168.254.40
                                   (HTTP:80)      (HTTP:80)      (HTTP:80)
                                   NX-API         NX-API         NX-API
```

## 2. 훈련 대상 설정 (상수 정의)

```python
# fastapi/routers/network.py 내 상수
DR_TRAINING_TARGETS = [
    {
        "procedure": "51.01",
        "device_name": "RBD_ASN_L3_01",
        "ip": "172.30.172.13",
        "interfaces": ["Ethernet1/41", "Ethernet1/48"]
    },
    {
        "procedure": "51.04",
        "device_name": "PYD_ASN_L3_01",
        "ip": "172.28.172.29",
        "interfaces": ["Ethernet1/41", "Ethernet1/42"]
    },
    {
        "procedure": "51.05",
        "device_name": "PHQ_ASN_L3_01",
        "ip": "192.168.254.40",
        "interfaces": ["Ethernet1/47"]
    }
]
```

## 3. Backend API 설계

### 3.1 NX-API 클라이언트 (`fastapi/utils/nxapi_client.py`)

```python
# 모듈 구조
import requests
import logging
import os

logger = logging.getLogger(__name__)

NXAPI_USERNAME = os.environ.get("NXAPI_USERNAME", "")
NXAPI_PASSWORD = os.environ.get("NXAPI_PASSWORD", "")
NXAPI_TIMEOUT = 5  # 초

def query_interfaces(ip: str, interfaces: list) -> dict:
    """
    NX-API로 특정 인터페이스 상태 조회
    
    Args:
        ip: 스위치 IP
        interfaces: 조회할 인터페이스 목록 ["Ethernet1/41", ...]
    
    Returns:
        {
            "success": True/False,
            "interfaces": [
                {
                    "name": "Ethernet1/41",
                    "admin_state": "up",
                    "oper_state": "up",
                    "speed": "1000",
                    "mtu": "9216",
                    "description": "...",
                    "last_link_flapped": "..."
                }
            ],
            "error": null | "에러 메시지"
        }
    """
    # NX-API JSON-RPC 호출
    # URL: http://{ip}/ins
    # Command: show interface {intf} (인터페이스별 개별 호출)
    # 또는 show interface 전체 조회 후 필터링
```

**NX-API 요청 형식:**
```json
{
    "ins_api": {
        "version": "1.0",
        "type": "cli_show",
        "chunk": "0",
        "sid": "1",
        "input": "show interface Ethernet1/41",
        "output_format": "json"
    }
}
```

**NX-API 응답 파싱 대상 필드:**
```
ins_api.outputs.output.body.TABLE_interface.ROW_interface
  ├── interface       → name
  ├── admin_state     → admin_state
  ├── state           → oper_state
  ├── eth_speed       → speed
  ├── eth_mtu         → mtu
  ├── desc            → description
  └── eth_link_flapped → last_link_flapped
```

### 3.2 FastAPI 엔드포인트 (`fastapi/routers/network.py`)

```
GET /api/v1/network/dr-training/status
```

**Response:**
```json
{
    "success": true,
    "timestamp": "2026-04-11T14:30:00",
    "devices": [
        {
            "procedure": "51.01",
            "device_name": "RBD_ASN_L3_01",
            "ip": "172.30.172.13",
            "reachable": true,
            "interfaces": [
                {
                    "name": "Ethernet1/41",
                    "admin_state": "up",
                    "oper_state": "up",
                    "speed": "1000",
                    "mtu": "9216",
                    "description": "to-member-server",
                    "last_link_flapped": "2026-03-15T10:00:00"
                },
                {
                    "name": "Ethernet1/48",
                    "admin_state": "up",
                    "oper_state": "down",
                    "speed": "auto",
                    "mtu": "-",
                    "description": "",
                    "last_link_flapped": "never"
                }
            ],
            "error": null
        }
    ],
    "summary": {
        "total_interfaces": 5,
        "up_count": 4,
        "down_count": 1,
        "all_up": false
    }
}
```

**처리 로직:**
1. `DR_TRAINING_TARGETS` 순회
2. `ThreadPoolExecutor`로 장비별 병렬 조회 (기존 executor 활용)
3. 각 장비에 `nxapi_client.query_interfaces()` 호출
4. 결과 집계하여 summary 계산
5. 개별 장비 실패 시 해당 장비만 `reachable: false`, 나머지는 정상 반환

### 3.3 Django View (`net_admin/app/views.py`)

```python
# 페이지 렌더링
def dr_training(request):
    return render(request, 'dr_training.html', {
        'parent_menu': 'network_monitoring',
        'sub_menu': 'dr_training'
    })

# API 프록시
def get_dr_training_status(request):
    response = requests.get(
        f"{FASTAPI_BASE_URL}/api/v1/network/dr-training/status",
        timeout=20
    )
    return JsonResponse(response.json())
```

### 3.4 URL 라우팅

```python
# net_admin/app/urls.py 추가
path('dr_training', views.dr_training, name='dr_training'),
path('get_dr_training_status', views.get_dr_training_status, name='get_dr_training_status'),

# net_admin/urls.py 추가
path('dr_training/', include('app.urls')),
```

## 4. Frontend 설계

### 4.1 화면 레이아웃 (`dr_training.html`)

```
┌─────────────────────────────────────────────────────────────────┐
│ 네트워크 모니터링 > 재해복구훈련                                    │
│                                                                 │
│ [재해복구훈련 모니터링]                    [새로고침] [자동갱신 ▼]   │
├─────────────────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│ │ 총 포트  │ │  Up      │ │  Down    │   마지막 조회: 14:30:00  │
│ │    5     │ │    4     │ │    1     │                         │
│ └──────────┘ └──────────┘ └──────────┘                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ┌─── 훈련절차 51.01 ─── RBD_ASN_L3_01 (172.30.172.13) ───────┐ │
│ │ Interface     │ Admin │ Oper  │ Speed │ Description │ Flap  │ │
│ │ Ethernet1/41  │  up   │  ●up  │ 1G    │ ...         │ ...   │ │
│ │ Ethernet1/48  │  up   │  ●down│ auto  │ ...         │ ...   │ │
│ └───────────────────────────────────────────────────────────── │ │
│                                                                 │
│ ┌─── 훈련절차 51.04 ─── PYD_ASN_L3_01 (172.28.172.29) ───────┐ │
│ │ Interface     │ Admin │ Oper  │ Speed │ Description │ Flap  │ │
│ │ Ethernet1/41  │  up   │  ●up  │ 1G    │ ...         │ ...   │ │
│ │ Ethernet1/42  │  up   │  ●up  │ 10G   │ ...         │ ...   │ │
│ └───────────────────────────────────────────────────────────── │ │
│                                                                 │
│ ┌─── 훈련절차 51.05 ─── PHQ_ASN_L3_01 (192.168.254.40) ──────┐ │
│ │ Interface     │ Admin │ Oper  │ Speed │ Description │ Flap  │ │
│ │ Ethernet1/47  │  up   │  ●up  │ 10G   │ ...         │ ...   │ │
│ └───────────────────────────────────────────────────────────── │ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 요약 카드 (상단)

- 3개 카드: 총 포트 수 / Up 수 (녹색) / Down 수 (빨간색)
- 전체 Up → 카드 영역에 "정상" 배지 표시
- 1개 이상 Down → "경고" 배지 + Down 카드 강조

### 4.3 장비별 테이블 카드

- 훈련절차별 카드로 구분
- 카드 헤더: 절차번호 | 장비명 | IP | 접속상태 배지
- 테이블 컬럼: Interface, Admin State, Oper State, Speed, Description, Last Flapped
- Oper State 시각화:
  - `up`: 녹색 원(●) + "up" 텍스트
  - `down`: 빨간색 원(●) + "down" 텍스트 + 행 배경 연빨간색
- 장비 접속 실패 시: 카드에 "접속 불가" 에러 표시

### 4.4 JavaScript (`dr_training.js`)

```javascript
// 주요 함수
function fetchStatus()          // API 호출 및 화면 갱신
function renderSummary(data)    // 상단 요약 카드 업데이트
function renderDeviceCards(data) // 장비별 카드 렌더링
function startAutoRefresh(sec)  // 자동 갱신 시작
function stopAutoRefresh()      // 자동 갱신 정지

// 자동 갱신
let autoRefreshTimer = null;    // setInterval ID
```

## 5. 사이드바 메뉴 추가 (`base.html`)

"네트워크 모니터링" 섹션 내, "멀티캐스트 시세수신체크" 다음에 추가:

```html
<!-- 재해복구훈련 -->
<div class="nav-item-wrapper">
  <a class="nav-link label-1 {% if sub_menu == 'dr_training' %}active{% endif %}" href="/dr_training">
    <div class="d-flex align-items-center">
      <span class="nav-link-icon"><span data-feather="shield"></span></span>
      <span class="nav-link-text">재해복구훈련</span>
    </div>
  </a>
</div>
```

## 6. 환경변수 (`.env`)

```
NXAPI_USERNAME=125003
NXAPI_PASSWORD=Dwr278577@
```

## 7. 파일 목록 및 변경 사항

| 파일 | 유형 | 설명 |
|---|---|---|
| `fastapi/utils/nxapi_client.py` | 신규 | NX-API HTTP 클라이언트 |
| `fastapi/routers/network.py` | 수정 | DR 훈련 상태 API 엔드포인트 추가 |
| `net_admin/app/views.py` | 수정 | dr_training, get_dr_training_status 뷰 추가 |
| `net_admin/app/urls.py` | 수정 | URL 패턴 2개 추가 |
| `net_admin/urls.py` | 수정 | dr_training/ include 추가 |
| `net_admin/templates/dr_training.html` | 신규 | 화면 템플릿 |
| `net_admin/static/assets/js/net_admin/dr_training.js` | 신규 | 프론트엔드 로직 |
| `net_admin/templates/components/base.html` | 수정 | 사이드바 메뉴 추가 |
| `.env` | 수정 | NXAPI 인증 정보 추가 |

## 8. 구현 순서

| 순서 | 작업 | 의존성 |
|---|---|---|
| 1 | `.env` NXAPI 인증 정보 추가 | 없음 |
| 2 | `nxapi_client.py` 작성 | Step 1 |
| 3 | `network.py` API 엔드포인트 추가 | Step 2 |
| 4 | `views.py` Django 뷰 추가 | Step 3 |
| 5 | `urls.py` URL 라우팅 추가 | Step 4 |
| 6 | `dr_training.html` 템플릿 작성 | Step 5 |
| 7 | `dr_training.js` 프론트엔드 작성 | Step 6 |
| 8 | `base.html` 사이드바 메뉴 추가 | Step 6 |
| 9 | 배포 및 테스트 | All |
