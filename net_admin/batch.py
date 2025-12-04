import json, logging, re, time, html, sys, asyncio, requests, os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pprint import pprint
from typing import List, Dict, Tuple, Union, Optional
## Netmiko 라이브러리
from netmiko import ConnectHandler
from utils.cisco_multicast import ProcessMulticastInfo
from utils.cisco_interface import ProcessCiscoInterfaceInfo
from utils.cisco_arp import ProcessCiscoArpInfo

## 장비관리 라이브러리
from genie.testbed import load

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/batch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

# FastAPI 웹훅 URL 설정
WEBHOOK_BASE_URL = "http://fastapi:8000/api/v1/webhook"

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
FILE_PATH = "/app/data/"

# 공통 정보 수집 API URL
CISCO_COMMON_COLLECT_API_URL = [
    {
        "market_gubn":"pr",
        "url":"http://fastapi:8000/api/v1/network/collect/cisco/pr"
    },
    {
        "market_gubn":"ts",
        "url":"http://fastapi:8000/api/v1/network/collect/cisco/ts"
    }
]

# batch.py main 함수
def main():
    # CISCO 공통 정보 수집
    for data in CISCO_COMMON_COLLECT_API_URL:
        logger.info(f"[{data['market_gubn']}] START_BATCH_PROCESS!!!!!")

        # API를 사용하여 CISCO 공통정보 수집
        response = requests.get(data["url"])

        if response.status_code == 200:
            try:
                logger.info("✅ API 요청 성공")
                response_json = response.json()

                # response_json = response.json()
                # result = {"data": [item["data"] for item in response_json['data']]}
                # logger.info(f"[[DEBUG]{data['market_gubn']}] RESPONSE_RESULT: {json.dumps(response_json, indent=4, ensure_ascii=False)}")

                SaveToCommonInfoJson(response_json, data["market_gubn"])

                # CISCO 멀티캐스트 정보 처리
                cisco_multicast_info = ProcessMulticastInfo(response_json, data["market_gubn"])
                # logger.info(f"[{data['market_gubn']}] CISCO_MULTICAST_INFO: {json.dumps(cisco_multicast_info, indent=4, ensure_ascii=False)}")
                SaveToMulticastJson(cisco_multicast_info, data["market_gubn"])

                cisco_interface_info = ProcessCiscoInterfaceInfo(response_json, data["market_gubn"])
                # logger.info(f"[DEBUG] [{data['market_gubn']}] CISCO_INTERFACE_INFO: {json.dumps(cisco_interface_info, indent=4, ensure_ascii=False)}")
                SaveToInterfaceJson(cisco_interface_info, data["market_gubn"])

                cisco_arp_info = ProcessCiscoArpInfo(response_json, data["market_gubn"])
                # # logger.info(f"[DEBUG] [{data['market_gubn']}] CISCO_ARP_INFO: {json.dumps(cisco_arp_info, indent=4, ensure_ascii=False)}")
                SaveToArpJson(cisco_arp_info, data["market_gubn"])

                # ## 확인필요 결과가 있을경우 슬랙으로 메세지 전송
                check_multicast_info(data["market_gubn"], cisco_multicast_info)

            except ValueError as e:
                logger.error("⚠️ JSON 디코딩 실패: %s", e)
                logger.error("응답 내용: %s", response.text)
        else:
            logger.error("❌ API 요청 실패 - 상태코드: %s", response.status_code)
            logger.error("응답 내용: %s", response.text)


def send_slack_message(message_info: Dict):
    """웹훅을 통해 Slack 메시지 전송"""
    logger.info("Slack 메시지 전송 요청: %s", message_info)
    
    try:
        # 웹훅 URL 구성
        webhook_url = f"{WEBHOOK_BASE_URL}/batch/multicast"
        
        # HTTP 요청으로 웹훅 호출
        response = requests.post(
            webhook_url,
            json=message_info,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('result'):
                logger.info("웹훅을 통한 메시지 전송 성공: %s", result.get('message', 'Success'))
            else:
                logger.error("웹훅 응답 오류: %s", result.get('detail', 'Unknown error'))
        else:
            logger.error("웹훅 호출 실패 - 상태코드: %s, 응답: %s", response.status_code, response.text)
            
    except requests.exceptions.RequestException as e:
        logger.error("웹훅 요청 실패: %s", e)
    except Exception as e:
        logger.error("메시지 전송 중 예상치 못한 오류: %s", e)
    
    # 전송 후 잠시 대기 (과도한 요청 방지)
    time.sleep(1)

# 멀티캐스트 정보 확인
# market_gubn: pr, ts
def check_multicast_info(market_gubn, members_mroute):
    path = f"/app/common/members_info.json"
    members_info:Dict = OpenJsonFile(path)

    path = f"/app/common/{market_gubn}_mpr_multicast_info.json"
    mpr_multicast_info:Dict = OpenJsonFile(path)

    logger.info(f"[DEBUG] rws_check_multicast_info")

    ## 데이터 유무 검증
    if members_mroute and members_info and mpr_multicast_info:
    ## 01. member_info <- 시세 멀티캐스트그룹 수신 개수 삽입
    ## 02. member_mroute <- member_info 정보 삽입
        merge_members_mroute = merge_multicast_group_count(members_mroute['data'], mpr_multicast_info)
        # print(f"[merge_members_info]\n{merge_members_info}\n\n")
        # print(f"[members_mroute['data']]\n{members_mroute['data']}")

        response_data:List = create_member_sise_info(merge_members_mroute, members_info, market_gubn)

# openJsonFile = lambda path: openJsonFile

def merge_multicast_group_count(members_mroute:list, mpr_multicast_info:Dict):
    for idx, device in enumerate(members_mroute):
        # products 키값 유무 확인하는 코드
        if "products" not in device:
            logger.warning("Device %s does not have 'products' key.", device['device_name'])
            break
        products = device["products"]
        total = 0

        for product in products:
            if product in mpr_multicast_info:
                total += mpr_multicast_info[product].get("multicast_group_count", 0)

        members_mroute[idx]["multicast_group_count"] = total

    return members_mroute


def create_member_sise_info(members_mroute:list, members_info:Dict, market_gubn:str):
    logger.info(f"[DEBUG] rws_create_member_sise_info")

    result = []
    member_no = 0
    member_code = ""
    member_name = ""
    device_name = ""
    device_os = ""
    products = ""
    pim_rp = ""
    product_cnt = 0
    mroute_cnt = 0
    oif_cnt = 0
    connected_server_cnt = 0
    min_update = ""
    bfd_nbr = ""
    rpf_nbr = ""
    org_output = ""
    check_result = ""
    type = ""
    icon = ""


    for idx, device in enumerate(members_mroute):
        if device['device_os'] == 'iosxe':
            device_os_key = ''
        elif device['device_os'] == 'nxos':
            device_os_key = 'default'
        
        device_name = device['device_name']
        device_os = device['device_os']
        pim_rp = device['rp_addresses']
        products = device['products']
        product_cnt = device['multicast_group_count']
        connected_server_cnt = device['connected_server_count']
        org_output = device['mroute'][0]['org_output'] ## ip mroute 정보만 표기하기 위함 show ip pim neighbor는 X

        # print(f"[multicast_group] : {device['mroute']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']}")
        # multicast_group = device['mroute']['parsed_output']['vrf'][device_os_key]['address_family']['ipv4']['multicast_group']
    
        mroute_cnt = device['valid_source_address_count'] if 'valid_source_address_count' in device else 0
        oif_cnt = device['valid_oif_count'] if 'valid_oif_count' in device else 0
        min_update = device['min_uptime'] if 'min_uptime' in device else '확인필요'
        rpf_nbr = device['rpf_nbrs'] if 'rpf_nbrs' in device else '확인필요'

        second_octet = device['mgmt_ip'].split(".")[1] # IP두번째 자리 코드값 추출
        if second_octet in members_info:
            member_no = second_octet
            member_code = members_info[second_octet]['member_code']
            member_name = members_info[second_octet]['member_name']

        ## 멀티캐스트 시세 정상 확인
        ## 시세상품 멀티캐스트 그룹 카운트 == 장비 mroute 카운트 == vlan 1100 OIF 카운트 비교
        if product_cnt == mroute_cnt == oif_cnt:
            check_result = '정상확인'
            type = "success"
            icon = "fas fa-check"
        elif connected_server_cnt == 0:
            check_result = '회원사연결서버없음'
            type = "primary"
            icon = "fas fa-check"
        elif mroute_cnt > product_cnt:
            check_result = '정상그룹개수초과'
            type = "warning"
            icon = "fas fa-exclamation-triangle"
        else:
            check_result = '확인필요'
            type = "danger"
            icon = "fas fa-x-square"
            info = {
                "market_gubn": market_gubn,
                "member_name": member_name,
                "device_name": device_name,
                "pim_rp": pim_rp,
                "products": products,
                "product_cnt": product_cnt,
                "mroute_cnt": mroute_cnt,
                "oif_cnt": oif_cnt,
                "rpf_nbr": rpf_nbr,
                "connected_server_cnt": connected_server_cnt,
                "check_result": check_result
            }

            send_slack_message(info)

        temp = {
            "id" : idx+1,
            "member_no": member_no,
            "member_code": member_code,
            "member_name": member_name,
            "device_name": device_name,
            "device_os": device_os,
            "products": products,
            "pim_rp": pim_rp,
            "product_cnt": product_cnt,
            "mroute_cnt": mroute_cnt,
            "oif_cnt": oif_cnt,
            "min_update": min_update,
            "bfd_nbr": bfd_nbr,
            "rpf_nbr": rpf_nbr,
            "org_output": org_output,
            "check_result": check_result,
            "check_result_badge": { "type": type, "icon": icon }
        }

        result.append(temp)

    logger.info("[DEBUG] CHECK_MUTLICAST_SUCCESS!!")
    return result

def SaveToMulticastJson(data, market_gubn):
    logger.info("SaveToMulticastJson...")
    ## write json
    file_name = f"{FILE_PATH}{market_gubn}_members_mroute.json"

    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def SaveToCommonInfoJson(data, market_gubn):
    logger.info("SaveToCommonInfoJson...")
    file_name = f"{FILE_PATH}{market_gubn}_cisco_common_info.json"
    logger.info("[DEBUG] 파일명: %s", file_name)
    logger.info("[DEBUG] 데이터 타입: %s", type(data))
    logger.info("[DEBUG] 데이터 길이: %s", len(data) if isinstance(data, (list, dict)) else 'N/A')
    
    try:
        with open(file_name, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=4, ensure_ascii=False)
        logger.info("[SUCCESS] 파일 저장 완료: %s", file_name)
        
        # 파일 크기 확인
        import os
        file_size = os.path.getsize(file_name)
        logger.info("[DEBUG] 저장된 파일 크기: %s bytes", file_size)
        
    except Exception as e:
        logger.error("[ERROR] 파일 저장 실패: %s", e)
        logger.error("[ERROR] 파일명: %s", file_name)
        logger.error("[ERROR] 데이터 타입: %s", type(data))
        raise e

def SaveToInterfaceJson(data, market_gubn):
    logger.info("SaveToInterfaceJson...")
    file_name = f"{FILE_PATH}{market_gubn}_cisco_interface_info.json"
    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def SaveToArpJson(data, market_gubn):
    logger.info("SaveToArpJson...")
    file_name = f"{FILE_PATH}{market_gubn}_cisco_arp_info.json"
    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def OpenJsonFile(path):
    data = {}
    try:
        with open(path, 'rt', encoding='UTF8') as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        logger.error("파일이 존재하지 않습니다: %s", path)
    except json.JSONDecodeError:
        logger.error("JSON 형식이 잘못되었습니다.: %s", path)

    return data

if __name__ == "__main__":
    main()
    # uvicorn.run(app, host="0.0.0.0", port=5000)
