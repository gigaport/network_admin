# Plan: 재해복구훈련 (DR Training) 인터페이스 모니터링

## 1. 개요

| 항목 | 내용 |
|---|---|
| Feature | dr-training |
| 목적 | 재해복구훈련 시 지정된 스위치의 특정 인터페이스 상태를 실시간으로 확인하는 전용 화면 개발 |
| 카테고리 | 네트워크 모니터링 > 재해복구훈련 (신규 메뉴) |
| 우선순위 | High |
| 작성일 | 2026-04-11 |

## 2. 배경 및 필요성

- 재해복구(DR) 훈련 시 특정 스위치의 인터페이스 상태(Up/Down)를 수동 CLI 접속 없이 웹에서 즉시 확인 필요
- Cisco NX-API를 통한 실시간 인터페이스 상태 조회가 서버에서 가능함을 확인 완료 (172.28.172.29 테스트 성공)
- 훈련 절차별 모니터링 대상이 명확하게 정의되어 있어 전용 화면이 효율적

## 3. 모니터링 대상

| 훈련절차 | 장비명 | IP | 모니터링 인터페이스 |
|---|---|---|---|
| 51.01 | RBD_ASN_L3_01 | 172.30.172.13 | Ethernet1/41, Ethernet1/48 |
| 51.04 | PYD_ASN_L3_01 | 172.28.172.29 | Ethernet1/41, Ethernet1/42 |
| 51.05 | PHQ_ASN_L3_01 | 192.168.254.40 | Ethernet1/47 |

- 인증 정보: NX-API 계정 (username/password) - 환경변수로 관리
- 프로토콜: HTTP NX-API (JSON-RPC, Port 80)

## 4. 기능 요구사항

### FR-01: 재해복구훈련 메뉴
- 사이드바 "네트워크 모니터링" 섹션에 "재해복구훈련" 메뉴 추가
- URL: `/dr_training`

### FR-02: 훈련 대상 장비 현황 카드
- 훈련절차별로 카드 형태로 장비 정보 표시
- 각 카드에 절차번호, 장비명, IP, 대상 인터페이스 목록 표시

### FR-03: 인터페이스 실시간 상태 조회
- NX-API `show interface <intf>` 명령으로 상태 조회
- 표시 항목: 인터페이스명, Admin Status, Oper Status, Speed, Last Link Flapped, Description
- 상태에 따른 시각적 표시 (Up: 녹색, Down: 빨간색)

### FR-04: 상태 새로고침
- 수동 새로고침 버튼
- 자동 갱신 옵션 (10초/30초/60초 선택)

### FR-05: 전체 상태 요약
- 상단에 전체 인터페이스 Up/Down 수 요약
- 모든 포트 Up 시 "정상" 표시, 하나라도 Down 시 "경고" 표시

## 5. 기술 스택

| 구분 | 기술 |
|---|---|
| Backend API | FastAPI - NX-API 프록시 엔드포인트 |
| Frontend | Django 템플릿 + JavaScript (기존 패턴) |
| NX-API 통신 | Python requests, HTTP (Port 80), JSON-RPC |
| 인증 관리 | .env 파일 (NXAPI_USERNAME, NXAPI_PASSWORD) |

## 6. 아키텍처

```
[브라우저] → [Django View] → [FastAPI /api/v1/network/dr-training/status]
                                        ↓
                              [NX-API HTTP 호출 (Port 80)]
                                        ↓
                    ┌─────────────────────────────────────┐
                    │ RBD_ASN_L3_01 (172.30.172.13)       │
                    │ PYD_ASN_L3_01 (172.28.172.29)       │
                    │ PHQ_ASN_L3_01 (192.168.254.40)      │
                    └─────────────────────────────────────┘
```

## 7. 구현 범위

### Backend (FastAPI)
- `fastapi/routers/network.py`에 DR 훈련 상태 조회 엔드포인트 추가
- NX-API 호출 유틸 함수 (`fastapi/utils/nxapi_client.py` 신규)
- 훈련 대상 장비/인터페이스 설정 (코드 내 상수 또는 설정 파일)

### Frontend (Django)
- 템플릿: `net_admin/templates/dr_training.html` (신규)
- JavaScript: `net_admin/static/assets/js/net_admin/dr_training.js` (신규)
- 사이드바 메뉴: `components/base.html` 수정
- URL: `net_admin/urls.py`, `net_admin/app/urls.py`, `net_admin/app/views.py` 수정

### 설정
- `.env`에 NX-API 인증 정보 추가

## 8. 구현 순서

1. `.env`에 NX-API 인증 정보 추가
2. `fastapi/utils/nxapi_client.py` - NX-API 클라이언트 유틸 작성
3. `fastapi/routers/network.py` - DR 훈련 상태 조회 API 엔드포인트 추가
4. `net_admin/templates/dr_training.html` - 화면 템플릿 작성
5. `net_admin/static/assets/js/net_admin/dr_training.js` - 프론트엔드 로직
6. `components/base.html` - 사이드바 메뉴 추가
7. `app/urls.py`, `app/views.py`, `net_admin/urls.py` - URL 라우팅 추가
8. 배포 및 테스트

## 9. 제약사항 및 리스크

| 리스크 | 대응 |
|---|---|
| NX-API 응답 지연 | 타임아웃 설정 (5초), 장비별 병렬 조회 |
| 스위치 접근 불가 | 오류 메시지 표시, 개별 장비 실패 허용 |
| 인증 정보 보안 | .env 파일로 관리, 코드에 하드코딩 금지 |
| 네트워크 방화벽 | 서버→스위치 80 포트 사전 확인 필요 (172.30.172.13, 192.168.254.40) |
