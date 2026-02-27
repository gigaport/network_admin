# 네트워크 관리 시스템 아키텍처 분석 및 개선 방안

## 현재 문제점 분석

### 1. Django 재시작 시간 문제
**현상**: Django 컨테이너 재시작 시 8-10초 이상 소요

**원인**:
```yaml
# docker-compose.yml Line 113-119
command: >
  bash -c "
    cd /app/net_admin &&
    python manage.py migrate &&           # 매번 migration 체크
    python manage.py collectstatic --noinput &&  # 매번 static 파일 수집
    python manage.py runserver 0.0.0.0:8080
  "
```

**문제점**:
- 재시작할 때마다 `migrate`와 `collectstatic` 실행
- Development server (`runserver`) 사용으로 느린 시작 시간
- Volume 마운트된 templates 디렉토리가 있어도 컨테이너 재시작 필요

---

### 2. Nginx 캐시 문제
**현상**: Django 재시작 후 nginx도 재시작 필요

**원인**:
```nginx
# nginx.conf Line 28-34
location / {
    proxy_pass http://django:8080;
    proxy_set_header Host $host;  # localhost:3000 전달
    # 캐시 설정 없음
    # upstream health check 없음
}
```

**문제점**:
- Django 재시작 시 nginx의 upstream connection pool이 끊김
- 캐시 무효화 메커니즘 없음
- Health check 없어서 Django가 준비되지 않았을 때 502 에러 발생
- `proxy_set_header Host $host`가 `localhost:3000`을 전달하여 Django ALLOWED_HOSTS 검증 실패 가능

---

### 3. 컨테이너 연계 불안정성
**현상**: 컨테이너 재시작 순서에 따라 연결 실패

**원인**:
```yaml
# depends_on만 있고 health check 없음
depends_on:
  - django
  - fastapi
```

**문제점**:
- `depends_on`은 컨테이너 시작 순서만 보장, 서비스 준비 상태는 보장 안 함
- Django가 준비되기 전에 nginx가 요청을 보낼 수 있음
- Health check가 없어 서비스 장애 감지 불가

---

### 4. 볼륨 마운트 불일치
**현상**: 코드 변경 시 컨테이너 재시작 필요

**원인**:
```yaml
django:
  volumes:
    - ./net_admin/static:/app/net_admin/static:Z
    - ./net_admin/staticfiles:/app/net_admin/staticfiles:Z
    - ./net_admin/templates:/app/net_admin/templates:Z
    # 하지만 코드 파일들(views.py, urls.py, models.py)은 마운트 안 됨!
```

**문제점**:
- Python 코드는 이미지에 빌드되어 있어서 변경 시 재빌드 또는 수동 복사 필요
- templates만 마운트되어 있어도 Python 코드 로드 문제로 재시작 필요

---

## 개선 방안

### 방안 1: Gunicorn + Nginx 최적화 (추천)

#### A. Django를 Gunicorn으로 변경
```yaml
django:
  command: >
    bash -c "
      cd /app/net_admin &&
      python manage.py collectstatic --noinput || true &&
      gunicorn net_admin.wsgi:application
        --bind 0.0.0.0:8080
        --workers 4
        --timeout 120
        --access-logfile -
        --error-logfile -
    "
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 30s
```

**장점**:
- Production-ready WSGI server
- 빠른 시작 시간 (2-3초)
- Worker 프로세스로 안정성 향상
- Health check로 준비 상태 확인

#### B. Nginx 설정 개선
```nginx
upstream django_backend {
    server django:8080 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 80;
    server_name net_admin.local;

    # 캐시 설정
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=django_cache:10m max_size=100m;

    # Django static files - 직접 서빙 (캐시)
    location /static/ {
        alias /app/staticfiles/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }

    # Django 애플리케이션 - 프록시
    location / {
        proxy_pass http://django_backend;

        # Host 헤더를 원본 유지 대신 실제 백엔드 주소로
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Connection 유지
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        # Timeout 설정
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # 버퍼 설정
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;

        # Django 재시작 시 자동 재시도
        proxy_next_upstream error timeout http_502 http_503;
        proxy_next_upstream_tries 3;
    }
}
```

**장점**:
- Upstream으로 connection pool 관리
- Health check 통합
- 캐시로 성능 향상
- Django 재시작 시 자동 재연결

---

### 방안 2: 개발 환경 볼륨 마운트 추가

```yaml
django:
  volumes:
    # 기존 볼륨
    - ./net_admin/static:/app/net_admin/static:Z
    - ./net_admin/staticfiles:/app/net_admin/staticfiles:Z
    - ./net_admin/templates:/app/net_admin/templates:Z

    # 추가: Python 코드 마운트 (개발 환경)
    - ./net_admin/information:/app/net_admin/information:Z
    - ./net_admin/multicast:/app/net_admin/multicast:Z
    - ./net_admin/app:/app/net_admin/app:Z
    - ./net_admin/net_admin:/app/net_admin/net_admin:Z
```

**장점**:
- 코드 변경 시 자동 리로드 (runserver 사용 시)
- 컨테이너 재시작 불필요

**단점**:
- Production 환경에서는 사용 불가
- 성능 저하 가능성

---

### 방안 3: Health Check 추가

```yaml
services:
  postgres-db:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nextrade"]
      interval: 10s
      timeout: 5s
      retries: 5

  fastapi:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    depends_on:
      postgres-db:
        condition: service_healthy

  django:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    depends_on:
      postgres-db:
        condition: service_healthy

  nginx:
    depends_on:
      django:
        condition: service_healthy
      fastapi:
        condition: service_healthy
```

**장점**:
- 서비스 준비 상태 보장
- 자동 장애 감지 및 재시작
- 의존성 순서 정확히 관리

---

### 방안 4: Django 시작 스크립트 최적화

```bash
#!/bin/bash
# entrypoint.sh

cd /app/net_admin

# Migration은 초기화 시에만 (파일 존재 확인)
if [ ! -f "/tmp/.migrations_done" ]; then
    echo "Running migrations..."
    python manage.py migrate
    touch /tmp/.migrations_done
fi

# Static files 수집 (변경 감지)
python manage.py collectstatic --noinput --clear

# Gunicorn 시작
exec gunicorn net_admin.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
```

```yaml
django:
  command: ["/app/entrypoint.sh"]
  volumes:
    - django_migrations:/tmp  # Migration 상태 유지
```

---

## 즉시 적용 가능한 개선안 (우선순위)

### 1단계: Nginx 설정 개선 (1시간)
- upstream 추가
- connection keepalive
- proxy_next_upstream 설정
- 캐시 설정

### 2단계: Health Check 추가 (30분)
- 모든 서비스에 healthcheck 추가
- depends_on condition 추가

### 3단계: Gunicorn 적용 (1시간)
- Dockerfile에 gunicorn 추가
- command 변경
- 성능 테스트

### 4단계: 시작 스크립트 최적화 (30분)
- entrypoint.sh 생성
- migration 최적화

---

## 예상 효과

| 항목 | 현재 | 개선 후 |
|------|------|---------|
| Django 재시작 시간 | 8-10초 | 2-3초 |
| Nginx 재시작 필요 | 필요 | 불필요 |
| 502 에러 발생 | 자주 발생 | 거의 없음 |
| 코드 변경 반영 | 컨테이너 재시작 | 자동 (개발 시) |
| 시스템 안정성 | 보통 | 높음 |

---

## 결론

현재 시스템의 주요 문제는:
1. **Development server 사용** → Gunicorn으로 변경
2. **Health check 부재** → Health check 추가
3. **Nginx upstream 미사용** → Upstream + keepalive 설정
4. **매번 migration 실행** → 조건부 실행

이 개선안들을 단계적으로 적용하면 안정적이고 빠른 개발/운영 환경 구축 가능합니다.
