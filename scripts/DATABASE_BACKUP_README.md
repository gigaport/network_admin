# 데이터베이스 백업/복구 시스템

## 개요

네트워크 관리 시스템의 PostgreSQL 데이터베이스를 안전하게 백업하고 복구하기 위한 자동화 시스템입니다.

## 파일 구조

```
/home/sysmon/network_admin/scripts/
├── db_backup.sh              # 백업 스크립트
├── db_restore.sh             # 복구 스크립트
├── setup_auto_backup.sh      # 자동 백업 설정
└── DATABASE_BACKUP_README.md # 이 문서

/home/sysmon/backups/database/
├── nxt_nms_db_full_YYYYMMDD_HHMMSS.sql.gz    # 전체 백업
├── nxt_nms_db_data_YYYYMMDD_HHMMSS.sql.gz    # 데이터 백업
├── nxt_nms_db_schema_YYYYMMDD_HHMMSS.sql.gz  # 스키마 백업
├── tables_YYYYMMDD_HHMMSS.tar.gz             # 테이블별 백업
└── backup.log                                 # 백업 로그
```

## 백업 종류

### 1. 전체 백업 (Full Backup)
- **내용**: 스키마 + 데이터 전체
- **용도**: 완전한 복구, 재해 복구
- **실행**: `./db_backup.sh --full`

### 2. 데이터 백업 (Data Only)
- **내용**: 데이터만 (테이블 구조 제외)
- **용도**: 데이터 마이그레이션, 일일 백업
- **실행**: `./db_backup.sh --data`

### 3. 스키마 백업 (Schema Only)
- **내용**: 테이블 구조만 (데이터 제외)
- **용도**: 개발/테스트 환경 구축
- **실행**: `./db_backup.sh --schema`

### 4. 테이블별 백업 (Table Backup)
- **내용**: 중요 테이블 개별 백업
- **용도**: 특정 테이블 복구
- **실행**: `./db_backup.sh --tables`

## 사용법

### 백업

```bash
# 전체 백업
./db_backup.sh --full

# 데이터만 백업
./db_backup.sh --data

# 스키마만 백업
./db_backup.sh --schema

# 테이블별 백업
./db_backup.sh --tables

# 백업 목록 확인
./db_backup.sh --list
```

### 복구

```bash
# 백업 목록 확인
./db_restore.sh --list

# 특정 파일에서 복구
./db_restore.sh --full /home/sysmon/backups/database/nxt_nms_db_full_20260407_020000.sql.gz

# 최신 전체 백업에서 자동 복구
./db_restore.sh --auto-full

# 특정 테이블만 복구
./db_restore.sh --table subscriber_codes backup.sql.gz
```

### 자동 백업 설정

```bash
# 자동 백업 cron 설정
./setup_auto_backup.sh
```

**기본 스케줄:**
- 매일 02:00 - 전체 백업
- 매일 10:00, 18:00 - 데이터 백업
- 매주 일요일 03:00 - 테이블별 백업

## 백업 대상 테이블

### 필수 테이블 (자동 백업)
- `subscriber_codes` - 회원사/정보이용사 코드
- `circuit` - 회원사 회선 정보
- `info_company_circuit` - 정보이용사 회선 정보
- `member_fee_schedule` - 회원사 요금표
- `info_fee_schedule` - 정보이용사 요금표
- `network_cost` - 네트워크 원가
- `purchase_contract` - 회원사 매입 계약
- `info_purchase_contract` - 정보이용사 매입 계약
- `customer_addresses` - 고객 주소

## 백업 보관 정책

- **보관 기간**: 30일
- **자동 삭제**: 30일 이상된 백업 자동 삭제
- **압축**: 모든 백업은 gzip으로 압축
- **명명 규칙**: `{DB명}_{타입}_{날짜}_{시간}.sql.gz`

## 복구 시나리오

### 시나리오 1: 전체 데이터베이스 손실
```bash
# 1. 최신 전체 백업 확인
./db_restore.sh --list

# 2. 자동 복구
./db_restore.sh --auto-full
```

### 시나리오 2: 특정 테이블 데이터 손실
```bash
# 1. 테이블별 백업에서 복구
cd /home/sysmon/backups/database
tar -xzf tables_YYYYMMDD_HHMMSS.tar.gz

# 2. 해당 테이블 복구
./db_restore.sh --table subscriber_codes tables_YYYYMMDD_HHMMSS/subscriber_codes.sql.gz
```

### 시나리오 3: 잘못된 데이터 수정 롤백
```bash
# 1. 가장 최근 데이터 백업 찾기
./db_restore.sh --list | grep data

# 2. 해당 백업에서 복구
./db_restore.sh --full nxt_nms_db_data_YYYYMMDD_HHMMSS.sql.gz
```

## 수동 백업 (pg_dump)

### 전체 백업
```bash
export PGPASSWORD='Sprtmxm1@3'
pg_dump -h localhost -U nextrade -d nxt_nms_db \
  --format=plain --no-owner --no-acl \
  | gzip > backup_$(date +%Y%m%d).sql.gz
```

### 특정 테이블만 백업
```bash
export PGPASSWORD='Sprtmxm1@3'
pg_dump -h localhost -U nextrade -d nxt_nms_db \
  --table=subscriber_codes \
  | gzip > subscriber_codes_backup.sql.gz
```

## 수동 복구 (psql)

### 백업에서 복구
```bash
export PGPASSWORD='Sprtmxm1@3'
gunzip -c backup_20260407.sql.gz | \
  psql -h localhost -U nextrade -d nxt_nms_db
```

## 모니터링

### 백업 로그 확인
```bash
tail -f /home/sysmon/backups/database/backup.log
```

### 백업 파일 용량 확인
```bash
du -h /home/sysmon/backups/database/
```

### 최근 백업 확인
```bash
ls -lht /home/sysmon/backups/database/ | head -10
```

## 문제 해결

### Q: 백업이 실행되지 않습니다
```bash
# cron 로그 확인
grep CRON /var/log/syslog | tail -20

# 백업 스크립트 권한 확인
ls -l /home/sysmon/network_admin/scripts/db_backup.sh

# 수동 실행 테스트
/home/sysmon/network_admin/scripts/db_backup.sh --full
```

### Q: 디스크 공간이 부족합니다
```bash
# 오래된 백업 수동 삭제
find /home/sysmon/backups/database -name "*.sql.gz" -mtime +7 -delete

# 백업 디렉토리 정리
rm -f /home/sysmon/backups/database/*_data_*.sql.gz
```

### Q: 복구 후 데이터가 최신이 아닙니다
- 가장 최근 백업 파일을 사용했는지 확인
- 백업 시간을 확인하여 원하는 시점의 백업인지 확인
- 필요시 다른 백업 파일로 재시도

## 주의사항

⚠️ **경고**
- 복구 작업은 기존 데이터를 **완전히 덮어씁니다**
- 복구 전 반드시 현재 상태를 백업하세요
- 프로덕션 환경에서는 복구 전 테스트 환경에서 먼저 검증하세요

## 연락처

문제 발생 시:
1. 백업 로그 확인: `/home/sysmon/backups/database/backup.log`
2. 시스템 로그 확인: `/var/log/syslog`
3. 데이터베이스 로그 확인: `podman logs postgres-db`
