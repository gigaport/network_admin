# Plan: NetBox 디바이스 연동

## 1. 개요

### 목적
NetBox(v4.3.2) REST API를 활용하여 네트워크 자산(Device) 정보를 MKNM 통합운영시스템에서 조회할 수 있는 화면을 개발한다.

### 배경
- NetBox에 1,165대의 디바이스가 등록되어 있으며, 현재 NetBox 웹 UI에서만 조회 가능
- MKNM 시스템에서 네트워크 자산을 통합 관리할 수 있도록 NetBox API 연동 필요
- 향후 NetBox의 다른 정보(사이트, 랙, IP 등)도 추가 연동 예정 → 확장 가능한 구조 필요

### 범위
| 포함 | 제외 |
|------|------|
| NetBox 디바이스 목록 조회 | NetBox 데이터 생성/수정/삭제 |
| 필터링 (역할, 제조사, 사이트, 상태) | NetBox 인증/권한 관리 |
| 상세정보 팝업 | 실시간 동기화/캐싱 |
| 요약 통계 카드 | NetBox 이외의 자산 관리 |

## 2. NetBox API 분석

### 접속 정보
| 항목 | 값 |
|------|-----|
| URL | `http://172.25.32.221/api/` |
| 인증 | Token `ef1874cea172b931d0b97c603a443377f2c82a23` |
| 버전 | NetBox 4.3.2 |

### 주요 엔드포인트
| API | 설명 | 데이터 수 |
|-----|------|-----------|
| `/api/dcim/devices/` | 디바이스 목록 | 1,165 |
| `/api/dcim/device-roles/` | 디바이스 역할 | DEV(16), DR(115), PRD(893), TST(141) |
| `/api/dcim/manufacturers/` | 제조사 | 51개사 (ARISTA, CISCO, DELL 등) |
| `/api/dcim/sites/` | 사이트(회원사) | 61개소 |
| `/api/dcim/device-types/` | 디바이스 타입(모델) | - |

### 디바이스 응답 주요 필드
```
id, name, status, device_type(model, manufacturer),
role(PRD/TST/DR/DEV), site(회원사), location, rack,
position, serial, primary_ip, description,
tags, custom_fields, interface_count,
created, last_updated
```

## 3. 기능 요구사항

### FR-01: 좌측 메뉴 추가
- "네트워크 자산" 메뉴 그룹 생성 (아이콘: `server`)
- 하위 메뉴: "디바이스" → `/netbox_devices`
- 위치: "네트워크 정보메뉴" 아래, "관리자 메뉴" 위

### FR-02: 요약 통계 카드
- 총 디바이스 수
- 역할별 분포 (PRD / TST / DR / DEV)
- Active / Planned / Offline 상태 분포
- 제조사 Top 5

### FR-03: 디바이스 목록 DataTable
| 컬럼 | 소스 필드 | 비고 |
|------|-----------|------|
| 디바이스명 | `name` | |
| 상태 | `status.label` | 뱃지 표시 (Active=green, Planned=blue, Offline=red) |
| 역할 | `role.name` | PRD/TST/DR/DEV |
| 제조사 | `device_type.manufacturer.name` | |
| 모델 | `device_type.model` | |
| 사이트 | `site.name` | |
| 위치 | `location.name` | |
| 랙 | `rack.name` | |
| Primary IP | `primary_ip.address` | null 가능 |
| 인터페이스 수 | `interface_count` | |
- 컬럼별 검색 필터
- Excel 다운로드 버튼
- 페이지네이션 (서버사이드 → NetBox offset/limit 활용)

### FR-04: 필터 기능
- 역할별 필터 (PRD, TST, DR, DEV)
- 제조사 필터 (상위 제조사 + 기타)
- 사이트 필터
- 상태 필터 (Active, Planned, Offline 등)

### FR-05: 상세보기 팝업
- 행 클릭 시 모달로 상세 정보 표시
- 기본 정보: 이름, 상태, 역할, 시리얼, 설명
- 위치 정보: 사이트, 로케이션, 랙, 포지션
- 네트워크: Primary IP, OOB IP
- 메타: 태그, custom_fields, 등록일, 수정일
- NetBox 바로가기 링크

## 4. 아키텍처

### 데이터 흐름
```
NetBox API (172.25.32.221)
    ↓ HTTP GET (Token Auth)
FastAPI Proxy (/api/v1/network/netbox/devices)
    ↓ JSON
Django View (netbox_devices)
    ↓ Template render
브라우저 (DataTable + JS fetch)
```

### FastAPI 프록시 패턴
- NetBox API 키를 `.env`에 저장 → FastAPI에서 관리
- Django/브라우저에서 직접 NetBox 호출 금지 → FastAPI를 통해 프록시
- 확장성: `/api/v1/network/netbox/{resource}` 패턴으로 향후 사이트, 랙 등 추가 용이

### 변경 파일 목록
| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `.env` | 수정 | NETBOX_URL, NETBOX_TOKEN 추가 |
| `fastapi/routers/network.py` | 수정 | NetBox 프록시 엔드포인트 추가 |
| `net_admin/app/views.py` | 수정 | netbox_devices 뷰 추가 |
| `net_admin/app/urls.py` | 수정 | URL 패턴 추가 |
| `net_admin/net_admin/urls.py` | 수정 | netbox_devices 경로 추가 |
| `net_admin/templates/components/base.html` | 수정 | 좌측 메뉴 추가 |
| `net_admin/templates/netbox_devices.html` | **신규** | 디바이스 목록 템플릿 |
| `net_admin/static/assets/js/net_admin/netbox_devices.js` | **신규** | 디바이스 JS |

## 5. 비기능 요구사항

### 보안
- NetBox API Token은 `.env` 파일에서만 관리 (프론트엔드 노출 금지)
- FastAPI 프록시를 통해서만 접근

### 성능
- NetBox 기본 페이지네이션 활용 (limit/offset)
- DataTables 서버사이드 처리로 1,165건 부담 없이 처리
- API 호출 timeout: 15초

### 확장성
- FastAPI 엔드포인트를 `/netbox/{resource}` 패턴으로 설계
- 향후 sites, racks, ip-addresses 등 동일 패턴으로 추가 가능

## 6. 구현 순서

1. `.env`에 NetBox 접속 정보 추가
2. FastAPI NetBox 프록시 엔드포인트 구현
3. Django 뷰/URL 추가
4. 좌측 메뉴에 "네트워크 자산 > 디바이스" 추가
5. HTML 템플릿 작성 (요약 카드 + DataTable)
6. JS 작성 (데이터 로드, 필터, 상세 팝업)
7. 테스트 및 배포
