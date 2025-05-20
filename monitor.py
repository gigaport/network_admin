from repynery import Repynery
from datetime import datetime, timezone, timedelta
import json
import re
import os
import time
import requests

# === [ 사용자 설정 영역 ] ===
feedname = "COR_ASN"
tag_values = ["ALL_SECUTIES","KB","KR_HQ","KR_KT","MR", "KW", "SH","NH","SS","KRX","STOCK-NET"]  # 여러 태그 지정 (리스트로 작성)
KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)
E_NOW_DATETIME = int(NOW_KST.timestamp())
THIRTY_SECONDS_AGO = NOW_KST - timedelta(seconds=60)
E_THIRTY_SECONDS_AGO = int(THIRTY_SECONDS_AGO.timestamp())
pre_from_time_str = "2025-05-20 07:58"
regular_from_time_str = "2025-05-20 08:58"
after_from_time_str = "2025-05-20 15:38"
test_from_time_str = "2025-05-20 23:39"
to_time_str   = "2025-05-20 08:51"
bind_value    = 61
# ===========================


def to_epoch(kst_string):
    dt = datetime.strptime(kst_string, "%Y-%m-%d %H:%M")
    dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
    return int(dt.timestamp())

def epoch_to_kst(epoch_time):
    dt = datetime.fromtimestamp(int(epoch_time), tz=timezone(timedelta(hours=9)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def epoch_to_kst_filename(epoch_time):
    dt = datetime.fromtimestamp(int(epoch_time), tz=timezone(timedelta(hours=9)))
    return dt.strftime("%Y%m%d%H%M%S")

def calc_traffic(data):
    try:
        data /= 1000000
        return f'{round(data, 1)}Mbps'
        # if abs(data) >= 1000000000 :
        #     data /= 1000000000
        #     return f'{round(data, 1)}Gbps'
        # else :
        #     data /= 1000000
        #     return f'{round(data, 1)}Mbps'
    except Exception as e:
        print(f"error : {e}")    

from_epoch = to_epoch(test_from_time_str)
to_epoch_val = to_epoch(to_time_str)

from_kst_for_filename = epoch_to_kst_filename(from_epoch)
to_kst_for_filename = epoch_to_kst_filename(to_epoch_val)

# downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
# filename = f"{from_kst_for_filename}_{to_kst_for_filename}_{'_'.join(tag_values)}.csv"
# filepath = os.path.join(downloads_folder, filename)

# 서버 접속 및 로그인
print("Log in")
r1 = Repynery(False, "172.24.32.47", 8080, "lampad", "Sprtmxm1@3")
if not r1.login():
    print("Failed to login. Check connection information")
    exit(-1)
else:
    print(f'Logged in. Token: {r1.token}, Tag: {r1.tag}')

# 결과 저장용 딕셔너리
results_by_tag = {}

for tag in tag_values:
    print(f"\n=== Processing Tag: {tag} ===")
    print(f"E_NOW_DATETIME : {E_NOW_DATETIME}, E_THIRTY_SECONDS_AGO : {E_THIRTY_SECONDS_AGO}")
    
    # 데이터 요청
    error = r1.request_data_generation(feedname, {
        'from': from_epoch,
        'to': E_NOW_DATETIME,
        'type': 'bps',
        'base': 'bytes',
        'tags': tag
    })
    if error != '':
        print(f"Error for tag {tag}: {error}")
        continue

    # 결과 조회
    get_parameters = {'bind': bind_value}
    status = r1.get_result({})
    while status != 200:
        if status < 300:
            status = r1.get_result(get_parameters)
        else:
            print(f"Failed to get result for tag {tag}. Status code: {status}")
            continue

    # 결과 저장
    try:
        decoded = r1.result.decode('utf-8')
        fixed_json = re.sub(r'(\w+):"', r'"\1":"', decoded)
        fixed_json = re.sub(r'(\w+):', r'"\1":', fixed_json)
        data = json.loads(fixed_json)
        top_unit = calc_traffic(data[0]['top'])
        print(f">> {tag} : {top_unit}")

        results_by_tag[tag] = {epoch_to_kst(entry['timestamp']): entry.get('top', '') for entry in data}
    except Exception as e:
        print(f"❌ Failed to process result for tag {tag}: {e}")



# 결과 출력 및 CSV 저장
#print("\n==== 분석 결과 (엑셀 붙여넣기용) ====\n")

# 모든 타임스탬프 통합 (정렬)
#all_timestamps = sorted(set(ts for tag_data in results_by_tag.values() for ts in tag_data))

# ✅ 콘솔 출력 헤더
#print("DATE\t" + "\t".join(tag_values))