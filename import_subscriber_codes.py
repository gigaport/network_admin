#!/usr/bin/env python3
"""
가입자코드기준.xlsx 파일을 읽어서 subscriber_codes 테이블에 데이터 입력
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
    excel_path = '/home/sysmon/data/가입자코드기준.xlsx'

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

        # 기존 데이터 삭제 (선택사항)
        print("\n기존 데이터 삭제 중...")
        cur.execute("DELETE FROM subscriber_codes")
        conn.commit()

        # 데이터 입력
        print("\n데이터 입력 중...")
        insert_query = """
            INSERT INTO subscriber_codes (
                member_code, member_number, company_name, subscription_type, is_pb
            ) VALUES (%s, %s, %s, %s, %s)
        """

        success_count = 0
        error_count = 0

        for idx, row in df.iterrows():
            try:
                # 컬럼명은 실제 Excel 파일 구조에 맞게 조정 필요
                # 일단 가능한 컬럼명들을 체크
                member_code = None
                member_number = None
                company_name = None
                subscription_type = None
                is_pb = False

                # 컬럼명 매칭 (Excel 파일 구조에 따라 조정)
                for col in df.columns:
                    col_lower = str(col).lower()
                    if '회원사코드' in col or 'member_code' in col_lower:
                        member_code = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '회원사번호' in col or 'member_number' in col_lower:
                        try:
                            member_number = int(row[col]) if pd.notna(row[col]) else None
                        except:
                            member_number = None
                    elif '회사명' in col or 'company' in col_lower:
                        company_name = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif '가입구분' in col or '가입유형' in col or 'subscription' in col_lower:
                        subscription_type = str(row[col]).strip() if pd.notna(row[col]) else None
                    elif col == 'PB' or 'pb' in col_lower:
                        is_pb = bool(row[col]) if pd.notna(row[col]) else False

                # 필수 필드 확인
                if not member_code or member_number is None or not company_name or not subscription_type:
                    print(f"  건너뜀 (행 {idx+1}): 필수 필드 누락 - code={member_code}, num={member_number}, name={company_name}, type={subscription_type}")
                    error_count += 1
                    continue

                # 데이터 입력
                cur.execute(insert_query, (
                    member_code,
                    member_number,
                    company_name,
                    subscription_type,
                    is_pb
                ))

                success_count += 1
                print(f"  ✓ 입력 완료: {member_code} - {company_name}")

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
    print("=== 가입자 코드 데이터 임포트 ===\n")

    # 1. Excel 파일 읽기
    df = read_excel_file()

    # 2. 데이터 입력
    insert_data(df)

if __name__ == '__main__':
    main()
