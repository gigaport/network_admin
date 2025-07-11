# Netbox 오픈소스 API를 사용하여
# NetBox에 등록된 네트워크 장비 정보를 가져오는 코드입니다.

import requests
import json
import os
from dotenv import load_dotenv
from typing import Dict, Any 
from requests.auth import HTTPBasicAuth

# .env 파일에서 환경 변수 로드
load_dotenv()

NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
NETBOX_URL = os.getenv("NETBOX_URL", "http://172.30.32.221:80")

def get_netbox_device_info() -> Dict[str, Any]:
    """
    NetBox API를 사용하여 네트워크 장비 정보를 가져옵니다.
    
    :param netbox_url: NetBox API URL
    :param netbox_token: NetBox API 토큰
    :return: 네트워크 장비 정보 딕셔너리
    """
    headers = {
        'Authorization': f'Token {NETBOX_TOKEN}',
        'Content-Type': 'application/json',
    }

    response = requests.get(f"{NETBOX_URL}/api/dcim/devices/", headers=headers)

    if response.status_code == 200:
        print(f"Successfully fetched data from NetBox: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.json()
    else:
        raise Exception(f"Failed to fetch data from NetBox: {response.status_code} - {response.text}")
    

if __name__ == "__main__":
    main()
    # uvicorn.run(app, host="0.0.0.0", port=5000)
def main():
    try:
        device_info = get_netbox_device_info()
        print(f"Device Info: {device_info}")
    except Exception as e:
        print(f"Error fetching device info: {e}")