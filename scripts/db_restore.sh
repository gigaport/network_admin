#!/bin/bash
#
# 데이터베이스 복구 스크립트
# 사용법: ./db_restore.sh [백업파일]
#

set -e

# 설정
DB_NAME="nxt_nms_db"
DB_USER="nextrade"
DB_HOST="localhost"
DB_PORT="5432"
BACKUP_DIR="/home/sysmon/backups/database"

# 비밀번호 설정
export PGPASSWORD='Sprtmxm1@3'

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 에러 함수
error() {
    echo "[ERROR] $1" >&2
    exit 1
}

# 복구 전 확인
confirm_restore() {
    log "⚠️  경고: 데이터베이스 복구는 기존 데이터를 덮어씁니다!"
    read -p "계속하시겠습니까? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log "복구 취소됨"
        exit 0
    fi
}

# 백업 파일 복구
restore_from_file() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        error "백업 파일을 찾을 수 없습니다: $backup_file"
    fi

    log "백업 파일: $backup_file"

    # 압축 여부 확인
    if [[ "$backup_file" == *.gz ]]; then
        log "압축 해제 중..."
        local temp_file="/tmp/restore_${RANDOM}.sql"
        gunzip -c "$backup_file" > "$temp_file"
        backup_file="$temp_file"
    fi

    confirm_restore

    log "데이터베이스 복구 시작..."

    # 복구 실행
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$backup_file"

    # 임시 파일 삭제
    if [ -n "${temp_file:-}" ] && [ -f "$temp_file" ]; then
        rm -f "$temp_file"
    fi

    log "✓ 복구 완료"
}

# 최신 백업 파일 찾기
find_latest_backup() {
    local pattern="$1"
    local latest=$(ls -t "$BACKUP_DIR"/${DB_NAME}_${pattern}_*.sql.gz 2>/dev/null | head -1)

    if [ -z "$latest" ]; then
        error "${pattern} 백업 파일을 찾을 수 없습니다."
    fi

    echo "$latest"
}

# 백업 목록 표시
list_backups() {
    log "사용 가능한 백업 파일:"
    echo ""
    ls -lht "$BACKUP_DIR" | grep -E '\.sql\.gz|\.tar\.gz' | head -20
}

# 특정 테이블만 복구
restore_table() {
    local table_name="$1"
    local backup_file="$2"

    if [ ! -f "$backup_file" ]; then
        error "백업 파일을 찾을 수 없습니다: $backup_file"
    fi

    log "테이블 복구: $table_name"

    # 압축 해제
    if [[ "$backup_file" == *.gz ]]; then
        local temp_file="/tmp/restore_${table_name}_${RANDOM}.sql"
        gunzip -c "$backup_file" > "$temp_file"
        backup_file="$temp_file"
    fi

    confirm_restore

    # 기존 테이블 데이터 삭제 (선택사항)
    log "기존 $table_name 테이블 데이터 삭제 중..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "TRUNCATE TABLE $table_name CASCADE;"

    # 복구 실행
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$backup_file"

    # 임시 파일 삭제
    if [ -n "${temp_file:-}" ] && [ -f "$temp_file" ]; then
        rm -f "$temp_file"
    fi

    log "✓ $table_name 테이블 복구 완료"
}

# 메인 로직
if [ $# -eq 0 ]; then
    log "=== 데이터베이스 복구 시스템 ==="
    log ""
    log "사용법: $0 [옵션] [백업파일]"
    log ""
    log "옵션:"
    log "  -l, --list              : 백업 목록 표시"
    log "  -f, --full [파일]       : 전체 백업에서 복구"
    log "  -a, --auto-full         : 최신 전체 백업 자동 복구"
    log "  -t, --table [테이블] [파일] : 특정 테이블만 복구"
    log ""
    log "예제:"
    log "  $0 -l                                    # 백업 목록 표시"
    log "  $0 -f /path/to/backup.sql.gz             # 파일에서 복구"
    log "  $0 -a                                    # 최신 백업 자동 복구"
    log "  $0 -t subscriber_codes backup.sql.gz     # 특정 테이블만 복구"
    log ""
    exit 0
fi

case "$1" in
    -l|--list)
        list_backups
        ;;
    -f|--full)
        if [ -z "${2:-}" ]; then
            error "백업 파일을 지정해주세요."
        fi
        restore_from_file "$2"
        ;;
    -a|--auto-full)
        latest=$(find_latest_backup "full")
        log "최신 백업 파일: $latest"
        restore_from_file "$latest"
        ;;
    -t|--table)
        if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
            error "테이블명과 백업 파일을 지정해주세요."
        fi
        restore_table "$2" "$3"
        ;;
    *)
        # 파일명을 직접 입력한 경우
        restore_from_file "$1"
        ;;
esac

log "=== 복구 완료 ==="
unset PGPASSWORD
