#!/usr/bin/env python3
"""
고객사주소.xlsx 파일을 읽어서 customer_addresses 테이블에 데이터 입력
"""
import pandas as pd
import psycopg2
from psycopg2 import sql
import sys

# 데이터베이스 연결 정보
DB_CONFIG = {
    'dbname': 'nxt_nms_db',
    'user': 'nextrade',
    'password': 'Sprtmxm1@3',
    'host': 'localhost',
    'port': '5432'
}

def read_excel_file():
    """Excel 파일 읽기"""
    excel_path = '/home/sysmon/data/고객사주소.xlsx'

    try:
        # Excel 파일 읽기
        df = pd.read_excel(excel_path)
        print(f"✓ Excel 파일 읽기 성공: {len(df)}행")
        print(f"\n컬럼 목록:")
        for i, col in enumerate(df.columns):
            print(f"  {i}: {col}")
        print(f"\n첫 5행 데이터:")
        print(df.head())

        return df
    except Exception as e:
        print(f"✗ Excel 파일 읽기 실패: {e}")
        sys.exit(1)

def insert_data(df):
    """데이터베이스에 데이터 입력"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 기존 데이터 삭제
        print("\n기존 데이터 삭제 중...")
        cur.execute("DELETE FROM customer_addresses")
        conn.commit()

        # 데이터 입력
        print("\n데이터 입력 중...")
        insert_query = """
            INSERT INTO customer_addresses (
                member_code, datacenter_code, post_code, main_address,
                detailed_address, summary_address
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        success_count = 0
        error_count = 0

        for idx, row in df.iterrows():
            try:
                member_code = None
                datacenter_code = None
                post_code = None
                main_address = None
                detailed_address = None
                summary_address = None

                # 컬럼명 매칭
                for col in df.columns:
                    col_str = str(col)
                    if '회원사코드' in col_str or 'member_code' in col_str:
                        member_code = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '데이터센터코드' in col_str or 'datacenter_code' in col_str or '데이터센터' in col_str:
                        datacenter_code = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '우편번호' in col_str or 'post_code' in col_str or '우편' in col_str:
                        post_code = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '주소' in col_str and '상세' not in col_str and '요약' not in col_str:
                        main_address = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '상세주소' in col_str or 'detailed' in col_str:
                        detailed_address = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '요약주소' in col_str or 'summary' in col_str:
                        summary_address = str(row[col]).strip() if pd.notna(row[col]) else None

                # 필수 필드 확인
                if not member_code or not datacenter_code:
                    print(f"  건너뜀 (행 {idx+1}): 필수 필드 누락 - code={member_code}, dc={datacenter_code}")
                    error_count += 1
                    continue

                # summary_address가 없으면 main_address로 대체
                if not summary_address:
                    summary_address = main_address if main_address else '주소 없음'

                # 데이터 입력
                cur.execute(insert_query, (
                    member_code,
                    datacenter_code,
                    post_code,
                    main_address,
                    detailed_address,
                    summary_address
                ))

                success_count += 1
                print(f"  ✓ 입력 완료: {member_code} - {datacenter_code}")

            except Exception as e:
                error_count += 1
                print(f"  ✗ 입력 실패 (행 {idx+1}): {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()

        print(f"\n=== 완료 ===")
        print(f"성공: {success_count}건")
        print(f"실패: {error_count}건")

    except Exception as e:
        print(f"✗ 데이터베이스 오류: {e}")
        sys.exit(1)

def main():
    print("=== 고객사 주소 데이터 임포트 ===\n")

    # 1. Excel 파일 읽기
    df = read_excel_file()

    # 2. 데이터 입력
    insert_data(df)

if __name__ == '__main__':
    main()
