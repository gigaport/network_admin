#!/usr/bin/env python3
"""
시세정보 데이터베이스 정규화 마이그레이션 스크립트
기존 sise_info_detail 테이블을 sise_products와 sise_channels로 분리
"""
import psycopg2
from psycopg2 import sql
import os
import sys

# 데이터베이스 연결 정보
DB_CONFIG = {
    'dbname': os.environ.get('POSTGRES_DB', 'nxt_nms_db'),
    'user': os.environ.get('POSTGRES_USER', 'nextrade'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'Sprtmxm1@3'),
    'host': os.environ.get('POSTGRES_HOST', 'postgres-db'),
    'port': os.environ.get('POSTGRES_PORT', '5432')
}

def create_new_tables(conn):
    """새로운 정규화된 테이블 생성"""
    create_tables_sql = """
    -- 1. 상품 마스터 테이블
    CREATE TABLE IF NOT EXISTS sise_products (
        id SERIAL PRIMARY KEY,
        product_name VARCHAR(50) NOT NULL UNIQUE,
        line_speed VARCHAR(20),
        data_format VARCHAR(20),
        operation_ip1 VARCHAR(20),
        operation_ip2 VARCHAR(20),
        test_ip VARCHAR(20),
        dr_ip VARCHAR(20),
        retransmit_port VARCHAR(10),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 2. 채널 정보 테이블
    CREATE TABLE IF NOT EXISTS sise_channels (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES sise_products(id) ON DELETE CASCADE,
        service_type VARCHAR(50),
        market_type VARCHAR(20),
        multicast_group_ip VARCHAR(20),
        operation_port VARCHAR(10),
        test_port VARCHAR(10),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id, service_type, market_type)
    );

    -- 인덱스 생성
    CREATE INDEX IF NOT EXISTS idx_product_name ON sise_products(product_name);
    CREATE INDEX IF NOT EXISTS idx_channel_product ON sise_channels(product_id);
    CREATE INDEX IF NOT EXISTS idx_channel_service ON sise_channels(service_type);
    CREATE INDEX IF NOT EXISTS idx_channel_market ON sise_channels(market_type);
    """

    with conn.cursor() as cur:
        cur.execute(create_tables_sql)
        conn.commit()
    print("✓ 새 테이블 생성 완료")

def migrate_data(conn):
    """기존 데이터를 새 테이블로 마이그레이션"""

    with conn.cursor() as cur:
        # 1. sise_products 테이블에 고유 상품 데이터 삽입
        print("\n1단계: 상품 마스터 데이터 마이그레이션...")
        migrate_products_sql = """
        INSERT INTO sise_products (
            product_name, line_speed, data_format,
            operation_ip1, operation_ip2, test_ip, dr_ip, retransmit_port
        )
        SELECT DISTINCT
            product_name,
            line_speed,
            data_format,
            operation_ip1,
            operation_ip2,
            test_ip,
            dr_ip,
            retransmit_port
        FROM sise_info_detail
        ORDER BY product_name
        ON CONFLICT (product_name) DO NOTHING;
        """
        cur.execute(migrate_products_sql)
        product_count = cur.rowcount
        conn.commit()
        print(f"✓ {product_count}개 상품 마이그레이션 완료")

        # 2. sise_channels 테이블에 채널 데이터 삽입
        print("\n2단계: 채널 정보 마이그레이션...")
        migrate_channels_sql = """
        INSERT INTO sise_channels (
            product_id, service_type, market_type,
            multicast_group_ip, operation_port, test_port
        )
        SELECT
            p.id,
            d.service_type,
            d.market_type,
            d.multicast_group_ip,
            d.operation_port,
            d.test_port
        FROM sise_info_detail d
        INNER JOIN sise_products p ON d.product_name = p.product_name
        ORDER BY p.id, d.service_type, d.market_type
        ON CONFLICT (product_id, service_type, market_type) DO NOTHING;
        """
        cur.execute(migrate_channels_sql)
        channel_count = cur.rowcount
        conn.commit()
        print(f"✓ {channel_count}개 채널 마이그레이션 완료")

def verify_migration(conn):
    """마이그레이션 결과 검증"""
    print("\n=== 마이그레이션 검증 ===")

    with conn.cursor() as cur:
        # 1. 레코드 수 확인
        cur.execute("SELECT COUNT(*) FROM sise_info_detail")
        old_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sise_products")
        product_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sise_channels")
        channel_count = cur.fetchone()[0]

        print(f"기존 테이블 레코드: {old_count}개")
        print(f"상품 마스터: {product_count}개")
        print(f"채널 정보: {channel_count}개")

        # 2. 외래키 무결성 검증
        cur.execute("""
            SELECT COUNT(*)
            FROM sise_channels c
            LEFT JOIN sise_products p ON c.product_id = p.id
            WHERE p.id IS NULL
        """)
        orphan_count = cur.fetchone()[0]

        if orphan_count == 0:
            print("✓ 외래키 무결성: 정상")
        else:
            print(f"✗ 외래키 무결성: {orphan_count}개 orphan 레코드 발견")

        # 3. 샘플 데이터 조회 (JOIN 테스트)
        print("\n=== 샘플 데이터 (상품별 채널 수) ===")
        cur.execute("""
            SELECT
                p.product_name,
                p.line_speed,
                COUNT(c.id) as channel_count
            FROM sise_products p
            LEFT JOIN sise_channels c ON p.id = c.product_id
            GROUP BY p.id, p.product_name, p.line_speed
            ORDER BY p.product_name
            LIMIT 5
        """)

        for row in cur.fetchall():
            print(f"  {row[0]:<15} {row[1]:<10} {row[2]}개 채널")

        # 4. 데이터 일치성 검증
        print("\n=== 데이터 일치성 검증 ===")
        cur.execute("""
            SELECT
                p.product_name,
                c.service_type,
                c.market_type,
                c.multicast_group_ip,
                d.multicast_group_ip as old_multicast_ip
            FROM sise_channels c
            JOIN sise_products p ON c.product_id = p.id
            JOIN sise_info_detail d ON
                p.product_name = d.product_name AND
                c.service_type = d.service_type AND
                c.market_type = d.market_type
            WHERE c.multicast_group_ip != d.multicast_group_ip
        """)

        mismatch = cur.fetchall()
        if len(mismatch) == 0:
            print("✓ 데이터 일치성: 정상 (모든 데이터가 일치함)")
        else:
            print(f"✗ 데이터 불일치: {len(mismatch)}건 발견")
            for row in mismatch:
                print(f"  {row[0]} - {row[1]} - {row[2]}: {row[3]} vs {row[4]}")

def backup_old_table(conn):
    """기존 테이블 백업"""
    print("\n=== 기존 테이블 백업 ===")

    with conn.cursor() as cur:
        # 백업 테이블이 이미 존재하는지 확인
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = 'sise_info_detail_backup'
        """)

        if cur.fetchone()[0] > 0:
            print("기존 백업 테이블 삭제 중...")
            cur.execute("DROP TABLE sise_info_detail_backup")

        # 테이블 이름 변경
        cur.execute("ALTER TABLE sise_info_detail RENAME TO sise_info_detail_backup")
        conn.commit()
        print("✓ sise_info_detail → sise_info_detail_backup으로 이름 변경 완료")

def main():
    try:
        # 데이터베이스 연결
        print(f"데이터베이스 연결 중... ({DB_CONFIG['host']}:{DB_CONFIG['port']})")
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ 데이터베이스 연결 성공\n")

        # 1. 새 테이블 생성
        create_new_tables(conn)

        # 2. 데이터 마이그레이션
        migrate_data(conn)

        # 3. 검증
        verify_migration(conn)

        # 4. 기존 테이블 백업
        backup_old_table(conn)

        conn.close()
        print("\n✅ 데이터베이스 정규화 완료!")
        print("\n다음 단계: import_sise_info.py 스크립트를 새 구조에 맞게 업데이트하세요.")

    except psycopg2.Error as e:
        print(f"✗ 데이터베이스 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
