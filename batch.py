import json, logging, re, time, html, sys, asyncio, requests, os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pprint import pprint
from typing import List, Dict, Tuple, Union, Optional
## Netmiko 라이브러리
from netmiko import ConnectHandler
## 장비관리 라이브러리
from genie.testbed import load
## 장비정보 파싱 라이브러리리
## IOSXE
from genie.libs.parser.iosxe.show_interface import ShowInterfaces
from genie.libs.parser.iosxe.show_mcast import ShowIpMroute
from genie.libs.parser.iosxe.show_pim import ShowPimNeighbor
## NXOS
from genie.libs.parser.nxos.show_mcast import ShowIpMrouteVrfAll
from genie.libs.parser.nxos.show_pim import ShowIpPimRp

# app = FastAPI()

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=60)

slack_token = os.getenv("SLACK_TOKEN")
client = WebClient(token=slack_token)

TODAY_STR = datetime.today().strftime('%Y-%m-%d')
TS_DEVICES = load('common/ts_member_mpr.yaml')
PR_DEVICES = load('common/pr_member_mpr.yaml')
FILE_PATH = "./data/"

NXOS_CMDS = [
    {
        "key": "show_ip_mroute_source-tree",
        "value": "show ip mroute source-tree"
    },
    {
        "key": "show_ip_pim_rp",
        "value": "show ip pim rp"
    }     
]

IOSXE_CMDS = [
    {
        "key": "show_ip_mroute",
        "value": "show ip mroute"
    }
]

# 멀티캐스트 수집 API URL
API_URL = [
    {
        "market_gubn":"pr",
        "url":"http://127.0.0.1:8000/api/collect/pr"
    },
    {
        "market_gubn":"ts",
        "url":"http://127.0.0.1:8000/api/collect/ts"
    }
]

# batch.py main 함수
def main():
    for data in API_URL:
        print("START_batch_proccess")
        response = requests.get(data["url"])
        response_json = response.json()

        result = {"data": [item["data"] for item in response_json]}

        ## 확인필요 결과가 있을경우 슬랙으로 메세지 전송
        check_multicast_info(data["market_gubn"], result)

        print(data["url"])
        save_to_json(result, data["market_gubn"])


def send_slack_message(message_info: Dict):
    print(message_info)
    if message_info['market_gubn'] == "pr":
        market_gubn = "가동"
    elif message_info['market_gubn'] == "ts":
        market_gubn = "테스트"
    elif message_info['market_gubn'] == "dr":
        market_gubn = "DR"
    channel = "#network-alert-multicast"
    try:
        response = client.chat_postMessage(
            channel=channel,  # 예: "#general" 또는 "C12345678"
            text= f":alert: *({market_gubn}){message_info['member_name']} 시세수신 이상* :alert:",
            attachments=[
                {
                    "color": "danger",
                    "title": f"대상회원사 : `{message_info['member_name']}`",
                    "text": (
                        f"*- 장비이름: {message_info['device_name']}*\n"
                        f"- 가입상품: `{message_info['products']}`\n"
                        f"- PIM_RP: {message_info['pim_rp']}\n"
                        f"- 기준 mroute: {message_info['product_cnt']}\n"
                        f"- 현재 mroute: {message_info['mroute_cnt']}\n"
                        f"- 현재 oif_cnt: {message_info['oif_cnt']}\n"
                        f"- RPF_NBR: `{message_info['rpf_nbr']}`\n"
                    ),
                    "mrkdwn_in": ["text", "title"]
                }
            ]
        )
        print("메시지 전송 성공:", response["ts"])
        time.sleep(1)


    except SlackApiError as e:
        print("메시지 전송 실패:", e.response["error"])

# 멀티캐스트 정보 확인
# market_gubn: pr, ts
def check_multicast_info(market_gubn, members_mroute):
    path = f"./common/members_info.json"
    members_info:Dict = openJsonFile(path)

    path = f"./common/{market_gubn}_mpr_multicast_info.json"
    mpr_multicast_info:Dict = openJsonFile(path)

    ## 데이터 유무 검증
    if members_mroute and members_info and mpr_multicast_info:
    ## 01. member_info <- 시세 멀티캐스트그룹 수신 개수 삽입
    ## 02. member_mroute <- member_info 정보 삽입
        merge_members_mroute = merge_multicast_group_count(members_mroute['data'], mpr_multicast_info)
        # print(f"[merge_members_info]\n{merge_members_info}\n\n")
        # print(f"[members_mroute['data']]\n{members_mroute['data']}")

        response_data:List = create_member_sise_info(merge_members_mroute, members_info, market_gubn)

# openJsonFile = lambda path: openJsonFile
def openJsonFile(path):
    data = {}
    try:
        with open(path, 'rt', encoding='UTF8') as json_file:
            data = json.load(json_file)
    except FileNotFoundError:
        print(f"파일이 존재하지 않습니다: {path}")
    except json.JSONDecodeError:
        print(f"JSON 형식이 잘못되었습니다.: {path}")

    return data

def merge_multicast_group_count(members_mroute:list, mpr_multicast_info:Dict):
    for idx, device in enumerate(members_mroute):
        products = device["products"]
        total = 0

        for product in products:
            if product in mpr_multicast_info:
                total += mpr_multicast_info[product].get("multicast_group_count", 0)

        members_mroute[idx]["multicast_group_count"] = total

    return members_mroute


def create_member_sise_info(members_mroute:list, members_info:Dict, market_gubn:str):
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
        org_output = device['mroute'][0]['org_output'] ## show ip mroute 정보만 표기하기 위함 show ip pim neighbor는 X

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

    return result

def save_to_json(data, market_gubn):
    print("save...")
    ## write json
    file_name = f"{FILE_PATH}{market_gubn}_members_mroute_{TODAY_STR}.json"

    with open(file_name, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
    # uvicorn.run(app, host="0.0.0.0", port=5000)
