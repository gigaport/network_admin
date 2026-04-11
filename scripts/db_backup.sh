#!/bin/bash
#
# 데이터베이스 자동 백업 스크립트
# 사용법: ./db_backup.sh [옵션]
# 옵션:
#   -f : 전체 백업 (schema + data)
#   -d : 데이터만 백업
#   -s : 스키마만 백업
#

set -e

# 설정
DB_NAME="nxt_nms_db"
DB_USER="nextrade"
DB_HOST="localhost"
DB_PORT="5432"
BACKUP_DIR="/home/sysmon/backups/database"
DATE=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=7  # 7일 이상된 백업 자동 삭제

# 비밀번호 설정
export PGPASSWORD='Sprtmxm1@3'

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 전체 백업 (스키마 + 데이터)
full_backup() {
    local backup_file="$BACKUP_DIR/${DB_NAME}_full_${DATE}.sql"

    log "전체 백업 시작..."

    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        --verbose \
        --format=plain \
        --no-owner \
        --no-acl \
        "$DB_NAME" > "$backup_file"

    # 압축
    gzip "$backup_file"
    backup_file="${backup_file}.gz"

    local size=$(du -h "$backup_file" | cut -f1)
    log "✓ 전체 백업 완료: $backup_file ($size)"
}

# 데이터만 백업
data_only_backup() {
    local backup_file="$BACKUP_DIR/${DB_NAME}_data_${DATE}.sql"

    log "데이터 백업 시작..."

    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        --verbose \
        --format=plain \
        --data-only \
        --no-owner \
        --no-acl \
        "$DB_NAME" > "$backup_file"

    # 압축
    gzip "$backup_file"
    backup_file="${backup_file}.gz"

    local size=$(du -h "$backup_file" | cut -f1)
    log "✓ 데이터 백업 완료: $backup_file ($size)"
}

# 스키마만 백업
schema_only_backup() {
    local backup_file="$BACKUP_DIR/${DB_NAME}_schema_${DATE}.sql"

    log "스키마 백업 시작..."

    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        --verbose \
        --format=plain \
        --schema-only \
        --no-owner \
        --no-acl \
        "$DB_NAME" > "$backup_file"

    # 압축
    gzip "$backup_file"
    backup_file="${backup_file}.gz"

    local size=$(du -h "$backup_file" | cut -f1)
    log "✓ 스키마 백업 완료: $backup_file ($size)"
}

# 테이블별 백업 (중요 테이블)
table_backup() {
    local tables=(
        "subscriber_codes"
        "circuit"
        "info_company_circuit"
        "member_fee_schedule"
        "info_fee_schedule"
        "network_cost"
        "purchase_contract"
        "info_purchase_contract"
        "customer_addresses"
    )

    local table_backup_dir="$BACKUP_DIR/tables_${DATE}"
    mkdir -p "$table_backup_dir"

    log "테이블별 백업 시작 (${#tables[@]}개 테이블)..."

    for table in "${tables[@]}"; do
        local backup_file="$table_backup_dir/${table}.sql"

        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
            --table="$table" \
            --format=plain \
            --no-owner \
            --no-acl \
            "$DB_NAME" > "$backup_file"

        gzip "$backup_file"
        log "  ✓ $table 백업 완료"
    done

    # 전체 테이블 백업 디렉토리 압축
    cd "$BACKUP_DIR"
    tar -czf "tables_${DATE}.tar.gz" "tables_${DATE}"
    rm -rf "tables_${DATE}"

    log "✓ 테이블별 백업 완료: tables_${DATE}.tar.gz"
}

# 오래된 백업 삭제
cleanup_old_backups() {
    log "오래된 백업 정리 중 (${RETENTION_DAYS}일 이상)..."

    find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete
    find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete

    log "✓ 정리 완료"
}

# 백업 목록 표시
list_backups() {
    log "백업 목록:"
    ls -lh "$BACKUP_DIR" | tail -n +2
}

# 메인 로직
case "${1:-}" in
    -f|--full)
        full_backup
        cleanup_old_backups
        ;;
    -d|--data)
        data_only_backup
        cleanup_old_backups
        ;;
    -s|--schema)
        schema_only_backup
        cleanup_old_backups
        ;;
    -t|--tables)
        table_backup
        cleanup_old_backups
        ;;
    -l|--list)
        list_backups
        ;;
    *)
        log "=== 데이터베이스 백업 시스템 ==="
        log ""
        log "사용법: $0 [옵션]"
        log ""
        log "옵션:"
        log "  -f, --full    : 전체 백업 (스키마 + 데이터)"
        log "  -d, --data    : 데이터만 백업"
        log "  -s, --schema  : 스키마만 백업"
        log "  -t, --tables  : 테이블별 개별 백업"
        log "  -l, --list    : 백업 목록 표시"
        log ""
        log "기본값: 전체 백업"
        log ""

        # 기본값: 전체 백업
        full_backup
        cleanup_old_backups
        ;;
esac

log "=== 백업 완료 ==="
unset PGPASSWORD
