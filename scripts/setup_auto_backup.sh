#!/bin/bash
#
# 데이터베이스 자동 백업 설정 스크립트
# crontab에 자동 백업 작업 추가
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/db_backup.sh"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 백업 스크립트 실행 권한 부여
chmod +x "$BACKUP_SCRIPT"
chmod +x "$SCRIPT_DIR/db_restore.sh"

log "=== 자동 백업 설정 ==="
log ""

# 현재 crontab 백업
log "현재 crontab 백업 중..."
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || true

# crontab 항목 생성
CRON_ENTRIES="
# 데이터베이스 자동 백업
# 매일 새벽 2시에 전체 백업
0 2 * * * $BACKUP_SCRIPT --full >> /home/sysmon/backups/database/backup.log 2>&1

# 매일 오전 10시, 오후 6시에 데이터만 백업
0 10,18 * * * $BACKUP_SCRIPT --data >> /home/sysmon/backups/database/backup.log 2>&1

# 매주 일요일 오전 3시에 테이블별 백업
0 3 * * 0 $BACKUP_SCRIPT --tables >> /home/sysmon/backups/database/backup.log 2>&1
"

log "crontab 항목:"
echo "$CRON_ENTRIES"
log ""

# 사용자 확인
read -p "위 스케줄로 자동 백업을 설정하시겠습니까? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    log "설정 취소됨"
    exit 0
fi

# crontab에 추가
(crontab -l 2>/dev/null || true; echo "$CRON_ENTRIES") | crontab -

log "✓ 자동 백업 설정 완료"
log ""
log "백업 스케줄:"
log "  - 매일 02:00 : 전체 백업 (스키마 + 데이터)"
log "  - 매일 10:00, 18:00 : 데이터 백업"
log "  - 매주 일요일 03:00 : 테이블별 백업"
log ""
log "백업 위치: /home/sysmon/backups/database/"
log "백업 로그: /home/sysmon/backups/database/backup.log"
log ""
log "현재 crontab:"
crontab -l | grep -A 5 "데이터베이스 자동 백업"
