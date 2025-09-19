# Network Admin API 사용 예제

## 기본 정보
- **Base URL**: `http://your-server:8000`
- **Content-Type**: `application/json`

## 헬스체크
```bash
curl -X GET "http://your-server:8000/health"
```

## 웹훅 엔드포인트

### 1. Zabbix 웹훅
**URL**: `POST /api/v1/webhook/zabbix`

**요청 예제**:
```bash
curl -X POST "http://your-server:8000/api/v1/webhook/zabbix" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "switch-01",
    "event_name": "Interface Down",
    "event_value": "1",
    "severity": "High",
    "host_group": "Network Switches",
    "event_date": "2024-01-15",
    "event_time": "10:30:00",
    "opdata": "Interface GigabitEthernet0/1 is down",
    "event_duration": "00:05:30"
  }'
```

**응답 예제**:
```json
{
  "result": true,
  "response": {
    "code": 200,
    "message": "[OK]send to message."
  }
}
```

### 2. Syslog 웹훅
**URL**: `POST /api/v1/webhook/syslog`

**요청 예제**:
```bash
curl -X POST "http://your-server:8000/api/v1/webhook/syslog" \
  -H "Content-Type: application/json" \
  -d '{
    "device": "router-01",
    "host_ip": "192.168.1.1",
    "timestamp_trans": "2024-01-15 10:30:00",
    "severity": "warning",
    "facility": "L2FM",
    "mnemonic": "IF_DOWN",
    "type": "interface",
    "message": "Interface GigabitEthernet0/1 is down"
  }'
```

### 3. Planka 웹훅
**URL**: `POST /api/v1/webhook/planka`

**요청 예제**:
```bash
curl -X POST "http://your-server:8000/api/v1/webhook/planka" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "cardCreate",
    "user": {
      "name": "John Doe"
    },
    "data": {
      "item": {
        "name": "새로운 작업",
        "description": "작업 설명",
        "dueDate": "2024-01-20"
      },
      "included": {
        "projects": [{"name": "네트워크"}],
        "lists": [{"name": "진행중"}],
        "boards": [{"name": "네트워크 관리"}],
        "cards": [{"name": "관련 카드"}]
      }
    }
  }'
```

## 에러 응답 형식

### 400 Bad Request (잘못된 요청)
```json
{
  "result": false,
  "error": "Missing required fields",
  "detail": "Required fields missing: ['hostname', 'event_name']"
}
```

### 500 Internal Server Error (서버 오류)
```json
{
  "result": false,
  "error": "Internal server error",
  "detail": "Error message here"
}
```

## 필수 필드

### Zabbix 웹훅
- `hostname`: 장비명
- `event_name`: 이벤트명
- `event_value`: 이벤트 값 (0: 해결, 1: 발생)
- `severity`: 심각도
- `host_group`: 호스트 그룹
- `event_date`: 이벤트 날짜
- `event_time`: 이벤트 시간
- `opdata`: 현재 상태

### Syslog 웹훅
- `device`: 장비명
- `host_ip`: 장비 IP
- `timestamp_trans`: 타임스탬프
- `severity`: 심각도
- `facility`: 시설
- `mnemonic`: 니모닉
- `type`: 타입
- `message`: 메시지

## 채널 매핑

### Zabbix
- 기본: `network-alert-critical`
- 회원사 스위치 (mpr, ord, com 포함): `network-alert-endpoint`

### Syslog
- 기본: `#network-alert-syslog`
- 일반 로그: `#network-alert-normal`
- 엔드포인트 로그: `#network-alert-endpoint`

## 테스트 방법

1. **헬스체크 테스트**:
```bash
curl -X GET "http://localhost:8000/health"
```

2. **Zabbix 웹훅 테스트**:
```bash
curl -X POST "http://localhost:8000/api/v1/webhook/zabbix" \
  -H "Content-Type: application/json" \
  -d '{"hostname":"test","event_name":"test","event_value":"1","severity":"High","host_group":"test","event_date":"2024-01-15","event_time":"10:30:00","opdata":"test"}'
```

3. **API 문서 확인**:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
