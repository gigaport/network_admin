import logging
import re
import statistics
import json
import os
import requests
from datetime import datetime
import pytz 
from dotenv import load_dotenv

# [중요] 세션 관리를 위한 라이브러리
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()
#NETWORK_ID = os.getenv('NETWORK_ID')
#NETWORK_PASSWD = os.getenv('NETWORK_PASSWD')
NETWORK_ID = "nwcfg"
NETWORK_PASSWD = "Sprtmxm1@3"

def CallAristaAPI_Text(ip, cmds):
    """
    Arista eAPI를 호출하되, 세션을 길게 유지하지 않고 
    짧고 굵게(Short-lived) 통신하여 스레드 고갈을 방지합니다.
    """
    # 1호기 패킷 분석 결과 HTTP(80) 사용 확인됨
    url = f"http://{ip}/command-api"
    
    headers = {
        'Content-Type': 'application/json',
        'Connection': 'close'  # ★ 핵심: 장비에게 연결을 바로 끊자고 명시
    }
    
    payload = {
        'jsonrpc': '2.0',
        'method': 'runCmds',
        'params': {
            'version': 1,
            'cmds': cmds,
            'format': 'text' 
        },
        'id': 1
    }

    # ★ 핵심: Session을 열어서 쓰고, with 구문이 끝나면 강제로 닫아버림 (좀비 세션 방지)
    with requests.Session() as s:
        # 재시도(Retry) 금지 설정 (한번 안되면 바로 포기해야 스레드가 안밀림)
        retries = Retry(total=0, connect=0, read=0)
        adapter = HTTPAdapter(max_retries=retries)
        
        # http/https 둘 다 어댑터 장착
        s.mount('http://', adapter)
        s.mount('https://', adapter)
        
        # 헤더 설정
        s.headers.update(headers)

        try:
            # timeout=2 (2초 안에 답 없으면 칼같이 끊음)
            response = s.post(
                url, 
                data=json.dumps(payload), 
                auth=(NETWORK_ID, NETWORK_PASSWD),
                verify=False,
                timeout=2 
            )
            
            # [중요] 응답 받자마자 소켓 연결 강제 종료
            response.close() 
            
            if response.status_code != 200:
                # 로그 레벨 warning (너무 많이 뜨면 debug로 낮추세요)
                logger.warning(f"[{ip}] API Status: {response.status_code}")
                return None
                
            response_json = response.json()
            
            if 'error' in response_json:
                logger.warning(f"[{ip}] API Error: {response_json['error']}")
                return None

            return response_json.get('result', [])

        except Exception as e:
            # 타임아웃 등 에러 발생 시에도 세션은 with 구문에 의해 자동으로 닫힘
            logger.warning(f"[{ip}] Request Failed: {e}")
            return None


def GetAristaPtpInfo(device_item):
    """
    Arista 장비의 'show ptp monitor' 정보를 eAPI(Text)로 수집하여 파싱합니다.
    """
    hostname, info = device_item
    ip = info.get('ip')
    
    # 1. 결과 담을 그릇
    result = {
        "device_name": hostname,
        "current_time": "-",
        "offset": 0,           
        "mean_path_delay": 0,  
        "jitter": 0,           
        "packet_continuity": 0,
        "details": []          
    }

    try:
        cmds = ["show ptp monitor"] 
        
        # 위에서 만든 '짧게 끊어치는' API 함수 호출
        response = CallAristaAPI_Text(ip, cmds)

        output = ""
        
        # 응답 데이터 추출
        if response and len(response) > 0:
            cmd_result = response[0]
            if 'output' in cmd_result:
                output = cmd_result['output']
        else:
            # 실패 시 조용히 넘어감 (로그는 위 함수에서 찍음)
            pass

        # -------------------------------------------------------
        # [데이터 파싱]
        # -------------------------------------------------------
        if output:
            lines = output.strip().splitlines()
            offsets = []
            delays = []
            seq_ids = []
            
            # Regex: Arista Monitor 포맷 대응
            pattern = re.compile(r'(\S+)\s+(\d{2}:\d{2}:\d{2}\.\d+)\s+UTC\s+(\w{3})\s+(\d{2})\s+(\d{4})\s+([-\d]+)\s+([-\d]+)\s+([\d\.]+)\s+(\d+)')
            
            kst_zone = pytz.timezone('Asia/Seoul')
            utc_zone = pytz.timezone('UTC')

            count = 0
            for line in lines:
                if count >= 50: break # 최신 50개만

                match = pattern.search(line)
                if match:
                    iface, time_str, month, day, year, offset, delay, skew, seq_id = match.groups()
                    
                    # [시간 변환] UTC -> KST
                    full_time_str = f"{month} {day} {year} {time_str}"
                    dt_utc = datetime.strptime(full_time_str, "%b %d %Y %H:%M:%S.%f")
                    dt_utc = utc_zone.localize(dt_utc)
                    dt_kst = dt_utc.astimezone(kst_zone)
                    final_time = dt_kst.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                    if result['current_time'] == "-":
                        result['current_time'] = final_time

                    offset_val = int(offset)
                    delay_val = int(delay)
                    seq_val = int(seq_id)

                    offsets.append(offset_val)
                    delays.append(delay_val)
                    seq_ids.append(seq_val)

                    result['details'].append({
                        "port": iface,
                        "time": final_time,
                        "offset": offset_val,
                        "delay": delay_val,
                        "skew": skew,
                        "sequence_id": seq_val
                    })
                    count += 1

            # 통계 계산
            if offsets:
                result['offset'] = int(statistics.mean(offsets))
                result['mean_path_delay'] = int(statistics.mean(delays))
                
                if len(offsets) > 1:
                    result['jitter'] = round(statistics.stdev(offsets), 2)
                else:
                    result['jitter'] = 0

                seq_ids.sort()
                if len(seq_ids) > 0:
                    min_seq = seq_ids[0]
                    max_seq = seq_ids[-1]
                    expected = max_seq - min_seq + 1
                    if expected > 0:
                        continuity = (len(seq_ids) / expected) * 100
                        result['packet_continuity'] = round(continuity, 2)

    except Exception as e:
        logger.error(f"[{hostname}] PTP 파싱 에러: {e}")
        result['device_name'] = f"{hostname} (Error)"

    return result
