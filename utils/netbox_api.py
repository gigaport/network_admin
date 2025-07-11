# Netbox 오픈소스 API를 사용하여
# NetBox에 등록된 네트워크 장비 정보를 가져오는 코드입니다.

import requests
import json
import os
import sys
from dotenv import load_dotenv
from typing import Dict, Any 
from requests.auth import HTTPBasicAuth

# .env 파일에서 환경 변수 로드
load_dotenv()

NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
NETBOX_URL = os.getenv("NETBOX_URL", "http://172.30.32.221:80")

def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else ""
    manufacturer = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        device_info = get_netbox_device_info(tag=tag, manufacturer=manufacturer)    
        print(f"Device Info: {device_info}")
    except Exception as e:
        print(f"Error fetching device info: {e}")

# tag값이 없을경우 전체 장비 정보를 가져옵니다.
def get_netbox_device_info(tag: str = "", manufacturer: str = "") -> Dict[str, Any]:
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

    # tag 값을 사용하여 특정 장비 정보를 가져옵니다.
    # tag 값이 없을경우 전체 장비 정보를 가져옵니다.
    # 예시: tag 값이 'test'인 장비 정보를 가져옵니다.
    # response = requests.get(f"{NETBOX_URL}/api/dcim/devices/?tag=test", headers=headers)
    # manufacturer = "Cisco" 값도 추가하여 특정 제조사 장비만 가져올 수 있습니다.
    # response = requests.get(f"{NETBOX_URL}/api/dcim/devices/?manufacturer=Cisco&tag={tag}", headers=headers)
    # tag 값이 없을경우 전체 장비 정보를 가져옵니다.
    if not tag:
        response = requests.get(f"{NETBOX_URL}/api/dcim/devices/", headers=headers)
    else:
        # tag 값이 있을 경우 해당 tag를 가진 장비 정보를 가져옵니다.
        # 예시: tag 값이 'network'인 장비 정보를 가져옵니다.
        # 2023-10-30 현재 NetBox API에서 tag 필터링은 지원하지 않습니다.
        # 따라서, tag 값을 사용하여 필터링할 수 없습니다.
        # 대신, 모든 장비 정보를 가져온 후, 클라이언트 측에서 필터링해야 합니다.
        response = requests.get(f"{NETBOX_URL}/api/dcim/devices/?tag={tag}&manufacturer={manufacturer}", headers=headers)

    if response.status_code == 200:
        print(f"Successfully fetched data from NetBox: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.json()
    else:
        raise Exception(f"Failed to fetch data from NetBox: {response.status_code} - {response.text}")
    

if __name__ == "__main__":
    main()
    # uvicorn.run(app, host="0.0.0.0", port=5000)
