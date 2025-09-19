#!/bin/bash
set -e

echo "Starting batch container..."

# 로그 디렉터리 및 파일 생성
mkdir -p /app/logs
touch /app/logs/batch.log

# cron daemon 시작
echo "Starting cron service..."
service cron start

# cron 상태 확인
service cron status

echo "Cron service started successfully"

# 초기 배치 실행 (테스트용)
echo "Running initial batch test..."
cd /app
python batch.py >> /app/logs/batch.log 2>&1 || echo "Initial batch run failed - this is normal on first run"

echo "Batch container is ready and running..."

# 컨테이너가 종료되지 않도록 무한 대기
while true; do
    sleep 60
    echo "Batch container heartbeat: $(date)"
done