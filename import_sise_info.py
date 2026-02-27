#!/usr/bin/env python3
"""
시세정보 상품 데이터를 Excel에서 PostgreSQL로 import하는 스크립트
정규화된 테이블 구조 (sise_products + sise_channels)로 import
"""
import pandas as pd
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

# Excel 파일 경로
EXCEL_FILE = '/home/sysmon/data/정보상품_IP_PORT_확인_ETF상품추가_20251226.xlsx'

def create_tables(conn):
    """정규화된 테이블 생성 (sise_products, sise_channels)"""
    create_table_sql = """
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
        cur.execute(create_table_sql)
        conn.commit()
    print("✓ 테이블 생성 완료")

def load_excel_data(file_path):
    """Excel 파일에서 데이터 로드 및 정제"""
    df = pd.read_excel(file_path)

    # 헤더 행 찾기 (1행: "정보상품", "회선", ... 행)
    header_row = 1
    data_start_row = 4  # 실제 데이터 시작 행

    # 컬럼명 매핑
    columns = {
        '□ 전용선(UDP) 상품별 채널 구성': 'product_name',
        'Unnamed: 1': 'line_speed',
        'Unnamed: 2': 'data_format',
        'Unnamed: 3': 'service_type',
        'Unnamed: 4': 'multicast_group_ip',
        'Unnamed: 5': 'operation_port',
        'Unnamed: 6': 'test_port',
        'Unnamed: 7': 'retransmit_port',
        'Unnamed: 8': 'market_type',
        'Unnamed: 9': 'operation_ip1',
        'Unnamed: 10': 'operation_ip2',
        'Unnamed: 11': 'test_ip',
        'Unnamed: 12': 'dr_ip'
    }

    # 데이터 행만 추출 (4행부터)
    data_df = df.iloc[data_start_row:].copy()

    # 컬럼명 변경
    data_df.columns = [columns.get(col, col) for col in df.columns]

    # NaN 값 처리
    data_df = data_df.fillna('')

    # 빈 행 제거 (product_name이 비어있는 행)
    data_df = data_df[data_df['product_name'].str.strip() != '']

    print(f"✓ Excel 파일 로드 완료: {len(data_df)}개 행")
    return data_df

def insert_products(conn, df):
    """상품 마스터 데이터 삽입"""
    # 고유한 상품 데이터 추출
    products_df = df[['product_name', 'line_speed', 'data_format',
                      'operation_ip1', 'operation_ip2', 'test_ip', 'dr_ip',
                      'retransmit_port']].drop_duplicates()

    insert_sql = """
    INSERT INTO sise_products (
        product_name, line_speed, data_format,
        operation_ip1, operation_ip2, test_ip, dr_ip, retransmit_port
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (product_name)
    DO UPDATE SET
        line_speed = EXCLUDED.line_speed,
        data_format = EXCLUDED.data_format,
        operation_ip1 = EXCLUDED.operation_ip1,
        operation_ip2 = EXCLUDED.operation_ip2,
        test_ip = EXCLUDED.test_ip,
        dr_ip = EXCLUDED.dr_ip,
        retransmit_port = EXCLUDED.retransmit_port,
        updated_at = CURRENT_TIMESTAMP
    """

    with conn.cursor() as cur:
        # 기존 채널 데이터 삭제 (CASCADE로 자동 삭제됨)
        cur.execute("TRUNCATE TABLE sise_products RESTART IDENTITY CASCADE")
        print("✓ 기존 데이터 삭제 완료")

        # 새 상품 데이터 삽입
        inserted_count = 0
        for idx, row in products_df.iterrows():
            try:
                cur.execute(insert_sql, (
                    row['product_name'],
                    row['line_speed'],
                    row['data_format'],
                    row['operation_ip1'],
                    row['operation_ip2'],
                    row['test_ip'],
                    row['dr_ip'],
                    row['retransmit_port']
                ))
                inserted_count += 1
            except Exception as e:
                print(f"✗ 상품 데이터 삽입 실패 (행 {idx}): {e}")
                print(f"  데이터: {row.to_dict()}")

        conn.commit()
        print(f"✓ 상품 데이터 삽입 완료: {inserted_count}개 상품")
        return inserted_count

def insert_channels(conn, df):
    """채널 정보 데이터 삽입"""
    insert_sql = """
    INSERT INTO sise_channels (
        product_id, service_type, market_type,
        multicast_group_ip, operation_port, test_port
    )
    SELECT
        p.id,
        %s,
        %s,
        %s,
        %s,
        %s
    FROM sise_products p
    WHERE p.product_name = %s
    ON CONFLICT (product_id, service_type, market_type)
    DO UPDATE SET
        multicast_group_ip = EXCLUDED.multicast_group_ip,
        operation_port = EXCLUDED.operation_port,
        test_port = EXCLUDED.test_port,
        updated_at = CURRENT_TIMESTAMP
    """

    with conn.cursor() as cur:
        # 채널 데이터 삽입
        inserted_count = 0
        for idx, row in df.iterrows():
            try:
                cur.execute(insert_sql, (
                    row['service_type'],
                    row['market_type'],
                    row['multicast_group_ip'],
                    row['operation_port'],
                    row['test_port'],
                    row['product_name']
                ))
                inserted_count += 1
            except Exception as e:
                print(f"✗ 채널 데이터 삽입 실패 (행 {idx}): {e}")
                print(f"  데이터: {row.to_dict()}")

        conn.commit()
        print(f"✓ 채널 데이터 삽입 완료: {inserted_count}개 채널")
        return inserted_count

def verify_data(conn):
    """데이터 검증"""
    with conn.cursor() as cur:
        # 레코드 수 확인
        cur.execute("SELECT COUNT(*) FROM sise_products")
        product_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sise_channels")
        channel_count = cur.fetchone()[0]

        print(f"\n✓ 데이터 검증:")
        print(f"  - 상품: {product_count}개")
        print(f"  - 채널: {channel_count}개")

        # 샘플 데이터 출력 (JOIN)
        cur.execute("""
            SELECT
                p.product_name,
                p.line_speed,
                p.data_format,
                c.service_type,
                c.market_type,
                COUNT(*) OVER (PARTITION BY p.id) as channel_count
            FROM sise_products p
            LEFT JOIN sise_channels c ON p.id = c.product_id
            ORDER BY p.product_name, c.service_type, c.market_type
            LIMIT 5
        """)
        rows = cur.fetchall()
        print("\n=== 샘플 데이터 (상품 + 채널) ===")
        for row in rows:
            print(f"  {row[0]:<15} {row[1]:<10} {row[2]:<15} {row[3]:<15} {row[4]:<10} (총 {row[5]}개 채널)")

        # 외래키 무결성 확인
        cur.execute("""
            SELECT COUNT(*)
            FROM sise_channels c
            LEFT JOIN sise_products p ON c.product_id = p.id
            WHERE p.id IS NULL
        """)
        orphan_count = cur.fetchone()[0]

        if orphan_count == 0:
            print("\n✓ 외래키 무결성: 정상")
        else:
            print(f"\n✗ 외래키 무결성: {orphan_count}개 orphan 레코드 발견")

def main():
    try:
        # 데이터베이스 연결
        print(f"데이터베이스 연결 중... ({DB_CONFIG['host']}:{DB_CONFIG['port']})")
        conn = psycopg2.connect(**DB_CONFIG)
        print("✓ 데이터베이스 연결 성공\n")

        # 테이블 생성
        create_tables(conn)

        # Excel 데이터 로드
        df = load_excel_data(EXCEL_FILE)

        # 상품 데이터 삽입
        print("\n=== 1단계: 상품 마스터 데이터 삽입 ===")
        product_count = insert_products(conn, df)

        # 채널 데이터 삽입
        print("\n=== 2단계: 채널 정보 데이터 삽입 ===")
        channel_count = insert_channels(conn, df)

        # 데이터 검증
        print("\n=== 3단계: 데이터 검증 ===")
        verify_data(conn)

        conn.close()
        print("\n✅ 데이터 import 완료!")

    except FileNotFoundError:
        print(f"✗ 파일을 찾을 수 없습니다: {EXCEL_FILE}")
        sys.exit(1)
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
