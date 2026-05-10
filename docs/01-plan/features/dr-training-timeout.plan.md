# Plan: DR훈련 수집 NX-API 타임아웃 튜닝 및 오탐 제거

## 1. 개요

| 항목 | 내용 |
|---|---|
| Feature | dr-training-timeout |
| 목적 | DR훈련 배치 수집 시 NX-API 일시 타임아웃으로 인한 오탐 알림 근절 및 수집 안정성 향상 |
| 카테고리 | 네트워크 모니터링 > 재해복구훈련 > 백엔드 안정화 |
| 우선순위 | High (운영 중 오탐 알림 발생) |
| 작성일 | 2026-04-24 |
| 관련 Feature | dr-training (상위 기능) |

## 2. 배경 및 필요성

### 2.1 실제 발생 사례 (2026-04-24 06:51)

**증상**: PYD_ASN_L3_01 (172.28.172.29) 장비에 대해 Slack `#network-alert-dr훈련` 채널로 "DR훈련 상태 변경" 알림 발송. 그러나 실제 장비 인터페이스는 내내 정상(up) 상태였음.

**근본 원인**:
1. 06:49:01 수집 배치에서 NX-API 호출이 `Read timed out (timeout=15s)`으로 실패
2. 해당 장비 procedure 51.04(Ethernet1/42) 항목이 `error "접속불가"` 행으로 DB에 저장 (`main_ok=f`, `item_no=1`)
3. 06:50, 06:51 배치에서는 정상 복구되어 interface up 행 저장 (`main_ok=t`)
4. 상태변경 판정 로직(`network.py:5992-5999`)이 `prev2(06:49)=f` vs `current(06:51)=t` 비교로 "Not OK → OK 변경"으로 오탐 → 알림 발송

**임시 조치 완료**: `prev2`가 reachable=False인 경우 상태변경 판정에서 제외하도록 패치 적용 (2026-04-24 13:15 배포).

### 2.2 근본적 문제점

- NX-API 호출 타임아웃이 `15초`로 고정되어 있으며 재시도 로직 없음
- 인터페이스 여러 개가 있는 장비는 **순차 호출**이므로 장비당 최대 `15초 × 인터페이스 수` 소요 가능
- `ThreadPoolExecutor` future timeout이 `30초`라 인터페이스 3개 이상 장비는 future timeout이 먼저 터질 수 있음
- NX-API 순간 타임아웃이 배치 1분 주기 특성상 잦게 발생 → 오탐 유발 원천

### 2.3 운영 영향

- 오탐 알림은 운영자가 즉시 장비 상태를 수동 확인해야 하므로 신뢰도 저하
- 상시 운영 기간(DR훈련 비훈련일)에도 매일 수회 발생 가능성
- 실제 장애를 "또 오탐이겠지" 하며 무시할 위험

## 3. 현재 구조 및 설정값

| 항목 | 파일 | 값 |
|---|---|---|
| NX-API HTTP timeout | `fastapi/utils/nxapi_client.py:12` | 15초 |
| Arista eAPI HTTP timeout | `fastapi/utils/arista_eapi_client.py:16` | 15초 |
| Future 대기 timeout | `fastapi/routers/network.py:5829,5851,5871` | 30초 |
| 재시도 | - | 없음 |
| 인터페이스 조회 방식 | `nxapi_client.py:24` | 순차 (`for intf in interfaces`) |
| 배치 주기 | cron | 1분 |
| 오탐 방지 | `network.py:5970-5999` | 2회 연속 확인 (prev & current 동일 + prev2와 다름) + prev2 reachable 체크 |

## 4. 기능 요구사항

### FR-01: NX-API 조회 효율화 (1건 호출로 다수 인터페이스 수집)
- NX-API `cli_show`에 `show interface <i1> ; show interface <i2>` 배치 커맨드 사용, 또는 `show interface` 전체 결과에서 필터
- 인터페이스 수와 무관하게 장비당 1회 HTTP 호출로 단축
- 실패 시 기존 방식(개별 호출)로 폴백

### FR-02: 재시도 로직 추가
- NX-API 호출 타임아웃/커넥션 오류 시 **1회 자동 재시도** (지수 백오프 1s)
- 재시도도 실패 시에만 `reachable=False` 판정

### FR-03: 타임아웃 파라미터 환경변수화
- `NXAPI_TIMEOUT`, `NXAPI_RETRY_COUNT`, `NXAPI_RETRY_DELAY`를 `.env`에서 조정 가능하도록 분리
- 기본값: timeout=10초, retry=1회, delay=1초 (현재 15초 → 10초로 단축)

### FR-04: Future 대기 timeout 조정
- HTTP timeout × (재시도+1) + 버퍼 기준으로 산정: 10 × 2 + 5 = 25초
- 혹은 장비별 인터페이스 개수 × timeout 기준으로 동적 계산

### FR-05: 오탐 확인 단계 강화 (기 적용, 문서화)
- `prev2 reachable=False` 스냅샷은 상태변경 비교에서 제외 (af8ca22 + 2026-04-24 핫픽스)
- 향후 "3회 연속 확인" 옵션 설정화 검토

### FR-06: 수집 실패 메트릭 기록
- 배치별 NX-API 실패 카운트/타임아웃 시간 DB 저장 (`dr_training_collect_metrics` 테이블 신설 또는 기존 테이블 확장)
- 관리자 화면에서 최근 24시간 실패율 그래프 제공 (후속 Feature 검토)

## 5. 비기능 요구사항

| 항목 | 기준 |
|---|---|
| 수집 성공률 | 95% 이상 (1분 배치, 24시간 평균) |
| 단일 배치 전체 수집 시간 | 30초 이내 |
| 오탐 알림 발생 빈도 | 0건/주 (정상 장비에 대해) |
| Slack 알림 정확도 | 장애 발생 시 2분 이내 발송, 정상 복구 시 즉시 복구 알림 |

## 6. 범위 및 제외

### In Scope
- NX-API 호출 방식 개선 (batch/retry)
- 타임아웃 튜닝 및 환경변수화
- 오탐 방지 로직 점검 및 문서화
- 단위 테스트 추가 (mock NX-API 응답으로 타임아웃/부분실패 시나리오)

### Out of Scope
- DR훈련 화면 UI 변경 없음
- 신규 모니터링 장비 추가 없음
- Arista eAPI는 동일 개선을 별건으로 분리 (PHQ 외 해당 없음, 우선순위 낮음)
- 알림 채널/포맷 변경 없음

## 7. 주요 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| NX-API batch 커맨드 미지원 버전 | 수집 실패 | 응답 파싱 실패 시 개별 호출로 폴백 |
| 재시도로 인한 배치 지연 | cron 다음 주기와 충돌 | future timeout 상한 엄격 관리 |
| 타임아웃 단축으로 정상 장비 오탐 증가 | 알림 폭증 | 배포 전 48시간 수집 성공률 측정 후 튜닝 |
| 장비 펌웨어별 응답 스키마 차이 | 파싱 오류 | 기존 3개 대상 장비 버전 사전 확인 |

## 8. 검증 계획

### 8.1 기능 검증
- 단위 테스트: `tests/test_nxapi_client.py` 신설
  - 정상 응답 / HTTP 타임아웃 / 부분 실패 / 재시도 성공 / 재시도 실패 / batch 폴백 케이스
- 통합 테스트: 실제 3개 대상 장비에 대해 20분간 1분 주기 수집 후 성공률 측정

### 8.2 오탐 검증
- 테스트 DB에 6개 배치 시뮬레이션 데이터 주입 (reachable=f 중간 삽입) 후 알림 발송 여부 확인
- 기대: prev2에 transient error 있어도 알림 비발송

### 8.3 회귀 검증
- DR훈련 화면에서 인터페이스 상태/전환율 표시 변동 없음 확인

## 9. 일정 (예상)

| 작업 | 예상 | 담당 |
|---|---|---|
| Design 작성 | 0.5d | - |
| NX-API batch 호출 구현 | 1d | - |
| 재시도 로직 추가 | 0.5d | - |
| 환경변수화 | 0.5d | - |
| 단위 테스트 | 1d | - |
| 통합 검증 (48시간 관찰) | 2d | - |
| **합계** | **~5.5d** | |

## 10. 관련 파일

- `fastapi/utils/nxapi_client.py` (주요 수정)
- `fastapi/utils/arista_eapi_client.py` (동일 패턴 참고)
- `fastapi/routers/network.py:5605-6081` (DR_TRAINING_TARGETS, collect_dr_training_status)
- `.env` / `.env.example` (환경변수 추가)
- `tests/test_nxapi_client.py` (신규)

## 11. 참고 이력

- 2026-04-24 06:51: 오탐 알림 발생 (PYD_ASN_L3_01)
- 2026-04-24 13:15: 핫픽스 배포 (prev2 reachable=False 스냅샷 제외)
- 이전 이력: af8ca22 "DR훈련 오탐 방지: 2회 연속 확인(confirmation) 도입"
