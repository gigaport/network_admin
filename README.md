# 네트워크 관리 시스템

금융거래 네트워크 인프라를 위한 종합적인 네트워크 관리 및 모니터링 시스템입니다.

## 프로젝트 개요

이 시스템은 **Django 웹 애플리케이션**과 **FastAPI 서비스**를 분리하여 네트워크 장비를 관리하고 모니터링하는 솔루션입니다. 특히 증권거래 환경의 운영(PR)과 테스트(TS) 환경을 지원합니다.

## 주요 기능

### 🔧 네트워크 장비 관리
- Cisco pyATS/Genie를 활용한 자동화된 장비 상호작용
- IOS-XE 및 NXOS 플랫폼 지원
- YAML 파일을 통한 장비 설정 관리

### 📊 실시간 모니터링
- **멀티캐스트 모니터링**: 금융데이터 배포를 위한 핵심 기능
- **인터페이스 상태 모니터링**: 네트워크 상태 감시
- **ARP/MAC 모니터링**: 장비 연결성 추적
- **대역폭 모니터링**: 거래 네트워크 트래픽 분석

### 🚨 알림 시스템
- Slack 연동을 통한 실시간 알림
- 다양한 외부 시스템 웹훅 지원
- 환경별/알림 유형별 채널 분리

## 시스템 아키텍처

### 분리된 서비스 구조
- **FastAPI 서버** (`fastapi/`): 네트워크 데이터 수집 및 API 엔드포인트 전담
- **Django 웹 애플리케이션** (`net_admin/`): 데이터 시각화 및 관리 인터페이스 전담

### 데이터 수집 파이프라인
1. **수집**: pyATS/Genie를 통한 장비 쿼리
2. **파싱**: Genie 파서로 CLI 출력을 구조화된 JSON으로 변환
3. **처리**: 비즈니스 로직 적용 (멀티캐스트 검증, 인터페이스 모니터링)
4. **저장**: 결과를 `data/` 디렉터리에 JSON 파일로 저장
5. **알림**: 이상 상황 시 Slack 알림

## 설치 및 실행

이 시스템은 **로컬 환경**과 **Docker 컨테이너** 두 가지 방식으로 실행할 수 있습니다.

### 🐳 Docker 컨테이너 실행 (권장)

#### 필수 요구사항
- Docker
- Docker Compose

#### 빠른 시작

1. **프로젝트 클론**
```bash
git clone <repository-url>
cd network_admin
```

2. **환경 변수 설정**
```bash
# .env 파일 생성 및 편집
cp .env.example .env  # .env.example이 있다면
nano .env  # 실제 값으로 수정
```

3. **서비스 시작**
```bash
# 모든 서비스 시작
docker-compose up -d

# 특정 서비스만 시작
docker-compose up -d web fastapi
```

4. **접속 확인**
- Django 웹 인터페이스: http://localhost:8000
- FastAPI API 서비스: http://localhost:8001
- FastAPI 문서: http://localhost:8001/docs

#### 주요 명령어

```bash
# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs
docker-compose logs fastapi  # 특정 서비스 로그

# 서비스 중지
docker-compose down

# 이미지 재빌드
docker-compose build

# 전체 정리 (볼륨 포함)
docker-compose down -v
```

### 💻 로컬 환경 실행

#### 필수 요구사항
- Python 3.8+
- PostgreSQL
- Redis (선택사항)

#### 환경 설정

1. **의존성 설치**
```bash
pip install -r requirements.txt
```

2. **환경 변수 설정**
`.env` 파일을 생성하고 필요한 환경 변수를 설정하세요:
```bash
SLACK_TOKEN=your_slack_token
DB_HOST=localhost
DB_PORT=5432
DB_NAME=nxt_nms_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

3. **데이터베이스 설정**
```bash
cd net_admin
python manage.py migrate
```

### 개발 서버 실행

**Django 개발 서버:**
```bash
cd net_admin
python manage.py runserver 0.0.0.0:8000
```

**FastAPI 서버:**
```bash
cd fastapi
python app.py
# 또는
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

**배치 데이터 수집:**
```bash
./batch.sh
# 또는 수동으로:
cd net_admin
python batch.py
```

## 사용법

### API 엔드포인트

#### 네트워크 데이터 수집
```bash
# Cisco 장비 정보 수집 (운영환경)
GET /api/v1/network/collect/cisco/pr

# Cisco 장비 정보 수집 (테스트환경)
GET /api/v1/network/collect/cisco/ts

# Arista 멀티캐스트 정보 수집
GET /api/v1/network/collect/multicast/arista/pr
```

#### 웹훅 엔드포인트
```bash
# Zabbix 알림
POST /webhook/zabbix

# Grafana 알림
POST /webhook/grafana

# Planka 프로젝트 관리
POST /webhook/planka
```

### 배치 작업

시스템은 자동화된 배치 작업을 통해 정기적으로 네트워크 데이터를 수집합니다:

```bash
# crontab 예시
0 */6 * * * /home/sysmon/network_admin/batch.sh
```

## 디렉터리 구조

```
network_admin/
├── fastapi/                  # FastAPI 애플리케이션
│   ├── app.py               # FastAPI 메인 애플리케이션
│   ├── routers/             # API 라우터
│   ├── utils/               # 네트워크 처리 유틸리티
│   ├── common/              # 공통 설정 및 유틸리티
│   ├── requirements.txt     # FastAPI 의존성
│   └── Dockerfile           # FastAPI 컨테이너 이미지
├── net_admin/               # Django 프로젝트 루트
│   ├── batch.py            # 배치 데이터 수집 스크립트
│   ├── manage.py           # Django 관리 도구
│   ├── net_admin/          # Django 설정
│   ├── templates/          # Django HTML 템플릿
│   ├── static/             # 웹 자산 (CSS, JS)
│   ├── information/        # 정보 관리 앱
│   ├── multicast/          # 멀티캐스트 모니터링 앱
│   └── app/                # 기타 Django 앱
├── data/                   # 생성된 데이터 파일 (JSON)
├── logs/                   # 로그 파일 디렉터리
├── scripts/                # 유틸리티 스크립트
├── postgres_config/        # PostgreSQL 설정
├── genieparser-main/       # Genie 파서 라이브러리
├── docker-compose.yml      # Docker 구성
├── requirements.txt        # 전체 프로젝트 의존성
├── batch.sh               # 배치 실행 스크립트
├── Containerfile          # 컨테이너 이미지 빌드 파일
└── README.md              # 이 파일
```

## 환경별 설정

### 운영 vs 테스트 환경
- `pr` (운영)과 `ts` (테스트) 환경은 별도의 장비 설정을 가집니다
- 시장 구분: "프리" (장전), "정규" (정규장), "에프터" (장후)
- 환경별/알림 유형별로 다른 Slack 채널 사용

### Slack 채널 구성
- `#network-alert-critical`: 심각한 알림
- `#network-alert-endpoint`: 엔드포인트 관련 알림
- `#network-alert-multicast`: 멀티캐스트 관련 알림
- `#network-monitor`: 일반 모니터링 정보

## 문제 해결

### 네트워크 장비 이슈
- YAML 테스트베드 파일에서 장비 연결성 확인
- pyATS 파서와 장비 OS 버전 호환성 검증
- 연결 타임아웃 및 인증 실패 모니터링

### 데이터 수집 문제
- `/home/sysmon/network_admin/batch.log`에서 배치 로그 확인
- FastAPI 서비스 상태 및 엔드포인트 접근 가능성 검증
- `data/` 디렉터리에서 JSON 파일 생성 확인
- pyATS 테스트베드 연결 상태 확인

### 웹 인터페이스 문제
- Django 정적 파일 수집: `python manage.py collectstatic`
- 데이터베이스 연결 및 마이그레이션 확인
- 브라우저 개발자 도구에서 콘솔 오류 모니터링

### 컨테이너 관련 문제
- `docker-compose logs` 명령으로 서비스별 로그 확인
- 포트 충돌 여부 확인 (8000, 8001, 5432 포트)
- 환경 변수 설정 확인 (.env 파일)

## 기여하기

1. 이 저장소를 포크하세요
2. 기능 브랜치를 생성하세요 (`git checkout -b feature/새기능`)
3. 변경사항을 커밋하세요 (`git commit -am '새기능 추가'`)
4. 브랜치에 푸시하세요 (`git push origin feature/새기능`)
5. 풀 리퀘스트를 생성하세요

## 라이선스

이 프로젝트는 내부 사용을 위한 것입니다.

## 연락처

네트워크 관련 문의: network@nextrade.co.kr