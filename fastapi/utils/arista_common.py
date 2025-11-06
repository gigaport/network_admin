import pytz, sys
import requests, json, codecs, threading, asyncio, paramiko, time, concurrent.futures, re, os
import logging
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
# from deepdiff import DeepDiff
from pathlib import Path

# 로깅 설정
logger = logging.getLogger(__name__)

# .env 파일에서 환경 변수 로드
load_dotenv()

NETWORK_ID = os.getenv('NETWORK_ID')
NETWORK_PASSWD = os.getenv('NETWORK_PASSWD')

NOW_DATETIME    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def CallAristaAPI(ip, cmds, params=None):
    # eAPI 엔드포인트 URL
    url = f"http://{ip}/command-api"

    # 요청에 사용할 헤더 설정
    headers = {
        'Content-Type': 'application/json'
    }

    # 요청할 명령어와 매개변수
    payload = {
        'jsonrpc': '2.0',
        'method': 'runCmds',
        'params': {
            'version': 1,
            'cmds': cmds,
            'format': 'json'
        },
        'id': 1
    }
    # eAPI 요청 보내기
    try:
        response = requests.post(
            url, 
            headers=headers, 
            data=json.dumps(payload), 
            auth=(NETWORK_ID, NETWORK_PASSWD),
            verify=False
        )
        # 상태 코드 확인
        if response.status_code != 200:
            logger.error(f"Error: Received status code {response.status_code}")
            return None
        # 응답이 비어 있는지 확인
        if not response.text.strip():
            logger.error("Response body is empty")
            return None

        # JSON 확인 및 파싱
        if 'application/json' in response.headers.get('Content-Type', ''):
            try:
                response_json = response.json()
                # return response_json
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON")
                logger.error(f"Response Content: {response.text}")
                return None
        else:
            logger.error("Response is not JSON")
            logger.error(f"Response Content: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        return None

    response_json = response.json()
    if 'error' in response_json:
        logger.error(f"Error in response: {response_json['error']}")
        return None
    
    data = response_json.get('result', [])
    if not data:
        logger.warning("No data found in response")
        return None

    return data
